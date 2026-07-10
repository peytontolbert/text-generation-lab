from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

from long_context_common import GENERIC_CORPUS_TERMS, STOPWORDS, STRUCTURED_NOISE_TERMS, mean, stable_id, write_json, write_jsonl


CODE_SIGNAL_RE = re.compile(
    r"\b(def|class|import|from|return|yield|async|await|function|const|let|var|export|public|private|protected|interface|struct|enum|impl|fn|package)\b|=>|::",
    re.IGNORECASE,
)


class CandidateMiningSafetyError(ValueError):
    """Raised when candidate mining is requested without an explicit gate."""


def _is_relative_to(child: Path, parent: Path) -> bool:
    try:
        child.relative_to(parent)
        return True
    except ValueError:
        return False


def validate_candidate_mining_request(
    *,
    index_dir: Path,
    output: Path,
    allow_candidate_mining: bool,
    allow_arxiv_output: bool,
) -> dict[str, Any]:
    resolved_index = index_dir.expanduser().resolve()
    resolved_output = output.expanduser()
    if resolved_output.exists():
        resolved_output = resolved_output.resolve()
    elif resolved_output.parent.exists():
        resolved_output = resolved_output.parent.resolve() / resolved_output.name
    arxiv_root = Path('/arxiv').resolve()
    index_under_arxiv = resolved_index == arxiv_root or _is_relative_to(resolved_index, arxiv_root)
    output_under_arxiv = resolved_output == arxiv_root or _is_relative_to(resolved_output, arxiv_root)
    checks = {
        'allow_candidate_mining_flag': allow_candidate_mining,
        'arxiv_output_requires_explicit_output_flag': allow_arxiv_output or not output_under_arxiv,
    }
    failures = [key for key, passed in checks.items() if passed is not True]
    if failures:
        raise CandidateMiningSafetyError(json.dumps({
            'failures': failures,
            'index_under_arxiv': index_under_arxiv,
            'output_under_arxiv': output_under_arxiv,
            'checks': checks,
        }, sort_keys=True))
    return {
        'resolved_index_dir': str(resolved_index),
        'resolved_output': str(resolved_output),
        'index_under_arxiv': index_under_arxiv,
        'output_under_arxiv': output_under_arxiv,
        'checks': checks,
    }


def _read_rows(directory: Path) -> list[dict[str, Any]]:
    import pyarrow.parquet as pq

    rows: list[dict[str, Any]] = []
    for path in sorted(directory.glob('*.parquet')):
        rows.extend(pq.read_table(path).to_pylist())
    return rows


def _canonical_name_ok(name: str) -> bool:
    lower = str(name or '').strip().lower()
    if len(lower) < 4:
        return False
    if lower in STOPWORDS or lower in GENERIC_CORPUS_TERMS or lower in STRUCTURED_NOISE_TERMS:
        return False
    banned = {
        'actions', 'action', 'base', 'behavior', 'both', 'given', 'next', 'task', 'days', 'plugin', 'resource', 'display',
        'return', 'state', 'updates', 'active', 'first', 'name', 'title', 'protocol', 'rewrite', 'any', 'files',
        'code', 'work', 'html', 'const', 'var', 'use', 'you', 'button', 'pdf', 'index', 'fig', 'com', 'https',
        'github', 'training', 'network', 'networks', 'maps', 'matrix', 'language', 'power', 'environment', 'module',
        'self', 'append', 'assert', 'label', 'dataset', 'blue', 'stars', 'args', 'style', 'torch', 'task', 'boolean',
        'case', 'class', 'context', 'configuration', 'length', 'number', 'generation', 'research', 'reward', 'social',
        'via', 'none', 'multi', 'buffer', 'auto', 'average', 'block', 'boundary', 'error', 'parameter', 'parameters',
    }
    return lower not in banned


