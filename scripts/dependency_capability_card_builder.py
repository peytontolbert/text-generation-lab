from __future__ import annotations

import json
from dataclasses import dataclass, asdict
from hashlib import sha256
from typing import Any


@dataclass(frozen=True)
class DependencyCapabilityCard:
    dependency_id: str
    name: str
    version: str | None
    language_family: str
    allowed_import: bool
    blocked_import: bool
    exports: list[str]
    common_errors: list[str]
    usage_patterns: list[str]
    adapter_requirements: list[str]
    verifier_requirements: list[str]
    failures: list[str]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _as_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item) for item in value if str(item).strip()]
    if isinstance(value, str):
        return [part.strip() for part in value.split(',') if part.strip()]
    return [str(value)]


def build_dependency_capability_card(row: dict[str, Any]) -> dict[str, Any]:
    name = str(row.get('name') or row.get('package') or row.get('repo_name') or '').strip()
    version = row.get('version') or row.get('package_version')
    language = str(row.get('language_family') or row.get('language') or 'unknown')
    allowed = bool(row.get('allowed_import', row.get('allowed', False)))
    blocked = bool(row.get('blocked_import', row.get('blocked', False)))
    exports = sorted(set(_as_list(row.get('exports') or row.get('symbols') or row.get('public_apis'))))
    common_errors = sorted(set(_as_list(row.get('common_errors') or row.get('errors'))))
    usage_patterns = sorted(set(_as_list(row.get('usage_patterns') or row.get('examples') or row.get('tasks'))))
    adapter_requirements = sorted(set(_as_list(row.get('adapter_requirements') or row.get('constraints'))))
    verifier_requirements = sorted(set(_as_list(row.get('verifier_requirements') or row.get('tests') or row.get('verification'))))
    failures: list[str] = []
    if not name:
        failures.append('missing_dependency_name')
    if allowed and blocked:
        failures.append('allowed_and_blocked_conflict')
    dependency_id = 'dep_card_' + sha256(json.dumps({'name': name, 'version': version, 'language': language}, sort_keys=True).encode('utf-8')).hexdigest()[:16]
    return DependencyCapabilityCard(dependency_id, name, str(version) if version is not None else None, language, allowed, blocked, exports, common_errors, usage_patterns, adapter_requirements, verifier_requirements, failures).to_dict()


def build_many(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [build_dependency_capability_card(row) for row in rows]


def main() -> None:
    import argparse
    from pathlib import Path
    parser = argparse.ArgumentParser(description='Build no-authority dependency capability cards from package/repo metadata rows.')
    parser.add_argument('input', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    rows = [json.loads(line) for line in args.input.read_text(encoding='utf-8').splitlines() if line.strip()]
    packets = build_many(rows)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(''.join(json.dumps(packet, sort_keys=True) + '\n' for packet in packets), encoding='utf-8')


if __name__ == '__main__':
    main()
