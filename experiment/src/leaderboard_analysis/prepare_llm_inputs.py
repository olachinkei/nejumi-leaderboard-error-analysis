from __future__ import annotations

import json
from collections import Counter
from datetime import datetime
from zoneinfo import ZoneInfo

import pandas as pd
import yaml

from leaderboard_analysis.common import PROJECT_ROOT, json_hash, sha256_file, write_json
from leaderboard_analysis.normalize_tables import normalized_text

PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"
OUTPUT_DIR = PROJECT_ROOT / "outputs" / "llm" / "input"
PROMPT_PATH = PROJECT_ROOT / "prompts" / "by_benchmark_classification.md"


def compact_answer(benchmark: str, answer: str) -> tuple[str, bool]:
    normalized = normalized_text(answer)
    if benchmark == "swebench" and normalized:
        return f"[patch chars={len(normalized)} sha256={json_hash(normalized)}]", True
    limit = 1200
    if len(normalized) <= limit:
        return normalized, False
    return normalized[:limit] + "…", True


def main() -> None:
    results = pd.read_parquet(PROCESSED_DIR / "item_results.parquet")
    common = pd.read_parquet(PROCESSED_DIR / "common_failures.parquet")
    top20 = pd.read_csv(PROJECT_ROOT / "data" / "manifests" / "top20_runs.csv")
    aliases = {
        row.run_id: {
            "alias": f"M{int(row.rank):02d}",
            "rank": int(row.rank),
            "model_name": row.model_name,
        }
        for row in top20.itertuples()
    }
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    write_json(OUTPUT_DIR / "model_aliases.private.json", aliases)

    rules = yaml.safe_load(
        (PROJECT_ROOT / "config" / "correctness_registry.yaml").read_text(encoding="utf-8")
    )["rules"]
    rule_by_benchmark = {
        benchmark: {
            key: value
            for key, value in rule.items()
            if key in {"score_field", "binary_rule", "source", "note", "caveat"}
        }
        for benchmark, rule in rules.items()
    }

    manifest = {
        "created_at": datetime.now(ZoneInfo("Asia/Tokyo")).isoformat(),
        "prompt_sha256": sha256_file(PROMPT_PATH),
        "input_files": {},
        "model": "gpt-5.6-sol",
        "reasoning_effort": "high",
        "temperature": "unsupported_in_codex_subagent",
        "top_p": "unsupported_in_codex_subagent",
        "seed": "unsupported_in_codex_subagent",
    }
    common_keys = set(common["item_key"])
    selected = results[results["item_key"].isin(common_keys)].copy()
    for benchmark, benchmark_items in common.groupby("benchmark", sort=True):
        path = OUTPUT_DIR / f"{benchmark}.jsonl"
        item_payloads = []
        for item in benchmark_items.sort_values("item_key").itertuples():
            rows = selected[selected["item_key"] == item.item_key].sort_values("rank")
            answer_counts: Counter[str] = Counter()
            answers = []
            any_truncated = False
            for row in rows.itertuples():
                compact, truncated = compact_answer(benchmark, row.model_answer)
                any_truncated |= truncated
                if compact:
                    answer_counts[compact] += 1
                answers.append(
                    {
                        "model": aliases[row.run_id]["alias"],
                        "answer": compact,
                        "raw_score": row.raw_score,
                        "is_correct": (None if pd.isna(row.is_correct) else bool(row.is_correct)),
                        "status": row.evaluation_status,
                    }
                )
            patterns = [
                {"answer": answer, "count": count} for answer, count in answer_counts.most_common()
            ]
            item_payloads.append(
                {
                    "item_key": item.item_key,
                    "item_id": item.item_id,
                    "benchmark": benchmark,
                    "subtask": item.subtask,
                    "evaluation_condition": item.evaluation_condition,
                    "metric": item.metric,
                    "question": item.question,
                    "reference_answer": item.reference_answer,
                    "scoring_rule": rule_by_benchmark.get(benchmark, {}),
                    "wrong_count": int(item.n_wrong),
                    "evaluable_count": int(item.n_evaluable),
                    "answer_patterns": patterns,
                    "answers": answers,
                    "content_truncated_or_structured": any_truncated,
                }
            )
        with path.open("w", encoding="utf-8") as handle:
            for payload in item_payloads:
                handle.write(json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n")
        manifest["input_files"][benchmark] = {
            "path": str(path.relative_to(PROJECT_ROOT)),
            "items": len(item_payloads),
            "sha256": sha256_file(path),
        }
    write_json(OUTPUT_DIR / "manifest.json", manifest)
    print(
        f"Prepared {len(common):,} classification items in "
        f"{len(manifest['input_files'])} benchmark files."
    )


if __name__ == "__main__":
    main()
