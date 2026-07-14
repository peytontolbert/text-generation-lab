#!/usr/bin/env python3
from __future__ import annotations
import json, sys, time
from pathlib import Path
from typing import Any
import torch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from legacy_src.agentkernel_lite.modeling_transformer import AgentKernelLiteTransformerConfig, AgentKernelLiteTransformerSeq2Seq
from legacy_src.agentkernel_lite.training_data import AgentKernelBPETokenizer
from legacy_src.agentkernel_lite.training_loop import _load_runtime_model_bundle, _write_bounded_choice_eval_audit

ARTIFACTS = ROOT / 'runs' / 'local' / 'artifacts'
STAGE = 10953
NAME = 'stage10953_evidence_contrast_margin_postrun_audit'
OUT_DIR = ARTIFACTS / NAME
SUMMARY_JSON = OUT_DIR / 'evidence_contrast_margin_postrun_audit.json'
ROWS_JSONL = OUT_DIR / 'explicit_ledger_slice_rows.jsonl'
RUNTIME_BUNDLE = ARTIFACTS / 'stage10952_evidence_contrast_margin_probe' / 'runtime_model' / 'runtime_model_bundle.json'


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding='utf-8'))


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines() if line.strip()]


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + '\n', encoding='utf-8')


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('w', encoding='utf-8') as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + '\n')


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def now_utc() -> str:
    return time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())


def load_runtime() -> tuple[AgentKernelLiteTransformerSeq2Seq, AgentKernelBPETokenizer, dict[str, Any]]:
    bundle = load_json(RUNTIME_BUNDLE)
    metadata = bundle['metadata']
    config = AgentKernelLiteTransformerConfig.from_recovered_target_json(load_json(Path(str(metadata['model_config']))))
    model = AgentKernelLiteTransformerSeq2Seq(config)
    runtime_init = _load_runtime_model_bundle(RUNTIME_BUNDLE, model=model)
    if torch.cuda.is_available():
        model = model.to(torch.device('cuda'))
    tokenizer = AgentKernelBPETokenizer(Path(str(metadata['tokenizer_json'])), Path(str(metadata['tokenizer_config'])))
    model.eval()
    return model, tokenizer, runtime_init


