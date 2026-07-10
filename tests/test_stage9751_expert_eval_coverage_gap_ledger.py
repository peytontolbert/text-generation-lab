from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load():
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "scripts"))
    path = root / "scripts/build_stage9751_expert_eval_coverage_gap_ledger.py"
    spec = importlib.util.spec_from_file_location("stage9751", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_stage9751_reports_eval_coverage_gaps_without_faking_readiness():
    mod = _load()
    ledger = mod.build_gap_ledger(
        mod.load_json(mod.CONTRACT),
        mod.load_json(mod.ANTI_HACK),
        mod.load_json(mod.ACCEPTANCE_LEDGER),
        mod.load_json(mod.TRUTHFUL_SUPPORT),
        mod.load_json(mod.RUNBOOK),
    )
    metrics = ledger["metrics"]
    assert ledger["failures"] == []
    assert metrics["records"] == 72
    assert metrics["supported_standalone_cells"] == 13
    assert metrics["cells_with_expert_rubric_attached"] == 0
    assert metrics["cells_with_anti_cheat_cards_attached"] == 0
    assert metrics["supported_standalone_cells_missing_expert_rubric"] == 13
    assert metrics["supported_standalone_cells_missing_anti_cheat_cards"] == 13
    assert metrics["supported_standalone_cells_missing_gemma_comparison"] == 13
    assert metrics["supported_standalone_cells_missing_checkpoint_hash"] == 13
    assert metrics["languages_with_any_truthful_support"] == ["c_cpp", "python", "rust", "web_js_ts_html"]
    assert metrics["supported_skill_coverage_by_language"] == {
        "c_cpp": 3,
        "python": 4,
        "rust": 3,
        "web_js_ts_html": 3,
    }
    assert metrics["languages_with_full_9_skill_support"] == []
    python_missing = metrics["missing_skills_by_language"]["python"]
    assert "symbol_binding" not in python_missing
    assert len(python_missing) == 5
