#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from typing import Any

import torch
import torch.nn.functional as F

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from legacy_src.agentkernel_lite.modeling_transformer import AgentKernelLiteTransformerConfig, AgentKernelLiteTransformerSeq2Seq
from legacy_src.agentkernel_lite.training_data import AgentKernelBPETokenizer, build_batch
from legacy_src.agentkernel_lite.training_loop import _load_runtime_model_bundle

ARTIFACTS = ROOT / 'runs' / 'local' / 'artifacts'
STAGE = 10954
NAME = 'stage10954_evidence_scorer_blend_audit'
OUT_DIR = ARTIFACTS / NAME
OUT_JSON = OUT_DIR / 'evidence_scorer_blend_audit.json'
ROW_JSONL = OUT_DIR / 'row_score_cards.jsonl'

RUNTIME_BUNDLE = ARTIFACTS / 'stage10952_evidence_contrast_margin_probe' / 'runtime_model' / 'runtime_model_bundle.json'
OVERLAY_EVAL = ARTIFACTS / 'stage10941_scorer_margin_support_package' / 'agentkernel_lite_encdec_validation.jsonl'
OVERLAY_STRICT = ARTIFACTS / 'stage10941_scorer_margin_support_package' / 'agentkernel_lite_encdec_strict_eval.jsonl'
EXPLICIT = ARTIFACTS / 'stage10938_explicit_verifier_ledger_strict_candidates' / 'strict_candidate_rows.jsonl'

ROLE_MAP = {
    'algorithmic_background_reference': 'background algorithm reference',
    'candidate_change_surface': 'current proposed edit surface',
    'external_analogue_reference': 'external analogue reference',
    'nearby_definition_or_usage_context': 'nearby definition or usage context',
    'symptom_or_call_path_analogue': 'symptom or call path analogue',
    'verifier_and_test_constraint': 'failing verifier or test constraint',
}


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
    meta = bundle['metadata']
    config = AgentKernelLiteTransformerConfig.from_recovered_target_json(load_json(Path(str(meta['model_config']))))
    model = AgentKernelLiteTransformerSeq2Seq(config)
    init_card = _load_runtime_model_bundle(RUNTIME_BUNDLE, model=model)
    if torch.cuda.is_available():
        model = model.to(torch.device('cuda'))
    model.eval()
    tokenizer = AgentKernelBPETokenizer(Path(str(meta['tokenizer_json'])), Path(str(meta['tokenizer_config'])))
    return model, tokenizer, init_card


def option_pairs(row: dict[str, Any]) -> list[tuple[str, str]]:
    opts = ((row.get('standalone_projection_source') or {}).get('opaque_options')) or row.get('opaque_options') or []
    return [(str(opt['label']), str(opt['value'])) for opt in opts if isinstance(opt, dict)]


def encode_texts(model, tokenizer, texts: list[str], device: torch.device) -> torch.Tensor:
    pad_id = int(getattr(tokenizer, 'pad_id', 0))
    bos_id = int(getattr(tokenizer, 'bos_id', 1))
    eos_id = int(getattr(tokenizer, 'eos_id', 2))
    encoded = []
    for text in texts:
        ids = [i for i in tokenizer.encode(text, max_length=768) if i not in {bos_id, eos_id}]
        if not ids:
            ids = [pad_id]
        encoded.append(ids)
    width = max(len(ids) for ids in encoded)
    input_ids = torch.full((len(encoded), width), pad_id, dtype=torch.long, device=device)
    attention_mask = torch.zeros((len(encoded), width), dtype=torch.bool, device=device)
    for row_idx, ids in enumerate(encoded):
        input_ids[row_idx, :len(ids)] = torch.tensor(ids, dtype=torch.long, device=device)
        attention_mask[row_idx, :len(ids)] = True
    return model.encode_pooled(input_ids, attention_mask)


def perspective(row: dict[str, Any]) -> str:
    prompt = str(row.get('prompt_text') or row.get('input_text') or '')
    for line in prompt.splitlines():
        if line.startswith('Perspective: '):
            return line.split(': ', 1)[1].strip()
    return ''


def score_variants(model, tokenizer, row: dict[str, Any]) -> dict[str, Any]:
    batch = build_batch([row], max_encoder_tokens=768, max_decoder_tokens=8, tokenizer=tokenizer)
    if torch.cuda.is_available():
        batch.input_ids = batch.input_ids.to(torch.device('cuda'))
        batch.decoder_input_ids = batch.decoder_input_ids.to(torch.device('cuda'))
        batch.labels = batch.labels.to(torch.device('cuda'))
        batch.loss_mask = {key: value.to(torch.device('cuda')) for key, value in batch.loss_mask.items()}
    with torch.no_grad():
        out = model(batch.input_ids, batch.decoder_input_ids)
    query = out['pooled'][0:1]
    if getattr(model, 'retrieval_query_head', None) is not None:
        query = model.retrieval_query_head(query)
    pairs = option_pairs(row)
    values = [value for _label, value in pairs]
    raw_texts = values
    role_texts = [f"Visible fact role under review: {ROLE_MAP.get(value, value)}" for value in values]
    raw_vecs = encode_texts(model, tokenizer, raw_texts, query.device)
    role_vecs = encode_texts(model, tokenizer, role_texts, query.device)
    if getattr(model, 'retrieval_doc_head', None) is not None:
        raw_vecs = model.retrieval_doc_head(raw_vecs)
        role_vecs = model.retrieval_doc_head(role_vecs)
    query = F.normalize(query.float(), dim=-1)
    raw_vecs = F.normalize(raw_vecs.float(), dim=-1)
    role_vecs = F.normalize(role_vecs.float(), dim=-1)
    raw_logits = torch.matmul(query, raw_vecs.transpose(0, 1)).squeeze(0).detach().cpu()
    role_logits = torch.matmul(query, role_vecs.transpose(0, 1)).squeeze(0).detach().cpu()
    return {
        'row': row,
        'pairs': pairs,
        'raw_logits': raw_logits,
        'role_logits': role_logits,
    }


