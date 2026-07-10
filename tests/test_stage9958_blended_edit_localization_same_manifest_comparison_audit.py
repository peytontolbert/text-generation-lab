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


def test_language_from_rows_uses_prompt_and_cell_key_fallbacks():
    mod = _load()
    inferred_from_prompt = mod.language_from_rows({}, {"prompt": "Structured input surface:\nlanguage=rust | route=KEEP_STRUCTURED"})
    inferred_from_cell = mod.language_from_rows({"cell_key": "python::structured_state::KEEP_STRUCTURED"}, {})
    inferred_web = mod.language_from_rows({}, {"prompt": "language=web_js_ts_html | state.file_extension=ts"})
    assert inferred_from_prompt == "rust"
    assert inferred_from_cell == "python"
    assert inferred_web == "web_js_ts_html"


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
