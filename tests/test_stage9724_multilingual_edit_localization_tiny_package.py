from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load():
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "scripts"))
    path = root / "scripts/build_stage9724_multilingual_edit_localization_tiny_package.py"
    spec = importlib.util.spec_from_file_location("stage9724", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_stage9724_selects_balanced_multilingual_rows():
    mod = _load()
    rows = mod.load_jsonl(mod.SOURCE)
    selected, failures = mod.select_rows(rows)
    assert failures == []
    assert len(selected) == 64
    counts = {}
    split_counts = {}
    for row in selected:
        lang = row["language_family"]
        counts[lang] = counts.get(lang, 0) + 1
        key = f"{lang}::{row['split']}"
        split_counts[key] = split_counts.get(key, 0) + 1
        assert row["expected_enabled_loss"] == "edit_localization_ce"
    assert counts == {
        "python": 16,
        "rust": 16,
        "c_cpp": 16,
        "web_js_ts_html": 16,
    }
    assert split_counts == {
        "python::train": 8,
        "python::eval": 4,
        "python::strict_eval": 4,
        "rust::train": 8,
        "rust::eval": 4,
        "rust::strict_eval": 4,
        "c_cpp::train": 8,
        "c_cpp::eval": 4,
        "c_cpp::strict_eval": 4,
        "web_js_ts_html::train": 8,
        "web_js_ts_html::eval": 4,
        "web_js_ts_html::strict_eval": 4,
    }
