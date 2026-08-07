"""Generate static figures for the article (1_introduction.md .. all.md) from
validated aggregate data only (outputs/paper_facts.json + outputs/llm/by_benchmark).
No raw item text is plotted or embedded, consistent with publication_policy.yaml,
EXCEPT the ARC-AGI worked example, which renders the puzzle grids themselves
(numeric color-index grids, not natural-language text) to make one specific,
already-discussed common failure (item arc_agi:0d87d2a6|0) concrete. The grid
values below were read from the cached raw output tables for that item and are
reproduced here only for this one illustrative figure.

Follows the project's dataviz conventions: a single categorical hue per
non-comparative bar chart (identity is carried by the axis labels, not color),
direct value labels at the bar tip instead of a legend, hairline recessive
gridlines, no dual axes.
"""

from __future__ import annotations

import csv
import textwrap

import matplotlib.pyplot as plt
from matplotlib import rcParams
from matplotlib.colors import ListedColormap

from leaderboard_analysis.common import PROJECT_ROOT, read_json

FIGURES_DIR = PROJECT_ROOT / "outputs" / "figures"

# Use a system Japanese font directly; the japanize-matplotlib package depends
# on distutils, which was removed in Python 3.12.
rcParams["font.family"] = ["Hiragino Sans", "sans-serif"]
rcParams["axes.unicode_minus"] = False

# Reference categorical palette slot 1 (blue) -- see dataviz skill references/palette.md.
BAR_COLOR = "#2a78d6"
GRID_COLOR = "#d8dee6"
TEXT_COLOR = "#17212b"

CAUSE_AXIS_LABELS = {
    "model_capability": "モデル能力",
    "format_or_protocol": "出力形式・評価器",
    "reference_defect_axis": "参照解答の間違い",
    "ambiguous_or_underspecified": "曖昧さ・前提不足",
    "uncertain": "判定不能",
}

# The original classification pass used one combined "reference_or_evaluator"
# axis. Splitting it in two reads more clearly: cases where the reference/
# answer key itself is the problem ("参照解答の間違い") versus cases where a
# substantively correct answer is scored wrong by the checker/classifier/
# scoring design ("出力形式・評価器", folded into format_or_protocol). The
# split is per-item, keyed on each item's own taxonomy category_id -- not a
# blanket re-tagging of the whole axis -- since the same category_id can
# carry a different cause_axis on other items (e.g. temporal_snapshot also
# appears under data_or_version elsewhere).
REFERENCE_DEFECT_CATEGORY_IDS = {
    "reference_or_evaluator_defect",
    "answer_key_option_misalignment",
    "reference_defect",
    "tool_action_selection",
    "temporal_snapshot",
}

# "data_or_version" (stale evaluator code, mismatched data versions) is folded
# into "reference_defect_axis" -- both are "the record that defines
# correctness is wrong or stale", read as one article-facing category rather
# than two thin ones.
DATA_OR_VERSION_MERGES_INTO = "reference_defect_axis"

# "mixed" was originally its own catch-all axis for items with more than one
# plausible cause. Read alone it added little (it never anchored one of the
# article's worked examples), so each item is reassigned to whichever single
# axis its own taxonomy category_id points to most strongly. Re-derive this
# set from concise_rationale text if the classification data changes --
# it is not a mechanical rule.
MIXED_REASSIGNMENT = {
    "equivalent_surface_form": "format_or_protocol",
    "label_protocol_mismatch": "format_or_protocol",
    "constrained_value": "format_or_protocol",
    "multi_claim_selection": "format_or_protocol",
    "reference_conflict": "format_or_protocol",
    "cat_checker_mismatch": "format_or_protocol",
    "definitive_stance_compliance": "format_or_protocol",
    "linguistic_inference_boundary": "ambiguous_or_underspecified",
    "scope_ambiguity": "ambiguous_or_underspecified",
    "relevance_boundary": "ambiguous_or_underspecified",
    "underspecified": "ambiguous_or_underspecified",
    "substantive_reasoning_or_knowledge": "model_capability",
    "other": "uncertain",
}

