#!/usr/bin/env python3
"""Design the candidate-selection repair package after Stage12083."""
from __future__ import annotations

import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = 12087
NAME = 'stage12087_candidate_selection_repair_design'
OUT = ROOT / 'runs/local/artifacts' / NAME
SUMMARY = OUT / 'candidate_selection_repair_design.json'
MIRROR = ROOT / 'runs/summaries' / f'{NAME}.json'
ATLAS = ROOT / 'runs/summaries/stage12086_candidate_selection_regression_atlas.json'
RECORDS = ROOT / 'runs/local/artifacts/stage12086_candidate_selection_regression_atlas/candidate_selection_regression_records.jsonl'


def read_json(path: Path) -> Any:
    return json.loads(path.read_text())


def iter_jsonl(path: Path):
    for line in path.read_text().splitlines():
        if line.strip():
            yield json.loads(line)


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + '\n')


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def top(counter: Counter, n: int = 20) -> list[dict[str, Any]]:
    return [{'key': k, 'count': v} for k, v in counter.most_common(n)]


def bucket(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        'rows': len(rows),
        'by_language': top(Counter(r.get('language_family') for r in rows)),
        'by_subfamily': top(Counter(r.get('subfamily') for r in rows)),
        'by_target_role': top(Counter(r.get('target_role') for r in rows)),
        'by_post_pred_role': top(Counter(r.get('post_pred_role') for r in rows)),
        'by_target_to_post_role': top(Counter((r.get('target_role'), r.get('post_pred_role')) for r in rows)),
    }


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    atlas = read_json(ATLAS)
    records = list(iter_jsonl(RECORDS))
    cand_losses = [r for r in records if r.get('task_type') == 'transition_candidate_selection' and r.get('direction') == 'loss']
    cand_gains = [r for r in records if r.get('task_type') == 'transition_candidate_selection' and r.get('direction') == 'gain']
    next_gains = [r for r in records if r.get('task_type') == 'transition_next_action' and r.get('direction') == 'gain']
    next_losses = [r for r in records if r.get('task_type') == 'transition_next_action' and r.get('direction') == 'loss']

    dominant_loss = Counter((r.get('target_role'), r.get('post_pred_role')) for r in cand_losses).most_common(1)
    loss_to_candidate_surface = [r for r in cand_losses if r.get('post_pred_role') == 'candidate_change_surface']
    rust_inline_losses = [r for r in cand_losses if r.get('post_pred_role') == 'selected_inline_test_anchor']
    verifier_constraint_losses = [
        r for r in cand_losses
        if r.get('target_role') in {'verifier_and_build_constraint', 'verifier_and_test_constraint'}
    ]

    design = {
        'stage': STAGE,
        'stage_name': NAME,
        'created_at_utc': datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00', 'Z'),
        'decision': 'design_candidate_selection_repair_packet_do_not_train_yet',
        'selected_transition_frontier': 'stage11924_transition_listwise_head_only_probe',
        'diagnostic_runtime': 'stage12083_next_action_repair_training_probe',
        'failure_summary': {
            'old_transition_delta': atlas['score_delta']['old_transition_640'],
            'next_action_delta': atlas['score_delta']['transition_next_action'],
            'candidate_selection_delta': atlas['score_delta']['transition_candidate_selection'],
            'candidate_selection_losses': len(cand_losses),
            'candidate_selection_gains': len(cand_gains),
            'next_action_gains': len(next_gains),
            'next_action_losses': len(next_losses),
            'dominant_candidate_selection_loss_shift': dominant_loss[0][0] if dominant_loss else None,
            'dominant_candidate_selection_loss_count': dominant_loss[0][1] if dominant_loss else 0,
        },
        'repair_hypothesis': (
            'Stage12083 learned useful next-action PLAN_PATCH distinctions but damaged the shared candidate-selection '
            'geometry, especially verifier/build candidates that were pulled toward candidate_change_surface. '
            'The repair should replay candidate-selection losses with the Stage12083 wrong role as a hard negative, '
            'while preserving candidate-selection gains and next-action gains.'
        ),
        'materialization_contract': {
            'recommended_stage': 'stage12088_candidate_selection_repair_packet',
            'do_not_train_from_design_only': True,
            'rows_total_target': 160,
            'packet_shape': {
                'candidate_selection_regression_replay': {
                    'rows': 60,
                    'minimum_unique_source_rows': min(len(cand_losses), 24),
                    'primary_sources': 'all Stage12086 candidate-selection losses, cycled only after full coverage',
                    'hard_negative': 'Stage12083 post_pred_role/post_pred_value for the same row',
                    'priority_roles': {
                        'verifier_constraint_losses': len(verifier_constraint_losses),
                        'losses_to_candidate_change_surface': len(loss_to_candidate_surface),
                        'rust_inline_anchor_losses': len(rust_inline_losses),
                    },
                    'purpose': 'Recover candidate-selection rows lost by Stage12083, especially verifier/build-vs-surface cases.',
                },
                'candidate_selection_gain_preservation': {
                    'rows': 25,
                    'minimum_unique_source_rows': min(len(cand_gains), 16),
                    'primary_sources': 'Stage12086 candidate-selection gains',
                    'hard_negative': 'Stage11924 base_pred_role/base_pred_value for the same row',
                    'purpose': 'Avoid undoing genuine candidate-selection gains while repairing losses.',
                },
                'next_action_gain_preservation': {
                    'rows': 45,
                    'minimum_unique_source_rows': min(len(next_gains), 30),
                    'primary_sources': 'Stage12086 next-action gains',
                    'hard_negative': 'Stage11924 wrong base prediction',
                    'purpose': 'Preserve the Stage12083 next-action improvement of 51/160 -> 59/160.',
                },
                'selected_verifier_next_action_preservation': {
                    'rows': 30,
                    'minimum_unique_source_rows': min(len(next_losses), 22),
                    'primary_sources': 'Stage12086 next-action losses with verifier/retrieval targets',
                    'hard_negative': 'Stage12083 wrong post prediction, commonly PLAN_PATCH',
                    'purpose': 'Prevent the repair from repeating Stage12075/12083 selected-verifier overcorrection.',
                },
            },
            'normalization_requirements': [
                'Every row must carry opaque_options and standalone_projection_source.opaque_options.',
                'Every row must retain semantic target value and role metadata.',
                'Every replay row must declare source_row_id and source_stage12086_direction.',
                'No singleton-option rows.',
                'No semantic target value visible before candidates.',
                'Deterministic option shuffle must be asserted or inherited from the source row.',
            ],
            'sampling_rule': (
                'Coverage first, cycling second: cover all 24 candidate-selection losses before duplicating any loss row. '
                'Do not allow next-action preservation rows to exceed 50% of the packet.'
            ),
        },
        'local_audit_contract': {
            'recommended_stage': 'stage12089_candidate_selection_repair_local_audit',
            'training_allowed_before_local_audit': False,
            'pass_conditions': {
                'candidate_selection_losses_covered': f'>={max(1, int(len(cand_losses) * 0.8))}/{len(cand_losses)}',
                'candidate_selection_gains_covered': f'>={max(1, int(len(cand_gains) * 0.75))}/{len(cand_gains)}',
                'next_action_gains_covered': f'>={max(1, int(len(next_gains) * 0.8))}/{len(next_gains)}',
                'next_action_losses_guarded': f'>={max(1, int(len(next_losses) * 0.6))}/{len(next_losses)}',
                'no_target_leak': True,
                'no_option_mirror_missing': True,
                'no_singleton_options': True,
            },
        },
        'postrun_promotion_gate': {
            'old_transition_640': '>364/640 required; >386/640 for Gemma win',
            'transition_next_action': '>=59/160',
            'transition_candidate_selection': '>=89/160',
            'transition_continue_or_stop': '>=128/160',
            'transition_verifier_transition': '>=96/160',
            'protected_filtered_strict': '22/22',
            'protected_filtered_validation': '>=20/22',
            'protected_old_canary_strict': '23/23',
            'protected_old_canary_validation': '>=21/23',
            'residual_bank': '>=7/10',
            'source_heldout_smoke': '>=6/12',
        },
        'buckets': {
            'candidate_selection_losses': bucket(cand_losses),
            'candidate_selection_gains': bucket(cand_gains),
            'next_action_gains': bucket(next_gains),
            'next_action_losses': bucket(next_losses),
        },
        'examples': {
            'candidate_selection_losses': cand_losses[:24],
            'candidate_selection_gains': cand_gains[:16],
            'next_action_gains': next_gains[:20],
            'next_action_losses': next_losses[:20],
        },
        'source_artifacts': {
            'atlas': rel(ATLAS),
            'records': rel(RECORDS),
        },
        'outputs': {
            'summary': rel(SUMMARY),
            'summary_mirror': rel(MIRROR),
        },
    }
    write_json(SUMMARY, design)
    write_json(MIRROR, design)
    print(json.dumps(design, indent=2, sort_keys=True))


if __name__ == '__main__':
    main()
