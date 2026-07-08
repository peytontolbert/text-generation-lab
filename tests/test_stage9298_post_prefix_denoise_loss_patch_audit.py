from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load():
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "scripts"))
    path = root / "scripts/build_stage9298_post_prefix_denoise_loss_patch_audit.py"
    spec = importlib.util.spec_from_file_location("stage9298", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_stage9298_post_prefix_loss_patch_is_present():
    mod = _load()
    audit = mod.audit_patch()
    assert audit["passed"] is True
    assert audit["missing_snippets"] == []
    assert audit["source_boundary_match_rate"] == 0.0
    assert audit["post_prefix_loss_mask_present"] is True
    assert audit["decoder_loss_accepts_token_mask"] is True
    assert audit["train_loop_uses_post_prefix_mask"] is True
    assert audit["eval_loop_uses_post_prefix_mask"] is True
    assert audit["execution_authorized_next"] is False
    assert audit["authority"]["model_execution_authorized_next"] is False
