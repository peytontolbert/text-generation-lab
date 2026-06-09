#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
from typing import Any

import torch
import torch.nn.functional as F


_QPAIR_RE = re.compile(r"\bqpair_([A-Za-z0-9]+)\b")
_DPAIR_RE = re.compile(r"\bdpair_([A-Za-z0-9]+)\b")
_QENT_RE = re.compile(r"\bqent_([A-Za-z0-9]+)\b")
_DENT_RE = re.compile(r"\bdent_([A-Za-z0-9]+)\b")


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


def _first(pattern: re.Pattern[str], text: str) -> str:
    match = pattern.search(str(text or ""))
    return str(match.group(1)) if match else ""


def _bucket(value: str, buckets: int, *, salt: str) -> int:
    if not value:
        return 0
    digest = hashlib.blake2b(f"{salt}:{value}".encode("utf-8"), digest_size=8).digest()
    return 1 + (int.from_bytes(digest, "little") % max(1, int(buckets) - 1))


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


def _build_embeddings(buckets: int, dim: int, seed: int) -> tuple[torch.Tensor, torch.Tensor]:
    generator = torch.Generator(device="cpu")
    generator.manual_seed(int(seed))
    pair = torch.randn((int(buckets), int(dim)), generator=generator)
    entity = torch.randn((int(buckets), int(dim)), generator=generator)
    pair[0].zero_()
    entity[0].zero_()
    return F.normalize(pair, dim=-1), F.normalize(entity, dim=-1)


def _sim(table: torch.Tensor, left: int, right: int) -> float:
    return float((table[int(left)] * table[int(right)]).sum().item())


def _materialize_split(
    *,
    split: str,
    partition_rows: list[dict[str, Any]],
    text_rows: list[dict[str, Any]],
    text_docs: list[str],
    pair_embed: torch.Tensor,
    entity_embed: torch.Tensor,
    buckets: int,
    hash_salt_prefix: str,
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for row in partition_rows:
        if str(row.get("operation", "")) != "relation":
            continue
        query_index = int(row["query_index"])
        query = str(text_rows[query_index].get("retrieval_query_text", "") or "")
        qpair = _first(_QPAIR_RE, query)
        qent = _first(_QENT_RE, query)
        qpair_bucket = _bucket(qpair, buckets, salt=f"{hash_salt_prefix}:pair")
        qent_bucket = _bucket(qent, buckets, salt=f"{hash_salt_prefix}:entity")
        candidates = []
        for rank, candidate in enumerate(list(row.get("candidates", []) or []), start=1):
            doc_index = int(candidate["doc_index"])
            doc = str(text_docs[doc_index] or "")
            dpair = _first(_DPAIR_RE, doc)
            dent = _first(_DENT_RE, doc)
            dpair_bucket = _bucket(dpair, buckets, salt=f"{hash_salt_prefix}:pair")
            dent_bucket = _bucket(dent, buckets, salt=f"{hash_salt_prefix}:entity")
            pair_similarity = _sim(pair_embed, qpair_bucket, dpair_bucket)
            entity_similarity = _sim(entity_embed, qent_bucket, dent_bucket)
            candidates.append(
                {
                    "doc_index": doc_index,
                    "rank": rank,
                    "base_score": float(candidate.get("base_score", 0.0) or 0.0),
                    "partition_probability": float(candidate.get("partition_probability", 0.0) or 0.0),
                    "pair_similarity": pair_similarity,
                    "entity_similarity": entity_similarity,
                    "teacher_bridge_score": pair_similarity + entity_similarity,
                    "is_answer_match": bool(candidate.get("is_answer_match")),
                    "is_exact": bool(candidate.get("is_exact")),
                    "doc_text": doc,
                }
            )
        out.append(
            {
                "split": split,
                "query_index": query_index,
                "operation": "relation",
                "query_text": query,
                "hash_salt_prefix": hash_salt_prefix,
                "candidates": candidates,
            }
        )
    return out


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--partitions-json", required=True)
    parser.add_argument("--dataset-manifest", required=True)
    parser.add_argument("--hash-buckets", type=int, default=65536)
    parser.add_argument("--hash-dim", type=int, default=64)
    parser.add_argument("--seed", type=int, default=896)
    parser.add_argument("--train-hash-salt", default="train_salt_898")
    parser.add_argument("--calibration-hash-salt", default="calibration_salt_898")
    parser.add_argument("--eval-hash-salt", default="eval_salt_898")
    parser.add_argument("--output-jsonl", required=True)
    parser.add_argument("--summary-json", required=True)
    args = parser.parse_args()

    partitions = json.loads(Path(args.partitions_json).read_text(encoding="utf-8"))
    context = _load_text_context(Path(args.dataset_manifest))
    pair_embed, entity_embed = _build_embeddings(int(args.hash_buckets), int(args.hash_dim), int(args.seed))
    salts = {
        "train": str(args.train_hash_salt),
        "calibration": str(args.calibration_hash_salt),
        "eval": str(args.eval_hash_salt),
    }
    rows: list[dict[str, Any]] = []
    for split in ("train", "calibration", "eval"):
        rows.extend(
            _materialize_split(
                split=split,
                partition_rows=partitions[split],
                text_rows=context[split][0],
                text_docs=context[split][1],
                pair_embed=pair_embed,
                entity_embed=entity_embed,
                buckets=int(args.hash_buckets),
                hash_salt_prefix=salts[split],
            )
        )

    output_jsonl = Path(args.output_jsonl)
    output_jsonl.parent.mkdir(parents=True, exist_ok=True)
    with output_jsonl.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")

    by_split: dict[str, dict[str, Any]] = {}
    for split in ("train", "calibration", "eval"):
        split_rows = [row for row in rows if row["split"] == split]
        positive_rows = [
            row
            for row in split_rows
            if any(bool(candidate["is_exact"]) or bool(candidate["is_answer_match"]) for candidate in row["candidates"])
        ]
        by_split[split] = {
            "rows": len(split_rows),
            "positive_rows": len(positive_rows),
            "candidate_count": sum(len(row["candidates"]) for row in split_rows),
        }

    summary = {
        "artifact_kind": "stage898_relation_bridge_distillation_targets",
        "output_jsonl": str(output_jsonl),
        "partitions_json": str(Path(args.partitions_json).resolve()),
        "dataset_manifest": str(Path(args.dataset_manifest).resolve()),
        "hash_buckets": int(args.hash_buckets),
        "hash_dim": int(args.hash_dim),
        "seed": int(args.seed),
        "hash_salts": salts,
        "by_split": by_split,
        "target_fields": ["pair_similarity", "entity_similarity", "teacher_bridge_score", "is_exact", "is_answer_match"],
        "next_use": "Train a model-owned relation value head to predict teacher_bridge_score from query/doc hidden states, then evaluate candidate top-1 without external bridge scoring.",
    }
    summary_path = Path(args.summary_json)
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
