from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load():
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "scripts"))
    path = root / "scripts/build_stage9728_multilingual_execution_readiness_ledger.py"
    spec = importlib.util.spec_from_file_location("stage9728", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_stage9728_builds_expected_status_counts():
    mod = _load()
    anti_hack = mod.load_json(mod.ANTI_HACK)
    symbol_binding = mod.load_json(mod.SYMBOL_BINDING)
    ledger = mod.build_ledger(anti_hack, symbol_binding)
    assert ledger["failures"] == []
    assert ledger["metrics"]["records"] == 16
    assert ledger["metrics"]["contract_only_preflight_ready_cells"] == 12
    assert ledger["metrics"]["support_probe_only_cells"] == 1
    assert ledger["metrics"]["missing_100m_surface_evidence_cells"] == 3


def test_stage9728_symbol_binding_is_python_only_support():
    mod = _load()
    anti_hack = mod.load_json(mod.ANTI_HACK)
    symbol_binding = mod.load_json(mod.SYMBOL_BINDING)
    records = mod.build_symbol_binding_records(anti_hack, symbol_binding)
    by_lang = {row["language_family"]: row for row in records}
    assert by_lang["python"]["status"] == "support_probe_only"
    assert by_lang["python"]["evidence"]
    assert by_lang["rust"]["status"] == "missing_100m_surface_evidence"
    assert by_lang["c_cpp"]["status"] == "missing_100m_surface_evidence"
    assert by_lang["web_js_ts_html"]["status"] == "missing_100m_surface_evidence"


def test_stage9728_multilingual_surfaces_cover_four_languages():
    mod = _load()
    anti_hack = mod.load_json(mod.ANTI_HACK)
    records = mod.build_multilingual_surface_records(anti_hack)
    assert len(records) == 12
    cells = {(row["surface"], row["language_family"], row["status"]) for row in records}
    for surface in {"verifier_repair", "edit_localization", "patch_operator"}:
        for language in {"python", "rust", "c_cpp", "web_js_ts_html"}:
            assert (surface, language, "contract_only_preflight_ready") in cells
