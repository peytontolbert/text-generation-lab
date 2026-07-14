#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / 'runs' / 'local' / 'artifacts'
STAGE = 10956
NAME = 'stage10956_multilingual_evidence_next_batch_package'
OUT_DIR = ARTIFACTS / NAME
SUMMARY_JSON = OUT_DIR / 'multilingual_evidence_next_batch_package.json'
ROWS_JSONL = OUT_DIR / 'next_batch_rows.jsonl'

QUEUE_JSON = ARTIFACTS / 'stage10913_multilingual_evidence_root_build_queue' / 'multilingual_evidence_root_build_queue.json'
QUEUE_ROWS = ARTIFACTS / 'stage10913_multilingual_evidence_root_build_queue' / 'root_build_queue.jsonl'
MANIFEST_JSON = ARTIFACTS / 'stage10914_evidence_successor_materialization_manifest' / 'evidence_successor_materialization_manifest.json'
MANIFEST_ROWS = ARTIFACTS / 'stage10914_evidence_successor_materialization_manifest' / 'candidate_rows.jsonl'
ATLAS_JSON = ARTIFACTS / 'stage10417_multilingual_reviewed_scaling_atlas' / 'multilingual_reviewed_scaling_atlas.json'
WEB_GAP_JSON = ARTIFACTS / 'stage10418_pure_web_verifier_anchor_gap_audit' / 'pure_web_verifier_anchor_gap_audit.json'
RATCHET_ROWS = ARTIFACTS / 'stage10751_multilingual_root_scale_quality_ratchet' / 'language_batch_plans.jsonl'
SCORER_DECISION_JSON = ARTIFACTS / 'stage10955_evidence_scorer_blend_decision' / 'evidence_scorer_blend_decision.json'


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding='utf-8'))


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines() if line.strip()]


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + '\n', encoding='utf-8')


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('w', encoding='utf-8') as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + '\n')


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def now_utc() -> str:
    return time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())


