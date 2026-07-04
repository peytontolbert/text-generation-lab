from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = ROOT / "configs/software_maintainer/shared_feature_normalizer_stage8664.json"


def load_aliases(path: Path = DEFAULT_CONFIG) -> dict[str, list[str]]:
    data = json.loads(path.read_text())
    aliases = data.get("aliases")
    if not isinstance(aliases, dict):
        raise ValueError(f"missing aliases in {path}")
    return {str(key): [str(item) for item in value] for key, value in aliases.items()}


def _walk_path(value: Any, parts: list[str]) -> list[Any]:
    if not parts:
        return [value]
    part = parts[0]
    rest = parts[1:]
    if part.endswith("[]"):
        key = part[:-2]
        if not isinstance(value, dict):
            return []
        seq = value.get(key)
        if not isinstance(seq, list):
            return []
        out: list[Any] = []
        for item in seq:
            out.extend(_walk_path(item, rest))
        return out
    if not isinstance(value, dict) or part not in value:
        return []
    return _walk_path(value[part], rest)


def extract_alias_values(row: dict[str, Any], alias_paths: list[str]) -> list[Any]:
    values: list[Any] = []
    for alias_path in alias_paths:
        values.extend(_walk_path(row, alias_path.split(".")))
    return values


def normalize_features(row: dict[str, Any], aliases: dict[str, list[str]] | None = None) -> dict[str, Any]:
    aliases = aliases or load_aliases()
    normalized: dict[str, Any] = {}
    for canonical, paths in aliases.items():
        values = extract_alias_values(row, paths)
        if not values:
            continue
        normalized[canonical] = values[0] if len(values) == 1 else values
    return normalized


def normalize_manifest_rows(rows: list[dict[str, Any]], aliases: dict[str, list[str]] | None = None) -> list[dict[str, Any]]:
    aliases = aliases or load_aliases()
    return [{"row_id": row.get("row_id") or row.get("id") or "", "normalized_features": normalize_features(row, aliases)} for row in rows]