# Display name and "is this a big benchmark (own bar-chart panel) or a small
# one (bullet list panel)" is derived from the actual assignment count at
# runtime -- see make_category_breakdown_figure(). This dict only supplies
# display names.
BENCHMARK_DISPLAY_NAMES = {
    "jaster": "Jaster",
    "hle": "HLE",
    "jtruthfulqa": "JTruthfulQA",
    "bfcl": "BFCL",
    "m_ifeval": "M-IFEval",
    "arc_agi": "ARC-AGI",
    "jbbq": "JBBQ",
    "jhumaneval": "JHumanEval",
    "mtbench": "MT-Bench",
    "swebench": "SWE-bench",
    "toxicity": "Toxicity",
    "hallulens": "HalluLens",
    "jmmlu_robust": "JMMLU Robust",
}

# The original gpt-5.6-sol classification pass named some benchmarks'
# categories in English (arc_agi, bfcl, jbbq, swebench); translate the ones
# that appear in the article's figures so labels stay consistently Japanese.
CATEGORY_LABEL_OVERRIDES = {
    "multiturn_execution": "複数ターンの状態・順序・呼び出し漏れ",
    "schema_contract": "function schema・引数形状の不一致",
    "constrained_value": "制約値・正規化の不一致",
    "relevance_boundary": "無関係ツール境界の誤判定",
    "temporal_snapshot": "時点固定・snapshotの不一致",
    "tool_action_selection": "誤ったtool・実行段階の選択",
    "underspecified_no_call": "未指定requestとno-call処理",
    "incomplete_or_null_output": "出力欠落・null出力",
    "systematic_rule_misinference": "変換規則の系統的誤読",
    "localized_grid_execution_error": "グリッド構築の局所誤り",
    "answer_key_option_misalignment": "選択肢とanswer keyの対応不一致",
    "convergent_incomplete_patch": "同一の不完全なpatchへの収束",
    "fragmented_unsuccessful_approaches": "アプローチが分散し収束しない失敗",
}

