import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.commit_inventory_dry_run_design_builder import build_inventory_design_rows
from scripts.commit_inventory_dry_run_gate_audit import audit_inventory_design_rows


def test_commit_inventory_dry_run_gate_passes_closed_design():
    rows = build_inventory_design_rows()
    audit = audit_inventory_design_rows(rows)
    assert audit["passed"] is True
    assert audit["gate_pass_rows"] == len(rows)
    assert audit["missing_design_id_count"] == 0
    assert audit["authority_open_rows"] == []
    assert audit["loss_open_rows"] == []
    assert audit["opening_rows"] == []
    assert audit["bad_route_rows"] == []
    assert audit["patch_body_field_rows"] == []
    assert audit["train_field_rows"] == []
    assert audit["arxiv_repository_walk_authorized"] is False
    assert audit["commit_reads_authorized"] is False
    assert audit["training_authorized"] is False
    assert audit["decoder_ce_authorized"] is False


def test_commit_inventory_dry_run_gate_catches_opening_and_patch_body():
    rows = build_inventory_design_rows()
    rows[0]["anti_cheat"]["walks_arxiv_repositories"] = True
    rows[0]["caps_and_bounds"]["repositories_per_dry_run"] = 1
    rows[0]["required_fields"].append("patch_body")
    audit = audit_inventory_design_rows(rows)
    assert audit["passed"] is False
    assert rows[0]["row_id"] in audit["opening_rows"]
    assert rows[0]["row_id"] in audit["missing_zero_caps"]
    assert rows[0]["row_id"] in audit["patch_body_field_rows"]
