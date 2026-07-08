from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load():
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "scripts"))
    path = root / "scripts/build_stage9303_causal_mask_boundary_probe_audit.py"
    spec = importlib.util.spec_from_file_location("stage9303", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_stage9303_records_train_and_strict_success_but_eval_failure():
    mod = _load()
    audit = mod.audit_run()
    assert audit["passed"] is True
    assert audit["safety_gate_passed"] is True
    assert audit["quality_gate_passed"] is False
    assert audit["boundary_artifact_present"] is True
    assert audit["boundary_rows"] == 6
    assert audit["boundary_match_rows"] == 5
    assert audit["boundary_match_rate"] == 5 / 6
    assert audit["target_prefix_match_rate"] == 5 / 6
    assert audit["baseline_boundary_match_rate"] == 2 / 6
    assert audit["boundary_match_rate_improved"] is True
    assert audit["split_boundary_summary"]["train"]["matches"] == 4
    assert audit["split_boundary_summary"]["strict_eval"]["matches"] == 1
    assert audit["split_boundary_summary"]["eval"]["matches"] == 0
    assert audit["runtime_executed"] is False
    assert audit["gemma_executed"] is False
    assert audit["harness_executed"] is False
    assert audit["final_checkpoint_exported"] is False
    assert audit["missing_artifacts"] == []
    assert audit["diagnosis"] == "corrected_causal_mask_enables_train_and_strict_generation_but_eval_suffix_class_remains_unlearned"
