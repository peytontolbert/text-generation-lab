from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load():
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "scripts"))
    path = root / "scripts/build_stage9853_attach_abstention_curriculum_to_review_packets_and_bridge.py"
    spec = importlib.util.spec_from_file_location("stage9853", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_stage9853_build_training_direction_bridge_supports_objective_shift():
    mod = _load()
    bridge = mod.build_training_direction_bridge(
        {
            "passed": True,
            "wins_100m": 0,
            "wins_gemma": 3,
            "macro_delta_by_split": {"eval": -0.25, "strict_eval": -0.25},
            "hundred_m": {
                "by_bucket": {f"{lang}:strict_eval": {"exact": 0.0} for lang in mod.LANGS},
            },
        },
        {"metrics": {"target_label_counts": {"ABSTAIN_INSUFFICIENT_EVIDENCE": 20}}},
        {
            "passed": True,
            "eval": {
                "eval": {"field_exact": {"edit_localization": {"exact": 1.0}}},
                "strict_eval": {"field_exact": {"edit_localization": {"exact": 0.5}}},
            },
        },
        {
            "passed": True,
            "wins_100m": 3,
            "wins_gemma": 1,
            "macro_delta_by_split": {"eval": 0.0, "strict_eval": 0.25},
            "hundred_m": {
                "by_bucket": {f"{lang}:strict_eval": {"exact": 0.5} for lang in mod.LANGS},
            },
            "gemma": {
                "by_bucket": {f"{lang}:strict_eval": {"exact": 0.0} for lang in mod.LANGS},
            },
            "comparisons": {f"{lang}:strict_eval": {"verdict": "100m_win"} for lang in mod.LANGS},
        },
    )
    assert bridge["passed"] is True
    assert bridge["metrics"]["strict_macro_delta_improvement"] == 0.5
    assert bridge["metrics"]["abstention_target_rows"] == 20
    assert bridge["metrics"]["objective_shift_supported"] is True


def test_stage9853_label_proxy_patch_stays_provisional():
    mod = _load()
    bridge = {
        "metrics": {
            "abstention_eval_exact_100m": 1.0,
            "abstention_strict_exact_100m": 0.5,
            "abstention_target_rows": 20,
        },
        "records": [
            {
                "language_family": "python",
                "forced_label_strict_exact_100m": 0.0,
                "abstention_strict_exact_100m": 0.5,
                "abstention_strict_exact_gemma": 1.0,
                "strict_verdict": "gemma_win",
            }
        ],
    }
    patch = mod._challenge_patch("label_proxy_shortcuts", "python", bridge)
    assert patch["cell_specific_card_present"] is True
    assert patch["passed"] is False
    assert "forced-label 0.0" in patch["notes"][0]
