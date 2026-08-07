import pandas as pd

from leaderboard_analysis.extract_common_failures import item_statistics


def test_common_failure_boundary_is_16_of_20() -> None:
    rows = []
    for index in range(20):
        rows.append(
            {
                "item_key": "included",
                "run_id": str(index),
                "is_correct": index >= 16,
                "evaluation_status": "evaluated",
            }
        )
        rows.append(
            {
                "item_key": "excluded",
                "run_id": str(index),
                "is_correct": index >= 15,
                "evaluation_status": "evaluated",
            }
        )
    stats = item_statistics(pd.DataFrame(rows)).set_index("item_key")
    assert bool(stats.loc["included", "common_failure_80"])
    assert not bool(stats.loc["excluded", "common_failure_80"])
