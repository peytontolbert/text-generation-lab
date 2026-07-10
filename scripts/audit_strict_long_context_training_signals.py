from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from long_context_common import read_jsonl, write_json, write_jsonl

GENERIC_TERMS = {
    'test', 'tests', 'config', 'default', 'init', 'base', 'main', 'utils', 'core', 'model', 'data', 'train',
    'agent', 'patch', 'update', 'file', 'files', 'docs', 'readme', 'script', 'scripts', 'repo', 'repository',
    'torch', 'tensor', 'attention', 'state', 'loss', 'module', 'python', 'class', 'function', 'value', 'runtime'
}
EXEC_ROUTES_REQUIRING_STATE_UPDATES = {'PATCH_PLUS_EXEC'}


def _text_tokens(text: str) -> set[str]:
    token: list[str] = []
    out: list[str] = []
    for char in str(text or '').lower():
        if char.isalnum():
            token.append(char)
            continue
        if len(token) >= 3:
            out.append(''.join(token))
        token = []
    if len(token) >= 3:
        out.append(''.join(token))
    return set(out)


def _norm_path(path: str) -> str:
    return str(path or '').replace('\\', '/').lstrip('./').lower()


def _path_terms(paths: list[str]) -> set[str]:
    out: set[str] = set()
    for path in paths:
        norm = _norm_path(path)
        out.update(term for term in _text_tokens(norm) if term not in GENERIC_TERMS)
    return out


def _symbol_terms(symbols: list[str]) -> set[str]:
    out: set[str] = set()
    for symbol in symbols:
        out.update(term for term in _text_tokens(str(symbol)) if term not in GENERIC_TERMS)
    return out




def _path_suffixes(paths: list[str]) -> set[str]:
    out: set[str] = set()
    for path in paths:
        parts = [part for part in _norm_path(path).split('/') if part]
        if not parts:
            continue
        if len(parts) >= 1:
            out.add(parts[-1])
        if len(parts) >= 2:
            out.add('/'.join(parts[-2:]))
        if len(parts) >= 3:
            out.add('/'.join(parts[-3:]))
    return out


def _symbol_query_terms(symbols: list[str]) -> set[str]:
    out: set[str] = set()
    weak = {'index', '__init__', 'event', 'rows', 'buffer', 'config', 'audio', 'segment', 'fusion', 'enums'}
    for symbol in symbols:
        normalized = str(symbol or '').strip().lower()
        if len(normalized) < 6:
            continue
        if normalized in GENERIC_TERMS or normalized in weak:
            continue
        out.add(normalized)
    return out

def _parse_final_state(target_row: dict[str, Any]) -> dict[str, Any]:
    raw = target_row.get('final_state_json')
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str) and raw.strip():
        return json.loads(raw)
    return {}


def _build_pack_index(context_rows: list[dict[str, Any]]) -> dict[str, Any]:
    exact_path_index: dict[str, list[int]] = defaultdict(list)
    suffix_path_index: dict[str, list[int]] = defaultdict(list)
    term_index: dict[str, list[int]] = defaultdict(list)
    row_terms: list[set[str]] = []
    row_search_text: list[str] = []
    tail_start = max(0, int(len(context_rows) * 0.95))
    for index, row in enumerate(context_rows):
        path_value = _norm_path(str(row.get('path') or ''))
        exact_path_index[path_value].append(index)
        raw_text = str(row.get('text') or '')
        observed_terms = _text_tokens(raw_text) | _text_tokens(path_value)
        row_search_text.append(path_value + "\n" + raw_text.lower())
        parts = [part for part in path_value.split('/') if part]
        if len(parts) >= 1:
            suffix_path_index[parts[-1]].append(index)
        if len(parts) >= 2:
            suffix_path_index['/'.join(parts[-2:])].append(index)
        if len(parts) >= 3:
            suffix_path_index['/'.join(parts[-3:])].append(index)
        row_terms.append(observed_terms)
        for term in observed_terms:
            term_index[term].append(index)
    return {
        'exact_path_index': exact_path_index,
        'suffix_path_index': suffix_path_index,
        'term_index': term_index,
        'row_terms': row_terms,
        'row_search_text': row_search_text,
        'tail_start': tail_start,
        'row_count': len(context_rows),
    }