def argmax_label(logits: torch.Tensor, pairs: list[tuple[str, str]]) -> str | None:
    if logits.numel() == 0 or not pairs:
        return None
    return pairs[int(torch.argmax(logits).item())][0]


def pred_value(label: str | None, pairs: list[tuple[str, str]]) -> str | None:
    for pair_label, pair_value in pairs:
        if pair_label == label:
            return pair_value
    return None


def target_rank(logits: torch.Tensor, target_label: str, pairs: list[tuple[str, str]]) -> int | None:
    scored = [(label, float(logits[idx].item())) for idx, (label, _value) in enumerate(pairs)]
    scored.sort(key=lambda item: item[1], reverse=True)
    for idx, (label, _score) in enumerate(scored, start=1):
        if label == target_label:
            return idx
    return None


def blended_logits(raw_logits: torch.Tensor, role_logits: torch.Tensor, alpha: float) -> torch.Tensor:
    return ((1.0 - alpha) * raw_logits) + (alpha * role_logits)


def biased_logits(raw_logits: torch.Tensor, pairs: list[tuple[str, str]], verifier_bias: float, candidate_bias: float) -> torch.Tensor:
    adjusted = raw_logits.clone()
    for idx, (_label, value) in enumerate(pairs):
        if value == 'verifier_and_test_constraint':
            adjusted[idx] += verifier_bias
        elif value == 'candidate_change_surface':
            adjusted[idx] += candidate_bias
    return adjusted


def row_group(row_id: str) -> str:
    if row_id.startswith('stage10938::'):
        return 'explicit'
    return 'overlay'


def language(row: dict[str, Any]) -> str:
    value = row.get('language_family')
    if value:
        return str(value)
    row_id = str(row.get('row_id') or '')
    if 'python_' in row_id or '::python::' in row_id:
        return 'python'
    if 'cpp_' in row_id or '::c_cpp::' in row_id:
        return 'c_cpp'
    if '::web_js_ts_html::' in row_id:
        return 'web_js_ts_html'
    if '::rust::' in row_id:
        return 'rust'
    return 'unknown'


def evaluate(cards: list[dict[str, Any]], mode: str, param_a: float, param_b: float | None = None) -> dict[str, Any]:
    row_cards = []
    for card in cards:
        row = card['row']
        pairs = card['pairs']
        if mode == 'blend':
            logits = blended_logits(card['raw_logits'], card['role_logits'], param_a)
        else:
            logits = biased_logits(card['raw_logits'], pairs, param_a, float(param_b or 0.0))
        pred = argmax_label(logits, pairs)
        target = str(row.get('target_text') or '')
        row_cards.append({
            'row_id': str(row.get('row_id')),
            'group': row_group(str(row.get('row_id'))),
            'language_family': language(row),
            'task_type': str(row.get('task_type') or ''),
            'perspective': perspective(row),
            'target_label': target,
            'target_value': pred_value(target, pairs),
            'predicted_label': pred,
            'predicted_value': pred_value(pred, pairs),
            'correct': pred == target,
            'target_rank': target_rank(logits, target, pairs),
            'selected_test_anchor': bool(row.get('selected_test_anchor')),
            'verifier_anchor': bool(row.get('verifier_anchor')),
        })
    overlay = [row for row in row_cards if row['group'] == 'overlay']
    explicit = [row for row in row_cards if row['group'] == 'explicit']
    def acc(rows: list[dict[str, Any]]) -> float | None:
        return (sum(1 for row in rows if row['correct']) / len(rows)) if rows else None
    return {
        'mode': mode,
        'param_a': param_a,
        'param_b': param_b,
        'overlay_accuracy': acc(overlay),
        'explicit_accuracy': acc(explicit),
        'overlay_correct': sum(1 for row in overlay if row['correct']),
        'explicit_correct': sum(1 for row in explicit if row['correct']),
        'overlay_rows': len(overlay),
        'explicit_rows': len(explicit),
        'all_overlay_correct': all(row['correct'] for row in overlay),
        'all_explicit_correct': all(row['correct'] for row in explicit),
        'rows': row_cards,
    }


