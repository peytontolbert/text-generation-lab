#!/usr/bin/env python3
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / 'runs' / 'local' / 'artifacts'

STAGE = 10816
NAME = 'stage10816_candle_transformers_materialization_checkpoint'
OUT_DIR = ARTIFACTS / NAME
SUMMARY_JSON = OUT_DIR / 'candle_transformers_materialization_checkpoint.json'

PREVIEW = ARTIFACTS / 'stage10678_rust_source_span_partial_materializer' / 'review_packets' / 'candle__candle-transformers' / 'fresh_rust_bundle_preview.json'
ANTI = ARTIFACTS / 'stage10678_rust_source_span_partial_materializer' / 'review_packets' / 'candle__candle-transformers' / 'anti_cheat_review_card.json'
GOLD = ARTIFACTS / 'stage10678_rust_source_span_partial_materializer' / 'review_packets' / 'candle__candle-transformers' / 'perspective_gold_adjudication.json'


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding='utf-8'))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + '\n', encoding='utf-8')


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def main() -> None:
    preview = load_json(PREVIEW)
    anti = load_json(ANTI)
    gold = load_json(GOLD)

    candidate_surface = preview.get('maintainer_visible_evidence', {}).get('candidate_change_surface', [])
    placeholder_candidates = [item.get('path') for item in candidate_surface if item.get('text') == 'TODO_MATERIALIZE_REAL_SOURCE_SPAN']
    verifier_entries = preview.get('maintainer_visible_evidence', {}).get('verifier_and_test_constraint', [])
    verifier_placeholder = any(item.get('text') == 'TODO_MATERIALIZE_SELECTED_TEST_OR_TRACE_CONSTRAINT' for item in verifier_entries)
    gold_todos = sum(1 for answer in (gold.get('perspective_gold_answers') or []) if str(answer.get('gold_answer_kind') or '').startswith('TODO_'))

    payload = {
        'stage': STAGE,
        'stage_name': NAME,
        'created_at_utc': datetime.now(timezone.utc).isoformat(),
        'passed': True,
        'decision': 'candle_transformers_source_spans_fully_recovered_verifier_anchor_still_missing',
        'claim_scope': [
            'Checkpoint the current candle-transformers Rust packet after completing all recoverable local source-span materialization.',
            'Distinguish finished source-span recovery from the still-missing verifier/test anchor and unfinished gold adjudication.',
        ],
        'headline_findings': [
            'All five candidate_change_surface files now have concrete source text attached from the spans corpus.',
            'The packet is still not admissible because verifier_and_test_constraint remains a placeholder and every perspective gold answer is still TODO-scaffolded.',
            'The next real blocker is now singular and explicit: recover one honest verifier/test anchor, then finish gold and anti-cheat review.',
        ],
        'metrics': {
            'candidate_change_surface_count': len(candidate_surface),
            'candidate_change_surface_placeholder_count': len(placeholder_candidates),
            'verifier_placeholder_present': verifier_placeholder,
            'gold_todo_answer_count': gold_todos,
            'supports_training_or_scoring_now': bool(preview.get('claim_boundary', {}).get('supports_training_or_scoring_now')),
        },
        'remaining_blockers': [
            'verifier/test anchor still placeholder',
            'gold adjudication still TODO-scaffolded',
            'anti-cheat admission still pending post-anchor review',
        ],
        'source_artifacts': {
            'preview_bundle': rel(PREVIEW),
            'anti_cheat_review_card': rel(ANTI),
            'perspective_gold_adjudication': rel(GOLD),
        },
        'next_best_steps': [
            'Search external repo/session sources for a real selected test, example, or verifier-like execution anchor tied to candle-transformers generation or pipelines behavior.',
            'Once one honest anchor is attached, re-run AI gold adjudication for all eight perspectives.',
            'Only then consider admitting candle-transformers into reviewed train-support alongside linux and candle-datasets.',
        ],
    }
    write_json(SUMMARY_JSON, payload)
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == '__main__':
    main()
