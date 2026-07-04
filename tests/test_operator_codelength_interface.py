from __future__ import annotations

import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from operator_codelength_interface import codelength_card, codelength_for_choice, normalize_probs, operator_inventory


def test_operator_inventory_includes_probabilistic_and_memory_layers() -> None:
    card = operator_inventory()
    assert card["operator_count"] >= 80
    assert card["categories"]["probabilistic_compression"] >= 6
    assert card["categories"]["memory_learning"] >= 5
    assert all(row["authority"]["training"] is False for row in card["operators"])


def test_normalize_probs_falls_back_to_uniform_for_zero_mass() -> None:
    assert normalize_probs([0.0, 0.0]) == [0.5, 0.5]


def test_codelength_for_choice_reports_bits_and_correctness() -> None:
    card = codelength_for_choice([0.1, 0.8, 0.1], 1)
    assert card["correct"] is True
    assert math.isclose(card["uniform_bits"], math.log2(3))
    assert card["model_nll_bits"] < card["uniform_bits"]
    assert card["compression_gain_bits"] > 0


def test_codelength_card_aggregates_exact_and_bits() -> None:
    card = codelength_card([
        {"row_id": "a", "probabilities": [0.8, 0.2], "target_index": 0},
        {"row_id": "b", "probabilities": [0.8, 0.2], "target_index": 1},
    ])
    assert card["rows"] == 2
    assert card["exact"] == 0.5
    assert card["uniform_bits"] == 2.0
    assert card["model_nll_bits"] > 0.0
    assert card["authority"]["model_execution"] is False
