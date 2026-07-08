from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load():
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "scripts"))
    path = root / "scripts/build_stage9242_multilang_source_backed_bounded_decoder_execution_review.py"
    spec = importlib.util.spec_from_file_location("stage9242", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_ticket_points_to_balanced_manifest_and_stays_inactive():
    mod = _load()
    ticket = mod.build_ticket({"metrics": {"manifest_sha256": "abc"}})
    assert ticket["source_manifest_path"].endswith("stage9240_source_backed_multilang_bounded_decoder_tiny_package/source_backed_multilang_bounded_decoder_tiny_manifest.jsonl")
    assert ticket["requested_stage"] == 9243
    assert "stage9243_multilang_source_backed_target_100m_bounded_tiny_probe" in ticket["future_output_dir"]
    assert ticket["execution_authorized_now"] is False
    assert ticket["command_executable_now"] is False
    assert ticket["requires_explicit_user_authorization"] is True
    assert "run_trainer" in ticket["denied_operations_now"]


def test_audit_rejects_runtime_opening():
    mod = _load()
    ticket = mod.build_ticket({"metrics": {"manifest_sha256": "abc"}})
    ticket["required_limits"]["runtime"] = True
    audit = mod.audit_ticket(ticket, {"passed": True}, {"passed": True, "metrics": {"model_execution_attempted": False}})
    assert audit["passed"] is False
    assert "limit_mismatch:runtime" in audit["failures"]
