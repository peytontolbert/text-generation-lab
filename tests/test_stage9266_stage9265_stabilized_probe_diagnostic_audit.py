from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load():
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "scripts"))
    path = root / "scripts/build_stage9266_stage9265_stabilized_probe_diagnostic_audit.py"
    spec = importlib.util.spec_from_file_location("stage9266", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_stage9266_audit_records_safe_execution_but_failed_quality_gate():
    mod = _load()
    audit = mod.build_audit()
    assert audit["passed"] is True
    assert audit["quality_gate_passed"] is False
    assert audit["metrics"]["execution_safety_passed"] is True
    assert audit["metrics"]["eos_loss_weight"] == 4.0
    assert audit["metrics"]["contentful_generation_rate"] == 0.0625
    assert audit["metrics"]["repetition_negative_rows"] >= 1
    assert audit["metrics"]["post_clip_grad_norm_max"] <= 10.0
