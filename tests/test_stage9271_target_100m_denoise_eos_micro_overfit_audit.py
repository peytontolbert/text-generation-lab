from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load():
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "scripts"))
    path = root / "scripts/build_stage9271_target_100m_denoise_eos_micro_overfit_audit.py"
    spec = importlib.util.spec_from_file_location("stage9271", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_stage9271_records_eos_improvement_but_quality_still_failed():
    mod = _load()
    audit = mod.audit_run()
    assert audit["passed"] is True
    assert audit["safety_gate_passed"] is True
    assert audit["quality_gate_passed"] is False
    assert audit["eos_loss_weight"] == 4.0
    assert audit["max_steps"] == 80
    assert audit["contentful_generation_rate"] > audit["previous_contentful_generation_rate"]
    assert audit["unterminated_generation_rate"] < audit["previous_unterminated_generation_rate"]
    assert audit["target_prefix_match_rate"] == 0.0
    assert audit["generated_internal_token_rows"] == 0
    assert audit["train_loss_decreased"] is True
    assert audit["runtime_executed"] is False
    assert audit["gemma_executed"] is False
    assert audit["harness_executed"] is False
    assert audit["final_checkpoint_exported"] is False
