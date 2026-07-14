#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = 10795
NAME = 'stage10795_deleaked_python_overflow_support_leak_audit'
OUT_DIR = ROOT / 'runs/local/artifacts' / NAME
SUMMARY_JSON = OUT_DIR / 'deleaked_python_overflow_support_leak_audit.json'
LEAK_ROWS_JSONL = OUT_DIR / 'leaking_rows.jsonl'
SUMMARY_CARD = ROOT / 'runs/summaries' / f'{NAME}.json'
SUPPORT_ROWS = ROOT / 'runs/local/artifacts/stage10794_deleaked_python_overflow_support_package/support_rows.jsonl'


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
    rows = load_jsonl(SUPPORT_ROWS)
    leaking_rows = []
    for row in rows:
        prompt = str(row.get('prompt_text') or row.get('input_text') or '')
        pre_options = prompt.split('Options:\n')[0]
        gold_value = str(row.get('gold_value') or '')
        if gold_value and gold_value != 'ABSTAIN_INSUFFICIENT_EVIDENCE' and gold_value in pre_options:
            leaking_rows.append({
                'row_id': row['row_id'],
                'repo_family': row['repo_family'],
                'perspective': row['perspective'],
                'gold_value': gold_value,
                'source_row_id': row['source_row_id'],
            })
    payload = {
        'stage': STAGE,
        'stage_name': NAME,
        'created_at_utc': now_utc(),
        'passed': len(leaking_rows) == 0,
        'decision': 'deleaked_python_overflow_support_leak_audit_complete',
        'claim_scope': [
            'Verify that the de-leaked successor to the Python overflow support package no longer exposes the exact gold value before the options.',
            'Use the same exact-string pre-options leak criterion as stage10793 so results are directly comparable.',
        ],
        'metrics': {
            'support_rows': len(rows),
            'leaking_rows': len(leaking_rows),
            'leak_rate': (len(leaking_rows) / len(rows)) if rows else 0.0,
            'leaks_by_perspective': dict(sorted(Counter(row['perspective'] for row in leaking_rows).items())),
            'leaks_by_repo': dict(sorted(Counter(row['repo_family'] for row in leaking_rows).items())),
        },
        'headline_findings': [
            'This audit is the hard gate for whether the de-leaked Python overflow package can be used in the next support-only probe.',
            'A zero-leak result means the exact gold strings no longer appear before the option set, though broader semantic anti-cheat review can still continue separately.',
        ],
        'next_best_step': 'If this passes, use stage10794 instead of stage10791 for the next support-only probe request; if it fails, de-leak again before training.',
        'source_artifacts': {
            'support_rows': display(SUPPORT_ROWS),
        },
        'outputs': {
            'summary_json': display(SUMMARY_JSON),
            'leaking_rows': display(LEAK_ROWS_JSONL),
        },
    }
    write_jsonl(LEAK_ROWS_JSONL, leaking_rows)
    write_json(SUMMARY_JSON, payload)
    write_json(SUMMARY_CARD, {
        'stage': STAGE,
        'passed': payload['passed'],
        'decision': payload['decision'],
        'leaking_rows': len(leaking_rows),
    })
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == '__main__':
    main()
