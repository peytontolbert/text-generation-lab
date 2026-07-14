#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / 'runs/local/artifacts'
STAGE = 11331
NAME = 'stage11331_rust_web_gap_recovery_manifest'
OUT = ART / NAME
SUMMARY = OUT / 'rust_web_gap_recovery_manifest.json'
RUST_ADMITTED = ART / 'stage11194_rust_replacement_admission_audit/admitted_rust_replacement_rows.jsonl'
RUST_BLOCKED = ART / 'stage11194_rust_replacement_admission_audit/blocked_rust_replacement_rows.jsonl'
STAGE11237_READY = ART / 'stage11237_multilingual_verifier_constraint_source_inventory/verifier_constraint_source_candidates.jsonl'
STAGE11275_BLOCKED = ART / 'stage11275_direct_retrieval_multilingual_evidence_materialization/direct_retrieval_multilingual_evidence_blocked_roots.jsonl'
STAGE11275_ROOTS = ART / 'stage11275_direct_retrieval_multilingual_evidence_materialization/direct_retrieval_multilingual_evidence_root_splits.jsonl'
OUT_RUST = OUT / 'admitted_rust_strict_replacement_rows.jsonl'
OUT_WEB_READY = OUT / 'web_ready_candidate_queue.jsonl'
OUT_BLOCKED = OUT / 'rust_web_blocked_source_queue.jsonl'


def now() -> str:
    return time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(''.join(json.dumps(row, sort_keys=True) + '\n' for row in rows))


def write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, sort_keys=True) + '\n')


def lang(row: dict[str, Any]) -> str:
    return str(row.get('language_family') or row.get('language') or 'unknown')


def root_id(row: dict[str, Any]) -> str:
    return str(row.get('root_id') or row.get('source_root_id') or row.get('source_row_id') or row.get('row_id') or '')


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    rust_admitted = [r for r in read_jsonl(RUST_ADMITTED) if lang(r) == 'rust']
    rust_blocked = [r for r in read_jsonl(RUST_BLOCKED) if lang(r) == 'rust']
    ready = [r for r in read_jsonl(STAGE11237_READY) if lang(r) in {'rust', 'web_js_ts_html'}]
    direct_roots = [r for r in read_jsonl(STAGE11275_ROOTS) if lang(r) in {'rust', 'web_js_ts_html'}]
    blocked = [r for r in read_jsonl(STAGE11275_BLOCKED) if lang(r) in {'rust', 'web_js_ts_html'}]

    direct_source_ids = {str(r.get('source_row_id')) for r in direct_roots}
    web_ready = []
    rust_ready_not_direct = []
    for row in ready:
        item = dict(row)
        item['already_materialized_in_stage11275'] = str(row.get('source_row_id')) in direct_source_ids
        item['recommended_action'] = (
            'materialize_web_alias_free_verifier_change_pair'
            if lang(row) == 'web_js_ts_html' and not item['already_materialized_in_stage11275']
            else 'already_covered_or_insufficient_for_new_train'
        )
        if lang(row) == 'web_js_ts_html':
            web_ready.append(item)
        elif lang(row) == 'rust' and not item['already_materialized_in_stage11275']:
            rust_ready_not_direct.append(item)

    blocked_queue = []
    for row in blocked:
        item = dict(row)
        item['recovery_requirement'] = 'needs concrete local changed+verifier evidence pair before row construction'
        item['usable_for_training_now'] = False
        blocked_queue.append(item)

    write_jsonl(OUT_RUST, rust_admitted)
    write_jsonl(OUT_WEB_READY, web_ready)
    write_jsonl(OUT_BLOCKED, blocked_queue)

    summary = {
        'stage': STAGE,
        'stage_name': NAME,
        'created_at_utc': now(),
        'passed': True,
        'decision': 'rust_web_gap_recovery_manifest_ready',
        'counts': {
            'admitted_rust_strict_replacement_rows': len(rust_admitted),
            'blocked_rust_replacement_rows': len(rust_blocked),
            'stage11237_ready_rust_web_candidates': len(ready),
            'stage11237_ready_by_language': dict(sorted(Counter(lang(r) for r in ready).items())),
            'stage11275_already_materialized_rust_web_roots': len(direct_roots),
            'stage11275_materialized_by_language': dict(sorted(Counter(lang(r) for r in direct_roots).items())),
            'stage11275_blocked_rust_web_roots': len(blocked),
            'stage11275_blocked_by_language': dict(sorted(Counter(lang(r) for r in blocked).items())),
            'web_ready_candidates': len(web_ready),
            'web_ready_not_already_materialized': sum(1 for r in web_ready if not r.get('already_materialized_in_stage11275')),
            'rust_ready_not_already_materialized': len(rust_ready_not_direct),
        },
        'admissibility': {
            'rust_rows_trainable_now': False,
            'rust_rows_scoreable_as_reserved_strict_replacements': bool(rust_admitted),
            'web_rows_trainable_now': False,
            'reason': 'Rust replacements are admitted but explicitly not train support; Web ready candidates still need materialized alias-free verifier/change rows before training.',
        },
        'blocked_reasons': {
            'stage11275_blocked': Counter(tuple(r.get('blockers') or []) for r in blocked).most_common(20),
            'rust_replacement_blocked': Counter(tuple(r.get('blockers') or []) for r in rust_blocked).most_common(20),
        },
        'source_artifacts': {
            'rust_admitted': rel(RUST_ADMITTED),
            'rust_blocked': rel(RUST_BLOCKED),
            'stage11237_ready': rel(STAGE11237_READY),
            'stage11275_blocked': rel(STAGE11275_BLOCKED),
            'stage11275_roots': rel(STAGE11275_ROOTS),
        },
        'outputs': {
            'summary': rel(SUMMARY),
            'admitted_rust_strict_replacement_rows': rel(OUT_RUST),
            'web_ready_candidate_queue': rel(OUT_WEB_READY),
            'rust_web_blocked_source_queue': rel(OUT_BLOCKED),
        },
        'recommended_next_action': 'materialize alias-free Web evidence rows from web_ready_candidate_queue; keep admitted Rust rows as reserved strict replacements, not train support, unless separately duplicated from disjoint Rust roots.',
    }
    write_json(SUMMARY, summary)
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == '__main__':
    main()
