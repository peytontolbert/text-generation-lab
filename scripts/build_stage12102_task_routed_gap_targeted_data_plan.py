#!/usr/bin/env python3
"""Plan sealed confirmation and targeted data after Stage12099 routed lift."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = 12102
NAME = 'stage12102_task_routed_gap_targeted_data_plan'
OUT = ROOT / 'runs/local/artifacts' / NAME
SUMMARY = OUT / 'task_routed_gap_targeted_data_plan.json'
MIRROR = ROOT / 'runs/summaries' / f'{NAME}.json'
GAP = ROOT / 'runs/summaries/stage12101_task_routed_transition_gap_atlas.json'
ROUTE_DECISION = ROOT / 'runs/summaries/stage12100_task_routed_transition_decision.json'


def read_json(path: Path) -> Any:
    return json.loads(path.read_text())


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + '\n')


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    gap = read_json(GAP)
    route_decision = read_json(ROUTE_DECISION)
    summary = {
        'stage': STAGE,
        'stage_name': NAME,
        'created_at_utc': datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00', 'Z'),
        'decision': 'route_confirmation_and_gap_data_plan_ready_no_training_launched',
        'current_state': {
            'standalone_selected': route_decision['standalone_selected_transition_frontier'],
            'product_routed_candidate': route_decision['product_routed_transition_candidate'],
            'gap_counts': gap['summary_counts'],
        },
        'confirmation_before_claim': {
            'stage12103_option_permutation_stability_audit': {
                'required': True,
                'route_policy': route_decision['product_routed_transition_candidate']['route_policy'],
                'minimum': {
                    'permutations_per_row': 3,
                    'rows': 640,
                    'stable_prediction_rate': '>=0.95 preferred, >=0.90 minimum for diagnostic',
                    'routed_correct_under_majority_vote': '>=375/640',
                    'no_task_rows_missing': True,
                },
                'purpose': 'Ensure the routed lift is not option-order/label-position brittle.',
            },
            'stage12104_sealed_transition_slice_request': {
                'required': True,
                'minimum_rows': 100,
                'preferred_rows': 250,
                'split': 'root-disjoint from Stage11897/11943/120xx transition projection rows',
                'task_balance': {
                    'transition_candidate_selection': '25%',
                    'transition_next_action': '35%',
                    'transition_verifier_transition': '25%',
                    'transition_continue_or_stop': '15%',
                },
                'purpose': 'Confirm Stage12099 route on rows not used to discover the route.',
            },
        },
        'targeted_data_plan': {
            'do_not_train_on_same_manifest_gemma_only_rows': True,
            'target_total_disjoint_analogues': 220,
            'allocations': {
                'transition_next_action': {
                    'rows': 80,
                    'why': 'Largest routed miss family: 101/160 misses; 25 Gemma-only rows remain.',
                    'hard_negatives': ['PLAN_PATCH when RETRIEVE_EVIDENCE is correct', 'FINISH when CONTINUE is correct', 'ABSTAIN_OR_ROLLBACK when SELECT_TEST is correct'],
                },
                'transition_candidate_selection': {
                    'rows': 60,
                    'why': 'Still 68 routed misses and 35 Gemma-only rows despite candidate route lift.',
                    'hard_negatives': ['candidate_change_surface vs verifier_and_build_constraint', 'selected_inline_test_anchor vs implementation_only_no_verifier'],
                },
                'transition_verifier_transition': {
                    'rows': 50,
                    'why': 'Plateaued at 96/160 with 22 Gemma-only rows.',
                    'hard_negatives': ['PASS_CURRENT_BUILD vs PASS_CURRENT_BUILD_AND_RUN', 'PASS_CURRENT_STATE vs PASS_TO_PASS', 'VERIFIER_REMOVED vs INSUFFICIENT_EVIDENCE'],
                },
                'transition_continue_or_stop': {
                    'rows': 30,
                    'why': 'Strongest family but still 15 Gemma-only rows and 32 routed misses.',
                    'hard_negatives': ['premature DONE after targeted test only', 'CONTINUE after verifier removed', 'ABSTAIN when evidence is sufficient'],
                },
            },
            'language_balance': {
                'python': '>=45 roots',
                'c_cpp': '>=45 roots',
                'rust': '>=35 roots',
                'web_js_ts_html': '>=35 roots',
                'repo_family_cap': '<=10% of any task family',
            },
            'row_requirements': [
                'source/test/verifier evidence visible before candidates',
                'opaque shuffled labels',
                'semantic candidate objects with role/artifact/evidence_ids',
                'no singleton options',
                'no target string leak before candidates',
                'root lineage disjoint from the 640-row discovery manifest for strict confirmation',
            ],
        },
        'training_policy_after_confirmation': {
            'if_route_fails_permutation_or_sealed': 'Do not consolidate; build better data first.',
            'if_route_holds_but_still_below_gemma': 'Train task-specific heads/adapters from disjoint analogues; keep task routing explicit.',
            'if_route_beats_gemma_on_sealed': 'Then build a single product routing contract and separately pursue standalone consolidation.',
            'standalone_weight_requirement': 'Still unmet; routed product candidate does not satisfy standalone weights better than Gemma.',
        },
        'source_artifacts': {
            'stage12101_gap_atlas': rel(GAP),
            'stage12100_route_decision': rel(ROUTE_DECISION),
        },
        'outputs': {
            'summary': rel(SUMMARY),
            'summary_mirror': rel(MIRROR),
        },
    }
    write_json(SUMMARY, summary)
    write_json(MIRROR, summary)
    print(json.dumps({
        'decision': summary['decision'],
        'confirmation_before_claim': summary['confirmation_before_claim'],
        'targeted_allocations': summary['targeted_data_plan']['allocations'],
    }, indent=2, sort_keys=True))


if __name__ == '__main__':
    main()