def _repo_path_quality(path: str) -> int:
    lower = str(path or '').lower()
    score = 0
    if any(part in lower for part in ['/node_modules/', '/dist/', '/build/', '/binder/', '/coverage/', '/vendor/']):
        score -= 5
    if any(part in lower for part in ['/assets/', '/translations/', '/i18n/', '/locale/', '/locales/', '/fixtures/', '/examples/']):
        score -= 4
    if any(name in lower for name in ['package-lock.json', 'pnpm-lock.yaml', 'yarn.lock', 'poetry.lock', 'cargo.lock']):
        score -= 5
    if any(part in lower for part in ['/src/', '/lib/', '/app/', '/core/', '/cmd/', '/pkg/']):
        score += 5
    if lower.endswith(('.py', '.ts', '.tsx', '.js', '.jsx', '.java', '.go', '.rs', '.c', '.cc', '.cpp', '.h', '.hpp')):
        score += 3
    if any(part in lower for part in ['/test', '/tests', '/benchmark/']):
        score -= 2
    if 'readme' in lower or lower.endswith('.md'):
        score -= 2
    if lower.endswith(('.json', '.yaml', '.yml', '.toml', '.cfg', '.ini')):
        score -= 2
    return score


def _repo_row_usable(row: dict[str, Any], *, quality: int) -> bool:
    if quality <= 1:
        return False
    modality = str(row.get('modality') or '')
    if modality != 'code':
        return False
    text = str(row.get('text') or '')
    return bool(CODE_SIGNAL_RE.search(text))


def _repo_concept_row_usable(row: dict[str, Any], *, quality: int) -> bool:
    if quality <= 0:
        return False
    modality = str(row.get('modality') or '')
    if modality not in {'code', 'text'}:
        return False
    metadata = json.loads(str(row.get('metadata_json') or '{}'))
    path = str(metadata.get('path') or '')
    if _repo_path_is_test(path):
        return False
    if 'readme' in path.lower():
        return False
    return True


def _repo_path_is_implementation(path: str) -> bool:
    lower = str(path or '').lower()
    return any(part in lower for part in ['/src/', '/lib/', '/app/', '/core/', '/cmd/', '/pkg/']) and not any(
        part in lower for part in ['/test', '/tests', '/benchmark/']
    )


def _repo_path_is_test(path: str) -> bool:
    lower = str(path or '').lower()
    return any(part in lower for part in ['/test', '/tests', '/benchmark/'])


def _repo_row_sort_key(row: dict[str, Any], *, quality: int) -> tuple[int, int, int, str]:
    metadata = json.loads(str(row.get('metadata_json') or '{}'))
    path = str(metadata.get('path') or '').lower()
    implementation_bias = 1 if _repo_path_is_implementation(path) else 0
    test_penalty = 1 if _repo_path_is_test(path) else 0
    return (-implementation_bias, test_penalty, -quality, path)


def _entity_support_ok(mention_rows: list[dict[str, Any]], required_source_types: tuple[str, ...]) -> bool:
    by_type: dict[str, list[dict[str, Any]]] = {}
    for row in mention_rows:
        by_type.setdefault(str(row.get('source_type') or ''), []).append(row)
    for source_type in required_source_types:
        rows = by_type.get(source_type, [])
        distinct_docs = {str(row.get('doc_id') or '') for row in rows}
        if len(rows) < 2 and len(distinct_docs) < 2:
            return False
    return True


def _compound_entity_support_ok(mention_rows: list[dict[str, Any]], required_source_types: tuple[str, ...]) -> bool:
    if 'paper' not in required_source_types or 'repo' not in required_source_types:
        return _entity_support_ok(mention_rows, required_source_types)
    paper_rows = [row for row in mention_rows if str(row.get('source_type') or '') == 'paper']
    repo_rows = [row for row in mention_rows if str(row.get('source_type') or '') == 'repo']
    paper_docs = {str(row.get('doc_id') or '') for row in paper_rows}
    repo_docs = {str(row.get('doc_id') or '') for row in repo_rows}
    repo_sources = {str(row.get('source_id') or '') for row in repo_rows}
    if len(paper_docs) >= 1 and len(repo_docs) >= 2 and len(repo_sources) >= 2:
        return True
    return _entity_support_ok(mention_rows, required_source_types)


