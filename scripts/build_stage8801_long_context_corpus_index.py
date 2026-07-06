from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from itertools import combinations
from pathlib import Path
from typing import Any

from long_context_common import (
    approx_token_count,
    chunk_text,
    extract_terms,
    iter_text_files,
    language_from_suffix,
    modality_from_suffix,
    safe_read_text,
    source_id_from_path,
    source_type_from_path,
    stable_id,
    write_json,
)
from long_context_parquet import shard_path, write_parquet_shard

FORBIDDEN_CORPUS_ROOTS = {
    Path('/arxiv'),
    Path('/arxiv/datasets'),
    Path('/arxiv/repositories'),
    Path('/data/repository_library'),
}


class CorpusIndexSafetyError(ValueError):
    """Raised when corpus indexing is requested without an explicit gate."""


def _is_relative_to(child: Path, parent: Path) -> bool:
    try:
        child.relative_to(parent)
        return True
    except ValueError:
        return False


def _resolve_existing_or_parent(path: Path) -> Path:
    path = Path(path).expanduser()
    if path.exists():
        return path.resolve()
    parent = path.parent
    if parent.exists():
        return parent.resolve() / path.name
    return parent


def validate_corpus_index_request(
    *,
    paper_roots: list[Path],
    repo_roots: list[Path],
    dataset_roots: list[Path],
    output_dir: Path,
    allow_corpus_scan: bool,
    allow_arxiv_output: bool,
) -> dict[str, Any]:
    roots = [Path(root).expanduser() for root in paper_roots + repo_roots + dataset_roots]
    resolved_roots = [_resolve_existing_or_parent(root) for root in roots]
    resolved_output = _resolve_existing_or_parent(output_dir)
    forbidden_hits: list[str] = []
    for root in resolved_roots:
        for forbidden in FORBIDDEN_CORPUS_ROOTS:
            forbidden_resolved = forbidden.resolve()
            if root == forbidden_resolved or _is_relative_to(root, forbidden_resolved):
                forbidden_hits.append(str(root))
                break

    arxiv_root = Path('/arxiv')
    output_under_arxiv = resolved_output == arxiv_root or _is_relative_to(resolved_output, arxiv_root)
    checks = {
        'allow_corpus_scan_flag': allow_corpus_scan,
        'corpus_roots_require_explicit_scan_flag': allow_corpus_scan or not roots,
        'forbidden_roots_require_explicit_scan_flag': allow_corpus_scan or not forbidden_hits,
        'arxiv_output_requires_explicit_output_flag': allow_arxiv_output or not output_under_arxiv,
    }
    failures = [key for key, passed in checks.items() if passed is not True]
    if failures:
        raise CorpusIndexSafetyError(json.dumps({
            'failures': failures,
            'forbidden_root_hits': forbidden_hits,
            'output_under_arxiv': output_under_arxiv,
            'checks': checks,
        }, sort_keys=True))
    return {
        'resolved_roots': [str(root) for root in resolved_roots],
        'resolved_output_dir': str(resolved_output),
        'forbidden_root_hits': forbidden_hits,
        'output_under_arxiv': output_under_arxiv,
        'checks': checks,
    }


def _read_parquet_rows(directory: Path) -> list[dict[str, Any]]:
    import pyarrow.parquet as pq

    rows: list[dict[str, Any]] = []
    for path in sorted(directory.glob('*.parquet')):
        table = pq.read_table(path)
        rows.extend(table.to_pylist())
    return rows


def _chunk_row(*, source_root: Path, path: Path, chunk_index: int, text: str) -> dict[str, Any]:
    source_type = source_type_from_path(path, source_root=source_root)
    source_id = source_id_from_path(path, source_root=source_root)
    rel = str(path.relative_to(source_root))
    metadata = {
        'path': rel,
        'language': language_from_suffix(path),
        'section_name': None,
        'title': path.stem if source_type == 'paper' else None,
        'symbol_names': [],
        'imports': [],
        'method_terms': extract_terms(text, max_terms=8),
        'benchmark_terms': [],
        'error_terms': [term for term in extract_terms(text, max_terms=12) if 'error' in term or 'fail' in term],
    }
    return {
        'chunk_id': stable_id(source_type, source_id, rel, str(chunk_index)),
        'source_type': source_type,
        'source_id': source_id,
        'doc_id': rel,
        'chunk_index': chunk_index,
        'modality': modality_from_suffix(path),
        'token_count': approx_token_count(text),
        'text': text,
        'metadata_json': json.dumps(metadata, sort_keys=True),
    }


