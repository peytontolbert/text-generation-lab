from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load():
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "scripts"))
    path = root / "scripts/build_stage9283_suffix_step_contract_preflight.py"
    spec = importlib.util.spec_from_file_location("stage9283", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_stage9283_accepts_suffix_step_manifest_contract_and_prefix_field():
    mod = _load()
    audit = mod.audit_preflight()
    assert audit["passed"] is True
    assert audit["rows"] == 8
    assert audit["split_counts"] == {"eval": 1, "strict_eval": 2, "train": 5}
    assert audit["trainer_contract_passed"] is True
    assert audit["loss_counts"]["denoise_ce"] == 8
    assert audit["loss_counts"].get("decoder_ce", 0) == 0
    assert audit["generation_prefix_field"] == "model_input.bridge_priming_span"
    assert audit["contract_generation_prefix_field"] == "model_input.bridge_priming_span"
    assert audit["missing_generation_prefix_rows"] == 0
    assert audit["prefix_target_mismatch_rows"] == 0
    assert audit["over_decoder_token_cap_rows"] == 0
    assert audit["authority_rows"] == 0
    assert audit["unsafe_loss_rows"] == 0
    assert audit["suffix_step_execution_ready"] is True
    assert audit["execution_authorized_now"] is False


def test_stage9283_runtime_support_detects_denoise_prefix_contract():
    mod = _load()
    support = mod._denoise_runtime_support()
    assert support["execution_supported"] is True
    assert support["has_native_denoise_runner"] is True
    assert support["trainer_dispatches_native_denoise_runner"] is True
    assert support["generation_prefix_contract_supported"] is True


def test_stage9283_nested_prefix_helper():
    mod = _load()
    row = {"model_input": {"bridge_priming_span": "Select the"}}
    assert mod._nested(row, "model_input.bridge_priming_span") == "Select the"
    assert mod._nested(row, "model_input.missing") is None
