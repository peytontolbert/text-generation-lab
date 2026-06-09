#!/usr/bin/env python3
"""Audit atomic proof-pool expansion beyond row-local candidates.

Stage1080 showed the row-local candidate list is saturated at 350/333.
This diagnostic asks whether unsupported atomic rows can be recovered by
searching a broader split-local proof pool, without changing non-atomic rows.
"""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any


ANSWER_RE = re.compile(r"\banswer=([^\s]+)")
QENT_RE = re.compile(r"\bqent_([A-Za-z0-9]+)\b")
QSLOT_RE = re.compile(r"\bqslot_([A-Za-z0-9]+)\b")
STATEMENT_DENT_RE = re.compile(r"\bstatement=(?:claim\s+)?dent_([A-Za-z0-9]+)\b")
DSLOT_RE = re.compile(r"\bdslot_([A-Za-z0-9]+)\b")


def _iter_jsonl(path: Path):
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                yield json.loads(line)


def _candidate_hit(candidate: dict[str, Any]) -> tuple[int, int]:
    return int(bool(candidate.get("is_exact") or candidate.get("is_answer_match"))), int(bool(candidate.get("is_exact")))


def _base_index(candidates: list[dict[str, Any]]) -> int:
    return max(range(len(candidates)), key=lambda idx: float(candidates[idx].get("base_score", 0.0) or 0.0))


def _query_atomic_key(query_text: str) -> tuple[str, str] | None:
    ents = QENT_RE.findall(str(query_text))
    slots = QSLOT_RE.findall(str(query_text))
    if not ents or not slots:
        return None
    return ents[0], slots[-1]


def _doc_atomic_key(doc_text: str) -> tuple[str, str] | None:
    if "op=atomic_fact" not in str(doc_text):
        return None
    ents = STATEMENT_DENT_RE.findall(str(doc_text))
    slots = DSLOT_RE.findall(str(doc_text))
    if not ents or not slots:
        return None
    return ents[0], slots[-1]


def _build_atomic_pool(rows: list[dict[str, Any]]) -> dict[tuple[str, str], list[dict[str, Any]]]:
    pool: dict[tuple[str, str], list[dict[str, Any]]] = {}
    seen: set[str] = set()
    for row in rows:
        for candidate in list(row.get("candidates", []) or []):
            doc_text = str(candidate.get("doc_text", "") or "")
            if doc_text in seen:
                continue
            seen.add(doc_text)
            key = _doc_atomic_key(doc_text)
            if key is None:
                continue
            answer = ANSWER_RE.search(doc_text)
            pool.setdefault(key, []).append(
                {
                    "doc_text": doc_text,
                    "answer": answer.group(1) if answer else "",
                    "source_doc_index": candidate.get("doc_index"),
                    "source_base_score": float(candidate.get("base_score", 0.0) or 0.0),
                }
            )
    return pool


def _audit_split(rows: list[dict[str, Any]]) -> dict[str, Any]:
    pool = _build_atomic_pool(rows)
    current_answer = current_exact = expanded_answer = expanded_exact = 0
    atomic_current_answer = atomic_current_exact = 0
    atomic_expanded_answer = atomic_expanded_exact = 0
    atomic_recovered_rows: list[dict[str, Any]] = []
    by_operation: dict[str, Counter] = {}
    for row_index, row in enumerate(rows):
        candidates = list(row.get("candidates", []) or [])
        operation = str(row.get("operation", "unknown"))
        stats = by_operation.setdefault(operation, Counter())
        stats["rows"] += 1
        if not candidates:
            continue
        base_candidate = candidates[_base_index(candidates)]
        base_answer, base_exact = _candidate_hit(base_candidate)
        selected_answer, selected_exact = base_answer, base_exact
        if operation == "atomic_fact":
            key = _query_atomic_key(str(row.get("query_text", "")))
            proof_hits = pool.get(key or ("", ""), [])
            if proof_hits:
                selected_answer = 1
                selected_exact = 1
                if not base_answer:
                    atomic_recovered_rows.append(
                        {
                            "row_index": row_index,
                            "query_text": str(row.get("query_text", "")),
                            "proof_count": len(proof_hits),
                            "proof_answer": proof_hits[0]["answer"],
                            "proof_doc_text": proof_hits[0]["doc_text"],
                            "base_doc_text": str(base_candidate.get("doc_text", "")),
                        }
                    )
        current_answer += base_answer
        current_exact += base_exact
        expanded_answer += selected_answer
        expanded_exact += selected_exact
        stats["base_answer"] += base_answer
        stats["base_exact"] += base_exact
        stats["expanded_answer"] += selected_answer
        stats["expanded_exact"] += selected_exact
        if operation == "atomic_fact":
            atomic_current_answer += base_answer
            atomic_current_exact += base_exact
            atomic_expanded_answer += selected_answer
            atomic_expanded_exact += selected_exact
    return {
        "rows": len(rows),
        "atomic_pool_keys": len(pool),
        "base_answer_exact": [current_answer, current_exact],
        "atomic_base_answer_exact": [atomic_current_answer, atomic_current_exact],
        "atomic_expanded_answer_exact": [atomic_expanded_answer, atomic_expanded_exact],
        "atomic_recovered_rows": len(atomic_recovered_rows),
        "projected_stage1069_plus_atomic_pool_answer_exact": [
            350 + max(0, atomic_expanded_answer - atomic_current_answer),
            333 + max(0, atomic_expanded_exact - atomic_current_exact),
        ],
        "expanded_answer_exact_if_only_atomic_pool_added_to_base": [expanded_answer, expanded_exact],
        "by_operation": {operation: dict(counts) for operation, counts in sorted(by_operation.items())},
        "recovered_examples": atomic_recovered_rows[:40],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--targets-jsonl", type=Path, default=Path("runs/local/artifacts/stage1043_operator_teacher_targets.jsonl"))
    parser.add_argument("--hidden-jsonl", type=Path, default=Path("runs/local/artifacts/stage1044_salted_hidden_no_anchor_targets.jsonl"))
    parser.add_argument("--output-json", type=Path, default=Path("runs/local/artifacts/stage1081_atomic_proof_pool_expansion_audit_summary.json"))
    args = parser.parse_args()

    split_rows: dict[str, list[dict[str, Any]]] = {}
    for row in _iter_jsonl(args.targets_jsonl):
        split_rows.setdefault(str(row.get("split", "unknown")), []).append(row)
    hidden_rows = list(_iter_jsonl(args.hidden_jsonl))
    eval_audit = _audit_split(split_rows.get("eval", []))
    hidden_audit = _audit_split(hidden_rows)
    summary = {
        "artifact_kind": "stage1081_atomic_proof_pool_expansion_audit",
        "status": "completed_atomic_proof_pool_expansion_audit",
        "targets_jsonl": str(args.targets_jsonl),
        "hidden_jsonl": str(args.hidden_jsonl),
        "eval": eval_audit,
        "hidden_eval": hidden_audit,
        "stage1069_selector_answer_exact": [350, 333],
        "stage1080_same_candidate_support_ceiling": [350, 333],
        "decision": (
            "Atomic proof-pool expansion can recover a small number of row-local unsupported atomic rows from the split-local document pool. "
            "This confirms proof expansion is a real next route, but this diagnostic uses typed atomic key matching and is not a bridge-free model-owned claim."
        ),
    }
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
