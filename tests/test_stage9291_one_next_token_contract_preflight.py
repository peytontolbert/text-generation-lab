from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load():
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "scripts"))
    path = root / "scripts/build_stage9291_one_next_token_contract_preflight.py"
    spec = importlib.util.spec_from_file_location("stage9291", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_stage9291_accepts_one_next_token_manifest_contract():
    mod = _load()
    audit = mod.audit_preflight()
    assert audit["passed"] is True
    assert audit["rows"] == 6
    assert audit["split_counts"] == {"train": 4, "eval": 1, "strict_eval": 1}
    assert audit["trainer_contract_passed"] is True
    assert audit["loss_counts"]["denoise_ce"] == 6
    assert audit["loss_counts"].get("decoder_ce", 0) == 0
    assert audit["generation_prefix_field"] == "model_input.bridge_priming_span"
    assert audit["generation_audit_splits"] == "train,eval,strict_eval"
    assert audit["contract_generation_audit_splits"] == "train,eval,strict_eval"
    assert audit["over_decoder_token_cap_rows"] == 0
    assert audit["authority_rows"] == 0
    assert audit["unsafe_loss_rows"] == 0
    assert audit["one_next_token_execution_ready"] is True
    assert audit["execution_authorized_now"] is False


def test_stage9291_runtime_support_detects_split_selector():
    mod = _load()
    support = mod._runtime_support()
    assert support["has_native_denoise_runner"] is True
    assert support["trainer_dispatches_native_denoise_runner"] is True
    assert support["generation_prefix_contract_supported"] is True
    assert support["generation_audit_splits_supported"] is True
