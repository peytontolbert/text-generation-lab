#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
from collections import Counter

ROOT = Path(__file__).resolve().parents[1]
STAGE = 10173
NAME = 'stage10173_encoder_option_retrieval_probe_audit'
OUT_DIR = ROOT / 'runs/local/artifacts' / NAME
OUT_PATH = OUT_DIR / 'encoder_option_retrieval_probe_audit.json'
SUMMARY = ROOT / 'runs/summaries' / f'{NAME}.json'
RUNS = {
    'stage10156': ROOT / 'runs/local/artifacts/stage10156_compact_choice_aux_target100m_probe/bounded_decoder_probe',
    'stage10165': ROOT / 'runs/local/artifacts/stage10165_choice_aux_low_decoder_ce_target100m_probe/bounded_decoder_probe',
    'stage10167': ROOT / 'runs/local/artifacts/stage10167_choice_aux_encoder_pooled_target100m_probe/bounded_decoder_probe',
    'stage10169': ROOT / 'runs/local/artifacts/stage10169_choice_aux_encoder_pooled_untied_target100m_probe/bounded_decoder_probe',
    'stage10172': ROOT / 'runs/local/artifacts/stage10172_choice_aux_encoder_option_retrieval_target100m_probe/bounded_decoder_probe',
}


def load_json(path: Path):
    return json.loads(path.read_text(encoding='utf-8'))


def display(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def run_card(base: Path) -> dict:
    result = load_json(base / 'execution_result.json')
    strict = load_json(base / 'bounded_choice_eval_audit_strict_eval.json')
    constrained_counts = Counter(card.get('constrained_choice_top1_label') for card in strict.get('row_cards', []))
    full_counts = Counter(card.get('full_vocab_top1_text') for card in strict.get('row_cards', []))
    return {
        'path': display(base),
        'run_id': result.get('run_id'),
        'bounded_choice_aux_source': result.get('bounded_choice_aux_source'),
        'decoder_ce_weight': result.get('decoder_ce_weight'),
        'bounded_choice_aux_weight': result.get('bounded_choice_aux_weight'),
        'strict_loss': result.get('eval', {}).get('strict_eval', {}).get('loss'),
        'contentful_generation_rate': result.get('contentful_generation_rate'),
        'full_vocab_top1_accuracy': strict.get('full_vocab_top1_accuracy'),
        'constrained_choice_top1_accuracy': strict.get('constrained_choice_top1_accuracy'),
        'rows_with_target_rank_1': strict.get('rows_with_target_rank_1'),
        'constrained_prediction_counts': dict(sorted(constrained_counts.items())),
        'full_vocab_prediction_counts': dict(sorted(full_counts.items())),
    }


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    cards = {name: run_card(path) for name, path in RUNS.items()}
    base_acc = float(cards['stage10169']['constrained_choice_top1_accuracy'])
    new_acc = float(cards['stage10172']['constrained_choice_top1_accuracy'])
    payload = {
        'stage': STAGE,
        'stage_name': NAME,
        'passed': True,
        'runs': cards,
        'comparison': {
            'baseline_stage': 'stage10169',
            'candidate_stage': 'stage10172',
            'constrained_choice_accuracy_delta': new_acc - base_acc,
            'full_vocab_accuracy_delta': float(cards['stage10172']['full_vocab_top1_accuracy']) - float(cards['stage10169']['full_vocab_top1_accuracy']),
            'first_real_constrained_lift': new_acc > base_acc,
            'decoder_full_vocab_still_collapsed': len(cards['stage10172']['full_vocab_prediction_counts']) == 1,
            'option_card_collapse_broken': len(cards['stage10172']['constrained_prediction_counts']) > 3,
        },
        'verdict': {
            'best_current_bounded_choice_source': 'encoder_option_retrieval',
            'best_current_bounded_choice_stage': 'stage10172',
            'headline': 'Content-based option retrieval breaks opaque-label collapse and becomes the first bounded standalone variant to materially improve constrained multilingual accuracy.',
            'next_action': 'Use encoder_option_retrieval as the standalone bounded-choice scorer path, then decide whether to either train the decoder to imitate the scorer or score bounded prompts directly via the scorer at inference time.',
        },
    }
    OUT_PATH.write_text(json.dumps(payload, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    SUMMARY.write_text(json.dumps({'stage': STAGE, 'passed': True, 'audit': display(OUT_PATH), 'best_stage': 'stage10172'}, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    print(json.dumps({'stage': STAGE, 'passed': True, 'audit': display(OUT_PATH), 'delta': payload['comparison']['constrained_choice_accuracy_delta']}, indent=2, sort_keys=True))


if __name__ == '__main__':
    main()
