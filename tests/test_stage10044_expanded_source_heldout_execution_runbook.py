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


def test_stage10044_expanded_source_heldout_execution_runbook():
    mod = _load(ROOT / "scripts/build_stage10044_expanded_source_heldout_execution_runbook.py", "stage10044")
    built = mod.build_runbook()
    assert built["passed"] is True
    assert built["metrics"]["runbook_steps"] == 6
    assert built["metrics"]["same_manifest_compare_rows"] == 55
    assert built["metrics"]["row_contract_ok"] is True

