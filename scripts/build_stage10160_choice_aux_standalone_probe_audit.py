#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = 10160
NAME = 'stage10160_choice_aux_standalone_probe_audit'
OUT_DIR = ROOT / 'runs/local/artifacts' / NAME
OUT_PATH = OUT_DIR / 'choice_aux_standalone_probe_audit.json'
SUMMARY = ROOT / 'runs/summaries' / f'{NAME}.json'

RUNS = {
    'stage10148': ROOT / 'runs/local/artifacts/stage10148_compact_standalone_bounded_target100m_probe/bounded_decoder_probe',
    'stage10151': ROOT / 'runs/local/artifacts/stage10151_compact_permutation_balanced_target100m_probe/bounded_decoder_probe',
    'stage10156': ROOT / 'runs/local/artifacts/stage10156_compact_choice_aux_target100m_probe/bounded_decoder_probe',
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
    bounded = load_json(base / 'bounded_choice_eval_audit_strict_eval.json')
    rows = [row for row in generation.get('samples') or [] if isinstance(row, dict)]
    predictions = Counter(str(row.get('generated_text') or '').strip() for row in rows)
    bounded_rows = [row for row in bounded.get('row_cards') or [] if isinstance(row, dict)]
    constrained_predictions = Counter(str(row.get('constrained_choice_top1_label') or '').strip() for row in bounded_rows)
    full_vocab_predictions = Counter(str(row.get('full_vocab_top1_text') or '').strip() for row in bounded_rows)
    target_counts = Counter(str(row.get('target_text') or '').strip() for row in bounded_rows)
    return {
        'run': name,
        'path': display(base),
        'strict_eval_loss': (((execution.get('eval') or {}).get('strict_eval') or {}).get('loss')),
        'generated_rows': len(rows),
        'contentful_generation_rate': generation.get('contentful_rate', execution.get('contentful_generation_rate')),
        'short_or_junk_rate': generation.get('short_or_junk_rate', short_probe.get('short_or_junk_rate')),
        'sample_generation_prediction_counts': dict(sorted(predictions.items())),
        'bounded_choice_rows': bounded.get('rows'),
        'bounded_choice_constrained_rows': bounded.get('constrained_choice_rows'),
        'bounded_choice_full_vocab_top1_accuracy': bounded.get('full_vocab_top1_accuracy'),
        'bounded_choice_constrained_top1_accuracy': bounded.get('constrained_choice_top1_accuracy'),
        'bounded_choice_rows_with_target_rank_1': bounded.get('rows_with_target_rank_1'),
        'bounded_choice_constrained_prediction_counts': dict(sorted(constrained_predictions.items())),
        'bounded_choice_full_vocab_prediction_counts': dict(sorted(full_vocab_predictions.items())),
        'bounded_choice_target_counts': dict(sorted(target_counts.items())),
        'failure_buckets': dict(failure.get('buckets') or {}),
        'required_artifacts_written': execution.get('required_artifacts_written'),
        'bounded_choice_eval_present': bool(bounded),
        'bounded_choice_aux_weight': execution.get('bounded_choice_aux_weight'),
    }


def build_report() -> dict[str, Any]:
    cards = {name: run_card(name, path) for name, path in RUNS.items()}
    stage10148 = cards['stage10148']
    stage10151 = cards['stage10151']
    stage10156 = cards['stage10156']
    verdict = {
        'strict_eval_loss_delta_vs_stage10148': (
            None
            if stage10148.get('strict_eval_loss') is None or stage10156.get('strict_eval_loss') is None
            else stage10156['strict_eval_loss'] - stage10148['strict_eval_loss']
        ),
        'strict_eval_loss_delta_vs_stage10151': (
            None
            if stage10151.get('strict_eval_loss') is None or stage10156.get('strict_eval_loss') is None
            else stage10156['strict_eval_loss'] - stage10151['strict_eval_loss']
        ),
        'contentful_generation_recovered': (
            (stage10156.get('contentful_generation_rate') or 0.0) > 0.0
            and (stage10151.get('contentful_generation_rate') or 0.0) == 0.0
        ),
        'bounded_choice_eval_unlocked': stage10156.get('bounded_choice_eval_present', False),
        'free_generation_still_collapsed': (
            len(stage10156.get('sample_generation_prediction_counts') or {}) == 1
            and stage10156.get('generated_rows', 0) > 0
        ),
        'full_vocab_label_prior_collapse': (
            len(stage10156.get('bounded_choice_full_vocab_prediction_counts') or {}) == 1
            and stage10156.get('bounded_choice_rows', 0) > 0
        ),
        'constrained_choice_accuracy': stage10156.get('bounded_choice_constrained_top1_accuracy'),
        'standalone_score_claim_allowed': False,
        'blocked_reason': 'choice_aux_improves_loss_and_unblocks_compact_choice_outputs_but_full_vocab_decoder_remains_collapsed_to_single_label_and_constrained_accuracy_is_still_low',
        'next_action': 'reduce or remove plain decoder CE and rerun a constrained-choice-only or constrained-choice-dominant standalone probe',
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
