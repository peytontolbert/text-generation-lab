from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load():
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "scripts"))
    path = root / "scripts/build_stage10017_quarantined_same_manifest_comparison_audit.py"
    spec = importlib.util.spec_from_file_location("stage10017", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_build_audit_reflects_quarantined_same_manifest_outputs():
    mod = _load()
    built = mod.build_audit()
    assert built["passed"] is True
    assert built["metrics"]["rows_100m_present"] == 72
    assert built["metrics"]["rows_gemma_present"] == 72
    assert built["metrics"]["comparison_rows"] == 72
    assert len(built["metrics"]["per_language"]) == 4
