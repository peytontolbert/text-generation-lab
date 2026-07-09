from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load():
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "scripts"))
    path = root / "scripts/build_stage9716_context_encoder_handoff_patch_audit.py"
    spec = importlib.util.spec_from_file_location("stage9716", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_stage9716_resolved_handoff_contracts():
    mod = _load()
    assert mod.stage9715.row_text_serializes_context_rows() is True
    assert mod.stage9715.trainer_default_max_encoder_tokens() >= 2048
    assert mod.stage9715.build_batch_default_max_encoder_tokens() >= 2048
