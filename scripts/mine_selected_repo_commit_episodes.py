from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from coverage_test_selection import select_tests
from long_context_common import extract_terms, lexical_overlap_score, read_jsonl, stable_id, write_json, write_jsonl
from mine_local_root_session_episodes import _collect_candidate_paths, _repo_index_from_paths
from program_state_call_graph_extractor import extract_python_call_graph
from program_state_symbol_table_extractor import extract_python_symbols

COMMIT_VERIFIED_ROUTE = 'COMMIT_PLUS_VERIFY'



GENERIC_QUERY_TERMS = {"modify", "repository", "files", "preserve", "behavior", "under", "execution", "backed", "maintenance", "changed", "verification", "targets", "key", "symbols", "route", "patch", "plus", "exec", "verify", "repair", "edit", "tool", "used", "goal", "task", "expected", "outcome", "any", "all", "get", "set", "str", "int", "float", "bool", "list", "dict", "train", "training", "loss", "loop", "state", "runtime", "config"}


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


def _is_useful_query_term(value: str) -> bool:
    term = str(value or '').strip().lower()
    if len(term) < 3 or term in GENERIC_QUERY_TERMS:
        return False
    if term.startswith('__') or term.endswith('__'):
        return False
    if not any(char.isalpha() for char in term):
        return False
    compact = term.replace('_', '')
    if not compact.isalnum() or term[0].isdigit():
        return False
    return True


