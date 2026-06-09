#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
from typing import Any


_TOKEN_RE = re.compile(r"\b([qd](?:ent|pair|slot|claim)_[A-Za-z0-9]+)\b")
_KIND_RE = re.compile(r"^([qd](?:ent|pair|slot|claim))_([A-Za-z0-9]+)$")


def _iter_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def _direct_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        row
        for row in rows
        if str(row.get("task_type", "") or "") == "active_agent_direct_answer"
        and str(row.get("retrieval_query_text", "") or "").strip()
        and str(row.get("retrieval_doc_text", "") or "").strip()
    ]


def _unique_docs(rows: list[dict[str, Any]]) -> list[str]:
    docs: list[str] = []
    seen: set[str] = set()
    for row in rows:
        doc = str(row.get("retrieval_doc_text", "") or "").strip()
        if doc and doc not in seen:
            seen.add(doc)
            docs.append(doc)
    return docs


def _load_text_context(manifest_path: Path) -> dict[str, tuple[list[dict[str, Any]], list[str]]]:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    train_rows = _direct_rows(_iter_jsonl(Path(manifest["train_dataset_path"])))
    eval_rows = _direct_rows(_iter_jsonl(Path(manifest["eval_dataset_path"])))
    calibration_rows = _direct_rows(_iter_jsonl(Path(manifest["calibration_dataset_path"])))
    return {
        "train": (train_rows, _unique_docs(train_rows)),
        "calibration": (calibration_rows, _unique_docs(calibration_rows)),
        "eval": (eval_rows, _unique_docs(eval_rows)),
    }


def _tokens(text: str) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    for raw in _TOKEN_RE.findall(str(text or "")):
        match = _KIND_RE.match(raw)
        if not match:
            continue
        kind, suffix = str(match.group(1)), str(match.group(2))
        out.setdefault(kind, [])
        if suffix not in out[kind]:
            out[kind].append(suffix)
    return out


def _any_equal(left: list[str], right: list[str]) -> bool:
    return bool(set(left) & set(right))


def _candidate_bridge_features(query_tokens: dict[str, list[str]], doc_tokens: dict[str, list[str]]) -> dict[str, Any]:
    qent = query_tokens.get("qent", [])
    dent = doc_tokens.get("dent", [])
    qpair = query_tokens.get("qpair", [])
    dpair = doc_tokens.get("dpair", [])
    qslot = query_tokens.get("qslot", [])
    dslot = doc_tokens.get("dslot", [])
    qclaim = query_tokens.get("qclaim", [])
    dclaim = doc_tokens.get("dclaim", [])
    return {
        "qent": qent,
        "dent": dent,
        "qpair": qpair,
        "dpair": dpair,
        "qslot": qslot,
        "dslot": dslot,
        "qclaim": qclaim,
        "dclaim": dclaim,
        "entity_suffix_match": _any_equal(qent, dent),
        "pair_suffix_match": _any_equal(qpair, dpair),
        "slot_suffix_match": _any_equal(qslot, dslot),
        "claim_suffix_match": _any_equal(qclaim, dclaim),
        "query_bridge_token_count": sum(len(values) for values in query_tokens.values()),
        "doc_bridge_token_count": sum(len(values) for values in doc_tokens.values()),
    }


def _materialize_split(
    split: str,
    partition_rows: list[dict[str, Any]],
    text_rows: list[dict[str, Any]],
    text_docs: list[str],
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for row in partition_rows:
        query_index = int(row["query_index"])
        query_text = str(text_rows[query_index].get("retrieval_query_text", "") or "")
        query_tokens = _tokens(query_text)
        candidates = []
        for rank, candidate in enumerate(list(row.get("candidates", []) or []), start=1):
            doc_index = int(candidate["doc_index"])
            doc_text = str(text_docs[doc_index] or "")
            bridge = _candidate_bridge_features(query_tokens, _tokens(doc_text))
            candidates.append(
                {
                    "doc_index": doc_index,
                    "rank": rank,
                    "base_score": float(candidate.get("base_score", 0.0) or 0.0),
                    "partition_probability": float(candidate.get("partition_probability", 0.0) or 0.0),
                    "is_exact": bool(candidate.get("is_exact")),
                    "is_answer_match": bool(candidate.get("is_answer_match")),
                    "bridge": bridge,
                    "doc_text": doc_text,
                }
            )
        out.append(
            {
                "split": split,
                "operation": str(row.get("operation", "") or ""),
                "query_index": query_index,
                "query_text": query_text,
                "query_bridge": query_tokens,
                "candidates": candidates,
            }
        )
    return out


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--partitions-json", required=True)
    parser.add_argument("--dataset-manifest", required=True)
    parser.add_argument("--output-jsonl", required=True)
    parser.add_argument("--summary-json", required=True)
    args = parser.parse_args()

    partitions = json.loads(Path(args.partitions_json).read_text(encoding="utf-8"))
    context = _load_text_context(Path(args.dataset_manifest))
    rows: list[dict[str, Any]] = []
    for split in ("train", "calibration", "eval"):
        rows.extend(_materialize_split(split, partitions[split], *context[split]))

    output = Path(args.output_jsonl)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")

    by_split_op: dict[str, dict[str, dict[str, int]]] = {}
    for row in rows:
        split = str(row["split"])
        op = str(row["operation"])
        stats = by_split_op.setdefault(split, {}).setdefault(
            op,
            {
                "rows": 0,
                "candidates": 0,
                "positive_rows": 0,
                "pair_match_positive_candidates": 0,
                "entity_match_positive_candidates": 0,
                "slot_match_positive_candidates": 0,
            },
        )
        stats["rows"] += 1
        candidates = list(row.get("candidates", []) or [])
        stats["candidates"] += len(candidates)
        stats["positive_rows"] += int(any(bool(c["is_exact"]) or bool(c["is_answer_match"]) for c in candidates))
        for candidate in candidates:
            positive = bool(candidate["is_exact"]) or bool(candidate["is_answer_match"])
            if not positive:
                continue
            bridge = dict(candidate.get("bridge", {}) or {})
            stats["pair_match_positive_candidates"] += int(bool(bridge.get("pair_suffix_match")))
            stats["entity_match_positive_candidates"] += int(bool(bridge.get("entity_suffix_match")))
            stats["slot_match_positive_candidates"] += int(bool(bridge.get("slot_suffix_match")))

    summary = {
        "artifact_kind": "stage907_broad_bridge_curriculum_targets",
        "output_jsonl": str(output),
        "partitions_json": str(Path(args.partitions_json).resolve()),
        "dataset_manifest": str(Path(args.dataset_manifest).resolve()),
        "rows": len(rows),
        "by_split_operation": by_split_op,
        "target_use": "Train an explicit binding-comparison head across operations before candidate scoring.",
    }
    summary_path = Path(args.summary_json)
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
