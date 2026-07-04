from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from cluster_slice_near_duplicate_detector import detect_clusters


def test_detector_finds_exact_duplicate_cluster() -> None:
    row = {"row_id": "a", "split": "train", "clean_state": {"action": "X"}}
    card = detect_clusters([row, dict(row, row_id="b")])
    assert card["metrics"]["semantic_duplicate_clusters"] >= 1


def test_detector_finds_semantic_split_overlap() -> None:
    rows = [
        {"row_id": "a", "split": "train", "semantic_key": "same", "clean_state": {"action": "X"}},
        {"row_id": "b", "split": "eval", "semantic_key": "same", "clean_state": {"action": "X"}},
    ]
    card = detect_clusters(rows)
    assert card["metrics"]["semantic_split_overlap_clusters"] == 1


def test_detector_finds_near_duplicate_pair() -> None:
    rows = [
        {"row_id": "a", "split": "train", "encoder_text": "alpha beta gamma delta epsilon zeta"},
        {"row_id": "b", "split": "train", "encoder_text": "alpha beta gamma delta epsilon zeta"},
    ]
    card = detect_clusters(rows, near_duplicate_threshold=0.9)
    assert card["metrics"]["near_duplicate_pairs"] == 1


def test_detector_reports_undercovered_slices() -> None:
    rows = [
        {"row_id": "a", "objective_family": "x", "split": "train", "clean_state": {"binding_action": "A"}, "graph_input": {"query_kind": "q"}},
        {"row_id": "b", "objective_family": "x", "split": "train", "clean_state": {"binding_action": "B"}, "graph_input": {"query_kind": "q"}},
    ]
    card = detect_clusters(rows)
    assert card["metrics"]["undercovered_slices"] == 2
