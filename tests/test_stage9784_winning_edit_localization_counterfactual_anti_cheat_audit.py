from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load():
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "scripts"))
    path = root / "scripts/build_stage9784_winning_edit_localization_counterfactual_anti_cheat_audit.py"
    spec = importlib.util.spec_from_file_location("stage9784", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_stage9784_builds_four_winning_edit_localization_cards_with_stubbed_probes():
    mod = _load()
    built = mod.build_audit(generate_fn=lambda prompt: "TARGET_FILE")
    assert built["passed"] is True
    assert built["metrics"]["validated_cells"] == 4
    assert built["metrics"]["100m_raw_output_rows_present"] == 4
    assert built["metrics"]["same_surface_live_gemma_rows_present"] == 4

    python_card = next(row for row in built["records"] if row["language_family"] == "python")
    assert python_card["state_hash"] == "174f1f24aefe3e7405178393af9f1a59be0575330632067f85c1c6c3502af436"
    assert python_card["manifest_hash"] == "4f6560c4ee7f92861f2c7f5cde1c689af724097883fde3a362ced16f0fa4f115"
    assert len(python_card["raw_100m_outputs"]) == 5
    assert len(python_card["raw_gemma_outputs"]) == 5
    assert set(python_card["counterfactual_probes"].keys()) == {
        "label_order_permutation",
        "decoy_label_injection",
        "critical_evidence_ablation",
        "causal_flip",
    }
    assert set(python_card["shallow_baselines"].keys()) == {"majority_label", "first_label", "metadata_only"}
    assert python_card["expert_reviewer_judgment"]["review_status"] == "pending_human_confirmation"
