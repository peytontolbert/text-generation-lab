from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load():
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "scripts"))
    path = root / "scripts/build_stage9722_multilingual_verifier_repair_tiny_package.py"
    spec = importlib.util.spec_from_file_location("stage9722", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_stage9722_selects_balanced_multilingual_rows():
    mod = _load()
    rows = mod.load_jsonl(mod.SOURCE)
    selected, failures = mod.select_rows(rows)
    assert failures == []
    assert len(selected) == 64
    counts = {}
    for lang in mod.LANGS:
        counts[lang] = sum(1 for row in selected if row["language_family"] == lang)
    assert counts == {"python": 16, "rust": 16, "c_cpp": 16, "web_js_ts_html": 16}


def test_stage9722_split_balance_is_8_4_4_per_language():
    mod = _load()
    rows = mod.load_jsonl(mod.SOURCE)
    selected, _ = mod.select_rows(rows)
    for lang in mod.LANGS:
        assert sum(1 for row in selected if row["language_family"] == lang and row["split"] == "train") == 8
        assert sum(1 for row in selected if row["language_family"] == lang and row["split"] == "eval") == 4
        assert sum(1 for row in selected if row["language_family"] == lang and row["split"] == "strict_eval") == 4
