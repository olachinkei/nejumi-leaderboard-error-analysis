from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import pandas as pd

from leaderboard_analysis.common import (
    MANIFEST_DIR,
    PROJECT_ROOT,
    load_config,
    read_json,
    write_json,
)

PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"
LLM_DIR = PROJECT_ROOT / "outputs" / "llm" / "by_benchmark"
ALLOWED_CAUSES = {
    "model_capability",
    "format_or_protocol",
    "ambiguous_or_underspecified",
    "reference_or_evaluator",
    "data_or_version",
    "mixed",
    "uncertain",
}


def assignment_category(assignment: dict[str, Any]) -> str:
    return str(assignment.get("category_id", assignment.get("category", "")))


def assignment_cause(assignment: dict[str, Any]) -> str:
    return str(assignment.get("cause_axis", assignment.get("cause", "")))


def validate_classifications(common: pd.DataFrame) -> tuple[list[dict[str, Any]], list[str]]:
    details = []
    errors = []
    for benchmark, expected in common.groupby("benchmark"):
        path = LLM_DIR / f"{benchmark}.json"
        if not path.exists():
            errors.append(f"Missing classification file: {path}")
            continue
        payload = read_json(path)
        taxonomy = payload.get("taxonomy", [])
        assignments = payload.get("assignments", [])
        category_ids = [str(item.get("category_id", "")) for item in taxonomy]
        if len(category_ids) != len(set(category_ids)):
            errors.append(f"{benchmark}: duplicate taxonomy IDs")
        if category_ids.count("other") != 1:
            errors.append(f"{benchmark}: taxonomy must contain other exactly once")
        if len([value for value in category_ids if value != "other"]) > 7:
            errors.append(f"{benchmark}: more than seven regular categories")
        if len(assignments) != len(expected):
            errors.append(f"{benchmark}: {len(assignments)} assignments for {len(expected)} items")
        assigned_categories = [assignment_category(item) for item in assignments]
        unknown = set(assigned_categories) - set(category_ids)
        if unknown:
            errors.append(f"{benchmark}: unknown categories {sorted(unknown)}")
        invalid_causes = {assignment_cause(item) for item in assignments} - ALLOWED_CAUSES
        if invalid_causes:
            errors.append(f"{benchmark}: invalid causes {sorted(invalid_causes)}")
        invalid_confidence = [
            item.get("confidence")
            for item in assignments
            if not isinstance(item.get("confidence"), (int, float))
            or not 0 <= item["confidence"] <= 1
        ]
        if invalid_confidence:
            errors.append(f"{benchmark}: invalid confidence values")
        if benchmark == "jaster":
            actual_ids = [str(item.get("item_key", "")) for item in assignments]
            expected_ids = expected["item_key"].astype(str).tolist()
        else:
            actual_ids = [str(item.get("item_id", "")) for item in assignments]
            expected_ids = expected["item_id"].astype(str).tolist()
        if len(actual_ids) != len(set(actual_ids)):
            errors.append(f"{benchmark}: duplicate assignment IDs")
        if set(actual_ids) != set(expected_ids):
            errors.append(f"{benchmark}: assignment ID set mismatch")
        evidence = {
            str(evidence_id)
            for item in assignments
            for evidence_id in item.get("evidence_item_ids", [])
        }
        if not evidence.issubset(set(expected["item_id"].astype(str))):
            errors.append(f"{benchmark}: evidence contains unknown item IDs")
        details.append(
            {
                "benchmark": benchmark,
                "taxonomy_categories": len(category_ids),
                "assignments": len(assignments),
                "cause_values": sorted({assignment_cause(item) for item in assignments}),
                "status": "passed",
            }
        )
    return details, errors


def visible_japanese_characters(path: Path) -> int:
    text = path.read_text(encoding="utf-8")
    text = text.split("\n## Appendix", maxsplit=1)[0]
    text = re.sub(r"```[\s\S]*?```", "", text)
    text = re.sub(r"[#>*_`\[\]\(\)\-|]", "", text)
    return len(re.sub(r"\s+", "", text))