def _entity_specificity_score(canonical_name: str, mention_rows: list[dict[str, Any]]) -> int:
    lower = canonical_name.lower()
    score = 0
    if '-' in lower or '_' in lower:
        score += 2
    if len(lower) >= 8:
        score += 1
    source_ids = {str(row.get('source_id') or '') for row in mention_rows}
    if len(source_ids) >= 3:
        score += 1
    repo_rows = [row for row in mention_rows if str(row.get('source_type') or '') == 'repo']
    paper_rows = [row for row in mention_rows if str(row.get('source_type') or '') == 'paper']
    if len(repo_rows) >= 2 and len(paper_rows) >= 2:
        score += 2
    if len(repo_rows) == 1 or len(paper_rows) == 1:
        score -= 2
    if lower.endswith(('ing', 'tion', 'ment', 'ness', 'able', 'ible')):
        score -= 1
    return score


def _entity_dispersion_score(mention_rows: list[dict[str, Any]]) -> int:
    distinct_docs = {(str(row.get('source_type') or ''), str(row.get('source_id') or ''), str(row.get('doc_id') or '')) for row in mention_rows}
    distinct_sources = {(str(row.get('source_type') or ''), str(row.get('source_id') or '')) for row in mention_rows}
    repo_docs = {str(row.get('doc_id') or '') for row in mention_rows if str(row.get('source_type') or '') == 'repo'}
    paper_docs = {str(row.get('doc_id') or '') for row in mention_rows if str(row.get('source_type') or '') == 'paper'}
    score = 0
    if len(distinct_docs) >= 4:
        score += 2
    elif len(distinct_docs) >= 3:
        score += 1
    if len(distinct_sources) >= 4:
        score += 2
    elif len(distinct_sources) >= 3:
        score += 1
    if len(repo_docs) >= 2:
        score += 2
    elif len(repo_docs) == 1:
        score -= 1
    if len(paper_docs) >= 2:
        score += 1
    elif len(paper_docs) == 1:
        score -= 1
    return score


def _paper_path_quality(path: str) -> int:
    lower = str(path or '').lower()
    score = 0
    if 'method' in lower or 'results' in lower or 'experiment' in lower or 'discussion' in lower:
        score += 2
    if lower.endswith('.jsonl'):
        score += 1
    return score


def _candidate_priority(canonical_name: str, mention_rows: list[dict[str, Any]]) -> tuple[int, int, int, int, str]:
    compound_bonus = 1 if '_' in canonical_name else 0
    specificity = _entity_specificity_score(canonical_name, mention_rows)
    dispersion = _entity_dispersion_score(mention_rows)
    distinct_sources = len({(str(row.get('source_type') or ''), str(row.get('source_id') or '')) for row in mention_rows})
    return (-compound_bonus, -specificity, -dispersion, -distinct_sources, canonical_name)


def _chunk_locator(row: dict[str, Any], *, role: str) -> dict[str, Any]:
    metadata = json.loads(str(row.get('metadata_json') or '{}'))
    return {
        'chunk_id': str(row.get('chunk_id') or ''),
        'role': role,
        'source_type': str(row.get('source_type') or ''),
        'source_id': str(row.get('source_id') or ''),
        'doc_id': str(row.get('doc_id') or ''),
        'chunk_index': int(row.get('chunk_index') or 0),
        'modality': str(row.get('modality') or ''),
        'path': str(metadata.get('path') or ''),
        'language': metadata.get('language'),
        'token_count': int(row.get('token_count') or 0),
    }


def _doc_key(row: dict[str, Any]) -> tuple[str, str, str]:
    return (
        str(row.get('source_type') or ''),
        str(row.get('source_id') or ''),
        str(row.get('doc_id') or ''),
    )


def _build_doc_chunk_index(chunks: list[dict[str, Any]]) -> tuple[dict[tuple[str, str, str], list[dict[str, Any]]], dict[str, int]]:
    by_doc: dict[tuple[str, str, str], list[dict[str, Any]]] = {}
    for row in chunks:
        by_doc.setdefault(_doc_key(row), []).append(row)
    position_by_chunk_id: dict[str, int] = {}
    for rows in by_doc.values():
        rows.sort(key=lambda item: (int(item.get('chunk_index') or 0), str(item.get('chunk_id') or '')))
        for idx, row in enumerate(rows):
            position_by_chunk_id[str(row.get('chunk_id') or '')] = idx
    return by_doc, position_by_chunk_id


