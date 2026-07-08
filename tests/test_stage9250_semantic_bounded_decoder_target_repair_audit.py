from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load():
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "scripts"))
    path = root / "scripts/build_stage9250_semantic_bounded_decoder_target_repair_audit.py"
    spec = importlib.util.spec_from_file_location("stage9250", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_stage9250_imports_closed_authority_and_manifest_path():
    mod = _load()
    assert mod.STAGE == 9250
    assert mod.MANIFEST.name == "semantic_bounded_decoder_target_repair_manifest.jsonl"
    assert all(value is False for value in mod.AUTHORITY_CLOSED.values())
