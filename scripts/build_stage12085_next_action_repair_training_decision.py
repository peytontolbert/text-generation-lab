#!/usr/bin/env python3
"""Record decision for Stage12083/12084 next-action repair probe."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STAGE = 12085
NAME = 'stage12085_next_action_repair_training_decision'
OUT = ROOT / 'runs/local/artifacts' / NAME
SUMMARY = OUT / 'next_action_repair_training_decision.json'
MIRROR = ROOT / 'runs/summaries' / f'{NAME}.json'
AUDIT = ROOT / 'runs/summaries/stage12084_next_action_repair_training_postrun_audit.json'
REQ = ROOT / 'runs/summaries/stage12082_next_action_repair_training_request.json'
PACKET = ROOT / 'runs/summaries/stage12080_next_action_subfamily_repair_packet.json'


def read(path: Path): return json.loads(path.read_text())
def rel(path: Path) -> str: return str(path.relative_to(ROOT))
def write(path: Path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True)+'\n')


def main():
    audit = read(AUDIT)
    req = read(REQ)
    packet = read(PACKET)
    st11924 = audit['results']['stage11924_transition_listwise_head_only']
    st12083 = audit['results']['stage12083_next_action_repair_training']
    payload = {
        'stage': STAGE,
        'stage_name': NAME,
        'created_at_utc': datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00','Z'),
        'decision': 'keep_stage11924_selected_transition_frontier_record_stage12083_next_action_lane_gain',
        'selected_transition_frontier': 'stage11924_transition_listwise_head_only_probe',
        'stage12083_status': 'diagnostic_lane_gain_not_overall_promotion',
        'why_not_promoted': [
            'Total old transition score retained Stage11924 at 364/640 but did not exceed it.',
            'Gemma same-manifest reference remains 386/640, so Stage12083 is not a Gemma win.',
            'Transition candidate-selection regressed enough to cancel next-action gains in total score.',
        ],
        'meaningful_progress': [
            'transition_next_action improved from 51/160 to 59/160 under the product semantic-candidate scorer.',
            'All protected compact gates were preserved: filtered strict, old strict, validation, residual, and source-heldout smoke.',
            'The subfamily-aware repair packet fixed the Stage12075 collapse enough to recover retention while improving the targeted lane.',
        ],
        'scoreboard': {
            'stage11924_old_transition': st11924['transition_projection_routed'],
            'stage12083_old_transition': st12083['transition_projection_routed'],
            'stage11924_by_task': st11924['transition_by_task'],
            'stage12083_by_task': st12083['transition_by_task'],
            'gates': audit['gates'],
            'row_changes_vs_stage11924': audit['transition_changes_vs_stage11924'],
            'gemma_same_manifest_reference': {'correct': 386, 'rows': 640},
        },
        'next_recommendation': {
            'recommended_stage': 'stage12086_candidate_selection_regression_atlas',
            'goal': 'Analyze the 46 gains / 46 losses from Stage12084, especially candidate-selection regressions that cancelled next-action gains.',
            'do_not_do': 'Do not promote Stage12083 as selected transition frontier and do not rerun the same packet with more steps.',
            'target_for_next_promotion': {
                'old_transition_640': '>364/640',
                'transition_next_action': '>=59/160 retained or improved',
                'transition_candidate_selection': 'recover from Stage12083 back to >=89/160',
                'protected_gates': 'all preserved',
            },
        },
        'source_artifacts': {
            'audit': rel(AUDIT),
            'request': rel(REQ),
            'repair_packet': rel(PACKET),
            'runtime': 'runs/local/artifacts/stage12083_next_action_repair_training_probe/runtime_model/runtime_model_bundle.json',
        },
        'outputs': {'summary': rel(SUMMARY), 'summary_mirror': rel(MIRROR)},
    }
    write(SUMMARY, payload); write(MIRROR, payload)
    print(json.dumps(payload, indent=2, sort_keys=True))

if __name__ == '__main__': main()
