from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from training_telemetry_metrics import (
    high_confidence_wrong_rows,
    margin_confidence_entropy,
    row_field_telemetry,
    summarize_failure_buckets,
    token_loss_map,
)


def test_margin_confidence_entropy_identifies_prediction_and_correctness() -> None:
    card = margin_confidence_entropy([0.0, 4.0, 1.0], label=1)
    assert card["predicted_index"] == 1
    assert card["correct"] is True
    assert card["confidence"] > 0.9
    assert card["margin"] > 0.8
    assert card["entropy"] < 0.4


def test_row_field_telemetry_maps_logits_to_labels() -> None:
    card = row_field_telemetry("r1", "build_mode", [0.1, 2.0], ["IMPORT", "BUILD"], "BUILD")
    assert card["predicted_label"] == "BUILD"
    assert card["correct"] is True


def test_high_confidence_wrong_rows_filters_only_dangerous_errors() -> None:
    rows = [
        {"row_id": "a", "correct": False, "confidence": 0.95},
        {"row_id": "b", "correct": False, "confidence": 0.40},
        {"row_id": "c", "correct": True, "confidence": 0.99},
    ]
    assert [row["row_id"] for row in high_confidence_wrong_rows(rows)] == ["a"]


def test_token_loss_map_preserves_positions() -> None:
    card = token_loss_map("r1", [10, 11], [0.25, 1.5], token_texts=["def", "bad"])
    assert card["token_count"] == 2
    assert card["max_loss"] == 1.5
    assert card["positions"][1]["token_text"] == "bad"


def test_failure_bucket_summary_prioritizes_leak_and_short_output() -> None:
    rows = [
        {"internal_leak": True, "correct": False, "confidence": 0.99},
        {"short_output": True, "correct": False, "confidence": 0.2},
        {"correct": False, "confidence": 0.9},
        {"correct": True, "confidence": 0.9},
    ]
    assert summarize_failure_buckets(rows) == {
        "internal_leak": 1,
        "short_output": 1,
        "high_confidence_wrong": 1,
        "ok": 1,
    }
