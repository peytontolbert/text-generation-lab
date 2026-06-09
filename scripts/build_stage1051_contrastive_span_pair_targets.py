#!/usr/bin/env python3
"""Export contrastive span-pair targets for bridge-free operator training."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any


QENT_RE = re.compile(r"\bqent_([A-Za-z0-9]+)\b")
Qslot_RE = re.compile(r"\bqslot_([A-Za-z0-9]+)\b")
STATEMENT_DENT_RE = re.compile(r"\bstatement=(?:claim\s+)?dent_([A-Za-z0-9]+)\b")
TARGET_DENT_RE = re.compile(r"\btarget for dent_([A-Za-z0-9]+)\b")
DSLOT_RE = re.compile(r"\bdslot_([A-Za-z0-9]+)\b")
DEFAULT_KIND_RE = re.compile(r"\bdefault\s+([A-Za-z0-9]+)\b")
ANSWER_KIND_RE = re.compile(r"\banswer=([A-Za-z0-9]+)_v[0-9A-Za-z]+\b")
DEFAULT_POLICY_RE = re.compile(r"\bstatement=default\s+([A-Za-z0-9]+)\s+policy\b")


def _iter_jsonl(path: Path):
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                yield json.loads(line)


def _span_text(prefix: str, value: str) -> str:
    return f"{prefix}_{value}"


def _add_example(
    examples: list[dict[str, Any]],
    *,
    split: str,
    operation: str,
    row_index: int,
    candidate_index: int,
    pair_type: str,
    query_span: str,
    doc_span: str,
    label: int,
    candidate: dict[str, Any],
) -> None:
    examples.append(
        {
            "split": split,
            "operation": operation,
            "row_index": int(row_index),
            "candidate_index": int(candidate_index),
            "pair_type": pair_type,
            "query_span": query_span,
            "doc_span": doc_span,
            "label": int(label),
            "candidate_is_answer_match": int(bool(candidate.get("is_answer_match") or candidate.get("is_exact"))),
            "candidate_is_exact": int(bool(candidate.get("is_exact"))),
            "candidate_base_score": float(candidate.get("base_score", 0.0) or 0.0),
            "candidate_rank": int(candidate.get("rank", 9999) or 9999),
        }
    )


def _export_from_rows(path: Path, examples: list[dict[str, Any]], *, split_override: str | None = None) -> dict[str, Any]:
    rows = candidates = 0
    by_pair_type: dict[str, dict[str, int]] = {}
    row_counters: dict[str, int] = {}
    for row in _iter_jsonl(path):
        split = str(split_override or row.get("split", "unknown"))
        row_index = row_counters.get(split, 0)
        row_counters[split] = row_index + 1
        rows += 1
        operation = str(row.get("operation", "unknown"))
        query = str(row.get("query_text", "") or "")
        qents = QENT_RE.findall(query)
        qslots = Qslot_RE.findall(query)
        default_kinds = DEFAULT_KIND_RE.findall(query)
        for candidate_index, candidate in enumerate(list(row.get("candidates", []) or [])):
            candidates += 1
            doc = str(candidate.get("doc_text", "") or "")
            dents = sorted(set(STATEMENT_DENT_RE.findall(doc) + TARGET_DENT_RE.findall(doc)))
            dslots = DSLOT_RE.findall(doc)
            answer_kinds = ANSWER_KIND_RE.findall(doc)
            policy_kinds = DEFAULT_POLICY_RE.findall(doc)
            for qent in qents:
                for dent in dents:
                    label = int(qent == dent)
                    _add_example(
                        examples,
                        split=split,
                        operation=operation,
                        row_index=row_index,
                        candidate_index=candidate_index,
                        pair_type="entity_statement",
                        query_span=_span_text("qent", qent),
                        doc_span=f"statement_dent_{dent}",
                        label=label,
                        candidate=candidate,
                    )
            for qslot in qslots:
                for dslot in dslots:
                    label = int(qslot == dslot)
                    _add_example(
                        examples,
                        split=split,
                        operation=operation,
                        row_index=row_index,
                        candidate_index=candidate_index,
                        pair_type="slot",
                        query_span=_span_text("qslot", qslot),
                        doc_span=_span_text("dslot", dslot),
                        label=label,
                        candidate=candidate,
                    )
            for default_kind in default_kinds:
                for answer_kind in answer_kinds:
                    _add_example(
                        examples,
                        split=split,
                        operation=operation,
                        row_index=row_index,
                        candidate_index=candidate_index,
                        pair_type="default_answer_kind",
                        query_span=f"default {default_kind}",
                        doc_span=f"answer {answer_kind}",
                        label=int(default_kind == answer_kind),
                        candidate=candidate,
                    )
                for policy_kind in policy_kinds:
                    _add_example(
                        examples,
                        split=split,
                        operation=operation,
                        row_index=row_index,
                        candidate_index=candidate_index,
                        pair_type="default_policy_kind",
                        query_span=f"default {default_kind}",
                        doc_span=f"default policy {policy_kind}",
                        label=int(default_kind == policy_kind),
                        candidate=candidate,
                    )
    for example in examples:
        stats = by_pair_type.setdefault(example["pair_type"], {"examples": 0, "positive": 0, "negative": 0})
        stats["examples"] += 1
        stats["positive"] += int(example["label"] == 1)
        stats["negative"] += int(example["label"] == 0)
    return {"rows": rows, "candidates": candidates, "by_pair_type": by_pair_type}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--teacher-jsonl", type=Path, default=Path("runs/local/artifacts/stage1043_operator_teacher_targets.jsonl"))
    parser.add_argument("--hidden-jsonl", type=Path, default=Path("runs/local/artifacts/stage1044_salted_hidden_no_anchor_targets.jsonl"))
    parser.add_argument("--output-jsonl", type=Path, default=Path("runs/local/artifacts/stage1051_contrastive_span_pair_targets.jsonl"))
    parser.add_argument("--output-summary", type=Path, default=Path("runs/local/artifacts/stage1051_contrastive_span_pair_targets_summary.json"))
    args = parser.parse_args()

    examples: list[dict[str, Any]] = []
    teacher_stats = _export_from_rows(args.teacher_jsonl, examples)
    hidden_start = len(examples)
    hidden_stats = _export_from_rows(args.hidden_jsonl, examples)
    for index in range(hidden_start, len(examples)):
        examples[index]["is_hidden_transfer"] = 1
    for index in range(0, hidden_start):
        examples[index]["is_hidden_transfer"] = 0

    by_split_pair_type: dict[str, dict[str, dict[str, int]]] = {}
    for example in examples:
        stats = by_split_pair_type.setdefault(example["split"], {}).setdefault(example["pair_type"], {"examples": 0, "positive": 0, "negative": 0})
        stats["examples"] += 1
        stats["positive"] += int(example["label"] == 1)
        stats["negative"] += int(example["label"] == 0)

    args.output_jsonl.parent.mkdir(parents=True, exist_ok=True)
    with args.output_jsonl.open("w", encoding="utf-8") as handle:
        for example in examples:
            handle.write(json.dumps(example, sort_keys=True) + "\n")

    summary = {
        "artifact_kind": "stage1051_contrastive_span_pair_targets",
        "status": "completed_contrastive_span_pair_target_export",
        "teacher_jsonl": str(args.teacher_jsonl),
        "hidden_jsonl": str(args.hidden_jsonl),
        "output_jsonl": str(args.output_jsonl),
        "examples": len(examples),
        "teacher_source": teacher_stats,
        "hidden_source": hidden_stats,
        "by_split_pair_type": by_split_pair_type,
        "decision": "Exports explicit positive and same-surface negative span-pair labels for contrastive entity, slot, and default-kind operator training. Hidden examples are for transfer reporting unless explicitly included as augmentation.",
    }
    args.output_summary.parent.mkdir(parents=True, exist_ok=True)
    args.output_summary.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
