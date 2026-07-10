from __future__ import annotations

import argparse
import json
import subprocess
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from long_context_common import extract_compound_terms, extract_terms, stable_id, write_json, write_jsonl

GENERIC_QUERY_TERMS = {
    'src', 'main', 'index', 'test', 'tests', 'app', 'lib', 'core', 'script', 'scripts', 'model', 'models',
    'utils', 'helper', 'helpers', 'repair', 'patch', 'tool', 'used', 'edit', 'local', 'repo',
}


def _read_parquet_rows(directory: Path) -> list[dict[str, Any]]:
    import pyarrow.parquet as pq

    rows: list[dict[str, Any]] = []
    for path in sorted(directory.glob('*.parquet')):
        rows.extend(pq.read_table(path).to_pylist())
    return rows


def _metadata(row: dict[str, Any]) -> dict[str, Any]:
    value = row.get('metadata_json') or '{}'
    if isinstance(value, dict):
        return value
    return json.loads(str(value))


def _mention_dir(index_dir: Path) -> Path:
    if (index_dir / 'chunk_mentions').is_dir():
        return index_dir / 'chunk_mentions'
    return index_dir / 'mentions'


def _norm_path(path: str) -> str:
    return str(path or '').replace('\\', '/').lstrip('./')


def _repo_relative_path(repo_id: str, rel_path: str) -> str:
    normalized = _norm_path(rel_path)
    prefix = f'{repo_id}/'
    if normalized.startswith(prefix):
        return normalized[len(prefix):]
    return normalized


def _path_terms(paths: list[str]) -> list[str]:
    terms: list[str] = []
    for path in paths:
        normalized = _norm_path(path)
        name = normalized.rsplit('/', 1)[-1]
        stem = name.rsplit('.', 1)[0]
        parts = [part for part in stem.replace('-', '_').split('_') if len(part) >= 3]
        terms.extend(part.lower() for part in parts)
        if len(stem) >= 3:
            terms.append(stem.lower())
    return terms


def _episode_query_terms(row: dict[str, Any], *, max_terms: int) -> list[str]:
    goal = str(row.get('goal') or '')
    symbols = ' '.join(str(item) for item in row.get('seed_symbols', []))
    paths = ' '.join(str(item) for item in row.get('seed_paths', []))
    tests = ' '.join(str(item) for item in row.get('selected_tests', []))
    local_seed_text = '\n'.join(
        str(context_row.get('text') or '')[:3000]
        for context_row in row.get('context_rows', [])
        if str(context_row.get('role') or '') in {'seed_change', 'repo_graph_neighbor', 'verification_constraint'}
    )
    text = '\n'.join(part for part in [goal, symbols, paths, tests, local_seed_text] if part)
    terms = extract_terms(text, max_terms=max_terms * 3)
    compounds = extract_compound_terms(text, max_terms=max_terms * 2)
    combined: list[str] = []
    seen: set[str] = set()
    for term in list(row.get('seed_symbols', [])) + compounds + _path_terms(list(row.get('seed_paths', []))) + terms:
        value = str(term or '').strip().lower()
        if len(value) < 3 or value in seen or value in GENERIC_QUERY_TERMS:
            continue
        seen.add(value)
        combined.append(value)
        if len(combined) >= max_terms:
            break
    return combined


def _run_git(args: list[str], *, repo_root: Path) -> str:
    result = subprocess.run(
        ['git', '-C', str(repo_root), *args],
        check=False,
        capture_output=True,
        text=True,
        encoding='utf-8',
        errors='ignore',
    )
    if result.returncode != 0:
        return ''
    return result.stdout


def _chunk_row_from_git(*, repo_id: str, rel_path: str, commit_sha: str, commit_ts: str, subject: str, text: str, score: float) -> dict[str, Any]:
    return {
        'chunk_id': stable_id('extgit', repo_id, rel_path, commit_sha),
        'source_type': 'external_git_commit',
        'source_id': repo_id,
        'doc_id': f'{commit_sha}:{rel_path}',
        'path': rel_path,
        'chunk_index': 0,
        'token_count': max(1, len(text.split())),
        'text': text,
        'role': 'external_commit_analogue',
        'retrieval_reason': f'external_git_history|{repo_id}|{rel_path}|{commit_sha[:12]}',
        'distance_from_seed': 2,
        'retrieval_score': float(score),
        'metadata': {
            'commit_sha': commit_sha,
            'commit_unix_ts': commit_ts,
            'commit_subject': subject,
        },
    }


def _dedupe_context_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_chunk_id: dict[str, dict[str, Any]] = {}
    for row in rows:
        chunk_id = str(row.get('chunk_id') or '')
        current = by_chunk_id.get(chunk_id)
        if current is None:
            by_chunk_id[chunk_id] = row
            continue
        current_score = (int(current.get('distance_from_seed') or 0), -float(current.get('retrieval_score') or 0.0))
        new_score = (int(row.get('distance_from_seed') or 0), -float(row.get('retrieval_score') or 0.0))
        if new_score < current_score:
            by_chunk_id[chunk_id] = row
    return sorted(
        by_chunk_id.values(),
        key=lambda row: (
            int(row.get('distance_from_seed') or 0),
            str(row.get('role') or ''),
            str(row.get('source_type') or ''),
            str(row.get('source_id') or ''),
            str(row.get('path') or ''),
            str(row.get('chunk_id') or ''),
        ),
    )


