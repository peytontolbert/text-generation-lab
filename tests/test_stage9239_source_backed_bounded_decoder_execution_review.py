from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load():
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "scripts"))
    path = root / "scripts/build_stage9239_source_backed_bounded_decoder_execution_review.py"
    spec = importlib.util.spec_from_file_location("stage9239", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def _sources():
    return {"passed": True}, {"passed": True, "metrics": {"manifest_sha256": "abc", "model_execution_attempted": False}}


def test_ticket_is_inactive_and_requires_explicit_authorization():
    mod = _load()
    _source9237, source9238 = _sources()
    ticket = mod.build_ticket(source9238)
    assert ticket["ticket_status"] == "DESIGN_ONLY_INACTIVE"
    assert ticket["execution_authorized_now"] is False
    assert ticket["model_execution_authorized_now"] is False
    assert ticket["decoder_ce_training_authorized_now"] is False
    assert ticket["requires_explicit_user_authorization"] is True
    assert "run_trainer" in ticket["denied_operations_now"]
    assert ticket["required_limits"]["max_train_rows"] == 32
    assert ticket["required_limits"]["runtime"] is False


def test_audit_rejects_open_execution_and_widened_caps():
    mod = _load()
    source9237, source9238 = _sources()
    ticket = mod.build_ticket(source9238)
    ticket["execution_authorized_now"] = True
    ticket["required_limits"]["max_train_rows"] = 128
    audit = mod.audit_ticket(ticket, source9237, source9238)
    assert audit["passed"] is False
    assert "execution_authorized_now_not_false" in audit["failures"]
    assert "limit_mismatch:max_train_rows" in audit["failures"]


def test_audit_rejects_arxiv_output_and_missing_denial():
    mod = _load()
    source9237, source9238 = _sources()
    ticket = mod.build_ticket(source9238)
    ticket["future_output_dir"] = "/arxiv/not_allowed"
    ticket["denied_operations_now"] = [item for item in ticket["denied_operations_now"] if item != "run_trainer"]
    audit = mod.audit_ticket(ticket, source9237, source9238)
    assert audit["passed"] is False
    assert "future_output_dir_not_under_repo" in audit["failures"]
    assert "future_output_dir_mentions_arxiv" in audit["failures"]
    assert "missing_denied_operation:run_trainer" in audit["failures"]
