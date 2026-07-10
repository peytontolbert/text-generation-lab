from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load():
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "scripts"))
    path = root / "scripts/build_stage9734_edit_localization_label_aligned_language_slice_audit.py"
    spec = importlib.util.spec_from_file_location("stage9734", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_stage9734_records_uniform_multilingual_improvement():
    mod = _load()
    audit = mod.build_audit()
    assert audit["failures"] == []
    for lang in mod.LANGS:
        assert audit["language_slices"][lang]["eval"]["rows"] == 7
        assert audit["language_slices"][lang]["eval"]["correct"] == 1
        assert audit["language_slices"][lang]["eval"]["exact"] == 1 / 7
        assert audit["language_slices"][lang]["strict_eval"]["rows"] == 7
        assert audit["language_slices"][lang]["strict_eval"]["correct"] == 1
        assert audit["language_slices"][lang]["strict_eval"]["exact"] == 1 / 7
