#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = 10170
NAME = 'stage10170_encoder_pooled_probe_audit'
OUT_DIR = ROOT / 'runs/local/artifacts' / NAME
OUT_PATH = OUT_DIR / 'encoder_pooled_probe_audit.json'
SUMMARY = ROOT / 'runs/summaries' / f'{NAME}.json'

RUNS = {
    'stage10156': ROOT / 'runs/local/artifacts/stage10156_compact_choice_aux_target100m_probe/bounded_decoder_probe',
    'stage10165': ROOT / 'runs/local/artifacts/stage10165_choice_aux_low_decoder_ce_target100m_probe/bounded_decoder_probe',
    'stage10167': ROOT / 'runs/local/artifacts/stage10167_choice_aux_encoder_pooled_target100m_probe/bounded_decoder_probe',
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
    bounded = load_json(base / 'bounded_choice_eval_audit_strict_eval.json')
    generation = load_json(base / 'sample_generation_audit.json')
    rows = [row for row in bounded.get('row_cards') or [] if isinstance(row, dict)]
    return {
        'run': name,
        'path': display(base),
        'strict_eval_loss': (((execution.get('eval') or {}).get('strict_eval') or {}).get('loss')),
        'decoder_ce_weight': execution.get('decoder_ce_weight'),
        'bounded_choice_aux_weight': execution.get('bounded_choice_aux_weight'),
        'bounded_choice_aux_source': execution.get('bounded_choice_aux_source'),
        'contentful_generation_rate': generation.get('contentful_rate', execution.get('contentful_generation_rate')),
        'bounded_choice_rows': bounded.get('rows'),
        'bounded_choice_full_vocab_top1_accuracy': bounded.get('full_vocab_top1_accuracy'),
        'bounded_choice_constrained_top1_accuracy': bounded.get('constrained_choice_top1_accuracy'),
        'bounded_choice_rows_with_target_rank_1': bounded.get('rows_with_target_rank_1'),
        'bounded_choice_constrained_prediction_counts': dict(sorted(Counter(str(row.get('constrained_choice_top1_label') or '').strip() for row in rows).items())),
        'bounded_choice_full_vocab_prediction_counts': dict(sorted(Counter(str(row.get('full_vocab_top1_text') or '').strip() for row in rows).items())),
    }


def build_report() -> dict[str, Any]:
    cards = {name: run_card(name, path) for name, path in RUNS.items()}
    baseline = cards['stage10156']
    low_ce = cards['stage10165']
    pooled = cards['stage10167']
    verdict = {
        'low_decoder_ce_improves_loss_not_accuracy': (
            low_ce.get('strict_eval_loss') is not None
            and baseline.get('strict_eval_loss') is not None
            and low_ce['strict_eval_loss'] < baseline['strict_eval_loss']
            and low_ce.get('bounded_choice_constrained_top1_accuracy') == baseline.get('bounded_choice_constrained_top1_accuracy')
        ),
        'encoder_pooled_changes_prior_not_accuracy': (
            pooled.get('bounded_choice_constrained_top1_accuracy') == low_ce.get('bounded_choice_constrained_top1_accuracy')
            and pooled.get('bounded_choice_constrained_prediction_counts') != low_ce.get('bounded_choice_constrained_prediction_counts')
        ),
        'full_vocab_accuracy_delta_pooled_minus_low_ce': (
            None
            if pooled.get('bounded_choice_full_vocab_top1_accuracy') is None or low_ce.get('bounded_choice_full_vocab_top1_accuracy') is None
            else pooled['bounded_choice_full_vocab_top1_accuracy'] - low_ce['bounded_choice_full_vocab_top1_accuracy']
        ),
        'rows_with_target_rank_1_delta_pooled_minus_low_ce': (
            None
            if pooled.get('bounded_choice_rows_with_target_rank_1') is None or low_ce.get('bounded_choice_rows_with_target_rank_1') is None
            else pooled['bounded_choice_rows_with_target_rank_1'] - low_ce['bounded_choice_rows_with_target_rank_1']
        ),
        'standalone_score_claim_allowed': False,
        'next_action': 'test encoder_pooled_untied_head because shared LM-token scoring still preserves opaque-label prior collapse',
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
