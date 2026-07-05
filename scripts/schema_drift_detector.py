from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

DEFAULT_ALLOWED_SPLITS = {"train", "eval", "strict", "strict_eval", "dev_failure_mining", "locked_regression", "hidden_final"}


def normalize_key(key: str, aliases: dict[str, str]) -> str:
    return aliases.get(key, key)


def normalize_row_keys(row: dict[str, Any], aliases: dict[str, str]) -> tuple[dict[str, Any], dict[str, str]]:
    out: dict[str, Any] = {}
    used: dict[str, str] = {}
    for key, value in row.items():
        canonical = normalize_key(str(key), aliases)
        if canonical in out and canonical != key:
            # Keep first value stable; collision is reported separately by audit_row.
            used[str(key)] = canonical
            continue
        out[canonical] = value
        if canonical != key:
            used[str(key)] = canonical
    return out, used


def type_name(value: Any) -> str:
    if isinstance(value, bool):
        return "bool"
    if isinstance(value, int) and not isinstance(value, bool):
        return "int"
    if isinstance(value, float):
        return "float"
    if isinstance(value, str):
        return "str"
    if isinstance(value, list):
        return "list"
    if isinstance(value, dict):
        return "dict"
    if value is None:
        return "null"
    return type(value).__name__


def type_ok(value: Any, expected: str | list[str]) -> bool:
    expected_types = {expected} if isinstance(expected, str) else set(expected)
    return type_name(value) in expected_types


def audit_row(row: dict[str, Any], schema: dict[str, Any], *, index: int = 0) -> dict[str, Any]:
    aliases = {str(k): str(v) for k, v in schema.get("aliases", {}).items()}
    normalized, aliases_used = normalize_row_keys(row, aliases)
    required = set(schema.get("required_fields", []))
    optional = set(schema.get("optional_fields", []))
    forbidden = set(schema.get("forbidden_fields", []))
    typed = schema.get("typed_fields", {}) if isinstance(schema.get("typed_fields"), dict) else {}
    allow_unknown = bool(schema.get("allow_unknown_fields", False))
    allowed_fields = required | optional | set(typed) | {"row_id"}
    missing_required = sorted(field for field in required if field not in normalized)
    forbidden_present = sorted(field for field in forbidden if field in normalized)
    unknown_fields = [] if allow_unknown else sorted(field for field in normalized if field not in allowed_fields and field not in forbidden)
    type_mismatches = []
    for field, expected in typed.items():
        if field in normalized and not type_ok(normalized[field], expected):
            type_mismatches.append({"field": field, "expected": expected, "actual": type_name(normalized[field])})
    alias_collisions = []
    reverse: dict[str, list[str]] = {}
    for key in row:
        reverse.setdefault(normalize_key(str(key), aliases), []).append(str(key))
    for canonical, keys in reverse.items():
        if len(keys) > 1:
            alias_collisions.append({"canonical": canonical, "keys": sorted(keys)})
    split = str(normalized.get("split", ""))
    split_invalid = bool(split and split not in set(schema.get("allowed_splits", DEFAULT_ALLOWED_SPLITS)))
    failures = []
    if missing_required:
        failures.append("missing_required_fields")
    if forbidden_present:
        failures.append("forbidden_fields_present")
    if unknown_fields:
        failures.append("unknown_fields_present")
    if type_mismatches:
        failures.append("type_mismatches")
    if alias_collisions:
        failures.append("alias_collisions")
    if split_invalid:
        failures.append("invalid_split")
    if forbidden_present or alias_collisions or type_mismatches or split_invalid:
        route = "BLOCK_SCHEMA_DRIFT"
    elif missing_required or unknown_fields:
        route = "HOLD_SCHEMA_REVIEW"
    else:
        route = "PASS_SCHEMA_STABLE"
    return {
        "row_id": str(row.get("row_id") or row.get("id") or f"row_{index}"),
        "schema_drift_route": route,
        "blocked": route == "BLOCK_SCHEMA_DRIFT",
        "needs_review": route == "HOLD_SCHEMA_REVIEW",
        "missing_required_fields": missing_required,
        "forbidden_fields_present": forbidden_present,
        "unknown_fields_present": unknown_fields,
        "type_mismatches": type_mismatches,
        "aliases_used": aliases_used,
        "alias_collisions": alias_collisions,
        "split_invalid": split_invalid,
        "failures": failures,
    }


def audit_rows(rows: list[dict[str, Any]], schema: dict[str, Any]) -> dict[str, Any]:
    records = [audit_row(row, schema, index=index) for index, row in enumerate(rows)]
    route_counts = Counter(record["schema_drift_route"] for record in records)
    failure_counts: Counter[str] = Counter()
    for record in records:
        failure_counts.update(record["failures"])
    return {
        "rows": len(rows),
        "records": records,
        "metrics": {
            "rows": len(rows),
            "blocked_rows": sum(int(record["blocked"]) for record in records),
            "review_rows": sum(int(record["needs_review"]) for record in records),
            "pass_rows": sum(int(record["schema_drift_route"] == "PASS_SCHEMA_STABLE") for record in records),
            "route_counts": dict(route_counts),
            "failure_counts": dict(failure_counts),
        },
    }


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit row manifests for schema drift, alias collisions, forbidden fields, and type mismatches.")
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--schema", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()
    card = audit_rows(read_jsonl(args.manifest), json.loads(args.schema.read_text(encoding="utf-8")))
    text = json.dumps(card, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
    print(text, end="")


if __name__ == "__main__":
    main()
