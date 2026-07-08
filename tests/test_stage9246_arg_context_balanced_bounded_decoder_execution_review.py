from __future__ import annotations

import copy
import importlib.util
import sys
from pathlib import Path


def _load():
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "scripts"))
    path = root / "scripts/build_stage9246_arg_context_balanced_bounded_decoder_execution_review.py"
    spec = importlib.util.spec_from_file_location("stage9246", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def _source_package():
    return {"passed": True}


def _source_preflight():
    return {
        "passed": True,
        "metrics": {
            "manifest_sha256": "abc",
            "model_execution_attempted": False,
        },
    }


def test_ticket_is_inactive_and_closed():
    mod = _load()
    ticket = mod.build_ticket(_source_preflight())
    audit = mod.audit_ticket(ticket, _source_package(), _source_preflight())
    assert audit["passed"] is True
    assert ticket["ticket_status"] == "DESIGN_ONLY_INACTIVE"
    assert ticket["execution_authorized_now"] is False
    assert ticket["model_execution_authorized_now"] is False
    assert ticket["decoder_ce_training_authorized_now"] is False
    assert ticket["allowed_operations_now"] == []
    assert ticket["command_executable_now"] is False
    assert all(value is False for value in ticket["authority"].values())


def test_negative_cases_are_rejected():
    mod = _load()
    ticket = mod.build_ticket(_source_preflight())
    negatives = mod.negative_cases(ticket, _source_package(), _source_preflight())
    assert len(negatives) == 9
    assert all(case["rejected"] for case in negatives)


def test_audit_rejects_arxiv_output_and_widened_caps():
    mod = _load()
    ticket = mod.build_ticket(_source_preflight())
    mutated = copy.deepcopy(ticket)
    mutated["future_output_dir"] = "/arxiv/blocked"
    mutated["required_limits"]["max_train_rows"] = 128
    audit = mod.audit_ticket(mutated, _source_package(), _source_preflight())
    assert audit["passed"] is False
    assert "future_output_dir_not_under_repo" in audit["failures"]
    assert "future_output_dir_mentions_arxiv" in audit["failures"]
    assert "limit_mismatch:max_train_rows" in audit["failures"]
