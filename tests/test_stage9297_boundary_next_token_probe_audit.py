from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load():
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "scripts"))
    path = root / "scripts/build_stage9297_boundary_next_token_probe_audit.py"
    spec = importlib.util.spec_from_file_location("stage9297", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_stage9297_records_boundary_rank_failure():
    mod = _load()
    audit = mod.audit_run()
    assert audit["passed"] is True
    assert audit["safety_gate_passed"] is True
    assert audit["quality_gate_passed"] is False
    assert audit["boundary_artifact_present"] is True
    assert audit["boundary_rows"] == 6
    assert audit["boundary_available_rows"] == 6
    assert audit["boundary_match_rows"] == 0
    assert audit["boundary_match_rate"] == 0.0
    assert audit["boundary_mean_expected_rank"] == 402.5
    assert audit["boundary_min_expected_rank"] == 101
    assert audit["boundary_max_expected_rank"] == 1293
    assert audit["split_boundary_summary"]["train"]["rows"] == 4
    assert audit["split_boundary_summary"]["train"]["matches"] == 0
    assert audit["train_loss_decreased"] is True
    assert audit["runtime_executed"] is False
    assert audit["gemma_executed"] is False
    assert audit["harness_executed"] is False
    assert audit["final_checkpoint_exported"] is False
    assert audit["missing_artifacts"] == []
    assert audit["diagnosis"] == "correct_suffix_token_not_top_ranked_at_forced_bridge_boundary_after_training"
