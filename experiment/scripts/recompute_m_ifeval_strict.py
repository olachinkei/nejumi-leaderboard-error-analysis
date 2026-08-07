"""Recompute the official M-IFEval prompt-level strict accuracy.

The pinned evaluator (`scripts/evaluator/evaluate_utils/m_ifeval_utils.py`,
`test_instruction_following_strict`) already computes `follow_all_instructions`
(bool, AND across every instruction in the prompt) before it is reduced to a
fractional `score` and logged to `m_ifeval_output_table`. This script reloads
the checker module standalone (bypassing `evaluate_utils/__init__.py`, which
pulls in unrelated heavy dependencies) and reruns it offline against the
`prompt`/`response`/`instruction_id_list`/`kwargs` text already captured in the
cached raw tables, so no new model calls are needed.

Output: data/interim/m_ifeval_strict.parquet
    columns: run_id, key, follow_all_instructions, n_instructions, n_followed,
             recompute_status, stored_score, score_reproduced

`score_reproduced` flags whether `n_followed / n_instructions` matches the
originally logged fractional score (sanity check against checker drift).
"""

from __future__ import annotations

import ast
import glob
import importlib.util
import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "data" / "raw" / "output_tables"
INTERIM_DIR = ROOT / "data" / "interim"
TOP20_CSV = ROOT / "data" / "manifests" / "top20_runs.csv"
CHECKER_PATH = (
    ROOT
    / "vendor"
    / "llm-leaderboard"
    / "scripts"
    / "evaluator"
    / "evaluate_utils"
    / "m_ifeval_utils.py"
)


def load_checker_module():
    spec = importlib.util.spec_from_file_location("m_ifeval_utils_standalone", CHECKER_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    # Fix language-detection nondeterminism so repeated runs are stable.
    try:
        import langdetect

        langdetect.DetectorFactory.seed = 0
    except Exception:
        pass
    return module


def find_table_path(run_id: str) -> Path | None:
    pattern = RAW_DIR / run_id / "media" / "table" / "m_ifeval_output_table_*.table.json"
    matches = glob.glob(str(pattern))
    if not matches:
        return None
    return Path(sorted(matches)[0])


def main() -> None:
    mod = load_checker_module()
    top20 = pd.read_csv(TOP20_CSV)

    records = []
    for run_id in top20["run_id"]:
        table_path = find_table_path(run_id)
        if table_path is None:
            print(f"WARNING: no m_ifeval_output_table found for run {run_id}", file=sys.stderr)
            continue
        payload = json.loads(table_path.read_text())
        cols = payload["columns"]
        idx = {c: i for i, c in enumerate(cols)}
        for row in payload["data"]:
            key = row[idx["key"]]
            prompt = row[idx["prompt"]]
            response = row[idx["response"]]
            stored_score = row[idx["score"]]
            try:
                instruction_id_list = ast.literal_eval(row[idx["instruction_id_list"]])
                kwargs = ast.literal_eval(row[idx["kwargs"]])
            except (ValueError, SyntaxError) as exc:
                records.append(
                    {
                        "run_id": run_id,
                        "key": key,
                        "follow_all_instructions": None,
                        "n_instructions": None,
                        "n_followed": None,
                        "recompute_status": f"parse_error:{exc}",
                        "stored_score": stored_score,
                        "score_reproduced": None,
                    }
                )
                continue

            inp = mod.InputExample(
                key=key, instruction_id_list=instruction_id_list, prompt=prompt, kwargs=kwargs
            )
            prompt_to_response = {prompt: response}
            try:
                out = mod.test_instruction_following_strict(inp, prompt_to_response)
                score_reproduced = abs(out.score - float(stored_score)) < 1e-6
                records.append(
                    {
                        "run_id": run_id,
                        "key": key,
                        "follow_all_instructions": bool(out.follow_all_instructions),
                        "n_instructions": len(out.follow_instruction_list),
                        "n_followed": int(sum(out.follow_instruction_list)),
                        "recompute_status": "ok",
                        "stored_score": stored_score,
                        "score_reproduced": bool(score_reproduced),
                    }
                )
            except Exception as exc:  # noqa: BLE001 - checker errors must not silently drop items
                records.append(
                    {
                        "run_id": run_id,
                        "key": key,
                        "follow_all_instructions": None,
                        "n_instructions": None,
                        "n_followed": None,
                        "recompute_status": f"checker_error:{type(exc).__name__}:{exc}",
                        "stored_score": stored_score,
                        "score_reproduced": None,
                    }
                )

    frame = pd.DataFrame.from_records(records)
    INTERIM_DIR.mkdir(parents=True, exist_ok=True)
    out_path = INTERIM_DIR / "m_ifeval_strict.parquet"
    frame.to_parquet(out_path, index=False)

    total = len(frame)
    ok = int((frame["recompute_status"] == "ok").sum())
    mismatched = int((frame["score_reproduced"] == False).sum())  # noqa: E712
    errors = total - ok
    print(f"Wrote {total:,} rows to {out_path}")
    print(f"  recomputed ok: {ok:,} ({ok / total:.1%})")
    print(f"  errors/parse failures: {errors:,}")
    print(f"  score mismatches among ok rows: {mismatched:,}")
    if errors:
        print("Non-ok statuses:")
        print(frame.loc[frame["recompute_status"] != "ok", "recompute_status"].value_counts())


if __name__ == "__main__":
    main()
