from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load():
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "scripts"))
    path = root / "scripts/build_stage9770_multilingual_edit_localization_gemma_comparison.py"
    spec = importlib.util.spec_from_file_location("stage9770", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_stage9770_reports_mixed_multilingual_edit_localization_result():
    mod = _load()
    audit = mod.build_audit()
    assert audit["passed"] is True
    assert audit["language_count"] == 4
    assert audit["gemma_better_language_count"] == 0
    assert audit["model_better_language_count"] == 0
    assert audit["tie_language_count"] == 4
    results = {row["language"]: row for row in audit["results"]}
    assert results["python"]["gemma_strict_exact"] == 0.2
    assert results["rust"]["gemma_strict_exact"] == 0.2
    assert results["c_cpp"]["gemma_strict_exact"] == 0.2
    assert results["web_js_ts_html"]["gemma_strict_exact"] == 0.2
    assert all(row["label_vocab_scope"] == "full_packet" for row in audit["results"])