def _support_row_analysis(target_row: dict[str, Any], context_rows: list[dict[str, Any]], pack_index: dict[str, Any]) -> dict[str, Any]:
    final_state = _parse_final_state(target_row)
    changed_files = [str(item) for item in final_state.get('expected_changed_files') or []]
    verification_targets = [str(item) for item in final_state.get('verification_targets') or []]
    key_symbols = [str(item) for item in final_state.get('key_symbols') or []]
    external_evidence_terms = [str(item) for item in final_state.get('external_evidence_terms') or []]
    execution_route = str(final_state.get('execution_route') or '')

    changed_norm = {_norm_path(path) for path in changed_files}
    verification_norm = {_norm_path(path) for path in verification_targets}
    path_suffixes = _path_suffixes(changed_files + verification_targets)
    path_terms: set[str] = set()
    symbol_terms = _symbol_terms(key_symbols)
    symbol_query_terms = _symbol_query_terms(key_symbols)
    external_query_terms = _symbol_query_terms(external_evidence_terms)

    exact_path_index = pack_index['exact_path_index']
    suffix_path_index = pack_index['suffix_path_index']
    term_index = pack_index['term_index']
    row_terms = pack_index['row_terms']
    row_search_text = pack_index['row_search_text']
    tail_start = int(pack_index['tail_start'])
    total_rows = int(pack_index['row_count'])

    candidate_indexes: set[int] = set()
    for path in changed_norm | verification_norm:
        candidate_indexes.update(exact_path_index.get(path, []))
    for suffix in path_suffixes:
        candidate_indexes.update(suffix_path_index.get(suffix, []))
    if symbol_query_terms or external_query_terms:
        all_query_terms = symbol_query_terms | external_query_terms
        for index, search_text in enumerate(row_search_text):
            if any(symbol in search_text for symbol in all_query_terms):
                candidate_indexes.add(index)

    support_rows: list[dict[str, Any]] = []
    support_ordinals: list[int] = []
    support_paths: set[str] = set()
    support_source_types: Counter[str] = Counter()
    support_roles: Counter[str] = Counter()
    path_hits = 0
    suffix_path_hits = 0
    symbol_hits = 0
    rare_symbol_hits = 0
    verification_hits = 0
    external_hits = 0
    paper_dataset_hits = 0
    tail_hits = 0

    for index in sorted(candidate_indexes):
        row = context_rows[index]
        path = _norm_path(str(row.get('path') or ''))
        observed_terms = row_terms[index]
        source_type = str(row.get('source_type') or 'unknown')
        role = str(row.get('role') or '')
        matched = False
        local_path_hit = False
        local_symbol_hit = False
        local_rare_symbol_hit = False
        local_verification_hit = False

        parts = [part for part in path.split('/') if part]
        row_suffixes = set()
        if len(parts) >= 1:
            row_suffixes.add(parts[-1])
        if len(parts) >= 2:
            row_suffixes.add('/'.join(parts[-2:]))
        if len(parts) >= 3:
            row_suffixes.add('/'.join(parts[-3:]))

        if path and path in changed_norm:
            matched = True
            local_path_hit = True
        if path and path in verification_norm:
            matched = True
            local_verification_hit = True
        if path_suffixes and row_suffixes & path_suffixes:
            matched = True
            if not local_path_hit:
                suffix_path_hits += 1
        if symbol_terms and any(symbol in row_search_text[index] for symbol in symbol_terms):
            matched = True
            local_symbol_hit = True
        if symbol_query_terms and any(symbol in row_search_text[index] for symbol in symbol_query_terms):
            matched = True
            local_rare_symbol_hit = True
        if external_query_terms and any(symbol in row_search_text[index] for symbol in external_query_terms):
            matched = True

        if not matched:
            continue

        support_rows.append(row)
        support_ordinals.append(int(row.get('chunk_ordinal') or index))
        support_paths.add(path)
        support_source_types[source_type] += 1
        support_roles[role] += 1
        if local_path_hit:
            path_hits += 1
        if local_symbol_hit:
            symbol_hits += 1
        if local_rare_symbol_hit:
            rare_symbol_hits += 1
        if local_verification_hit:
            verification_hits += 1
        if source_type != 'local_repo':
            external_hits += 1
        if source_type in {'paper', 'dataset'}:
            paper_dataset_hits += 1
        if index >= tail_start:
            tail_hits += 1

    span_fraction = 0.0
    if support_ordinals and total_rows > 1:
        span_fraction = (max(support_ordinals) - min(support_ordinals)) / max(1, total_rows - 1)
    tail_fraction = (tail_hits / len(support_rows)) if support_rows else 0.0
    support_fraction = (len(support_rows) / total_rows) if total_rows else 0.0
    overbroad_support = support_fraction > 0.35
    path_only_support = bool(support_rows) and path_hits == len(support_rows) and symbol_hits == 0 and paper_dataset_hits == 0
    anchored_hits = path_hits + suffix_path_hits + verification_hits + rare_symbol_hits
    needs_state_update = execution_route in EXEC_ROUTES_REQUIRING_STATE_UPDATES
    verification_bound = verification_hits > 0 or support_roles.get('verification_constraint', 0) > 0
    state_update_supported = (not needs_state_update) or (verification_bound and support_roles.get('seed_change', 0) > 0 and anchored_hits >= 2)

    compact_locality_ready = len(support_rows) >= 4 and len(support_paths) >= 3 and support_fraction <= 0.25 and anchored_hits >= 4
    locality_probe_ready = len(support_rows) >= 3 and len(support_paths) >= 2 and (span_fraction >= 0.20 or compact_locality_ready) and tail_fraction < 0.80 and not overbroad_support and anchored_hits >= 2
    retrieval_probe_ready = external_hits >= 1 and rare_symbol_hits >= 1 and anchored_hits >= 2 and not path_only_support and not overbroad_support
    long_range_join_probe_ready = len(support_source_types) >= 2 and len(support_paths) >= 2 and paper_dataset_hits >= 1 and anchored_hits >= 2 and not overbroad_support

    return {
        'example_id': str(target_row.get('example_id') or ''),
        'program_id': str(target_row.get('program_id') or ''),
        'execution_route': execution_route,
        'support_row_count': len(support_rows),
        'support_path_count': len(support_paths),
        'support_source_type_count': len(support_source_types),
        'span_fraction': span_fraction,
        'tail_fraction': tail_fraction,
        'path_hits': path_hits,
        'suffix_path_hits': suffix_path_hits,
        'symbol_hits': symbol_hits,
        'rare_symbol_hits': rare_symbol_hits,
        'verification_hits': verification_hits,
        'external_hits': external_hits,
        'paper_dataset_hits': paper_dataset_hits,
        'support_role_counts': dict(sorted(support_roles.items())),
        'support_source_type_counts': dict(sorted(support_source_types.items())),
        'locality_probe_ready': locality_probe_ready,
        'retrieval_probe_ready': retrieval_probe_ready,
        'long_range_join_probe_ready': long_range_join_probe_ready,
        'state_update_probe_ready': state_update_supported,
        'support_fraction': support_fraction,
        'overbroad_support': overbroad_support,
        'anchored_hits': anchored_hits,
        'path_only_support': path_only_support,
        'needs_state_update': needs_state_update,
    }


