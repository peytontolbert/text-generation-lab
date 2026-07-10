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


def test_stage9999_source_heldout_gemma_queue():
    mod = _load(ROOT / "scripts/build_stage9999_source_heldout_same_manifest_gemma_queue.py", "stage9999")
    built = mod.build_queue()
    assert built["passed"] is True
    assert built["metrics"]["rows"] == 78
    assert built["metrics"]["split_counts"] == {"eval": 21, "strict_eval": 17, "train": 40}


def test_stage10001_comparison_builder_is_structurally_sound_without_outputs():
    mod = _load(ROOT / "scripts/build_stage10001_source_heldout_same_manifest_comparison_audit.py", "stage10001")
    built = mod.build_audit()
    assert built["passed"] is False
    assert built["rows"] == []
    assert "per_language_not_4" in built["failures"]
