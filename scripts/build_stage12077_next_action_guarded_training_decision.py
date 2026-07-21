#!/usr/bin/env python3
"""Record decision for Stage12075/12076 next-action guarded probe."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STAGE = 12077
NAME = 'stage12077_next_action_guarded_training_decision'
OUT = ROOT / 'runs/local/artifacts' / NAME
SUMMARY = OUT / 'next_action_guarded_training_decision.json'
MIRROR = ROOT / 'runs/summaries' / f'{NAME}.json'
AUDIT = ROOT / 'runs/summaries/stage12076_next_action_guarded_training_postrun_audit.json'
REQ = ROOT / 'runs/summaries/stage12074_next_action_guarded_training_request.json'
MAT = ROOT / 'runs/summaries/stage12073_next_action_support_materializer.json'


def read(path: Path):
    return json.loads(path.read_text())


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    MIRROR.parent.mkdir(parents=True, exist_ok=True)
    audit = read(AUDIT)
    request = read(REQ)
    materializer = read(MAT)
    stage11924 = audit['results']['stage11924_transition_listwise_head_only']
    stage12075 = audit['results']['stage12075_next_action_guarded_training']
    payload = {
        'stage': STAGE,
        'stage_name': NAME,
        'created_at_utc': datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00', 'Z'),
        'decision': 'reject_stage12075_keep_stage11924_selected_transition_frontier',
        'selected_transition_frontier': 'stage11924_transition_listwise_head_only_probe',
        'why_rejected': [
            'Old transition 640 regressed from 364/640 to 350/640.',
            'The targeted transition_next_action family regressed from 51/160 to 40/160.',
            'The run preserved compact gates but did not improve any promotion frontier metric.',
            'Row changes were net -14 versus Stage11924: 12 gains, 26 losses.',
        ],
        'positive_result': [
            'Protected compact gates stayed preserved, so catastrophic compact interference did not occur.',
            'Stage12073 admission pipeline is usable as a data-construction mechanism, but its current row geometry is not sufficient for training.',
        ],
        'scoreboard': {
            'stage11924_old_transition': stage11924['transition_projection_routed'],
            'stage12075_old_transition': stage12075['transition_projection_routed'],
            'stage11924_next_action': stage11924['transition_by_task']['transition_next_action'],
            'stage12075_next_action': stage12075['transition_by_task']['transition_next_action'],
            'protected_gates': audit['gates'],
            'gemma_same_manifest_reference': {'correct': 386, 'rows': 640},
        },
        'root_cause_read': [
            'The next-action materializer overcorrected the wrong boundary: it helped some patch-impact next_action rows but damaged evidence-citation selected-verifier next_action rows.',
            'The synthetic milestone states are too broad for evidence-citation rows where verifier/test evidence should trigger SELECT_TEST or VERIFY_RESULT instead of broad patch/retrieve/abstain behavior.',
            'More next-action rows alone are not enough; rows must be aligned to the frozen miss subfamilies and include counterexamples that preserve existing correct evidence-citation next-action behavior.',
        ],
        'next_recommendation': {
            'recommended_stage': 'stage12078_next_action_loss_gain_atlas',
            'goal': 'Analyze the 12 gains and 26 losses from Stage12076 by source subfamily/target/prediction before building any more rows.',
            'do_not_do': 'Do not rerun Stage12075 with larger steps or the same Stage12073 rows.',
            'minimum_next_data_fix': [
                'Separate patch-impact next_action support from evidence-citation next_action support.',
                'Add preservation replay specifically for evidence_citation_selected_verifier::next_action rows that Stage12075 lost.',
                'Downweight or quarantine broad ABSTAIN/PLAN synthetic rows until loss/gain atlas proves they do not erase SELECT_TEST/VERIFY_RESULT behavior.',
            ],
        },
        'source_artifacts': {
            'stage12076_audit': rel(AUDIT),
            'stage12074_request': rel(REQ),
            'stage12073_materializer': rel(MAT),
            'stage12075_runtime': 'runs/local/artifacts/stage12075_next_action_guarded_training_probe/runtime_model/runtime_model_bundle.json',
        },
        'outputs': {'summary': rel(SUMMARY), 'summary_mirror': rel(MIRROR)},
    }
    SUMMARY.write_text(json.dumps(payload, indent=2, sort_keys=True) + '\n')
    MIRROR.write_text(json.dumps(payload, indent=2, sort_keys=True) + '\n')
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == '__main__':
    main()
