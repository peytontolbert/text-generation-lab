#!/usr/bin/env python3
from __future__ import annotations
import json, sys
from pathlib import Path
import torch
import torch.nn.functional as F
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from legacy_src.agentkernel_lite.modeling_transformer import AgentKernelLiteTransformerConfig, AgentKernelLiteTransformerSeq2Seq
from legacy_src.agentkernel_lite.training_data import AgentKernelBPETokenizer, build_batch
from legacy_src.agentkernel_lite.training_loop import _load_runtime_model_bundle
RUNTIME = ROOT/'runs/local/artifacts/stage10943_scorer_margin_support_probe/runtime_model/runtime_model_bundle.json'
EVAL = ROOT/'runs/local/artifacts/stage10941_scorer_margin_support_package/agentkernel_lite_encdec_validation.jsonl'
STRICT = ROOT/'runs/local/artifacts/stage10941_scorer_margin_support_package/agentkernel_lite_encdec_strict_eval.jsonl'
OUT = ROOT/'runs/local/artifacts/stage10945_overlay_evidence_margin_dump.json'
ROLE_MAP = {
    'algorithmic_background_reference': 'background algorithm reference',
    'candidate_change_surface': 'current proposed edit surface',
    'external_analogue_reference': 'external analogue reference',
    'nearby_definition_or_usage_context': 'nearby definition or usage context',
    'symptom_or_call_path_analogue': 'symptom or call path analogue',
    'verifier_and_test_constraint': 'failing verifier or test constraint',
}
def load_json(path: Path): return json.loads(path.read_text())
def load_jsonl(path: Path): return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
bundle = load_json(RUNTIME)
meta = bundle['metadata']
config = AgentKernelLiteTransformerConfig.from_recovered_target_json(load_json(Path(meta['model_config'])))
model = AgentKernelLiteTransformerSeq2Seq(config)
_load_runtime_model_bundle(RUNTIME, model=model)
model.eval()
tokenizer = AgentKernelBPETokenizer(Path(meta['tokenizer_json']), Path(meta['tokenizer_config']))
def option_pairs(row):
    opts = ((row.get('standalone_projection_source') or {}).get('opaque_options')) or row.get('opaque_options') or []
    return [(str(opt['label']), str(opt['value'])) for opt in opts if isinstance(opt, dict)]
def encode_texts(texts, device):
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
def score(row, variant):
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
    option_vectors = encode_texts(texts, query.device)
    if getattr(model, 'retrieval_doc_head', None) is not None:
        option_vectors = model.retrieval_doc_head(option_vectors)
    query = F.normalize(query.float(), dim=-1)
    option_vectors = F.normalize(option_vectors.float(), dim=-1)
    logits = torch.matmul(query, option_vectors.transpose(0, 1)).squeeze(0)
    scored = [{'label': label, 'value': value, 'logit': float(logits[idx].item())} for idx, (label, value) in enumerate(pairs)]
    scored.sort(key=lambda item: item['logit'], reverse=True)
    return scored
payload = {}
for split_name, path in [('eval', EVAL), ('strict', STRICT)]:
    rows = []
    for row in load_jsonl(path):
        if row.get('task_type') != 'evidence_citation':
            continue
        rows.append({
            'row_id': row['row_id'],
            'lang': row.get('language_family'),
            'target': row.get('target_text'),
            'gold_value': ((row.get('standalone_projection_source') or {}).get('gold_value')),
            'selected_test_anchor': row.get('selected_test_anchor'),
            'verifier_anchor': row.get('verifier_anchor'),
            'raw_top2': score(row, 'raw')[:2],
            'role_top2': score(row, 'role')[:2],
        })
    payload[split_name] = rows
OUT.write_text(json.dumps(payload, indent=2, sort_keys=True))
print(OUT)
