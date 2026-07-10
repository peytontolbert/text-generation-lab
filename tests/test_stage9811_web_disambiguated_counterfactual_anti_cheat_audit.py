from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load():
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "scripts"))
    path = root / "scripts/build_stage9811_web_disambiguated_counterfactual_anti_cheat_audit.py"
    spec = importlib.util.spec_from_file_location("stage9811", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_stage9811_builds_web_disambiguated_cards_with_stubbed_probes():
    mod = _load()
    built = mod.build_audit(generate_fn=lambda prompt: "A")
    assert built["passed"] is True
    assert built["metrics"]["validated_cells"] == 4
    assert built["metrics"]["100m_raw_output_rows_present"] == 4
    assert built["metrics"]["same_surface_live_gemma_rows_present"] == 4
    assert built["metrics"]["prompt_target_literal_row_count"] == 0
    assert built["metrics"]["prompt_hidden_target_literal_row_count"] == 0
    assert built["metrics"]["stable_choice_mapping_language_count"] == 4

    python_card = next(row for row in built["records"] if row["language_family"] == "python")
    assert python_card["comparison_summary"]["model_strict_exact_100m"] == 0.4
    assert python_card["comparison_summary"]["gemma_strict_exact"] == 0.2
    assert python_card["comparison_summary"]["verdict"] == "100m_better"
    assert python_card["mapping_stability"]["stable_across_splits"] is True
    assert set(python_card["counterfactual_probes"].keys()) == {
        "label_order_permutation",
        "decoy_label_injection",
        "critical_evidence_ablation",
        "causal_flip",
    }
