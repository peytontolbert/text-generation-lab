from __future__ import annotations

from pathlib import Path
from typing import Any
import argparse
import json

from stage_summary_schema import AUTHORITY_KEYS, normalize_authority, read_summary


class AuthorityGateError(ValueError):
    pass


def authority_counts(rows: list[dict[str, Any]]) -> dict[str, int]:
    counts = {key: 0 for key in AUTHORITY_KEYS}
    for row in rows:
        auth = normalize_authority(row)
        for key, value in auth.items():
            counts[key] += int(bool(value))
    return counts


def assert_authority_closed(payload: dict[str, Any], *, allowed: set[str] | None = None) -> None:
    allowed = allowed or set()
    auth = normalize_authority(payload)
    open_forbidden = [key for key, value in auth.items() if value and key not in allowed]
    if open_forbidden:
        raise AuthorityGateError(f"forbidden authority opened: {open_forbidden}")


def summarize_paths(paths: list[Path]) -> dict[str, Any]:
    rows = [read_summary(path) for path in paths]
    counts = authority_counts(rows)
    return {
        "summary_count": len(rows),
        "authority_counts": counts,
        "all_closed": all(value == 0 for value in counts.values()),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Check authority flags across stage summaries.")
    parser.add_argument("paths", nargs="*", type=Path)
    parser.add_argument("--summaries-dir", type=Path, default=Path("runs/summaries"))
    parser.add_argument("--require-closed", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    paths = args.paths or sorted(args.summaries_dir.rglob("*.json"))
    card = summarize_paths(paths)
    if args.require_closed and not card["all_closed"]:
        raise SystemExit(json.dumps(card, indent=2, sort_keys=True))
    print(json.dumps(card, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
