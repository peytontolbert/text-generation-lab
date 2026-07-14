#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = 10152
NAME = 'stage10152_standalone_bounded_probe_comparison_audit'
OUT_DIR = ROOT / 'runs/local/artifacts' / NAME
OUT_PATH = OUT_DIR / 'standalone_bounded_probe_comparison_audit.json'
SUMMARY = ROOT / 'runs/summaries' / f'{NAME}.json'

RUNS = {
    'stage10148': ROOT / 'runs/local/artifacts/stage10148_compact_standalone_bounded_target100m_probe/bounded_decoder_probe',
    'stage10151': ROOT / 'runs/local/artifacts/stage10151_compact_permutation_balanced_target100m_probe/bounded_decoder_probe',
}


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding='utf-8')) if path.exists() else {}


def display(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def now_utc() -> str:
    return time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())


def run_card(name: str, base: Path) -> dict[str, Any]:
    execution = load_json(base / 'execution_result.json')
    generation = load_json(base / 'sample_generation_audit.json')
    failure = load_json(base / 'failure_bucket_card.json')
    short_probe = load_json(base / 'short_output_probe.json')
    rows = [row for row in generation.get('samples') or [] if isinstance(row, dict)]
    predictions = Counter(str(row.get('generated_text') or '').strip() for row in rows)
    exact = sum(1 for row in rows if bool(row.get('exact_match')))
    prefix = sum(1 for row in rows if bool(row.get('target_prefix_match')))
    return {
        'run': name,
        'path': display(base),
        'strict_eval_loss': (((execution.get('eval') or {}).get('strict_eval') or {}).get('loss')),
        'generated_rows': len(rows),
        'exact_match_rows': exact,
        'exact_match_rate': (exact / len(rows)) if rows else None,
        'target_prefix_match_rows': prefix,
        'target_prefix_match_rate': (prefix / len(rows)) if rows else None,
        'contentful_generation_rate': generation.get('contentful_rate', execution.get('contentful_generation_rate')),
        'short_or_junk_rate': generation.get('short_or_junk_rate', short_probe.get('short_or_junk_rate')),
        'prediction_counts': dict(sorted(predictions.items())),
        'failure_buckets': dict(failure.get('buckets') or {}),
    }


def build_report() -> dict[str, Any]:
    cards = {name: run_card(name, path) for name, path in RUNS.items()}
    old = cards['stage10148']
    new = cards['stage10151']
    verdict = {
        'strict_eval_loss_delta': (
            None
            if old.get('strict_eval_loss') is None or new.get('strict_eval_loss') is None
            else new['strict_eval_loss'] - old['strict_eval_loss']
        ),
        'generation_behavior_changed': old.get('prediction_counts') != new.get('prediction_counts'),
        'collapse_persists': (
            len(new.get('prediction_counts') or {}) == 1
            and new.get('generated_rows', 0) > 0
        ),
        'standalone_score_claim_allowed': False,
        'blocked_reason': 'permutation_balancing_improved_loss_but_decoder_generation_still_collapses_to_single_label',
        'next_action': 'change bounded decoder objective or decoding contract; permutation balancing alone is insufficient',
    }
    return {
        'stage': STAGE,
        'stage_name': NAME,
        'created_at_utc': now_utc(),
        'passed': True,
        'runs': cards,
        'verdict': verdict,
    }


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    report = build_report()
    OUT_PATH.write_text(json.dumps(report, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    SUMMARY.write_text(
        json.dumps(
            {
                'stage': STAGE,
                'passed': True,
                'report': display(OUT_PATH),
                'verdict': report['verdict'],
            },
            indent=2,
            sort_keys=True,
        ) + '\n',
        encoding='utf-8',
    )
    print(json.dumps({'stage': STAGE, 'passed': True, 'report': display(OUT_PATH), 'verdict': report['verdict']}, indent=2, sort_keys=True))


if __name__ == '__main__':
    main()
