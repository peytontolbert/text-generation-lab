from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load():
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "scripts"))
    path = root / "scripts/build_stage9270_target_100m_denoise_generation_audit.py"
    spec = importlib.util.spec_from_file_location("stage9270", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_stage9270_records_safe_but_quality_failed_generation_audit():
    mod = _load()
    audit = mod.audit_run()
    assert audit["passed"] is True
    assert audit["safety_gate_passed"] is True
    assert audit["quality_gate_passed"] is False
    assert audit["generated_rows"] == 13
    assert audit["contentful_generation_rate"] == 0.0
    assert audit["unterminated_generation_rate"] == 1.0
    assert audit["target_prefix_match_rate"] == 0.0
    assert audit["generated_internal_token_rows"] == 0
    assert audit["decoder_ce_training_authorized_next"] is False if "decoder_ce_training_authorized_next" in audit else True
    assert audit["runtime_executed"] is False
    assert audit["gemma_executed"] is False
    assert audit["harness_executed"] is False
    assert audit["final_checkpoint_exported"] is False