def _mention_rows(chunk: dict[str, Any]) -> list[dict[str, Any]]:
    metadata = json.loads(chunk['metadata_json'])
    candidates = set(extract_terms(chunk.get('text', ''), max_terms=16))
    for field in ('method_terms', 'benchmark_terms', 'error_terms', 'symbol_names'):
        value = metadata.get(field)
        if isinstance(value, list):
            candidates.update(str(item).lower() for item in value if str(item).strip())
    rows = []
    for term in sorted(candidates):
        if len(term) < 3:
            continue
        rows.append({
            'term': term,
            'chunk_id': chunk['chunk_id'],
            'source_type': chunk['source_type'],
            'source_id': chunk['source_id'],
            'doc_id': chunk['doc_id'],
        })
    return rows


def build_chunk_and_mention_shards(
    *,
    paper_roots: list[Path],
    repo_roots: list[Path],
    dataset_roots: list[Path],
    output_dir: Path,
    paper_chunk_tokens: int = 1024,
    repo_chunk_tokens: int = 512,
    trace_chunk_tokens: int = 384,
    max_files_per_root: int | None = None,
    max_chars_per_file: int = 120_000,
    rows_per_shard: int = 5000,
) -> dict[str, Any]:
    chunks_dir = output_dir / 'chunks'
    mentions_dir = output_dir / 'chunk_mentions'
    chunks_dir.mkdir(parents=True, exist_ok=True)
    mentions_dir.mkdir(parents=True, exist_ok=True)

    chunk_buffer: list[dict[str, Any]] = []
    mention_buffer: list[dict[str, Any]] = []
    chunk_shard = 0
    mention_shard = 0
    inventory: list[dict[str, Any]] = []
    source_counts: Counter[str] = Counter()
    file_count = 0

    all_roots = [(root, 'paper') for root in paper_roots] + [(root, 'repo') for root in repo_roots] + [(root, 'dataset') for root in dataset_roots]
    for root, declared_type in all_roots:
        if not root.exists():
            inventory.append({'root': str(root), 'declared_type': declared_type, 'exists': False, 'files_scanned': 0})
            continue
        scanned = 0
        for index, path in enumerate(iter_text_files(root)):
            if max_files_per_root is not None and index >= max_files_per_root:
                break
            scanned += 1
            file_count += 1
            raw = safe_read_text(path, max_chars=max_chars_per_file)
            if not raw.strip():
                continue
            budget = paper_chunk_tokens if declared_type == 'paper' else repo_chunk_tokens if declared_type == 'repo' else trace_chunk_tokens
            for local_chunk_index, text in enumerate(chunk_text(raw, max_tokens=budget), start=1):
                row = _chunk_row(source_root=root, path=path, chunk_index=local_chunk_index, text=text)
                chunk_buffer.append(row)
                source_counts[row['source_type']] += 1
                mention_buffer.extend(_mention_rows(row))
                if len(chunk_buffer) >= rows_per_shard:
                    write_parquet_shard(shard_path(chunks_dir, 'chunks', chunk_shard), chunk_buffer)
                    chunk_shard += 1
                    chunk_buffer = []
                if len(mention_buffer) >= rows_per_shard:
                    write_parquet_shard(shard_path(mentions_dir, 'chunk_mentions', mention_shard), mention_buffer)
                    mention_shard += 1
                    mention_buffer = []
        inventory.append({'root': str(root), 'declared_type': declared_type, 'exists': True, 'files_scanned': scanned})

    if chunk_buffer:
        write_parquet_shard(shard_path(chunks_dir, 'chunks', chunk_shard), chunk_buffer)
        chunk_shard += 1
    if mention_buffer:
        write_parquet_shard(shard_path(mentions_dir, 'chunk_mentions', mention_shard), mention_buffer)
        mention_shard += 1

    summary = {
        'file_count': file_count,
        'chunk_count': int(sum(source_counts.values())),
        'source_type_counts': dict(sorted(source_counts.items())),
        'chunk_shards': chunk_shard,
        'mention_shards': mention_shard,
        'inventory': inventory,
    }
    write_json(output_dir / 'source_inventory.json', summary)
    return summary


