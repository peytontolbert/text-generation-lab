from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load():
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "scripts"))
    path = root / "scripts/build_stage9292_one_next_token_execution_review.py"
    spec = importlib.util.spec_from_file_location("stage9292", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_stage9292_authorizes_only_one_next_token_denoise_run():
    mod = _load()
    review = mod.build_review()
    validation = mod.validate_review(review)
    assert validation == []
    assert review["passed"] is True
    assert review["execution_authorized_next"] is True
    assert review["authorization_scope"] == "one_tiny_one_next_token_suffix_denoise_probe_only"
    limits = review["required_limits"]
    assert limits["mode"] == "denoise_repair_probe"
    assert limits["probe_scale"] == "target_100m"
    assert limits["max_train_rows"] == 4
    assert limits["max_eval_rows"] == 1
    assert limits["max_strict_rows"] == 1
    assert limits["max_decoder_tokens"] == 96
    assert limits["max_generation_rows"] == 6
    assert limits["max_generation_tokens"] == 32
    assert limits["generation_audit_splits"] == "train,eval,strict_eval"
    assert review["authority"]["model_execution_authorized_next"] is True
    assert review["authority"]["denoise_ce_training_authorized_next"] is True
    assert review["authority"]["decoder_ce_training_authorized_next"] is False
    assert review["authority"]["runtime_authorized"] is False


def test_stage9292_validation_rejects_forbidden_authority():
    mod = _load()
    review = mod.build_review()
    review["authority"]["runtime_authorized"] = True
    failures = mod.validate_review(review)
    assert "forbidden_authority_true:runtime_authorized" in failures