def audit_strict_long_context_training_signals(
    *,
    training_rows_path: Path,
    min_locality_ready_fraction: float = 0.60,
    min_retrieval_ready_fraction: float = 0.55,
    min_long_range_join_ready_fraction: float = 0.40,
    min_state_update_ready_fraction: float = 0.80,
    min_target_rows_for_lost_state_probe: int = 32,
    min_programs_for_lost_state_probe: int = 8,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    training_rows = read_jsonl(training_rows_path)
    pack_rows: list[dict[str, Any]] = []
    target_rows_out: list[dict[str, Any]] = []
    readiness_counts: Counter[str] = Counter()

    for pack in training_rows:
        context_rows = [dict(row) for row in pack.get('context_rows') or [] if isinstance(row, dict)]
        targets = [dict(row) for row in pack.get('target_rows') or [] if isinstance(row, dict)]
        pack_index = _build_pack_index(context_rows)
        target_audits = [_support_row_analysis(target, context_rows, pack_index) for target in targets]
        target_rows_out.extend(target_audits)

        target_count = len(target_audits)
        program_count = len({row['program_id'] for row in target_audits if row['program_id']})
        locality_ready_fraction = (sum(1 for row in target_audits if row['locality_probe_ready']) / target_count) if target_count else 0.0
        retrieval_ready_fraction = (sum(1 for row in target_audits if row['retrieval_probe_ready']) / target_count) if target_count else 0.0
        long_range_join_ready_fraction = (sum(1 for row in target_audits if row['long_range_join_probe_ready']) / target_count) if target_count else 0.0
        state_update_ready_fraction = (sum(1 for row in target_audits if row['state_update_probe_ready']) / target_count) if target_count else 0.0

        lost_state_probe_ready = target_count >= min_target_rows_for_lost_state_probe and program_count >= min_programs_for_lost_state_probe
        locality_probe_ready = locality_ready_fraction >= min_locality_ready_fraction
        retrieval_probe_ready = retrieval_ready_fraction >= min_retrieval_ready_fraction
        long_range_join_probe_ready = long_range_join_ready_fraction >= min_long_range_join_ready_fraction
        state_update_probe_ready = state_update_ready_fraction >= min_state_update_ready_fraction

        if locality_probe_ready:
            readiness_counts['locality_probe_ready'] += 1
        if retrieval_probe_ready:
            readiness_counts['retrieval_probe_ready'] += 1
        if lost_state_probe_ready:
            readiness_counts['lost_state_probe_ready'] += 1
        if long_range_join_probe_ready:
            readiness_counts['long_range_join_probe_ready'] += 1
        if state_update_probe_ready:
            readiness_counts['state_update_probe_ready'] += 1

        fatal_reasons: list[str] = []
        if not locality_probe_ready:
            fatal_reasons.append('insufficient_locality_probe_coverage')
        if not retrieval_probe_ready:
            fatal_reasons.append('insufficient_retrieval_probe_coverage')
        if not lost_state_probe_ready:
            fatal_reasons.append('insufficient_lost_state_probe_coverage')
        if not long_range_join_probe_ready:
            fatal_reasons.append('insufficient_long_range_join_probe_coverage')
        if not state_update_probe_ready:
            fatal_reasons.append('insufficient_state_update_probe_coverage')

        pack_rows.append({
            'pack_id': str(pack.get('pack_id') or ''),
            'pack_token_count': int(pack.get('pack_token_count') or 0),
            'chunk_count': int(pack.get('chunk_count') or 0),
            'target_count': target_count,
            'program_count': program_count,
            'locality_ready_fraction': locality_ready_fraction,
            'retrieval_ready_fraction': retrieval_ready_fraction,
            'long_range_join_ready_fraction': long_range_join_ready_fraction,
            'state_update_ready_fraction': state_update_ready_fraction,
            'locality_probe_ready': locality_probe_ready,
            'retrieval_probe_ready': retrieval_probe_ready,
            'lost_state_probe_ready': lost_state_probe_ready,
            'long_range_join_probe_ready': long_range_join_probe_ready,
            'state_update_probe_ready': state_update_probe_ready,
            'fatal_reasons': fatal_reasons,
            'accepted': not fatal_reasons,
        })

    summary = {
        'pack_count': len(pack_rows),
        'target_audit_count': len(target_rows_out),
        'accepted_pack_count': sum(1 for row in pack_rows if row['accepted']),
        'readiness_counts': dict(sorted(readiness_counts.items())),
        'thresholds': {
            'min_locality_ready_fraction': float(min_locality_ready_fraction),
            'min_retrieval_ready_fraction': float(min_retrieval_ready_fraction),
            'min_long_range_join_ready_fraction': float(min_long_range_join_ready_fraction),
            'min_state_update_ready_fraction': float(min_state_update_ready_fraction),
            'min_target_rows_for_lost_state_probe': int(min_target_rows_for_lost_state_probe),
            'min_programs_for_lost_state_probe': int(min_programs_for_lost_state_probe),
        },
        'top_failing_packs': [row for row in pack_rows if not row['accepted']][:10],
    }
    return pack_rows, target_rows_out, summary


def main() -> None:
    parser = argparse.ArgumentParser(description='Audit strict long-context pack training rows for mining completeness against long-context failure modes.')
    parser.add_argument('--training-rows', type=Path, required=True)
    parser.add_argument('--pack-output', type=Path, required=True)
    parser.add_argument('--target-output', type=Path, required=True)
    parser.add_argument('--summary-output', type=Path, required=True)
    parser.add_argument('--min-locality-ready-fraction', type=float, default=0.60)
    parser.add_argument('--min-retrieval-ready-fraction', type=float, default=0.55)
    parser.add_argument('--min-long-range-join-ready-fraction', type=float, default=0.40)
    parser.add_argument('--min-state-update-ready-fraction', type=float, default=0.80)
    parser.add_argument('--min-target-rows-for-lost-state-probe', type=int, default=32)
    parser.add_argument('--min-programs-for-lost-state-probe', type=int, default=8)
    args = parser.parse_args()

    pack_rows, target_rows, summary = audit_strict_long_context_training_signals(
        training_rows_path=args.training_rows,
        min_locality_ready_fraction=args.min_locality_ready_fraction,
        min_retrieval_ready_fraction=args.min_retrieval_ready_fraction,
        min_long_range_join_ready_fraction=args.min_long_range_join_ready_fraction,
        min_state_update_ready_fraction=args.min_state_update_ready_fraction,
        min_target_rows_for_lost_state_probe=args.min_target_rows_for_lost_state_probe,
        min_programs_for_lost_state_probe=args.min_programs_for_lost_state_probe,
    )
    write_jsonl(args.pack_output, pack_rows)
    write_jsonl(args.target_output, target_rows)
    write_json(args.summary_output, summary)


if __name__ == '__main__':
    main()
