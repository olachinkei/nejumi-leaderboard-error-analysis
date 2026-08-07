from __future__ import annotations

import pandas as pd

from leaderboard_analysis.common import MANIFEST_DIR, PROJECT_ROOT, write_json
from leaderboard_analysis.normalize_tables import table_frame

PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"
TABLE_DIR = PROJECT_ROOT / "outputs" / "tables"


def main() -> None:
    manifest = pd.read_csv(MANIFEST_DIR / "artifact_manifest.csv")
    selected = manifest[manifest["official_or_dev"] == "official_candidate"]
    rows = []
    for row in selected.itertuples():
        frame = table_frame(row.run_id, row.run_file_path)
        prompt_tokens = (
            pd.to_numeric(frame["prompt_tokens"], errors="coerce").sum(min_count=1)
            if "prompt_tokens" in frame
            else None
        )
        completion_tokens = (
            pd.to_numeric(frame["completion_tokens"], errors="coerce").sum(min_count=1)
            if "completion_tokens" in frame
            else None
        )
        if "input_token_count" in frame:
            prompt_tokens = pd.to_numeric(frame["input_token_count"], errors="coerce").sum(
                min_count=1
            )
        if "output_token_count" in frame:
            completion_tokens = pd.to_numeric(frame["output_token_count"], errors="coerce").sum(
                min_count=1
            )
        rows.append(
            {
                "run_id": row.run_id,
                "rank": row.rank,
                "benchmark": row.benchmark,
                "summary_key": row.summary_key,
                "observed_rows": len(frame),
                "artifact_size_bytes": row.artifact_size,
                "prompt_tokens_observed": prompt_tokens,
                "completion_tokens_observed": completion_tokens,
                "token_source": (
                    "output_table"
                    if prompt_tokens is not None or completion_tokens is not None
                    else "not_available"
                ),
            }
        )
    metrics = pd.DataFrame(rows)
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    TABLE_DIR.mkdir(parents=True, exist_ok=True)
    metrics.to_csv(PROCESSED_DIR / "operational_metrics.csv", index=False)
    coverage = (
        metrics.groupby("benchmark")
        .agg(
            tables=("summary_key", "count"),
            runs=("run_id", "nunique"),
            observed_rows=("observed_rows", "sum"),
            artifact_size_bytes=("artifact_size_bytes", "sum"),
            tables_with_token_counts=(
                "token_source",
                lambda values: values.eq("output_table").sum(),
            ),
            prompt_tokens_observed=("prompt_tokens_observed", "sum"),
            completion_tokens_observed=("completion_tokens_observed", "sum"),
        )
        .reset_index()
    )
    coverage.to_csv(TABLE_DIR / "operational_coverage.csv", index=False)
    limitations = {
        "status": "partial",
        "available": [
            "output-table row counts",
            "output-table artifact byte sizes",
            "prompt/completion tokens where explicitly logged",
        ],
        "not_available": [
            "provider billing amounts",
            "benchmark-level wall-clock time",
            "judge token counts for every judge benchmark",
            "GPU/CPU resource-hours",
            "agent step counts",
        ],
        "decision": (
            "No monetary-cost or benchmark-duration chart will be published; "
            "coverage-only operational evidence is retained."
        ),
    }
    write_json(PROCESSED_DIR / "operational_limitations.json", limitations)
    print(
        f"Wrote operational evidence for {len(metrics)} run/table pairs; "
        f"token counts exist for {metrics.token_source.eq('output_table').sum()}."
    )


if __name__ == "__main__":
    main()
