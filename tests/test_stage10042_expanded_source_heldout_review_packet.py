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


def test_stage10042_expanded_source_heldout_review_packet():
    mod = _load(ROOT / "scripts/build_stage10042_expanded_source_heldout_review_packet.py", "stage10042")
    built = mod.build_packet()
    assert built["passed"] is True
    assert built["metrics"]["rows"] == 18
    assert built["metrics"]["language_counts"] == {"c_cpp": 12, "python": 6}
    assert built["metrics"]["split_counts"] == {"eval": 18}

