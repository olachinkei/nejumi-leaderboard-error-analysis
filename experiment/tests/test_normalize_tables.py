from leaderboard_analysis.normalize_tables import (
    correctness,
    normalized_text,
    set_bottom_quartile_thresholds,
)


def test_correctness_rules_apply_official_or_bottom_quartile_boundaries() -> None:
    # exact_match/exact_match_figure remain the official binary judgment.
    assert correctness("jaster", 1.0, "exact_match") == (True, "evaluated")
    # char_f1/comet_wmt22 have no official boundary; v3 applies the documented
    # bottom-quartile convention (score < Q1 of the pooled top-20 distribution
    # is "wrong") instead of leaving them unclassified.
    set_bottom_quartile_thresholds({("jaster", "char_f1"): 0.5})
    assert correctness("jaster", 0.8, "char_f1", "jaster") == (
        True,
        "evaluated_bottom_quartile_convention",
    )
    assert correctness("jaster", 0.4999, "char_f1", "jaster") == (
        False,
        "evaluated_bottom_quartile_convention",
    )
    assert correctness("jaster", 0.5, "char_f1", "jaster") == (
        True,
        "evaluated_bottom_quartile_convention",
    )
    assert correctness("non_binary", 3, "judge") == (None, "non_binary_score")


def test_bottom_quartile_rule_uses_the_precomputed_threshold() -> None:
    # mtbench: threshold computed from the pooled top-20 score distribution.
    set_bottom_quartile_thresholds({("mtbench", "judge_score_1_10"): 10.0})
    assert correctness("bottom_quartile", 9, "judge_score_1_10", "mtbench") == (
        False,
        "evaluated_bottom_quartile_convention",
    )
    assert correctness("bottom_quartile", 10, "judge_score_1_10", "mtbench") == (
        True,
        "evaluated_bottom_quartile_convention",
    )
    set_bottom_quartile_thresholds({("jmmlu_robust", "robustness"): 1.0})
    assert correctness("bottom_quartile", 0.5, "robustness", "jmmlu_robust") == (
        False,
        "evaluated_bottom_quartile_convention",
    )
    assert correctness("bottom_quartile", None, "robustness", "jmmlu_robust") == (
        None,
        "missing_score",
    )


def test_operational_swebench_status_is_not_wrong() -> None:
    assert correctness("swebench", "resolved", "resolution") == (True, "evaluated")
    assert correctness("swebench", "unresolved", "resolution") == (False, "evaluated")
    assert correctness("swebench", "error", "resolution") == (
        None,
        "operational_error",
    )


def test_normalized_text_is_stable() -> None:
    assert normalized_text("Ａ  \n B") == "A B"
