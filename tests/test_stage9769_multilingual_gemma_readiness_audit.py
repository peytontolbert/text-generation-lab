from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load():
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "scripts"))
    path = root / "scripts/build_stage9769_multilingual_gemma_readiness_audit.py"
    spec = importlib.util.spec_from_file_location("stage9769", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_stage9769_audit_reports_target_language_coverage_and_real_execution():
    mod = _load()
    audit = mod.build_audit()
    assert audit["passed"] is True
    assert audit["ready_cell_count"] == 13
    assert audit["evidence_complete_cell_count"] == 13
    assert sorted(audit["target_languages"]) == ["c_cpp", "python", "rust", "web_js_ts_html"]
    assert audit["real_gemma_execution_cell_count"] >= 1
    assert audit["per_language"]["python"]["real_gemma_cells"] >= 1
    assert audit["packet_language_field_missing_count"] == 13
    assert any("label vocabulary" in finding for finding in audit["findings"])