def build_entities_with_pyarrow(*, output_dir: Path, min_mention_count: int = 2) -> dict[str, Any]:
    mentions = _read_parquet_rows(output_dir / 'chunk_mentions')
    by_term: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in mentions:
        by_term[str(row['term'])].append(row)

    entity_rows: list[dict[str, Any]] = []
    for term, rows in sorted(by_term.items()):
        chunk_ids = sorted({str(row['chunk_id']) for row in rows})
        if len(chunk_ids) < min_mention_count:
            continue
        counts = Counter(str(row['source_type']) for row in rows)
        entity_rows.append({
            'entity_id': stable_id('ent', term),
            'canonical_name': term,
            'alias': term,
            'mention_count': len(rows),
            'distinct_chunk_count': len(chunk_ids),
            'mentions_json': json.dumps(chunk_ids),
            'source_type_counts_json': json.dumps(dict(sorted(counts.items())), sort_keys=True),
        })

    entities_dir = output_dir / 'entities'
    entities_dir.mkdir(parents=True, exist_ok=True)
    write_parquet_shard(entities_dir / 'entities-000000.parquet', entity_rows)
    summary = {
        'entity_count': len(entity_rows),
        'min_mention_count': min_mention_count,
        'top_entities': [
            {'canonical_name': row['canonical_name'], 'mention_count': row['mention_count']}
            for row in sorted(entity_rows, key=lambda item: (-int(item['mention_count']), item['canonical_name']))[:20]
        ],
    }
    write_json(output_dir / 'entity_aliases.json', summary)
    return summary