def summarize_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    if not rows:
        return {'rows': 0, 'correct': 0, 'exact_accuracy': None, 'scored_rows': 0}
    scored = [row for row in rows if row.get('constrained_choice_match') is not None]
    correct = sum(1 for row in scored if row.get('constrained_choice_match') is True)
    return {
        'rows': len(rows),
        'scored_rows': len(scored),
        'correct': correct,
        'exact_accuracy': (correct / len(scored)) if scored else None,
    }


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    model, tokenizer, runtime_init = load_runtime()
    overlay_eval = _write_bounded_choice_eval_audit(
        OUT_DIR,
        model=model,
        rows=load_jsonl(ARTIFACTS / 'stage10941_scorer_margin_support_package' / 'agentkernel_lite_encdec_validation.jsonl'),
        tokenizer=tokenizer,
        max_encoder_tokens=768,
        max_decoder_tokens=8,
        split_name='eval_raw_contract',
        bounded_choice_aux_source='encoder_option_retrieval',
        eval_batch_size=8,
    )
    overlay_strict = _write_bounded_choice_eval_audit(
        OUT_DIR,
        model=model,
        rows=load_jsonl(ARTIFACTS / 'stage10941_scorer_margin_support_package' / 'agentkernel_lite_encdec_strict_eval.jsonl'),
        tokenizer=tokenizer,
        max_encoder_tokens=768,
        max_decoder_tokens=8,
        split_name='strict_eval_raw_contract',
        bounded_choice_aux_source='encoder_option_retrieval',
        eval_batch_size=8,
    )
    fresh_rows = load_jsonl(ARTIFACTS / 'stage10938_explicit_verifier_ledger_strict_candidates' / 'strict_candidate_rows.jsonl')
    write_jsonl(ROWS_JSONL, fresh_rows)
    slice_card = _write_bounded_choice_eval_audit(
        OUT_DIR,
        model=model,
        rows=fresh_rows,
        tokenizer=tokenizer,
        max_encoder_tokens=768,
        max_decoder_tokens=8,
        split_name='explicit_ledger_candidate_slice',
        bounded_choice_aux_source='encoder_option_retrieval',
        eval_batch_size=8,
    )
    baseline_slice = load_json(ARTIFACTS / 'stage10950_evidence_role_map_aux_postrun_audit' / 'evidence_role_map_aux_postrun_audit.json')
    slice_rows = slice_card.get('row_cards') or []
    baseline_rows = {str(row.get('row_id')): row for row in ((baseline_slice.get('explicit_ledger_slice') or {}).get('rows') or [])}
    compared_rows = []
    for row in slice_rows:
        row_id = str(row.get('row_id'))
        prior = baseline_rows.get(row_id, {})
        compared_rows.append({
            'row_id': row_id,
            'language_family': row.get('language_family'),
            'target_text': row.get('bounded_choice_target_label'),
            'target_value': next((opt.get('value') for opt in row.get('options', []) if opt.get('label') == row.get('bounded_choice_target_label')), None),
            'baseline_constrained_choice_top1_label': prior.get('baseline_constrained_choice_top1_label') or prior.get('new_constrained_choice_top1_label') or prior.get('constrained_choice_top1_label'),
            'baseline_constrained_choice_match': prior.get('baseline_constrained_choice_match') if 'baseline_constrained_choice_match' in prior else prior.get('constrained_choice_match'),
            'baseline_target_rank_full_vocab': prior.get('baseline_target_rank_full_vocab') if 'baseline_target_rank_full_vocab' in prior else prior.get('target_rank_full_vocab'),
            'new_constrained_choice_top1_label': row.get('constrained_choice_top1_label'),
            'new_constrained_choice_match': row.get('constrained_choice_match'),
            'new_target_rank_full_vocab': row.get('target_rank_full_vocab'),
            'gemma12b_predicted_label': prior.get('gemma12b_predicted_label'),
            'gemma12b_correct': prior.get('gemma12b_correct'),
        })
    payload = {
        'stage': STAGE,
        'stage_name': NAME,
        'created_at_utc': now_utc(),
        'passed': True,
        'claim_scope': [
            'Audit the direct evidence-contrast margin runtime against the unchanged raw-contract overlay and the explicit-ledger 3-row candidate slice.',
            'Keep evaluation on encoder_option_retrieval raw value scoring so any gain reflects direct scorer/objective shaping rather than an interface swap.',
        ],
        'runtime_bundle': rel(RUNTIME_BUNDLE),
        'runtime_initialization': runtime_init,
        'overlay': {
            'eval_accuracy': overlay_eval.get('constrained_choice_top1_accuracy'),
            'eval_miss_rows': [str(row.get('row_id')) for row in (overlay_eval.get('row_cards') or []) if row.get('constrained_choice_match') is not True],
            'strict_accuracy': overlay_strict.get('constrained_choice_top1_accuracy'),
            'strict_miss_rows': [str(row.get('row_id')) for row in (overlay_strict.get('row_cards') or []) if row.get('constrained_choice_match') is not True],
        },
        'explicit_ledger_slice': {
            'baseline_overall': ((baseline_slice.get('explicit_ledger_slice') or {}).get('overall') or {}),
            'overall': summarize_rows(slice_rows),
            'by_language': {
                language: summarize_rows([row for row in slice_rows if str(row.get('language_family') or 'unknown') == language])
                for language in sorted({str(row.get('language_family') or 'unknown') for row in slice_rows})
            },
            'rows': compared_rows,
        },
        'findings': [
            'A positive result requires raw-contract improvement beyond stage10944/stage10950 on the explicit-ledger slice without any new overlay regressions.',
            'If raw-contract behavior still does not move, the next repair must change scorer architecture or training row geometry rather than objective weights alone.',
        ],
        'outputs': {
            'summary_json': rel(SUMMARY_JSON),
            'slice_rows_jsonl': rel(ROWS_JSONL),
            'slice_audit_json': rel(OUT_DIR / 'explicit_ledger_candidate_slice_bounded_choice_eval.json'),
        },
    }
    write_json(SUMMARY_JSON, payload)
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == '__main__':
    main()
