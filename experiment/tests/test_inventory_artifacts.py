from leaderboard_analysis.inventory_artifacts import table_identity, table_pointers


def test_table_pointers_selects_only_output_tables() -> None:
    summary = {
        "foo_output_table": {
            "_type": "table-file",
            "artifact_path": "wandb-client-artifact://id/foo.table.json",
            "path": "media/table/foo.table.json",
            "sha256": "abc",
            "nrows": 1,
            "ncols": 2,
        },
        "leaderboard_table": {"_type": "table-file"},
        "scalar": 1,
    }
    assert list(table_pointers(summary)) == ["foo_output_table"]


def test_table_identity_tracks_condition_and_exclusions() -> None:
    assert table_identity("jaster_2shot_output_table") == (
        "jaster",
        "2shot",
        "official",
        "official_candidate",
    )
    assert table_identity("hle_dev_output_table") == (
        "hle",
        "default",
        "dev",
        "dev_excluded",
    )
    assert table_identity("toxicity_output_table")[-1] == "official_candidate_partial_12item"
