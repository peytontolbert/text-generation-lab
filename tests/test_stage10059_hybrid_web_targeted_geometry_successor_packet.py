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


def test_stage10059_hybrid_web_targeted_geometry_successor_packet():
    mod = _load(ROOT / "scripts/build_stage10059_hybrid_web_targeted_geometry_successor_packet.py", "stage10059")
    built = mod.build_packet()
    assert built["passed"] is True
    assert built["metrics"]["base_rows"] == 103
    assert built["metrics"]["successor_rows"] == 124
    assert built["metrics"]["fresh_source_rows"] == 21
    assert built["metrics"]["split_counts"] == {"eval": 38, "strict_eval": 17, "train": 69}
    assert built["metrics"]["language_counts"] == {"c_cpp": 38, "python": 27, "rust": 17, "web_js_ts_html": 42}
    assert built["metrics"]["selected_counts"] == {
        "c_cpp:A": 1, "c_cpp:B": 3, "c_cpp:C": 1, "c_cpp:D": 1, "c_cpp:E": 2,
        "rust:A": 1, "rust:B": 1, "rust:C": 2, "rust:D": 1, "rust:E": 1,
        "web_js_ts_html:A": 6, "web_js_ts_html:C": 1,
    }
    assert built["metrics"]["readiness_passed"] is True
