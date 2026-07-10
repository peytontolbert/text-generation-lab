from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from long_context_common import write_json


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding='utf-8'))


def build_pack_training_gate(
    *,
    overlap_summary_path: Path,
    cluster_summary_path: Path,
    split_summary_path: Path,
    max_cross_split_jaccard_for_independent_eval: float = 0.25,
    max_pack_fraction_in_largest_family_for_independent_eval: float = 0.5,
) -> dict[str, Any]:
    overlap_summary = _read_json(overlap_summary_path)
    cluster_summary = _read_json(cluster_summary_path)
    split_summary = _read_json(split_summary_path)

    pack_count = int(cluster_summary.get('pack_count') or overlap_summary.get('pack_count') or split_summary.get('pack_count') or 0)
    largest_cluster_pack_count = int(cluster_summary.get('largest_cluster_pack_count') or 0)
    largest_family_fraction = (largest_cluster_pack_count / pack_count) if pack_count else 0.0
    cross_split_stats = split_summary.get('cross_split_chunk_jaccard_stats') or {}
    max_cross_split_jaccard = float(cross_split_stats.get('max') or 0.0)
    avg_cross_split_jaccard = float(cross_split_stats.get('avg') or 0.0)
    flagged_pair_count = int(overlap_summary.get('flagged_pair_count') or 0)

    independent_eval_allowed = (
        max_cross_split_jaccard <= max_cross_split_jaccard_for_independent_eval
        and largest_family_fraction <= max_pack_fraction_in_largest_family_for_independent_eval
    )
    family_aware_training_required = largest_cluster_pack_count > 1 or flagged_pair_count > 0
    heldout_eval_blocked = not independent_eval_allowed
    trainable_now = pack_count > 0

    checks = {
        'pack_count_positive': pack_count > 0,
        'cross_split_jaccard_within_independent_eval_limit': max_cross_split_jaccard <= max_cross_split_jaccard_for_independent_eval,
        'largest_family_fraction_within_independent_eval_limit': largest_family_fraction <= max_pack_fraction_in_largest_family_for_independent_eval,
    }

    if independent_eval_allowed:
        trainer_policy = {
            'trainable_now': trainable_now,
            'family_aware_training_required': family_aware_training_required,
            'independent_heldout_eval_allowed': True,
            'heldout_eval_blocked': False,
            'recommended_eval_mode': 'independent_split_eval',
            'recommended_training_mode': 'standard_pack_training',
        }
        decision = 'Pack overlap is low enough to permit independent heldout evaluation.'
    elif largest_cluster_pack_count == pack_count and pack_count > 0:
        trainer_policy = {
            'trainable_now': trainable_now,
            'family_aware_training_required': True,
            'independent_heldout_eval_allowed': False,
            'heldout_eval_blocked': True,
            'recommended_eval_mode': 'single_family_no_independent_heldout',
            'recommended_training_mode': 'single_family_train_only_or_more_mining_required',
        }
        decision = 'All packs fall into one overlap family, so independent heldout evaluation is blocked.'
    else:
        trainer_policy = {
            'trainable_now': trainable_now,
            'family_aware_training_required': True,
            'independent_heldout_eval_allowed': False,
            'heldout_eval_blocked': True,
            'recommended_eval_mode': 'family_aware_eval_only',
            'recommended_training_mode': 'family_cluster_constrained_training',
        }
        decision = 'Packs are trainable, but overlap families cross split boundaries, so only family-aware evaluation is allowed.'

    return {
        'passed': True,
        'inputs': {
            'overlap_summary_path': str(overlap_summary_path),
            'cluster_summary_path': str(cluster_summary_path),
            'split_summary_path': str(split_summary_path),
        },
        'checks': checks,
        'metrics': {
            'pack_count': pack_count,
            'flagged_pair_count': flagged_pair_count,
            'largest_cluster_pack_count': largest_cluster_pack_count,
            'largest_family_fraction': largest_family_fraction,
            'max_cross_split_jaccard': max_cross_split_jaccard,
            'avg_cross_split_jaccard': avg_cross_split_jaccard,
        },
        'thresholds': {
            'max_cross_split_jaccard_for_independent_eval': max_cross_split_jaccard_for_independent_eval,
            'max_pack_fraction_in_largest_family_for_independent_eval': max_pack_fraction_in_largest_family_for_independent_eval,
        },
        'trainer_policy': trainer_policy,
        'decision': decision,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description='Gate long-context pack training and evaluation using overlap-family diagnostics.')
    parser.add_argument('--overlap-summary', type=Path, required=True)
    parser.add_argument('--cluster-summary', type=Path, required=True)
    parser.add_argument('--split-summary', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--max-cross-split-jaccard-for-independent-eval', type=float, default=0.25)
    parser.add_argument('--max-pack-fraction-in-largest-family-for-independent-eval', type=float, default=0.5)
    args = parser.parse_args()
    card = build_pack_training_gate(
        overlap_summary_path=args.overlap_summary,
        cluster_summary_path=args.cluster_summary,
        split_summary_path=args.split_summary,
        max_cross_split_jaccard_for_independent_eval=args.max_cross_split_jaccard_for_independent_eval,
        max_pack_fraction_in_largest_family_for_independent_eval=args.max_pack_fraction_in_largest_family_for_independent_eval,
    )
    write_json(args.output, card)


if __name__ == '__main__':
    main()
