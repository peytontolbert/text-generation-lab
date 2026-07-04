from __future__ import annotations

from pathlib import Path
from typing import Any
import argparse
import json
import re

INTERNAL_TOKEN_RE = re.compile(r"(<MTC|POLICY_|COPY:|CONTROL_|INTERNAL_|decoder_control)")
HTML_RE = re.compile(r"<(html|body|script|style|div|span|table|svg|DOCTYPE)\b", re.I)
REPEAT_RE = re.compile(r"\b(\w{3,})\b(?:\s+\1\b){4,}", re.I)


def text_of(row: dict[str, Any], *keys: str) -> str:
    parts=[]
    for key in keys:
        value=row.get(key)
        if isinstance(value, str):
            parts.append(value)
    return "\n".join(parts)


def rank_row(row: dict[str, Any], *, max_decoder_tokens: int = 768) -> dict[str, Any]:
    reasons: list[str] = []
    decoder_text = text_of(row, 'decoder_text', 'decoder_target', 'target_text')
    encoder_text = text_of(row, 'encoder_text', 'input_text')
    token_len = row.get('decoder_token_len')
    if not isinstance(token_len, int):
        token_len = int(row.get('decoder_content_chars', len(decoder_text)) or 0)
    if token_len > max_decoder_tokens:
        reasons.append('target_over_decoder_budget')
    if token_len > 10000:
        reasons.append('long_blob')
    if HTML_RE.search(decoder_text):
        reasons.append('html_doc_fragment')
    if INTERNAL_TOKEN_RE.search(decoder_text):
        reasons.append('raw_internal_token_in_decoder')
    if INTERNAL_TOKEN_RE.search(encoder_text) and row.get('objective_kind') == 'structured':
        reasons.append('raw_text_leak_in_structured_objective')
    stripped = decoder_text.strip()
    if decoder_text and (len(stripped) < 12 or stripped in {'.', '...', 'OK', 'None'}):
        reasons.append('short_or_junk_target')
    if REPEAT_RE.search(decoder_text):
        reasons.append('degenerate_repetition_target')
    if row.get('evidence_state') in {'missing', 'evidence_removed'} and row.get('decode_allowed') is True:
        reasons.append('missing_evidence_but_decode_allowed')
    if row.get('decoder_budget_ok') is False and row.get('decode_allowed') is True:
        reasons.append('budget_bad_but_decode_allowed')
    if row.get('duplicate_semantic_key') is True:
        reasons.append('duplicate_semantic_key')
    if row.get('authority_true') is True or bool((row.get('authority') or {}).get('runtime_authorized', False)):
        reasons.append('authority_true')
    route = 'KEEP_STRUCTURED'
    if 'authority_true' in reasons or 'duplicate_semantic_key' in reasons:
        route = 'QUARANTINE_LABEL_CONFLICT'
    elif 'raw_internal_token_in_decoder' in reasons or 'short_or_junk_target' in reasons or 'degenerate_repetition_target' in reasons:
        route = 'USE_FOR_DENOISE_REPAIR'
    elif 'target_over_decoder_budget' in reasons or 'long_blob' in reasons or 'html_doc_fragment' in reasons:
        route = 'HOLD_LONG_OUTPUT'
    elif 'missing_evidence_but_decode_allowed' in reasons:
        route = 'NEEDS_RETRIEVAL'
    elif row.get('decode_allowed') is True and row.get('decoder_budget_ok') is True:
        route = 'KEEP_BOUNDED_DECODER'
    elif row.get('internal_control_token_negative') or row.get('short_output_negative'):
        route = 'USE_AS_NEGATIVE'
    score = min(1.0, 0.15 * len(reasons) + (0.35 if route.startswith('QUARANTINE') else 0.0))
    return {"row_id": row.get('row_id') or row.get('candidate_id') or '', "junk_score": round(score, 4), "risk_bucket": route, "reasons": reasons, "recommended_action": route}


def rank_rows(rows: list[dict[str, Any]], *, max_decoder_tokens: int = 768) -> dict[str, Any]:
    ranked=[rank_row(row, max_decoder_tokens=max_decoder_tokens) for row in rows]
    route_counts: dict[str, int] = {}
    reason_counts: dict[str, int] = {}
    for item in ranked:
        route_counts[item['risk_bucket']] = route_counts.get(item['risk_bucket'], 0) + 1
        for reason in item['reasons']:
            reason_counts[reason] = reason_counts.get(reason, 0) + 1
    return {"rows": len(rows), "route_counts": dict(sorted(route_counts.items())), "reason_counts": dict(sorted(reason_counts.items())), "ranked_rows": ranked}


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines() if line.strip()]


def parse_args() -> argparse.Namespace:
    parser=argparse.ArgumentParser(description='Deterministic objective-aware structured dataset junk/routing ranker.')
    parser.add_argument('manifest', type=Path)
    parser.add_argument('--max-decoder-tokens', type=int, default=768)
    parser.add_argument('--output', type=Path, default=None)
    return parser.parse_args()


def main() -> None:
    args=parse_args()
    card=rank_rows(read_jsonl(args.manifest), max_decoder_tokens=args.max_decoder_tokens)
    text=json.dumps(card, indent=2, sort_keys=True)+'\n'
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding='utf-8')
    print(text, end='')


if __name__ == '__main__':
    main()
