from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load():
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "scripts"))
    path = root / "scripts/build_stage9284_suffix_step_execution_review.py"
    spec = importlib.util.spec_from_file_location("stage9284", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_stage9284_authorizes_only_one_suffix_step_denoise_run():
    mod = _load()
    review = mod.build_review()
    failures = mod.validate_review(review)
    assert failures == []
    assert review["passed"] is True
    assert review["execution_authorized_next"] is True
    assert review["authorization_scope"] == "one_tiny_suffix_step_denoise_probe_only"
    authority = review["authority"]
    assert authority["model_execution_authorized_next"] is True
    assert authority["denoise_ce_training_authorized_next"] is True
    for key, value in authority.items():
        if key not in {"model_execution_authorized_next", "denoise_ce_training_authorized_next"}:
            assert value is False, key
    limits = review["required_limits"]
    assert limits["mode"] == "denoise_repair_probe"
    assert limits["max_train_rows"] == 5
    assert limits["max_eval_rows"] == 1
    assert limits["max_strict_rows"] == 2
    assert limits["max_steps"] == 16
    assert limits["max_decoder_tokens"] == 160
    assert limits["decoder_ce_weight"] == 0.0
    assert limits["denoise_weight"] == 1.0
    assert limits["generation_prefix_field"] == "model_input.bridge_priming_span"
    assert "--execution-authorized-for-recovery-probe" in review["required_flags"]
    assert "decoder_ce_training" in review["forbidden_operations"]
    assert "runtime_execution" in review["forbidden_operations"]
    assert "cleanup_proof.json" in review["required_postrun_artifacts"]


def test_stage9284_validation_rejects_forbidden_authority_or_missing_limits():
    mod = _load()
    review = mod.build_review()
    review["authority"]["runtime_authorized"] = True
    review["required_limits"]["max_steps"] = 999
    failures = mod.validate_review(review)
    assert "forbidden_authority_true:runtime_authorized" in failures
    assert "limit_mismatch:max_steps" in failures


def test_stage9284_fails_closed_if_source_not_passed(monkeypatch):
    mod = _load()
    real_load = mod.load_json

    def fake_load(path):
        if path == mod.SOURCE_SUMMARY:
            return {"passed": False, "metrics": {}}
        return real_load(path)

    monkeypatch.setattr(mod, "load_json", fake_load)
    review = mod.build_review()
    assert review["passed"] is False
    assert review["execution_authorized_next"] is False
    assert review["authority"]["model_execution_authorized_next"] is False
    assert "source_stage9283_not_passed" in review["failures"]
