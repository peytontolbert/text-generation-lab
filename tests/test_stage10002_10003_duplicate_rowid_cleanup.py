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


def test_stage10002_duplicate_rowid_audit():
    mod = _load(ROOT / "scripts/build_stage10002_duplicate_rowid_eval_audit.py", "stage10002")
    built = mod.build_audit()
    assert built["passed"] is True
    assert built["metrics"]["duplicate_row_id_count"] == 1


def test_stage10003_deduped_successor_request():
    mod = _load(ROOT / "scripts/build_stage10003_deduped_source_heldout_successor_request.py", "stage10003")
    built = mod.build_request()
    assert built["passed"] is True
    assert built["metrics"]["rows"] == 77
    assert built["metrics"]["removed_duplicate_eval_rows"] == 1
    assert built["metrics"]["split_counts"] == {"eval": 20, "strict_eval": 17, "train": 40}
