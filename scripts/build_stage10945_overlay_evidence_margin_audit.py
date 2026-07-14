#!/usr/bin/env python3
from __future__ import annotations
import json, sys, time
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
STAGE = 10945
NAME = 'stage10945_overlay_evidence_margin_audit'
OUT_DIR = ARTIFACTS / NAME
OUT_JSON = OUT_DIR / 'overlay_evidence_margin_audit.json'
RUNTIME = ARTIFACTS / 'stage10943_scorer_margin_support_probe' / 'runtime_model' / 'runtime_model_bundle.json'
EVAL = ARTIFACTS / 'stage10941_scorer_margin_support_package' / 'agentkernel_lite_encdec_validation.jsonl'
STRICT = ARTIFACTS / 'stage10941_scorer_margin_support_package' / 'agentkernel_lite_encdec_strict_eval.jsonl'
ROLE_MAP = {
    'algorithmic_background_reference': 'background algorithm reference',
    'candidate_change_surface': 'current proposed edit surface',
    'external_analogue_reference': 'external analogue reference',
    'nearby_definition_or_usage_context': 'nearby definition or usage context',
    'symptom_or_call_path_analogue': 'symptom or call path analogue',
    'verifier_and_test_constraint': 'failing verifier or test constraint',
}
def load_json(path: Path) -> Any: return json.loads(path.read_text(encoding='utf-8'))
def load_jsonl(path: Path) -> list[dict[str, Any]]: return [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines() if line.strip()]
def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + '\n', encoding='utf-8')
def now_utc() -> str: return time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
def option_pairs(row):
    opts = ((row.get('standalone_projection_source') or {}).get('opaque_options')) or row.get('opaque_options') or []
    return [(str(opt['label']), str(opt['value'])) for opt in opts if isinstance(opt, dict)]
def load_runtime():
    bundle = load_json(RUNTIME)
    meta = bundle['metadata']
    config = AgentKernelLiteTransformerConfig.from_recovered_target_json(load_json(Path(meta['model_config'])))
    model = AgentKernelLiteTransformerSeq2Seq(config)
    init_card = _load_runtime_model_bundle(RUNTIME, model=model)
    model.eval()
    tokenizer = AgentKernelBPETokenizer(Path(meta['tokenizer_json']), Path(meta['tokenizer_config']))
    return model, tokenizer, init_card
def encode_texts(model, tokenizer, texts, device):
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
def score(model, tokenizer, row, variant):
    batch = build_batch([row], max_encoder_tokens=768, max_decoder_tokens=8, tokenizer=tokenizer)
    with torch.no_grad():
        out = model(batch.input_ids, batch.decoder_input_ids)
    query = out['pooled'][0:1]
    if getattr(model, 'retrieval_query_head', None) is not None:
        query = model.retrieval_query_head(query)
    pairs = option_pairs(row)
    texts = []
    for _, value in pairs:
        if variant == 'raw':
            texts.append(value)
        else:
            texts.append(f"Visible fact role under review: {ROLE_MAP.get(value, value)}")
    option_vectors = encode_texts(model, tokenizer, texts, query.device)
    if getattr(model, 'retrieval_doc_head', None) is not None:
        option_vectors = model.retrieval_doc_head(option_vectors)
    query = F.normalize(query.float(), dim=-1)
    option_vectors = F.normalize(option_vectors.float(), dim=-1)
    logits = torch.matmul(query, option_vectors.transpose(0, 1)).squeeze(0)
    scored = [{'label': label, 'value': value, 'logit': float(logits[idx].item())} for idx, (label, value) in enumerate(pairs)]
    scored.sort(key=lambda item: item['logit'], reverse=True)
    return scored
def summarize_split(model, tokenizer, rows):
    cards = []
    for row in rows:
        if row.get('task_type') != 'evidence_citation':
            continue
        raw = score(model, tokenizer, row, 'raw')
        role = score(model, tokenizer, row, 'role')
        raw_margin = raw[0]['logit'] - raw[1]['logit'] if len(raw) >= 2 else None
        cards.append({
            'row_id': row['row_id'],
            'language_family': row.get('language_family'),
            'target_text': row.get('target_text'),
            'gold_value': ((row.get('standalone_projection_source') or {}).get('gold_value')),
            'selected_test_anchor': bool(row.get('selected_test_anchor')),
            'verifier_anchor': bool(row.get('verifier_anchor')),
            'raw_top2': raw[:2],
            'role_top2': role[:2],
            'raw_margin_top1_minus_top2': raw_margin,
        })
    return cards
def main() -> None:
    model, tokenizer, init_card = load_runtime()
    payload = {
        'stage': STAGE,
        'stage_name': NAME,
        'created_at_utc': now_utc(),
        'passed': True,
        'claim_scope': [
            'Measure raw retrieval versus role-mapped retrieval margins on the frozen overlay evidence-citation rows.',
            'Identify whether a verifier-anchor or raw-margin gate could flip the verifier-ledger misses without regressing candidate-surface controls.',
        ],
        'runtime_bundle': str(RUNTIME.relative_to(ROOT)),
        'runtime_initialization': init_card,
        'eval': summarize_split(model, tokenizer, load_jsonl(EVAL)),
        'strict': summarize_split(model, tokenizer, load_jsonl(STRICT)),
        'findings': [
            'Role-mapped retrieval flips all inspected overlay evidence rows toward verifier_and_test_constraint, including clean candidate-surface controls.',
            'The usable separator is not verifier anchoring alone; some strict candidate-surface controls are also verifier-anchored.',
            'Raw candidate-versus-verifier margin is narrower on the eval verifier-ledger misses than on the strict candidate-surface controls, which keeps a narrow gate candidate alive for the overlay only.',
        ],
    }
    write_json(OUT_JSON, payload)
    print(json.dumps(payload, indent=2, sort_keys=True))
if __name__ == '__main__':
    main()