def _select_external_repo_paths(
    *,
    query_terms: list[str],
    inverted_mentions: dict[str, list[dict[str, Any]]],
    chunk_by_id: dict[str, dict[str, Any]],
    external_repo_root: Path,
    max_term_docfreq: int,
    max_external_repos: int,
    max_paths_per_repo: int,
) -> list[tuple[str, str, float]]:
    repo_scores: dict[str, float] = defaultdict(float)
    repo_path_scores: dict[tuple[str, str], float] = defaultdict(float)
    for term in query_terms:
        hits = inverted_mentions.get(term, [])
        if not hits or len(hits) > max_term_docfreq:
            continue
        weight = 1.0 / max(1.0, len(hits) ** 0.5)
        for hit in hits:
            if str(hit.get('source_type') or '') != 'repo':
                continue
            chunk = chunk_by_id.get(str(hit.get('chunk_id') or ''))
            if not chunk:
                continue
            repo_id = str(hit.get('source_id') or '')
            repo_root = external_repo_root / repo_id
            if not repo_id or not repo_root.exists() or not (repo_root / '.git').exists():
                continue
            metadata = _metadata(chunk)
            rel_path = _repo_relative_path(repo_id, str(metadata.get('path') or ''))
            if not rel_path:
                continue
            repo_scores[repo_id] += weight
            repo_path_scores[(repo_id, rel_path)] += weight
    ranked_repos = [repo_id for repo_id, _ in sorted(repo_scores.items(), key=lambda item: (-item[1], item[0]))[:max_external_repos]]
    selected: list[tuple[str, str, float]] = []
    for repo_id in ranked_repos:
        candidates = [
            (rel_path, score)
            for (candidate_repo_id, rel_path), score in repo_path_scores.items()
            if candidate_repo_id == repo_id
        ]
        candidates.sort(key=lambda item: (-item[1], item[0]))
        for rel_path, score in candidates[:max_paths_per_repo]:
            selected.append((repo_id, rel_path, float(score)))
    return selected


def _history_rows_for_external_path(
    *,
    external_repo_root: Path,
    repo_id: str,
    rel_path: str,
    base_score: float,
    max_commits_per_path: int,
    max_chars_per_commit: int,
) -> list[dict[str, Any]]:
    repo_root = external_repo_root / repo_id
    log_text = _run_git(
        ['log', f'--max-count={max_commits_per_path}', '--format=%H\t%ct\t%s', '--', rel_path],
        repo_root=repo_root,
    )
    out: list[dict[str, Any]] = []
    for line in log_text.splitlines():
        if not line.strip():
            continue
        parts = line.split('\t', 2)
        if len(parts) != 3:
            continue
        commit_sha, commit_ts, subject = parts
        show_text = _run_git(
            ['show', '--stat', '--summary', '--unified=0', '--format=medium', commit_sha, '--', rel_path],
            repo_root=repo_root,
        )[:max_chars_per_commit]
        if not show_text.strip():
            continue
        text = '\n'.join(
            [
                f'external_repo_id: {repo_id}',
                f'commit_sha: {commit_sha}',
                f'commit_unix_ts: {commit_ts}',
                f'commit_subject: {subject}',
                f'path: {rel_path}',
                '',
                show_text.strip(),
            ]
        )
        out.append(
            _chunk_row_from_git(
                repo_id=repo_id,
                rel_path=rel_path,
                commit_sha=commit_sha,
                commit_ts=commit_ts,
                subject=subject,
                text=text,
                score=base_score,
            )
        )
    return out


