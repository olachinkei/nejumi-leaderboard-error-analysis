from __future__ import annotations

import csv
import gc
import json
from collections.abc import Iterable
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import quote, urlparse
from zoneinfo import ZoneInfo

import requests
import wandb
from dotenv import load_dotenv
from wandb.apis.public.api import gql

from leaderboard_analysis.common import (
    MANIFEST_DIR,
    RAW_DIR,
    WORKSPACE_ROOT,
    json_hash,
    load_config,
    read_json,
    sha256_file,
)

OUTPUT_MARKER = "output_table"
POINTER_FIELDS = {"artifact_path", "path", "sha256", "nrows", "ncols"}

ARTIFACT_FIELDS = [
    "snapshot_id",
    "rank",
    "run_id",
    "model_name",
    "benchmark",
    "evaluation_condition",
    "split",
    "summary_key",
    "pointer_sha256",
    "pointer_artifact_path",
    "artifact_name",
    "version",
    "digest",
    "type",
    "artifact_id",
    "artifact_created_at",
    "artifact_size",
    "table_entry",
    "manifest_entry_digest",
    "manifest_entry_size",
    "run_file_path",
    "local_path",
    "row_count",
    "column_count",
    "columns_hash",
    "official_or_dev",
    "extraction_status",
    "skipped_reason",
    "fetched_at",
]

SCHEMA_FIELDS = [
    "snapshot_id",
    "rank",
    "run_id",
    "benchmark",
    "evaluation_condition",
    "split",
    "summary_key",
    "row_count",
    "column_count",
    "columns_hash",
    "columns_json",
    "id_candidates",
    "question_candidates",
    "reference_answer_candidates",
    "model_answer_candidates",
    "score_candidates",
    "error_candidates",
    "official_or_dev",
]


