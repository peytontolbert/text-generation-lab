from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load():
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "scripts"))
    path = root / "scripts/build_stage9301_transformer_attention_mask_patch_audit.py"
    spec = importlib.util.spec_from_file_location("stage9301", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_stage9301_attention_mask_patch_is_present():
    mod = _load()
    audit = mod.audit_patch()
    assert audit["passed"] is True
    assert audit["missing_snippets"] == []
    assert audit["uses_additive_future_mask"] is True
    assert audit["uses_additive_padding_mask"] is True
    assert audit["has_causal_mask_test"] is True
    assert audit["has_padding_mask_test"] is True
    assert audit["execution_authorized_next"] is False
    assert audit["authority"]["model_execution_authorized_next"] is False
