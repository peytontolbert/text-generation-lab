from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load():
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "scripts"))
    path = root / "scripts/build_stage9289_train_generation_memorization_probe_audit.py"
    spec = importlib.util.spec_from_file_location("stage9289", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_stage9289_records_train_generation_failure():
    mod = _load()
    audit = mod.audit_run()
    assert audit["passed"] is True
    assert audit["safety_gate_passed"] is True
    assert audit["quality_gate_passed"] is False
    assert audit["train_memorization_passed"] is False
    assert audit["generated_rows"] == 8
    assert audit["generation_audit_splits"] == "train,eval,strict_eval"
    assert audit["split_generation_summary"]["train"]["rows"] == 5
    assert audit["split_generation_summary"]["train"]["target_prefix_match_rows"] == 0
    assert audit["split_generation_summary"]["train"]["unterminated_rows"] == 5
    assert audit["target_prefix_match_rate"] == 0.0
    assert audit["unterminated_generation_rate"] == 1.0
    assert audit["train_loss_decreased"] is True
    assert audit["runtime_executed"] is False
    assert audit["gemma_executed"] is False
    assert audit["harness_executed"] is False
    assert audit["final_checkpoint_exported"] is False
