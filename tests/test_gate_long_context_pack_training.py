from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

from gate_long_context_pack_training import build_pack_training_gate  # noqa: E402


def _write_json(path: Path, payload: dict) -> Path:
    path.write_text(json.dumps(payload), encoding='utf-8')
    return path


def test_gate_long_context_pack_training_blocks_independent_eval_for_single_family(tmp_path: Path) -> None:
    overlap = _write_json(tmp_path / 'overlap.json', {'pack_count': 5, 'flagged_pair_count': 10})
    cluster = _write_json(tmp_path / 'cluster.json', {'pack_count': 5, 'largest_cluster_pack_count': 5})
    split = _write_json(tmp_path / 'split.json', {'pack_count': 5, 'cross_split_chunk_jaccard_stats': {'max': 0.55, 'avg': 0.48}})
    card = build_pack_training_gate(
        overlap_summary_path=overlap,
        cluster_summary_path=cluster,
        split_summary_path=split,
    )
    assert card['trainer_policy']['independent_heldout_eval_allowed'] is False
    assert card['trainer_policy']['heldout_eval_blocked'] is True
    assert card['trainer_policy']['recommended_eval_mode'] == 'single_family_no_independent_heldout'


def test_gate_long_context_pack_training_marks_family_aware_mode_for_multi_family_overlap(tmp_path: Path) -> None:
    overlap = _write_json(tmp_path / 'overlap.json', {'pack_count': 13, 'flagged_pair_count': 9})
    cluster = _write_json(tmp_path / 'cluster.json', {'pack_count': 13, 'largest_cluster_pack_count': 7})
    split = _write_json(tmp_path / 'split.json', {'pack_count': 13, 'cross_split_chunk_jaccard_stats': {'max': 0.53, 'avg': 0.49}})
    card = build_pack_training_gate(
        overlap_summary_path=overlap,
        cluster_summary_path=cluster,
        split_summary_path=split,
    )
    assert card['trainer_policy']['trainable_now'] is True
    assert card['trainer_policy']['family_aware_training_required'] is True
    assert card['trainer_policy']['recommended_eval_mode'] == 'family_aware_eval_only'


def test_gate_long_context_pack_training_allows_independent_eval_when_overlap_is_low(tmp_path: Path) -> None:
    overlap = _write_json(tmp_path / 'overlap.json', {'pack_count': 6, 'flagged_pair_count': 0})
    cluster = _write_json(tmp_path / 'cluster.json', {'pack_count': 6, 'largest_cluster_pack_count': 2})
    split = _write_json(tmp_path / 'split.json', {'pack_count': 6, 'cross_split_chunk_jaccard_stats': {'max': 0.12, 'avg': 0.08}})
    card = build_pack_training_gate(
        overlap_summary_path=overlap,
        cluster_summary_path=cluster,
        split_summary_path=split,
    )
    assert card['trainer_policy']['independent_heldout_eval_allowed'] is True
    assert card['trainer_policy']['heldout_eval_blocked'] is False
    assert card['trainer_policy']['recommended_eval_mode'] == 'independent_split_eval'
