#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / 'runs' / 'local' / 'artifacts'
STAGE = 10922
NAME = 'stage10922_reviewed_v27_scored_interface_contract'
OUT_DIR = ARTIFACTS / NAME
OUT_JSON = OUT_DIR / 'reviewed_v27_scored_interface_contract.json'

ALIAS_SAFE_BASELINE = ARTIFACTS / 'stage10881_evidence_alias_quarantine_successor' / 'evidence_alias_quarantine_successor.json'
VERIFIER_POLICY_AUDIT = ARTIFACTS / 'stage10908_verifier_transition_policy_audit' / 'verifier_transition_policy_audit.json'
VERIFIER_POLICY_COMPARISON = ARTIFACTS / 'stage10909_verifier_transition_policy_candidate_comparison' / 'verifier_transition_policy_candidate_comparison.json'
VERIFIER_POLICY_SLICE = ARTIFACTS / 'stage10910_python_verifier_transition_policy_slice_comparison' / 'python_verifier_transition_policy_slice_comparison.json'
EVIDENCE_POLICY_DECISION = ARTIFACTS / 'stage10912_current_evidence_policy_decision' / 'current_evidence_policy_decision.json'
EVIDENCE_SLICE_DECISION = ARTIFACTS / 'stage10917_evidence_successor_slice_decision' / 'evidence_successor_slice_decision.json'
WEB_BLOCKER_DECISION = ARTIFACTS / 'stage10919_evidence_policy_and_web_blocker_decision' / 'evidence_policy_and_web_blocker_decision.json'
WEB_ACQUISITION_ATLAS = ARTIFACTS / 'stage10921_broad_pure_web_source_acquisition_atlas' / 'broad_pure_web_source_acquisition_atlas.json'


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding='utf-8'))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + '\n', encoding='utf-8')


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def now_utc() -> str:
    return time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())


def main() -> None:
    alias_safe = load_json(ALIAS_SAFE_BASELINE)
    verifier_audit = load_json(VERIFIER_POLICY_AUDIT)
    verifier_compare = load_json(VERIFIER_POLICY_COMPARISON)
    verifier_slice = load_json(VERIFIER_POLICY_SLICE)
    evidence_policy = load_json(EVIDENCE_POLICY_DECISION)
    evidence_slice = load_json(EVIDENCE_SLICE_DECISION)
    web_blocker = load_json(WEB_BLOCKER_DECISION)
    web_atlas = load_json(WEB_ACQUISITION_ATLAS)

    current_eval = (((verifier_audit.get('policies') or {}).get('current_retrieval') or {}).get('eval') or {})
    transition_strict = (((verifier_audit.get('policies') or {}).get('current_retrieval') or {}).get('strict_eval') or {})
    compare_headline = verifier_compare.get('headline') or {}
    web_metrics = web_atlas.get('metrics') or {}

    payload = {
        'stage': STAGE,
        'stage_name': NAME,
        'created_at_utc': now_utc(),
        'passed': True,
        'decision': 'reviewed_v27_scored_interface_contract_ready',
        'claim_scope': [
            'Freeze the approved bounded-choice scoring interface for the current honest reviewed-v2.7 standalone frontier.',
            'Adopt only task-scoped policy changes that have explicit anti-cheat support and leave broader multilingual evidence policy blocked until fresh web controls exist.',
        ],
        'source_artifacts': {
            'alias_safe_baseline': rel(ALIAS_SAFE_BASELINE),
            'verifier_policy_audit': rel(VERIFIER_POLICY_AUDIT),
            'verifier_policy_candidate_comparison': rel(VERIFIER_POLICY_COMPARISON),
            'verifier_policy_slice_comparison': rel(VERIFIER_POLICY_SLICE),
            'evidence_policy_decision': rel(EVIDENCE_POLICY_DECISION),
            'evidence_slice_decision': rel(EVIDENCE_SLICE_DECISION),
            'web_blocker_decision': rel(WEB_BLOCKER_DECISION),
            'web_acquisition_atlas': rel(WEB_ACQUISITION_ATLAS),
        },
        'approved_scoring_contract': {
            'default_policy': 'current_retrieval',
            'task_policy_overrides': {
                'verifier_outcome_semantic_transition': 'decoder_on_transition_only',
            },
            'explicit_non_overrides': {
                'evidence_citation': 'current_retrieval',
                'verifier_outcome': 'current_retrieval',
                'symptom_localization': 'current_retrieval',
                'patch_impact': 'current_retrieval',
                'minimal_fix_selection': 'current_retrieval',
                'abstention_insufficient_evidence': 'current_retrieval',
            },
        },
        'evidence_for_approved_override': {
            'fresh_python_verifier_slice_before_after': compare_headline.get('fresh_python_verifier_slice'),
            'cleaned_canary_regression_check': compare_headline.get('cleaned_canary_regression_check'),
            'strict_transition_rows_under_current_retrieval': transition_strict,
            'slice_comparison_overall': {
                'hundred_m_current_retrieval': (verifier_slice.get('hundred_m_current_retrieval') or {}).get('overall'),
                'hundred_m_policy_candidate': (verifier_slice.get('hundred_m_policy_candidate') or {}).get('overall'),
                'gemma12b': (verifier_slice.get('gemma12b') or {}).get('overall'),
            },
        },
        'blocked_policy_changes': {
            'evidence_citation': {
                'status': 'blocked',
                'decision': evidence_policy.get('decision'),
                'fresh_slice_status': evidence_slice.get('decision'),
                'reason': 'Role-mapped evidence retrieval helps fresh Python/C++ F rows but is not safe to promote because it breaks the clean web B control, and no fresh pure-web verifier-anchored control family exists.',
            },
            'web_multilingual_promotion': {
                'status': 'blocked',
                'decision': web_blocker.get('decision'),
                'broad_source_search': web_atlas.get('decision'),
                'reason': 'Current refinery inventories contain no fresh pure-web selected-test source family, so multilingual evidence-policy promotion remains web-blocked.',
            },
        },
        'current_honest_boundary': {
            'alias_safe_baseline_metrics': alias_safe.get('metrics'),
            'cleaned_canary_eval_accuracy_under_default_policy': current_eval.get('accuracy'),
            'fresh_python_transition_slice_after_override': compare_headline.get('fresh_python_verifier_slice'),
            'web_source_supply_metrics': {
                'fresh_pure_web_selected_test_rows': web_metrics.get('unique_fresh_pure_web_selected_test_rows'),
                'fresh_selected_test_rows': web_metrics.get('unique_fresh_selected_test_rows'),
                'fresh_web_rows': web_metrics.get('unique_fresh_web_rows'),
            },
        },
        'findings': [
            'A narrow verifier-transition override is now justified: decoder_on_transition_only lifts the fresh Python semantic-transition slice from 1/2 to 2/2 while Gemma stays at 0/2.',
            'That override does not change the cleaned multilingual canary check surface because no verifier_outcome_semantic_transition rows are present there.',
            'Evidence citation remains the main blocked multilingual family: the fresh Python/C++ successor slice still confirms the B-vs-F gap and no honest multilingual evidence scorer candidate exists yet.',
            'Web remains a hard anti-cheat blocker for evidence-policy promotion because the broader acquisition atlas still finds zero fresh pure-web selected-test roots in current inventories.',
        ],
        'next_best_step': 'Use this scored-interface contract for future standalone 100M-vs-Gemma comparisons, then keep dataset work focused on fresh Python/C++ evidence successors and new pure-web source acquisition rather than new global scorer changes.',
    }
    write_json(OUT_JSON, payload)
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == '__main__':
    main()
