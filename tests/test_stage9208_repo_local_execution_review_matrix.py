from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load():
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "scripts"))
    path = root / "scripts/build_stage9208_repo_local_execution_review_matrix.py"
    spec = importlib.util.spec_from_file_location("stage9208_review", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_limit_failures_catch_eval_and_strict_over_cap():
    mod = _load()
    command = [
        "python",
        "trainer.py",
        "--max-train-rows",
        "32",
        "--max-eval-rows",
        "32",
        "--max-strict-rows",
        "32",
        "--max-steps",
        "8",
    ]
    failures = mod.limit_failures(command, mod.BOUNDED_DECODER_TINY_LIMITS)
    assert "max_eval_rows:32>16" in failures
    assert "max_strict_rows:32>16" in failures
    assert not any(item.startswith("max_train_rows") for item in failures)


def test_structured_review_accepts_tiny_loss_contract():
    mod = _load()
    command = [
        "python",
        "legacy_src/scripts/train_agentkernel_lite_encdec.py",
        "--manifest",
        "runs/local/artifacts/example/trainer_rows.jsonl",
        "--mode",
        "structured_policy_probe",
        "--max-train-rows",
        "1",
        "--max-eval-rows",
        "1",
        "--max-strict-rows",
        "1",
        "--max-steps",
        "8",
        "--decoder-ce-weight",
        "0.0",
        "--structured-aux-weight",
        "1.0",
        "--denoise-weight",
        "0.0",
        "--require-loss-mask-enforcement-audit",
        "--no-final-checkpoint-export",
        "--output-dir",
        "runs/local/artifacts/example/structured_probe",
    ]
    assert mod.limit_failures(command, mod.STRUCTURED_TINY_LIMITS) == []
    assert mod.loss_failures(command, "structured_policy_probe") == []
    assert mod.required_flag_failures(command) == []


def test_cleanup_flag_is_blocked_before_explicit_execution():
    mod = _load()
    command = [
        "python",
        "trainer.py",
        "--manifest",
        "runs/local/artifacts/example/trainer_rows.jsonl",
        "--mode",
        "structured_policy_probe",
        "--output-dir",
        "runs/local/artifacts/example/out",
        "--require-loss-mask-enforcement-audit",
        "--no-final-checkpoint-export",
        "--cleanup-checkpoints-after-probe",
    ]
    assert "cleanup_flag_present_before_explicit_execution" in mod.required_flag_failures(command)
