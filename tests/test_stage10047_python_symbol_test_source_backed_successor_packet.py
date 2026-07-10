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


def test_stage10047_python_symbol_test_source_backed_successor_packet():
    mod = _load(ROOT / "scripts/build_stage10047_python_symbol_test_source_backed_successor_packet.py", "stage10047")
    built = mod.build_packet()
    assert built["passed"] is True
    assert built["metrics"]["train_rows"] == 8
    assert built["metrics"]["heldout_candidate_rows"] == 8
    assert built["metrics"]["selected_rows"] == 16
    assert built["metrics"]["selection_counts"] == {
        "TARGET_CONFIG:heldout_eval": 2,
        "TARGET_CONFIG:train": 2,
        "TARGET_SYMBOL:heldout_eval": 3,
        "TARGET_SYMBOL:train": 3,
        "TARGET_TEST:heldout_eval": 3,
        "TARGET_TEST:train": 3,
    }
    assert built["metrics"]["train_target_counts"] == {
        "TARGET_CONFIG": 2,
        "TARGET_SYMBOL": 3,
        "TARGET_TEST": 3,
    }
    assert built["metrics"]["heldout_target_counts"] == {
        "TARGET_CONFIG": 2,
        "TARGET_SYMBOL": 3,
        "TARGET_TEST": 3,
    }
    assert built["metrics"]["readiness_passed"] is True
