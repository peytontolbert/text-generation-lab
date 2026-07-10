from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from long_context_common import extract_compound_terms, extract_terms, stable_id, write_json, write_jsonl

GENERIC_QUERY_TERMS = {'src', 'main', 'index', 'test', 'tests', 'app', 'lib', 'core', 'script', 'scripts', 'model', 'models', 'utils', 'helper', 'helpers'}
LOW_SIGNAL_QUERY_TERMS = {'dict', 'path', 'paths', 'call', 'unit', 'readme', 'mod', 'client', 'data', 'line', 'lines', 'file', 'files', 'item', 'items', 'value', 'values', 'result', 'results', 'any', 'all', 'get', 'set', 'str', 'int', 'float', 'bool', 'list', 'train', 'training', 'loss', 'loop', 'config', 'state', 'runtime'}
CODE_SUFFIXES = {'.py', '.ts', '.tsx', '.js', '.jsx', '.java', '.go', '.rs', '.c', '.cc', '.cpp', '.h', '.hpp', '.sh'}
CONFIG_SUFFIXES = {'.json', '.yaml', '.yml', '.toml', '.cfg', '.ini', '.xml'}
DOC_SUFFIXES = {'.md', '.rst', '.txt'}
BAD_REPO_PATH_FRAGMENTS = ('readme', 'years/', 'newsletter', 'awesome-', 'papers-of-the-week')
BAD_PAPER_PATH_FRAGMENTS = ('structured/repo_skills_miner', 'repos_chunks/', '.edges.jsonl', '.entities.jsonl', '.artifacts.jsonl')
BAD_DATASET_PATH_FRAGMENTS = ('/readme.md', '/readme.rst', '/readme.txt')
TRACE_HINT_TERMS = {'trace', 'error', 'stack', 'runtime', 'assert', 'failure', 'bug', 'exception', 'stderr', 'stdout', 'log'}
SOFTWARE_PAPER_HINT_TERMS = {'algorithm', 'model', 'training', 'inference', 'attention', 'retrieval', 'memory', 'agent', 'software', 'code', 'execution', 'debug', 'verification', 'compiler', 'benchmark', 'repair', 'patch'}
STRONG_VERIFIED_ROUTES = {'PATCH_PLUS_EXEC', 'PATCH_PLUS_VERIFY', 'COMMIT_PLUS_VERIFY', 'COMMIT_PLUS_VERIFY'}
GENERIC_OVERLAP_TERMS = GENERIC_QUERY_TERMS | LOW_SIGNAL_QUERY_TERMS | TRACE_HINT_TERMS | SOFTWARE_PAPER_HINT_TERMS | {'config', 'issue', 'goal', 'task', 'route'}
SOURCE_TYPE_ABS_SCORE_FLOORS = {'repo': 2.5, 'paper': 2.0, 'dataset': 1.0}
SOURCE_TYPE_REL_SCORE_FLOORS = {'repo': 0.12, 'paper': 0.06, 'dataset': 0.18}
SOURCE_TYPE_SOURCE_ID_CAPS = {'repo': 16, 'paper': 12, 'dataset': 8}
SOURCE_TYPE_PATH_CAPS = {'repo': 1, 'paper': 1, 'dataset': 1}
MAX_QUERY_SEED_SYMBOLS = 12
MAX_QUERY_CHANGED_PATHS = 12
MAX_QUERY_VERIFICATION_TARGETS = 12


def _read_parquet_rows(directory: Path) -> list[dict[str, Any]]:
    import pyarrow.parquet as pq

    rows: list[dict[str, Any]] = []
    for path in sorted(directory.glob('*.parquet')):
        rows.extend(pq.read_table(path).to_pylist())
    return rows


def _norm_path(path: str) -> str:
    return str(path or '').replace('\\', '/').lstrip('./')


def _metadata(row: dict[str, Any]) -> dict[str, Any]:
    value = row.get('metadata_json') or '{}'
    if isinstance(value, dict):
        return value
    return json.loads(str(value))


def _mention_dir(index_dir: Path) -> Path:
    if (index_dir / 'chunk_mentions').is_dir():
        return index_dir / 'chunk_mentions'
    return index_dir / 'mentions'


def _existing_chunk_ids(row: dict[str, Any]) -> set[str]:
    return {str(context_row.get('chunk_id') or '') for context_row in row.get('context_rows', []) if str(context_row.get('chunk_id') or '')}


def _split_term_variants(value: str) -> list[str]:
    compact = str(value or '').strip()
    if not compact:
        return []
    normalized = []
    token = []
    for char in compact:
        if char.isalnum():
            token.append(char)
        else:
            token.append(' ')
    base = ''.join(token)
    for piece in base.replace('_', ' ').replace('-', ' ').split():
        if not piece:
            continue
        normalized.append(piece.lower())
        camel = []
        current = []
        for ch in piece:
            if current and ch.isupper() and not current[-1].isupper():
                camel.append(''.join(current).lower())
                current = [ch]
            else:
                current.append(ch)
        if current:
            camel.append(''.join(current).lower())
        normalized.extend(part for part in camel if part)
    deduped = []
    seen = set()
    for part in normalized:
        if len(part) < 3 or part in seen:
            continue
        seen.add(part)
        deduped.append(part)
    return deduped


