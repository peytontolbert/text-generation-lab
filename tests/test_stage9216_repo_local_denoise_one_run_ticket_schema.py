from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load():
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "scripts"))
    path = root / "scripts/build_stage9216_repo_local_denoise_one_run_ticket_schema.py"
    spec = importlib.util.spec_from_file_location("stage9216_ticket", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_denoise_review_selects_denoise_family():
    mod = _load()
    matrix = {
        "family_reviews": [
            {"mode": "bounded_decoder_ce_probe", "manifest_path": "bounded"},
            {"mode": "denoise_repair_probe", "manifest_path": "denoise"},
        ]
    }
    assert mod.denoise_review(matrix)["manifest_path"] == "denoise"


def test_denoise_ticket_is_inactive_and_denoise_only():
    mod = _load()
    review = {
        "manifest_path": "runs/local/artifacts/stage9211_repo_local_tiny_cap_adapters/denoise_tiny_cap_manifest.jsonl"
    }
    ticket = mod.build_ticket(review)
    assert ticket["ticket_status"] == "DESIGN_ONLY_INACTIVE"
    assert ticket["command_materialized"] is False
    assert ticket["execution_authorized_now"] is False
    assert ticket["allowed_operations_now"] == []
    assert ticket["required_limits"]["mode"] == "denoise_repair_probe"
    assert ticket["required_limits"]["decoder_ce_weight"] == 0.0
    assert ticket["required_limits"]["structured_aux_weight"] == 0.0
    assert ticket["required_limits"]["denoise_weight"] == 1.0
    assert ticket["required_limits"]["runtime_verifier_execution"] is False
    assert ticket["required_limits"]["target_store_resolver_mode"] == "readonly"
    assert "run_runtime_verifier" in ticket["denied_operations_now"]
    assert "walk_arxiv" in ticket["denied_operations_now"]


def test_audit_rejects_runtime_verifier_opening():
    mod = _load()
    review = {
        "mode": "denoise_repair_probe",
        "status": "requires_dedicated_one_run_ticket_schema",
        "manifest_path": "runs/local/artifacts/stage9211_repo_local_tiny_cap_adapters/denoise_tiny_cap_manifest.jsonl",
        "review_failures": ["dedicated_one_run_ticket_schema_missing"],
    }
    ticket = mod.build_ticket(review)
    ticket["required_limits"]["runtime_verifier_execution"] = True
    audit = mod.audit_ticket(ticket, {"passed": True}, {"passed": True}, {"passed": True}, review)
    assert "limit_mismatch:runtime_verifier_execution" in audit["failures"]
