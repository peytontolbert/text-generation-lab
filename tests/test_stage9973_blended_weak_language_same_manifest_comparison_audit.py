from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load():
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "scripts"))
    path = root / "scripts/build_stage9973_blended_weak_language_same_manifest_comparison_audit.py"
    spec = importlib.util.spec_from_file_location("stage9973", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_build_audit_scores_real_same_manifest_outputs():
    mod = _load()
    audit, rows = mod.build_audit()
    assert audit["passed"] is True
    metrics = audit["metrics"]
    assert metrics["comparison_ready_now"] is True
    assert metrics["rows_100m_present"] == 80
    assert metrics["rows_gemma_present"] == 80
    assert metrics["comparison_cells"] == 8
    assert len(rows) == 80
