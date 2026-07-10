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


def test_stage10058_same_manifest_comparison_audit_requires_successor_outputs():
    mod = _load(ROOT / "scripts/build_stage10058_balanced_fresh_source_multilingual_same_manifest_comparison_audit.py", "stage10058")
    built = mod.build_audit()
    if built["metrics"]["rows_successor_present"] == 0:
        assert built["passed"] is False
        assert "shared_ids_not_equal_to_55" in built["failures"]
    else:
        assert built["passed"] is True
        assert built["metrics"]["shared_rows"] == 55
        assert len(built["metrics"]["per_language"]) == 4
