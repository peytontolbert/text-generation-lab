#!/usr/bin/env python3
"""Record decision for Stage12091 candidate-selection repair training."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = 12093
NAME = 'stage12093_candidate_selection_repair_training_decision'
OUT = ROOT / 'runs/local/artifacts' / NAME
SUMMARY = OUT / 'candidate_selection_repair_training_decision.json'
MIRROR = ROOT / 'runs/summaries' / f'{NAME}.json'
AUDIT = ROOT / 'runs/summaries/stage12092_candidate_selection_repair_training_postrun_audit.json'


def read_json(path: Path) -> Any:
    return json.loads(path.read_text())


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + '\n')


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    audit = read_json(AUDIT)
    stage11924 = audit['results']['stage11924_transition_listwise_head_only']
    stage12083 = audit['results']['stage12083_next_action_repair_training']
    stage12091 = audit['results']['stage12091_candidate_selection_repair_training']
    summary = {
        'stage': STAGE,
        'stage_name': NAME,
        'created_at_utc': datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00', 'Z'),
        'decision': 'reject_stage12091_keep_stage11924_selected_transition_frontier',
        'selected_transition_frontier': {
            'stage': 'stage11924_transition_listwise_head_only_probe',
            'runtime': 'runs/local/artifacts/stage11924_transition_listwise_head_only_probe/runtime_model/runtime_model_bundle.json',
            'scorer': 'encoder_option_retrieval_semantic_candidate_head',
            'transition_projection_score': stage11924['transition_projection_routed'],
            'by_task': stage11924['transition_by_task'],
        },
        'diagnostic_result': {
            'stage12083': {
                'status': 'diagnostic_next_action_lane_gain_no_total_gain',
                'transition_projection_score': stage12083['transition_projection_routed'],
                'by_task': stage12083['transition_by_task'],
            },
            'stage12091': {
                'status': 'rejected_candidate_selection_repair_regressed_total_and_next_action',
                'transition_projection_score': stage12091['transition_projection_routed'],
                'by_task': stage12091['transition_by_task'],
            },
        },
        'why_rejected': [
            'old transition projection dropped from 364/640 to 355/640',
            'next_action dropped from Stage12083 59/160 to 49/160',
            'candidate_selection only reached 82/160, still below Stage11924 baseline 89/160',
            'Gemma same-manifest target remains 386/640',
        ],
        'what_was_preserved': {
            'filtered_strict': audit['gates']['filtered_strict_preserved'],
            'old_canary_strict': audit['gates']['old_canary_strict_preserved'],
            'filtered_validation': audit['gates']['filtered_validation_preserved'],
            'old_canary_validation': audit['gates']['old_canary_validation_preserved'],
            'residual_bank': audit['gates']['residual_preserved'],
            'source_heldout_smoke': audit['gates']['smoke_preserved'],
        },
        'lesson': (
            'Coverage of the Stage12086 loss/gain rows was not sufficient. The shared task_balanced head-only objective still interferes: '
            'candidate-selection repair rows pull against evidence-citation next-action preservation, and the combined packet overcorrects both.'
        ),
        'recommended_next_stage': {
            'name': 'stage12094_separate_head_or_two_phase_candidate_next_action_ablation_design',
            'do_not_launch_more_same_objective_training': True,
            'hypotheses_to_test': [
                'candidate_selection repair requires scorer-head-only training on candidate_selection rows first, then next_action preservation as a second phase',
                'next_action and candidate_selection need separate routed heads or separate loss weights, not one shared semantic candidate head update',
                'evidence-citation selected-verifier next_action rows should be frozen/replayed with stronger preservation before patch-impact positives',
            ],
            'minimum_gate': {
                'old_transition_640': '>364',
                'transition_next_action': '>=59',
                'transition_candidate_selection': '>=89',
                'protected_gates': 'preserved',
            },
        },
        'source_artifacts': {
            'stage12092_audit': rel(AUDIT),
        },
        'outputs': {
            'summary': rel(SUMMARY),
            'summary_mirror': rel(MIRROR),
        },
    }
    write_json(SUMMARY, summary)
    write_json(MIRROR, summary)
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == '__main__':
    main()