def augment_session_episode_with_external_repo_git_history(
    *,
    episodes_path: Path,
    index_dir: Path,
    external_repo_root: Path,
    max_query_terms: int = 32,
    max_term_docfreq: int = 2500,
    max_external_repos: int = 8,
    max_paths_per_repo: int = 4,
    max_commits_per_path: int = 6,
    max_chars_per_commit: int = 12000,
    max_external_commit_rows: int = 128,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    episodes = [json.loads(line) for line in episodes_path.read_text(encoding='utf-8').splitlines() if line.strip()]
    chunk_rows = _read_parquet_rows(index_dir / 'chunks')
    mention_rows = _read_parquet_rows(_mention_dir(index_dir))
    chunk_by_id = {str(row.get('chunk_id') or ''): row for row in chunk_rows}
    inverted_mentions: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in mention_rows:
        term = str(row.get('term') or '').strip().lower()
        chunk_id = str(row.get('chunk_id') or '')
        if not term or not chunk_id or chunk_id not in chunk_by_id:
            continue
        inverted_mentions[term].append(row)

    augmented_rows: list[dict[str, Any]] = []
    role_counts: Counter[str] = Counter()
    added_row_counts: list[int] = []
    added_token_counts: list[int] = []
    history_cache: dict[tuple[str, str], list[dict[str, Any]]] = {}

    for row in episodes:
        query_terms = _episode_query_terms(row, max_terms=max_query_terms)
        selected_paths = _select_external_repo_paths(
            query_terms=query_terms,
            inverted_mentions=inverted_mentions,
            chunk_by_id=chunk_by_id,
            external_repo_root=external_repo_root,
            max_term_docfreq=max_term_docfreq,
            max_external_repos=max_external_repos,
            max_paths_per_repo=max_paths_per_repo,
        )
        external_rows: list[dict[str, Any]] = []
        for repo_id, rel_path, score in selected_paths:
            cache_key = (repo_id, rel_path)
            cached_rows = history_cache.get(cache_key)
            if cached_rows is None:
                cached_rows = _history_rows_for_external_path(
                    external_repo_root=external_repo_root,
                    repo_id=repo_id,
                    rel_path=rel_path,
                    base_score=score,
                    max_commits_per_path=max_commits_per_path,
                    max_chars_per_commit=max_chars_per_commit,
                )
                history_cache[cache_key] = [dict(item) for item in cached_rows]
            external_rows.extend([dict(item, retrieval_score=float(score)) for item in cached_rows])
        external_rows = external_rows[:max_external_commit_rows]
        merged_context = _dedupe_context_rows(list(row.get('context_rows') or []) + external_rows)
        context_role_counts = dict(sorted(Counter(str(context_row.get('role') or '') for context_row in merged_context).items()))
        augmented = dict(row)
        augmented['episode_id'] = stable_id(str(row.get('episode_id') or 'extgitaug'), 'extgithist', str(max_external_repos), str(max_external_commit_rows))
        augmented['context_rows'] = merged_context
        augmented['context_token_count'] = sum(int(context_row.get('token_count') or 0) for context_row in merged_context)
        augmented['context_role_counts'] = context_role_counts
        augmented['external_git_history_augmentation_metadata'] = {
            'query_terms': query_terms,
            'selected_repo_paths': [{'repo_id': repo_id, 'path': rel_path, 'score': score} for repo_id, rel_path, score in selected_paths],
            'added_external_commit_rows': len(external_rows),
            'added_external_commit_tokens': sum(int(context_row.get('token_count') or 0) for context_row in external_rows),
        }
        for context_row in external_rows:
            role_counts[str(context_row.get('role') or '')] += 1
        added_row_counts.append(len(external_rows))
        added_token_counts.append(sum(int(context_row.get('token_count') or 0) for context_row in external_rows))
        augmented_rows.append(augmented)

    summary = {
        'episode_count': len(episodes),
        'augmented_episode_count': len(augmented_rows),
        'avg_added_external_commit_rows': (sum(added_row_counts) / len(added_row_counts)) if added_row_counts else 0.0,
        'avg_added_external_commit_tokens': (sum(added_token_counts) / len(added_token_counts)) if added_token_counts else 0.0,
        'max_added_external_commit_tokens': max(added_token_counts) if added_token_counts else 0,
        'role_counts': dict(sorted(role_counts.items())),
    }
    return augmented_rows, summary


def main() -> None:
    parser = argparse.ArgumentParser(description='Augment session-derived episodes with external repository git history selected from the sparse mention index.')
    parser.add_argument('--episodes', type=Path, required=True)
    parser.add_argument('--index-dir', type=Path, required=True)
    parser.add_argument('--external-repo-root', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--summary-output', type=Path)
    parser.add_argument('--max-query-terms', type=int, default=32)
    parser.add_argument('--max-term-docfreq', type=int, default=2500)
    parser.add_argument('--max-external-repos', type=int, default=8)
    parser.add_argument('--max-paths-per-repo', type=int, default=4)
    parser.add_argument('--max-commits-per-path', type=int, default=6)
    parser.add_argument('--max-chars-per-commit', type=int, default=12000)
    parser.add_argument('--max-external-commit-rows', type=int, default=128)
    args = parser.parse_args()
    rows, summary = augment_session_episode_with_external_repo_git_history(
        episodes_path=args.episodes,
        index_dir=args.index_dir,
        external_repo_root=args.external_repo_root,
        max_query_terms=args.max_query_terms,
        max_term_docfreq=args.max_term_docfreq,
        max_external_repos=args.max_external_repos,
        max_paths_per_repo=args.max_paths_per_repo,
        max_commits_per_path=args.max_commits_per_path,
        max_chars_per_commit=args.max_chars_per_commit,
        max_external_commit_rows=args.max_external_commit_rows,
    )
    write_jsonl(args.output, rows)
    write_json(args.summary_output or args.output.with_name('augmented_session_episode_external_git_history_summary.json'), summary)


if __name__ == '__main__':
    main()