def build_links_with_pyarrow(*, output_dir: Path, max_pairwise_mentions_per_entity: int = 64) -> dict[str, Any]:
    chunks = _read_parquet_rows(output_dir / 'chunks')
    mentions = _read_parquet_rows(output_dir / 'chunk_mentions')
    entities = _read_parquet_rows(output_dir / 'entities')

    entity_by_term = {str(row['canonical_name']): row for row in entities}
    links: list[dict[str, Any]] = []
    edge_counts: Counter[str] = Counter()

    for mention in mentions:
        entity = entity_by_term.get(str(mention['term']))
        if entity is None:
            continue
        entity_id = str(entity['entity_id'])
        chunk_id = str(mention['chunk_id'])
        links.append({
            'link_id': stable_id('link', chunk_id, entity_id, 'chunk_mentions_entity'),
            'src': chunk_id,
            'dst': entity_id,
            'edge_type': 'chunk_mentions_entity',
        })
        edge_counts['chunk_mentions_entity'] += 1
        links.append({
            'link_id': stable_id('link', entity_id, chunk_id, 'entity_mentioned_by_chunk'),
            'src': entity_id,
            'dst': chunk_id,
            'edge_type': 'entity_mentioned_by_chunk',
        })
        edge_counts['entity_mentioned_by_chunk'] += 1

    by_doc: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for chunk in chunks:
        by_doc[(str(chunk['source_id']), str(chunk['doc_id']))].append(chunk)
    for doc_chunks in by_doc.values():
        doc_chunks.sort(key=lambda row: int(row['chunk_index']))
        for left, right in zip(doc_chunks, doc_chunks[1:]):
            links.append({
                'link_id': stable_id('link', str(left['chunk_id']), str(right['chunk_id']), 'adjacent_chunk'),
                'src': str(left['chunk_id']),
                'dst': str(right['chunk_id']),
                'edge_type': 'adjacent_chunk',
            })
            edge_counts['adjacent_chunk'] += 1

    mentions_by_term: dict[str, list[str]] = defaultdict(list)
    for mention in mentions:
        if str(mention['term']) not in entity_by_term:
            continue
        mentions_by_term[str(mention['term'])].append(str(mention['chunk_id']))
    for term, chunk_ids in mentions_by_term.items():
        entity_id = str(entity_by_term[term]['entity_id'])
        capped = sorted(set(chunk_ids))[:max_pairwise_mentions_per_entity]
        for left, right in combinations(capped, 2):
            links.append({
                'link_id': stable_id('link', entity_id, left, right, 'entity_co_mention'),
                'src': left,
                'dst': right,
                'edge_type': 'entity_co_mention',
                'entity_id': entity_id,
            })
            edge_counts['entity_co_mention'] += 1

    links_dir = output_dir / 'links'
    links_dir.mkdir(parents=True, exist_ok=True)
    write_parquet_shard(links_dir / 'links-000000.parquet', links)
    summary = {
        'link_count': len(links),
        'edge_type_counts': dict(sorted(edge_counts.items())),
        'max_pairwise_mentions_per_entity': max_pairwise_mentions_per_entity,
    }
    write_json(output_dir / 'links_summary.json', summary)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description='Build a production-grade long-context corpus index with sharded Parquet outputs.')
    parser.add_argument('--papers-root', action='append', type=Path, default=[])
    parser.add_argument('--repos-root', action='append', type=Path, default=[])
    parser.add_argument('--datasets-root', action='append', type=Path, default=[])
    parser.add_argument('--output-dir', type=Path, required=True)
    parser.add_argument('--paper-chunk-tokens', type=int, default=1024)
    parser.add_argument('--repo-chunk-tokens', type=int, default=512)
    parser.add_argument('--trace-chunk-tokens', type=int, default=384)
    parser.add_argument('--max-files-per-root', type=int)
    parser.add_argument('--max-chars-per-file', type=int, default=120000)
    parser.add_argument('--rows-per-shard', type=int, default=5000)
    parser.add_argument('--min-mention-count', type=int, default=2)
    parser.add_argument('--max-pairwise-mentions-per-entity', type=int, default=64)
    parser.add_argument('--allow-corpus-scan', action='store_true', help='Required for any real corpus scan, including /arxiv or repository_library roots.')
    parser.add_argument('--allow-arxiv-output', action='store_true', help='Required before writing the index under /arxiv.')
    args = parser.parse_args()

    out = args.output_dir
    validate_corpus_index_request(
        paper_roots=args.papers_root,
        repo_roots=args.repos_root,
        dataset_roots=args.datasets_root,
        output_dir=out,
        allow_corpus_scan=args.allow_corpus_scan,
        allow_arxiv_output=args.allow_arxiv_output,
    )
    out.mkdir(parents=True, exist_ok=True)

    source_summary = build_chunk_and_mention_shards(
        paper_roots=args.papers_root,
        repo_roots=args.repos_root,
        dataset_roots=args.datasets_root,
        output_dir=out,
        paper_chunk_tokens=args.paper_chunk_tokens,
        repo_chunk_tokens=args.repo_chunk_tokens,
        trace_chunk_tokens=args.trace_chunk_tokens,
        max_files_per_root=args.max_files_per_root,
        max_chars_per_file=args.max_chars_per_file,
        rows_per_shard=args.rows_per_shard,
    )
    entity_summary = build_entities_with_pyarrow(output_dir=out, min_mention_count=args.min_mention_count)
    link_summary = build_links_with_pyarrow(output_dir=out, max_pairwise_mentions_per_entity=args.max_pairwise_mentions_per_entity)

    write_json(out / 'index_summary.json', {
        'source_summary': source_summary,
        'entity_summary': entity_summary,
        'link_summary': link_summary,
    })


if __name__ == '__main__':
    main()
