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


def test_stage10062_web_non_b_anticollapse_successor_packet():
    mod = _load(ROOT / "scripts/build_stage10062_web_non_b_anticollapse_successor_packet.py", "stage10062")
    built = mod.build_packet()
    assert built["passed"] is True
    assert built["metrics"]["base_rows"] == 127
    assert built["metrics"]["successor_rows"] == 142
    assert built["metrics"]["fresh_source_rows"] == 15
    assert built["metrics"]["split_counts"] == {"eval": 38, "strict_eval": 17, "train": 87}
    assert built["metrics"]["language_counts"] == {
        "c_cpp": 38,
        "python": 27,
        "rust": 17,
        "web_js_ts_html": 60,
    }
    assert built["metrics"]["selected_counts"] == {"C": 5, "D": 5, "E": 5}
    assert built["metrics"]["readiness_passed"] is True
