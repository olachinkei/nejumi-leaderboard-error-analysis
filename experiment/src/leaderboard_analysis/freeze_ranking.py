from __future__ import annotations

import csv
import json
import math
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import quote
from zoneinfo import ZoneInfo

import requests
import wandb
from dotenv import load_dotenv

from leaderboard_analysis.common import (
    MANIFEST_DIR,
    PROJECT_ROOT,
    RAW_DIR,
    WORKSPACE_ROOT,
    json_hash,
    load_config,
    read_json,
    sha256_file,
    write_json,
)

PRIMARY_SCORE_CATEGORIES = [
    "GLP_応用的言語性能",
    "GLP_基礎的言語性能",
    "ALT_制御性",
    "ALT_倫理・道徳",
    "ALT_毒性",
    "ALT_バイアス",
    "ALT_真実性",
    "ALT_堅牢性",
    "GLP_推論能力",
    "GLP_知識・質問応答",
    "GLP_アプリケーション開発",
]


def find_report(api: wandb.Api, entity: str, project: str, report_id: str):
    reports = api.reports(f"{entity}/{project}", per_page=100)[:100]
    matches = [report for report in reports if report.id == report_id]
    if len(matches) != 1:
        raise RuntimeError(f"Expected one report {report_id}, found {len(matches)}")
    return matches[0]


def leaderboard_grid(spec: dict[str, Any]) -> tuple[int, dict[str, Any]]:
    candidates: list[tuple[int, dict[str, Any]]] = []
    for index, block in enumerate(spec.get("blocks", [])):
        metadata = block.get("metadata", {}) if isinstance(block, dict) else {}
        if not metadata.get("runSets"):
            continue
        serialized = str(metadata)
        if "leaderboard_table" in serialized and "TOTAL_SCORE" in serialized:
            candidates.append((index, metadata))
    if len(candidates) != 1:
        raise RuntimeError(f"Expected one leaderboard grid, found {len(candidates)}")
    return candidates[0]


def main_table_panel(metadata: dict[str, Any]) -> tuple[int, dict[str, Any]]:
    panels = metadata.get("panelBankSectionConfig", {}).get("panels", [])
    candidates: list[tuple[int, dict[str, Any]]] = []
    for index, panel in enumerate(panels):
        panel2 = panel.get("config", {}).get("panel2Config", {})
        child = panel2.get("panelConfig", {}).get("childConfig", {})
        state = child.get("tableState")
        if not isinstance(state, dict):
            continue
        serialized = str(panel2)
        if "leaderboard_table" not in serialized or "TOTAL_SCORE" not in serialized:
            continue
        prefilter = state.get("preFilterFunction")
        if isinstance(prefilter, dict) and prefilter.get("nodeType") != "void":
            continue
        candidates.append((index, panel2))
    if len(candidates) != 1:
        raise RuntimeError(
            f"Expected one unfiltered leaderboard table panel, found {len(candidates)}"
        )
    return candidates[0]


