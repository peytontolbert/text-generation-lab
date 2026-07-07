from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load():
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "scripts"))
    path = root / "scripts/build_stage9214_repo_local_bounded_decoder_one_run_ticket_design.py"
    spec = importlib.util.spec_from_file_location("stage9214_ticket", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_bounded_review_selects_bounded_family():
    mod = _load()
    matrix = {
        "family_reviews": [
            {"mode": "structured_policy_probe", "manifest_path": "structured"},
            {"mode": "bounded_decoder_ce_probe", "manifest_path": "bounded"},
        ]
    }
    assert mod.bounded_review(matrix)["manifest_path"] == "bounded"


def test_bounded_ticket_is_inactive_and_decoder_only():
    mod = _load()
    review = {
        "manifest_path": "runs/local/artifacts/stage9211_repo_local_tiny_cap_adapters/bounded_decoder_tiny_cap_manifest.jsonl"
    }
    ticket = mod.build_ticket(review)
    assert ticket["ticket_status"] == "DESIGN_ONLY_INACTIVE"
    assert ticket["command_materialized"] is False
    assert ticket["execution_authorized_now"] is False
    assert ticket["allowed_operations_now"] == []
    assert ticket["required_limits"]["mode"] == "bounded_decoder_ce_probe"
    assert ticket["required_limits"]["decoder_ce_weight"] == 1.0
    assert ticket["required_limits"]["structured_aux_weight"] == 0.0
    assert ticket["required_limits"]["denoise_weight"] == 0.0
    assert ticket["authority"] == mod.AUTHORITY_CLOSED
    assert "run_trainer" in ticket["denied_operations_now"]
    assert "walk_arxiv" in ticket["denied_operations_now"]


def test_audit_rejects_arxiv_output_dir():
    mod = _load()
    review = {
        "mode": "bounded_decoder_ce_probe",
        "status": "future_review_candidate",
        "manifest_path": "runs/local/artifacts/stage9211_repo_local_tiny_cap_adapters/bounded_decoder_tiny_cap_manifest.jsonl",
        "review_failures": [],
    }
    ticket = mod.build_ticket(review)
    ticket["future_output_dir"] = "/arxiv/blocked"
    audit = mod.audit_ticket(ticket, {"passed": True}, {"passed": True}, {"passed": True}, review)
    assert "future_output_dir_outside_repo" in audit["failures"]
    assert "future_output_dir_mentions_arxiv" in audit["failures"]
