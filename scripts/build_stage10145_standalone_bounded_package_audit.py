#!/usr/bin/env python3
from __future__ import annotations

import json
import statistics
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = 10145
NAME = 'stage10145_standalone_bounded_package_audit'
OUT_DIR = ROOT / 'runs/local/artifacts' / NAME
OUT_PATH = OUT_DIR / 'standalone_bounded_package_audit.json'
SUMMARY = ROOT / 'runs/summaries' / f'{NAME}.json'
PACKAGE = ROOT / 'runs/local/artifacts/stage10144_v27_standalone_bounded_maintainer_bundle_package/standalone_bounded_maintainer_bundle_package.json'


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding='utf-8')) if path.exists() else {}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = []
    if not path.exists():
        return rows
    with path.open(encoding='utf-8') as handle:
        for line in handle:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def display(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def now_utc() -> str:
    return time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())


def bundle_id(row: dict[str, Any]) -> str:
    return str(row.get('source_bundle_id') or '')


def label_counter(rows: list[dict[str, Any]]) -> dict[str, int]:
    counts = Counter()
    for row in rows:
        counts[str(row.get('target_text') or '')] += 1
    return dict(sorted(counts.items()))


def prompt_lengths(rows: list[dict[str, Any]]) -> dict[str, Any]:
    lengths = [len(str(row.get('prompt_text') or '')) for row in rows]
    if not lengths:
        return {'min': 0, 'median': 0, 'max': 0, 'mean': 0.0}
    return {
        'min': min(lengths),
        'median': int(statistics.median(lengths)),
        'max': max(lengths),
        'mean': round(sum(lengths) / len(lengths), 2),
    }


def build_audit() -> dict[str, Any]:
    package = load_json(PACKAGE)
    train_path = ROOT / str(package.get('train_dataset_path') or '')
    eval_path = ROOT / str(package.get('eval_dataset_path') or '')
    train_rows = load_jsonl(train_path)
    eval_rows = load_jsonl(eval_path)
    train_bundles = {bundle_id(row) for row in train_rows}
    eval_bundles = {bundle_id(row) for row in eval_rows}
    overlap = sorted(train_bundles & eval_bundles)
    by_language: dict[str, dict[str, Any]] = {}
    for language in sorted({str(row.get('language_family') or '') for row in train_rows + eval_rows}):
        train_lang = [row for row in train_rows if str(row.get('language_family') or '') == language]
        eval_lang = [row for row in eval_rows if str(row.get('language_family') or '') == language]
        by_language[language] = {
            'train_rows': len(train_lang),
            'strict_eval_rows': len(eval_lang),
            'train_bundles': sorted({bundle_id(row) for row in train_lang}),
            'strict_eval_bundles': sorted({bundle_id(row) for row in eval_lang}),
            'train_label_counts': label_counter(train_lang),
            'strict_eval_label_counts': label_counter(eval_lang),
        }
    anti_cheat = {
        'bundle_split_no_overlap': not overlap,
        'freeform_rows_excluded': all(str(row.get('objective_family') or '') == 'bounded_decoder_ce' for row in train_rows + eval_rows),
        'opaque_labels_only': all(len(str(row.get('target_text') or '')) == 1 for row in train_rows + eval_rows),
        'decoder_contract_gate_required': True,
        'train_eval_bundle_overlap': overlap,
    }
    readiness = {
        'fit_for_standalone_decoder_ce_training': bool(train_rows and eval_rows),
        'fit_for_primary_maintainer_leaderboard': False,
        'next_required_gate': 'stage10142_standalone_decoder_contract_audit must flip to allowed after training before standalone score claims',
    }
    return {
        'stage': STAGE,
        'stage_name': NAME,
        'created_at_utc': now_utc(),
        'source_package': display(PACKAGE),
        'passed': anti_cheat['bundle_split_no_overlap'] and anti_cheat['freeform_rows_excluded'] and anti_cheat['opaque_labels_only'],
        'metrics': {
            'train_rows': len(train_rows),
            'strict_eval_rows': len(eval_rows),
            'train_bundles': len(train_bundles),
            'strict_eval_bundles': len(eval_bundles),
            'language_count': len(by_language),
        },
        'prompt_length_stats': {
            'train': prompt_lengths(train_rows),
            'strict_eval': prompt_lengths(eval_rows),
        },
        'anti_cheat': anti_cheat,
        'readiness': readiness,
        'by_language': by_language,
    }


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    audit = build_audit()
    OUT_PATH.write_text(json.dumps(audit, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    SUMMARY.write_text(json.dumps({'stage': STAGE, 'passed': audit['passed'], 'artifact': display(OUT_PATH), 'metrics': audit['metrics'], 'anti_cheat': audit['anti_cheat']}, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    print(json.dumps({'stage': STAGE, 'passed': audit['passed'], 'artifact': display(OUT_PATH), 'metrics': audit['metrics'], 'anti_cheat': audit['anti_cheat']}, indent=2, sort_keys=True))


if __name__ == '__main__':
    main()
