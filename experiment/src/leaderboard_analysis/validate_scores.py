from __future__ import annotations

import ast
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pandas as pd
import wandb
from dotenv import load_dotenv

from leaderboard_analysis.common import MANIFEST_DIR, PROJECT_ROOT, WORKSPACE_ROOT, read_json
from leaderboard_analysis.freeze_ranking import selective_run_metadata
from leaderboard_analysis.inventory_artifacts import download_tables
from leaderboard_analysis.normalize_tables import table_frame

RAW_SCORE_DIR = PROJECT_ROOT / "data" / "raw" / "score_validation"
OUTPUT_PATH = PROJECT_ROOT / "outputs" / "tables" / "score_validation.csv"

LEADERBOARD_KEYS = [
    "arc_agi_leaderboard_table",
    "bfcl_leaderboard_table",
    "hallulens_leaderboard_table",
    "hle_test_leaderboard_table",
    "jaster_0shot_leaderboard_table",
    "jaster_2shot_leaderboard_table",
    "jbbq_2shot_leaderboard_table",
    "jhumaneval_leaderboard_table",
    "jmmlu_robust_2shot_leaderboard_table",
    "jtruthfulqa_leaderboard_table",
    "m_ifeval_leaderboard_table",
    "mtbench_leaderboard_table",
    "swebench_leaderboard_table",
]


def row_dict(path: Path) -> dict[str, Any]:
    payload = read_json(path)
    return dict(zip(payload["columns"], payload["data"][0], strict=True))


def add_result(
    rows: list[dict[str, Any]],
    run_id: str,
    benchmark: str,
    metric: str,
    calculated: float,
    published: float,
    tolerance: float = 1e-9,
) -> None:
    difference = abs(float(calculated) - float(published))
    rows.append(
        {
            "run_id": run_id,
            "benchmark": benchmark,
            "metric": metric,
            "calculated": calculated,
            "published": published,
            "absolute_difference": difference,
            "tolerance": tolerance,
            "passed": difference <= tolerance,
        }
    )


def bfcl_overall_accuracy(frame: pd.DataFrame) -> float:
    category = frame.groupby("category")["accuracy"].agg(["mean", "count"])
    simple = category.loc[["simple", "java", "javascript"], "mean"].mean()
    non_live = pd.Series(
        [simple, category.loc["multiple", "mean"], category.loc["irrelevance", "mean"]]
    ).mean()
    live_names = ["live_simple", "live_multiple", "live_irrelevance", "live_relevance"]
    live = (
        category.loc[live_names, "mean"] * category.loc[live_names, "count"]
    ).sum() / category.loc[live_names, "count"].sum()
    multi = category.loc[
        ["multi_turn_base", "multi_turn_miss_func", "multi_turn_miss_param"], "mean"
    ].mean()
    return float(pd.Series([non_live, live, multi]).mean())


