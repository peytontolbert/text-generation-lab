from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load():
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "scripts"))
    path = root / "scripts/build_stage9286_suffix_step_denoise_probe_audit.py"
    spec = importlib.util.spec_from_file_location("stage9286", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_stage9286_audit_records_safe_execution_and_quality_failure():
    mod = _load()
    audit = mod.audit_run()
    assert audit["passed"] is True
    assert audit["safety_gate_passed"] is True
    assert audit["quality_gate_passed"] is False
    assert audit["rows"] == 8
    assert audit["train_rows"] == 5
    assert audit["eval_rows"] == 1
    assert audit["strict_rows"] == 2
    assert audit["generated_rows"] == 3
    assert audit["generation_prefix_start_rate"] == 1.0
    assert audit["target_prefix_match_rate"] == 0.0
    assert audit["unterminated_generation_rate"] == 1.0
    assert audit["train_loss_decreased"] is True
    assert audit["train_loss_end"] < audit["train_loss_start"]
    assert audit["runtime_executed"] is False
    assert audit["gemma_executed"] is False
    assert audit["harness_executed"] is False
    assert audit["final_checkpoint_exported"] is False
    assert audit["required_artifacts_written"] is True
    assert audit["missing_artifacts"] == []
    assert audit["diagnosis"] == "teacher_forcing_loss_decreases_but_eval_strict_suffix_generation_still_fails"


def test_stage9286_detects_missing_artifacts(monkeypatch):
    mod = _load()
    monkeypatch.setattr(mod, "REQUIRED_ARTIFACTS", ["definitely_missing.json"])
    audit = mod.audit_run()
    assert audit["passed"] is False
    assert "required_artifacts_missing" in audit["failures"]