def _support_row_priority(
    row: dict[str, Any],
    *,
    mention_chunk_ids: set[str],
    core_chunk_ids: set[str],
) -> tuple[int, int, int, int, int, str, int, str]:
    chunk_id = str(row.get('chunk_id') or '')
    source_type = str(row.get('source_type') or '')
    metadata = json.loads(str(row.get('metadata_json') or '{}'))
    path = str(metadata.get('path') or '')
    mention_bonus = 1 if chunk_id in mention_chunk_ids else 0
    core_bonus = 1 if chunk_id in core_chunk_ids else 0
    implementation_bonus = 1 if source_type == 'repo' and _repo_path_is_implementation(path) else 0
    if source_type == 'repo':
        quality = _repo_path_quality(path)
    elif source_type == 'paper':
        quality = _paper_path_quality(path)
    else:
        quality = 0
    source_priority = 2 if source_type == 'repo' else 1 if source_type == 'paper' else 0
    return (
        -core_bonus,
        -mention_bonus,
        -implementation_bonus,
        -source_priority,
        -quality,
        str(row.get('source_id') or ''),
        int(row.get('chunk_index') or 0),
        chunk_id,
    )


def _expand_support_rows(
    *,
    chosen: list[dict[str, Any]],
    mention_rows: list[dict[str, Any]],
    chunks_by_doc: dict[tuple[str, str, str], list[dict[str, Any]]],
    position_by_chunk_id: dict[str, int],
    adjacent_support_window: int,
    max_expanded_support_chunks: int,
    include_all_mentions_in_support: bool,
) -> tuple[list[dict[str, Any]], dict[str, str], dict[str, Any]]:
    core_chunk_ids = [str(row.get('chunk_id') or '') for row in chosen]
    core_chunk_id_set = set(core_chunk_ids)
    mention_chunk_id_set = {str(row.get('chunk_id') or '') for row in mention_rows}
    support_by_id: dict[str, dict[str, Any]] = {str(row.get('chunk_id') or ''): row for row in chosen}
    support_roles: dict[str, str] = {}
    for row in chosen:
        chunk_id = str(row.get('chunk_id') or '')
        source_type = str(row.get('source_type') or '')
        support_roles[chunk_id] = 'repo_support' if source_type == 'repo' else 'paper_support' if source_type == 'paper' else 'other_support'

    if include_all_mentions_in_support:
        for row in mention_rows:
            chunk_id = str(row.get('chunk_id') or '')
            if chunk_id in support_by_id:
                continue
            support_by_id[chunk_id] = row
            support_roles[chunk_id] = 'entity_mention_support'

    if adjacent_support_window > 0:
        for row in chosen:
            doc_rows = chunks_by_doc.get(_doc_key(row), [])
            position = position_by_chunk_id.get(str(row.get('chunk_id') or ''))
            if position is None:
                continue
            start = max(0, position - adjacent_support_window)
            stop = min(len(doc_rows), position + adjacent_support_window + 1)
            for adjacent in doc_rows[start:stop]:
                chunk_id = str(adjacent.get('chunk_id') or '')
                if chunk_id in support_by_id:
                    continue
                support_by_id[chunk_id] = adjacent
                support_roles[chunk_id] = 'adjacent_context'

    ordered_support_rows = sorted(
        support_by_id.values(),
        key=lambda row: _support_row_priority(
            row,
            mention_chunk_ids=mention_chunk_id_set,
            core_chunk_ids=core_chunk_id_set,
        ),
    )
    if max_expanded_support_chunks > 0 and len(ordered_support_rows) > max_expanded_support_chunks:
        ordered_support_rows = ordered_support_rows[:max_expanded_support_chunks]
        retained_ids = {str(row.get('chunk_id') or '') for row in ordered_support_rows}
        support_roles = {chunk_id: role for chunk_id, role in support_roles.items() if chunk_id in retained_ids}

    ordered_support_rows.sort(
        key=lambda row: (
            str(row.get('source_type') or ''),
            str(row.get('source_id') or ''),
            str(row.get('doc_id') or ''),
            int(row.get('chunk_index') or 0),
            str(row.get('chunk_id') or ''),
        )
    )
    ordered_ids = [str(row.get('chunk_id') or '') for row in ordered_support_rows]
    expansion_summary = {
        'core_supporting_chunk_count': len(core_chunk_ids),
        'expanded_supporting_chunk_count': len(ordered_ids),
        'extra_supporting_chunk_count': max(0, len(ordered_ids) - len(core_chunk_ids)),
        'adjacent_support_window': int(adjacent_support_window),
        'max_expanded_support_chunks': int(max_expanded_support_chunks),
        'include_all_mentions_in_support': bool(include_all_mentions_in_support),
    }
    return ordered_support_rows, support_roles, expansion_summary


