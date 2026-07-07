from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load():
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "scripts"))
    path = root / "scripts/build_stage9209_repo_local_structured_one_run_ticket_design.py"
    spec = importlib.util.spec_from_file_location("stage9209_ticket", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_structured_review_selects_only_structured_family():
    mod = _load()
    matrix = {
        "family_reviews": [
            {"mode": "bounded_decoder_ce_probe", "bundle_id": "bounded"},
            {"mode": "structured_policy_probe", "bundle_id": "structured"},
        ]
    }
    assert mod.structured_review(matrix)["bundle_id"] == "structured"


def test_inactive_ticket_has_no_execution_authority():
    mod = _load()
    review = {
        "bundle_id": "stage8937_structured_policy_bundle",
        "manifest_path": str(
            mod.ROOT
            / "runs/local/artifacts/stage9206_repo_local_three_family_selector/stage8937_structured_policy_bundle/materialization_preview/trainer_rows.jsonl"
        ),
    }
    ticket = mod.build_ticket(review)
    assert ticket["ticket_status"] == "DESIGN_ONLY_INACTIVE"
    assert ticket["command_materialized"] is False
    assert ticket["execution_authorized_now"] is False
    assert ticket["allowed_operations_now"] == []
    assert ticket["authority"] == mod.AUTHORITY_CLOSED
    assert "run_trainer" in ticket["denied_operations_now"]
    assert "walk_arxiv" in ticket["denied_operations_now"]


def test_audit_rejects_arxiv_output_dir():
    mod = _load()
    review = {
        "mode": "structured_policy_probe",
        "bundle_id": "stage8937_structured_policy_bundle",
        "manifest_path": str(
            mod.ROOT
            / "runs/local/artifacts/stage9206_repo_local_three_family_selector/stage8937_structured_policy_bundle/materialization_preview/trainer_rows.jsonl"
        ),
        "review_failures": [],
    }
    ticket = mod.build_ticket(review)
    ticket["future_output_dir"] = "/arxiv/blocked"
    audit = mod.audit_ticket(
        ticket,
        {"passed": True},
        {"passed": True},
        review,
    )
    assert "future_output_dir_outside_repo" in audit["failures"]
    assert "future_output_dir_mentions_arxiv" in audit["failures"]
