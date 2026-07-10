from __future__ import annotations

import argparse
import json
import subprocess
from collections import Counter
from pathlib import Path
from typing import Any

from long_context_common import stable_id, write_json, write_jsonl


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


def _history_rows_for_path(
    *,
    repo_root: Path,
    repo_id: str,
    rel_path: str,
    max_commits_per_path: int,
    max_chars_per_commit: int,
) -> list[dict[str, Any]]:
    log_text = _run_git(
        [
            'log',
            f'--max-count={max_commits_per_path}',
            '--format=%H\t%ct\t%s',
            '--',
            rel_path,
        ],
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
                f'commit_sha: {commit_sha}',
                f'commit_unix_ts: {commit_ts}',
                f'commit_subject: {subject}',
                f'path: {rel_path}',
                '',
                show_text.strip(),
            ]
        )
        out.append(
            {
                'chunk_id': stable_id('gitcommit', repo_id, rel_path, commit_sha),
                'source_type': 'git_commit',
                'source_id': repo_id,
                'doc_id': f'{commit_sha}:{rel_path}',
                'path': rel_path,
                'chunk_index': 0,
                'token_count': max(1, len(text.split())),
                'text': text,
                'role': 'commit_history_analogue',
                'retrieval_reason': f'git_history_for_path|{rel_path}|{commit_sha[:12]}',
                'distance_from_seed': 1,
                'retrieval_score': 1.0,
                'metadata': {
                    'commit_sha': commit_sha,
                    'commit_unix_ts': commit_ts,
                    'commit_subject': subject,
                },
            }
        )
    return out


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
            str(row.get('path') or ''),
            str(row.get('chunk_id') or ''),
        ),
    )


def augment_session_episode_with_git_history(
    *,
    episodes_path: Path,
    max_commits_per_path: int = 8,
    max_chars_per_commit: int = 12_000,
    max_commit_history_rows: int = 64,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    episodes = [json.loads(line) for line in episodes_path.read_text(encoding='utf-8').splitlines() if line.strip()]
    augmented_rows: list[dict[str, Any]] = []
    role_counts: Counter[str] = Counter()
    added_row_counts: list[int] = []
    added_token_counts: list[int] = []

    for row in episodes:
        repo_root = Path(str(row.get('local_repo_root') or ''))
        repo_id = str(row.get('repo_id') or repo_root.name)
        if not repo_root.exists() or not (repo_root / '.git').exists():
            augmented_rows.append(dict(row))
            added_row_counts.append(0)
            added_token_counts.append(0)
            continue
        commit_rows: list[dict[str, Any]] = []
        for rel_path in list(row.get('seed_paths') or []):
            value = str(rel_path or '').strip()
            if not value:
                continue
            commit_rows.extend(
                _history_rows_for_path(
                    repo_root=repo_root,
                    repo_id=repo_id,
                    rel_path=value,
                    max_commits_per_path=max_commits_per_path,
                    max_chars_per_commit=max_chars_per_commit,
                )
            )
        commit_rows = commit_rows[:max_commit_history_rows]
        merged_context = _dedupe_context_rows(list(row.get('context_rows') or []) + commit_rows)
        context_role_counts = dict(sorted(Counter(str(context_row.get('role') or '') for context_row in merged_context).items()))
        augmented = dict(row)
        augmented['episode_id'] = stable_id(str(row.get('episode_id') or 'gitaug'), 'githist', str(max_commits_per_path), str(max_commit_history_rows))
        augmented['context_rows'] = merged_context
        augmented['context_token_count'] = sum(int(context_row.get('token_count') or 0) for context_row in merged_context)
        augmented['context_role_counts'] = context_role_counts
        augmented['git_history_augmentation_metadata'] = {
            'max_commits_per_path': int(max_commits_per_path),
            'max_chars_per_commit': int(max_chars_per_commit),
            'added_commit_history_rows': len(commit_rows),
            'added_commit_history_tokens': sum(int(context_row.get('token_count') or 0) for context_row in commit_rows),
        }
        for context_row in commit_rows:
            role_counts[str(context_row.get('role') or '')] += 1
        added_row_counts.append(len(commit_rows))
        added_token_counts.append(sum(int(context_row.get('token_count') or 0) for context_row in commit_rows))
        augmented_rows.append(augmented)

    summary = {
        'episode_count': len(episodes),
        'augmented_episode_count': len(augmented_rows),
        'avg_added_commit_rows': (sum(added_row_counts) / len(added_row_counts)) if added_row_counts else 0.0,
        'avg_added_commit_tokens': (sum(added_token_counts) / len(added_token_counts)) if added_token_counts else 0.0,
        'max_added_commit_tokens': max(added_token_counts) if added_token_counts else 0,
        'role_counts': dict(sorted(role_counts.items())),
    }
    return augmented_rows, summary


def main() -> None:
    parser = argparse.ArgumentParser(description='Augment session-derived episodes with local git commit history for changed paths.')
    parser.add_argument('--episodes', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--summary-output', type=Path)
    parser.add_argument('--max-commits-per-path', type=int, default=8)
    parser.add_argument('--max-chars-per-commit', type=int, default=12000)
    parser.add_argument('--max-commit-history-rows', type=int, default=64)
    args = parser.parse_args()
    rows, summary = augment_session_episode_with_git_history(
        episodes_path=args.episodes,
        max_commits_per_path=args.max_commits_per_path,
        max_chars_per_commit=args.max_chars_per_commit,
        max_commit_history_rows=args.max_commit_history_rows,
    )
    write_jsonl(args.output, rows)
    write_json(args.summary_output or args.output.with_name('augmented_session_episode_git_history_summary.json'), summary)


if __name__ == '__main__':
    main()