def main() -> None:
    errors: list[str] = []
    checks: dict[str, Any] = {}
    top20 = pd.read_csv(MANIFEST_DIR / "top20_runs.csv")
    artifact_manifest = pd.read_csv(MANIFEST_DIR / "artifact_manifest.csv")
    results = pd.read_parquet(PROCESSED_DIR / "item_results.parquet")
    item_summary = pd.read_parquet(PROCESSED_DIR / "item_summary.parquet")
    common = pd.read_parquet(PROCESSED_DIR / "common_failures.parquet")
    facts = read_json(PROJECT_ROOT / "outputs" / "paper_facts.json")
    config = load_config()

    checks["top20_unique_runs"] = bool(len(top20) == 20 and top20["run_id"].nunique() == 20)
    checks["top20_required_tag"] = bool(
        "required_tag" in top20
        and top20["required_tag"].eq(config["ranking"]["required_tag"]).all()
    )
    checks["artifact_manifest_complete"] = bool(
        len(artifact_manifest) == 440
        and artifact_manifest["run_id"].nunique() == 20
        and artifact_manifest["extraction_status"].eq("verified").all()
    )
    checks["item_cross_product"] = bool(
        results["item_key"].nunique() == 7026
        and len(results) == results["item_key"].nunique() * 20
        and results.groupby("item_key")["run_id"].nunique().eq(20).all()
    )
    expected_common = item_summary[
        item_summary["n_evaluable"].eq(config["common_failure"]["required_run_count"])
        & item_summary["n_wrong"].ge(config["common_failure"]["minimum_wrong_count"])
    ]
    checks["common_failure_contract"] = bool(
        set(common["item_key"]) == set(expected_common["item_key"])
        and common["n_evaluable"]
        .eq(config["common_failure"]["required_run_count"])
        .all()
        and common["n_wrong"].ge(config["common_failure"]["minimum_wrong_count"]).all()
    )
    checks["facts_match"] = (
        facts["top20_run_count"] == len(top20)
        and facts["normalized_item_count"] == results["item_key"].nunique()
        and facts["common_failure_count"] == len(common)
    )
    classification_details, classification_errors = validate_classifications(common)
    errors.extend(classification_errors)
    checks["classification_schema"] = not classification_errors

    score_path = PROJECT_ROOT / "outputs" / "tables" / "score_validation.csv"
    if score_path.exists():
        score_checks = pd.read_csv(score_path)
        checks["published_score_reproduction"] = bool(score_checks["passed"].all())
        checks["published_score_check_count"] = len(score_checks)
    else:
        checks["published_score_reproduction"] = False
        errors.append("score_validation.csv is missing")

    report_path = PROJECT_ROOT / "report.html"
    checks["report_exists"] = report_path.exists() and report_path.stat().st_size > 100_000
    if report_path.exists():
        report_text = report_path.read_text(encoding="utf-8")
        visible_report = re.sub(
            r"<(?:script|style)\b[^>]*>[\s\S]*?</(?:script|style)>",
            "",
            report_text,
            flags=re.IGNORECASE,
        )
        checks["report_has_no_placeholder"] = re.search(r"\bXX\b", visible_report) is None
        checks["report_has_no_api_key_assignment"] = "WANDB_API_KEY=" not in report_text

    # Paper.md (the original 3,400-5,100 character compact article) was
    # retired in favor of the chapter files (0_abstract.md .. 5_references.md)
    # assembled into all.md, which has no analogous length budget. Only the
    # placeholder check still applies.
    article_path = PROJECT_ROOT.parent / "all.md"
    if article_path.exists():
        checks["article_character_count"] = visible_japanese_characters(article_path)
        checks["article_has_no_placeholder"] = "XX" not in article_path.read_text(
            encoding="utf-8"
        )

    for name, passed in checks.items():
        if isinstance(passed, bool) and not passed:
            errors.append(f"Failed check: {name}")
    report = {
        "status": "passed" if not errors else "failed",
        "checks": checks,
        "classification_details": classification_details,
        "errors": errors,
    }
    write_json(PROJECT_ROOT / "outputs" / "validation_report.json", report)
    if errors:
        raise RuntimeError(f"Validation failed with {len(errors)} errors")
    print("All validation checks passed.")


if __name__ == "__main__":
    main()
