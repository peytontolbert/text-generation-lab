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


def test_stage10050_balanced_multilingual_successor_packet():
    mod = _load(ROOT / "scripts/build_stage10050_balanced_multilingual_successor_packet.py", "stage10050")
    built = mod.build_packet()
    assert built["passed"] is True
    assert built["metrics"]["base_rows"] == 103
    assert built["metrics"]["successor_rows"] == 121
    assert built["metrics"]["anchor_rows"] == 18
    assert built["metrics"]["split_counts"] == {"eval": 38, "strict_eval": 17, "train": 66}
    assert built["metrics"]["anchor_language_counts"] == {
        "c_cpp": 7,
        "python": 2,
        "rust": 2,
        "web_js_ts_html": 7,
    }
    assert built["metrics"]["anchor_label_counts"] == {
        "c_cpp:A": 1,
        "c_cpp:B": 3,
        "c_cpp:C": 1,
        "c_cpp:E": 2,
        "python:C": 2,
        "rust:C": 2,
        "web_js_ts_html:A": 6,
        "web_js_ts_html:C": 1,
    }
    assert built["metrics"]["readiness_passed"] is True
