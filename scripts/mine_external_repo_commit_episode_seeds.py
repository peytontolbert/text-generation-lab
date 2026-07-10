from __future__ import annotations

import argparse
import json
import subprocess
from collections import Counter
from pathlib import Path
from typing import Any

from long_context_common import stable_id, write_json, write_jsonl

TEXT_CODE_SUFFIXES = {
    '.py', '.md', '.txt', '.rst', '.json', '.jsonl', '.yaml', '.yml', '.toml', '.cfg', '.ini',
    '.ts', '.tsx', '.js', '.jsx', '.java', '.go', '.rs', '.c', '.cc', '.cpp', '.h', '.hpp', '.sh',
}
SKIP_PATH_MARKERS = ('/dist/', '/build/', '/coverage/', '/vendor/', '/node_modules/', '/.git/')
SKIP_FILENAMES = {'package-lock.json', 'pnpm-lock.yaml', 'yarn.lock', 'poetry.lock', 'cargo.lock'}


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


def _keep_path(path: str) -> bool:
    normalized = str(path or '').replace('\\', '/').lstrip('./')
    if not normalized:
        return False
    lower = normalized.lower()
    if any(marker in lower for marker in SKIP_PATH_MARKERS):
        return False
    name = lower.rsplit('/', 1)[-1]
    if name in SKIP_FILENAMES:
        return False
    return Path(normalized).suffix.lower() in TEXT_CODE_SUFFIXES


def _commit_changed_paths(repo_root: Path, commit_sha: str, *, max_files_per_commit: int) -> list[str]:
    output = _run_git(['show', '--name-only', '--format=', commit_sha], repo_root=repo_root)
    out: list[str] = []
    seen: set[str] = set()
    for line in output.splitlines():
        path = str(line or '').strip()
        if not _keep_path(path):
            continue
        normalized = path.replace('\\', '/').lstrip('./')
        if normalized in seen:
            continue
        seen.add(normalized)
        out.append(normalized)
        if len(out) >= max_files_per_commit:
            break
    return out


def _commit_symbol_hint(repo_root: Path, rel_path: str) -> str:
    stem = Path(rel_path).stem
    if stem.startswith('test_'):
        stem = stem[5:]
    return stem if len(stem) >= 3 else ''


def _repo_commits(repo_root: Path, *, max_commits_per_repo: int) -> list[tuple[str, str, str]]:
    output = _run_git(
        ['log', f'--max-count={max_commits_per_repo}', '--format=%H\t%ct\t%s'],
        repo_root=repo_root,
    )
    out: list[tuple[str, str, str]] = []
    for line in output.splitlines():
        if not line.strip():
            continue
        parts = line.split('\t', 2)
        if len(parts) != 3:
            continue
        out.append((parts[0], parts[1], parts[2]))
    return out


def mine_external_repo_commit_episode_seeds(
    *,
    repo_root: Path,
    max_repos: int,
    max_commits_per_repo: int,
    max_files_per_commit: int,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    repos = [path for path in sorted(repo_root.iterdir()) if path.is_dir() and (path / '.git').exists()]
    seeds: list[dict[str, Any]] = []
    route_counts: Counter[str] = Counter()
    repos_seen = 0

    for repo_path in repos[:max_repos]:
        repo_id = repo_path.name
        repos_seen += 1
        commits = _repo_commits(repo_path, max_commits_per_repo=max_commits_per_repo)
        for commit_sha, commit_ts, subject in commits:
            changed_paths = _commit_changed_paths(repo_path, commit_sha, max_files_per_commit=max_files_per_commit)
            if not changed_paths:
                route_counts['SKIP_NO_TEXT_CODE_PATHS'] += 1
                continue
            changes = []
            for rel_path in changed_paths:
                symbol = _commit_symbol_hint(repo_path, rel_path)
                row = {'path': f'{repo_id}/{rel_path}'}
                if symbol:
                    row['symbol'] = symbol
                changes.append(row)
            seed_id = stable_id('extcommitseed', repo_id, commit_sha, '|'.join(changed_paths))
            seeds.append(
                {
                    'seed_id': seed_id,
                    'seed_type': 'external_repo_commit',
                    'repo_id': repo_id,
                    'goal': subject,
                    'changes': changes,
                    'target': {
                        'expected_patch_summary': subject,
                        'expected_outcome': 'commit_applied',
                        'state_after': {},
                    },
                    'metadata': {
                        'commit_sha': commit_sha,
                        'commit_unix_ts': commit_ts,
                        'commit_subject': subject,
                        'repo_root': str(repo_path),
                    },
                }
            )
            route_counts['EMIT_COMMIT_SEED'] += 1

    summary = {
        'repos_considered': min(len(repos), max_repos),
        'repos_with_git': len(repos),
        'seed_count': len(seeds),
        'route_counts': dict(sorted(route_counts.items())),
        'max_commits_per_repo': int(max_commits_per_repo),
        'max_files_per_commit': int(max_files_per_commit),
    }
    return seeds, summary


def main() -> None:
    parser = argparse.ArgumentParser(description='Mine commit-derived episode seeds from external git repositories.')
    parser.add_argument('--repo-root', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--summary-output', type=Path)
    parser.add_argument('--max-repos', type=int, default=64)
    parser.add_argument('--max-commits-per-repo', type=int, default=3)
    parser.add_argument('--max-files-per-commit', type=int, default=6)
    args = parser.parse_args()
    rows, summary = mine_external_repo_commit_episode_seeds(
        repo_root=args.repo_root,
        max_repos=args.max_repos,
        max_commits_per_repo=args.max_commits_per_repo,
        max_files_per_commit=args.max_files_per_commit,
    )
    write_jsonl(args.output, rows)
    write_json(args.summary_output or args.output.with_name('external_repo_commit_episode_seed_summary.json'), summary)


if __name__ == '__main__':
    main()