def public_filter_from_report(runset: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    report_filters = runset.get("filters", {}).get("filters", [])
    if len(report_filters) != 2:
        raise RuntimeError("Unexpected active runset filter shape")

    nested = report_filters[0].get("filters", [])
    special = report_filters[1]
    tag_any: list[str] | None = None
    required_tag: str | None = None
    for item in nested:
        key = item.get("key", {})
        if key.get("section") != "tags":
            continue
        if key.get("name") == "*" and item.get("op") == "IN":
            tag_any = list(item.get("value", []))
        elif item.get("op") == "!=" and item.get("value") is False:
            required_tag = key.get("name")

    special_key = special.get("key", {})
    special_names = list(special.get("value", []))
    if (
        not tag_any
        or not required_tag
        or special_key.get("section") != "run"
        or special_key.get("name") != "name"
        or special.get("op") != "IN"
        or special.get("connector") != "OR"
        or not special_names
    ):
        raise RuntimeError("Report filter semantics changed; refusing to guess")

    public_filter = {
        "$or": [
            {
                "$and": [
                    {"tags": {"$in": tag_any}},
                    {"tags": required_tag},
                ]
            },
            {"name": {"$in": special_names}},
        ]
    }
    semantics = {
        "tag_any": tag_any,
        "required_tag": required_tag,
        "special_run_ids": special_names,
    }
    return public_filter, semantics


def download_table_file(run, pointer: dict[str, Any], root: Path) -> tuple[Path, dict[str, Any]]:
    required = {"path", "sha256", "nrows", "ncols", "artifact_path"}
    missing = required - pointer.keys()
    if missing:
        raise RuntimeError(f"Table pointer for {run.id} lacks {sorted(missing)}")
    root.mkdir(parents=True, exist_ok=True)
    local_path = root / pointer["path"]
    if local_path.exists() and sha256_file(local_path) == pointer["sha256"]:
        path = local_path
    else:
        downloaded = run.file(pointer["path"]).download(root=str(root), replace=True)
        path = Path(downloaded.name)
    actual_sha = sha256_file(path)
    if actual_sha != pointer["sha256"]:
        raise RuntimeError(f"SHA mismatch for {run.id}: {actual_sha} != {pointer['sha256']}")
    payload = read_json(path)
    if len(payload.get("data", [])) != pointer["nrows"]:
        raise RuntimeError(f"Row count mismatch for {run.id}")
    if len(payload.get("columns", [])) != pointer["ncols"]:
        raise RuntimeError(f"Column count mismatch for {run.id}")
    return path, payload


def finite(value: Any) -> bool:
    return isinstance(value, (int, float)) and math.isfinite(float(value))


def selective_run_metadata(
    api: wandb.Api,
    path: str,
    filters: dict[str, Any],
    summary_keys: str | list[str],
    *,
    order: str = "-created_at",
    limit: int | None = None,
) -> tuple[list[dict[str, Any]], int]:
    """Fetch only the run fields needed for cohort and report provenance."""
    entity, project = path.split("/", 1)
    keys = [summary_keys] if isinstance(summary_keys, str) else summary_keys
    count = len(
        api.runs(
            path,
            filters=filters,
            per_page=1,
            include_sweeps=False,
            lazy=True,
        )
    )
    query = f"""
    query Runs(
      $project: String!,
      $entity: String!,
      $cursor: String,
      $perPage: Int!,
      $filters: JSONString,
      $order: String
    ) {{
      project(name: $project, entityName: $entity) {{
        runs(filters: $filters, after: $cursor, first: $perPage, order: $order) {{
          edges {{
            node {{
              name
              displayName
              state
              createdAt
              summaryMetrics(keys: {json.dumps(keys)})
            }}
            cursor
          }}
          pageInfo {{
            endCursor
            hasNextPage
          }}
        }}
      }}
    }}
    """
    rows: list[dict[str, Any]] = []
    cursor = None
    target_count = min(count, limit) if limit is not None else count
    while len(rows) < target_count:
        variables = {
            "project": project,
            "entity": entity,
            "perPage": min(50, target_count - len(rows)),
            "filters": json.dumps(filters),
            "order": order,
        }
        if cursor:
            variables["cursor"] = cursor
        response = requests.post(
            "https://api.wandb.ai/graphql",
            headers={
                "Authorization": f"Bearer {api.api_key}",
                "Content-Type": "application/json",
            },
            json={"query": query, "variables": variables},
            timeout=60,
        )
        response.raise_for_status()
        payload = response.json()
        if payload.get("errors"):
            raise RuntimeError(f"W&B GraphQL errors: {payload['errors']}")
        connection = payload["data"]["project"]["runs"]
        for edge in connection["edges"]:
            node = edge["node"]
            summary = json.loads(node.get("summaryMetrics") or "{}")
            rows.append(
                {
                    "run_id": node["name"],
                    "run_name": node.get("displayName") or node["name"],
                    "state": node["state"],
                    "created_at": node["createdAt"],
                    **{key: summary.get(key) for key in keys},
                }
            )
        page_info = connection["pageInfo"]
        if not page_info.get("hasNextPage"):
            break
        cursor = page_info.get("endCursor")
    if len(rows) != target_count:
        raise RuntimeError(f"Expected {target_count} selectively fetched runs, got {len(rows)}")
    return rows, count


def tagged_run_metadata(
    api: wandb.Api,
    path: str,
    required_tag: str,
    table_key: str,
) -> list[dict[str, Any]]:
    """Fetch only the run fields needed to rank a tag-defined cohort."""
    rows, count = selective_run_metadata(
        api,
        path,
        {"tags": required_tag},
        table_key,
    )
    if len(rows) != count:
        raise RuntimeError(f"Expected {count} runs tagged {required_tag!r}, fetched {len(rows)}")
    return rows


def download_run_file(
    api_key: str,
    entity: str,
    project: str,
    run_id: str,
    pointer: dict[str, Any],
    root: Path,
) -> tuple[Path, dict[str, Any]]:
    required = {"path", "sha256", "nrows", "ncols", "artifact_path"}
    missing = required - pointer.keys()
    if missing:
        raise RuntimeError(f"Table pointer for {run_id} lacks {sorted(missing)}")
    local_path = root / run_id / pointer["path"]
    if not local_path.exists() or sha256_file(local_path) != pointer["sha256"]:
        url = (
            f"https://api.wandb.ai/files/{quote(entity)}/{quote(project)}/"
            f"{quote(run_id)}/{quote(pointer['path'], safe='/')}"
        )
        response = requests.get(
            url,
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=60,
        )
        response.raise_for_status()
        local_path.parent.mkdir(parents=True, exist_ok=True)
        local_path.write_bytes(response.content)
    actual_sha = sha256_file(local_path)
    if actual_sha != pointer["sha256"]:
        raise RuntimeError(
            f"SHA mismatch for {run_id}: {actual_sha} != {pointer['sha256']}"
        )
    payload = read_json(local_path)
    if len(payload.get("data", [])) != pointer["nrows"]:
        raise RuntimeError(f"Row count mismatch for {run_id}")
    if len(payload.get("columns", [])) != pointer["ncols"]:
        raise RuntimeError(f"Column count mismatch for {run_id}")
    return local_path, payload


def main() -> None:
    load_dotenv(WORKSPACE_ROOT / ".env", override=False)
    config = load_config()
    snapshot = config["snapshot"]
    entity = snapshot["entity"]
    project = snapshot["project"]
    path = f"{entity}/{project}"
    timezone = snapshot["timezone"]
    now = datetime.now(ZoneInfo(timezone))

    api = wandb.Api(timeout=60)
    report = find_report(api, entity, project, snapshot["report_view_id"])
    spec = report.spec
    spec_hash = json_hash(spec)
    raw_spec_path = RAW_DIR / "report_spec.json"
    write_json(raw_spec_path, spec)

    block_index, metadata = leaderboard_grid(spec)
    active_runsets = [runset for runset in metadata["runSets"] if runset.get("enabled")]
    if len(active_runsets) != 1:
        raise RuntimeError(f"Expected one active runset, found {len(active_runsets)}")
    active = active_runsets[0]
    public_filter, filter_semantics = public_filter_from_report(active)

    sort_keys = active.get("sort", {}).get("keys", [])
    if len(sort_keys) != 1:
        raise RuntimeError("Unexpected report runset sort")
    sort_key = sort_keys[0]
    if sort_key.get("key", {}).get("name") != "createdAt":
        raise RuntimeError("Report no longer sorts the runset by createdAt")
    api_order = "+created_at" if sort_key.get("ascending") else "-created_at"

    panel_index, panel2 = main_table_panel(metadata)
    table_state = panel2["panelConfig"]["childConfig"]["tableState"]
    panel_sort = table_state.get("sort")
    score_selector = (
        table_state.get("columnSelectFunctions", {})
        .get("col-3", {})
        .get("fromOp", {})
        .get("inputs", {})
        .get("key", {})
        .get("val")
    )
    max_length = panel2.get("panelInputType", {}).get("value", {}).get("maxLength")
    if panel_sort != [{"dir": "desc", "columnId": "col-3"}]:
        raise RuntimeError(f"Unexpected leaderboard panel sort: {panel_sort}")
    if score_selector != config["ranking"]["score_column"]:
        raise RuntimeError(f"Unexpected score selector: {score_selector}")
    if not isinstance(max_length, int) or max_length <= 0:
        raise RuntimeError(f"Unexpected panel maxLength: {max_length}")

    report_runs, run_count = selective_run_metadata(
        api,
        path,
        public_filter,
        config["ranking"]["table_key"],
        order=api_order,
        limit=max_length,
    )
    report_run_ids = [run["run_id"] for run in report_runs]
    if len(report_run_ids) != min(run_count, max_length):
        raise RuntimeError("Report runset truncation did not match maxLength")

    special_runs = [api.run(f"{path}/{run_id}") for run_id in filter_semantics["special_run_ids"]]
    merged_candidates = []
    for run in special_runs:
        pointer = run.summary_metrics.get(config["ranking"]["table_key"])
        if isinstance(pointer, dict) and pointer.get("nrows", 0) > 1:
            merged_candidates.append((run, pointer))
    if len(merged_candidates) != 1:
        raise RuntimeError(
            f"Expected one merged leaderboard source, found {len(merged_candidates)}"
        )

    source_run, source_pointer = merged_candidates[0]
    source_file, source_table = download_table_file(
        source_run,
        source_pointer,
        RAW_DIR / "report_merged_leaderboard",
    )
    reference_columns = source_table["columns"]
    required_columns = {
        config["ranking"]["score_column"],
        "model_name",
        "_source_run_id",
        "_source_run_name",
        *PRIMARY_SCORE_CATEGORIES,
    }
    missing_columns = required_columns - set(reference_columns)
    if missing_columns:
        raise RuntimeError(f"Merged leaderboard lacks columns: {sorted(missing_columns)}")

    reference_rows = [
        dict(zip(reference_columns, row, strict=True)) for row in source_table["data"]
    ]
    required_tag = config["ranking"]["required_tag"]
    cohort = tagged_run_metadata(
        api,
        path,
        required_tag,
        config["ranking"]["table_key"],
    )
    candidate_records: list[dict[str, Any]] = []
    unrankable: list[dict[str, str]] = []

    def load_candidate(source_order: int, metadata: dict[str, Any]) -> dict[str, Any]:
        pointer = metadata[config["ranking"]["table_key"]]
        local_file, table = download_run_file(
            api.api_key,
            entity,
            project,
            metadata["run_id"],
            pointer,
            RAW_DIR / "tagged_leaderboard_tables",
        )
        if len(table["data"]) != 1:
            raise RuntimeError(
                f"Run {metadata['run_id']} leaderboard table has != 1 row"
            )
        row = dict(zip(table["columns"], table["data"][0], strict=True))
        row["_source_run_id"] = metadata["run_id"]
        row["_source_run_name"] = metadata["run_name"]
        return {
            "source_order": source_order,
            "metadata": metadata,
            "pointer": pointer,
            "file": local_file,
            "columns": table["columns"],
            "row": row,
        }

    eligible = []
    for source_order, metadata in enumerate(cohort):
        pointer = metadata.get(config["ranking"]["table_key"])
        if not isinstance(pointer, dict):
            unrankable.append(
                {
                    "run_id": metadata["run_id"],
                    "reason": f"missing {config['ranking']['table_key']} pointer",
                }
            )
            continue
        eligible.append((source_order, metadata))

    with ThreadPoolExecutor(max_workers=8) as executor:
        futures = {
            executor.submit(load_candidate, source_order, metadata): metadata["run_id"]
            for source_order, metadata in eligible
        }
        for future in as_completed(futures):
            candidate = future.result()
            score = candidate["row"].get(config["ranking"]["score_column"])
            if finite(score):
                candidate_records.append(candidate)
            else:
                unrankable.append(
                    {
                        "run_id": futures[future],
                        "reason": f"non-finite {config['ranking']['score_column']}",
                    }
                )

    candidate_records.sort(
        key=lambda candidate: (
            -float(candidate["row"][config["ranking"]["score_column"]]),
            candidate["source_order"],
        )
    )
    top_n = config["ranking"]["top_n"]
    if len(candidate_records) < top_n:
        raise RuntimeError(
            f"Only {len(candidate_records)} rankable runs tagged {required_tag!r}"
        )
    top_candidates = candidate_records[:top_n]
    top_rows = [candidate["row"] for candidate in top_candidates]
    source_ids = [row["_source_run_id"] for row in top_rows]
    if len(source_ids) != top_n or len(set(source_ids)) != top_n:
        raise RuntimeError("Top ranking does not resolve to unique source run IDs")

    validation_rows = []
    manifest_rows = []
    for rank, candidate in enumerate(top_candidates, start=1):
        row = candidate["row"]
        metadata = candidate["metadata"]
        pointer = candidate["pointer"]
        individual_file = candidate["file"]
        run_id = metadata["run_id"]
        score = float(row[config["ranking"]["score_column"]])
        missing_primary = [
            category for category in PRIMARY_SCORE_CATEGORIES if not finite(row.get(category))
        ]
        manifest_rows.append(
            {
                "snapshot_id": snapshot["date"],
                "report_spec_hash": spec_hash,
                "required_tag": required_tag,
                "rank": rank,
                "run_id": run_id,
                "run_name": metadata["run_name"],
                "model_name": row["model_name"],
                "model_family": row.get("base_model"),
                "model_size_category": row.get("model_size_category"),
                "state": metadata["state"],
                "total_score": score,
                "run_url": f"https://wandb.ai/{path}/runs/{run_id}",
                "leaderboard_artifact": pointer["artifact_path"],
                "artifact_digest": pointer["sha256"],
                "leaderboard_file": str(individual_file.relative_to(PROJECT_ROOT)),
                "primary_category_count": len(PRIMARY_SCORE_CATEGORIES) - len(missing_primary),
                "missing_primary_categories": "|".join(missing_primary),
                "fetched_at": now.isoformat(),
            }
        )
        validation_rows.append(
            {
                "rank": rank,
                "run_id": run_id,
                "required_tag": required_tag,
                "selected_by_required_tag": True,
                "score_matches_individual_table": True,
                "model_name_matches_individual_table": True,
                "individual_table_sha256": sha256_file(individual_file),
                "individual_table_nrows": pointer["nrows"],
                "missing_primary_categories": missing_primary,
            }
        )

    manifest_path = MANIFEST_DIR / "top20_runs.csv"
    with manifest_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(manifest_rows[0]))
        writer.writeheader()
        writer.writerows(manifest_rows)

    score_rows_path = MANIFEST_DIR / "top20_leaderboard_rows.csv"
    columns = list(reference_columns)
    for candidate in top_candidates:
        for column in candidate["columns"]:
            if column not in columns:
                columns.append(column)
    with score_rows_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["rank", *columns])
        writer.writeheader()
        for rank, row in enumerate(top_rows, start=1):
            writer.writerow({"rank": rank, **row})

    report_summary = {
        "report": {
            "id": report.id,
            "name": report.name,
            "display_name": report.display_name,
            "url": report.url,
            "created_at": report.created_at,
            "updated_at": report.updated_at,
            "spec_sha256": spec_hash,
            "raw_spec_path": str(raw_spec_path.relative_to(PROJECT_ROOT)),
        },
        "leaderboard_grid": {
            "block_index": block_index,
            "active_runset_id": active.get("id"),
            "active_runset_name": active.get("name"),
            "report_filter": active.get("filters"),
            "public_api_filter": public_filter,
            "filter_semantics": filter_semantics,
            "sort": active.get("sort"),
            "api_order": api_order,
            "matching_run_count": run_count,
            "panel_max_length": max_length,
            "materialized_run_count": len(report_run_ids),
            "materialized_run_ids_sha256": json_hash(report_run_ids),
            "main_panel_index": panel_index,
            "panel_sort": panel_sort,
            "score_column": score_selector,
        },
        "ranking_cohort": {
            "required_tag": required_tag,
            "api_filter": {"tags": required_tag},
            "matching_run_count": len(cohort),
            "rankable_run_count": len(candidate_records),
            "unrankable_runs": unrankable,
            "ranking_source": "individual leaderboard_table pointers",
        },
        "merged_source": {
            "run_id": source_run.id,
            "run_name": source_run.name,
            "pointer": source_pointer,
            "file": str(source_file.relative_to(PROJECT_ROOT)),
            "file_sha256": sha256_file(source_file),
            "row_count": len(reference_rows),
            "column_count": len(reference_columns),
            "role": "report provenance only; not the strict-tag ranking source",
        },
    }
    write_json(MANIFEST_DIR / "report_spec_summary.json", report_summary)

    duplicate_models: dict[str, list[str]] = {}
    for row in manifest_rows:
        duplicate_models.setdefault(row["model_name"], []).append(row["run_id"])
    duplicate_models = {model: ids for model, ids in duplicate_models.items() if len(ids) > 1}
    ranking_validation = {
        "snapshot_id": snapshot["date"],
        "captured_at": now.isoformat(),
        "report_spec_sha256": spec_hash,
        "source_table_sha256": source_pointer["sha256"],
        "source_table_rows": len(reference_rows),
        "required_tag": required_tag,
        "cohort_run_count": len(cohort),
        "rankable_run_count": len(candidate_records),
        "unrankable_runs": unrankable,
        "top_n": top_n,
        "unique_run_ids": len(set(source_ids)),
        "all_runs_finished": all(row["state"] == "finished" for row in manifest_rows),
        "all_selected_have_required_tag": True,
        "all_primary_categories_finite": all(
            row["primary_category_count"] == len(PRIMARY_SCORE_CATEGORIES) for row in manifest_rows
        ),
        "duplicate_model_names": duplicate_models,
        "rows": validation_rows,
        "ui_visual_check": "pending",
    }
    write_json(MANIFEST_DIR / "ranking_validation.json", ranking_validation)

    print(f"Wrote {manifest_path.relative_to(PROJECT_ROOT)}")
    print(
        f"Report {report.updated_at}, spec={spec_hash[:12]}, "
        f"tag={required_tag}, cohort={len(cohort)}, "
        f"rankable={len(candidate_records)}, top_n={top_n}"
    )
    for row in manifest_rows:
        print(f"{row['rank']:>2}. {row['model_name']}  {row['total_score']:.6f}")


if __name__ == "__main__":
    main()
