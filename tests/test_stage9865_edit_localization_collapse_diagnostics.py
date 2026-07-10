from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load():
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "scripts"))
    path = root / "scripts/build_stage9865_edit_localization_collapse_diagnostics.py"
    spec = importlib.util.spec_from_file_location("stage9865", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_option_position_stats_detects_fixed_slot_binding():
    mod = _load()
    rows = [
        {"split": "train", "language_family": "python", "target": {"edit_localization": "A"}, "input_state": {"candidate_choices": ["option A: x", "option B: y", "option C: z", "option D: q", "option E: w"]}},
        {"split": "train", "language_family": "python", "target": {"edit_localization": "B"}, "input_state": {"candidate_choices": ["option A: x", "option B: y", "option C: z", "option D: q", "option E: w"]}},
    ]
    stats = mod.option_position_stats(rows)
    assert stats["all_rows_use_fixed_alphabetical_option_order"] is True
    assert stats["target_position_is_singleton_for_every_label"] is True
    assert stats["target_position_counts"]["A"] == {0: 1}
    assert stats["target_position_counts"]["B"] == {1: 1}


def test_build_position_debiased_rows_spreads_target_positions():
    mod = _load()
    rows = []
    for i in range(10):
        rows.append({
            "row_id": f"row-{i}",
            "target": {"edit_localization": "A"},
            "input_state": {"candidate_choices": ["option A: x", "option B: y", "option C: z", "option D: q", "option E: w"]},
        })
    out_rows, card = mod.build_position_debiased_rows(rows)
    assert len(out_rows) == 10
    assert card["every_label_spans_multiple_positions"] is True
    assert len(card["target_position_counts"]["A"]) > 1


def test_logit_stats_detects_full_single_label_collapse():
    mod = _load()
    stats = mod.logit_stats([
        {"target": "A", "pred": "A", "confidence": 0.2, "margin": 0.01, "top1_logit": 0.7, "top2_label": "B"},
        {"target": "B", "pred": "A", "confidence": 0.2, "margin": 0.01, "top1_logit": 0.7, "top2_label": "B"},
    ])
    assert stats["all_rows_predicted_as_single_label"] is True
    assert stats["all_rows_predicted_as_A"] is True
    assert stats["dominant_predicted_label"] == "A"
    assert stats["pred_counts"] == {"A": 2}