# ---------------------------------------------------------------------------
# ARC-AGI worked example (item arc_agi:0d87d2a6|0): one training pair (to show
# the rule), the test input, the correct reference output, and the modal wrong
# answer (14/20 models). Read from data/raw/output_tables via
# outputs/llm/input/arc_agi.jsonl at analysis time; hardcoded here since this
# is a one-off illustrative figure, not a recomputed aggregate.
ARC_TRAIN_IN = [
    [0, 0, 0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0, 2, 2, 2, 2, 0, 0],
    [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 2, 2, 2, 2, 0, 0],
    [0, 0, 0, 0, 0, 0, 2, 2, 2, 2, 2, 0, 0, 0, 2, 2, 2, 2, 0, 0],
    [0, 0, 0, 0, 0, 0, 2, 2, 2, 2, 2, 0, 0, 0, 0, 0, 0, 0, 0, 0],
    [0, 0, 0, 0, 0, 0, 2, 2, 2, 2, 2, 0, 0, 0, 0, 0, 0, 0, 0, 0],
    [0, 0, 0, 0, 0, 0, 2, 2, 2, 2, 2, 0, 0, 0, 0, 0, 0, 0, 0, 0],
    [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
    [0, 0, 2, 2, 2, 2, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
    [1, 0, 2, 2, 2, 2, 0, 0, 0, 0, 0, 2, 2, 2, 2, 0, 0, 0, 0, 1],
    [0, 0, 2, 2, 2, 2, 0, 0, 0, 0, 0, 2, 2, 2, 2, 0, 0, 0, 0, 0],
    [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 2, 2, 2, 2, 0, 0, 0, 0, 0],
    [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
    [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
    [0, 0, 2, 2, 2, 2, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
    [0, 0, 2, 2, 2, 2, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
    [0, 0, 2, 2, 2, 2, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
    [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 2, 2, 2, 2, 2, 0],
    [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 2, 2, 2, 2, 2, 0],
    [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
    [0, 0, 0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
]
ARC_TRAIN_OUT = [
    [0, 0, 0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0, 2, 2, 2, 2, 0, 0],
    [0, 0, 0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0, 2, 2, 2, 2, 0, 0],
    [0, 0, 0, 0, 0, 0, 1, 1, 1, 1, 1, 0, 0, 0, 2, 2, 2, 2, 0, 0],
    [0, 0, 0, 0, 0, 0, 1, 1, 1, 1, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0],
    [0, 0, 0, 0, 0, 0, 1, 1, 1, 1, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0],
    [0, 0, 0, 0, 0, 0, 1, 1, 1, 1, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0],
    [0, 0, 0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
    [0, 0, 1, 1, 1, 1, 0, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
    [1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1],
    [0, 0, 1, 1, 1, 1, 0, 1, 0, 0, 0, 1, 1, 1, 1, 0, 0, 0, 0, 0],
    [0, 0, 0, 0, 0, 0, 0, 1, 0, 0, 0, 1, 1, 1, 1, 0, 0, 0, 0, 0],
    [0, 0, 0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
    [0, 0, 0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
    [0, 0, 2, 2, 2, 2, 0, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
    [0, 0, 2, 2, 2, 2, 0, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
    [0, 0, 2, 2, 2, 2, 0, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
    [0, 0, 0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0, 2, 2, 2, 2, 2, 0],
    [0, 0, 0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0, 2, 2, 2, 2, 2, 0],
    [0, 0, 0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
    [0, 0, 0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
]
ARC_TEST_IN = [
    [0, 0, 0, 0, 0, 1, 0, 0, 0, 2, 2, 2, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
    [0, 0, 0, 0, 0, 0, 0, 0, 0, 2, 2, 2, 0, 0, 0, 0, 0, 0, 0, 2, 2, 2, 2, 0, 0],
    [0, 0, 0, 0, 0, 0, 0, 0, 0, 2, 2, 2, 0, 0, 0, 0, 0, 0, 0, 2, 2, 2, 2, 0, 0],
    [0, 0, 0, 0, 2, 2, 2, 0, 0, 2, 2, 2, 0, 2, 2, 2, 2, 2, 0, 2, 2, 2, 2, 0, 0],
    [1, 0, 0, 0, 2, 2, 2, 0, 0, 0, 0, 0, 0, 2, 2, 2, 2, 2, 0, 2, 2, 2, 2, 0, 1],
    [0, 0, 0, 0, 2, 2, 2, 0, 0, 0, 0, 0, 0, 2, 2, 2, 2, 2, 0, 0, 0, 0, 0, 0, 0],
    [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 2, 2, 2, 2, 2, 0, 0, 0, 0, 2, 2, 0],
    [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 2, 2, 2, 2, 2, 0, 0, 0, 0, 2, 2, 0],
    [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 2, 2, 0],
    [0, 0, 0, 0, 0, 0, 0, 0, 0, 2, 2, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
    [0, 2, 2, 2, 2, 2, 0, 0, 0, 2, 2, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
    [1, 2, 2, 2, 2, 2, 0, 0, 0, 2, 2, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1],
    [0, 2, 2, 2, 2, 2, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
    [0, 2, 2, 2, 2, 2, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
    [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
    [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
    [0, 0, 0, 0, 0, 2, 2, 2, 2, 2, 2, 2, 2, 2, 0, 0, 0, 0, 0, 0, 0, 2, 2, 2, 0],
    [0, 0, 0, 0, 0, 2, 2, 2, 2, 2, 2, 2, 2, 2, 0, 0, 0, 0, 0, 0, 0, 2, 2, 2, 0],
    [0, 0, 0, 0, 0, 2, 2, 2, 2, 2, 2, 2, 2, 2, 0, 0, 0, 2, 2, 0, 0, 2, 2, 2, 0],
    [0, 0, 0, 0, 0, 2, 2, 2, 2, 2, 2, 2, 2, 2, 0, 0, 0, 2, 2, 0, 0, 0, 0, 0, 0],
    [0, 0, 0, 0, 0, 2, 2, 2, 2, 2, 2, 2, 2, 2, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
    [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
    [0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
]
ARC_TEST_REF_TEXT = """0 0 0 0 0 1 0 0 0 1 1 1 0 0 0 0 0 0 0 0 0 0 0 0 0
0 0 0 0 0 1 0 0 0 1 1 1 0 0 0 0 0 0 0 1 1 1 1 0 0
0 0 0 0 0 1 0 0 0 1 1 1 0 0 0 0 0 0 0 1 1 1 1 0 0
0 0 0 0 1 1 1 0 0 1 1 1 0 1 1 1 1 1 0 1 1 1 1 0 0
1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1
0 0 0 0 1 1 1 0 0 0 0 0 0 1 1 1 1 1 0 0 0 0 0 0 0
0 0 0 0 0 1 0 0 0 0 0 0 0 1 1 1 1 1 0 0 0 0 2 2 0
0 0 0 0 0 1 0 0 0 0 0 0 0 1 1 1 1 1 0 0 0 0 2 2 0
0 0 0 0 0 1 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 2 2 0
0 0 0 0 0 1 0 0 0 1 1 0 0 0 0 0 0 0 0 0 0 0 0 0 0
0 1 1 1 1 1 0 0 0 1 1 0 0 0 0 0 0 0 0 0 0 0 0 0 0
1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1
0 1 1 1 1 1 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0
0 1 1 1 1 1 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0
0 0 0 0 0 1 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0
0 0 0 0 0 1 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0
0 0 0 0 0 1 1 1 1 1 1 1 1 1 0 0 0 0 0 0 0 2 2 2 0
0 0 0 0 0 1 1 1 1 1 1 1 1 1 0 0 0 0 0 0 0 2 2 2 0
0 0 0 0 0 1 1 1 1 1 1 1 1 1 0 0 0 2 2 0 0 2 2 2 0
0 0 0 0 0 1 1 1 1 1 1 1 1 1 0 0 0 2 2 0 0 0 0 0 0
0 0 0 0 0 1 1 1 1 1 1 1 1 1 0 0 0 0 0 0 0 0 0 0 0
0 0 0 0 0 1 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0
0 0 0 0 0 1 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0"""
ARC_TEST_WRONG_TEXT = """0 0 0 0 0 1 0 0 0 2 2 2 0 0 0 0 0 0 0 0 0 0 0 0 0
0 0 0 0 0 1 0 0 0 2 2 2 0 0 0 0 0 0 0 1 1 1 1 0 0
0 0 0 0 0 1 0 0 0 2 2 2 0 0 0 0 0 0 0 1 1 1 1 0 0
0 0 0 0 1 1 1 0 0 2 2 2 0 1 1 1 1 1 0 1 1 1 1 0 0
1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1
0 0 0 0 1 1 1 0 0 0 0 0 0 1 1 1 1 1 0 0 0 0 0 0 0
0 0 0 0 0 1 0 0 0 0 0 0 0 1 1 1 1 1 0 0 0 0 2 2 0
0 0 0 0 0 1 0 0 0 0 0 0 0 1 1 1 1 1 0 0 0 0 2 2 0
0 0 0 0 0 1 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 2 2 0
0 0 0 0 0 1 0 0 0 1 1 0 0 0 0 0 0 0 0 0 0 0 0 0 0
0 1 1 1 1 1 0 0 0 1 1 0 0 0 0 0 0 0 0 0 0 0 0 0 0
1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1
0 1 1 1 1 1 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0
0 1 1 1 1 1 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0
0 0 0 0 0 1 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0
0 0 0 0 0 1 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0
0 0 0 0 0 1 1 1 1 1 1 1 1 1 0 0 0 0 0 0 0 2 2 2 0
0 0 0 0 0 1 1 1 1 1 1 1 1 1 0 0 0 0 0 0 0 2 2 2 0
0 0 0 0 0 1 1 1 1 1 1 1 1 1 0 0 0 2 2 0 0 2 2 2 0
0 0 0 0 0 1 1 1 1 1 1 1 1 1 0 0 0 2 2 0 0 0 0 0 0
0 0 0 0 0 1 1 1 1 1 1 1 1 1 0 0 0 0 0 0 0 0 0 0 0
0 0 0 0 0 1 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0
0 0 0 0 0 1 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0"""


def _parse_grid(text: str) -> list[list[int]]:
    return [[int(x) for x in row.split()] for row in text.strip().split("\n")]


# ARC-AGI's own palette uses color index 0-9; only 0/1/2 appear in this item.
# 0 = background (near-white here so it reads on a light article page),
# 1 = dataviz blue, 2 = dataviz orange.
ARC_CMAP = ListedColormap(["#f4f5f7", "#2a78d6", "#eb6834"])


def draw_grid(
    ax,
    grid: list[list[int]],
    title: str,
    highlight: set[tuple[int, int]] | None = None,
) -> None:
    ax.imshow(grid, cmap=ARC_CMAP, vmin=0, vmax=2, interpolation="nearest")
    rows, cols = len(grid), len(grid[0])
    ax.set_xticks([])
    ax.set_yticks([])
    for spine in ax.spines.values():
        spine.set_color(GRID_COLOR)
        spine.set_linewidth(0.8)
    ax.set_title(title, fontsize=10, color=TEXT_COLOR)
    if highlight:
        for r, c in highlight:
            ax.add_patch(
                plt.Rectangle(
                    (c - 0.5, r - 0.5), 1, 1, fill=False, edgecolor="#e34948", linewidth=2.2
                )
            )
    ax.set_xlim(-0.5, cols - 0.5)
    ax.set_ylim(rows - 0.5, -0.5)


def make_arc_agi_example_figure() -> None:
    ref = _parse_grid(ARC_TEST_REF_TEXT)
    wrong = _parse_grid(ARC_TEST_WRONG_TEXT)
    diff_cells = {
        (r, c)
        for r in range(len(ref))
        for c in range(len(ref[0]))
        if ref[r][c] != wrong[r][c]
    }

    fig = plt.figure(figsize=(13, 6.5), dpi=200)
    gs = fig.add_gridspec(2, 3, height_ratios=[1, 1.15], hspace=0.35, wspace=0.15)

    ax_train_in = fig.add_subplot(gs[0, 0])
    draw_grid(ax_train_in, ARC_TRAIN_IN, "訓練例：入力")
    ax_train_out = fig.add_subplot(gs[0, 1])
    draw_grid(ax_train_out, ARC_TRAIN_OUT, "訓練例：出力（お手本）")
    ax_note = fig.add_subplot(gs[0, 2])
    ax_note.axis("off")
    ax_note.text(
        0,
        0.5,
        "対になった色1のマス(端に離れて配置)を\n結ぶように水平・垂直の線を引き、\n線が触れた色2のブロックを\n色1へ塗り替える、という規則。",
        fontsize=10.5,
        color=TEXT_COLOR,
        va="center",
        ha="left",
        wrap=True,
    )

    ax_test_in = fig.add_subplot(gs[1, 0])
    draw_grid(ax_test_in, ARC_TEST_IN, "テスト入力")
    ax_test_ref = fig.add_subplot(gs[1, 1])
    draw_grid(ax_test_ref, ref, "正解")
    ax_test_wrong = fig.add_subplot(gs[1, 2])
    wrong_title = "20モデル中14モデルの誤答\n(赤枠が正解と異なる12マス)"
    draw_grid(ax_test_wrong, wrong, wrong_title, highlight=diff_cells)

    fig.suptitle(
        "ARC-AGI 具体例（item: 0d87d2a6|0）", fontsize=13, color=TEXT_COLOR, x=0.02, ha="left"
    )
    fig.savefig(FIGURES_DIR / "arc_agi_example.png", facecolor="white", bbox_inches="tight")
    plt.close(fig)


def wrap_label(text: str, width: int = 14) -> str:
    """Wrap a long category label onto two lines so it doesn't overflow a
    narrow bar-chart panel and bleed into a neighboring subplot."""
    return "\n".join(textwrap.wrap(text, width=width, break_long_words=False)) or text


def style_axes(ax) -> None:
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_visible(False)
    ax.spines["bottom"].set_color(GRID_COLOR)
    ax.tick_params(axis="both", colors=TEXT_COLOR, labelsize=10)
    ax.xaxis.grid(True, color=GRID_COLOR, linewidth=0.8)
    ax.set_axisbelow(True)


def horizontal_bar_with_labels(
    ax, labels: list[str], values: list[float], value_labels: list[str] | None = None
) -> None:
    y_pos = range(len(labels))
    bars = ax.barh(y_pos, values, color=BAR_COLOR, height=0.62)
    ax.set_yticks(list(y_pos))
    ax.set_yticklabels(labels, color=TEXT_COLOR)
    ax.invert_yaxis()
    max_value = max(values)
    texts = value_labels if value_labels is not None else [f"{v:,}" for v in values]
    for bar, text in zip(bars, texts, strict=True):
        ax.text(
            bar.get_width() + max_value * 0.015,
            bar.get_y() + bar.get_height() / 2,
            text,
            va="center",
            ha="left",
            color=TEXT_COLOR,
            fontsize=10,
        )
    ax.set_xlim(0, max_value * 1.14)
    style_axes(ax)


def make_cause_axis_figure() -> None:
    counts: dict[str, int] = {}
    for path in (PROJECT_ROOT / "outputs" / "llm" / "by_benchmark").glob("*.json"):
        payload = read_json(path)
        for assignment in payload.get("assignments", []):
            cause = assignment.get("cause_axis", assignment.get("cause", "uncertain"))
            category_id = assignment.get("category_id", assignment.get("category"))
            if cause == "reference_or_evaluator":
                cause = (
                    "reference_defect_axis"
                    if category_id in REFERENCE_DEFECT_CATEGORY_IDS
                    else "format_or_protocol"
                )
            elif cause == "data_or_version":
                cause = DATA_OR_VERSION_MERGES_INTO
            elif cause == "mixed":
                cause = MIXED_REASSIGNMENT.get(category_id, "uncertain")
            counts[cause] = counts.get(cause, 0) + 1
    ordered = sorted(counts.items(), key=lambda item: item[1], reverse=True)
    labels = [CAUSE_AXIS_LABELS.get(key, key) for key, _ in ordered]
    values = [value for _, value in ordered]
    total = sum(values)
    value_labels = [f"{value:,}件（{value / total * 100:.1f}%）" for value in values]

    fig, ax = plt.subplots(figsize=(9, 4.2), dpi=200)
    horizontal_bar_with_labels(ax, labels, values, value_labels=value_labels)
    title = f"誤答の原因軸（{total:,}件、cause axis）"
    ax.set_title(title, fontsize=12, color=TEXT_COLOR, loc="left")
    fig.tight_layout()
    fig.savefig(FIGURES_DIR / "cause_axis.png", facecolor="white")
    plt.close(fig)


def make_benchmark_failure_rate_figure() -> None:
    with (PROJECT_ROOT / "outputs" / "tables" / "benchmark_counts.csv").open(
        encoding="utf-8", newline=""
    ) as f:
        rows = list(csv.DictReader(f))

    records = []
    for row in rows:
        evaluable = int(row["fully_evaluable_items"])
        failures = int(row["common_failures"])
        rate = failures / evaluable * 100 if evaluable else 0.0
        records.append((row["benchmark"], evaluable, failures, rate))
    records.sort(key=lambda r: r[3], reverse=True)

    labels = [BENCHMARK_DISPLAY_NAMES[bm] for bm, *_ in records]
    value_labels = [
        f"{failures}/{evaluable}件（{rate:.2f}%）" for _, evaluable, failures, rate in records
    ]
    values = [rate for *_, rate in records]

    fig, ax = plt.subplots(figsize=(8, 5.5), dpi=200)
    horizontal_bar_with_labels(ax, labels, values, value_labels=value_labels)
    ax.set_xlabel(
        "誤答率（16/20以上が誤答した問題数 ÷ 判定可能な問題数、%）", fontsize=9, color=TEXT_COLOR
    )
    ax.set_title(
        "ベンチマーク別の80%以上共通誤答", fontsize=12, color=TEXT_COLOR, loc="left"
    )
    fig.tight_layout()
    fig.savefig(FIGURES_DIR / "benchmark_failure_rate.png", facecolor="white")
    plt.close(fig)


def _load_benchmark_categories() -> dict[str, dict[str, int]]:
    by_benchmark: dict[str, dict[str, int]] = {}
    for benchmark in BENCHMARK_DISPLAY_NAMES:
        path = PROJECT_ROOT / "outputs" / "llm" / "by_benchmark" / f"{benchmark}.json"
        if not path.exists():
            continue
        payload = read_json(path)
        counts: dict[str, int] = {}
        name_by_id = {
            t["category_id"]: CATEGORY_LABEL_OVERRIDES.get(t["category_id"], t["name"])
            for t in payload["taxonomy"]
        }
        for assignment in payload["assignments"]:
            category_id = assignment.get("category_id", assignment.get("category"))
            counts[category_id] = counts.get(category_id, 0) + 1
        labelled = {name_by_id.get(k, k): v for k, v in counts.items()}
        by_benchmark[benchmark] = dict(sorted(labelled.items(), key=lambda kv: kv[1], reverse=True))
    return by_benchmark


def _draw_category_bar_panel(ax, title: str, data: dict[str, int]) -> None:
    labels = [wrap_label(label, width=9) for label in data]
    values = list(data.values())
    y_pos = range(len(labels))
    bars = ax.barh(y_pos, values, color=BAR_COLOR, height=0.55)
    ax.set_yticks(list(y_pos))
    ax.set_yticklabels(labels, color=TEXT_COLOR, fontsize=8.5)
    ax.invert_yaxis()
    max_value = max(values)
    for bar, value in zip(bars, values, strict=True):
        ax.text(
            bar.get_width() + max_value * 0.02,
            bar.get_y() + bar.get_height() / 2,
            f"{value}",
            va="center",
            ha="left",
            color=TEXT_COLOR,
            fontsize=8.5,
        )
    ax.set_xlim(0, max_value * 1.22)
    ax.set_title(title, fontsize=11, color=TEXT_COLOR, loc="left")
    style_axes(ax)


def make_category_breakdown_figure() -> None:
    by_benchmark = _load_benchmark_categories()
    # "Big" benchmarks (>=10 items) get their own bar-chart panel; "small"
    # ones are listed compactly as bullet text so tiny bars don't waste space.
    big = [bm for bm, cats in by_benchmark.items() if sum(cats.values()) >= 10]
    small = [bm for bm, cats in by_benchmark.items() if sum(cats.values()) < 10]
    big.sort(key=lambda bm: sum(by_benchmark[bm].values()), reverse=True)
    small.sort(key=lambda bm: sum(by_benchmark[bm].values()), reverse=True)

    # Fixed, hand-placed layout (figure-fraction coordinates) rather than
    # GridSpec + automatic layout: with long wrapped Japanese tick labels,
    # both tight_layout and constrained_layout either overlapped neighboring
    # panels or collapsed axes to zero size. Explicit positions are more
    # verbose but fully deterministic. Each column reserves its own left
    # margin for tick labels, so panels never bleed into their neighbor.
    n_cols = 3
    col_w = 0.30
    col_gap = 0.02
    col_left_margin = 0.155  # blank space at the left of each panel for labels
    lefts = [0.015 + i * (col_w + col_gap) + col_left_margin for i in range(n_cols)]
    panel_w = col_w - col_left_margin

    fig = plt.figure(figsize=(16, 12.5), dpi=200)

    # Row height is unchanged from the version already verified to have
    # comfortable internal label spacing; the taller figure means that same
    # fraction now maps to more absolute points, and the reclaimed fraction
    # (from not needing to shrink anything) goes entirely into the gaps
    # between rows so a row's x-axis tick numbers never crowd the next row's
    # title.
    row_tops = [0.91, 0.56]
    row_h = 0.24
    for i, benchmark in enumerate(big[: 2 * n_cols]):
        row, col = divmod(i, n_cols)
        ax = fig.add_axes((lefts[col], row_tops[row] - row_h, panel_w, row_h))
        data = by_benchmark[benchmark]
        total = sum(data.values())
        _draw_category_bar_panel(ax, f"{BENCHMARK_DISPLAY_NAMES[benchmark]}（{total}件）", data)

    # One wide bullet-list panel spanning the full width for small benchmarks.
    ax_small = fig.add_axes((0.015, 0.02, 0.97, 0.20))
    ax_small.axis("off")
    ax_small.set_title(
        "件数の少ないベンチマーク（内訳）", fontsize=11, color=TEXT_COLOR, loc="left"
    )
    # Lay the small benchmarks out in 3 side-by-side text columns so the
    # panel doesn't grow arbitrarily tall as more benchmarks are added.
    n_text_cols = 3
    per_col = -(-len(small) // n_text_cols)  # ceil division
    for col_idx in range(n_text_cols):
        chunk = small[col_idx * per_col : (col_idx + 1) * per_col]
        if not chunk:
            continue
        lines: list[str] = []
        for benchmark in chunk:
            data = by_benchmark[benchmark]
            total = sum(data.values())
            lines.append(f"● {BENCHMARK_DISPLAY_NAMES[benchmark]}（計{total}件）")
            for category, count in data.items():
                lines.append(f"    ・{category}：{count}件")
        ax_small.text(
            col_idx / n_text_cols,
            0.88,
            "\n".join(lines),
            fontsize=9,
            color=TEXT_COLOR,
            va="top",
            ha="left",
            linespacing=1.7,
            transform=ax_small.transAxes,
        )

    fig.suptitle(
        "ベンチマーク別の誤答パターン分類（全11ベンチマーク）",
        fontsize=13,
        color=TEXT_COLOR,
        x=0.015,
        ha="left",
    )
    fig.savefig(FIGURES_DIR / "category_breakdown.png", facecolor="white")
    plt.close(fig)


def main() -> None:
    FIGURES_DIR.mkdir(parents=True, exist_ok=True)
    make_benchmark_failure_rate_figure()
    make_cause_axis_figure()
    make_category_breakdown_figure()
    make_arc_agi_example_figure()
    print(f"Wrote figures to {FIGURES_DIR}")


if __name__ == "__main__":
    main()