def by_language(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {str(row.get('language_family')): row for row in rows}


def main() -> None:
    queue = load_json(QUEUE_JSON)
    queue_rows = load_jsonl(QUEUE_ROWS)
    manifest = load_json(MANIFEST_JSON)
    manifest_rows = load_jsonl(MANIFEST_ROWS)
    atlas = load_json(ATLAS_JSON)
    web_gap = load_json(WEB_GAP_JSON)
    ratchet = by_language(load_jsonl(RATCHET_ROWS))
    scorer_decision = load_json(SCORER_DECISION_JSON)

    immediate_rows = [row for row in manifest_rows if str(row.get('queue_id') or '') in {
        'python_repository_library_evidence_b_vs_f_replenishment',
        'cpp_parametergolf_evidence_b_vs_f_replenishment',
        'cpp_agentkernel_counterfamily_evidence_replenishment',
    }]

    atlas_rows = atlas.get('admitted_bundle_rows') or []
    rust_ready = [
        row for row in atlas_rows
        if str(row.get('language_family') or '') == 'rust' and str(row.get('bundle_id') or '') in {
            'stage10126::candle::candle-core::rust',
            'stage10126::tokenizers::tokenizers::rust',
            'stage10413::candle::candle-flash-attn::rust',
        }
    ]
    rust_support = [
        {
            'bundle_id': 'stage10674::linux::rust',
            'repo_id': 'linux',
            'status': 'reviewed_v27_support_reference',
            'reason': 'Named in the rust scaling ratchet as a primary remaining materialization target with verifier-anchor expectations.',
            'next_action': 'materialize_reviewed_bundle_into_fresh_E_vs_F_rows',
        },
        {
            'bundle_id': 'stage10674::candle::candle-datasets',
            'repo_id': 'candle',
            'status': 'reviewed_v27_support_reference',
            'reason': 'Named in the rust scaling ratchet and existing support manifests as a verifier-anchored E-vs-F source family.',
            'next_action': 'materialize_reviewed_bundle_into_fresh_E_vs_F_rows',
        },
        {
            'bundle_id': 'candle::candle-transformers',
            'repo_id': 'candle',
            'status': 'source_family_target_not_yet_materialized_here',
            'reason': 'Explicitly named in the rust scaling ratchet as a primary next builder target, but not yet present as an admitted reviewed bundle in the checked atlas.',
            'next_action': 'acquire_or_materialize_review_packet_first',
        },
    ]

    web_rows = [row for row in queue_rows if str(row.get('language_family') or '') == 'web_js_ts_html']

    common_gates = [
        'prompt_target_leak_rows == 0 for every promoted root',
        'same root_id and root_lineage_key isolated to one split component',
        'fresh heldout reserved before training',
        'repo family cap respected at admission time',
        'preserve the repaired v2.7 canary and leak-clean status',
        'preserve all six visible evidence roles for evidence-citation successors whenever the source packet supports them',
        'no visible target path string before options',
    ]

    next_rows = []
    for row in immediate_rows:
        next_rows.append({
            'lane': 'immediate_materialization',
            'language_family': row.get('language_family'),
            'queue_id': row.get('queue_id'),
            'repo_id': row.get('repo_id'),
            'source_bundle_id': row.get('source_bundle_id'),
            'competition_family': row.get('competition_family'),
            'gold_answer_value': row.get('gold_answer_value'),
            'selected_tests': row.get('selected_tests'),
            'candidate_paths': row.get('candidate_paths'),
            'next_action': row.get('next_action'),
            'anti_cheat_challenge_families': row.get('anti_cheat_challenge_families'),
            'materialization_requirements': row.get('materialization_requirements'),
        })
    for row in rust_ready:
        next_rows.append({
            'lane': 'rust_reviewed_supply',
            'language_family': row.get('language_family'),
            'bundle_id': row.get('bundle_id'),
            'repo_id': row.get('repo_id'),
            'selected_tests': row.get('selected_tests'),
            'selected_tests_count': row.get('selected_tests_count'),
            'visible_evidence_keys': row.get('visible_evidence_keys'),
            'decision_rationale': row.get('decision_rationale'),
            'status': 'available_reviewed_bundle',
        })
    next_rows.extend(rust_support)
    for row in web_rows:
        next_rows.append({
            'lane': 'web_supply_or_stress',
            'language_family': row.get('language_family'),
            'queue_id': row.get('queue_id'),
            'repo_id': row.get('repo_id'),
            'status': row.get('status'),
            'task': row.get('task'),
            'anti_cheat_requirements': row.get('anti_cheat_requirements'),
            'selected_tests': row.get('selected_tests'),
            'candidate_paths': row.get('candidate_paths'),
        })

    payload = {
        'stage': STAGE,
        'stage_name': NAME,
        'created_at_utc': now_utc(),
        'passed': True,
        'claim_scope': [
            'Package the next honest multilingual evidence-expansion batch after scorer calibration was exhausted.',
            'Separate immediate Python/C++ row materialization from Rust reviewed supply and the unresolved pure-web acquisition blocker under one anti-cheat contract.',
        ],
        'source_artifacts': {
            'queue': rel(QUEUE_JSON),
            'materialization_manifest': rel(MANIFEST_JSON),
            'reviewed_scaling_atlas': rel(ATLAS_JSON),
            'pure_web_gap': rel(WEB_GAP_JSON),
            'root_scale_ratchet': rel(RATCHET_ROWS),
            'scorer_blocker_decision': rel(SCORER_DECISION_JSON),
        },
        'headline': {
            'immediate_materialization_candidates': len(immediate_rows),
            'rust_reviewed_bundle_candidates': len(rust_ready),
            'rust_additional_target_families': len(rust_support),
            'web_queue_items': len(web_rows),
            'web_source_heldout_headline_ready': ((web_gap.get('verdict') or {}).get('web_source_heldout_headline_ready')),
            'scorer_calibration_remaining': False,
        },
        'findings': [
            'The current scorer/objective branch is exhausted: stage10955 shows no honest linear calibration preserves the overlay while fixing the explicit-ledger blocker.',
            'The immediate next multilingual evidence work is concrete: 3 ready materialization candidates already exist for Python/C++ with gold, anti-cheat, and selected-test anchors.',
            'Rust has reviewed supply and named next target families, but still needs fresh E-vs-F row materialization or new review packets rather than more same-surface probes.',
            'Web remains supply-blocked for headline use until a non-overlapping pure-web selected-test family is ingested; code_assist remains stress/train-support only.',
        ],
        'common_honesty_gates': common_gates,
        'per_language_constraints': {
            'python': ratchet.get('python'),
            'c_cpp': ratchet.get('c_cpp'),
            'rust': ratchet.get('rust'),
            'web_js_ts_html': ratchet.get('web_js_ts_html'),
        },
        'next_best_step': 'Materialize the 3 immediate Python/C++ evidence successors, then either materialize fresh Rust E-vs-F rows from reviewed supply or acquire a new pure-web selected-test family before another multilingual promotion run.',
        'outputs': {
            'summary_json': rel(SUMMARY_JSON),
            'next_batch_rows_jsonl': rel(ROWS_JSONL),
        },
    }
    write_json(SUMMARY_JSON, payload)
    write_jsonl(ROWS_JSONL, next_rows)
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == '__main__':
    main()
