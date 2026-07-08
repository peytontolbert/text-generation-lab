from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load():
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "scripts"))
    path = root / "scripts/build_stage9295_boundary_next_token_telemetry_patch_audit.py"
    spec = importlib.util.spec_from_file_location("stage9295", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_stage9295_boundary_next_token_telemetry_patch_is_present():
    mod = _load()
    audit = mod.audit_patch()
    assert audit["passed"] is True
    assert audit["missing_snippets"] == []
    assert audit["source_quality_gate_passed"] is False
    assert audit["records_expected_token_rank"] is True
    assert audit["records_top_k"] is True
    assert audit["writes_boundary_logits_artifact"] is True
    assert audit["sample_generation_card_has_boundary_metrics"] is True
    assert audit["execution_authorized_next"] is False
    assert audit["authority"]["model_execution_authorized_next"] is False
    assert audit["authority"]["denoise_ce_training_authorized_next"] is False
