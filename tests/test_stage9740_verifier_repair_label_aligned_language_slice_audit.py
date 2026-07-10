from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load():
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "scripts"))
    path = root / "scripts/build_stage9740_verifier_repair_label_aligned_language_slice_audit.py"
    spec = importlib.util.spec_from_file_location("stage9740", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_stage9740_build_audit_shape():
    mod = _load()
    audit = mod.build_audit()
    assert set(audit["language_slices"]) == set(mod.LANGS)
