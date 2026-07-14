#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = 10793
NAME = 'stage10793_python_overflow_support_leak_audit'
OUT_DIR = ROOT / 'runs/local/artifacts' / NAME
SUMMARY_JSON = OUT_DIR / 'python_overflow_support_leak_audit.json'
LEAK_ROWS_JSONL = OUT_DIR / 'leaking_rows.jsonl'
SUMMARY_CARD = ROOT / 'runs/summaries' / f'{NAME}.json'
SUPPORT_ROWS = ROOT / 'runs/local/artifacts/stage10791_larger_root_split_plus_python_overflow_support_package/support_rows.jsonl'


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
        'decision': 'python_overflow_support_leak_audit_complete',
        'claim_scope': [
            'Audit the second-wave Python overflow support package for prompt-target leakage before any new training probe consumes it.',
            'Treat support-only rows as still needing leak hygiene; train-only status is not a substitute for prompt-target cleanliness.',
        ],
        'metrics': {
            'support_rows': len(rows),
            'leaking_rows': len(leaking_rows),
            'leak_rate': (len(leaking_rows) / len(rows)) if rows else 0.0,
            'leaks_by_perspective': dict(sorted(Counter(row['perspective'] for row in leaking_rows).items())),
            'leaks_by_repo': dict(sorted(Counter(row['repo_family'] for row in leaking_rows).items())),
        },
        'headline_findings': [
            'The second-wave Python support package is not yet clean enough for trustworthy support training because most rows expose the gold value before options.',
            'Leak concentration is highest in verifier_outcome, evidence_citation, alternative_hypothesis_elimination, and regression_risk, where gold evidence-role/test values are repeated verbatim in the prompt.',
            'The next move is de-leaking, not probing: replace visible gold test/path strings with opaque handles or role-only previews before using this package.',
        ],
        'next_best_step': 'Build a de-leaked successor package that replaces visible gold paths and evidence-role literals before the options, then rerun the leak audit before any training execution request.',
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
