from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load():
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "scripts"))
    path = root / "scripts/build_stage9818_web_only_phase2_manifest.py"
    spec = importlib.util.spec_from_file_location("stage9818", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_stage9818_builds_web_only_train_and_full_multilingual_eval_manifest():
    mod = _load()
    audit = mod.build_manifest()
    assert audit["passed"] is True
    assert audit["rows"] == 45
    rows = mod.load_jsonl(mod.MANIFEST)
    train_rows = [row for row in rows if row["split"] == "train"]
    eval_rows = [row for row in rows if row["split"] == "eval"]
    strict_rows = [row for row in rows if row["split"] == "strict_eval"]
    assert len(train_rows) == 5
    assert len(eval_rows) == 20
    assert len(strict_rows) == 20
    assert {row["language_family"] for row in train_rows} == {"web_js_ts_html"}
    assert {row["language_family"] for row in strict_rows} == {"python", "rust", "c_cpp", "web_js_ts_html"}
