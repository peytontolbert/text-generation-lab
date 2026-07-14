#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import sys
import time
from collections import defaultdict
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
STAGE = 10933
NAME = 'stage10933_mixed_evidence_candidate_postrun_audit'
OUT_DIR = ARTIFACTS / NAME
SUMMARY_JSON = OUT_DIR / 'mixed_evidence_candidate_postrun_audit.json'
SLICE_AUDIT_JSON = OUT_DIR / 'fresh_slice_bounded_choice_eval.json'
SLICE_ROWS_JSONL = OUT_DIR / 'fresh_slice_rows.jsonl'

RUNTIME_BUNDLE = ARTIFACTS / 'stage10932_mixed_evidence_candidate_support_probe' / 'runtime_model' / 'runtime_model_bundle.json'
OVERLAY_EVAL_JSON = ARTIFACTS / 'stage10932_mixed_evidence_candidate_support_probe' / 'bounded_decoder_probe' / 'bounded_choice_eval_audit_eval.json'
OVERLAY_STRICT_JSON = ARTIFACTS / 'stage10932_mixed_evidence_candidate_support_probe' / 'bounded_decoder_probe' / 'bounded_choice_eval_audit_strict_eval.json'
FRESH_STRICT_ROWS = ARTIFACTS / 'stage10915_evidence_successor_strict_candidates' / 'strict_candidate_rows.jsonl'
BASELINE_SLICE_JSON = ARTIFACTS / 'stage10916_evidence_successor_candidate_slice_comparison' / 'evidence_successor_candidate_slice_comparison.json'

TORCH_THREADS = max(1, int(os.environ.get('AGENTKERNEL_EVAL_THREADS', '8')))
torch.set_num_threads(TORCH_THREADS)
torch.set_num_interop_threads(max(1, min(4, TORCH_THREADS)))
EVAL_DEVICE = torch.device(os.environ.get('AGENTKERNEL_EVAL_DEVICE', 'cuda' if torch.cuda.is_available() else 'cpu'))


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding='utf-8'))


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines() if line.strip()] if path.exists() else []


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


def metric_block(rows: list[dict[str, Any]], field: str) -> dict[str, Any]:
    scored = [row for row in rows if isinstance(row.get(field), bool)]
    correct = sum(1 for row in scored if row.get(field) is True)
    return {'rows': len(rows), 'scored_rows': len(scored), 'correct': correct, 'exact_accuracy': (correct / len(scored)) if scored else None}


def group_metrics(rows: list[dict[str, Any]], group_field: str, result_field: str) -> dict[str, Any]:
    buckets: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        buckets[str(row.get(group_field) or 'unknown')].append(row)
    return {key: metric_block(bucket, result_field) for key, bucket in sorted(buckets.items())}


def load_runtime() -> tuple[AgentKernelLiteTransformerSeq2Seq, AgentKernelBPETokenizer, dict[str, Any]]:
    bundle = load_json(RUNTIME_BUNDLE)
    metadata = bundle['metadata']
    config = AgentKernelLiteTransformerConfig.from_recovered_target_json(load_json(Path(str(metadata['model_config']))))
    model = AgentKernelLiteTransformerSeq2Seq(config)
    init_card = _load_runtime_model_bundle(RUNTIME_BUNDLE, model=model)
    tokenizer = AgentKernelBPETokenizer(Path(str(metadata['tokenizer_json'])), Path(str(metadata['tokenizer_config'])))
    model.to(EVAL_DEVICE)
    model.eval()
    return model, tokenizer, init_card


def main() -> None:
    overlay_eval = load_json(OVERLAY_EVAL_JSON)
    overlay_strict = load_json(OVERLAY_STRICT_JSON)
    baseline_slice = load_json(BASELINE_SLICE_JSON)
    fresh_rows = load_jsonl(FRESH_STRICT_ROWS)

    model, tokenizer, init_card = load_runtime()
    slice_card = _write_bounded_choice_eval_audit(
        OUT_DIR,
        model=model,
        rows=fresh_rows,
        tokenizer=tokenizer,
        max_encoder_tokens=768,
        max_decoder_tokens=8,
        split_name='fresh_evidence_successor_slice',
        bounded_choice_aux_source='encoder_option_retrieval',
        eval_batch_size=8,
    )
    row_cards = list(slice_card.get('row_cards') or [])
    write_json(SLICE_AUDIT_JSON, slice_card)
    write_jsonl(SLICE_ROWS_JSONL, row_cards)

    baseline_rows = {str(row.get('row_id') or ''): row for row in baseline_slice.get('rows') or []}
    combined = []
    for row in row_cards:
        base = baseline_rows.get(str(row.get('row_id') or ''), {})
        source_row = next((candidate for candidate in fresh_rows if candidate.get('row_id') == row.get('row_id')), {})
        combined.append({
            'row_id': row.get('row_id'),
            'language_family': source_row.get('language_family'),
            'target_text': row.get('target_text'),
            'new_constrained_choice_top1_label': row.get('constrained_choice_top1_label'),
            'new_constrained_choice_match': row.get('constrained_choice_match'),
            'new_target_rank_full_vocab': row.get('target_rank_full_vocab'),
            'baseline_constrained_choice_top1_label': base.get('constrained_choice_top1_label'),
            'baseline_constrained_choice_match': base.get('constrained_choice_match'),
            'baseline_target_rank_full_vocab': base.get('target_rank_full_vocab'),
            'gemma12b_correct': base.get('gemma12b_correct'),
            'gemma12b_predicted_label': base.get('gemma12b_predicted_label'),
            'target_value': base.get('target_value'),
        })

    summary = {
        'stage': STAGE,
        'stage_name': NAME,
        'created_at_utc': now_utc(),
        'passed': True,
        'claim_scope': [
            'Audit the stage10932 runtime against the unchanged 23-row overlay and the fresh 3-row evidence successor slice.',
            'Keep Gemma fixed from the prior slice comparison; this artifact measures only whether candidate-wise evidence support moved the evidence lane.',
        ],
        'runtime_bundle': rel(RUNTIME_BUNDLE),
        'runtime_initialization': init_card,
        'overlay': {
            'eval_accuracy': overlay_eval.get('constrained_choice_top1_accuracy'),
            'eval_miss_rows': [r.get('row_id') for r in overlay_eval.get('row_cards', []) if not r.get('constrained_choice_match')],
            'strict_accuracy': overlay_strict.get('constrained_choice_top1_accuracy'),
            'strict_miss_rows': [r.get('row_id') for r in overlay_strict.get('row_cards', []) if not r.get('constrained_choice_match')],
        },
        'fresh_successor_slice': {
            'overall': metric_block(row_cards, 'constrained_choice_match'),
            'by_language': group_metrics(combined, 'language_family', 'new_constrained_choice_match'),
            'baseline_overall': baseline_slice.get('hundred_m', {}).get('overall'),
            'rows': combined,
        },
        'findings': [
            'Candidate-wise evidence-role support is only useful if the fresh 3-row successor slice improves beyond the stage10916 baseline while preserving the same 23-row overlay.',
            'If the overlay stays fixed but the fresh successor rows do not move, the remaining blocker is scorer or row-design alignment rather than multilingual evidence support volume.',
        ],
        'outputs': {
            'summary_json': rel(SUMMARY_JSON),
            'slice_audit_json': rel(SLICE_AUDIT_JSON),
            'slice_rows_jsonl': rel(SLICE_ROWS_JSONL),
        },
    }
    write_json(SUMMARY_JSON, summary)
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == '__main__':
    main()
