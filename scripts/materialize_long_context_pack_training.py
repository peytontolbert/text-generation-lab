from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from long_context_common import read_jsonl, write_json, write_jsonl


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding='utf-8'))


def build_long_context_pack_trainer_rows(
    *,
    training_rows_path: Path,
    split_assignments_path: Path,
    cluster_summary_path: Path,
    gate_path: Path,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    training_rows = read_jsonl(training_rows_path)
    split_assignments = read_jsonl(split_assignments_path)
    cluster_summary = _read_json(cluster_summary_path)
    gate = _read_json(gate_path)

    training_row_by_pack = {str(row.get('pack_id') or ''): row for row in training_rows}
    split_by_pack = {str(row.get('pack_id') or ''): row for row in split_assignments}

    family_by_pack: dict[str, dict[str, Any]] = {}
    for family in cluster_summary.get('clusters', []):
        family_id = str(family.get('cluster_id') or '')
        for pack_id in family.get('pack_ids', []):
            family_by_pack[str(pack_id)] = {
                'overlap_family_id': family_id,
                'family_pack_count': int(family.get('pack_count') or 0),
                'family_token_count': int(family.get('cluster_token_count') or 0),
                'family_chunk_union_count': int(family.get('cluster_chunk_union_count') or 0),
            }

    trainer_policy = gate.get('trainer_policy') or {}
    recommended_training_mode = str(trainer_policy.get('recommended_training_mode') or 'standard_pack_training')
    independent_eval_allowed = bool(trainer_policy.get('independent_heldout_eval_allowed') is True)
    family_aware_required = bool(trainer_policy.get('family_aware_training_required') is True)

    trainer_rows: list[dict[str, Any]] = []
    missing_training_rows: list[str] = []
    missing_split_assignments: list[str] = []
    for pack_id, split_row in split_by_pack.items():
        training_row = training_row_by_pack.get(pack_id)
        if training_row is None:
            missing_training_rows.append(pack_id)
            continue
        family = family_by_pack.get(pack_id)
        if family is None:
            missing_split_assignments.append(pack_id)
            continue
        requested_split = str(split_row.get('split') or 'train')
        if recommended_training_mode == 'standard_pack_training' and independent_eval_allowed:
            effective_split = requested_split
        else:
            effective_split = 'train'
        trainer_rows.append(
            {
                'row_id': f'longctx::{pack_id}',
                'pack_id': pack_id,
                'requested_split': requested_split,
                'effective_split': effective_split,
                'eval_eligible': bool(independent_eval_allowed and effective_split != 'train'),
                'trainer_policy_mode': recommended_training_mode,
                'family_aware_training_required': family_aware_required,
                'independent_heldout_eval_allowed': independent_eval_allowed,
                'overlap_family_id': family['overlap_family_id'],
                'family_pack_count': family['family_pack_count'],
                'family_token_count': family['family_token_count'],
                'family_chunk_union_count': family['family_chunk_union_count'],
                'prompt_text': str(training_row.get('prompt_text') or ''),
                'context_rows': list(training_row.get('context_rows') or []),
                'target_rows': list(training_row.get('target_rows') or []),
                'pack_token_count': int(training_row.get('pack_token_count') or 0),
                'chunk_count': int(training_row.get('chunk_count') or 0),
                'candidate_count': int(training_row.get('candidate_count') or 0),
            }
        )

    trainer_rows.sort(key=lambda row: (row['effective_split'], row['pack_token_count'], row['pack_id']), reverse=True)
    split_counts: dict[str, int] = {}
    family_counts: dict[str, int] = {}
    eval_eligible_count = 0
    for row in trainer_rows:
        split = str(row.get('effective_split') or 'train')
        split_counts[split] = split_counts.get(split, 0) + 1
        family_id = str(row.get('overlap_family_id') or '')
        family_counts[family_id] = family_counts.get(family_id, 0) + 1
        if row.get('eval_eligible') is True:
            eval_eligible_count += 1
    audit = {
        'trainer_rows': len(trainer_rows),
        'missing_training_rows': len(missing_training_rows),
        'missing_training_row_examples': missing_training_rows[:25],
        'missing_family_assignments': len(missing_split_assignments),
        'missing_family_assignment_examples': missing_split_assignments[:25],
        'recommended_training_mode': recommended_training_mode,
        'independent_heldout_eval_allowed': independent_eval_allowed,
        'family_aware_training_required': family_aware_required,
        'effective_split_counts': dict(sorted(split_counts.items())),
        'overlap_family_counts': dict(sorted(family_counts.items())),
        'eval_eligible_rows': eval_eligible_count,
    }
    return trainer_rows, audit


def materialize_long_context_pack_training(
    *,
    training_rows_path: Path,
    split_assignments_path: Path,
    cluster_summary_path: Path,
    gate_path: Path,
    output_dir: Path,
) -> dict[str, Any]:
    trainer_rows, audit = build_long_context_pack_trainer_rows(
        training_rows_path=training_rows_path,
        split_assignments_path=split_assignments_path,
        cluster_summary_path=cluster_summary_path,
        gate_path=gate_path,
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    trainer_rows_path = output_dir / 'trainer_rows.jsonl'
    trainer_audit_path = output_dir / 'trainer_audit.json'
    trainer_input_path = output_dir / 'trainer_input.json'
    write_jsonl(trainer_rows_path, trainer_rows)
    write_json(trainer_audit_path, audit)
    write_json(
        trainer_input_path,
        {
            'trainer_rows_path': str(trainer_rows_path),
            'trainer_audit_path': str(trainer_audit_path),
            'trainer_row_count': len(trainer_rows),
            'recommended_training_mode': audit['recommended_training_mode'],
            'independent_heldout_eval_allowed': audit['independent_heldout_eval_allowed'],
            'effective_split_counts': audit['effective_split_counts'],
        },
    )
    return {
        'passed': audit['missing_training_rows'] == 0 and audit['missing_family_assignments'] == 0,
        'trainer_rows_path': str(trainer_rows_path),
        'trainer_audit_path': str(trainer_audit_path),
        'trainer_input_path': str(trainer_input_path),
        'trainer_audit': audit,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description='Materialize trainer rows for long-context candidate packs using overlap-family gate policy.')
    parser.add_argument('--training-rows', type=Path, required=True)
    parser.add_argument('--split-assignments', type=Path, required=True)
    parser.add_argument('--cluster-summary', type=Path, required=True)
    parser.add_argument('--gate', type=Path, required=True)
    parser.add_argument('--output-dir', type=Path, required=True)
    args = parser.parse_args()
    result = materialize_long_context_pack_training(
        training_rows_path=args.training_rows,
        split_assignments_path=args.split_assignments,
        cluster_summary_path=args.cluster_summary,
        gate_path=args.gate,
        output_dir=args.output_dir,
    )
    write_json(args.output_dir / 'materialization_result.json', result)


if __name__ == '__main__':
    main()
