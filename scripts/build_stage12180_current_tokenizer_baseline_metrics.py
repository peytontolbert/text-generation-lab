#!/usr/bin/env python3
from __future__ import annotations

import json
import statistics
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / 'runs/local/artifacts'
SUM = ROOT / 'runs/summaries'
STAGE = 'stage12180_current_1506_tokenizer_baseline_metrics'
OUT = ART / STAGE
TOKENIZER_JSON = ROOT / 'configs/tokenizer/agentkernel_bpe_1506/tokenizer.json'
TOKENIZER_CONFIG = ROOT / 'configs/tokenizer/agentkernel_bpe_1506/tokenizer_config.json'
SOURCES = {
    'stage11923_transition': ART / 'stage11923_transition_listwise_head_only_probe_request/transition_listwise_head_only_manifest.jsonl',
    'stage12155_selected_test_counterfactual': ART / 'stage12155_selected_test_counterfactual_expansion_package/expanded_counterfactual_rows.jsonl',
    'stage12173_next_action': ART / 'stage12173_transition_next_action_head_from_stage12083_request/transition_next_action_head_diagnostic_manifest.jsonl',
}

from tokenizers import Tokenizer




def row_text(row: dict[str, Any]) -> str:
    parts: list[str] = []
    def walk(prefix: str, value: Any, depth: int = 0) -> None:
        if depth > 4:
            return
        if isinstance(value, str):
            if value.strip():
                parts.append(f"{prefix}={value}")
        elif isinstance(value, (int, float, bool)):
            parts.append(f"{prefix}={value}")
        elif isinstance(value, dict):
            for key in sorted(value):
                if key in {"target", "decoder_text"} or key.endswith("_target"):
                    continue
                walk(f"{prefix}.{key}" if prefix else str(key), value[key], depth + 1)
        elif isinstance(value, list):
            for idx, item in enumerate(value[:24]):
                walk(f"{prefix}.{idx}", item, depth + 1)
    for key in ("language_family", "task_type", "prompt_text", "query_text", "input_text", "model_input", "standalone_projection_source", "context_rows", "episode_transition"):
        if key in row:
            walk(key, row[key])
    return "\n".join(parts)

def now() -> str:
    return time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines() if line.strip()]


def encode_raw(tok: AgentKernelBPETokenizer, text: str) -> list[int]:
    enc = tok.encode(text, add_special_tokens=False)
    return [int(idx) for idx in enc.ids]


