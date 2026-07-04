from __future__ import annotations

import argparse
import shutil
from pathlib import Path

from safe_paths import UnsafePathError, build_safe_cleanup_plan


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description='Safely clean temporary checkpoint children for a bounded probe output directory.')
    parser.add_argument('--repo-root', required=True, type=Path)
    parser.add_argument('--output-dir', required=True, type=Path)
    parser.add_argument('--run-id', required=True)
    parser.add_argument('--dry-run', action='store_true')
    return parser.parse_args()


def safe_cleanup_checkpoints(*, repo_root: Path, output_dir: Path, run_id: str, dry_run: bool = False) -> dict[str, object]:
    plan = build_safe_cleanup_plan(repo_root=repo_root, output_dir=output_dir, run_id=run_id)
    removed: list[str] = []
    for child in plan.deletable_children:
        removed.append(str(child))
        if dry_run:
            continue
        if child.is_dir():
            shutil.rmtree(child)
        elif child.exists():
            child.unlink()
    return {
        'repo_root': str(plan.repo_root),
        'output_dir': str(plan.output_dir),
        'checkpoint_dir': str(plan.checkpoint_dir),
        'marker_file': str(plan.marker_file),
        'run_id': plan.run_id,
        'dry_run': dry_run,
        'removed': removed,
        'removed_count': len(removed),
    }


def main() -> None:
    args = parse_args()
    try:
        result = safe_cleanup_checkpoints(repo_root=args.repo_root, output_dir=args.output_dir, run_id=args.run_id, dry_run=args.dry_run)
    except UnsafePathError as exc:
        raise SystemExit(f'unsafe cleanup refused: {exc}') from exc
    import json
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == '__main__':
    main()