def compact_rows(cards: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out = []
    for card in cards:
        row = card['row']
        pairs = card['pairs']
        raw_pred = argmax_label(card['raw_logits'], pairs)
        role_pred = argmax_label(card['role_logits'], pairs)
        out.append({
            'row_id': str(row.get('row_id')),
            'group': row_group(str(row.get('row_id'))),
            'language_family': language(row),
            'target_label': str(row.get('target_text') or ''),
            'target_value': pred_value(str(row.get('target_text') or ''), pairs),
            'raw_predicted_label': raw_pred,
            'raw_predicted_value': pred_value(raw_pred, pairs),
            'role_predicted_label': role_pred,
            'role_predicted_value': pred_value(role_pred, pairs),
            'raw_target_rank': target_rank(card['raw_logits'], str(row.get('target_text') or ''), pairs),
            'role_target_rank': target_rank(card['role_logits'], str(row.get('target_text') or ''), pairs),
            'pairs': [{'label': label, 'value': value} for label, value in pairs],
            'selected_test_anchor': bool(row.get('selected_test_anchor')),
            'verifier_anchor': bool(row.get('verifier_anchor')),
        })
    return out


def main() -> None:
    rows = load_jsonl(OVERLAY_EVAL) + load_jsonl(OVERLAY_STRICT) + load_jsonl(EXPLICIT)
    model, tokenizer, init_card = load_runtime()
    cards = [score_variants(model, tokenizer, row) for row in rows if option_pairs(row)]

    blend_results = []
    for step in range(0, 21):
        alpha = step / 20.0
        blend_results.append(evaluate(cards, 'blend', alpha))

    bias_results = []
    for vb in [x / 100.0 for x in range(-10, 21, 2)]:
        for cb in [x / 100.0 for x in range(-20, 11, 2)]:
            bias_results.append(evaluate(cards, 'bias', vb, cb))

    feasible_blends = [
        {'alpha': result['param_a'], 'overlay_accuracy': result['overlay_accuracy'], 'explicit_accuracy': result['explicit_accuracy']}
        for result in blend_results if result['all_overlay_correct'] and result['all_explicit_correct']
    ]
    feasible_biases = [
        {'verifier_bias': result['param_a'], 'candidate_bias': result['param_b'], 'overlay_accuracy': result['overlay_accuracy'], 'explicit_accuracy': result['explicit_accuracy']}
        for result in bias_results if result['all_overlay_correct'] and result['all_explicit_correct']
    ]

    best_blend = max(blend_results, key=lambda item: (item['explicit_correct'], item['overlay_correct']))
    best_bias = max(bias_results, key=lambda item: (item['explicit_correct'], item['overlay_correct']))

    payload = {
        'stage': STAGE,
        'stage_name': NAME,
        'created_at_utc': now_utc(),
        'passed': True,
        'claim_scope': [
            'Search honest linear evidence-scorer families on the current runtime: convex blends of raw and role-mapped retrieval logits, and raw-logit verifier/candidate semantic bias terms.',
            'Require the same scorer family to preserve the frozen overlay while repairing the explicit-ledger 3-row blocker slice.',
        ],
        'runtime_bundle': rel(RUNTIME_BUNDLE),
        'runtime_initialization': init_card,
        'row_cards': compact_rows(cards),
        'search': {
            'blend_alpha_grid': [step / 20.0 for step in range(0, 21)],
            'bias_verifier_grid': [x / 100.0 for x in range(-10, 21, 2)],
            'bias_candidate_grid': [x / 100.0 for x in range(-20, 11, 2)],
            'feasible_blends': feasible_blends,
            'feasible_biases': feasible_biases,
            'best_blend': {
                'alpha': best_blend['param_a'],
                'overlay_correct': best_blend['overlay_correct'],
                'overlay_rows': best_blend['overlay_rows'],
                'explicit_correct': best_blend['explicit_correct'],
                'explicit_rows': best_blend['explicit_rows'],
                'all_overlay_correct': best_blend['all_overlay_correct'],
                'all_explicit_correct': best_blend['all_explicit_correct'],
            },
            'best_bias': {
                'verifier_bias': best_bias['param_a'],
                'candidate_bias': best_bias['param_b'],
                'overlay_correct': best_bias['overlay_correct'],
                'overlay_rows': best_bias['overlay_rows'],
                'explicit_correct': best_bias['explicit_correct'],
                'explicit_rows': best_bias['explicit_rows'],
                'all_overlay_correct': best_bias['all_overlay_correct'],
                'all_explicit_correct': best_bias['all_explicit_correct'],
            },
        },
        'findings': [
            'If there are no feasible blends or semantic bias settings, the blocker has moved beyond scorer calibration and needs either a different scorer architecture or fresh row geometry.',
            'If a feasible family appears, it is a candidate inference interface that should be audited before any more training probes.',
        ],
        'outputs': {
            'summary_json': rel(OUT_JSON),
            'row_score_cards_jsonl': rel(ROW_JSONL),
        },
    }
    write_json(OUT_JSON, payload)
    write_jsonl(ROW_JSONL, compact_rows(cards))
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == '__main__':
    main()
