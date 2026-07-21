#!/usr/bin/env python3
"""Record decision for Stage12096 candidate-head-only diagnostic."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = 12098
NAME = 'stage12098_candidate_head_only_decision'
OUT = ROOT / 'runs/local/artifacts' / NAME
SUMMARY = OUT / 'candidate_head_only_decision.json'
MIRROR = ROOT / 'runs/summaries' / f'{NAME}.json'
AUDIT = ROOT / 'runs/summaries/stage12097_candidate_head_only_candidate_selection_postrun_audit.json'
DESIGN = ROOT / 'runs/summaries/stage12094_separate_head_or_two_phase_candidate_next_action_ablation_design.json'


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
    design = read_json(DESIGN)
    stage11924 = audit['selected_transition_frontier_remains']
    composite = audit['results']['stage12096_candidate_head_only_candidate_selection']['transition::semantic_plus_transition_candidate_head']
    composite_tasks = audit['results']['stage12096_candidate_head_only_candidate_selection']['transition_by_task::semantic_plus_transition_candidate_head']
    pure = audit['results']['stage12096_candidate_head_only_candidate_selection']['transition::transition_candidate_head']
    pure_tasks = audit['results']['stage12096_candidate_head_only_candidate_selection']['transition_by_task::transition_candidate_head']
    summary = {
        'stage': STAGE,
        'stage_name': NAME,
        'created_at_utc': datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00', 'Z'),
        'decision': 'reject_stage12096_keep_stage11924_selected_transition_frontier',
        'selected_transition_frontier': stage11924,
        'diagnostic_findings': {
            'pure_transition_candidate_head': {
                'score': pure,
                'by_task': pure_tasks,
                'interpretation': 'transition-candidate head alone is not usable; it scores 227/640 and fails candidate_selection.',
            },
            'semantic_plus_transition_candidate_head': {
                'score': composite,
                'by_task': composite_tasks,
                'interpretation': 'composite route improves candidate_selection to 92/160 but damages next_action to 41/160, total 357/640.',
            },
        },
        'why_rejected': [
            'composite total 357/640 is below selected Stage11924 364/640',
            'composite next_action 41/160 is below Stage11924 51/160 and Stage12083 59/160',
            'pure transition-candidate head total 227/640 is far below usable',
            'promotion gate required old_transition >364, candidate_selection >=89, next_action >=51; next_action and total failed',
        ],
        'what_was_preserved': {
            'filtered_strict': audit['gates']['filtered_strict_preserved'],
            'filtered_validation': audit['gates']['filtered_validation_preserved'],
            'old_canary_strict': audit['gates']['old_canary_strict_preserved'],
            'old_canary_validation': audit['gates']['old_canary_validation_preserved'],
            'residual_bank': audit['gates']['residual_preserved'],
            'source_heldout_smoke': audit['gates']['smoke_preserved'],
        },
        'lesson': (
            'Separate transition-candidate head training can supply candidate-selection signal when added to the semantic route, '
            'but it also pushes next_action in the wrong direction. The next ablation must route candidate_selection only, '
            'or add a second next_action-preserving phase initialized from Stage12096 with explicit next_action gates.'
        ),
        'recommended_next_stage': {
            'name': 'stage12099_task_routed_candidate_selection_composite_audit',
            'do_not_train_yet': True,
            'hypothesis': 'A task-routed inference policy can use Stage12096 composite only for candidate_selection while retaining Stage11924 or Stage12083 for next_action.',
            'route_to_test_before_more_training': {
                'candidate_selection': 'stage12096 semantic_plus_transition_candidate_head',
                'next_action': 'stage12083 semantic_candidate_head if it preserves selected-verifier rows, otherwise stage11924 semantic_candidate_head',
                'continue_or_stop': 'stage11924 semantic_candidate_head',
                'verifier_transition': 'stage11924 semantic_candidate_head',
            },
            'promotion_gate': {
                'old_transition_640': '>364',
                'candidate_selection': '>=92/160 preferred, >=89 required',
                'next_action': '>=59/160 preferred, >=51 required',
                'protected_gates': 'preserved',
                'route_declared_before_eval': True,
            },
        },
        'source_artifacts': {
            'stage12097_audit': rel(AUDIT),
            'stage12094_design': rel(DESIGN),
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