def _difficulty_label(level: int) -> str:
    labels = {
        0: 'syntax_or_local',
        1: 'single_file_grounding',
        2: 'multi_chunk_grounding',
        3: 'multi_file_transition',
        4: 'cross_source_transition',
        5: 'high_dispersion_reconciliation',
    }
    return labels.get(level, 'unknown')


def _difficulty_profile(chosen: list[dict[str, Any]]) -> dict[str, Any]:
    repo_rows = [row for row in chosen if str(row.get('source_type') or '') == 'repo']
    paper_rows = [row for row in chosen if str(row.get('source_type') or '') == 'paper']
    repo_docs = {str(row.get('doc_id') or '') for row in repo_rows}
    paper_docs = {str(row.get('doc_id') or '') for row in paper_rows}
    paths = set()
    for row in chosen:
        metadata = json.loads(str(row.get('metadata_json') or '{}'))
        paths.add(str(metadata.get('path') or ''))
    level = 1
    if len(chosen) >= 3:
        level += 1
    if len(repo_docs) >= 2 or len(paths) >= 3:
        level += 1
    if len(paper_docs) >= 2 and len(repo_docs) >= 1:
        level += 1
    if len(repo_docs) >= 2 and len(paper_docs) >= 2:
        level += 1
    level = max(0, min(5, level))
    return {
        'level': level,
        'label': _difficulty_label(level),
        'signals': {
            'supporting_chunk_count': len(chosen),
            'repo_doc_count': len(repo_docs),
            'paper_doc_count': len(paper_docs),
            'path_count': len(paths),
        },
    }


def _quality_bucket(overall_score: int) -> str:
    if overall_score >= 80:
        return 'high'
    if overall_score >= 60:
        return 'medium'
    return 'low'


