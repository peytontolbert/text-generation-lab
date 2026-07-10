from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load():
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "scripts"))
    path = root / "scripts/build_stage9958_blended_edit_localization_same_manifest_comparison_audit.py"
    spec = importlib.util.spec_from_file_location("stage9958", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_build_audit_stays_pending_before_real_outputs_exist():
    mod = _load()
    audit, rows = mod.build_audit()
    assert audit["passed"] is True
    assert audit["metrics"]["comparison_ready_now"] is False
    assert "stage9950_row_field_logits_missing" in audit["pending_conditions"]
    assert "stage9953_gemma_rows_missing" in audit["pending_conditions"]
    assert rows == []


def test_bucket_metrics_compares_100m_and_gemma_by_split():
    mod = _load()
    rows = [
        {"row_id": "a", "language_family": "python", "split": "eval", "hundred_m_correct": True, "gemma_correct": False},
        {"row_id": "b", "language_family": "python", "split": "eval", "hundred_m_correct": False, "gemma_correct": False},
        {"row_id": "c", "language_family": "rust", "split": "strict_eval", "hundred_m_correct": False, "gemma_correct": True},
    ]
    buckets = mod.bucket_metrics(rows)
    assert buckets["python:eval"]["hundred_m_correct"] == 1
    assert buckets["python:eval"]["verdict"] == "100m_better"
    assert buckets["rust:strict_eval"]["verdict"] == "gemma_better"
