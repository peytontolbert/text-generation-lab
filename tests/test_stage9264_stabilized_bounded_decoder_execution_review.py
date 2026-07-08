from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load():
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "scripts"))
    path = root / "scripts/build_stage9264_stabilized_bounded_decoder_execution_review.py"
    spec = importlib.util.spec_from_file_location("stage9264", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_stage9264_review_records_stabilized_future_command_without_current_authority():
    mod = _load()
    source = {"passed": True, "metrics": {"manifest_sha256": mod.MANIFEST_SHA, "eos_loss_weight": 4.0, "model_execution_attempted": False}}
    ticket = mod.build_ticket(source)
    audit = mod.audit_ticket(ticket, source)
    assert audit["passed"] is True
    assert ticket["execution_authorized_now"] is False
    assert ticket["required_limits"]["eos_loss_weight"] == 4.0
    assert ticket["required_limits"]["learning_rate"] == 1e-5
    assert "--eos-loss-weight" in ticket["future_argv"]
    assert all(value is False for value in ticket["authority"].values())


def test_stage9264_negative_cases_are_rejected():
    mod = _load()
    source = {"passed": True, "metrics": {"manifest_sha256": mod.MANIFEST_SHA, "eos_loss_weight": 4.0, "model_execution_attempted": False}}
    ticket = mod.build_ticket(source)
    negatives = mod.negative_cases(ticket, source)
    assert negatives
    assert all(case["rejected"] for case in negatives)