def _candidate_quality_profile(
    *,
    canonical_name: str,
    mention_rows: list[dict[str, Any]],
    chosen: list[dict[str, Any]],
    repo_pairs: list[tuple[int, dict[str, Any]]],
    paper_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    specificity = _entity_specificity_score(canonical_name, mention_rows)
    dispersion = _entity_dispersion_score(mention_rows)
    repo_quality_mean = mean(max(0, quality) for quality, _ in repo_pairs) if repo_pairs else 0.0
    support_balance = min(len(repo_pairs), len(paper_rows))
    supporting_docs = len({(str(row.get('source_type') or ''), str(row.get('doc_id') or '')) for row in chosen})
    overall_score = int(
        max(0, min(100, (
            10 * specificity
            + 8 * dispersion
            + 6 * support_balance
            + 4 * supporting_docs
            + 3 * repo_quality_mean
        )))
    )
    return {
        'specificity': specificity,
        'dispersion': dispersion,
        'repo_path_precision': round(repo_quality_mean, 2),
        'paper_support_count': len(paper_rows),
        'repo_support_count': len(repo_pairs),
        'support_balance': support_balance,
        'supporting_doc_count': supporting_docs,
        'overall_score': overall_score,
        'bucket': _quality_bucket(overall_score),
    }


def _skill_tags(canonical_name: str, chosen: list[dict[str, Any]]) -> list[str]:
    tags = {'state_transition', 'retrieval_grounded', 'multi_source'}
    if '_' in canonical_name:
        tags.add('compound_concept')
    source_types = {str(row.get('source_type') or '') for row in chosen}
    if 'repo' in source_types:
        tags.add('software_maintenance')
    if 'paper' in source_types:
        tags.add('paper_grounding')
    if len({str(row.get('doc_id') or '') for row in chosen if str(row.get('source_type') or '') == 'repo'}) >= 2:
        tags.add('cross_repo_evidence')
    return sorted(tags)


def _dataset_compiler_payload(
    *,
    canonical_name: str,
    mention_rows: list[dict[str, Any]],
    chosen: list[dict[str, Any]],
    support_rows: list[dict[str, Any]],
    support_roles: dict[str, str],
    repo_pairs: list[tuple[int, dict[str, Any]]],
    paper_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    retrieval_links = [
        _chunk_locator(row, role=str(support_roles.get(str(row.get('chunk_id') or ''), 'other_support')))
        for row in support_rows
    ]
    difficulty = _difficulty_profile(chosen)
    quality = _candidate_quality_profile(
        canonical_name=canonical_name,
        mention_rows=mention_rows,
        chosen=chosen,
        repo_pairs=repo_pairs,
        paper_rows=paper_rows,
    )
    return {
        'task_type': 'state_transition_reconciliation',
        'segmentation_units': sorted({str(row.get('source_type') or '') for row in support_rows}),
        'skill_tags': _skill_tags(canonical_name, chosen),
        'difficulty': difficulty,
        'quality': quality,
        'retrieval_links': retrieval_links,
    }


def mine_candidates(
    *,
    index_dir: Path,
    max_candidates: int = 5000,
    min_sources: int = 2,
    required_source_types: tuple[str, ...] = ('paper', 'repo'),
    max_entity_chunk_ratio: float = 0.01,
    max_compound_entity_chunk_ratio: float = 0.04,
    compound_only: bool = False,
    adjacent_support_window: int = 2,
    max_expanded_support_chunks: int = 64,
    include_all_mentions_in_support: bool = True,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    chunks = _read_rows(index_dir / 'chunks')
    entities = _read_rows(index_dir / 'entities')
    total_chunk_count = max(1, len(chunks))
    chunk_by_id = {str(row['chunk_id']): row for row in chunks}
    chunks_by_doc, position_by_chunk_id = _build_doc_chunk_index(chunks)
    candidates: list[dict[str, Any]] = []

    ranked_entities: list[tuple[tuple[int, int, int, int, str], dict[str, Any], list[dict[str, Any]]]] = []
    for entity in entities:
        canonical_name = str(entity.get('canonical_name') or '')
        if not _canonical_name_ok(canonical_name):
            continue
        if compound_only and '_' not in canonical_name:
            continue
        mentions = json.loads(str(entity.get('mentions_json') or '[]'))
        mention_rows = [chunk_by_id[m] for m in mentions if m in chunk_by_id]
        if len(mention_rows) < 2:
            continue
        ranked_entities.append((_candidate_priority(canonical_name, mention_rows), entity, mention_rows))

    for _, entity, mention_rows in sorted(ranked_entities, key=lambda item: item[0]):
        canonical_name = str(entity.get('canonical_name') or '')
        distinct_chunk_ratio = len({str(row.get('chunk_id') or '') for row in mention_rows}) / total_chunk_count
        ratio_limit = max_compound_entity_chunk_ratio if '_' in canonical_name else max_entity_chunk_ratio
        if distinct_chunk_ratio > ratio_limit:
            continue
        if len(mention_rows) < 2:
            continue
        source_types = {str(row.get('source_type') or '') for row in mention_rows}
        if len(source_types) < min_sources:
            continue
        if required_source_types and not set(required_source_types).issubset(source_types):
            continue
        support_ok = _compound_entity_support_ok(mention_rows, required_source_types) if '_' in canonical_name else _entity_support_ok(mention_rows, required_source_types)
        if not support_ok:
            continue
        if _entity_specificity_score(canonical_name, mention_rows) < 1:
            continue
        if _entity_dispersion_score(mention_rows) < 3:
            continue

        scored_rows = []
        for row in mention_rows:
            metadata = json.loads(str(row.get('metadata_json') or '{}'))
            path = str(metadata.get('path') or '')
            source_type = str(row.get('source_type') or '')
            if source_type == 'repo':
                quality = _repo_path_quality(path)
            elif source_type == 'paper':
                quality = _paper_path_quality(path)
            else:
                quality = 0
            scored_rows.append((quality, row))

        paper_rows = [row for quality, row in scored_rows if str(row.get('source_type') or '') == 'paper' and quality >= 0]
        sorted_repo_scored = [
            (quality, row)
            for quality, row in sorted(
                scored_rows,
                key=lambda item: _repo_row_sort_key(item[1], quality=item[0]) if str(item[1].get('source_type') or '') == 'repo' else (0, 0, 0, ''),
            )
            if str(row.get('source_type') or '') == 'repo'
        ]
        repo_pairs = [(quality, row) for quality, row in sorted_repo_scored if _repo_row_usable(row, quality=quality)]
        implementation_repo_pairs = []
        for quality, row in repo_pairs:
            metadata = json.loads(str(row.get('metadata_json') or '{}'))
            repo_path = str(metadata.get('path') or '')
            if _repo_path_is_implementation(repo_path):
                implementation_repo_pairs.append((quality, row))
        if implementation_repo_pairs:
            repo_pairs = implementation_repo_pairs
        elif '_' in canonical_name:
            repo_pairs = [(quality, row) for quality, row in sorted_repo_scored if _repo_concept_row_usable(row, quality=quality)]
        elif 'repo' in required_source_types:
            continue
        repo_rows = [row for _, row in repo_pairs]
        if required_source_types == ('paper', 'repo') and (not paper_rows or not repo_rows):
            continue

        chosen = sorted(
            paper_rows[:4] + repo_rows[:2],
            key=lambda row: (str(row.get('source_type') or ''), str(row.get('source_id') or ''), str(row.get('doc_id') or ''), int(row.get('chunk_index') or 0)),
        )
        if len(chosen) < 2:
            continue

        transitions = []
        state_name = f"{canonical_name}_active"
        current = False
        for idx, row in enumerate(chosen, start=1):
            source_type = str(row.get('source_type') or '')
            if source_type == 'paper':
                current = True
                kind = 'claim'
            elif source_type == 'repo':
                current = True
                kind = 'implementation_evidence'
            else:
                current = not current
                kind = 'trace_or_benchmark_signal'
            transitions.append({
                'transition_id': stable_id('t', entity['entity_id'], row['chunk_id'], str(idx)),
                'trigger_chunk_id': row['chunk_id'],
                'source_type': source_type,
                'kind': kind,
                'effects': {state_name: current},
            })

        final_state = {state_name: False}
        for transition in transitions:
            final_state.update(transition['effects'])
        support_rows, support_roles, support_expansion = _expand_support_rows(
            chosen=chosen,
            mention_rows=mention_rows,
            chunks_by_doc=chunks_by_doc,
            position_by_chunk_id=position_by_chunk_id,
            adjacent_support_window=adjacent_support_window,
            max_expanded_support_chunks=max_expanded_support_chunks,
            include_all_mentions_in_support=include_all_mentions_in_support,
        )
        core_supporting_chunk_ids = [transition['trigger_chunk_id'] for transition in transitions]
        dataset_compiler = _dataset_compiler_payload(
            canonical_name=canonical_name,
            mention_rows=mention_rows,
            chosen=chosen,
            support_rows=support_rows,
            support_roles=support_roles,
            repo_pairs=repo_pairs,
            paper_rows=paper_rows,
        )
        candidates.append({
            'candidate_id': stable_id('cand', entity['entity_id'], str(len(candidates) + 1)),
            'canonical_name': canonical_name,
            'entity_id': entity['entity_id'],
            'template_family': 'compound_concept_transition' if '_' in canonical_name else 'natural_multi_source_transition',
            'state_variable': state_name,
            'required_source_types': sorted({str(row.get('source_type') or '') for row in chosen}),
            'core_supporting_chunk_ids': core_supporting_chunk_ids,
            'supporting_chunk_ids': [str(row.get('chunk_id') or '') for row in support_rows],
            'support_expansion': support_expansion,
            'transition_chain': transitions,
            'initial_state': {state_name: False},
            'final_state': final_state,
            'dataset_compiler': dataset_compiler,
        })
        if len(candidates) >= max_candidates:
            break

    family_counts: dict[str, int] = {}
    quality_bucket_counts: dict[str, int] = {}
    difficulty_level_counts: dict[str, int] = {}
    for candidate in candidates:
        family = str(candidate.get('template_family') or 'unknown')
        family_counts[family] = family_counts.get(family, 0) + 1
        compiler = candidate.get('dataset_compiler') or {}
        quality = compiler.get('quality') or {}
        bucket = str(quality.get('bucket') or 'unknown')
        quality_bucket_counts[bucket] = quality_bucket_counts.get(bucket, 0) + 1
        difficulty = compiler.get('difficulty') or {}
        level = str(difficulty.get('level') if difficulty.get('level') is not None else 'unknown')
        difficulty_level_counts[level] = difficulty_level_counts.get(level, 0) + 1
    expanded_support_counts = [int((candidate.get('support_expansion') or {}).get('expanded_supporting_chunk_count') or 0) for candidate in candidates]
    core_support_counts = [int((candidate.get('support_expansion') or {}).get('core_supporting_chunk_count') or 0) for candidate in candidates]
    summary = {
        'candidate_count': len(candidates),
        'max_candidates': max_candidates,
        'min_sources': min_sources,
        'required_source_types': list(required_source_types),
        'max_entity_chunk_ratio': max_entity_chunk_ratio,
        'max_compound_entity_chunk_ratio': max_compound_entity_chunk_ratio,
        'adjacent_support_window': int(adjacent_support_window),
        'max_expanded_support_chunks': int(max_expanded_support_chunks),
        'include_all_mentions_in_support': bool(include_all_mentions_in_support),
        'template_family_counts': dict(sorted(family_counts.items())),
        'quality_bucket_counts': dict(sorted(quality_bucket_counts.items())),
        'difficulty_level_counts': dict(sorted(difficulty_level_counts.items())),
        'supporting_chunk_count_stats': {
            'core_min': min(core_support_counts, default=0),
            'core_max': max(core_support_counts, default=0),
            'expanded_min': min(expanded_support_counts, default=0),
            'expanded_max': max(expanded_support_counts, default=0),
            'expanded_avg': mean(expanded_support_counts),
        },
        'compound_only': compound_only,
    }
    return candidates, summary


def main() -> None:
    parser = argparse.ArgumentParser(description='Mine transition candidates from a long-context corpus index.')
    parser.add_argument('--index-dir', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--summary-output', type=Path)
    parser.add_argument('--max-candidates', type=int, default=5000)
    parser.add_argument('--min-sources', type=int, default=2)
    parser.add_argument('--required-source-types', type=str, default='paper,repo')
    parser.add_argument('--max-entity-chunk-ratio', type=float, default=0.01)
    parser.add_argument('--max-compound-entity-chunk-ratio', type=float, default=0.04)
    parser.add_argument('--compound-only', action='store_true')
    parser.add_argument('--adjacent-support-window', type=int, default=2)
    parser.add_argument('--max-expanded-support-chunks', type=int, default=64)
    parser.add_argument('--no-include-all-mentions-in-support', action='store_true')
    parser.add_argument('--allow-candidate-mining', action='store_true', help='Required before reading a real corpus index.')
    parser.add_argument('--allow-arxiv-output', action='store_true', help='Required before writing candidates under /arxiv.')
    args = parser.parse_args()
    validate_candidate_mining_request(
        index_dir=args.index_dir,
        output=args.output,
        allow_candidate_mining=args.allow_candidate_mining,
        allow_arxiv_output=args.allow_arxiv_output,
    )
    candidates, summary = mine_candidates(
        index_dir=args.index_dir,
        max_candidates=args.max_candidates,
        min_sources=args.min_sources,
        required_source_types=tuple(item.strip() for item in args.required_source_types.split(',') if item.strip()),
        max_entity_chunk_ratio=args.max_entity_chunk_ratio,
        max_compound_entity_chunk_ratio=args.max_compound_entity_chunk_ratio,
        compound_only=args.compound_only,
        adjacent_support_window=args.adjacent_support_window,
        max_expanded_support_chunks=args.max_expanded_support_chunks,
        include_all_mentions_in_support=not args.no_include_all_mentions_in_support,
    )
    write_jsonl(args.output, candidates)
    write_json(args.summary_output or args.output.with_name('candidates_summary.json'), summary)


if __name__ == '__main__':
    main()
