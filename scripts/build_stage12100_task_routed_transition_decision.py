#!/usr/bin/env python3
"""Record decision for Stage12099 task-routed transition audit."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = 12100
NAME = 'stage12100_task_routed_transition_decision'
OUT = ROOT / 'runs/local/artifacts' / NAME
SUMMARY = OUT / 'task_routed_transition_decision.json'
MIRROR = ROOT / 'runs/summaries' / f'{NAME}.json'
AUDIT = ROOT / 'runs/summaries/stage12099_task_routed_candidate_selection_composite_audit.json'


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
    score = audit['routed_transition_score']
    selected = audit['selected_transition_frontier_baseline']
    summary = {
        'stage': STAGE,
        'stage_name': NAME,
        'created_at_utc': datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00', 'Z'),
        'decision': 'record_stage12099_as_product_route_frontier_candidate_not_standalone_promotion',
        'standalone_selected_transition_frontier': {
            'stage': selected['stage'],
            'scorer': selected['scorer'],
            'score': selected['score'],
            'status': 'remains selected standalone transition runtime',
        },
        'product_routed_transition_candidate': {
            'stage': 'stage12099_task_routed_candidate_selection_composite_audit',
            'score': score,
            'by_task': audit['routed_by_task'],
            'route_policy': audit['route_policy'],
            'delta_vs_stage11924': score['correct'] - selected['score']['correct'],
            'delta_vs_gemma_386': score['correct'] - 386,
            'status': 'frontier candidate for product routing only; requires sealed confirmation',
        },
        'why_not_final_promotion': [
            '375/640 improves over Stage11924 364/640 but does not beat Gemma 386/640',
            'route uses multiple runtimes/scorers; it is not a single standalone weight checkpoint',
            'route was composed from existing audit cards and needs sealed/source-heldout confirmation under the same declared route',
        ],
        'why_it_matters': [
            'candidate_selection can be lifted to 92/160 without sacrificing next_action if task routing is allowed',
            'next_action diagnostic gain from Stage12083 can coexist with Stage12096 candidate_selection gain when routed by task',
            'the remaining transition gap to Gemma is now 11 rows instead of 22 rows for product-routed transition scoring',
        ],
        'next_stage': {
            'recommended': 'stage12101_task_routed_transition_gap_atlas',
            'purpose': 'Analyze the remaining 265 routed misses and the 11-row Gemma gap without launching more training.',
            'do_not_train_before_gap_atlas': True,
            'sealed_confirmation_needed': True,
        },
        'source_artifacts': {
            'stage12099_audit': rel(AUDIT),
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
