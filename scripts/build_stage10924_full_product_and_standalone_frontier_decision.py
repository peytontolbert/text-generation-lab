#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / 'runs' / 'local' / 'artifacts'
STAGE = 10924
NAME = 'stage10924_full_product_and_standalone_frontier_decision'
OUT_DIR = ARTIFACTS / NAME
OUT_JSON = OUT_DIR / 'full_product_and_standalone_frontier_decision.json'

STANDALONE_SUCCESSOR = ARTIFACTS / 'stage10923_reviewed_v27_scored_interface_successor_comparison_audit' / 'reviewed_v27_scored_interface_successor_comparison_audit.json'
STANDALONE_CONTRACT = ARTIFACTS / 'stage10922_reviewed_v27_scored_interface_contract' / 'reviewed_v27_scored_interface_contract.json'
HARNESS_REPAIRED = ARTIFACTS / 'stage10659_repaired_headline_harness_result_audit' / 'repaired_headline_harness_result_audit.json'
HARNESS_REVIEWED_V28 = ARTIFACTS / 'stage10651_reviewed_v28_harness_result_audit' / 'reviewed_v28_harness_result_audit.json'
HARNESS_HANDOFF = ARTIFACTS / 'stage10657_repaired_headline_harness_handoff_bundle' / 'repaired_headline_harness_handoff_bundle.json'
WEB_BLOCKER = ARTIFACTS / 'stage10921_broad_pure_web_source_acquisition_atlas' / 'broad_pure_web_source_acquisition_atlas.json'


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
    standalone = load_json(STANDALONE_SUCCESSOR)
    standalone_contract = load_json(STANDALONE_CONTRACT)
    harness_repaired = load_json(HARNESS_REPAIRED)
    harness_v28 = load_json(HARNESS_REVIEWED_V28)
    handoff = load_json(HARNESS_HANDOFF)
    web = load_json(WEB_BLOCKER)

    standalone_headline = standalone.get('headline') or {}
    repaired_metrics = harness_repaired.get('metrics') or {}
    v28_metrics = harness_v28.get('metrics') or {}
    handoff_authority = handoff.get('authority') or {}

    payload = {
        'stage': STAGE,
        'stage_name': NAME,
        'created_at_utc': now_utc(),
        'passed': True,
        'decision': 'dual_track_frontier_frozen',
        'claim_scope': [
            'Choose the current best truthful standalone frontier and the current best truthful full-product harness frontier from existing audited artifacts.',
            'Keep the two claim paths separate so maximal-score harness work does not contaminate the standalone maintainer benchmark boundary.',
        ],
        'source_artifacts': {
            'standalone_successor_audit': rel(STANDALONE_SUCCESSOR),
            'standalone_scoring_contract': rel(STANDALONE_CONTRACT),
            'repaired_headline_harness_audit': rel(HARNESS_REPAIRED),
            'reviewed_v28_harness_audit': rel(HARNESS_REVIEWED_V28),
            'repaired_headline_harness_handoff': rel(HARNESS_HANDOFF),
            'web_source_supply_audit': rel(WEB_BLOCKER),
        },
        'current_best_standalone_frontier': {
            'name': 'reviewed_v27_alias_safe_successor_under_scored_interface_contract',
            'artifact': rel(STANDALONE_SUCCESSOR),
            'hundred_m_accuracy': standalone_headline.get('strict_exact_100m_under_contract'),
            'gemma_accuracy': standalone_headline.get('strict_exact_gemma'),
            'delta': standalone_headline.get('strict_delta_100m_minus_gemma'),
            'rows': standalone_headline.get('rows'),
            'language_wins_100m': standalone_headline.get('language_wins_100m'),
            'language_wins_gemma': standalone_headline.get('language_wins_gemma'),
            'language_ties': standalone_headline.get('language_ties'),
            'same_manifest_only': True,
            'source_heldout_supported': False,
            'full_product_claim': False,
            'notes': [
                'Only one task-scoped scoring override is approved: verifier_outcome_semantic_transition -> decoder_on_transition_only.',
                'Evidence-citation scoring remains blocked at retrieval until fresh Python/C++ successors and a pure-web control family exist.',
            ],
        },
        'current_best_full_product_harness_frontier': {
            'name': 'repaired_headline_same_manifest_harness',
            'artifact': rel(HARNESS_REPAIRED),
            'hundred_m_accuracy': repaired_metrics.get('hundred_m_accuracy'),
            'gemma_accuracy': repaired_metrics.get('gemma_accuracy'),
            'delta': repaired_metrics.get('delta'),
            'rows': repaired_metrics.get('total_rows'),
            'cells': repaired_metrics.get('cells'),
            'writeback_repaired_cells': repaired_metrics.get('writeback_repaired_cells'),
            'language_breakdown': harness_repaired.get('per_language'),
            'same_manifest_only': True,
            'source_heldout_supported': False,
            'machine_writeback_completed': repaired_metrics.get('writeback_repaired_cells') == repaired_metrics.get('cells'),
            'notes': [
                'This is the best current score-aligned harness path for the v2.7-style headline slice.',
                'It remains separate from the broader reviewed-v28 harness path and from any source-heldout claim.',
            ],
        },
        'broader_but_lower_harness_frontier': {
            'name': 'reviewed_v28_maintainer_choice_harness',
            'artifact': rel(HARNESS_REVIEWED_V28),
            'hundred_m_accuracy': v28_metrics.get('hundred_m_accuracy'),
            'gemma_accuracy': v28_metrics.get('gemma_accuracy'),
            'delta': v28_metrics.get('delta'),
            'rows': v28_metrics.get('total_rows'),
            'cells': v28_metrics.get('cells'),
            'notes': [
                'Broader harness surface than the repaired headline path, but currently lower headline score.',
                'Useful as a realism/breadth track, not the maximal-score harness headline for now.',
            ],
        },
        'authority_state': {
            'repaired_headline_harness_execution_authorized_next': handoff_authority.get('harness_execution_authorized_next'),
            'repaired_headline_harness_promotion_ready': handoff_authority.get('promotion_ready'),
            'standalone_scoring_contract_ready': standalone_contract.get('decision') == 'reviewed_v27_scored_interface_contract_ready',
        },
        'anti_cheat_and_realism_boundaries': {
            'web_pure_source_supply_blocked': (web.get('metrics') or {}).get('unique_fresh_pure_web_selected_test_rows') == 0,
            'web_block_reason': web.get('decision'),
            'standalone_evidence_policy_blocked': True,
            'source_heldout_claims_blocked': True,
            'harness_and_standalone_must_remain_separate': True,
        },
        'findings': [
            'Standalone is currently stronger on the audited compact surface: 100M reaches 23/23 under the approved scored-interface contract while Gemma stays at 6/23.',
            'Full-product harness is already recovered enough to score honestly: the repaired headline harness path has completed machine writeback for all four language cells and still shows a 100M advantage.',
            'The broader reviewed-v28 harness path exists and is healthy, but it is a lower-scoring realism track than the repaired headline harness path.',
            'The main remaining integrity blocker is still fresh pure-web selected-test source supply, which limits broader multilingual evidence-policy promotion and stronger realism claims.',
        ],
        'next_best_step': 'Use stage10923 as the current standalone frontier and stage10659 as the current maximal-score harness frontier; put new data-building effort into fresh Python/C++ evidence successors and fresh pure-web selected-test source acquisition before trying to broaden claims.',
    }
    write_json(OUT_JSON, payload)
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == '__main__':
    main()
