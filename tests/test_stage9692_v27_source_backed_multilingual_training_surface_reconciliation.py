from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load():
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "scripts"))
    path = root / "scripts/build_stage9692_v27_source_backed_multilingual_training_surface_reconciliation.py"
    spec = importlib.util.spec_from_file_location("stage9692", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def _locked_suite():
    skills = [
        "intent_to_build_strategy",
        "repo_state_graph_navigation",
        "symbol_binding",
        "edit_localization",
        "patch_operator_selection",
        "bounded_argument_rendering",
        "verifier_expectation",
        "verifier_failure_repair_or_abstain",
        "final_user_facing_summary",
    ]
    packs = []
    for mode in ["standalone_100m_weights", "full_product_harness"]:
        for language in ["python", "rust", "c_cpp", "web_js_ts_html"]:
            for skill in skills:
                packs.append({"mode": mode, "language_family": language, "skill_area": skill})
    return {"benchmark_packs": packs}


def test_gap_matrix_separates_refresh_ready_from_missing_objectives():
    mod = _load()
    gap, failures = mod.build_gap_matrix(_locked_suite())
    assert failures == []
    assert gap["locked_eval_cells"] == 72
    assert set(gap["ready_for_locked_guard_refresh_skills"]) == {
        "symbol_binding",
        "edit_localization",
        "patch_operator_selection",
        "bounded_argument_rendering",
        "verifier_failure_repair_or_abstain",
    }
    assert set(gap["needs_new_objective_skills"]) == {
        "intent_to_build_strategy",
        "repo_state_graph_navigation",
        "verifier_expectation",
        "final_user_facing_summary",
    }
    assert all(record["train_authority_open"] is False for record in gap["skill_records"])
    assert gap["language_counts"] == {"c_cpp": 18, "python": 18, "rust": 18, "web_js_ts_html": 18}
