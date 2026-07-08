from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load():
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "scripts"))
    path = root / "scripts/build_stage9268_denoise_repair_contract_preflight.py"
    spec = importlib.util.spec_from_file_location("stage9268", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_stage9268_accepts_manifest_contract_and_keeps_authority_closed():
    mod = _load()
    audit = mod.audit_preflight()
    assert audit["passed"] is True
    assert audit["rows"] == 21
    assert audit["split_counts"] == {"eval": 7, "strict_eval": 6, "train": 8}
    assert audit["trainer_contract_passed"] is True
    assert audit["loss_counts"]["denoise_ce"] == 21
    assert audit["loss_counts"]["decoder_ce"] == 0
    assert audit["authority_rows"] == 0
    assert audit["unsafe_loss_rows"] == 0
    assert audit["denoise_execution_ready"] is True
    assert audit["execution_authorized_now"] is False


def test_stage9268_runtime_support_detects_native_runner_and_dispatch():
    mod = _load()
    support = mod._denoise_runtime_support()
    assert support["execution_supported"] is True
    assert support["has_native_denoise_runner"] is True
    assert support["trainer_dispatches_native_denoise_runner"] is True
