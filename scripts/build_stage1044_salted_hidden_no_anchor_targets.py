#!/usr/bin/env python3
"""Build a salted hidden no-anchor split for bridge-free KBPP transfer tests."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any


ID_PREFIX_RE = re.compile(r"\b(?P<prefix>qent|dent|qslot|dslot|qpair|dpair|qclaim|dclaim|entity|slot)_([A-Za-z0-9]+)\b")


def _iter_jsonl(path: Path):
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                yield json.loads(line)


def _salt_value(value: str, *, salt: str) -> str:
    return hashlib.blake2b(f"{salt}:{value}".encode("utf-8"), digest_size=8).hexdigest()


def _rewrite_text(text: str, *, mapping: dict[str, str], salt: str) -> str:
    def repl(match: re.Match[str]) -> str:
        prefix = match.group("prefix")
        value = match.group(2)
        salted = mapping.setdefault(value, _salt_value(value, salt=salt))
        return f"{prefix}_{salted}"

    return ID_PREFIX_RE.sub(repl, text)


def _rewrite_bridge_value(value: Any, *, mapping: dict[str, str], salt: str) -> Any:
    if isinstance(value, list):
        return [_rewrite_bridge_value(item, mapping=mapping, salt=salt) for item in value]
    if isinstance(value, str):
        return mapping.setdefault(value, _salt_value(value, salt=salt))
    return value


def _rewrite_bridge(bridge: Any, *, mapping: dict[str, str], salt: str) -> Any:
    if not isinstance(bridge, dict):
        return bridge
    out: dict[str, Any] = {}
    for key, value in bridge.items():
        if key in {"qent", "dent", "qslot", "dslot", "qpair", "dpair", "qclaim", "dclaim"}:
            out[key] = _rewrite_bridge_value(value, mapping=mapping, salt=salt)
        else:
            out[key] = value
    return out


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-jsonl", type=Path, default=Path("runs/local/artifacts/stage1013_no_anchor_targets.jsonl"))
    parser.add_argument("--source-split", default="eval")
    parser.add_argument("--hidden-split", default="hidden_eval")
    parser.add_argument("--salt", default="stage1044_hidden_v1")
    parser.add_argument("--output-jsonl", type=Path, default=Path("runs/local/artifacts/stage1044_salted_hidden_no_anchor_targets.jsonl"))
    parser.add_argument("--output-summary", type=Path, default=Path("runs/local/artifacts/stage1044_salted_hidden_no_anchor_targets_summary.json"))
    args = parser.parse_args()

    mapping: dict[str, str] = {}
    rows = candidates = answer_candidates = exact_candidates = 0
    by_operation: dict[str, dict[str, int]] = {}
    args.output_jsonl.parent.mkdir(parents=True, exist_ok=True)
    with args.output_jsonl.open("w", encoding="utf-8") as out:
        for row in _iter_jsonl(args.input_jsonl):
            if str(row.get("split", "")) != str(args.source_split):
                continue
            rows += 1
            operation = str(row.get("operation", "unknown"))
            stats = by_operation.setdefault(operation, {"rows": 0, "candidates": 0, "answer_candidates": 0, "exact_candidates": 0})
            stats["rows"] += 1
            new_row = dict(row)
            new_row["split"] = str(args.hidden_split)
            new_row["query_text"] = _rewrite_text(str(row.get("query_text", "") or ""), mapping=mapping, salt=str(args.salt))
            new_row["query_bridge"] = _rewrite_bridge(row.get("query_bridge", {}) or {}, mapping=mapping, salt=str(args.salt))
            new_candidates = []
            for candidate in list(row.get("candidates", []) or []):
                candidates += 1
                stats["candidates"] += 1
                answer_candidates += int(bool(candidate.get("is_answer_match") or candidate.get("is_exact")))
                exact_candidates += int(bool(candidate.get("is_exact")))
                stats["answer_candidates"] += int(bool(candidate.get("is_answer_match") or candidate.get("is_exact")))
                stats["exact_candidates"] += int(bool(candidate.get("is_exact")))
                new_candidate = dict(candidate)
                new_candidate["doc_text"] = _rewrite_text(str(candidate.get("doc_text", "") or ""), mapping=mapping, salt=str(args.salt))
                new_candidate["bridge"] = _rewrite_bridge(candidate.get("bridge", {}) or {}, mapping=mapping, salt=str(args.salt))
                new_candidates.append(new_candidate)
            new_row["candidates"] = new_candidates
            new_row["stage1044_surface"] = {
                "source_split": str(args.source_split),
                "hidden_split": str(args.hidden_split),
                "salted_identifier_families": ["entity", "slot", "pair", "claim"],
                "answer_labels_preserved": True,
                "structured_bridge_fields_retained_for_audit_only": True,
                "no_pair_anchor_tokens": True,
            }
            out.write(json.dumps(new_row, sort_keys=True) + "\n")

    summary = {
        "artifact_kind": "stage1044_salted_hidden_no_anchor_targets",
        "status": "completed_salted_hidden_no_anchor_target_build",
        "input_jsonl": str(args.input_jsonl),
        "source_split": str(args.source_split),
        "hidden_split": str(args.hidden_split),
        "salt": str(args.salt),
        "output_jsonl": str(args.output_jsonl),
        "rows": rows,
        "candidates": candidates,
        "answer_candidates": answer_candidates,
        "exact_candidates": exact_candidates,
        "unique_salted_identifier_count": len(mapping),
        "by_operation": by_operation,
        "decision": "Builds a salted hidden no-anchor transfer split by remapping entity/slot/pair/claim identifiers while preserving labels and candidate groups. Bridge fields are retained for audit/teacher export only and must not be used at bridge-free eval.",
    }
    args.output_summary.parent.mkdir(parents=True, exist_ok=True)
    args.output_summary.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
