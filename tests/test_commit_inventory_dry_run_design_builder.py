import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.commit_inventory_dry_run_design_builder import (
    COMMIT_METADATA_FIELDS,
    INVENTORY_FIELDS,
    build_card,
    build_inventory_design_rows,
)


def test_commit_inventory_dry_run_design_is_closed_and_complete():
    rows = build_inventory_design_rows()
    card = build_card(rows)
    assert card["passed"] is True
    assert card["dry_run_design_ready_rows"] == len(rows)
    assert card["arxiv_repository_walk_authorized"] is False
    assert card["commit_reads_authorized"] is False
    assert card["commit_mining_authorized"] is False
    assert card["training_authorized"] is False
    assert card["decoder_ce_authorized"] is False
    for row in rows:
        assert row["route"] == "DRY_RUN_DESIGN_ONLY_NO_REPO_WALK"
        assert set(INVENTORY_FIELDS).issubset(row["inventory_fields"])
        assert set(COMMIT_METADATA_FIELDS).issubset(row["commit_metadata_fields"])
        assert not any(row["authority"].values())
        assert not any(row["loss_mask"].values())
        assert not any(row["anti_cheat"].values())


def test_commit_inventory_dry_run_caps_are_zero_for_current_stage():
    rows = build_inventory_design_rows()
    for row in rows:
        caps = row["caps_and_bounds"]
        assert caps["repositories_per_dry_run"] == 0
        assert caps["commits_read_per_repo"] == 0
        assert caps["diff_bodies_read"] == 0
        assert caps["patch_bodies_emitted"] == 0
        assert caps["training_rows_emitted"] == 0
