from leaderboard_analysis.freeze_ranking import public_filter_from_report


def test_public_filter_from_report() -> None:
    runset = {
        "filters": {
            "filterFormat": "filterV2",
            "filters": [
                {
                    "filters": [
                        {
                            "key": {"section": "tags", "name": "*"},
                            "op": "IN",
                            "value": ["leaderboard", "archived"],
                        },
                        {
                            "key": {"section": "tags", "name": "merged"},
                            "op": "!=",
                            "value": False,
                        },
                    ]
                },
                {
                    "key": {"section": "run", "name": "name"},
                    "op": "IN",
                    "value": ["run-a", "run-b"],
                    "connector": "OR",
                },
            ],
        }
    }

    public_filter, semantics = public_filter_from_report(runset)

    assert public_filter == {
        "$or": [
            {
                "$and": [
                    {"tags": {"$in": ["leaderboard", "archived"]}},
                    {"tags": "merged"},
                ]
            },
            {"name": {"$in": ["run-a", "run-b"]}},
        ]
    }
    assert semantics["required_tag"] == "merged"
