from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load():
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "scripts"))
    path = root / "scripts/build_stage9729_multilingual_structured_execution_support_ledger.py"
    spec = importlib.util.spec_from_file_location("stage9729", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_stage9729_surface_audits_match_current_exec_outputs():
    mod = _load()
    verifier = mod.audit_surface("verifier_repair", mod.SURFACES["verifier_repair"])
    edit = mod.audit_surface("edit_localization", mod.SURFACES["edit_localization"])
    patch = mod.audit_surface("patch_operator", mod.SURFACES["patch_operator"])
    assert verifier["passed"] is True
    assert edit["passed"] is True
    assert patch["passed"] is True
    assert verifier["eval_exact"] == 0.25
    assert verifier["strict_exact"] == 0.25
    assert edit["eval_exact"] == 0.0
    assert edit["strict_exact"] == 0.0
    assert patch["eval_exact"] == 0.0
    assert patch["strict_exact"] == 0.0


def test_stage9729_builds_twelve_executed_supporting_cells():
    mod = _load()
    ledger = mod.build_ledger()
    assert ledger["failures"] == []
    assert ledger["metrics"]["records"] == 12
    assert ledger["metrics"]["executed_supporting_evidence_cells"] == 12
    assert ledger["metrics"]["status_counts"] == {"executed_supporting_evidence": 12}


def test_stage9729_records_four_languages_per_surface():
    mod = _load()
    ledger = mod.build_ledger()
    cells = {(row["surface"], row["language_family"], row["status"]) for row in ledger["records"]}
    for surface in {"verifier_repair", "edit_localization", "patch_operator"}:
        for language in {"python", "rust", "c_cpp", "web_js_ts_html"}:
            assert (surface, language, "executed_supporting_evidence") in cells