def read_top20(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    if len(rows) != 20:
        raise RuntimeError(f"Expected 20 frozen runs, found {len(rows)}")
    run_ids = [row["run_id"] for row in rows]
    if len(set(run_ids)) != 20:
        raise RuntimeError("Frozen top20 contains duplicate run IDs")
    return rows


def table_pointers(summary: dict[str, Any]) -> dict[str, dict[str, Any]]:
    pointers: dict[str, dict[str, Any]] = {}
    for key, value in summary.items():
        if OUTPUT_MARKER in key and isinstance(value, dict) and value.get("_type") == "table-file":
            missing = POINTER_FIELDS - value.keys()
            if missing:
                raise RuntimeError(f"{key} pointer lacks fields: {sorted(missing)}")
            pointers[key] = value
    return pointers


def table_identity(summary_key: str) -> tuple[str, str, str, str]:
    split = "dev" if summary_key.endswith("_dev") else "official"
    base = summary_key.removesuffix("_dev").removesuffix("_output_table")
    condition = "default"
    benchmark = base

    if base.startswith("jaster_"):
        benchmark = "jaster"
        condition = base.removeprefix("jaster_")
    elif base.startswith("hle_"):
        benchmark = "hle"
        split = base.removeprefix("hle_")
    elif base == "jmmlu_robust_2shot":
        benchmark = "jmmlu_robust"
        condition = "2shot"
    elif base == "jbbq_2shot":
        benchmark = "jbbq"
        condition = "2shot"

    if split == "dev":
        publication_class = "dev_excluded"
    elif benchmark == "toxicity":
        # Only question_id 0-11 are persisted per-item (toxicity.py:219 logs
        # df_toxicity.iloc[:12]); see correctness_registry.yaml's toxicity
        # rule for why this partial set is still analyzable.
        publication_class = "official_candidate_partial_12item"
    else:
        publication_class = "official_candidate"
    return benchmark, condition, split, publication_class


def resolve_artifact(api: wandb.Api, artifact_path: str) -> tuple[Any, str, Any]:
    parsed = urlparse(artifact_path)
    if parsed.scheme != "wandb-client-artifact" or not parsed.netloc:
        raise RuntimeError(f"Unsupported artifact pointer: {artifact_path}")
    query = gql(
        """
        query ClientIDMapping($clientID: ID!) {
            clientIDMapping(clientID: $clientID) {
                serverID
            }
        }
        """
    )
    response = api.client.execute(query, variable_values={"clientID": parsed.netloc})
    mapping = response.get("clientIDMapping") if response else None
    artifact_id = mapping.get("serverID") if mapping else None
    if not artifact_id:
        raise RuntimeError(f"Could not resolve W&B client artifact ID {parsed.netloc}")
    artifact = wandb.Artifact._from_id(artifact_id, api.client)
    if artifact is None:
        raise RuntimeError(f"Could not load artifact {artifact_id}")
    entry_name = parsed.path.lstrip("/")
    entry = artifact.manifest.entries.get(entry_name)
    if entry is None:
        raise RuntimeError(f"Artifact {artifact.name} lacks entry {entry_name}")
    return artifact, entry_name, entry


def download_tables(
    api: wandb.Api,
    run: Any,
    pointers: dict[str, dict[str, Any]],
    root: Path,
) -> dict[str, Path]:
    root.mkdir(parents=True, exist_ok=True)
    resolved: dict[str, Path] = {}
    for pointer in pointers.values():
        path = root / pointer["path"]
        if path.exists() and sha256_file(path) == pointer["sha256"]:
            resolved[pointer["path"]] = path
        else:
            url = (
                f"https://api.wandb.ai/files/{quote(run.entity)}/{quote(run.project)}/"
                f"{quote(run.id)}/{quote(pointer['path'], safe='/')}"
            )
            response = requests.get(
                url,
                headers={"Authorization": f"Bearer {api.api_key}"},
                timeout=60,
            )
            response.raise_for_status()
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(response.content)
            if sha256_file(path) != pointer["sha256"]:
                raise RuntimeError(f"Downloaded SHA mismatch for {run.id}/{pointer['path']}")
            resolved[pointer["path"]] = path
    return resolved


def candidates(columns: Iterable[Any], terms: tuple[str, ...]) -> list[str]:
    matches = []
    for column in columns:
        text = str(column)
        lowered = text.lower()
        if any(term in lowered for term in terms):
            matches.append(text)
    return matches


def schema_row(
    top_row: dict[str, str],
    summary_key: str,
    payload: dict[str, Any],
    fetched_at: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    del fetched_at
    columns = payload.get("columns")
    data = payload.get("data")
    if not isinstance(columns, list) or not isinstance(data, list):
        raise RuntimeError(f"{summary_key} is not a W&B table JSON")
    benchmark, condition, split, publication_class = table_identity(summary_key)
    shared = {
        "snapshot_id": top_row["snapshot_id"],
        "rank": top_row["rank"],
        "run_id": top_row["run_id"],
        "benchmark": benchmark,
        "evaluation_condition": condition,
        "split": split,
        "summary_key": summary_key,
        "row_count": len(data),
        "column_count": len(columns),
        "columns_hash": json_hash(columns),
        "official_or_dev": publication_class,
    }
    schema = {
        **shared,
        "columns_json": json.dumps(columns, ensure_ascii=False, separators=(",", ":")),
        "id_candidates": json.dumps(
            candidates(columns, ("id", "index", "key")), ensure_ascii=False
        ),
        "question_candidates": json.dumps(
            candidates(columns, ("question", "prompt", "input", "instruction")),
            ensure_ascii=False,
        ),
        "reference_answer_candidates": json.dumps(
            candidates(
                columns,
                (
                    "reference",
                    "expected",
                    "correct_answer",
                    "possible_answer",
                    "ground_truth",
                    "target",
                ),
            ),
            ensure_ascii=False,
        ),
        "model_answer_candidates": json.dumps(
            candidates(
                columns,
                ("response", "output", "prediction", "generated", "model_answer"),
            ),
            ensure_ascii=False,
        ),
        "score_candidates": json.dumps(
            candidates(columns, ("score", "correct", "pass", "label", "resolved")),
            ensure_ascii=False,
        ),
        "error_candidates": json.dumps(
            candidates(columns, ("error", "exception", "timeout", "status")),
            ensure_ascii=False,
        ),
    }
    return shared, schema


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def reusable_run_rows(
    top_row: dict[str, str],
    artifact_rows: list[dict[str, str]],
    schema_rows: list[dict[str, str]],
    fetched_at: str,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]] | None:
    run_id = top_row["run_id"]
    artifacts = [row.copy() for row in artifact_rows if row["run_id"] == run_id]
    schemas = [row.copy() for row in schema_rows if row["run_id"] == run_id]
    if not artifacts or len(artifacts) != len(schemas):
        return None
    for row in artifacts:
        local_path = RAW_DIR / "output_tables" / run_id / row["run_file_path"]
        if (
            row.get("extraction_status") != "verified"
            or not local_path.exists()
            or sha256_file(local_path) != row["pointer_sha256"]
        ):
            return None
        row.update(
            {
                "snapshot_id": top_row["snapshot_id"],
                "rank": top_row["rank"],
                "model_name": top_row["model_name"],
                "fetched_at": fetched_at,
            }
        )
    for row in schemas:
        row.update(
            {
                "snapshot_id": top_row["snapshot_id"],
                "rank": top_row["rank"],
            }
        )
    return artifacts, schemas


def main() -> None:
    load_dotenv(WORKSPACE_ROOT / ".env", override=False)
    config = load_config()
    snapshot = config["snapshot"]
    project_path = f"{snapshot['entity']}/{snapshot['project']}"
    top20 = read_top20(MANIFEST_DIR / "top20_runs.csv")
    top_by_id = {row["run_id"]: row for row in top20}
    run_ids = list(top_by_id)
    fetched_at = datetime.now(ZoneInfo(snapshot["timezone"])).isoformat()

    existing_artifacts = read_csv_rows(MANIFEST_DIR / "artifact_manifest.csv")
    existing_schemas = read_csv_rows(MANIFEST_DIR / "schema_inventory.csv")
    api = wandb.Api(timeout=60)
    artifact_rows: list[dict[str, Any]] = []
    schema_rows: list[dict[str, Any]] = []
    for index, run_id in enumerate(run_ids, start=1):
        top_row = top_by_id[run_id]
        reusable = reusable_run_rows(
            top_row,
            existing_artifacts,
            existing_schemas,
            fetched_at,
        )
        if reusable is not None:
            reused_artifacts, reused_schemas = reusable
            artifact_rows.extend(reused_artifacts)
            schema_rows.extend(reused_schemas)
            print(
                f"[{index:02d}/20] {run_id}: reused {len(reused_artifacts)} verified tables",
                flush=True,
            )
            continue

        run = api.run(f"{project_path}/{run_id}")
        pointers = table_pointers(run.summary_metrics)
        if not pointers:
            raise RuntimeError(f"Run {run_id} has no output table pointers")
        print(f"[{index:02d}/20] {run_id}: {len(pointers)} output tables", flush=True)
        local_root = RAW_DIR / "output_tables" / run_id
        downloaded = download_tables(api, run, pointers, local_root)

        for summary_key, pointer in sorted(pointers.items()):
            local_path = downloaded[pointer["path"]]
            actual_sha = sha256_file(local_path)
            if actual_sha != pointer["sha256"]:
                raise RuntimeError(
                    f"SHA mismatch for {run_id}/{summary_key}: {actual_sha} != {pointer['sha256']}"
                )
            payload = read_json(local_path)
            shared, schema = schema_row(top_row, summary_key, payload, fetched_at)
            if shared["row_count"] != pointer["nrows"]:
                raise RuntimeError(f"Row count mismatch for {run_id}/{summary_key}")
            if shared["column_count"] != pointer["ncols"]:
                raise RuntimeError(f"Column count mismatch for {run_id}/{summary_key}")

            artifact, entry_name, entry = resolve_artifact(api, pointer["artifact_path"])
            if entry_name != urlparse(pointer["artifact_path"]).path.lstrip("/"):
                raise RuntimeError(f"Artifact entry mismatch for {run_id}/{summary_key}")

            artifact_rows.append(
                {
                    **shared,
                    "model_name": top_row["model_name"],
                    "pointer_sha256": pointer["sha256"],
                    "pointer_artifact_path": pointer["artifact_path"],
                    "artifact_name": artifact.name.rsplit(":", 1)[0],
                    "version": artifact.version,
                    "digest": artifact.digest,
                    "type": artifact.type,
                    "artifact_id": artifact.id,
                    "artifact_created_at": artifact.created_at,
                    "artifact_size": artifact.size,
                    "table_entry": entry_name,
                    "run_file_path": pointer["path"],
                    "local_path": str(local_path.relative_to(local_path.parents[3])),
                    "extraction_status": "verified",
                    "skipped_reason": (
                        "dev table is not part of the official score"
                        if shared["official_or_dev"] == "dev_excluded"
                        else (
                            "evaluator logs only the first 12 rows"
                            if shared["official_or_dev"] == "incomplete_sample_excluded"
                            else ""
                        )
                    ),
                    "fetched_at": fetched_at,
                    "manifest_entry_digest": entry.digest,
                    "manifest_entry_size": entry.size,
                }
            )
            schema_rows.append(schema)
            del artifact, entry
            gc.collect()
        del run
        gc.collect()

    artifact_rows.sort(key=lambda row: (int(row["rank"]), row["summary_key"]))
    schema_rows.sort(key=lambda row: (int(row["rank"]), row["summary_key"]))
    write_csv(MANIFEST_DIR / "artifact_manifest.csv", artifact_rows, ARTIFACT_FIELDS)
    write_csv(MANIFEST_DIR / "schema_inventory.csv", schema_rows, SCHEMA_FIELDS)
    print(
        f"Wrote {len(artifact_rows)} verified tables across {len(run_ids)} runs.",
        flush=True,
    )


if __name__ == "__main__":
    main()