def _path_terms(paths: list[str]) -> list[str]:
    terms: list[str] = []
    for path in paths:
        normalized = _norm_path(path)
        name = normalized.rsplit('/', 1)[-1]
        stem = name.rsplit('.', 1)[0]
        terms.extend(_split_term_variants(stem))
        for segment in normalized.split('/'):
            terms.extend(_split_term_variants(segment.rsplit('.', 1)[0]))
    return terms


def _text_terms(text: str) -> set[str]:
    return set(_split_term_variants(str(text or '')))


def _path_suffix_terms(paths: list[str]) -> list[str]:
    terms: list[str] = []
    for path in paths:
        normalized = _norm_path(path).lower()
        parts = [part for part in normalized.split('/') if part]
        if not parts:
            continue
        candidates = []
        if len(parts) >= 1:
            candidates.append(parts[-1].rsplit('.', 1)[0])
        if len(parts) >= 2:
            candidates.append('/'.join(parts[-2:]).rsplit('.', 1)[0])
        if len(parts) >= 3:
            candidates.append('/'.join(parts[-3:]).rsplit('.', 1)[0])
        for candidate in candidates:
            value = candidate.strip().lower()
            if value and _is_useful_query_term(value):
                terms.append(value)
    return terms


def _rare_symbol_terms(symbols: list[str]) -> list[str]:
    terms: list[str] = []
    seen: set[str] = set()
    for raw_symbol in symbols:
        symbol = str(raw_symbol or '').strip()
        if not symbol:
            continue
        if '.' not in symbol and '_' not in symbol and not any(ch.isupper() for ch in symbol[1:]):
            continue
        for term in _split_term_variants(symbol):
            value = term.strip().lower()
            if value in seen or not _is_useful_query_term(value):
                continue
            if len(value) < 5:
                continue
            seen.add(value)
            terms.append(value)
    return terms

def _non_generic_terms(values: set[str]) -> set[str]:
    return {
        term for term in values
        if _is_useful_query_term(term) and term not in GENERIC_OVERLAP_TERMS
    }


def _goal_field_values(goal: str, prefix: str) -> list[str]:
    values: list[str] = []
    wanted = f'{prefix.lower()}:'
    for line in str(goal or '').splitlines():
        stripped = line.strip()
        if not stripped.lower().startswith(wanted):
            continue
        payload = stripped.split(':', 1)[1].strip()
        if not payload:
            continue
        values.extend(part.strip() for part in payload.split(',') if part.strip())
    return values


def _path_priority(path: str) -> tuple[int, int, str]:
    normalized = _norm_path(path).lower()
    name = normalized.rsplit('/', 1)[-1]
    score = 0
    if '/test' in normalized or normalized.startswith('tests/'):
        score += 3
    if any(segment in normalized for segment in ('src/', 'core/', 'model', 'inference', 'engine', 'train', 'loader')):
        score += 2
    if name.startswith('test_'):
        score += 2
    return (-score, len(normalized), normalized)


def _compact_seed_symbols(symbols: list[str], *, row: dict[str, Any], max_symbols: int) -> list[str]:
    if max_symbols <= 0:
        return []
    goal = str(row.get('goal') or '')
    seed_paths = [_norm_path(path).lower() for path in list(row.get('seed_paths', []))]
    selected_tests = [_norm_path(path).lower() for path in list(row.get('selected_tests', []))]
    goal_symbols = {item.lower() for item in _goal_field_values(goal, 'Key symbols')}
    local_context = '\n'.join(
        str(context_row.get('text') or '')[:4000]
        for context_row in row.get('context_rows', [])
        if str(context_row.get('role') or '') in {'seed_change', 'verification_constraint'}
    ).lower()
    ranked: list[tuple[tuple[int, int, int, str], str]] = []
    seen: set[str] = set()
    for raw_symbol in symbols:
        symbol = str(raw_symbol or '').strip()
        if not symbol:
            continue
        root = symbol.split('.', 1)[0].strip()
        if not root or root.startswith('__') or root.endswith('__'):
            continue
        lower_root = root.lower()
        if lower_root in seen or not _is_useful_query_term(lower_root):
            continue
        variants = {lower_root, *_split_term_variants(root)}
        if not any(_is_useful_query_term(variant) for variant in variants):
            continue
        priority = 0
        if lower_root in goal_symbols:
            priority += 5
        if any(lower_root in path for path in seed_paths):
            priority += 4
        if any(lower_root in path for path in selected_tests):
            priority += 3
        if f'{lower_root}(' in local_context or f'class {lower_root}' in local_context:
            priority += 2
        if '.' not in symbol:
            priority += 1
        if len(root) <= 32:
            priority += 1
        seen.add(lower_root)
        ranked.append(((-priority, len(root), len(symbol), lower_root), lower_root))
    ranked.sort(key=lambda item: item[0])
    return [symbol for _, symbol in ranked[:max_symbols]]


