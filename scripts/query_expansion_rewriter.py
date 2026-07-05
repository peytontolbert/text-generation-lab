from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any, Mapping

TARGET_FIELD_NAMES = {
    "target_label",
    "label",
    "clean_label",
    "expected_label",
    "patch_operator",
    "answer",
    "target",
    "clean_state",
}
SAFE_HINT_FIELDS = ("intent", "symbol", "error", "api", "path", "language", "test_name")


def _text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, list):
        return " ".join(_text(item) for item in value)
    if isinstance(value, Mapping):
        return " ".join(_text(v) for v in value.values())
    return str(value)


def _tokens(text: str) -> list[str]:
    return [tok for tok in re.split(r"[^A-Za-z0-9_./:-]+", text.strip()) if tok]


def _has_forbidden_target_field(row: Mapping[str, Any]) -> bool:
    for key, value in row.items():
        if key in TARGET_FIELD_NAMES and value not in (None, "", {}, []):
            return True
    return False


def _dedupe_keep_order(items: list[str]) -> list[str]:
    out = []
    seen = set()
    for item in items:
        norm = " ".join(item.split())
        if not norm or norm.lower() in seen:
            continue
        seen.add(norm.lower())
        out.append(norm)
    return out


def expand_query(row: Mapping[str, Any], *, max_variants: int = 6) -> dict[str, Any]:
    source_bits = {field: bool(_text(row.get(field)).strip()) for field in SAFE_HINT_FIELDS}
    if _has_forbidden_target_field(row):
        return {
            "row_id": str(row.get("row_id", row.get("id", "unknown_row"))),
            "query_variants": [],
            "query_source_bits": source_bits,
            "expansion_reason": "blocked_target_field_visible",
            "query_expansion_route": "BLOCK_QUERY_EXPANSION_LEAK",
            "leak_or_target_rows": 1,
            "authority": {"training_authorized": False, "retrieval_execution_authorized": False, "promotion_ready": False},
        }
    intent = _text(row.get("intent") or row.get("query") or row.get("task"))
    symbol = _text(row.get("symbol"))
    error = _text(row.get("error") or row.get("failure"))
    api = _text(row.get("api"))
    path = _text(row.get("path"))
    language = _text(row.get("language"))
    test_name = _text(row.get("test_name"))
    variants = []
    if intent:
        variants.append(intent)
    if symbol:
        variants.append(f"{symbol} definition references")
        variants.append(f"{symbol} tests call sites")
    if error:
        err_tokens = " ".join(_tokens(error)[:8])
        variants.append(f"{err_tokens} root cause")
    if api:
        variants.append(f"{api} usage examples")
    if path:
        variants.append(f"{path} related tests")
    if language and (symbol or error):
        variants.append(f"{language} {symbol or error} fix")
    if test_name:
        variants.append(f"{test_name} failing test implementation")
    variants = _dedupe_keep_order(variants)[:max(1, max_variants)]
    route = "PASS_QUERY_EXPANSION" if variants else "HOLD_QUERY_EXPANSION_NO_HINTS"
    reason_parts = [field for field, present in source_bits.items() if present]
    return {
        "row_id": str(row.get("row_id", row.get("id", "unknown_row"))),
        "query_variants": variants,
        "query_source_bits": source_bits,
        "expansion_reason": "visible_hints:" + ",".join(reason_parts) if reason_parts else "no_visible_hints",
        "query_expansion_route": route,
        "leak_or_target_rows": 0,
        "authority": {"training_authorized": False, "retrieval_execution_authorized": False, "promotion_ready": False},
    }


def query_expansion_card(rows: list[Mapping[str, Any]]) -> dict[str, Any]:
    records = [expand_query(row) for row in rows]
    routes = Counter(record["query_expansion_route"] for record in records)
    source_counts = Counter()
    for record in records:
        for field, present in record["query_source_bits"].items():
            if present:
                source_counts[field] += 1
    return {
        "rows": len(rows),
        "records": records,
        "metrics": {
            "rows": len(rows),
            "query_variant_count": sum(len(record["query_variants"]) for record in records),
            "pass_rows": routes.get("PASS_QUERY_EXPANSION", 0),
            "hold_rows": routes.get("HOLD_QUERY_EXPANSION_NO_HINTS", 0),
            "blocked_rows": routes.get("BLOCK_QUERY_EXPANSION_LEAK", 0),
            "leak_or_target_rows": sum(record["leak_or_target_rows"] for record in records),
            "expansion_source_bits": dict(source_counts),
            "route_counts": dict(routes),
            "authority_rows": 0,
        },
    }


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def main() -> None:
    parser = argparse.ArgumentParser(description="Shortcut-safe no-authority query expansion rewriter.")
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    card = query_expansion_card(read_jsonl(args.manifest))
    text = json.dumps(card, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
    print(text, end="")


if __name__ == "__main__":
    main()
