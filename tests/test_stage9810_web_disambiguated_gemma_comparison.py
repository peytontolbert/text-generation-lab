from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load():
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "scripts"))
    path = root / "scripts/build_stage9810_web_disambiguated_gemma_comparison.py"
    spec = importlib.util.spec_from_file_location("stage9810", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_stage9810_model_slice_reader_uses_manifest_rows():
    mod = _load()
    manifest_rows = mod.load_jsonl(mod.MANIFEST) if mod.MANIFEST.exists() else []
    if not manifest_rows:
        return
    model_rows = mod.load_jsonl(mod.MODEL_ROWS) if mod.MODEL_ROWS.exists() else []
    if not model_rows:
        return
    slices = mod.model_language_slices(manifest_rows, model_rows)
    assert set(slices) == {"python", "rust", "c_cpp", "web_js_ts_html"}
