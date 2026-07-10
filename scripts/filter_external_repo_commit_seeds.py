from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

from long_context_common import write_json, write_jsonl

CODE_SUFFIXES = {'.py', '.ts', '.tsx', '.js', '.jsx', '.java', '.go', '.rs', '.c', '.cc', '.cpp', '.h', '.hpp', '.sh'}
WEAK_PATH_MARKERS = ('/translations/', '/translation/', '/locale/', '/locales/', '/i18n/', '/docs/', '/doc/', '/years/')
WEAK_FILENAMES = {'readme.md', 'readme-zh.md', 'summary.md', '.co-op-translator.json'}
WEAK_GOAL_MARKERS = ('update readme', 'newsletter sync', 'sync translations', 're-sort', 'update:', 'update ', 'chore(i18n)')


def _is_code_path(path: str) -> bool:
    return Path(str(path or '')).suffix.lower() in CODE_SUFFIXES


def _is_weak_path(path: str) -> bool:
    lower = str(path or '').replace('\\', '/').lower()
    name = lower.rsplit('/', 1)[-1]
    if any(marker in lower for marker in WEAK_PATH_MARKERS):
        return True
    return name in WEAK_FILENAMES


def _keep_seed(row: dict[str, Any]) -> tuple[bool, str]:
    goal = str(row.get('goal') or '').strip().lower()
    changes = [dict(item) for item in row.get('changes', []) if isinstance(item, dict)]
    if not changes:
        return False, 'SKIP_NO_CHANGES'
    code_paths = [str(item.get('path') or '') for item in changes if _is_code_path(str(item.get('path') or ''))]
    if not code_paths:
        return False, 'SKIP_NO_CODE_PATHS'
    weak_paths = sum(int(_is_weak_path(str(item.get('path') or ''))) for item in changes)
    if weak_paths == len(changes):
        return False, 'SKIP_ALL_WEAK_PATHS'
    if any(marker in goal for marker in WEAK_GOAL_MARKERS) and len(code_paths) < 2:
        return False, 'SKIP_WEAK_GOAL_LOW_CODE'
    return True, 'KEEP_CODE_HEAVY'


def filter_external_repo_commit_seeds(seeds_path: Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    rows = [json.loads(line) for line in seeds_path.read_text(encoding='utf-8').splitlines() if line.strip()]
    kept: list[dict[str, Any]] = []
    route_counts: Counter[str] = Counter()
    for row in rows:
        keep, route = _keep_seed(row)
        route_counts[route] += 1
        if keep:
            kept.append(row)
    summary = {
        'input_seed_count': len(rows),
        'kept_seed_count': len(kept),
        'route_counts': dict(sorted(route_counts.items())),
    }
    return kept, summary


def main() -> None:
    parser = argparse.ArgumentParser(description='Filter external repo commit seeds down to code-heavy software transitions.')
    parser.add_argument('--seeds', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--summary-output', type=Path)
    args = parser.parse_args()
    rows, summary = filter_external_repo_commit_seeds(args.seeds)
    write_jsonl(args.output, rows)
    write_json(args.summary_output or args.output.with_name('filtered_external_repo_commit_seed_summary.json'), summary)


if __name__ == '__main__':
    main()
