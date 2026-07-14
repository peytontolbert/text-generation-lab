from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from long_context_common import write_json


ROOT = Path(__file__).resolve().parents[1]


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open('r', encoding='utf-8') as handle:
        for line in handle:
            if not line.strip():
                continue
            rows.append(json.loads(line))
    return rows


def _maybe_json(value: Any) -> Any:
    if isinstance(value, str):
        text = value.strip()
        if text.startswith('{') or text.startswith('['):
            try:
                return json.loads(text)
            except json.JSONDecodeError:
                return value
    return value


def _as_list(value: Any) -> list[Any]:
    parsed = _maybe_json(value)
    return parsed if isinstance(parsed, list) else []


def _as_dict(value: Any) -> dict[str, Any]:
    parsed = _maybe_json(value)
    return parsed if isinstance(parsed, dict) else {}


def _split_target_lines(text: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line in str(text or '').splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            rows.append(payload)
    return rows


def _build_pack_index(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    packs: dict[str, dict[str, Any]] = defaultdict(lambda: {
        'full': None,
        'memory': None,
        'retrieval': [],
        'split': None,
    })
    for row in rows:
        pack_id = str(row.get('pack_id') or '').strip()
        if not pack_id:
            raise ValueError('missing_pack_id')
        pack = packs[pack_id]
        split = str(row.get('split') or row.get('effective_split') or 'train')
        pack['split'] = split
        surface = str(row.get('mixture_surface') or '')
        if surface == 'full_context_rows':
            pack['full'] = row
        elif surface == 'memory_rows':
            pack['memory'] = row
        elif surface == 'retrieval_rows':
            pack['retrieval'].append(row)
    return packs


def audit_strict_long_context_split_quality(*, manifest_path: Path, output_path: Path) -> dict[str, Any]:
    rows = _read_jsonl(manifest_path)
    packs = _build_pack_index(rows)

    counts = Counter()
    split_counts: dict[str, Counter[str]] = defaultdict(Counter)
    failed_packs: list[dict[str, Any]] = []

    for pack_id, pack in sorted(packs.items()):
        split = str(pack.get('split') or 'train')
        full = pack.get('full')
        memory = pack.get('memory')
        retrieval_rows = list(pack.get('retrieval') or [])
        if full is None or memory is None or not retrieval_rows:
            raise ValueError(f'incomplete_pack:{pack_id}')

        context_rows = _as_list(full.get('context_rows'))
        chunk_index = {}
        first_chunk_ids: list[str] = []
        for idx, item in enumerate(context_rows):
            if not isinstance(item, dict):
                continue
            chunk_id = str(item.get('chunk_id') or '')
            if not chunk_id:
                continue
            chunk_index[chunk_id] = {
                'ordinal': idx,
                'source_type': str(item.get('source_type') or ''),
            }
            if len(first_chunk_ids) < 3:
                first_chunk_ids.append(chunk_id)

        target_lines = _split_target_lines(str(full.get('target_text') or ''))
        nonempty_target_lines = [
            line for line in target_lines
            if str(line.get('state_variable') or '').strip() or bool(line.get('final_state'))
        ]
        if not nonempty_target_lines:
            counts['blank_full_target_packs'] += 1
            split_counts[split]['blank_full_target_packs'] += 1

        memory_target = _as_dict(memory.get('target_text'))
        state_variables = [str(value or '').strip() for value in _as_list(memory_target.get('state_variables'))]
        canonical_names = [str(value or '').strip() for value in _as_list(memory_target.get('canonical_names'))]
        if not any(state_variables) and not any(canonical_names):
            counts['blank_memory_target_packs'] += 1
            split_counts[split]['blank_memory_target_packs'] += 1

        pack_fallback_rows = 0
        pack_blank_query_rows = 0
        pack_blank_target_rows = 0
        pack_unmapped_positive_rows = 0
        pack_local_rows = 0
        pack_long_join_rows = 0
        pack_rows_with_signal = 0

        for row in retrieval_rows:
            query_text = str(row.get('query_text') or '')
            if 'final value of ``' in query_text:
                pack_blank_query_rows += 1
            target = _as_dict(row.get('target_text'))
            if not str(target.get('state_variable') or '').strip() and not bool(target.get('final_state')):
                pack_blank_target_rows += 1

            positive_chunk_ids = [str(value) for value in _as_list(row.get('positive_chunk_ids')) if str(value).strip()]
            if not positive_chunk_ids:
                pack_unmapped_positive_rows += 1
                continue
            mapped = [chunk_index.get(chunk_id) for chunk_id in positive_chunk_ids]
            mapped = [item for item in mapped if item is not None]
            if len(mapped) != len(positive_chunk_ids):
                pack_unmapped_positive_rows += 1
                continue
            pack_rows_with_signal += 1
            ordinals = sorted(int(item['ordinal']) for item in mapped)
            source_types = {str(item['source_type'] or '') for item in mapped if str(item['source_type'] or '')}
            if positive_chunk_ids == first_chunk_ids[: len(positive_chunk_ids)]:
                pack_fallback_rows += 1
            if len(context_rows) > 0:
                span_ratio = (ordinals[-1] - ordinals[0]) / max(1, len(context_rows) - 1)
                edge_window = max(8, int(0.02 * len(context_rows)))
                edge_only = len(context_rows) >= 100 and (
                    ordinals[-1] < edge_window or ordinals[0] > max(0, len(context_rows) - edge_window)
                )
                if span_ratio <= 0.02 or edge_only:
                    pack_local_rows += 1
                if len(source_types) >= 2 and span_ratio >= 0.30:
                    pack_long_join_rows += 1

        retrieval_count = len(retrieval_rows)
        counts['retrieval_rows'] += retrieval_count
        split_counts[split]['retrieval_rows'] += retrieval_count
        counts['blank_query_rows'] += pack_blank_query_rows
        split_counts[split]['blank_query_rows'] += pack_blank_query_rows
        counts['blank_target_rows'] += pack_blank_target_rows
        split_counts[split]['blank_target_rows'] += pack_blank_target_rows
        counts['fallback_positive_rows'] += pack_fallback_rows
        split_counts[split]['fallback_positive_rows'] += pack_fallback_rows
        counts['unmapped_positive_rows'] += pack_unmapped_positive_rows
        split_counts[split]['unmapped_positive_rows'] += pack_unmapped_positive_rows
        counts['locality_risk_rows'] += pack_local_rows
        split_counts[split]['locality_risk_rows'] += pack_local_rows
        counts['long_join_rows'] += pack_long_join_rows
        split_counts[split]['long_join_rows'] += pack_long_join_rows
        counts['rows_with_signal'] += pack_rows_with_signal
        split_counts[split]['rows_with_signal'] += pack_rows_with_signal

        if (
            not nonempty_target_lines
            or (not any(state_variables) and not any(canonical_names))
            or pack_blank_query_rows == retrieval_count
            or pack_rows_with_signal == 0
        ):
            failed_packs.append({
                'pack_id': pack_id,
                'split': split,
                'retrieval_rows': retrieval_count,
                'blank_query_rows': pack_blank_query_rows,
                'blank_target_rows': pack_blank_target_rows,
                'fallback_positive_rows': pack_fallback_rows,
                'unmapped_positive_rows': pack_unmapped_positive_rows,
                'locality_risk_rows': pack_local_rows,
                'long_join_rows': pack_long_join_rows,
                'blank_full_target': not bool(nonempty_target_lines),
                'blank_memory_target': not any(state_variables) and not any(canonical_names),
            })

    retrieval_rows = max(1, counts['retrieval_rows'])
    rows_with_signal = counts['rows_with_signal']
    summary = {
        'manifest_path': str(manifest_path),
        'pack_count': len(packs),
        'retrieval_rows': counts['retrieval_rows'],
        'blank_full_target_packs': counts['blank_full_target_packs'],
        'blank_memory_target_packs': counts['blank_memory_target_packs'],
        'blank_query_rows': counts['blank_query_rows'],
        'fallback_positive_rows': counts['fallback_positive_rows'],
        'blank_target_rows': counts['blank_target_rows'],
        'unmapped_positive_rows': counts['unmapped_positive_rows'],
        'locality_risk_rows': counts['locality_risk_rows'],
        'long_join_rows': counts['long_join_rows'],
        'rows_with_signal': rows_with_signal,
        'rates': {
            'blank_query_rate': counts['blank_query_rows'] / retrieval_rows,
            'fallback_positive_rate': counts['fallback_positive_rows'] / retrieval_rows,
            'unmapped_positive_rate': counts['unmapped_positive_rows'] / retrieval_rows,
            'locality_risk_rate': counts['locality_risk_rows'] / max(1, rows_with_signal),
            'long_join_rate': counts['long_join_rows'] / max(1, rows_with_signal),
        },
        'split_counts': {split: dict(sorted(counter.items())) for split, counter in sorted(split_counts.items())},
        'failed_packs': failed_packs[:20],
    }
    failures: list[str] = []
    if counts['blank_full_target_packs'] > 0:
        failures.append('blank_full_target_packs_present')
    if counts['blank_memory_target_packs'] > 0:
        failures.append('blank_memory_target_packs_present')
    if summary['rates']['blank_query_rate'] > 0.05:
        failures.append('blank_query_rate_too_high')
    if summary['rates']['fallback_positive_rate'] > 0.25:
        failures.append('fallback_positive_rate_too_high')
    if summary['rates']['unmapped_positive_rate'] > 0.0:
        failures.append('unmapped_positive_rows_present')
    if rows_with_signal == 0:
        failures.append('no_retrieval_signal_rows')
    else:
        if summary['rates']['locality_risk_rate'] > 0.80:
            failures.append('locality_risk_rate_too_high')
        if summary['rates']['long_join_rate'] < 0.10:
            failures.append('long_join_rate_too_low')
    card = {
        'passed': not failures,
        'failures': failures,
        'summary': summary,
        'decision': 'Held-out strict long-context split quality passed all pressure checks.' if not failures else 'Held-out strict long-context split quality failed; retrieval/state/join pressure is not strong enough for training-grade evaluation.',
    }
    write_json(output_path, card)
    return card


def main() -> None:
    parser = argparse.ArgumentParser(description='Audit held-out strict long-context split quality for locality, retrieval shortcutting, lost-state, and long-range join pressure.')
    parser.add_argument('--manifest', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    audit_strict_long_context_split_quality(manifest_path=args.manifest, output_path=args.output)


if __name__ == '__main__':
    main()
