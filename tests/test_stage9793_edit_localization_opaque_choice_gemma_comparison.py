from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load():
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "scripts"))
    path = root / "scripts/build_stage9793_edit_localization_opaque_choice_gemma_comparison.py"
    spec = importlib.util.spec_from_file_location("stage9793", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_stage9793_builds_expected_opaque_choice_model_slices():
    mod = _load()
    manifest_rows = mod.load_jsonl(mod.MANIFEST)
    model_rows = mod.load_jsonl(mod.DEFAULT_MODEL_ROWS)
    labels = mod.label_vocab(manifest_rows)
    slices = mod.model_language_slices(manifest_rows, model_rows)
    assert labels == ["A", "B", "C", "D", "E"]
    assert slices["python"]["strict_exact"] == 0.0
    assert slices["rust"]["strict_exact"] == 0.2
    assert slices["c_cpp"]["strict_exact"] == 0.0
    assert slices["web_js_ts_html"]["strict_exact"] == 0.0


def test_stage9793_dry_run_preserves_artifact_shape():
    mod = _load()
    audit, rows = mod.build_audit(execute_gemma=False)
    assert audit["passed"] is True
    assert audit["gemma_executed"] is False
    assert audit["results"][0]["label_vocab_scope"] == "full_packet"
    assert len(rows) == 20
