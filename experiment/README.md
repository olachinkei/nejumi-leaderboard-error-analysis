# Nejumi Leaderboard 4 failure analysis

This directory contains the reproducible implementation for `../analysis_detail.md`
(the analysis protocol; the original planning document `Plan.md` has been
superseded and removed once `analysis_detail.md` was written to fully absorb
its content).

## Safety

- The repository-root `.env` is read only for credentials.
- API key values are never printed or persisted.
- Downloaded raw W&B tables, caches, and logs are excluded from version control.
- Public outputs must follow `config/publication_policy.yaml`.

## Reproduction

Run commands from `experiment/`.

```bash
uv sync
uv run python -m leaderboard_analysis.freeze_snapshot
uv run python -m leaderboard_analysis.freeze_ranking
uv run python -m leaderboard_analysis.inventory_artifacts
uv run python scripts/recompute_m_ifeval_strict.py
uv run python -m leaderboard_analysis.normalize_tables
uv run python -m leaderboard_analysis.extract_common_failures
uv run python -m leaderboard_analysis.prepare_llm_inputs
uv run python -m leaderboard_analysis.analyze_operational_cost
uv run python -m leaderboard_analysis.validate_scores
uv run python -m leaderboard_analysis.build_report
uv run python -m leaderboard_analysis.validate
uv run pytest
```

Each stage writes a machine-readable manifest under `data/manifests/`. Later
stages must consume those manifests instead of querying mutable aliases.
`scripts/recompute_m_ifeval_strict.py` must run before `normalize_tables`: it
derives `data/interim/m_ifeval_strict.parquet`, the official
`follow_all_instructions` binary recomputed offline from already-captured
prompt/response text (see `correctness_registry.yaml`'s `m_ifeval` rule).
Phase 5 and 6 JSON files were produced by Codex sub-agents using
`gpt-5.6-sol` with reasoning effort `high`; their fixed inputs and hashes are
under `outputs/llm/input/`.

## Current status (v3)

- Phase 0: complete — environment, lockfile, source SHAs, and secret handling fixed
- Phase 1: complete — 102 `leaderboard`-tagged runs ranked from individual tables;
  the top-20 run manifest is frozen
- Phase 2: complete — 440 output tables verified and correctness rules frozen.
  `correctness_registry.yaml` is at `version: 3`; see its `revision_note` for the
  full v1→v2→v3 history (toxicity 12-item partial inclusion, M-IFEval offline
  recomputation, and the move from a fixed half-scale cut to a bottom-quartile
  convention for jhumaneval/mtbench/jmmlu_robust/jaster char_f1+comet_wmt22).
- Phase 3: complete — 7,026 items expanded to 140,520 explicit item/run rows
- Phase 4: complete — **857** common failures (v3; was 796 in v2, 640 originally)
  extracted with threshold sensitivity. v3's bottom-quartile convention
  materially changed which items qualify: jhumaneval 67→3, mtbench 0→2, jaster
  471→594 (comet_wmt22 items newly qualify for the first time).
- Phase 5: complete for all 857 items, but with a **classifier substitution**:
  gpt-5.6-sol high was not reachable in this environment, so every item beyond
  the original 640 (jaster's char_f1/comet_wmt22 deltas, jhumaneval, m_ifeval,
  toxicity, mtbench) was classified by Claude (this session's model) instead.
  This is flagged in each affected `outputs/llm/by_benchmark/*.json`'s
  `limitations` and in `outputs/llm/cross_benchmark/synthesis.json`'s
  `scope.v3_note`. New/changed items were assigned into *existing* frozen
  taxonomies where one already existed (jaster, jhumaneval); jhumaneval was
  pruned back down to its 3 remaining items; m_ifeval, toxicity, and mtbench
  got fresh small taxonomies. Notable findings: (1) the M-IFEval batch
  surfaced a real, verified checker bug (`ja:keywords:existence` requires an
  exact single-token match from the Janome tokenizer, so it fails on any
  keyword the tokenizer splits across two tokens); (2) a Jaster ALT-corpus
  translation pair (`alt-e-to-j|89` / `alt-j-to-e|89`) where the reference
  translation itself confuses "Austrian" and "Australian", penalizing every
  model that translated faithfully. Both were verified directly against the
  underlying code/data, independent of any LLM judgment.
- Phase 6: complete — all benchmark-level categories (original + v2 + v3) were
  mapped into the existing 8-pattern cross-taxonomy (no new pattern was
  needed); `synthesis.json`'s narrative prose fields (`cause_summary`,
  `benchmark_or_evaluator_implications`, etc.) still describe only the
  original 640 and were not rewritten — only `cross_taxonomy` and
  `benchmark_category_mapping`, which is all `build_report` consumes, are kept
  current.
- Phase 7: complete with limitations — only evidenced token/size/row metrics retained
- Phase 8: complete — `report.html`, `outputs/paper_facts.json`, and the
  article figures (`outputs/figures/*.png`, via
  `scripts/generate_article_figures.py`) are regenerated from the merged
  classification files and reflect the v3 857/6,953/7,026 figures.
- Phase 9: complete — the article now lives as chapter files (`../0_abstract.md`,
  `../1_introduction.md`, `../2_method.md`, `../3_result.md`, `../4_thought.md`,
  `../5_references.md`) assembled into `../all.md`, which has no length budget.
  The original compact `../Paper.md` (3,400–5,100 characters, v2 numbers) was
  retired and deleted once `all.md` fully superseded it; `validate.py`'s
  placeholder check now targets `all.md` instead, with no length constraint
  (that budget was specific to Paper.md's format). The reference list lives in
  its own chapter file (`../5_references.md`) at the end of the article rather
  than inline after the introduction. There is no standalone "終わりに"
  (conclusion) chapter — that content was folded into the article or dropped.
- Phase 10: complete — `uv run python -m leaderboard_analysis.validate` and
  `pytest` both pass against the v3 state.