def main() -> None:
    load_dotenv(WORKSPACE_ROOT / ".env", override=False)
    top20 = pd.read_csv(MANIFEST_DIR / "top20_runs.csv")
    output_manifest = pd.read_csv(MANIFEST_DIR / "artifact_manifest.csv")
    api = wandb.Api(timeout=60)
    project = "llm-leaderboard/nejumi-leaderboard4"
    run_metadata, _ = selective_run_metadata(
        api,
        project,
        {"name": {"$in": top20["run_id"].tolist()}},
        LEADERBOARD_KEYS,
        limit=20,
    )
    metadata_by_id = {row["run_id"]: row for row in run_metadata}
    checks: list[dict[str, Any]] = []
    for number, top in enumerate(top20.itertuples(), start=1):
        metadata = metadata_by_id[top.run_id]
        run = SimpleNamespace(
            id=top.run_id,
            entity="llm-leaderboard",
            project="nejumi-leaderboard4",
        )
        pointers = {key: metadata[key] for key in LEADERBOARD_KEYS}
        downloaded = download_tables(api, run, pointers, RAW_SCORE_DIR / run.id)
        leaders = {key: row_dict(downloaded[pointer["path"]]) for key, pointer in pointers.items()}
        print(f"[{number:02d}/20] validating {run.id}", flush=True)

        by_key = {
            row.summary_key: row.run_file_path
            for row in output_manifest[output_manifest["run_id"] == run.id].itertuples()
        }
        arc1 = table_frame(
            run.id,
            by_key["arc_agi_1_output_table"],
        )
        arc2 = table_frame(
            run.id,
            by_key["arc_agi_2_output_table"],
        )
        for label, frame in (("arc-agi-1", arc1), ("arc-agi-2", arc2)):
            score = (
                frame.groupby(["task_id", "test_example_id"])["correct"]
                .max()
                .groupby("task_id")
                .mean()
                .mean()
            )
            add_result(
                checks, run.id, "arc_agi", label, score, leaders["arc_agi_leaderboard_table"][label]
            )

        bfcl = table_frame(run.id, by_key["bfcl_output_table"])
        add_result(
            checks,
            run.id,
            "bfcl",
            "Overall Acc",
            bfcl_overall_accuracy(bfcl),
            leaders["bfcl_leaderboard_table"]["Overall Acc"],
        )

        hallu = table_frame(run.id, by_key["hallulens_output_table"])
        add_result(
            checks,
            run.id,
            "hallulens",
            "hallucination_resistance",
            1 - hallu["does_believe"].mean(),
            leaders["hallulens_leaderboard_table"]["hallucination_resistance"],
        )

        hle = table_frame(run.id, by_key["hle_test_output_table"])
        hle_target = leaders["hle_test_leaderboard_table"]
        hle_score = hle["correct"].eq("yes").sum() / hle_target["total_questions"]
        add_result(
            checks, run.id, "hle", "accuracy", hle_score, hle_target["accuracy"], tolerance=5.1e-5
        )

        for shot in ("0shot", "2shot"):
            frame = table_frame(run.id, by_key[f"jaster_{shot}_output_table"])
            target = leaders[f"jaster_{shot}_leaderboard_table"]
            task_scores = frame.groupby("task")["score"].mean()
            for task, score in task_scores.items():
                if task in target and pd.notna(score):
                    add_result(
                        checks,
                        run.id,
                        "jaster",
                        f"{shot}:{task}",
                        score,
                        target[task],
                        tolerance=1e-7,
                    )

        jbbq = table_frame(run.id, by_key["jbbq_2shot_output_table"])
        add_result(
            checks,
            run.id,
            "jbbq",
            "acc",
            jbbq["correct"].mean(),
            leaders["jbbq_2shot_leaderboard_table"]["acc"],
        )

        jhuman = table_frame(run.id, by_key["jhumaneval_output_table"])
        for metric, score in jhuman.groupby("metrics")["score"].mean().items():
            add_result(
                checks,
                run.id,
                "jhumaneval",
                metric,
                score,
                leaders["jhumaneval_leaderboard_table"][metric],
                tolerance=1e-7,
            )

        robust = table_frame(run.id, by_key["jmmlu_robust_2shot_output_table"])
        add_result(
            checks,
            run.id,
            "jmmlu_robust",
            "robust_score",
            robust["score"].mean(),
            leaders["jmmlu_robust_2shot_leaderboard_table"]["robust_score"],
        )

        truth = table_frame(run.id, by_key["jtruthfulqa_output_table"])
        add_result(
            checks,
            run.id,
            "jtruthfulqa",
            "overall_score",
            truth["Label"].mean(),
            leaders["jtruthfulqa_leaderboard_table"]["overall_score"],
        )

        ifeval = table_frame(run.id, by_key["m_ifeval_output_table"])
        instruction_counts = ifeval["instruction_id_list"].map(
            lambda value: len(ast.literal_eval(value))
        )
        ifeval_score = (ifeval["score"] * instruction_counts).sum() / instruction_counts.sum()
        add_result(
            checks,
            run.id,
            "m_ifeval",
            "m_ifeval_score",
            ifeval_score,
            leaders["m_ifeval_leaderboard_table"]["m_ifeval_score"],
        )

        mtbench = table_frame(run.id, by_key["mtbench_output_table"])
        valid = mtbench[mtbench["score"] != -1]
        per_turn = valid.groupby(["question_id", "turn", "category"], as_index=False)[
            "score"
        ].mean()
        category_scores = per_turn.groupby("category")["score"].mean() / 10
        add_result(
            checks,
            run.id,
            "mtbench",
            "AVG_mtbench",
            category_scores.mean(),
            leaders["mtbench_leaderboard_table"]["AVG_mtbench"],
            tolerance=1e-7,
        )

        swe = table_frame(run.id, by_key["swebench_output_table"])
        swe_target = leaders["swebench_leaderboard_table"]
        swe_score = swe["status"].eq("resolved").sum() / swe_target["total_samples"]
        add_result(
            checks, run.id, "swebench", "resolution_rate", swe_score, swe_target["resolution_rate"]
        )

    validation = pd.DataFrame(checks)
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    validation.to_csv(OUTPUT_PATH, index=False)
    failures = validation[~validation["passed"]]
    print(f"Passed {validation.passed.sum()}/{len(validation)} score checks.")
    if not failures.empty:
        raise RuntimeError(f"{len(failures)} score checks failed; see {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
