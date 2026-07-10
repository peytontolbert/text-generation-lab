from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load():
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "scripts"))
    path = root / "scripts/build_stage9856_abstention_honesty_gemma_comparison.py"
    spec = importlib.util.spec_from_file_location("stage9856", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_stage9856_build_audit_counts_surface_wins():
    mod = _load()
    hundred = []
    gemma = []
    for surface in mod.SURFACES:
        for lang in mod.LANGS:
            for split in mod.SPLITS:
                hundred.append({"surface": surface, "language_family": lang, "split": split, "correct": True})
                gemma.append({"surface": surface, "language_family": lang, "split": split, "correct": surface == "patch_operator"})
    audit = mod.build_audit(hundred, gemma)
    assert audit["wins_100m"] == 8
    assert audit["wins_gemma"] == 0
    assert audit["ties"] == 8
