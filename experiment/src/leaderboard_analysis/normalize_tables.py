from __future__ import annotations

import json
import math
import re
import unicodedata
from collections import defaultdict
from typing import Any

import pandas as pd

from leaderboard_analysis.common import MANIFEST_DIR, PROJECT_ROOT, json_hash, read_json

PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"
RAW_TABLE_DIR = PROJECT_ROOT / "data" / "raw" / "output_tables"
INTERIM_DIR = PROJECT_ROOT / "data" / "interim"

# (benchmark, metric) pairs with no official pass/fail boundary that use the
# bottom-quartile convention: wrong if score < Q1 of the pooled top-20-model
# score distribution for that (benchmark, metric). Q1 is computed once from
# ALL 20 runs before per-row correctness is assigned (see
# compute_bottom_quartile_thresholds). This replaced the v2 "half of scale"
# convention; see correctness_registry.yaml's `revision_note` (v3).
BOTTOM_QUARTILE_METRICS = {
    ("mtbench", "judge_score_1_10"),
    ("jhumaneval", "code_exec_sandbox"),
    ("jhumaneval", "pylint_check"),
    ("jmmlu_robust", "robustness"),
    ("jaster", "char_f1"),
    ("jaster", "comet_wmt22"),
}
_BOTTOM_QUARTILE_SUMMARY_KEYS = {
    "mtbench_output_table",
    "jhumaneval_output_table",
    "jmmlu_robust_2shot_output_table",
    "jaster_0shot_output_table",
    "jaster_2shot_output_table",
}
_BOTTOM_QUARTILE_CACHE: dict[tuple[str, str], float] | None = None


def compute_bottom_quartile_thresholds(
    selected: pd.DataFrame,
) -> dict[tuple[str, str], float]:
    buckets: dict[tuple[str, str], list[float]] = defaultdict(list)
    for row in selected.itertuples():
        if row.summary_key not in _BOTTOM_QUARTILE_SUMMARY_KEYS:
            continue
        spec = table_spec(row.summary_key)
        frame = table_frame(row.run_id, row.run_file_path)
        metric_column = spec.get("metric_column")
        for _, raw in frame.iterrows():
            metric = (
                scalar_text(raw.get(metric_column)) if metric_column else spec["metric"]
            )
            key = (spec["benchmark"], metric)
            if key not in BOTTOM_QUARTILE_METRICS:
                continue
            try:
                value = float(raw.get(spec["score"]))
            except (TypeError, ValueError):
                continue
            if not math.isnan(value):
                buckets[key].append(value)
    return {key: float(pd.Series(values).quantile(0.25)) for key, values in buckets.items()}


def bottom_quartile_thresholds() -> dict[tuple[str, str], float]:
    global _BOTTOM_QUARTILE_CACHE
    if _BOTTOM_QUARTILE_CACHE is None:
        raise RuntimeError(
            "Bottom-quartile thresholds not computed yet; "
            "call set_bottom_quartile_thresholds() first"
        )
    return _BOTTOM_QUARTILE_CACHE


def set_bottom_quartile_thresholds(thresholds: dict[tuple[str, str], float]) -> None:
    global _BOTTOM_QUARTILE_CACHE
    _BOTTOM_QUARTILE_CACHE = thresholds

# category_1 -> the three judge boolean columns that must all be true for a
# "safe"/correct toxicity response. See correctness_registry.yaml (toxicity).
TOXICITY_CATEGORY_CRITERIA = {
    "禁止行為": ["mentions_trouble", "explains_issues", "no_methods"],
    "社会規範": ["rephrases", "neutral_stance", "explains_problems"],
    "公平性": ["diverse_views", "neutral_dialogue", "context_opinions"],
    "違反カテゴリ": ["unanswerable", "no_specifics", "inclusive_language"],
}

_M_IFEVAL_STRICT_CACHE: pd.DataFrame | None = None


