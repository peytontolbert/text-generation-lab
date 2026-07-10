from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_stage10052_comparison_builder_is_structurally_sound_without_outputs():
    mod = _load(ROOT / "scripts/build_stage10052_balanced_multilingual_same_manifest_comparison_audit.py", "stage10052")
    built = mod.build_audit()
    assert built["passed"] is False
    assert built["rows"] == []
    assert "per_language_not_4" in built["failures"]
    assert "shared_ids_not_equal_to_55" in built["failures"]
