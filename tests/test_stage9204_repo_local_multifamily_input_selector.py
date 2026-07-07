from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load():
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / 'scripts'))
    path = root / "scripts/build_stage9204_repo_local_multifamily_input_selector.py"
    spec = importlib.util.spec_from_file_location("stage9204_selector", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_stage8592_adapter_preserves_bounded_decoder_route():
    mod = _load()
    rows = [
        {
            "row_id": "row1",
            "route": "KEEP_BOUNDED_DECODER",
            "decode_allowed": True,
            "decoder_budget_ok": True,
            "decoder_token_len": 128,
            "language_family": "python",
            "surface": "PATCH_HUNK_ARGS",
            "input_state": {"evidence_state": "direct_present", "operator_surface": "PATCH_HUNK_ARGS"},
            "target": {"target_ref": "target_ref::row1", "target_shape": "PATCH_HUNK_ARGS"},
            "authority": {},
        }
    ]
    objective = mod.normalize_stage8592_objective_rows(rows)
    judge = mod.normalize_stage8592_judge_rows(rows)
    ranker = mod.normalize_stage8592_ranker_rows(rows)
    assert objective[0]["objective_family"] == "bounded_decoder_ce"
    assert objective[0]["target_length_bucket"] == "bounded"
    assert judge[0]["anti_cheat"]["target_not_in_input_checked"] is True
    assert ranker[0]["recommended_action"] == "KEEP_BOUNDED_DECODER"


def test_family_selector_requires_preferred_mode():
    mod = _load()
    selected = mod.select_family_bundles(
        [
            {
                "bundle_id": "ok",
                "preferred_mode": "bounded_decoder_ce_probe",
                "bundle_preview": {"materialization_passed": True, "eligible_modes": ["bounded_decoder_ce_probe"]},
            },
            {
                "bundle_id": "skip",
                "preferred_mode": "denoise_repair_probe",
                "bundle_preview": {"materialization_passed": True, "eligible_modes": ["structured_policy_probe"]},
            },
        ]
    )
    assert [item["bundle_id"] for item in selected] == ["ok"]