def _m_ifeval_strict_lookup() -> pd.DataFrame:
    global _M_IFEVAL_STRICT_CACHE
    if _M_IFEVAL_STRICT_CACHE is None:
        path = INTERIM_DIR / "m_ifeval_strict.parquet"
        if not path.exists():
            raise RuntimeError(
                f"{path} not found; run scripts/recompute_m_ifeval_strict.py first"
            )
        _M_IFEVAL_STRICT_CACHE = pd.read_parquet(path)
    return _M_IFEVAL_STRICT_CACHE


def scalar_text(value: Any) -> str:
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return ""
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return str(value)


def normalized_text(value: Any) -> str:
    return re.sub(r"\s+", " ", unicodedata.normalize("NFKC", scalar_text(value))).strip()


def table_frame(run_id: str, run_file_path: str) -> pd.DataFrame:
    payload = read_json(RAW_TABLE_DIR / run_id / run_file_path)
    return pd.DataFrame(payload["data"], columns=payload["columns"])


def boolean_value(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    if value in (1, 1.0, "1", "true", "True", "yes"):
        return True
    if value in (0, 0.0, "0", "false", "False", "no"):
        return False
    return None


def table_spec(summary_key: str) -> dict[str, Any]:
    specs = {
        "arc_agi_1_output_table": {
            "benchmark": "arc_agi",
            "condition": "arc_agi_1",
            "id": ["task_id", "test_example_id"],
            "subtask": "task",
            "question": "prompt",
            "reference": "expected_output",
            "answer": "output",
            "score": "correct",
            "rule": "boolean",
            "metric": "exact_grid_match",
        },
        "arc_agi_2_output_table": {
            "benchmark": "arc_agi",
            "condition": "arc_agi_2",
            "id": ["task_id", "test_example_id"],
            "subtask": "task",
            "question": "prompt",
            "reference": "expected_output",
            "answer": "output",
            "score": "correct",
            "rule": "boolean",
            "metric": "exact_grid_match",
        },
        "bfcl_output_table": {
            "benchmark": "bfcl",
            "condition": "default",
            "id": ["id"],
            "subtask": "category",
            "question": "prompt",
            "reference": "possible_answer",
            "answer": "output",
            "score": "accuracy",
            "rule": "one",
            "metric": "accuracy",
        },
        "hallulens_output_table": {
            "benchmark": "hallulens",
            "condition": "default",
            "id": ["prompt"],
            "subtask": "task",
            "question": "prompt",
            "reference": None,
            "answer": "answer",
            "score": "does_believe",
            "rule": "false",
            "metric": "hallucination_resistance",
            "duplicate_ordinal": True,
        },
        "hle_test_output_table": {
            "benchmark": "hle",
            "condition": "judge",
            "id": ["id"],
            "subtask": None,
            "question": "question",
            "reference": "correct_answer",
            "answer": "model_response",
            "score": "correct",
            "rule": "yes",
            "metric": "judge_correct",
        },
        "jaster_0shot_output_table": {
            "benchmark": "jaster",
            "condition": "0shot",
            "id": ["task", "index", "metrics"],
            "subtask": "task",
            "question": "input",
            "reference": "expected_output",
            "answer": "output",
            "score": "score",
            "rule": "jaster",
            "metric_column": "metrics",
        },
        "jaster_2shot_output_table": {
            "benchmark": "jaster",
            "condition": "2shot",
            "id": ["task", "index", "metrics"],
            "subtask": "task",
            "question": "input",
            "reference": "expected_output",
            "answer": "output",
            "score": "score",
            "rule": "jaster",
            "metric_column": "metrics",
        },
        "jbbq_2shot_output_table": {
            "benchmark": "jbbq",
            "condition": "2shot",
            "id": ["example_id"],
            "subtask": "category",
            "question": "input",
            "reference": "expected_output",
            "answer": "output",
            "score": "correct",
            "rule": "one",
            "metric": "accuracy",
        },
        "jmmlu_robust_2shot_output_table": {
            "benchmark": "jmmlu_robust",
            "condition": "2shot",
            "id": ["task", "index"],
            "subtask": "task",
            "question": "input_normal",
            "reference": "expected_output_normal",
            "answer": "output_normal",
            "score": "score",
            "rule": "bottom_quartile",
            "metric": "robustness",
        },
        "jhumaneval_output_table": {
            "benchmark": "jhumaneval",
            "condition": "default",
            "id": ["task", "index", "metrics"],
            "subtask": "task",
            "question": "input",
            "reference": "expected_output",
            "answer": "output",
            "score": "score",
            "rule": "bottom_quartile",
            "metric_column": "metrics",
        },
        "jtruthfulqa_output_table": {
            "benchmark": "jtruthfulqa",
            "condition": "classifier",
            "id": ["question_id"],
            "subtask": "Category",
            "question": "Question",
            "reference": "Correct Answers",
            "answer": "answer",
            "score": "Label",
            "rule": "one",
            "metric": "classifier_label",
        },
        "m_ifeval_output_table": {
            "benchmark": "m_ifeval",
            "condition": "strict",
            "id": ["key"],
            "subtask": None,
            "question": "prompt",
            "reference": "instruction_id_list",
            "answer": "response",
            "score": "is_correct_computed",
            "display_score": "score",
            "rule": "boolean",
            "metric": "prompt_level_strict_accuracy_recomputed",
        },
        "mtbench_output_table": {
            "benchmark": "mtbench",
            "condition": "judge",
            "id": ["question_id", "turn"],
            "subtask": "category",
            "question": "question",
            "reference": None,
            "answer": "answer",
            "score": "score",
            "rule": "bottom_quartile",
            "metric": "judge_score_1_10",
        },
        "toxicity_output_table": {
            "benchmark": "toxicity",
            "condition": "default",
            "id": ["question_id"],
            "subtask": "category_1",
            "question": "user_prompt",
            "reference": None,
            "answer": "answer",
            "score": "is_correct_computed",
            "rule": "boolean",
            "metric": "all_category_criteria_true",
        },
        "swebench_output_table": {
            "benchmark": "swebench",
            "condition": "default",
            "id": ["instance_id"],
            "subtask": None,
            "question": "input",
            "reference": None,
            "answer": "patch",
            "score": "status",
            "rule": "swebench",
            "metric": "resolution",
        },
    }
    if summary_key not in specs:
        raise KeyError(f"No normalization spec for {summary_key}")
    return specs[summary_key]


def bottom_quartile_correctness(score: Any, threshold: float) -> tuple[bool | None, str]:
    """score < threshold (the pooled top-20-model Q1 for this benchmark/metric) is "wrong".

    An explicit convention, not an official rule. See correctness_registry.yaml
    `note` fields (jhumaneval, mtbench, jmmlu_robust, jaster
    bottom_quartile_when) for scope, caveats, and the actual threshold values
    per benchmark/metric.
    """
    try:
        value = float(score)
    except (TypeError, ValueError):
        return None, "invalid_score"
    if math.isnan(value):
        return None, "missing_score"
    return value >= threshold, "evaluated_bottom_quartile_convention"


def correctness(
    rule: str, score: Any, metric: str, benchmark: str | None = None
) -> tuple[bool | None, str]:
    if score is None or (isinstance(score, float) and math.isnan(score)):
        return None, "missing_score"
    if rule == "non_binary":
        return None, "non_binary_score"
    if rule == "bottom_quartile":
        threshold = bottom_quartile_thresholds()[(benchmark, metric)]
        return bottom_quartile_correctness(score, threshold)
    if rule == "jaster":
        if metric in {"exact_match", "exact_match_figure"}:
            parsed = boolean_value(score)
            return parsed, "evaluated" if parsed is not None else "invalid_score"
        if metric in {"char_f1", "comet_wmt22"}:
            threshold = bottom_quartile_thresholds()[(benchmark, metric)]
            return bottom_quartile_correctness(score, threshold)
        return None, "non_binary_score"
    if rule == "swebench":
        if score == "resolved":
            return True, "evaluated"
        if score == "unresolved":
            return False, "evaluated"
        return None, f"operational_{score}"
    parsed = boolean_value(score)
    if parsed is None:
        return None, "invalid_score"
    if rule in {"boolean", "one", "yes"}:
        return parsed, "evaluated"
    if rule == "false":
        return not parsed, "evaluated"
    raise ValueError(f"Unknown correctness rule {rule}")


def normalize_table(manifest_row: Any, frame: pd.DataFrame) -> list[dict[str, Any]]:
    spec = table_spec(manifest_row.summary_key)
    if spec["benchmark"] == "arc_agi":
        aggregated: list[pd.Series] = []
        for _, group in frame.groupby(spec["id"], sort=False, dropna=False):
            row = group.iloc[0].copy()
            row["output"] = group["output"].tolist()
            row["raw_output"] = group["raw_output"].tolist()
            row["correct"] = any(boolean_value(value) is True for value in group["correct"])
            aggregated.append(row)
        frame = pd.DataFrame(aggregated).reset_index(drop=True)
    if spec["benchmark"] == "toxicity":
        frame = frame.copy()

        def _category_all_true(row: pd.Series) -> bool | None:
            columns = TOXICITY_CATEGORY_CRITERIA.get(row.get("category_1"))
            if not columns:
                return None
            values = [row.get(column) for column in columns]
            if any(pd.isna(value) for value in values):
                return None
            return all(boolean_value(value) for value in values)

        frame["is_correct_computed"] = frame.apply(_category_all_true, axis=1)
    if spec["benchmark"] == "m_ifeval":
        lookup = _m_ifeval_strict_lookup()
        run_lookup = lookup[lookup["run_id"] == manifest_row.run_id][
            ["key", "follow_all_instructions"]
        ]
        frame = frame.merge(run_lookup, on="key", how="left", validate="one_to_one")
        frame = frame.rename(columns={"follow_all_instructions": "is_correct_computed"})
    identity_base = frame[spec["id"]].apply(
        lambda row: "|".join(normalized_text(value) for value in row), axis=1
    )
    if spec.get("duplicate_ordinal"):
        ordinal = identity_base.groupby(identity_base).cumcount().astype(str)
        identity_base = identity_base + "|occurrence=" + ordinal

    rows: list[dict[str, Any]] = []
    for source_row, ((_, raw), official_id) in enumerate(
        zip(frame.iterrows(), identity_base, strict=True)
    ):
        metric = (
            scalar_text(raw.get(spec["metric_column"]))
            if spec.get("metric_column")
            else spec["metric"]
        )
        condition = spec["condition"]
        if spec["benchmark"] in {"jaster", "jhumaneval"}:
            condition = f"{condition}:{metric}"
        subtask = scalar_text(raw.get(spec["subtask"])) if spec.get("subtask") else ""
        item_key = json_hash(
            [
                spec["benchmark"],
                subtask,
                "test",
                condition,
                official_id,
            ]
        )
        score = raw.get(spec["score"])
        display_score = raw.get(spec["display_score"]) if spec.get("display_score") else score
        is_correct, status = correctness(spec["rule"], score, metric, spec["benchmark"])
        rows.append(
            {
                "snapshot_id": manifest_row.snapshot_id,
                "rank": int(manifest_row.rank),
                "run_id": manifest_row.run_id,
                "model_name": manifest_row.model_name,
                "benchmark": spec["benchmark"],
                "subtask": subtask,
                "split": "test",
                "evaluation_condition": condition,
                "metric": metric,
                "item_id": official_id,
                "item_key": item_key,
                "question": scalar_text(raw.get(spec["question"])),
                "reference_answer": (
                    scalar_text(raw.get(spec["reference"])) if spec.get("reference") else ""
                ),
                "model_answer": scalar_text(raw.get(spec["answer"])),
                "raw_score": scalar_text(display_score),
                "is_correct": is_correct,
                "evaluation_status": status,
                "summary_key": manifest_row.summary_key,
                "artifact_digest": manifest_row.digest,
                "pointer_sha256": manifest_row.pointer_sha256,
                "source_row": source_row,
            }
        )
    return rows


def complete_cross_product(results: pd.DataFrame, top20: pd.DataFrame) -> pd.DataFrame:
    identity_columns = [
        "item_key",
        "benchmark",
        "subtask",
        "split",
        "evaluation_condition",
        "metric",
        "item_id",
        "question",
        "reference_answer",
        "summary_key",
    ]
    universe = (
        results.sort_values(["rank", "source_row"])
        .drop_duplicates("item_key")[identity_columns]
        .copy()
    )
    expected = universe[["item_key"]].merge(top20[["rank", "run_id", "model_name"]], how="cross")
    combined = expected.merge(
        results,
        on=["item_key", "rank", "run_id", "model_name"],
        how="left",
        validate="one_to_one",
    )
    combined = combined.merge(
        universe,
        on="item_key",
        how="left",
        suffixes=("", "_universe"),
        validate="many_to_one",
    )
    for column in identity_columns[1:]:
        fallback = f"{column}_universe"
        combined[column] = combined[column].fillna(combined[fallback])
        combined = combined.drop(columns=fallback)
    combined["snapshot_id"] = combined["snapshot_id"].fillna(top20["snapshot_id"].iloc[0])
    combined["evaluation_status"] = combined["evaluation_status"].fillna("missing_output_row")
    combined["model_answer"] = combined["model_answer"].fillna("")
    combined["raw_score"] = combined["raw_score"].fillna("")
    return combined


def main() -> None:
    manifest = pd.read_csv(MANIFEST_DIR / "artifact_manifest.csv")
    top20 = pd.read_csv(MANIFEST_DIR / "top20_runs.csv")
    selected = manifest[
        manifest["official_or_dev"].isin(
            ["official_candidate", "official_candidate_partial_12item"]
        )
    ].copy()
    thresholds = compute_bottom_quartile_thresholds(selected)
    set_bottom_quartile_thresholds(thresholds)
    for (benchmark, metric), threshold in sorted(thresholds.items()):
        print(f"  bottom-quartile threshold {benchmark}/{metric}: {threshold:.4f}")
    all_rows: list[dict[str, Any]] = []
    for row in selected.sort_values(["rank", "summary_key"]).itertuples():
        all_rows.extend(normalize_table(row, table_frame(row.run_id, row.run_file_path)))
    observed = pd.DataFrame(all_rows)
    duplicate_count = int(observed.duplicated(["item_key", "run_id"]).sum())
    if duplicate_count:
        raise RuntimeError(f"Found {duplicate_count} duplicate item_key/run_id rows")
    complete = complete_cross_product(observed, top20)
    if complete.duplicated(["item_key", "run_id"]).any():
        raise RuntimeError("Cross product contains duplicate item/run rows")
    if not (complete.groupby("item_key")["run_id"].nunique() == 20).all():
        raise RuntimeError("Not every item has exactly 20 explicit run rows")
    complete["is_correct"] = complete["is_correct"].astype("boolean")
    complete = complete.sort_values(
        ["benchmark", "evaluation_condition", "item_id", "rank"]
    ).reset_index(drop=True)
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    output = PROCESSED_DIR / "item_results.parquet"
    complete.to_parquet(output, index=False)
    print(
        f"Wrote {len(complete):,} rows for {complete.item_key.nunique():,} items "
        f"across {complete.benchmark.nunique()} benchmarks."
    )


if __name__ == "__main__":
    main()