def _path_suffix_terms(paths: list[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
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
        for candidate in candidates:
            value = candidate.strip().lower()
            if value and value not in seen and _is_useful_query_term(value):
                seen.add(value)
                out.append(value)
    return out


def _compact_seed_symbols(seed_symbols: set[str], *, max_symbols: int = 12) -> list[str]:
    ranked: list[tuple[tuple[int, int, str], str]] = []
    seen: set[str] = set()
    for raw_symbol in seed_symbols:
        symbol = str(raw_symbol or '').strip()
        if not symbol:
            continue
        root = symbol.split('.', 1)[0].strip()
        lower_root = root.lower()
        if lower_root in seen or not _is_useful_query_term(lower_root):
            continue
        variants = [lower_root, *_split_term_variants(root)]
        useful = [term for term in variants if _is_useful_query_term(term)]
        if not useful:
            continue
        priority = 0
        if '.' in symbol:
            priority += 3
        if '_' in root:
            priority += 2
        if any(ch.isupper() for ch in root[1:]):
            priority += 2
        if len(root) >= 8:
            priority += 1
        seen.add(lower_root)
        ranked.append(((-priority, len(root), lower_root), lower_root))
        for term in useful:
            if term in seen:
                continue
            seen.add(term)
            ranked.append(((-max(priority - 1, 0), len(term), term), term))
    ranked.sort(key=lambda item: item[0])
    return [symbol for _, symbol in ranked[:max_symbols]]


def _commit_query_text(*, goal: str, changed_paths: list[str], seed_symbols: set[str], changed_infos: list[dict[str, Any]]) -> str:
    compact_symbols = _compact_seed_symbols(seed_symbols, max_symbols=12)
    path_terms = _path_suffix_terms(changed_paths)
    local_terms: list[str] = []
    for info in changed_infos:
        for term in _split_term_variants(str(info.get('path') or '')):
            if _is_useful_query_term(term):
                local_terms.append(term)
        for symbol in list(info.get('defined_symbols') or [])[:16]:
            for term in _split_term_variants(str(symbol)):
                if _is_useful_query_term(term):
                    local_terms.append(term)
    deduped: list[str] = []
    seen: set[str] = set()
    for term in compact_symbols + path_terms + local_terms:
        value = str(term or '').strip().lower()
        if value in seen or not _is_useful_query_term(value):
            continue
        seen.add(value)
        deduped.append(value)
        if len(deduped) >= 24:
            break
    return '\n'.join(part for part in [str(goal or ''), ' '.join(deduped)] if part.strip())


def _read_filtered_chunk_rows(index_dir: Path, selected_repo_ids: set[str], *, include_papers: bool) -> list[dict[str, Any]]:
    import pyarrow.parquet as pq

    rows: list[dict[str, Any]] = []
    for shard in sorted((index_dir / 'chunks').glob('*.parquet')):
        for row in pq.read_table(shard).to_pylist():
            source_type = str(row.get('source_type') or '')
            source_id = str(row.get('source_id') or '')
            if include_papers and source_type == 'paper':
                rows.append(row)
            elif source_type == 'repo' and source_id in selected_repo_ids:
                rows.append(row)
    return rows


def _metadata(row: dict[str, Any]) -> dict[str, Any]:
    value = row.get('metadata_json') or '{}'
    if isinstance(value, dict):
        return value
    return json.loads(str(value))


def _norm_path(path: str) -> str:
    return str(path or '').replace('\\', '/').lstrip('./')


def _is_python_path(path: str) -> bool:
    return _norm_path(path).endswith('.py')


def _is_test_path(path: str) -> bool:
    normalized = _norm_path(path)
    name = normalized.rsplit('/', 1)[-1]
    return normalized.startswith('tests/') or normalized.startswith('test/') or '/tests/' in normalized or '/test/' in normalized or name.startswith('test_') or name.endswith('_test.py')


VERIFICATION_PATH_MARKERS = ('eval', 'evaluate', 'benchmark', 'bench', 'check', 'verify', 'smoke', 'integration', 'example')


def _is_verification_artifact_path(path: str) -> bool:
    normalized = _norm_path(path)
    name = normalized.rsplit('/', 1)[-1].lower()
    if _is_test_path(normalized):
        return False
    if not normalized.endswith('.py'):
        return False
    return any(marker in normalized.lower() or marker in name for marker in VERIFICATION_PATH_MARKERS)


def _repo_file_text(chunk_rows: list[dict[str, Any]]) -> str:
    ordered = sorted(chunk_rows, key=lambda row: (int(row.get('chunk_index') or 0), str(row.get('chunk_id') or '')))
    return '\n'.join(str(row.get('text') or '') for row in ordered if str(row.get('text') or '').strip())


def _build_repo_file_index(chunks: list[dict[str, Any]]) -> dict[str, dict[str, list[dict[str, Any]]]]:
    repo_files: dict[str, dict[str, list[dict[str, Any]]]] = defaultdict(lambda: defaultdict(list))
    for row in chunks:
        if str(row.get('source_type') or '') != 'repo':
            continue
        metadata = _metadata(row)
        path = _norm_path(str(metadata.get('path') or ''))
        if not path:
            continue
        repo_id = str(row.get('source_id') or '')
        repo_files[repo_id][path].append(row)
    return {repo_id: dict(path_map) for repo_id, path_map in repo_files.items()}


def _build_paper_chunk_rows(chunks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [row for row in chunks if str(row.get('source_type') or '') == 'paper']


def _repo_analysis_from_local_root(
    *,
    repo_root: Path,
    repo_id: str,
    changes: list[dict[str, Any]],
    root_file_limit: int,
    neighbor_dir_file_limit: int,
    max_total_candidates: int,
    walk_cache: dict[str, list[Path]],
    file_info_cache: dict[str, dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    changed_rel_paths = [_strip_repo_prefix(repo_id, path) for path in _changed_paths(changes)]
    candidate_paths = _collect_candidate_paths(
        repo_root,
        changed_rel_paths,
        root_file_limit=root_file_limit,
        neighbor_dir_file_limit=neighbor_dir_file_limit,
        max_total_candidates=max_total_candidates,
        walk_cache=walk_cache,
    )
    repo_files = _repo_index_from_paths(repo_root, candidate_paths, file_info_cache=file_info_cache)
    repo_analysis: dict[str, dict[str, Any]] = {}
    for rel_path, info in repo_files.items():
        synthetic_chunk = {
            'chunk_id': stable_id('localrepochunk', repo_id, rel_path),
            'source_type': 'repo',
            'source_id': repo_id,
            'doc_id': f'{repo_id}/{rel_path}',
            'chunk_index': 0,
            'token_count': int(info.get('token_count') or 0),
            'text': str(info.get('text') or ''),
            'metadata_json': {'path': rel_path},
        }
        repo_analysis[rel_path] = {
            'path': rel_path,
            'repo_id': repo_id,
            'chunk_rows': [synthetic_chunk],
            'text': str(info.get('text') or ''),
            'defined_symbols': list(info.get('defined_symbols') or []),
            'imported_symbols': list(info.get('imported_symbols') or []),
            'called_symbols': list(info.get('called_symbols') or []),
            'analysis_status': str(info.get('analysis_status') or ''),
            'analysis_error_type': str(info.get('analysis_error_type') or ''),
        }
    return repo_analysis


def _python_file_analysis(repo_id: str, path: str, chunk_rows: list[dict[str, Any]]) -> dict[str, Any]:
    text = _repo_file_text(chunk_rows)
    symbol_packet = extract_python_symbols(text, row_id=f'{repo_id}:{path}', path=path).to_dict()
    call_packet = extract_python_call_graph(text, row_id=f'{repo_id}:{path}', path=path).to_dict()
    defined_symbols = {
        str(symbol.get('name') or '')
        for symbol in symbol_packet.get('symbols', [])
        if str(symbol.get('symbol_kind') or '') in {'function', 'async_function', 'method', 'class'}
    }
    imported_symbols = {
        str(symbol.get('name') or '')
        for symbol in symbol_packet.get('symbols', [])
        if str(symbol.get('symbol_kind') or '') == 'import'
    }
    called_symbols = {
        str(node.get('name') or '')
        for node in call_packet.get('call_nodes', [])
        if str(node.get('node_kind') or '') in {'callee_reference', 'callsite'}
    }
    return {
        'path': path,
        'repo_id': repo_id,
        'chunk_rows': sorted(chunk_rows, key=lambda row: (int(row.get('chunk_index') or 0), str(row.get('chunk_id') or ''))),
        'text': text,
        'defined_symbols': sorted(symbol for symbol in defined_symbols if symbol),
        'imported_symbols': sorted(symbol for symbol in imported_symbols if symbol),
        'called_symbols': sorted(symbol for symbol in called_symbols if symbol and symbol != '<unknown>'),
    }


def _build_repo_analysis(repo_files: dict[str, dict[str, list[dict[str, Any]]]]) -> dict[str, dict[str, dict[str, Any]]]:
    analysis: dict[str, dict[str, dict[str, Any]]] = {}
    for repo_id, path_map in repo_files.items():
        repo_analysis: dict[str, dict[str, Any]] = {}
        for path, chunk_rows in path_map.items():
            if _is_python_path(path):
                repo_analysis[path] = _python_file_analysis(repo_id, path, chunk_rows)
            else:
                repo_analysis[path] = {
                    'path': path,
                    'repo_id': repo_id,
                    'chunk_rows': sorted(chunk_rows, key=lambda row: (int(row.get('chunk_index') or 0), str(row.get('chunk_id') or ''))),
                    'text': _repo_file_text(chunk_rows),
                    'defined_symbols': [],
                    'imported_symbols': [],
                    'called_symbols': [],
                }
        analysis[repo_id] = repo_analysis
    return analysis


def _build_test_to_symbols(repo_analysis: dict[str, dict[str, Any]]) -> dict[str, list[str]]:
    return {
        path: sorted(set(info.get('defined_symbols', [])) | set(info.get('called_symbols', [])))
        for path, info in repo_analysis.items()
        if _is_test_path(path)
    }


def _changed_paths(changes: list[dict[str, Any]]) -> list[str]:
    out = []
    for change in changes:
        if not isinstance(change, dict):
            continue
        path = _norm_path(str(change.get('path') or change.get('file') or ''))
        if path:
            out.append(path)
    return out


def _strip_repo_prefix(repo_id: str, path: str) -> str:
    normalized = _norm_path(path)
    prefix = f'{repo_id}/'
    if normalized.startswith(prefix):
        return normalized[len(prefix):]
    return normalized


def _suffix_path_matches(path: str, repo_paths: set[str]) -> list[str]:
    normalized = _norm_path(path)
    if not normalized:
        return []
    suffixes = {normalized}
    parts = normalized.split('/')
    for index in range(1, len(parts) - 1):
        suffixes.add('/'.join(parts[index:]))
    matches = {
        candidate
        for candidate in repo_paths
        for suffix in suffixes
        if candidate == suffix or candidate.endswith('/' + suffix)
    }
    return sorted(matches)




def _resolve_selected_test_paths(repo_id: str, selected_tests: list[str], repo_analysis: dict[str, dict[str, Any]]) -> tuple[list[str], list[str]]:
    repo_paths = set(repo_analysis)
    lookup_paths: list[str] = []
    display_paths: list[str] = []
    seen_lookup: set[str] = set()
    for path in selected_tests:
        raw = _norm_path(path)
        stripped = _strip_repo_prefix(repo_id, path)
        candidates: list[str] = []
        if raw in repo_paths:
            candidates.append(raw)
        if stripped in repo_paths and stripped not in candidates:
            candidates.append(stripped)
        if not candidates:
            suffix_matches = _suffix_path_matches(stripped, repo_paths)
            if len(suffix_matches) == 1:
                candidates.append(suffix_matches[0])
        if not candidates:
            continue
        lookup = candidates[0]
        if lookup in seen_lookup:
            continue
        seen_lookup.add(lookup)
        lookup_paths.append(lookup)
        display_paths.append(stripped)
    return lookup_paths, display_paths


def _resolve_changed_paths(repo_id: str, changes: list[dict[str, Any]], repo_analysis: dict[str, dict[str, Any]]) -> tuple[list[str], list[str]]:
    repo_paths = set(repo_analysis)
    changed_lookup_paths: list[str] = []
    changed_display_paths: list[str] = []
    seen_lookup: set[str] = set()
    for path in _changed_paths(changes):
        raw = _norm_path(path)
        stripped = _strip_repo_prefix(repo_id, path)
        candidates: list[str] = []
        if raw in repo_paths:
            candidates.append(raw)
        if stripped in repo_paths and stripped not in candidates:
            candidates.append(stripped)
        if not candidates:
            suffix_matches = _suffix_path_matches(stripped, repo_paths)
            if len(suffix_matches) == 1:
                candidates.append(suffix_matches[0])
        if not candidates:
            continue
        lookup = candidates[0]
        if lookup in seen_lookup:
            continue
        seen_lookup.add(lookup)
        changed_lookup_paths.append(lookup)
        changed_display_paths.append(stripped)
    return changed_lookup_paths, changed_display_paths


def _seed_symbol_names(changes: list[dict[str, Any]], changed_infos: list[dict[str, Any]]) -> set[str]:
    names = {str(change.get('symbol') or change.get('function') or change.get('class') or '') for change in changes if isinstance(change, dict)}
    for info in changed_infos:
        names.update(info.get('defined_symbols', []))
        names.update(info.get('called_symbols', []))
        names.update(info.get('imported_symbols', []))
    return {name for name in names if name}


def _candidate_neighbor_paths(*, repo_analysis: dict[str, dict[str, Any]], changed_paths: list[str], seed_symbols: set[str]) -> list[dict[str, Any]]:
    changed_set = set(changed_paths)
    neighbors: list[dict[str, Any]] = []
    for path, info in repo_analysis.items():
        if path in changed_set:
            continue
        reasons: list[str] = []
        score = 0.0
        defined = set(info.get('defined_symbols', []))
        imported = set(info.get('imported_symbols', []))
        called = set(info.get('called_symbols', []))
        if defined & seed_symbols:
            reasons.append('defines_seed_symbol')
            score += 3.0
        if imported & seed_symbols:
            reasons.append('imports_seed_symbol')
            score += 2.0
        if called & seed_symbols:
            reasons.append('calls_seed_symbol')
            score += 2.0
        if not reasons:
            continue
        if _is_test_path(path):
            score -= 0.5
        neighbors.append({'path': path, 'reasons': sorted(set(reasons)), 'score': score})
    return sorted(neighbors, key=lambda row: (-float(row['score']), row['path']))




def _basename_stem(path: str) -> str:
    normalized = _norm_path(path)
    name = normalized.rsplit('/', 1)[-1]
    if name.endswith('.py'):
        name = name[:-3]
    if name.startswith('test_'):
        name = name[5:]
    if name.endswith('_test'):
        name = name[:-5]
    return name


def _broad_discovery_test_candidates(
    *,
    repo_analysis: dict[str, dict[str, Any]],
    changed_paths: list[str],
    changed_infos: list[dict[str, Any]],
    seed_symbols: set[str],
    goal: str,
    max_results: int,
) -> list[dict[str, Any]]:
    query_text = _commit_query_text(goal=str(goal or ''), changed_paths=changed_paths, seed_symbols=seed_symbols, changed_infos=changed_infos)
    changed_stems = {_basename_stem(path) for path in changed_paths if _basename_stem(path)}
    changed_topdirs = {parts[0] for parts in (_norm_path(path).split('/') for path in changed_paths) if parts and parts[0]}
    candidates: list[dict[str, Any]] = []
    for path, info in repo_analysis.items():
        if not _is_test_path(path):
            continue
        score = 0.0
        reasons: list[str] = []
        test_text = str(info.get('text') or '')
        lexical = lexical_overlap_score(query_text, test_text)
        if lexical > 0.0:
            score += lexical * 8.0
            reasons.append('lexical_overlap')
        test_symbols = set(info.get('defined_symbols', [])) | set(info.get('called_symbols', [])) | set(info.get('imported_symbols', []))
        shared_symbols = sorted(test_symbols & seed_symbols)
        if shared_symbols:
            score += min(len(shared_symbols), 8) * 2.0
            reasons.append('shared_seed_symbol')
        test_stem = _basename_stem(path)
        if any(stem and (stem == test_stem or stem in test_stem or test_stem in stem) for stem in changed_stems):
            score += 3.0
            reasons.append('path_stem_overlap')
        path_parts = [part for part in _norm_path(path).split('/') if part]
        if changed_topdirs & set(path_parts):
            score += 1.0
            reasons.append('directory_overlap')
        if score <= 0.0:
            continue
        candidates.append(
            {
                'test_path': path,
                'score': score,
                'reasons': sorted(set(reasons)),
                'shared_symbols': shared_symbols[:12],
                'lexical_overlap': lexical,
            }
        )
    candidates.sort(key=lambda row: (-float(row['score']), row['test_path']))
    return candidates[:max_results]


def _broad_discovery_verification_candidates(
    *,
    repo_analysis: dict[str, dict[str, Any]],
    changed_paths: list[str],
    changed_infos: list[dict[str, Any]],
    seed_symbols: set[str],
    goal: str,
    max_results: int,
) -> list[dict[str, Any]]:
    query_text = _commit_query_text(goal=str(goal or ''), changed_paths=changed_paths, seed_symbols=seed_symbols, changed_infos=changed_infos)
    changed_set = set(changed_paths)
    changed_stems = {_basename_stem(path) for path in changed_paths if _basename_stem(path)}
    candidates: list[dict[str, Any]] = []
    for path, info in repo_analysis.items():
        if path in changed_set or not _is_verification_artifact_path(path):
            continue
        score = 0.0
        reasons: list[str] = []
        artifact_text = str(info.get('text') or '')
        lexical = lexical_overlap_score(query_text, artifact_text)
        if lexical > 0.0:
            score += lexical * 8.0
            reasons.append('lexical_overlap')
        symbols = set(info.get('defined_symbols', [])) | set(info.get('called_symbols', [])) | set(info.get('imported_symbols', []))
        shared_symbols = sorted(symbols & seed_symbols)
        if shared_symbols:
            score += min(len(shared_symbols), 8) * 2.0
            reasons.append('shared_seed_symbol')
        stem = _basename_stem(path)
        if any(changed and (changed == stem or changed in stem or stem in changed) for changed in changed_stems):
            score += 2.0
            reasons.append('path_stem_overlap')
        lower_path = path.lower()
        marker_hits = [marker for marker in VERIFICATION_PATH_MARKERS if marker in lower_path]
        if marker_hits:
            score += min(len(marker_hits), 3) * 0.75
            reasons.append('verification_marker')
        if score <= 0.0:
            continue
        candidates.append(
            {
                'test_path': path,
                'score': score,
                'reasons': sorted(set(reasons)),
                'shared_symbols': shared_symbols[:12],
                'lexical_overlap': lexical,
            }
        )
    candidates.sort(key=lambda row: (-float(row['score']), row['test_path']))
    return candidates[:max_results]


def _paper_grounding_candidates(*, paper_rows: list[dict[str, Any]], seed_symbols: set[str], goal: str, max_results: int) -> list[dict[str, Any]]:
    query_text = _commit_query_text(goal=str(goal or ''), changed_paths=[], seed_symbols=seed_symbols, changed_infos=[])
    if not query_text.strip():
        return []
    seed_terms = set(extract_terms(query_text, max_terms=48))
    candidates: list[dict[str, Any]] = []
    for row in paper_rows:
        text = str(row.get('text') or '')
        if not text.strip():
            continue
        overlap = lexical_overlap_score(query_text, text)
        if overlap <= 0.0:
            continue
        chunk_terms = set(extract_terms(text, max_terms=48))
        shared_terms = sorted(seed_terms & chunk_terms)[:12]
        score = overlap + 0.05 * len(shared_terms)
        candidates.append({'row': row, 'score': score, 'shared_terms': shared_terms})
    return sorted(candidates, key=lambda item: (-float(item['score']), str(item['row'].get('source_id') or ''), str(item['row'].get('chunk_id') or '')))[:max_results]


def _chunk_context_rows(chunk_rows: list[dict[str, Any]], *, role: str, retrieval_reason: str, distance_from_seed: int, retrieval_score: float) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for chunk in sorted(chunk_rows, key=lambda row: (int(row.get('chunk_index') or 0), str(row.get('chunk_id') or ''))):
        metadata = _metadata(chunk)
        out.append(
            {
                'chunk_id': str(chunk.get('chunk_id') or ''),
                'source_type': str(chunk.get('source_type') or ''),
                'source_id': str(chunk.get('source_id') or ''),
                'doc_id': str(chunk.get('doc_id') or ''),
                'path': _norm_path(str(metadata.get('path') or '')),
                'chunk_index': int(chunk.get('chunk_index') or 0),
                'token_count': int(chunk.get('token_count') or 0),
                'text': str(chunk.get('text') or ''),
                'role': role,
                'retrieval_reason': retrieval_reason,
                'distance_from_seed': int(distance_from_seed),
                'retrieval_score': float(retrieval_score),
            }
        )
    return out


def _role_priority(role: str) -> int:
    priorities = {
        'verification_constraint': 0,
        'seed_change': 1,
        'test_neighbor': 2,
        'repo_graph_neighbor': 3,
        'algorithm_grounding': 4,
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
    return sorted(by_chunk_id.values(), key=lambda row: (_role_priority(str(row.get('role') or '')), int(row.get('distance_from_seed') or 0), str(row.get('path') or ''), int(row.get('chunk_index') or 0), str(row.get('chunk_id') or '')))


def _task_summary(*, repo_id: str, changed_paths: list[str], selected_tests: list[str], seed_symbols: set[str], commit_subject: str, commit_sha: str) -> str:
    return '\n'.join(
        [
            f'Recreate verified repository transition from historical commit evidence.',
            f'Repository: {repo_id}',
            f'Commit subject: {commit_subject}',
            f'Commit sha: {commit_sha}',
            f'Changed files: {", ".join(changed_paths)}',
            f'Verification targets: {", ".join(selected_tests)}',
            f'Key symbols: {", ".join(sorted(seed_symbols)[:24]) if seed_symbols else "<none>"}',
            f'Execution route: {COMMIT_VERIFIED_ROUTE}',
        ]
    )


def _target_payload(*, changed_paths: list[str], selected_tests: list[str], seed_symbols: set[str], commit_subject: str, commit_sha: str, test_selection_route: str) -> dict[str, Any]:
    if not changed_paths:
        raise ValueError('missing_changed_paths')
    if not selected_tests:
        raise ValueError('missing_selected_tests')
    patch_summary = (
        f"Recreate the commit-level change '{commit_subject}' by updating {', '.join(changed_paths)} so that "
        f"{', '.join(selected_tests)} remain satisfied under {COMMIT_VERIFIED_ROUTE.lower()}."
    )
    return {
        'expected_patch_summary': patch_summary,
        'expected_outcome': 'verification_targets_hold_under_commit_plus_verify',
        'state_after': {
            'expected_changed_files': list(changed_paths),
            'verification_targets': list(selected_tests),
            'execution_route': COMMIT_VERIFIED_ROUTE,
            'test_selection_route': test_selection_route,
            'key_symbols': sorted(seed_symbols)[:32],
            'commit_subject': commit_subject,
            'commit_sha': commit_sha,
        },
    }


def build_selected_repo_commit_episodes(
    *,
    seeds_path: Path,
    index_dir: Path | None = None,
    repositories_root: Path | None = None,
    max_neighbor_files: int = 12,
    max_selected_tests: int = 8,
    max_paper_chunks: int = 12,
    include_papers: bool = True,
    allow_broad_discovery: bool = False,
    root_file_limit: int = 400,
    neighbor_dir_file_limit: int = 250,
    max_total_candidates: int = 1600,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    if (index_dir is None) == (repositories_root is None):
        raise ValueError('exactly_one_source_mode_required')
    if repositories_root is not None and include_papers:
        raise ValueError('papers_require_index_dir')

    seeds = read_jsonl(seeds_path)
    selected_repo_ids = {str(row.get('repo_id') or '') for row in seeds if str(row.get('repo_id') or '')}
    repo_analysis_by_id: dict[str, dict[str, dict[str, Any]]] = {}
    paper_rows: list[dict[str, Any]] = []
    source_mode = 'repositories_root' if repositories_root is not None else 'index_dir'
    if index_dir is not None:
        chunks = _read_filtered_chunk_rows(index_dir, selected_repo_ids, include_papers=include_papers)
        repo_files = _build_repo_file_index(chunks)
        repo_analysis_by_id = _build_repo_analysis(repo_files)
        paper_rows = _build_paper_chunk_rows(chunks)
    walk_cache_by_repo: dict[str, dict[str, list[Path]]] = {}
    file_info_cache_by_repo: dict[str, dict[str, dict[str, Any]]] = {}

    episodes: list[dict[str, Any]] = []
    route_counts: Counter[str] = Counter()
    role_counts: Counter[str] = Counter()

    for seed in seeds:
        repo_id = str(seed.get('repo_id') or '')
        changes = list(seed.get('changes') or [])
        if repositories_root is not None:
            metadata = dict(seed.get('metadata') or {})
            explicit_root = str(metadata.get('repo_root') or '').strip()
            repo_root = Path(explicit_root) if explicit_root else repositories_root / repo_id
            if not repo_root.exists() or not repo_root.is_dir():
                route_counts['SKIP_NO_LOCAL_REPO_ROOT'] += 1
                continue
            repo_analysis = _repo_analysis_from_local_root(
                repo_root=repo_root,
                repo_id=repo_id,
                changes=changes,
                root_file_limit=root_file_limit,
                neighbor_dir_file_limit=neighbor_dir_file_limit,
                max_total_candidates=max_total_candidates,
                walk_cache=walk_cache_by_repo.setdefault(repo_id, {}),
                file_info_cache=file_info_cache_by_repo.setdefault(repo_id, {}),
            )
        else:
            repo_analysis = repo_analysis_by_id.get(repo_id)
        if not repo_analysis:
            route_counts['SKIP_NO_REPO_ANALYSIS'] += 1
            continue
        changed_lookup_paths, changed_display_paths = _resolve_changed_paths(repo_id, changes, repo_analysis)
        if not changed_lookup_paths:
            route_counts['SKIP_NO_MATCHED_PATHS'] += 1
            continue
        changed_infos = [repo_analysis[path] for path in changed_lookup_paths]
        seed_symbols = _seed_symbol_names(changes, changed_infos)
        repo_index = {'files': sorted(repo_analysis), 'coverage_map': {}, 'test_to_symbols': _build_test_to_symbols(repo_analysis)}
        test_selection = select_tests({'row_id': str(seed.get('seed_id') or ''), 'repo_index': repo_index, 'changes': [{'path': path} for path in changed_display_paths]}, max_tests=max_selected_tests)
        raw_route = str(test_selection.get('test_selection_route') or '')
        route_counts[raw_route] += 1
        selected_tests = [str(item) for item in list(test_selection.get('selected_tests') or []) if str(item)]
        broad_candidates: list[dict[str, Any]] = []
        effective_test_selection_route = raw_route
        if not selected_tests and allow_broad_discovery and raw_route == 'NEEDS_BROAD_TEST_DISCOVERY':
            broad_candidates = _broad_discovery_test_candidates(
                repo_analysis=repo_analysis,
                changed_paths=changed_display_paths,
                changed_infos=changed_infos,
                seed_symbols=seed_symbols,
                goal=str(seed.get('goal') or ''),
                max_results=max_selected_tests,
            )
            selected_tests = [str(item.get('test_path') or '') for item in broad_candidates if str(item.get('test_path') or '')]
            if selected_tests:
                effective_test_selection_route = 'PASS_BROAD_TEST_DISCOVERY'
                route_counts[effective_test_selection_route] += 1
            else:
                broad_candidates = _broad_discovery_verification_candidates(
                    repo_analysis=repo_analysis,
                    changed_paths=changed_display_paths,
                    changed_infos=changed_infos,
                    seed_symbols=seed_symbols,
                    goal=str(seed.get('goal') or ''),
                    max_results=max_selected_tests,
                )
                selected_tests = [str(item.get('test_path') or '') for item in broad_candidates if str(item.get('test_path') or '')]
                if selected_tests:
                    effective_test_selection_route = 'PASS_BROAD_VERIFICATION_DISCOVERY'
                    route_counts[effective_test_selection_route] += 1
        selected_test_lookup_paths, selected_tests = _resolve_selected_test_paths(repo_id, selected_tests, repo_analysis)
        if not selected_tests:
            route_counts['SKIP_NO_SELECTED_TESTS'] += 1
            continue

        context_rows: list[dict[str, Any]] = []
        for path in changed_lookup_paths:
            context_rows.extend(_chunk_context_rows(repo_analysis[path]['chunk_rows'], role='seed_change', retrieval_reason='changed_path', distance_from_seed=0, retrieval_score=1.0))
        for neighbor in _candidate_neighbor_paths(repo_analysis=repo_analysis, changed_paths=changed_lookup_paths, seed_symbols=seed_symbols)[:max_neighbor_files]:
            path = str(neighbor['path'])
            context_rows.extend(_chunk_context_rows(repo_analysis[path]['chunk_rows'], role='repo_graph_neighbor' if not _is_test_path(path) else 'test_neighbor', retrieval_reason='|'.join(neighbor['reasons']), distance_from_seed=1, retrieval_score=float(neighbor['score'])))
        broad_candidate_by_path = {_strip_repo_prefix(repo_id, str(item.get('test_path') or '')): item for item in broad_candidates}
        for rank, (test_lookup_path, test_path) in enumerate(zip(selected_test_lookup_paths, selected_tests), start=1):
            if test_lookup_path not in repo_analysis:
                continue
            broad_hit = broad_candidate_by_path.get(test_path)
            retrieval_reason = 'targeted_test_selection'
            retrieval_score = max(0.0, 2.0 - rank * 0.1)
            if broad_hit is not None:
                retrieval_reason = '|'.join(list(broad_hit.get('reasons') or [])[:6]) or 'broad_test_discovery'
                retrieval_score = float(broad_hit.get('score') or 0.0)
            context_rows.extend(_chunk_context_rows(repo_analysis[test_lookup_path]['chunk_rows'], role='verification_constraint', retrieval_reason=retrieval_reason, distance_from_seed=1, retrieval_score=retrieval_score))
        if include_papers:
            for paper_hit in _paper_grounding_candidates(paper_rows=paper_rows, seed_symbols=seed_symbols, goal=str(seed.get('goal') or ''), max_results=max_paper_chunks):
                paper_row = paper_hit['row']
                metadata = _metadata(paper_row)
                context_rows.append({'chunk_id': str(paper_row.get('chunk_id') or ''), 'source_type': str(paper_row.get('source_type') or ''), 'source_id': str(paper_row.get('source_id') or ''), 'doc_id': str(paper_row.get('doc_id') or ''), 'path': _norm_path(str(metadata.get('path') or '')), 'chunk_index': int(paper_row.get('chunk_index') or 0), 'token_count': int(paper_row.get('token_count') or 0), 'text': str(paper_row.get('text') or ''), 'role': 'algorithm_grounding', 'retrieval_reason': '|'.join(list(paper_hit['shared_terms'])[:6]) or 'lexical_overlap', 'distance_from_seed': 3, 'retrieval_score': float(paper_hit['score'])})
        context_rows = _dedupe_context_rows(context_rows)
        role_counter = Counter(str(row.get('role') or '') for row in context_rows)
        if role_counter.get('verification_constraint', 0) == 0:
            route_counts['SKIP_MISSING_VERIFICATION_CONTEXT'] += 1
            continue
        commit_subject = str((seed.get('metadata') or {}).get('commit_subject') or seed.get('goal') or '')
        commit_sha = str((seed.get('metadata') or {}).get('commit_sha') or '')
        goal = _task_summary(repo_id=repo_id, changed_paths=changed_display_paths, selected_tests=selected_tests, seed_symbols=seed_symbols, commit_subject=commit_subject, commit_sha=commit_sha)
        target = _target_payload(changed_paths=changed_display_paths, selected_tests=selected_tests, seed_symbols=seed_symbols, commit_subject=commit_subject, commit_sha=commit_sha, test_selection_route=effective_test_selection_route)
        for row in context_rows:
            role_counts[str(row.get('role') or '')] += 1
        episode_id = stable_id('selrepoepisode', str(seed.get('seed_type') or 'commit'), repo_id, str(seed.get('seed_id') or ''), '|'.join(changed_display_paths))
        source_metadata = dict(seed.get('metadata') or {})
        source_metadata['route'] = COMMIT_VERIFIED_ROUTE
        episodes.append(
            {
                'episode_id': episode_id,
                'seed_id': str(seed.get('seed_id') or ''),
                'seed_type': str(seed.get('seed_type') or 'external_repo_commit'),
                'repo_id': repo_id,
                'goal': goal,
                'changes': [{'path': path} for path in changed_display_paths],
                'seed_paths': changed_display_paths,
                'seed_symbols': sorted(seed_symbols),
                'selected_tests': selected_tests,
                'test_selection_route': effective_test_selection_route,
                'context_rows': context_rows,
                'context_token_count': sum(int(row.get('token_count') or 0) for row in context_rows),
                'context_role_counts': dict(sorted(role_counter.items())),
                'target': target,
                'source_metadata': {**source_metadata, 'source_mode': source_mode},
            }
        )

    summary = {'seed_count': len(seeds), 'episode_count': len(episodes), 'route_counts': dict(sorted(route_counts.items())), 'context_role_counts': dict(sorted(role_counts.items())), 'source_mode': source_mode}
    return episodes, summary


def main() -> None:
    parser = argparse.ArgumentParser(description='Mine long-context episodes from selected external repo commit seeds using either an index-backed corpus or explicit local repositories.')
    source_group = parser.add_mutually_exclusive_group(required=True)
    source_group.add_argument('--index-dir', type=Path)
    source_group.add_argument('--repositories-root', type=Path)
    parser.add_argument('--seeds', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--summary-output', type=Path)
    parser.add_argument('--max-neighbor-files', type=int, default=12)
    parser.add_argument('--max-selected-tests', type=int, default=8)
    parser.add_argument('--max-paper-chunks', type=int, default=12)
    parser.add_argument('--no-papers', action='store_true')
    parser.add_argument('--allow-broad-discovery', action='store_true')
    parser.add_argument('--root-file-limit', type=int, default=400)
    parser.add_argument('--neighbor-dir-file-limit', type=int, default=250)
    parser.add_argument('--max-total-candidates', type=int, default=1600)
    args = parser.parse_args()
    rows, summary = build_selected_repo_commit_episodes(
        index_dir=args.index_dir,
        repositories_root=args.repositories_root,
        seeds_path=args.seeds,
        max_neighbor_files=args.max_neighbor_files,
        max_selected_tests=args.max_selected_tests,
        max_paper_chunks=args.max_paper_chunks,
        include_papers=not args.no_papers,
        allow_broad_discovery=args.allow_broad_discovery,
        root_file_limit=args.root_file_limit,
        neighbor_dir_file_limit=args.neighbor_dir_file_limit,
        max_total_candidates=args.max_total_candidates,
    )
    write_jsonl(args.output, rows)
    write_json(args.summary_output or args.output.with_name('selected_repo_commit_episode_summary.json'), summary)


if __name__ == '__main__':
    main()
