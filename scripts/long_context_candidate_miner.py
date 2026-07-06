from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

from long_context_common import GENERIC_CORPUS_TERMS, STOPWORDS, STRUCTURED_NOISE_TERMS, stable_id, write_json, write_jsonl


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


def mine_candidates(
    *,
    index_dir: Path,
    max_candidates: int = 5000,
    min_sources: int = 2,
    required_source_types: tuple[str, ...] = ('paper', 'repo'),
    max_entity_chunk_ratio: float = 0.01,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    chunks = _read_rows(index_dir / 'chunks')
    entities = _read_rows(index_dir / 'entities')
    total_chunk_count = max(1, len(chunks))
    chunk_by_id = {str(row['chunk_id']): row for row in chunks}
    candidates: list[dict[str, Any]] = []

    for entity in entities:
        canonical_name = str(entity.get('canonical_name') or '')
        if not _canonical_name_ok(canonical_name):
            continue
        mentions = json.loads(str(entity.get('mentions_json') or '[]'))
        mention_rows = [chunk_by_id[m] for m in mentions if m in chunk_by_id]
        distinct_chunk_ratio = len({str(row.get('chunk_id') or '') for row in mention_rows}) / total_chunk_count
        if distinct_chunk_ratio > max_entity_chunk_ratio:
            continue
        if len(mention_rows) < 2:
            continue
        source_types = {str(row.get('source_type') or '') for row in mention_rows}
        if len(source_types) < min_sources:
            continue
        if required_source_types and not set(required_source_types).issubset(source_types):
            continue
        if not _entity_support_ok(mention_rows, required_source_types):
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
        repo_pairs = [
            (quality, row)
            for quality, row in sorted(
                scored_rows,
                key=lambda item: _repo_row_sort_key(item[1], quality=item[0]) if str(item[1].get('source_type') or '') == 'repo' else (0, 0, 0, ''),
            )
            if str(row.get('source_type') or '') == 'repo' and _repo_row_usable(row, quality=quality)
        ]
        implementation_repo_pairs = []
        for quality, row in repo_pairs:
            metadata = json.loads(str(row.get('metadata_json') or '{}'))
            repo_path = str(metadata.get('path') or '')
            if _repo_path_is_implementation(repo_path):
                implementation_repo_pairs.append((quality, row))
        if implementation_repo_pairs:
            repo_pairs = implementation_repo_pairs
        elif 'repo' in required_source_types:
            continue
        repo_rows = [row for _, row in repo_pairs]
        if required_source_types == ('paper', 'repo') and (not paper_rows or not repo_rows):
            continue

        chosen = sorted(paper_rows[:4] + repo_rows[:2], key=lambda row: (str(row.get('source_type') or ''), str(row.get('source_id') or ''), str(row.get('doc_id') or ''), int(row.get('chunk_index') or 0)))
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
        candidates.append({
            'candidate_id': stable_id('cand', entity['entity_id'], str(len(candidates) + 1)),
            'canonical_name': canonical_name,
            'entity_id': entity['entity_id'],
            'template_family': 'natural_multi_source_transition',
            'state_variable': state_name,
            'required_source_types': sorted({str(row.get('source_type') or '') for row in chosen}),
            'supporting_chunk_ids': [transition['trigger_chunk_id'] for transition in transitions],
            'transition_chain': transitions,
            'initial_state': {state_name: False},
            'final_state': final_state,
        })
        if len(candidates) >= max_candidates:
            break

    summary = {
        'candidate_count': len(candidates),
        'max_candidates': max_candidates,
        'min_sources': min_sources,
        'required_source_types': list(required_source_types),
        'max_entity_chunk_ratio': max_entity_chunk_ratio,
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
    )
    write_jsonl(args.output, candidates)
    write_json(args.summary_output or args.output.with_name('candidates_summary.json'), summary)


if __name__ == '__main__':
    main()
