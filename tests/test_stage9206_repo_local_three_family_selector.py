from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load():
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "scripts"))
    path = root / "scripts/build_stage9206_repo_local_three_family_selector.py"
    spec = importlib.util.spec_from_file_location("stage9206_selector", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_stage8647_adapter_emits_denoise_objective():
    mod = _load()
    rows = [
        {
            "row_id": "d1",
            "semantic_key": "train:x:d1",
            "split": "train",
            "authority": {},
            "clean_state": {"output_repair_action": "REPAIR_INTERNAL_LEAK"},
            "corrupted_state": {
                "language": "python",
                "candidate_surface": "A user-facing maintainer answer candidate exists.",
                "repair_signal": "internal_token_leak_visible",
                "budget": {"decoder_budget_ok": False},
                "bad_output_features": {"verifier_feedback_visible": True},
            },
        }
    ]
    objective = mod.normalize_stage8647_objective_rows(rows)
    judge = mod.normalize_stage8647_judge_rows(rows)
    ranker = mod.normalize_stage8647_ranker_rows(rows)
    assert objective[0]["objective_family"] == "output_repair_denoise"
    assert objective[0]["target"]["label"] == "REPAIR_INTERNAL_LEAK"
    assert judge[0]["anti_cheat"]["target_not_in_input_checked"] is True
    assert ranker[0]["recommended_action"] == "USE_FOR_DENOISE_REPAIR"


def test_selector_requires_three_probe_families():
    mod = _load()
    selected = mod.select_family_bundles(
        [
            {
                "bundle_id": "a",
                "preferred_mode": "structured_policy_probe",
                "bundle_preview": {"materialization_passed": True, "eligible_modes": ["structured_policy_probe"]},
            },
            {
                "bundle_id": "b",
                "preferred_mode": "bounded_decoder_ce_probe",
                "bundle_preview": {"materialization_passed": True, "eligible_modes": ["bounded_decoder_ce_probe"]},
            },
            {
                "bundle_id": "c",
                "preferred_mode": "denoise_repair_probe",
                "bundle_preview": {"materialization_passed": True, "eligible_modes": ["denoise_repair_probe"]},
            },
        ]
    )
    assert {item["preferred_mode"] for item in selected} == {
        "structured_policy_probe",
        "bounded_decoder_ce_probe",
        "denoise_repair_probe",
    }
