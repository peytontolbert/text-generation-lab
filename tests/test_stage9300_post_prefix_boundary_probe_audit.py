from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load():
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "scripts"))
    path = root / "scripts/build_stage9300_post_prefix_boundary_probe_audit.py"
    spec = importlib.util.spec_from_file_location("stage9300", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_stage9300_records_improved_but_incomplete_boundary_generation():
    mod = _load()
    audit = mod.audit_run()
    assert audit["passed"] is True
    assert audit["safety_gate_passed"] is True
    assert audit["quality_gate_passed"] is False
    assert audit["boundary_artifact_present"] is True
    assert audit["boundary_rows"] == 6
    assert audit["boundary_match_rows"] == 2
    assert audit["boundary_match_rate"] == 2 / 6
    assert audit["baseline_boundary_match_rate"] == 0.0
    assert audit["boundary_match_rate_improved"] is True
    assert audit["boundary_mean_rank_improved"] is True
    assert audit["boundary_mean_expected_rank"] == 217.83333333333334
    assert audit["target_prefix_match_rate"] == 0.0
    assert audit["split_boundary_summary"]["train"]["matches"] == 2
    assert audit["split_boundary_summary"]["eval"]["matches"] == 0
    assert audit["split_boundary_summary"]["strict_eval"]["matches"] == 0
    assert audit["runtime_executed"] is False
    assert audit["gemma_executed"] is False
    assert audit["harness_executed"] is False
    assert audit["final_checkpoint_exported"] is False
    assert audit["missing_artifacts"] == []
    assert audit["diagnosis"] == "post_prefix_loss_mask_improves_boundary_rank_but_generation_still_not_safe"
