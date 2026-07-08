from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load():
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "scripts"))
    path = root / "scripts/build_stage9263_stabilized_bounded_decoder_contract_preflight_summary.py"
    spec = importlib.util.spec_from_file_location("stage9263", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_stage9263_preflight_records_stabilized_non_execution_contract():
    mod = _load()
    audit = mod.audit_preflight()
    assert audit["passed"] is True
    assert audit["metrics"]["rows"] == 64
    assert audit["metrics"]["decoder_ce_rows"] == 64
    assert audit["metrics"]["eos_loss_weight"] == 4.0
    assert audit["metrics"]["model_execution_attempted"] is False
    assert audit["metrics"]["second_execution_authorized_now"] is False
    assert audit["metrics"]["unsafe_loss_rows"] == 0
