from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load():
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "scripts"))
    path = root / "scripts/build_stage9821_weighted_web_phase2_manifest.py"
    spec = importlib.util.spec_from_file_location("stage9821", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_stage9821_builds_multilingual_train_manifest_with_web_boost_duplicates():
    mod = _load()
    audit = mod.build_manifest()
    assert audit["passed"] is True
    assert audit["rows"] == 65
    rows = mod.load_jsonl(mod.MANIFEST)
    train_rows = [row for row in rows if row["split"] == "train"]
    assert len(train_rows) == 25
    assert sum(1 for row in train_rows if row["language_family"] == "web_js_ts_html") == 10
    assert {row["language_family"] for row in train_rows} == {"python", "rust", "c_cpp", "web_js_ts_html"}
