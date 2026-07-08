from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load():
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "scripts"))
    path = root / "scripts/build_stage9273_target_grounded_denoise_probe_audit.py"
    spec = importlib.util.spec_from_file_location("stage9273", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_stage9273_records_safe_but_prefix_recovery_failed():
    mod = _load()
    audit = mod.audit_run()
    assert audit["passed"] is True
    assert audit["safety_gate_passed"] is True
    assert audit["quality_gate_passed"] is False
    assert audit["target_prefix_match_rate"] == 0.0
    assert audit["generated_internal_token_rows"] == 0
    assert audit["decoder_ce_training_authorized_next"] is False if "decoder_ce_training_authorized_next" in audit else True
    assert audit["runtime_executed"] is False
    assert audit["gemma_executed"] is False
    assert audit["harness_executed"] is False
    assert audit["final_checkpoint_exported"] is False
    assert audit["diagnosis"] == "minimal_target_anchors_too_weak_for_prefix_recovery"
