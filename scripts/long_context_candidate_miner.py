from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from long_context_common import GENERIC_CORPUS_TERMS, STOPWORDS, STRUCTURED_NOISE_TERMS, stable_id, write_json, write_jsonl


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
        'actions', 'base', 'behavior', 'both', 'given', 'next', 'task', 'days', 'plugin', 'resource', 'display',
        'return', 'state', 'updates', 'active', 'first', 'name', 'title', 'protocol', 'rewrite', 'any', 'files',
        'code', 'work', 'html', 'const', 'var', 'use', 'you', 'button', 'pdf', 'index', 'fig', 'com', 'https',
        'github', 'training', 'network', 'networks', 'maps', 'matrix', 'language', 'power', 'environment', 'module',
    }
    return lower not in banned


def _repo_path_quality(path: str) -> int:
    lower = str(path or '').lower()
    score = 0
    if any(part in lower for part in ['/src/', '/lib/', '/app/', '/core/']):
        score += 3
    if lower.endswith(('.py', '.ts', '.tsx', '.js', '.jsx', '.java', '.go', '.rs', '.c', '.cc', '.cpp')):
        score += 2
    if any(part in lower for part in ['/test', '/tests']):
        score += 1
    if any(part in lower for part in ['/dist/', '/build/', '/binder/']):
        score -= 3
    if 'readme' in lower or lower.endswith('.md'):
        score -= 2
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
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    chunks = _read_rows(index_dir / 'chunks')
    entities = _read_rows(index_dir / 'entities')
    chunk_by_id = {str(row['chunk_id']): row for row in chunks}
    candidates: list[dict[str, Any]] = []

    for entity in entities:
        canonical_name = str(entity.get('canonical_name') or '')
        if not _canonical_name_ok(canonical_name):
            continue
        mentions = json.loads(str(entity.get('mentions_json') or '[]'))
        mention_rows = [chunk_by_id[m] for m in mentions if m in chunk_by_id]
        if len(mention_rows) < 2:
            continue
        source_types = {str(row.get('source_type') or '') for row in mention_rows}
        if len(source_types) < min_sources:
            continue
        if required_source_types and not set(required_source_types).issubset(source_types):
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
        repo_rows = [row for quality, row in scored_rows if str(row.get('source_type') or '') == 'repo' and quality > 0]
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
    )
    write_jsonl(args.output, candidates)
    write_json(args.summary_output or args.output.with_name('candidates_summary.json'), summary)


if __name__ == '__main__':
    main()
