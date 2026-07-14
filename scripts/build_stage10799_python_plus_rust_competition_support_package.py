#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / 'runs' / 'local' / 'artifacts'
STAGE = 10799
NAME = 'stage10799_python_plus_rust_competition_support_package'
OUT_DIR = ARTIFACTS / NAME
SUMMARY_JSON = OUT_DIR / 'python_plus_rust_competition_support_package.json'
SUPPORT_ROWS_JSONL = OUT_DIR / 'support_rows.jsonl'
TRAIN_ROWS_JSONL = OUT_DIR / 'agentkernel_lite_encdec_train.jsonl'
VALIDATION_ROWS_JSONL = OUT_DIR / 'agentkernel_lite_encdec_validation.jsonl'
STRICT_ROWS_JSONL = OUT_DIR / 'agentkernel_lite_encdec_strict_eval.jsonl'
STRESS_ROWS_JSONL = OUT_DIR / 'agentkernel_lite_encdec_stress_eval.jsonl'
SUMMARY_CARD = ROOT / 'runs' / 'summaries' / f'{NAME}.json'

BASE_PACKAGE = ARTIFACTS / 'stage10794_deleaked_python_overflow_support_package' / 'deleaked_python_overflow_support_package.json'
BASE_SUPPORT = ARTIFACTS / 'stage10794_deleaked_python_overflow_support_package' / 'support_rows.jsonl'
BASE_TRAIN = ARTIFACTS / 'stage10794_deleaked_python_overflow_support_package' / 'agentkernel_lite_encdec_train.jsonl'
BASE_VALIDATION = ARTIFACTS / 'stage10794_deleaked_python_overflow_support_package' / 'agentkernel_lite_encdec_validation.jsonl'
BASE_STRICT = ARTIFACTS / 'stage10794_deleaked_python_overflow_support_package' / 'agentkernel_lite_encdec_strict_eval.jsonl'
BASE_STRESS = ARTIFACTS / 'stage10794_deleaked_python_overflow_support_package' / 'agentkernel_lite_encdec_stress_eval.jsonl'
RUST_SUPPORT = ARTIFACTS / 'stage10798_rust_chroma_citation_repair_packet' / 'support_rows.jsonl'


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


def write_json(path: Path, payload: Any) -> None:
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
    base_package = load_json(BASE_PACKAGE)
    base_support = load_jsonl(BASE_SUPPORT)
    base_train = load_jsonl(BASE_TRAIN)
    base_validation = load_jsonl(BASE_VALIDATION)
    base_strict = load_jsonl(BASE_STRICT)
    base_stress = load_jsonl(BASE_STRESS)
    rust_support = load_jsonl(RUST_SUPPORT)

    support_rows = list(base_support) + list(rust_support)
    support_row_ids = [str(row['row_id']) for row in support_rows]
    duplicate_support_ids = [row_id for row_id, count in Counter(support_row_ids).items() if count > 1]
    if duplicate_support_ids:
        raise SystemExit(f'duplicate support row ids detected: {duplicate_support_ids}')

    train_row_ids = {str(row['row_id']) for row in base_train}
    rust_row_ids = {str(row['row_id']) for row in rust_support}
    duplicate_train_overlap = sorted(train_row_ids.intersection(rust_row_ids))
    if duplicate_train_overlap:
        raise SystemExit(f'rust support rows already present in base train rows: {duplicate_train_overlap[:5]}')

    merged_train = list(base_train) + list(rust_support)

    payload = {
        'stage': STAGE,
        'stage_name': NAME,
        'created_at_utc': now_utc(),
        'passed': True,
        'decision': 'python_plus_rust_competition_support_package_ready',
        'claim_scope': [
            'Extend the clean de-leaked Python-expanded package with the first explicit Rust citation-vs-candidate-surface repair rows.',
            'Keep validation, strict, and stress rows unchanged from the honest reviewed v2.7 frontier while broadening support on the live Rust failure mode.',
            'Preserve support-only scope; this merged package is still non-promotable and only exists for the next diagnostic probe.',
        ],
        'metrics': {
            'base_support_rows': len(base_support),
            'rust_competition_support_rows': len(rust_support),
            'merged_support_rows': len(support_rows),
            'base_train_rows': len(base_train),
            'merged_train_rows': len(merged_train),
            'validation_rows': len(base_validation),
            'strict_rows': len(base_strict),
            'stress_rows': len(base_stress),
            'support_languages': dict(sorted(Counter(str(row.get('language_family') or 'unknown') for row in support_rows).items())),
            'train_languages': dict(sorted(Counter(str(row.get('language_family') or 'unknown') for row in merged_train).items())),
        },
        'headline_findings': [
            'The widened Python support remains intact and leak-clean while the first Rust competition-repair rows are added on top.',
            'The added Rust rows explicitly contrast changed-surface evidence with verifier-anchor evidence and abstention.',
            'This package is the first mixed-support successor after the clean Python plateau at 22/24.',
        ],
        'next_best_step': 'Run a package-level leak audit; if it passes, issue the next mixed Python-plus-Rust support probe request from this package.',
        'source_artifacts': {
            'base_package': display(BASE_PACKAGE),
            'base_support_rows': display(BASE_SUPPORT),
            'rust_support_rows': display(RUST_SUPPORT),
            'base_package_metrics': base_package.get('metrics'),
        },
        'outputs': {
            'summary_json': display(SUMMARY_JSON),
            'support_rows': display(SUPPORT_ROWS_JSONL),
            'train_rows': display(TRAIN_ROWS_JSONL),
            'validation_rows': display(VALIDATION_ROWS_JSONL),
            'strict_rows': display(STRICT_ROWS_JSONL),
            'stress_rows': display(STRESS_ROWS_JSONL),
        },
    }

    write_jsonl(SUPPORT_ROWS_JSONL, support_rows)
    write_jsonl(TRAIN_ROWS_JSONL, merged_train)
    write_jsonl(VALIDATION_ROWS_JSONL, base_validation)
    write_jsonl(STRICT_ROWS_JSONL, base_strict)
    write_jsonl(STRESS_ROWS_JSONL, base_stress)
    write_json(SUMMARY_JSON, payload)
    write_json(SUMMARY_CARD, {
        'stage': STAGE,
        'passed': True,
        'decision': payload['decision'],
        'merged_support_rows': len(support_rows),
        'rust_competition_support_rows': len(rust_support),
    })
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == '__main__':
    main()
