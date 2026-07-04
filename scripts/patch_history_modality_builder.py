from __future__ import annotations

import json
import re
from dataclasses import dataclass, asdict
from hashlib import sha256
from typing import Any

FILE_RE = re.compile(r'^diff --git a/(?P<old>\S+) b/(?P<new>\S+)')
HUNK_RE = re.compile(r'^@@ -(?P<old_start>\d+)(?:,(?P<old_count>\d+))? \+(?P<new_start>\d+)(?:,(?P<new_count>\d+))? @@(?P<header>.*)$')
SYMBOL_RE = re.compile(r'\b(def|class|function|fn|impl|struct|interface)\s+([A-Za-z_][\w]*)')


@dataclass(frozen=True)
class PatchHistoryPacket:
    patch_id: str
    files: list[dict[str, Any]]
    hunks: list[dict[str, Any]]
    changed_symbols: list[str]
    stats: dict[str, int]
    failures: list[str]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def build_patch_history_packet(diff_text: str, *, row_id: str = 'row') -> dict[str, Any]:
    text = str(diff_text or '')
    patch_id = 'patch_' + sha256((row_id + '\n' + text).encode('utf-8')).hexdigest()[:16]
    files: list[dict[str, Any]] = []
    hunks: list[dict[str, Any]] = []
    current_file: str | None = None
    additions = deletions = 0
    changed_symbols: set[str] = set()
    for line in text.splitlines():
        file_match = FILE_RE.match(line)
        if file_match:
            current_file = file_match.group('new')
            files.append({'path': current_file, 'old_path': file_match.group('old'), 'file_id': 'file_' + sha256(f'{patch_id}:{current_file}'.encode('utf-8')).hexdigest()[:16]})
            continue
        hunk_match = HUNK_RE.match(line)
        if hunk_match:
            hunks.append({
                'hunk_id': 'hunk_' + sha256(f'{patch_id}:{current_file}:{line}'.encode('utf-8')).hexdigest()[:16],
                'path': current_file,
                'old_start': int(hunk_match.group('old_start')),
                'old_count': int(hunk_match.group('old_count') or 1),
                'new_start': int(hunk_match.group('new_start')),
                'new_count': int(hunk_match.group('new_count') or 1),
                'header': hunk_match.group('header').strip(),
            })
            continue
        if line.startswith('+') and not line.startswith('+++'):
            additions += 1
            for _, symbol in SYMBOL_RE.findall(line):
                changed_symbols.add(symbol)
        elif line.startswith('-') and not line.startswith('---'):
            deletions += 1
            for _, symbol in SYMBOL_RE.findall(line):
                changed_symbols.add(symbol)
    failures = [] if files or hunks or text.strip() else ['empty_patch']
    return PatchHistoryPacket(
        patch_id=patch_id,
        files=files,
        hunks=hunks,
        changed_symbols=sorted(changed_symbols),
        stats={'files_changed': len(files), 'hunks': len(hunks), 'additions': additions, 'deletions': deletions},
        failures=failures,
    ).to_dict()


def main() -> None:
    import argparse
    from pathlib import Path
    parser = argparse.ArgumentParser(description='Build no-authority patch history modality packets from unified diffs.')
    parser.add_argument('input', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    rows = [json.loads(line) for line in args.input.read_text(encoding='utf-8').splitlines() if line.strip()]
    packets = [build_patch_history_packet(str(row.get('diff') or row.get('patch') or row.get('text') or ''), row_id=str(row.get('row_id') or row.get('id') or 'row')) for row in rows]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(''.join(json.dumps(packet, sort_keys=True) + '\n' for packet in packets), encoding='utf-8')


if __name__ == '__main__':
    main()
