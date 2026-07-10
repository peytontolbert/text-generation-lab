from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load():
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "scripts"))
    path = root / "scripts/build_stage9741_label_aligned_multilingual_structured_surface_comparison.py"
    spec = importlib.util.spec_from_file_location("stage9741", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_stage9741_surface_source_keys():
    mod = _load()
    assert set(mod.SOURCES) == {"verifier_repair", "edit_localization", "patch_operator"}
