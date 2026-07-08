from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load():
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "scripts"))
    path = root / "scripts/build_stage9276_prefix_primed_denoise_probe_audit.py"
    spec = importlib.util.spec_from_file_location("stage9276", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_stage9276_audit_records_prefix_control_fixed_but_quality_failed():
    mod = _load()
    audit = mod.audit_run()
    assert audit["passed"] is True
    assert audit["safety_gate_passed"] is True
    assert audit["quality_gate_passed"] is False
    assert audit["rows"] == 21
    assert audit["generation_prefix_field"] == "model_input.copy_prefix_span"
    assert audit["generation_prefix_start_rate"] == 1.0
    assert audit["target_prefix_match_rate"] == 0.0
    assert audit["generated_internal_token_rows"] == 0
    assert audit["diagnosis"] == "decoder_start_control_fixed_continuation_semantics_still_failing"


def test_stage9276_audit_keeps_forbidden_surfaces_closed():
    mod = _load()
    audit = mod.audit_run()
    assert audit["runtime_executed"] is False
    assert audit["gemma_executed"] is False
    assert audit["harness_executed"] is False
    assert audit["final_checkpoint_exported"] is False
