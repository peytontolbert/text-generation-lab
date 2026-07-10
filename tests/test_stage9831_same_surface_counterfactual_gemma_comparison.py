from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load():
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "scripts"))
    path = root / "scripts/build_stage9831_same_surface_counterfactual_gemma_comparison.py"
    spec = importlib.util.spec_from_file_location("stage9831", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_stage9831_summarize_accuracy_and_comparison_counts():
    mod = _load()
    hundred_m_rows = [
        {"language_family": "python", "split": "eval", "correct": True},
        {"language_family": "python", "split": "eval", "correct": False},
        {"language_family": "python", "split": "strict_eval", "correct": True},
        {"language_family": "rust", "split": "eval", "correct": False},
        {"language_family": "rust", "split": "strict_eval", "correct": False},
        {"language_family": "c_cpp", "split": "eval", "correct": True},
        {"language_family": "c_cpp", "split": "strict_eval", "correct": True},
        {"language_family": "web_js_ts_html", "split": "eval", "correct": False},
        {"language_family": "web_js_ts_html", "split": "strict_eval", "correct": True},
    ]
    gemma_rows = [
        {"language_family": "python", "split": "eval", "correct": False},
        {"language_family": "python", "split": "eval", "correct": False},
        {"language_family": "python", "split": "strict_eval", "correct": True},
        {"language_family": "rust", "split": "eval", "correct": True},
        {"language_family": "rust", "split": "strict_eval", "correct": False},
        {"language_family": "c_cpp", "split": "eval", "correct": False},
        {"language_family": "c_cpp", "split": "strict_eval", "correct": True},
        {"language_family": "web_js_ts_html", "split": "eval", "correct": False},
        {"language_family": "web_js_ts_html", "split": "strict_eval", "correct": False},
    ]
    manifest_rows = [
        {"row_id": "r1", "split": "eval", "language_family": "python", "input_state": {"task_observation": "o", "visible_locality_evidence": "e"}, "target": {"decoder_text": "A"}},
        {"row_id": "r2", "split": "strict_eval", "language_family": "python", "input_state": {"task_observation": "o2", "visible_locality_evidence": "e2"}, "target": {"decoder_text": "B"}},
    ]
    mod.risk_flags = lambda: {"cells_with_shortcut_risk": 4, "flagged_cells": []}
    audit = mod.build_audit(gemma_rows, hundred_m_rows, manifest_rows)
    assert audit["wins_100m"] == 3
    assert audit["wins_gemma"] == 1
    assert audit["ties"] == 4
    assert audit["comparisons"]["python:eval"]["verdict"] == "100m_win"
    assert audit["comparisons"]["rust:eval"]["verdict"] == "gemma_win"
    assert audit["comparisons"]["python:strict_eval"]["verdict"] == "tie"
