import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.commit_learning_signal_contract_builder import build_commit_learning_signal_rows
from scripts.commit_learning_signal_no_mining_gate_audit import audit_commit_contract_rows


def test_commit_learning_signal_no_mining_gate_passes_closed_contract():
    rows = build_commit_learning_signal_rows()
    audit = audit_commit_contract_rows(rows)
    assert audit["passed"] is True
    assert audit["gate_pass_rows"] == len(rows)
    assert audit["missing_contract_id_count"] == 0
    assert audit["authority_open_rows"] == []
    assert audit["loss_open_rows"] == []
    assert audit["opening_rows"] == []
    assert audit["bad_route_rows"] == []
    assert audit["decoder_target_policy_fail_rows"] == []
    assert audit["source_gate_fail_rows"] == []
    assert audit["commit_mining_authorized"] is False
    assert audit["arxiv_repository_walk_authorized"] is False
    assert audit["training_authorized"] is False
    assert audit["decoder_ce_authorized"] is False


def test_commit_learning_signal_no_mining_gate_catches_openings():
    rows = build_commit_learning_signal_rows()
    rows[0]["anti_cheat"]["walks_arxiv_repositories"] = True
    rows[0]["loss_mask"]["decoder_ce"] = True
    rows[0]["route"] = "MINE"
    audit = audit_commit_contract_rows(rows)
    assert audit["passed"] is False
    assert rows[0]["row_id"] in audit["opening_rows"]
    assert rows[0]["row_id"] in audit["loss_open_rows"]
    assert rows[0]["row_id"] in audit["bad_route_rows"]
