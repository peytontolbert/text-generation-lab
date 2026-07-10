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


def test_stage10045_expanded_source_heldout_review_packets():
    mod = _load(ROOT / "scripts/build_stage10045_expanded_source_heldout_review_packets.py", "stage10045")
    built = mod.build_packets()
    assert built["passed"] is True
    assert built["metrics"]["language_packets"] == 4
    assert built["metrics"]["compare_rows"] == 55
    assert built["metrics"]["fresh_review_rows"] == 18
    assert built["metrics"]["fresh_language_counts"] == {"c_cpp": 12, "python": 6}
