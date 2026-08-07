from __future__ import annotations

import math
from collections import Counter

import pandas as pd

from leaderboard_analysis.common import PROJECT_ROOT
from leaderboard_analysis.normalize_tables import normalized_text

PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"
TABLE_DIR = PROJECT_ROOT / "outputs" / "tables"


def item_statistics(results: pd.DataFrame) -> pd.DataFrame:
    frame = results.copy()
    frame["wrong"] = frame["is_correct"].eq(False)
    frame["evaluable"] = frame["is_correct"].notna()
    grouped = frame.groupby("item_key", sort=False)
    stats = grouped.agg(
        n_runs=("run_id", "nunique"),
        n_evaluable=("evaluable", "sum"),
        n_wrong=("wrong", "sum"),
        n_missing_output=(
            "evaluation_status",
            lambda values: (values == "missing_output_row").sum(),
        ),
        n_operational=(
            "evaluation_status",
            lambda values: values.str.startswith("operational_").sum(),
        ),
    )
    stats["wrong_rate"] = stats["n_wrong"] / stats["n_evaluable"].replace(0, pd.NA)
    stats["primary_eligible"] = stats["n_evaluable"].eq(20)
    stats["common_failure_80"] = stats["primary_eligible"] & stats["n_wrong"].ge(16)
    return stats.reset_index()


def answer_summary(group: pd.DataFrame) -> pd.Series:
    answers = [normalized_text(value) for value in group["model_answer"]]
    answers = [value for value in answers if value]
    counts = Counter(answers)
    modal_answer, modal_count = counts.most_common(1)[0] if counts else ("", 0)
    return pd.Series(
        {
            "unique_answer_count": len(counts),
            "modal_answer": modal_answer,
            "modal_answer_count": modal_count,
        }
    )


def sensitivity_table(summary: pd.DataFrame, metadata: pd.DataFrame) -> pd.DataFrame:
    joined = summary.merge(metadata[["item_key", "benchmark"]], on="item_key")
    rows = []
    for threshold in (0.7, 0.8, 0.9):
        required = math.ceil(20 * threshold)
        selected = joined[joined["primary_eligible"] & joined["n_wrong"].ge(required)]
        for benchmark, group in joined.groupby("benchmark"):
            rows.append(
                {
                    "threshold": threshold,
                    "required_wrong_of_20": required,
                    "benchmark": benchmark,
                    "binary_items": int(group["n_evaluable"].gt(0).sum()),
                    "fully_evaluable_items": int(group["primary_eligible"].sum()),
                    "common_failure_count": int((selected["benchmark"] == benchmark).sum()),
                }
            )
    return pd.DataFrame(rows)


def main() -> None:
    results = pd.read_parquet(PROCESSED_DIR / "item_results.parquet")
    stats = item_statistics(results)
    metadata_columns = [
        "item_key",
        "benchmark",
        "subtask",
        "split",
        "evaluation_condition",
        "metric",
        "item_id",
        "question",
        "reference_answer",
    ]
    metadata = results.sort_values("rank").drop_duplicates("item_key")[metadata_columns]
    summaries = stats.merge(metadata, on="item_key", validate="one_to_one")
    answers = (
        results.groupby("item_key", sort=False, group_keys=False)
        .apply(answer_summary, include_groups=False)
        .reset_index()
    )
    summaries = summaries.merge(answers, on="item_key", validate="one_to_one")
    common = summaries[summaries["common_failure_80"]].copy()

    coverage = results.pivot(
        index="item_key", columns="run_id", values="evaluation_status"
    ).reset_index()
    wrong = (
        results.assign(wrong=results["is_correct"].map({True: False, False: True}))
        .pivot(index="item_key", columns="run_id", values="wrong")
        .reset_index()
    )
    sensitivity = sensitivity_table(stats, metadata)

    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    TABLE_DIR.mkdir(parents=True, exist_ok=True)
    summaries.to_parquet(PROCESSED_DIR / "item_summary.parquet", index=False)
    common.to_parquet(PROCESSED_DIR / "common_failures.parquet", index=False)
    coverage.to_parquet(PROCESSED_DIR / "coverage_matrix.parquet", index=False)
    wrong.to_parquet(PROCESSED_DIR / "wrong_matrix.parquet", index=False)
    sensitivity.to_csv(PROCESSED_DIR / "threshold_sensitivity.csv", index=False)

    benchmark_counts = (
        summaries.groupby("benchmark")
        .agg(
            item_count=("item_key", "size"),
            binary_items=("n_evaluable", lambda values: values.gt(0).sum()),
            fully_evaluable_items=("primary_eligible", "sum"),
            common_failures=("common_failure_80", "sum"),
        )
        .reset_index()
    )
    benchmark_counts.to_csv(TABLE_DIR / "benchmark_counts.csv", index=False)
    print(
        f"Found {len(common):,} common failures among "
        f"{int(summaries.primary_eligible.sum()):,} fully evaluable binary items."
    )


if __name__ == "__main__":
    main()