def stats(values: list[float]) -> dict[str, float | int | None]:
    if not values:
        return {'count': 0, 'mean': None, 'median': None, 'p90': None, 'min': None, 'max': None}
    ordered = sorted(values)
    p90 = ordered[min(len(ordered)-1, int(0.9 * (len(ordered)-1)))]
    return {
        'count': len(values),
        'mean': round(float(statistics.mean(values)), 4),
        'median': round(float(statistics.median(values)), 4),
        'p90': round(float(p90), 4),
        'min': round(float(ordered[0]), 4),
        'max': round(float(ordered[-1]), 4),
    }


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    config = json.loads(TOKENIZER_CONFIG.read_text(encoding='utf-8'))
    tok = Tokenizer.from_file(str(TOKENIZER_JSON))
    vocab = tok.get_vocab()
    id_to_token = {idx: token for token, idx in vocab.items()}
    used = Counter()
    rows_out = []
    by_lang_bpt: dict[str, list[float]] = defaultdict(list)
    by_lang_tokens: dict[str, list[int]] = defaultdict(list)
    trunc = {'768': Counter(), '4096': Counter()}
    source_counts = {}

    for source_name, path in SOURCES.items():
        rows = read_jsonl(path)
        source_counts[source_name] = len(rows)
        for row in rows:
            text = row_text(row)
            if not text:
                continue
            raw_ids = encode_raw(tok, text)
            used.update(raw_ids)
            byte_len = len(text.encode('utf-8'))
            token_len = len(raw_ids)
            lang = str(row.get('language_family') or 'unknown')
            bpt = byte_len / max(1, token_len)
            by_lang_bpt[lang].append(bpt)
            by_lang_tokens[lang].append(token_len)
            trunc['768'][lang] += int(token_len > 768)
            trunc['4096'][lang] += int(token_len > 4096)
            if len(rows_out) < 5000:
                rows_out.append({
                    'source': source_name,
                    'row_id': row.get('row_id'),
                    'language_family': lang,
                    'bytes': byte_len,
                    'non_special_tokens': token_len,
                    'bytes_per_token': round(bpt, 4),
                    'would_truncate_768': token_len > 768,
                    'would_truncate_4096': token_len > 4096,
                })

    label_strings = list('ABCDEFGHIJKLMNOPQRSTUVWXYZ') + [
        'SELECT_TEST', 'RUN_VERIFIER', 'RETRIEVE_EVIDENCE', 'PLAN_PATCH', 'FINISH',
        'LOCALIZE_FAILURE', 'ABSTAIN_OR_ROLLBACK', 'PASS_TO_PASS', 'NOT_EXERCISED',
        'INSUFFICIENT_EVIDENCE', 'VERIFIER_REMOVED', 'candidate_change_surface',
        'verifier_and_test_constraint', 'symptom_or_call_path_analogue',
    ]
    label_metrics = {}
    for label in label_strings:
        ids = encode_raw(tok, label)
        label_metrics[label] = {
            'token_ids': ids,
            'token_count': len(ids),
            'single_token': len(ids) == 1,
            'decoded': tok.decode(ids),
        }

    total_non_special_vocab = len([idx for idx in id_to_token if idx not in {int(config.get('pad_token_id', 0)), int(config.get('bos_token_id', 1)), int(config.get('eos_token_id', 2))}])
    used_non_special = len([idx for idx in used if idx not in {int(config.get('pad_token_id', 0)), int(config.get('bos_token_id', 1)), int(config.get('eos_token_id', 2))}])
    dead_est = max(0, total_non_special_vocab - used_non_special)
    lang_summary = {}
    for lang in sorted(by_lang_bpt):
        bpt_stats = stats(by_lang_bpt[lang])
        tok_stats = stats([float(x) for x in by_lang_tokens[lang]])
        mean_bpt = bpt_stats['mean'] or 0.0
        lang_summary[lang] = {
            'rows': len(by_lang_bpt[lang]),
            'bytes_per_token': bpt_stats,
            'non_special_tokens_per_row': tok_stats,
            'estimated_effective_bytes_at_768_tokens': round(float(mean_bpt) * 768, 1),
            'estimated_effective_bytes_at_4096_tokens': round(float(mean_bpt) * 4096, 1),
            'rows_over_768_tokens': int(trunc['768'][lang]),
            'rows_over_4096_tokens': int(trunc['4096'][lang]),
        }

    payload = {
        'stage': STAGE,
        'created_at_utc': now(),
        'decision': 'baseline_metrics_only_no_tokenizer_change_no_training',
        'tokenizer': {
            'tokenizer_json': str(TOKENIZER_JSON.relative_to(ROOT)),
            'tokenizer_config': str(TOKENIZER_CONFIG.relative_to(ROOT)),
            'tokenizer_kind': str(config.get('tokenizer_kind') or 'agentkernel_bytelevel_bpe_v1'),
            'vocab_size': int(config.get('vocab_size') or len(vocab)),
            'pad_id': int(config.get('pad_token_id', 0)),
            'bos_id': int(config.get('bos_token_id', 1)),
            'eos_id': int(config.get('eos_token_id', 2)),
            'byte_fallback': False,
        },
        'source_counts': source_counts,
        'sampled_rows': len(rows_out),
        'dead_token_estimate_on_sample': {
            'non_special_vocab': total_non_special_vocab,
            'used_non_special_tokens': used_non_special,
            'dead_or_unseen_non_special_tokens': dead_est,
            'dead_or_unseen_fraction': round(dead_est / max(1, total_non_special_vocab), 4),
        },
        'language_summary': lang_summary,
        'bounded_label_tokenization': label_metrics,
        'contract_interpretation': {
            'protected_frontier_tokenizer_changed': False,
            '4096_ablation_supported_by_metrics_alone': 'undecided_requires_comparison_tokenizer',
            'notable_current_risk': 'Many semantic action/status labels are multi-token, but opaque A-Z labels are single-token. Input compression should be judged separately from bounded-label decoding.',
        },
    }
    (OUT / 'row_token_metrics_sample.jsonl').write_text(''.join(json.dumps(r, sort_keys=True) + '\n' for r in rows_out), encoding='utf-8')
    for p in [OUT / 'summary.json', OUT / 'current_1506_tokenizer_baseline_metrics.json', SUM / f'{STAGE}.json']:
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(payload, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    print(json.dumps({
        'stage': STAGE,
        'vocab_size': int(config.get('vocab_size') or len(vocab)),
        'sampled_rows': len(rows_out),
        'dead_or_unseen_fraction': payload['dead_token_estimate_on_sample']['dead_or_unseen_fraction'],
        'language_summary': lang_summary,
    }, indent=2, sort_keys=True))

if __name__ == '__main__':
    main()
