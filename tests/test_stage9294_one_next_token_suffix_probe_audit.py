from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load():
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "scripts"))
    path = root / "scripts/build_stage9294_one_next_token_suffix_probe_audit.py"
    spec = importlib.util.spec_from_file_location("stage9294", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_stage9294_records_safe_one_next_token_generation_failure():
    mod = _load()
    audit = mod.audit_run()
    assert audit["passed"] is True
    assert audit["safety_gate_passed"] is True
    assert audit["quality_gate_passed"] is False
    assert audit["train_one_token_generation_passed"] is False
    assert audit["rows"] == 6
    assert audit["train_rows"] == 4
    assert audit["eval_rows"] == 1
    assert audit["strict_rows"] == 1
    assert audit["generated_rows"] == 6
    assert audit["generation_audit_splits"] == "train,eval,strict_eval"
    assert audit["generation_prefix_start_rate"] == 1.0
    assert audit["target_prefix_match_rate"] == 0.0
    assert audit["unterminated_generation_rate"] == 1.0
    assert audit["degenerate_repetition_rate"] == 0.0
    assert audit["generated_internal_token_rows"] == 0
    assert audit["train_loss_decreased"] is True
    assert audit["runtime_executed"] is False
    assert audit["gemma_executed"] is False
    assert audit["harness_executed"] is False
    assert audit["final_checkpoint_exported"] is False
    assert audit["missing_artifacts"] == []
    assert audit["diagnosis"] == "one_next_token_free_run_suffix_generation_fails_despite_teacher_forced_loss_drop"


def test_stage9294_split_summary_covers_train_eval_strict():
    mod = _load()
    audit = mod.audit_run()
    splits = audit["split_generation_summary"]
    assert splits["train"]["rows"] == 4
    assert splits["eval"]["rows"] == 1
    assert splits["strict_eval"]["rows"] == 1
    assert splits["train"]["target_prefix_match_rows"] == 0
    assert splits["train"]["unterminated_rows"] == 4
