#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = 10792
NAME = 'stage10792_rust_competition_repair_queue'
OUT_DIR = ROOT / 'runs/local/artifacts' / NAME
SUMMARY_JSON = OUT_DIR / 'rust_competition_repair_queue.json'
QUEUE_JSONL = OUT_DIR / 'rust_competition_repair_queue.jsonl'
SUMMARY_CARD = ROOT / 'runs/summaries' / f'{NAME}.json'

DECISIONS_JSONL = ROOT / 'runs/local/artifacts/stage10775_bulk_multilingual_packet_ai_adjudication/packet_ai_adjudication.jsonl'


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding='utf-8'))


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open(encoding='utf-8') as handle:
        for line in handle:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + '\n', encoding='utf-8')


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('w', encoding='utf-8') as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + '\n')


def display(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def now_utc() -> str:
    return time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())


def main() -> None:
    decisions = load_jsonl(DECISIONS_JSONL)
    rust_rows = [
        row for row in decisions
        if row['language_family'] == 'rust' and row['ai_status'] == 'fresh_candidate_needs_richer_competition'
    ]
    queue_rows = []
    for row in sorted(rust_rows, key=lambda r: (int(r['queue_rank']), -int(r['priority_score']), str(r['root_id']))):
        packet_dir = ROOT / str(row['packet_dir'])
        bundle = load_json(packet_dir / 'fresh_root_bundle_preview.json')
        anti_cheat = load_json(packet_dir / 'anti_cheat_review_card.json')
        queue_rows.append({
            'root_id': row['root_id'],
            'root_lineage_key': row['root_lineage_key'],
            'repo_family': row['repo_family'],
            'queue_rank': int(row['queue_rank']),
            'priority_score': int(row['priority_score']),
            'packet_dir': str(row['packet_dir']),
            'semantic_lane': str(row.get('semantic_lane') or 'rust_verifier_anchor_and_citation_scale'),
            'required_repairs': list(row.get('required_repairs') or []),
            'changed_files_sample': list(bundle['compiled_brief_summary'].get('changed_files_sample') or []),
            'verification_targets_sample': list(bundle['compiled_brief_summary'].get('verification_targets_sample') or []),
            'key_symbols_sample': list(bundle['compiled_brief_summary'].get('key_symbols_sample') or []),
            'visible_evidence_keys': sorted((bundle.get('maintainer_visible_evidence') or {}).keys()),
            'suggested_candidate_pool_seed': anti_cheat.get('suggested_candidate_pool_seed') or {
                'changed_files_sample': list(bundle['compiled_brief_summary'].get('changed_files_sample') or []),
                'verification_targets_sample': list(bundle['compiled_brief_summary'].get('verification_targets_sample') or []),
                'key_symbols_sample': list(bundle['compiled_brief_summary'].get('key_symbols_sample') or []),
            },
            'repair_contract': {
                'must_add_explicit_citation_vs_candidate_surface_competition': True,
                'must_keep_selected_test_anchor_visible': bool(bundle['compiled_brief_summary'].get('selected_test_anchor_present')),
                'must_add_non_changed_competing_candidates': True,
                'must_avoid_single-test-singleton_shortcut': True,
                'support_only_until_repaired': True,
            },
        })
    payload = {
        'stage': STAGE,
        'stage_name': NAME,
        'created_at_utc': now_utc(),
        'passed': True,
        'decision': 'rust_competition_repair_queue_ready',
        'claim_scope': [
            'Turn the three Rust needs-richer-competition roots into an explicit repair queue rather than leaving them as vague backlog notes.',
            'Capture the visible source/test anchors and candidate-pool seeds needed for a real citation-vs-surface repair pass.',
            'Keep Rust roots out of promotable or train-support packages until the competition contract is satisfied.',
        ],
        'metrics': {
            'queued_rust_roots': len(queue_rows),
            'repos': [row['repo_family'] for row in queue_rows],
        },
        'headline_findings': [
            'Rust is blocked by competition design, not by missing source packets.',
            'All three queued roots already have verifier anchors and visible evidence keys, but the current candidate pools are too thin.',
            'The next Rust step should be a candidate-expansion/materialization pass, not another broad support probe.',
        ],
        'next_best_step': 'Build a Rust citation competition repair packet that expands each queued root into explicit citation-vs-candidate-surface options before adding any of them to train support.',
        'source_artifacts': {
            'bulk_packet_adjudication': display(DECISIONS_JSONL),
        },
        'outputs': {
            'summary_json': display(SUMMARY_JSON),
            'repair_queue': display(QUEUE_JSONL),
        },
    }
    write_jsonl(QUEUE_JSONL, queue_rows)
    write_json(SUMMARY_JSON, payload)
    write_json(SUMMARY_CARD, {
        'stage': STAGE,
        'passed': True,
        'decision': payload['decision'],
        'queued_rust_roots': len(queue_rows),
    })
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == '__main__':
    main()
