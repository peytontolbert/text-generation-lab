from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load():
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "scripts"))
    path = root / "scripts/build_stage9730_multilingual_structured_execution_language_slice_audit.py"
    spec = importlib.util.spec_from_file_location("stage9730", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_stage9730_verifier_repair_is_quarter_exact_per_language():
    mod = _load()
    audit = mod.audit_surface(
        "verifier_repair",
        mod.SURFACES["verifier_repair"]["manifest"],
        mod.SURFACES["verifier_repair"]["logits"],
    )
    assert audit["failures"] == []
    for lang in mod.LANGS:
        assert audit["language_slices"][lang]["eval"]["rows"] == 4
        assert audit["language_slices"][lang]["strict_eval"]["rows"] == 4
        assert audit["language_slices"][lang]["eval"]["exact"] == 0.25
        assert audit["language_slices"][lang]["strict_eval"]["exact"] == 0.25


def test_stage9730_edit_and_patch_are_zero_exact_per_language():
    mod = _load()
    for surface in ["edit_localization", "patch_operator"]:
        audit = mod.audit_surface(
            surface,
            mod.SURFACES[surface]["manifest"],
            mod.SURFACES[surface]["logits"],
        )
        assert audit["failures"] == []
        for lang in mod.LANGS:
            assert audit["language_slices"][lang]["eval"]["exact"] == 0.0
            assert audit["language_slices"][lang]["strict_eval"]["exact"] == 0.0


def test_stage9730_build_audit_passes():
    mod = _load()
    audit = mod.build_audit()
    assert audit["failures"] == []
    assert audit["passed"] is True
