from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load():
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root))
    sys.path.insert(0, str(root / "scripts"))
    path = root / "scripts/build_stage9906_geometry_aware_edit_localization_shortcut_audit.py"
    spec = importlib.util.spec_from_file_location("stage9906", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules["stage9906"] = module
    spec.loader.exec_module(module)
    return module


def test_stage9906_option_order_metrics_detect_fixed_kmrtz_order():
    mod = _load()
    rows = [
        {
            "target": {"decoder_text": "M"},
            "input_state": {"candidate_choices": ["option K: a", "option M: b", "option R: c", "option T: d", "option Z: e"]},
        },
        {
            "target": {"decoder_text": "R"},
            "input_state": {"candidate_choices": ["option K: a", "option M: b", "option R: c", "option T: d", "option Z: e"]},
        },
    ]
    metrics = mod.option_order_metrics(rows)
    assert metrics["all_rows_use_fixed_label_order"] is True
    assert metrics["target_position_is_singleton_for_every_label"] is True
    assert metrics["target_position_counts"]["M"] == {1: 1}
    assert metrics["target_position_counts"]["R"] == {2: 1}


def test_stage9906_build_audit_marks_geometry_aware_surface_not_hardened():
    mod = _load()
    audit = mod.build_audit()
    assert audit["passed"] is True
    assert audit["metrics"]["validated_buckets"] == 8
    assert audit["metrics"]["buckets_with_prompt_label_vocab_exposed"] == 8
    assert audit["gate_recommendation"]["same_surface_claim_hardened"] is False
    assert audit["gate_recommendation"]["label_proxy_shortcuts_pass_recommended"] is False
