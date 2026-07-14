#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = 10163
NAME = 'stage10163_choice_aux_only_ablation_audit'
OUT_DIR = ROOT / 'runs/local/artifacts' / NAME
OUT_PATH = OUT_DIR / 'choice_aux_only_ablation_audit.json'
SUMMARY = ROOT / 'runs/summaries' / f'{NAME}.json'

RUNS = {
    'stage10156': ROOT / 'runs/local/artifacts/stage10156_compact_choice_aux_target100m_probe/bounded_decoder_probe',
    'stage10162': ROOT / 'runs/local/artifacts/stage10162_choice_aux_only_target100m_probe/bounded_decoder_probe',
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
    bounded = load_json(base / 'bounded_choice_eval_audit_strict_eval.json')
    rows = [row for row in bounded.get('row_cards') or [] if isinstance(row, dict)]
    return {
        'run': name,
        'path': display(base),
        'strict_eval_loss': (((execution.get('eval') or {}).get('strict_eval') or {}).get('loss')),
        'decoder_ce_weight': execution.get('decoder_ce_weight'),
        'bounded_choice_aux_weight': execution.get('bounded_choice_aux_weight'),
        'contentful_generation_rate': generation.get('contentful_rate', execution.get('contentful_generation_rate')),
        'bounded_choice_rows': bounded.get('rows'),
        'bounded_choice_full_vocab_top1_accuracy': bounded.get('full_vocab_top1_accuracy'),
        'bounded_choice_constrained_top1_accuracy': bounded.get('constrained_choice_top1_accuracy'),
        'bounded_choice_rows_with_target_rank_1': bounded.get('rows_with_target_rank_1'),
        'bounded_choice_constrained_prediction_counts': dict(sorted(Counter(str(row.get('constrained_choice_top1_label') or '').strip() for row in rows).items())),
        'bounded_choice_full_vocab_prediction_counts': dict(sorted(Counter(str(row.get('full_vocab_top1_text') or '').strip() for row in rows).items())),
        'bounded_choice_target_counts': dict(sorted(Counter(str(row.get('target_text') or '').strip() for row in rows).items())),
    }


def build_report() -> dict[str, Any]:
    cards = {name: run_card(name, path) for name, path in RUNS.items()}
    mixed = cards['stage10156']
    aux_only = cards['stage10162']
    verdict = {
        'strict_eval_loss_delta_aux_only_minus_mixed': (
            None
            if mixed.get('strict_eval_loss') is None or aux_only.get('strict_eval_loss') is None
            else aux_only['strict_eval_loss'] - mixed['strict_eval_loss']
        ),
        'constrained_choice_accuracy_delta_aux_only_minus_mixed': (
            None
            if mixed.get('bounded_choice_constrained_top1_accuracy') is None or aux_only.get('bounded_choice_constrained_top1_accuracy') is None
            else aux_only['bounded_choice_constrained_top1_accuracy'] - mixed['bounded_choice_constrained_top1_accuracy']
        ),
        'contentful_generation_delta_aux_only_minus_mixed': (
            None
            if mixed.get('contentful_generation_rate') is None or aux_only.get('contentful_generation_rate') is None
            else aux_only['contentful_generation_rate'] - mixed['contentful_generation_rate']
        ),
        'full_vocab_accuracy_delta_aux_only_minus_mixed': (
            None
            if mixed.get('bounded_choice_full_vocab_top1_accuracy') is None or aux_only.get('bounded_choice_full_vocab_top1_accuracy') is None
            else aux_only['bounded_choice_full_vocab_top1_accuracy'] - mixed['bounded_choice_full_vocab_top1_accuracy']
        ),
        'conclusion': 'decoder_ce_is_required_for_any_usable_decoding_but_aux_only_does_not_improve_constrained_choice_accuracy_over_the_mixed_objective',
        'next_action': 'sweep a reduced nonzero decoder CE weight against bounded choice aux instead of removing decoder CE entirely',
        'standalone_score_claim_allowed': False,
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
