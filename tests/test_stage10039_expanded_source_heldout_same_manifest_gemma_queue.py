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


def test_stage10039_expanded_source_heldout_gemma_queue():
    mod = _load(ROOT / "scripts/build_stage10039_expanded_source_heldout_same_manifest_gemma_queue.py", "stage10039")
    built = mod.build_queue()
    assert built["passed"] is True
    assert built["metrics"]["rows"] == 95
    assert built["metrics"]["split_counts"] == {"eval": 38, "strict_eval": 17, "train": 40}
    assert built["metrics"]["heldout_compare_rows"] == 55