def _is_useful_query_term(value: str) -> bool:
    term = str(value or '').strip().lower()
    if len(term) < 3:
        return False
    if term in GENERIC_QUERY_TERMS or term in LOW_SIGNAL_QUERY_TERMS:
        return False
    if term.startswith('__') or term.endswith('__'):
        return False
    if not any(char.isalpha() for char in term):
        return False
    compact = term.replace('_', '')
    if not compact.isalnum():
        return False
    if term[0].isdigit():
        return False
    return True


def _episode_query_terms(row: dict[str, Any], *, max_terms: int) -> list[str]:
    goal = str(row.get('goal') or '')
    goal_changed_paths = _goal_field_values(goal, 'Changed files')
    goal_selected_tests = _goal_field_values(goal, 'Verification targets')
    goal_commit_subject = _goal_field_values(goal, 'Commit subject')
    selected_seed_paths = sorted(
        {str(item).strip() for item in (goal_changed_paths or list(row.get('seed_paths', []))) if str(item).strip()},
        key=_path_priority,
    )[:MAX_QUERY_CHANGED_PATHS]
    selected_tests = sorted(
        {str(item).strip() for item in (goal_selected_tests or list(row.get('selected_tests', []))) if str(item).strip()},
        key=_path_priority,
    )[:MAX_QUERY_VERIFICATION_TARGETS]
    compact_symbols = _compact_seed_symbols(list(row.get('seed_symbols', [])), row=row, max_symbols=MAX_QUERY_SEED_SYMBOLS)
    symbols = ' '.join(compact_symbols)
    paths = ' '.join(selected_seed_paths)
    tests = ' '.join(selected_tests)
    local_seed_text = '\n'.join(
        str(context_row.get('text') or '')[:4000]
        for context_row in row.get('context_rows', [])
        if str(context_row.get('role') or '') in {'seed_change', 'repo_graph_neighbor', 'verification_constraint'}
    )
    structured_text = '\n'.join(part for part in [goal, ' '.join(goal_commit_subject), symbols, paths, tests] if part)
    terms = extract_terms(structured_text, max_terms=max_terms)
    compounds = extract_compound_terms(structured_text, max_terms=max_terms)
    local_seed_compounds = extract_compound_terms(local_seed_text, max_terms=max_terms // 2)
    path_suffix_terms = _path_suffix_terms(selected_seed_paths + selected_tests)
    rare_symbols = _rare_symbol_terms(compact_symbols)
    combined: list[str] = []
    seen: set[str] = set()
    candidate_terms: list[str] = []
    for term in path_suffix_terms + compact_symbols + rare_symbols + goal_commit_subject + _path_terms(selected_seed_paths) + _path_terms(selected_tests) + compounds + local_seed_compounds + terms:
        candidate_terms.append(str(term or '').strip())
        candidate_terms.extend(_split_term_variants(str(term or '').strip()))
    for term in candidate_terms:
        value = str(term or '').strip().lower()
        if value in seen or not _is_useful_query_term(value):
            continue
        if value in LOW_SIGNAL_QUERY_TERMS or value in GENERIC_OVERLAP_TERMS:
            continue
        seen.add(value)
        combined.append(value)
        if len(combined) >= max_terms:
            break
    if not combined:
        raise ValueError(f"no_query_terms:{row.get('episode_id')}")
    return combined


def _chunk_row_from_index(row: dict[str, Any], *, role: str, retrieval_reason: str, retrieval_score: float, distance_from_seed: int) -> dict[str, Any]:
    metadata = _metadata(row)
    return {
        'chunk_id': str(row.get('chunk_id') or ''),
        'source_type': str(row.get('source_type') or ''),
        'source_id': str(row.get('source_id') or ''),
        'doc_id': str(row.get('doc_id') or ''),
        'path': _norm_path(str(metadata.get('path') or '')),
        'chunk_index': int(row.get('chunk_index') or 0),
        'token_count': int(row.get('token_count') or 0),
        'text': str(row.get('text') or ''),
        'role': role,
        'retrieval_reason': retrieval_reason,
        'distance_from_seed': int(distance_from_seed),
        'retrieval_score': float(retrieval_score),
    }


def _doc_groups(chunk_by_id: dict[str, dict[str, Any]]) -> dict[tuple[str, str, str], list[dict[str, Any]]]:
    groups: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in chunk_by_id.values():
        key = (
            str(row.get('source_type') or ''),
            str(row.get('source_id') or ''),
            str(row.get('doc_id') or ''),
        )
        groups[key].append(row)
    for rows in groups.values():
        rows.sort(key=lambda row: (int(row.get('chunk_index') or 0), str(row.get('chunk_id') or '')))
    return groups


def _role_for_source_type(source_type: str) -> str:
    if source_type == 'paper':
        return 'algorithm_grounding'
    if source_type == 'dataset':
        return 'trace_analogue'
    return 'cross_repo_analogue'


def _shared_terms(*, path: str, text: str, ref_terms: set[str]) -> set[str]:
    return ref_terms & (_text_terms(path) | _text_terms(text))


def _category_hits(
    *,
    path: str,
    text: str,
    seed_path_terms: set[str],
    selected_test_terms: set[str],
    seed_symbol_terms: set[str],
) -> set[str]:
    observed = _text_terms(path) | _text_terms(text)
    hits: set[str] = set()
    if observed & seed_path_terms:
        hits.add('seed_path')
    if observed & selected_test_terms:
        hits.add('verification_target')
    if observed & seed_symbol_terms:
        hits.add('seed_symbol')
    return hits


def _verification_binding_hits(*, path: str, text: str, selected_test_terms: set[str]) -> set[str]:
    observed = _text_terms(path) | _text_terms(text)
    return observed & selected_test_terms


def _is_allowed_chunk(
    *,
    source_type: str,
    path: str,
    text: str,
    shared_terms: set[str],
    strong_shared_terms: set[str],
    category_hits: set[str],
    strict_anchor_hits: set[str],
    suffix_anchor_hits: set[str],
) -> bool:
    norm = _norm_path(path).lower()
    suffix = Path(norm).suffix.lower()
    lower_text = str(text or '').lower()
    if not strong_shared_terms and not category_hits and not strict_anchor_hits:
        return False
    if source_type == 'repo':
        if any(fragment in norm for fragment in BAD_REPO_PATH_FRAGMENTS):
            return False
        if suffix not in CODE_SUFFIXES | CONFIG_SUFFIXES | DOC_SUFFIXES:
            return False
        if 'seed_symbol' in category_hits or 'verification_target' in category_hits:
            return True
        if 'seed_path' in category_hits and (len(strict_anchor_hits) >= 2 or len(strong_shared_terms) >= 2):
            return True
        if len(strict_anchor_hits) >= 2:
            return True
        return bool(suffix_anchor_hits) and len(strong_shared_terms) >= 2 and len(strict_anchor_hits) >= 1
    if source_type == 'paper':
        if any(fragment in norm for fragment in BAD_PAPER_PATH_FRAGMENTS):
            return False
        if not any(term in norm or term in lower_text for term in SOFTWARE_PAPER_HINT_TERMS):
            return False
        return bool(strict_anchor_hits) or len(strong_shared_terms) >= 1
    if source_type == 'dataset':
        if any(fragment in norm for fragment in BAD_DATASET_PATH_FRAGMENTS):
            return False
        if not any(term in norm or term in lower_text for term in TRACE_HINT_TERMS):
            return False
        return bool(strict_anchor_hits) or len(strong_shared_terms) >= 1 or 'verification_target' in category_hits
    return False


def _select_augmented_chunks(
    *,
    row: dict[str, Any],
    query_terms: list[str],
    inverted_mentions: dict[str, list[dict[str, Any]]],
    chunk_by_id: dict[str, dict[str, Any]],
    chunk_doc_groups: dict[tuple[str, str, str], list[dict[str, Any]]],
    max_term_docfreq: int,
    external_token_budget: int,
    max_augmented_chunks: int,
    max_chunks_per_source_type: int,
    max_chunks_per_source_id: int,
    max_chunks_per_path: int,
    neighbor_window: int,
    max_neighbor_chunks_per_anchor: int,
    min_external_chunks: int,
) -> list[dict[str, Any]]:
    existing = _existing_chunk_ids(row)
    candidate_scores: dict[str, float] = defaultdict(float)
    candidate_reasons: dict[str, list[str]] = defaultdict(list)
    source_type_counts: Counter[str] = Counter()
    source_id_counts: Counter[str] = Counter()
    path_counts: Counter[str] = Counter()
    query_term_set = set(query_terms)
    repo_id = str(row.get('repo_id') or '')
    seed_path_terms = _non_generic_terms(set(_path_suffix_terms(list(row.get('seed_paths', [])))))
    selected_test_terms = _non_generic_terms(set(_path_suffix_terms(list(row.get('selected_tests', [])))))
    seed_symbol_terms = _non_generic_terms({_norm_path(term).lower() for term in list(row.get('seed_symbols', [])) if str(term).strip()})
    rare_seed_symbol_terms = _non_generic_terms(set(_rare_symbol_terms(list(row.get('seed_symbols', [])))))
    path_suffix_terms = _non_generic_terms(set(_path_suffix_terms(list(row.get('seed_paths', [])) + list(row.get('selected_tests', [])))))
    ref_terms = query_term_set | seed_path_terms | selected_test_terms | seed_symbol_terms | rare_seed_symbol_terms | path_suffix_terms
    strong_ref_terms = _non_generic_terms(ref_terms)

    for term in query_terms:
        hits = inverted_mentions.get(term, [])
        if not hits or len(hits) > max_term_docfreq:
            continue
        weight = 1.0 / max(1.0, len(hits) ** 0.5)
        for hit in hits:
            chunk_id = str(hit.get('chunk_id') or '')
            if not chunk_id or chunk_id in existing:
                continue
            chunk = chunk_by_id.get(chunk_id)
            if not chunk:
                continue
            source_type = str(chunk.get('source_type') or '')
            if source_type == 'repo' and str(chunk.get('source_id') or '') == repo_id:
                continue
            metadata = _metadata(chunk)
            path = _norm_path(str(metadata.get('path') or ''))
            text = str(chunk.get('text') or '')
            shared = _shared_terms(path=path, text=text, ref_terms=ref_terms)
            strong_shared = shared & strong_ref_terms
            category_hits = _category_hits(
                path=path,
                text=text,
                seed_path_terms=seed_path_terms,
                selected_test_terms=selected_test_terms,
                seed_symbol_terms=seed_symbol_terms,
            )
            strict_anchor_hits = shared & (rare_seed_symbol_terms | selected_test_terms | seed_path_terms)
            suffix_anchor_hits = shared & path_suffix_terms
            if not _is_allowed_chunk(
                source_type=source_type,
                path=path,
                text=text,
                shared_terms=shared,
                strong_shared_terms=strong_shared,
                category_hits=category_hits,
                strict_anchor_hits=strict_anchor_hits,
                suffix_anchor_hits=suffix_anchor_hits,
            ):
                continue
            anchored_term_hits = (shared & (rare_seed_symbol_terms | path_suffix_terms | selected_test_terms | seed_path_terms))
            strict_anchor_hits = shared & (rare_seed_symbol_terms | selected_test_terms | seed_path_terms)
            if not strict_anchor_hits and not category_hits:
                continue
            score = weight + (0.18 * len(strong_shared)) + (0.08 * len(shared))
            if source_type == 'repo':
                score += 0.45
            elif source_type == 'paper':
                score += 0.30
            elif source_type == 'dataset':
                score += 0.20
            score += 0.35 * len(category_hits)
            verification_binding = _verification_binding_hits(path=path, text=text, selected_test_terms=selected_test_terms)
            if verification_binding:
                score += 0.50 + (0.08 * len(verification_binding))
            if term in path_suffix_terms and term in path.lower():
                score += 1.00
            if term in seed_path_terms and term in path.lower():
                score += 0.75
            if term in selected_test_terms and term in text.lower():
                score += 0.70
            if term in rare_seed_symbol_terms and term in text.lower():
                score += 0.70
            elif term in seed_symbol_terms and term in text.lower():
                score += 0.35
            candidate_scores[chunk_id] += score
            observed_terms = _text_terms(path) | _text_terms(text)
            candidate_reasons[chunk_id].extend(f'{label}:{value}' for label, values in (
                ('seed_path', sorted(observed_terms & seed_path_terms)[:3]),
                ('path_suffix', sorted(observed_terms & path_suffix_terms)[:3]),
                ('verification_target', sorted(observed_terms & selected_test_terms)[:3]),
                ('seed_symbol', sorted(observed_terms & seed_symbol_terms)[:3]),
                ('rare_seed_symbol', sorted(observed_terms & rare_seed_symbol_terms)[:3]),
            ) for value in values)
            candidate_reasons[chunk_id].extend(sorted(strong_shared)[:8])

    ranked: list[tuple[float, str]] = []
    source_type_top_scores: dict[str, float] = {}
    for chunk_id, score in candidate_scores.items():
        chunk = chunk_by_id.get(chunk_id)
        if not chunk:
            continue
        metadata = _metadata(chunk)
        path = _norm_path(str(metadata.get('path') or ''))
        text = str(chunk.get('text') or '')
        shared_terms = sorted(_shared_terms(path=path, text=text, ref_terms=ref_terms))[:12]
        strong_shared_terms = sorted((set(shared_terms) & strong_ref_terms))[:12]
        category_hits = _category_hits(
            path=path,
            text=text,
            seed_path_terms=seed_path_terms,
            selected_test_terms=selected_test_terms,
            seed_symbol_terms=seed_symbol_terms,
        )
        anchored_term_hits = set(shared_terms) & (rare_seed_symbol_terms | path_suffix_terms | selected_test_terms | seed_path_terms)
        if not strong_shared_terms and not category_hits and not strict_anchor_hits:
            continue
        if not strict_anchor_hits and 'verification_target' not in category_hits and not ('seed_symbol' in category_hits or 'seed_path' in category_hits):
            continue
        verification_binding = _verification_binding_hits(path=path, text=text, selected_test_terms=selected_test_terms)
        anchored_term_hits = set(shared_terms) & (rare_seed_symbol_terms | path_suffix_terms | selected_test_terms | seed_path_terms)
        final_score = score + 0.12 * len(strong_shared_terms) + 0.06 * len(shared_terms) + 0.20 * len(category_hits) + 0.30 * len(anchored_term_hits)
        if verification_binding:
            final_score += 0.40 + (0.05 * len(verification_binding))
        source_type = str(chunk.get('source_type') or '')
        current_top = source_type_top_scores.get(source_type, 0.0)
        if final_score > current_top:
            source_type_top_scores[source_type] = final_score
        ranked.append((final_score, chunk_id))
        candidate_reasons[chunk_id].extend(sorted(anchored_term_hits)[:8])
        candidate_reasons[chunk_id].extend(strong_shared_terms)
        if path:
            candidate_reasons[chunk_id].append(path.rsplit('/', 1)[-1].lower())

    selected: list[dict[str, Any]] = []
    selected_chunk_ids: set[str] = set()
    total_tokens = 0
    for score, chunk_id in sorted(ranked, key=lambda item: (-item[0], item[1])):
        if len(selected) >= max_augmented_chunks or total_tokens >= external_token_budget:
            break
        chunk = chunk_by_id[chunk_id]
        source_type = str(chunk.get('source_type') or '')
        source_type_top_score = float(source_type_top_scores.get(source_type, 0.0))
        abs_floor = float(SOURCE_TYPE_ABS_SCORE_FLOORS.get(source_type, 0.0))
        rel_floor = float(SOURCE_TYPE_REL_SCORE_FLOORS.get(source_type, 0.0))
        effective_floor = max(abs_floor, source_type_top_score * rel_floor)
        if float(score) < effective_floor:
            continue
        source_id = str(chunk.get('source_id') or '')
        metadata = _metadata(chunk)
        path = _norm_path(str(metadata.get('path') or ''))
        path_key = f'{source_type}:{path}'
        if source_type_counts[source_type] >= max_chunks_per_source_type:
            continue
        source_id_cap = min(int(max_chunks_per_source_id), int(SOURCE_TYPE_SOURCE_ID_CAPS.get(source_type, max_chunks_per_source_id)))
        if source_id_counts[source_id] >= source_id_cap:
            continue
        path_cap = min(int(max_chunks_per_path), int(SOURCE_TYPE_PATH_CAPS.get(source_type, max_chunks_per_path)))
        if path_counts[path_key] >= path_cap:
            continue
        token_count = int(chunk.get('token_count') or 0)
        if selected and total_tokens + token_count > external_token_budget:
            continue
        source_type_counts[source_type] += 1
        source_id_counts[source_id] += 1
        path_counts[path_key] += 1
        total_tokens += token_count
        reason_terms = []
        seen_terms: set[str] = set()
        for term in candidate_reasons.get(chunk_id, []):
            value = str(term or '').strip().lower()
            if not value or value in seen_terms:
                continue
            seen_terms.add(value)
            reason_terms.append(value)
            if len(reason_terms) >= 8:
                break
        selected_row = _chunk_row_from_index(
            chunk,
            role=_role_for_source_type(source_type),
            retrieval_reason='|'.join(reason_terms),
            retrieval_score=float(score),
            distance_from_seed=2 if source_type == 'repo' else 3,
        )
        selected.append(selected_row)
        selected_chunk_ids.add(chunk_id)

    if len(selected) < min_external_chunks:
        raise ValueError(f"insufficient_anchor_chunks:{row.get('episode_id')}:{len(selected)}<{min_external_chunks}")

    anchor_rows = list(selected)
    for anchor_row in anchor_rows:
        if len(selected) >= max_augmented_chunks or total_tokens >= external_token_budget:
            break
        anchor_source_type = str(anchor_row.get('source_type') or '')
        if anchor_source_type != 'repo':
            continue
        key = (
            anchor_source_type,
            str(anchor_row.get('source_id') or ''),
            str(anchor_row.get('doc_id') or ''),
        )
        doc_rows = chunk_doc_groups.get(key, [])
        if len(doc_rows) <= 1:
            continue
        anchor_chunk_id = str(anchor_row.get('chunk_id') or '')
        anchor_index = None
        for index, chunk in enumerate(doc_rows):
            if str(chunk.get('chunk_id') or '') == anchor_chunk_id:
                anchor_index = index
                break
        if anchor_index is None:
            continue
        neighbor_offsets: list[int] = []
        for distance in range(1, neighbor_window + 1):
            neighbor_offsets.extend([-distance, distance])
        added_for_anchor = 0
        for offset in neighbor_offsets:
            if len(selected) >= max_augmented_chunks or total_tokens >= external_token_budget:
                break
            if added_for_anchor >= max_neighbor_chunks_per_anchor:
                break
            neighbor_position = anchor_index + offset
            if neighbor_position < 0 or neighbor_position >= len(doc_rows):
                continue
            neighbor_chunk = doc_rows[neighbor_position]
            neighbor_chunk_id = str(neighbor_chunk.get('chunk_id') or '')
            if not neighbor_chunk_id or neighbor_chunk_id in existing or neighbor_chunk_id in selected_chunk_ids:
                continue
            source_type = str(neighbor_chunk.get('source_type') or '')
            source_id = str(neighbor_chunk.get('source_id') or '')
            metadata = _metadata(neighbor_chunk)
            path = _norm_path(str(metadata.get('path') or ''))
            path_key = f'{source_type}:{path}'
            text = str(neighbor_chunk.get('text') or '')
            shared = _shared_terms(path=path, text=text, ref_terms=ref_terms)
            strong_shared = shared & strong_ref_terms
            category_hits = _category_hits(
                path=path,
                text=text,
                seed_path_terms=seed_path_terms,
                selected_test_terms=selected_test_terms,
                seed_symbol_terms=seed_symbol_terms,
            )
            strict_anchor_hits = shared & (rare_seed_symbol_terms | selected_test_terms | seed_path_terms)
            suffix_anchor_hits = shared & path_suffix_terms
            if not _is_allowed_chunk(
                source_type=source_type,
                path=path,
                text=text,
                shared_terms=shared,
                strong_shared_terms=strong_shared,
                category_hits=category_hits,
                strict_anchor_hits=strict_anchor_hits,
                suffix_anchor_hits=suffix_anchor_hits,
            ):
                continue
            if source_type_counts[source_type] >= max_chunks_per_source_type:
                continue
            source_id_cap = min(int(max_chunks_per_source_id), int(SOURCE_TYPE_SOURCE_ID_CAPS.get(source_type, max_chunks_per_source_id)))
            if source_id_counts[source_id] >= source_id_cap:
                continue
            path_cap = min(int(max_chunks_per_path), int(SOURCE_TYPE_PATH_CAPS.get(source_type, max_chunks_per_path)))
            if path_counts[path_key] >= path_cap:
                continue
            token_count = int(neighbor_chunk.get('token_count') or 0)
            if selected and total_tokens + token_count > external_token_budget:
                continue
            source_type_counts[source_type] += 1
            source_id_counts[source_id] += 1
            path_counts[path_key] += 1
            total_tokens += token_count
            selected_chunk_ids.add(neighbor_chunk_id)
            added_for_anchor += 1
            distance = abs(offset)
            selected.append(
                _chunk_row_from_index(
                    neighbor_chunk,
                    role=_role_for_source_type(source_type),
                    retrieval_reason=f'doc_neighbor|anchor:{anchor_chunk_id}|distance:{distance}',
                    retrieval_score=max(0.0, float(anchor_row.get('retrieval_score') or 0.0) - (0.04 * distance)),
                    distance_from_seed=int(anchor_row.get('distance_from_seed') or 0) + distance,
                )
            )
    return selected


def _role_priority(role: str) -> int:
    priorities = {
        'verification_constraint': 0,
        'seed_change': 1,
        'test_neighbor': 2,
        'repo_graph_neighbor': 3,
        'cross_repo_analogue': 4,
        'algorithm_grounding': 5,
        'trace_analogue': 6,
    }
    return priorities.get(str(role or ''), 99)


def _dedupe_context_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_chunk_id: dict[str, dict[str, Any]] = {}
    for row in rows:
        chunk_id = str(row.get('chunk_id') or '')
        current = by_chunk_id.get(chunk_id)
        if current is None:
            by_chunk_id[chunk_id] = row
            continue
        current_score = (_role_priority(str(current.get('role') or '')), int(current.get('distance_from_seed') or 0), -float(current.get('retrieval_score') or 0.0))
        new_score = (_role_priority(str(row.get('role') or '')), int(row.get('distance_from_seed') or 0), -float(row.get('retrieval_score') or 0.0))
        if new_score < current_score:
            by_chunk_id[chunk_id] = row
    return sorted(
        by_chunk_id.values(),
        key=lambda row: (
            _role_priority(str(row.get('role') or '')),
            int(row.get('distance_from_seed') or 0),
            str(row.get('source_type') or ''),
            str(row.get('path') or ''),
            int(row.get('chunk_index') or 0),
            str(row.get('chunk_id') or ''),
        ),
    )


def augment_session_episode_context(
    *,
    episodes_path: Path,
    index_dir: Path,
    external_token_budget: int = 250_000,
    max_query_terms: int = 24,
    max_term_docfreq: int = 2500,
    max_augmented_chunks: int = 320,
    max_chunks_per_source_type: int = 128,
    max_chunks_per_source_id: int = 16,
    max_chunks_per_path: int = 4,
    neighbor_window: int = 2,
    max_neighbor_chunks_per_anchor: int = 4,
    min_external_chunks: int = 12,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    episodes = [json.loads(line) for line in episodes_path.read_text(encoding='utf-8').splitlines() if line.strip()]
    if not episodes:
        raise ValueError('no_episode_rows')
    chunk_rows = _read_parquet_rows(index_dir / 'chunks')
    mention_rows = _read_parquet_rows(_mention_dir(index_dir))
    if not chunk_rows:
        raise ValueError(f'empty_chunk_index:{index_dir}')
    if not mention_rows:
        raise ValueError(f'empty_mention_index:{index_dir}')
    chunk_by_id = {str(row.get('chunk_id') or ''): row for row in chunk_rows}
    chunk_doc_groups = _doc_groups(chunk_by_id)
    inverted_mentions: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in mention_rows:
        term = str(row.get('term') or '').strip().lower()
        chunk_id = str(row.get('chunk_id') or '')
        if not term or not chunk_id or chunk_id not in chunk_by_id:
            continue
        inverted_mentions[term].append(row)

    augmented_rows: list[dict[str, Any]] = []
    uplift_tokens: list[int] = []
    role_counts: Counter[str] = Counter()
    source_type_counts: Counter[str] = Counter()

    for row in episodes:
        execution_route = str((row.get('source_metadata') or {}).get('route') or '')
        if execution_route not in STRONG_VERIFIED_ROUTES:
            raise ValueError(f"weak_execution_route:{row.get('episode_id')}:{execution_route}")
        if not list(row.get('selected_tests') or []):
            raise ValueError(f"missing_selected_tests:{row.get('episode_id')}")
        query_terms = _episode_query_terms(row, max_terms=max_query_terms)
        augmented_context = _select_augmented_chunks(
            row=row,
            query_terms=query_terms,
            inverted_mentions=inverted_mentions,
            chunk_by_id=chunk_by_id,
            chunk_doc_groups=chunk_doc_groups,
            max_term_docfreq=max_term_docfreq,
            external_token_budget=external_token_budget,
            max_augmented_chunks=max_augmented_chunks,
            max_chunks_per_source_type=max_chunks_per_source_type,
            max_chunks_per_source_id=max_chunks_per_source_id,
            max_chunks_per_path=max_chunks_per_path,
            neighbor_window=neighbor_window,
            max_neighbor_chunks_per_anchor=max_neighbor_chunks_per_anchor,
            min_external_chunks=min_external_chunks,
        )
        merged_context = _dedupe_context_rows(list(row.get('context_rows') or []) + augmented_context)
        context_role_counts = dict(sorted(Counter(str(context_row.get('role') or '') for context_row in merged_context).items()))
        if context_role_counts.get('verification_constraint', 0) == 0:
            raise ValueError(f"missing_verification_context_after_merge:{row.get('episode_id')}")
        if context_role_counts.get('cross_repo_analogue', 0) == 0:
            raise ValueError(f"missing_cross_repo_grounding:{row.get('episode_id')}")
        augmented = dict(row)
        augmented['episode_id'] = stable_id(str(row.get('episode_id') or 'aug'), 'aug', str(external_token_budget))
        augmented['context_rows'] = merged_context
        augmented['context_token_count'] = sum(int(context_row.get('token_count') or 0) for context_row in merged_context)
        augmented['context_role_counts'] = context_role_counts
        augmented['augmentation_metadata'] = {
            'query_terms': query_terms,
            'external_token_budget': int(external_token_budget),
            'augmented_chunk_count': len(augmented_context),
            'augmented_token_count': sum(int(context_row.get('token_count') or 0) for context_row in augmented_context),
            'neighbor_window': int(neighbor_window),
            'max_neighbor_chunks_per_anchor': int(max_neighbor_chunks_per_anchor),
            'max_chunks_per_path': int(max_chunks_per_path),
        }
        uplift = int(augmented['context_token_count']) - int(row.get('context_token_count') or 0)
        if uplift <= 0:
            raise ValueError(f"non_positive_uplift:{row.get('episode_id')}:{uplift}")
        uplift_tokens.append(uplift)
        for context_row in augmented_context:
            role_counts[str(context_row.get('role') or '')] += 1
            source_type_counts[str(context_row.get('source_type') or '')] += 1
        augmented_rows.append(augmented)

    summary = {
        'episode_count': len(episodes),
        'augmented_episode_count': len(augmented_rows),
        'external_token_budget': int(external_token_budget),
        'neighbor_window': int(neighbor_window),
        'max_neighbor_chunks_per_anchor': int(max_neighbor_chunks_per_anchor),
        'max_chunks_per_path': int(max_chunks_per_path),
        'avg_uplift_tokens': (sum(uplift_tokens) / len(uplift_tokens)) if uplift_tokens else 0.0,
        'max_uplift_tokens': max(uplift_tokens) if uplift_tokens else 0,
        'min_uplift_tokens': min(uplift_tokens) if uplift_tokens else 0,
        'augmented_role_counts': dict(sorted(role_counts.items())),
        'augmented_source_type_counts': dict(sorted(source_type_counts.items())),
    }
    return augmented_rows, summary


def main() -> None:
    parser = argparse.ArgumentParser(description='Augment session-derived local-root episodes with external corpus evidence from the long-context index.')
    parser.add_argument('--episodes', type=Path, required=True)
    parser.add_argument('--index-dir', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--summary-output', type=Path)
    parser.add_argument('--external-token-budget', type=int, default=250000)
    parser.add_argument('--max-query-terms', type=int, default=24)
    parser.add_argument('--max-term-docfreq', type=int, default=600)
    parser.add_argument('--max-augmented-chunks', type=int, default=320)
    parser.add_argument('--max-chunks-per-source-type', type=int, default=128)
    parser.add_argument('--max-chunks-per-source-id', type=int, default=16)
    parser.add_argument('--max-chunks-per-path', type=int, default=4)
    parser.add_argument('--neighbor-window', type=int, default=2)
    parser.add_argument('--max-neighbor-chunks-per-anchor', type=int, default=4)
    parser.add_argument('--min-external-chunks', type=int, default=12)
    args = parser.parse_args()
    rows, summary = augment_session_episode_context(
        episodes_path=args.episodes,
        index_dir=args.index_dir,
        external_token_budget=args.external_token_budget,
        max_query_terms=args.max_query_terms,
        max_term_docfreq=args.max_term_docfreq,
        max_augmented_chunks=args.max_augmented_chunks,
        max_chunks_per_source_type=args.max_chunks_per_source_type,
        max_chunks_per_source_id=args.max_chunks_per_source_id,
        max_chunks_per_path=args.max_chunks_per_path,
        neighbor_window=args.neighbor_window,
        max_neighbor_chunks_per_anchor=args.max_neighbor_chunks_per_anchor,
        min_external_chunks=args.min_external_chunks,
    )
    write_jsonl(args.output, rows)
    write_json(args.summary_output or args.output.with_name('augmented_session_episode_context_summary.json'), summary)


if __name__ == '__main__':
    main()
