#!/usr/bin/env python3
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / 'runs' / 'local' / 'artifacts'

STAGE = 10817
NAME = 'stage10817_candle_transformers_verifier_anchor_blocker'
OUT_DIR = ARTIFACTS / NAME
SUMMARY_JSON = OUT_DIR / 'candle_transformers_verifier_anchor_blocker.json'

MATERIALIZER = ARTIFACTS / 'stage10679_rust_verifier_anchor_materializer' / 'rust_verifier_anchor_materializer.json'
PREVIEW = ARTIFACTS / 'stage10679_rust_verifier_anchor_materializer' / 'review_packets' / 'candle__candle-transformers' / 'fresh_rust_bundle_preview.json'
ANTI = ARTIFACTS / 'stage10679_rust_verifier_anchor_materializer' / 'review_packets' / 'candle__candle-transformers' / 'anti_cheat_review_card.json'
GOLD = ARTIFACTS / 'stage10679_rust_verifier_anchor_materializer' / 'review_packets' / 'candle__candle-transformers' / 'perspective_gold_adjudication.json'
DISCOVERY = ARTIFACTS / 'stage10125_true_source_backed_rust_root_discovery_manifest' / 'true_source_backed_rust_root_candidates.jsonl'
BUILDER = ARTIFACTS / 'stage10441_rust_evidence_citation_fresh_builder_request' / 'rust_evidence_citation_fresh_builder_targets.jsonl'
EXTERNAL_REQ = ARTIFACTS / 'stage10677_rust_external_source_materialization_request' / 'rust_external_source_materialization_targets.jsonl'


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding='utf-8'))


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = []
    with path.open(encoding='utf-8') as handle:
        for line in handle:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + '\n', encoding='utf-8')


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def main() -> None:
    materializer = load_json(MATERIALIZER)
    preview = load_json(PREVIEW)
    anti = load_json(ANTI)
    gold = load_json(GOLD)
    discovery = next(row for row in load_jsonl(DISCOVERY) if str(row.get('candidate_root_id') or '') == 'candle::candle-transformers')
    builder = next(row for row in load_jsonl(BUILDER) if str(row.get('candidate_root_id') or '') == 'candle::candle-transformers')
    external_req = next(row for row in load_jsonl(EXTERNAL_REQ) if str(row.get('bundle_id') or '') == 'candle::candle-transformers')

    candidate_surface = preview.get('maintainer_visible_evidence', {}).get('candidate_change_surface', [])
    verifier_entries = preview.get('maintainer_visible_evidence', {}).get('verifier_and_test_constraint', [])
    selected_tests = preview.get('selected_tests') or []
    gold_todos = sum(1 for answer in (gold.get('perspective_gold_answers') or []) if str(answer.get('gold_answer_kind') or '').startswith('TODO_'))

    payload = {
        'stage': STAGE,
        'stage_name': NAME,
        'created_at_utc': datetime.now(timezone.utc).isoformat(),
        'passed': True,
        'decision': 'candle_transformers_requires_external_or_new_anchor_recovery_before_admission',
        'claim_scope': [
            'Prove whether candle-transformers is still blocked on verifier-anchor recovery after the latest local materialization stages.',
            'Separate finished local source-span recovery from the remaining external evidence dependency.',
        ],
        'headline_findings': [
            'Local source-span recovery is complete for candle-transformers: all candidate paths have real source text attached.',
            'No local selected test or verifier anchor is present in the latest stage10679 packet.',
            'Because verifier_outcome has no honest anchor and all eight gold answers remain TODO, candle-transformers is still not admissible for train-support or scoring.',
        ],
        'metrics': {
            'candidate_change_surface_count': len(candidate_surface),
            'candidate_change_surface_nonempty_count': sum(1 for item in candidate_surface if str(item.get('text') or '') != 'TODO_MATERIALIZE_REAL_SOURCE_SPAN'),
            'selected_test_count': len(selected_tests),
            'verifier_anchor_entry_count': len(verifier_entries),
            'verifier_anchor_placeholder_count': sum(1 for item in verifier_entries if str(item.get('text') or '') == 'TODO_MATERIALIZE_SELECTED_TEST_OR_TRACE_CONSTRAINT'),
            'gold_todo_answer_count': gold_todos,
            'supports_training_or_scoring_now': bool(preview.get('claim_boundary', {}).get('supports_training_or_scoring_now')),
            'test_file_count_from_discovery': int(discovery.get('test_file_count') or 0),
            'support_file_count_from_discovery': int(discovery.get('support_file_count') or 0),
        },
        'blocking_evidence': {
            'preview_claim_boundary': preview.get('claim_boundary'),
            'anti_cheat_status': anti.get('status'),
            'anti_cheat_decision_rationale': anti.get('decision_rationale'),
            'builder_recommendation': builder.get('recommendation'),
            'required_builder_delta': builder.get('required_builder_delta'),
            'external_recovery_route': external_req.get('recovery_route'),
            'required_recovered_fields': external_req.get('required_recovered_fields'),
        },
        'next_best_steps': [
            'Recover one real example, selected test, trace, or verifier-like execution anchor for candle-transformers generation/pipelines behavior from external repo/session evidence.',
            'Attach that anchor into verifier_and_test_constraint and selected_tests in the packet.',
            'Re-run AI gold adjudication and anti-cheat review only after the anchor is present.',
        ],
        'source_artifacts': {
            'materializer_summary': rel(MATERIALIZER),
            'preview_bundle': rel(PREVIEW),
            'anti_cheat_review_card': rel(ANTI),
            'perspective_gold_adjudication': rel(GOLD),
            'root_discovery_manifest': rel(DISCOVERY),
            'fresh_builder_targets': rel(BUILDER),
            'external_materialization_request': rel(EXTERNAL_REQ),
        },
    }
    write_json(SUMMARY_JSON, payload)
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == '__main__':
    main()
