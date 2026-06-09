#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import random
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


def _prepare(
    partition_rows: list[dict[str, Any]],
    text_rows: list[dict[str, Any]],
    text_docs: list[str],
    *,
    buckets: int,
    hash_salt_prefix: str = "",
) -> list[dict[str, Any]]:
    prepared: list[dict[str, Any]] = []
    for row in partition_rows:
        if str(row.get("operation", "")) != "relation":
            continue
        candidates = list(row.get("candidates", []) or [])
        labels = [idx for idx, candidate in enumerate(candidates) if bool(candidate.get("is_exact"))]
        if not labels:
            labels = [idx for idx, candidate in enumerate(candidates) if bool(candidate.get("is_answer_match"))]
        label = int(labels[0]) if labels else -1
        query = str(text_rows[int(row["query_index"])].get("retrieval_query_text", "") or "")
        qpair = _first(_QPAIR_RE, query)
        qent = _first(_QENT_RE, query)
        qpair_bucket = _bucket(qpair, buckets, salt=f"{hash_salt_prefix}:pair")
        qent_bucket = _bucket(qent, buckets, salt=f"{hash_salt_prefix}:entity")
        candidate_features = []
        for rank, candidate in enumerate(candidates, start=1):
            doc = str(text_docs[int(candidate["doc_index"])] or "")
            dpair = _first(_DPAIR_RE, doc)
            dent = _first(_DENT_RE, doc)
            selected_count = max(1, int(row.get("selected_count", len(candidates))) or len(candidates) or 1)
            candidate_features.append(
                {
                    "qpair_bucket": qpair_bucket,
                    "dpair_bucket": _bucket(dpair, buckets, salt=f"{hash_salt_prefix}:pair"),
                    "qent_bucket": qent_bucket,
                    "dent_bucket": _bucket(dent, buckets, salt=f"{hash_salt_prefix}:entity"),
                    "base_score": float(candidate.get("base_score", 0.0) or 0.0),
                    "partition_probability": float(candidate.get("partition_probability", 0.0) or 0.0),
                    "rank_feature": float(rank) / float(selected_count),
                    "inv_rank": 1.0 / float(rank),
                    "is_exact": bool(candidate.get("is_exact")),
                    "is_answer_match": bool(candidate.get("is_answer_match")),
                }
            )
        prepared.append({"row": row, "candidates": candidate_features, "label": label})
    return prepared


class BridgeScorer(torch.nn.Module):
    def __init__(self, buckets: int, dim: int, *, freeze_embeddings: bool = False) -> None:
        super().__init__()
        self.pair_embed = torch.nn.Embedding(int(buckets), int(dim), padding_idx=0)
        self.entity_embed = torch.nn.Embedding(int(buckets), int(dim), padding_idx=0)
        self.scalar = torch.nn.Linear(6, 1)
        with torch.no_grad():
            self.pair_embed.weight.normal_(mean=0.0, std=1.0)
            self.entity_embed.weight.normal_(mean=0.0, std=1.0)
            self.pair_embed.weight[0].zero_()
            self.entity_embed.weight[0].zero_()
        if freeze_embeddings:
            self.pair_embed.weight.requires_grad_(False)
            self.entity_embed.weight.requires_grad_(False)

    def forward(self, batch: dict[str, torch.Tensor]) -> torch.Tensor:
        qpair = self.pair_embed(batch["qpair_bucket"])
        dpair = self.pair_embed(batch["dpair_bucket"])
        qent = self.entity_embed(batch["qent_bucket"])
        dent = self.entity_embed(batch["dent_bucket"])
        pair_dot = (F.normalize(qpair, dim=-1) * F.normalize(dpair, dim=-1)).sum(dim=-1, keepdim=True)
        ent_dot = (F.normalize(qent, dim=-1) * F.normalize(dent, dim=-1)).sum(dim=-1, keepdim=True)
        scalars = torch.stack(
            [
                batch["base_score"],
                batch["partition_probability"],
                batch["rank_feature"],
                batch["inv_rank"],
                pair_dot.squeeze(-1),
                ent_dot.squeeze(-1),
            ],
            dim=-1,
        )
        return self.scalar(scalars).squeeze(-1)


def _batch(candidates: list[dict[str, Any]], device: torch.device) -> dict[str, torch.Tensor]:
    return {
        "qpair_bucket": torch.tensor([c["qpair_bucket"] for c in candidates], dtype=torch.long, device=device),
        "dpair_bucket": torch.tensor([c["dpair_bucket"] for c in candidates], dtype=torch.long, device=device),
        "qent_bucket": torch.tensor([c["qent_bucket"] for c in candidates], dtype=torch.long, device=device),
        "dent_bucket": torch.tensor([c["dent_bucket"] for c in candidates], dtype=torch.long, device=device),
        "base_score": torch.tensor([c["base_score"] for c in candidates], dtype=torch.float32, device=device),
        "partition_probability": torch.tensor([c["partition_probability"] for c in candidates], dtype=torch.float32, device=device),
        "rank_feature": torch.tensor([c["rank_feature"] for c in candidates], dtype=torch.float32, device=device),
        "inv_rank": torch.tensor([c["inv_rank"] for c in candidates], dtype=torch.float32, device=device),
    }


def _score_split(model: BridgeScorer, rows: list[dict[str, Any]], device: torch.device) -> dict[str, Any]:
    answer = exact = recoverable_answer = recoverable_exact = 0
    mrr = 0.0
    with torch.no_grad():
        for item in rows:
            candidates = item["candidates"]
            scores = model(_batch(candidates, device)).detach().cpu()
            order = sorted(range(len(candidates)), key=lambda idx: (-float(scores[idx].item()), idx))
            top = candidates[order[0]]
            top_answer = bool(top["is_exact"]) or bool(top["is_answer_match"])
            answer += int(top_answer)
            exact += int(bool(top["is_exact"]))
            recoverable_answer += int(any(bool(c["is_exact"]) or bool(c["is_answer_match"]) for c in candidates))
            recoverable_exact += int(any(bool(c["is_exact"]) for c in candidates))
            label = int(item["label"])
            rank = order.index(label) + 1 if label >= 0 and label in order else len(order) + 1
            mrr += 1.0 / float(rank)
    total = len(rows)
    return {
        "examples": total,
        "answer_correct": answer,
        "exact_correct": exact,
        "answer_recoverable": recoverable_answer,
        "exact_recoverable": recoverable_exact,
        "mrr": mrr / float(total or 1),
    }


def train(args: argparse.Namespace) -> dict[str, Any]:
    random.seed(int(args.seed))
    torch.manual_seed(int(args.seed))
    device = torch.device(str(args.device))
    partitions = json.loads(Path(args.partitions_json).read_text(encoding="utf-8"))
    context = _load_text_context(Path(args.dataset_manifest))
    train_rows = _prepare(
        partitions["train"],
        *context["train"],
        buckets=int(args.hash_buckets),
        hash_salt_prefix=str(args.train_hash_salt),
    )
    calibration_rows = _prepare(
        partitions["calibration"],
        *context["calibration"],
        buckets=int(args.hash_buckets),
        hash_salt_prefix=str(args.calibration_hash_salt),
    )
    eval_rows = _prepare(
        partitions["eval"],
        *context["eval"],
        buckets=int(args.hash_buckets),
        hash_salt_prefix=str(args.eval_hash_salt),
    )
    train_supervised = [row for row in train_rows if int(row["label"]) >= 0]
    model = BridgeScorer(int(args.hash_buckets), int(args.hash_dim), freeze_embeddings=bool(args.freeze_embeddings)).to(device)
    optimizer = torch.optim.AdamW(
        [parameter for parameter in model.parameters() if parameter.requires_grad],
        lr=float(args.learning_rate),
        weight_decay=float(args.weight_decay),
    )
    order = list(range(len(train_supervised)))
    best_state = None
    best_calibration = None
    history = []
    for step in range(1, int(args.steps) + 1):
        random.shuffle(order)
        losses = []
        for idx in order[: int(args.rows_per_step)]:
            item = train_supervised[idx]
            scores = model(_batch(item["candidates"], device))
            losses.append(F.cross_entropy(scores.unsqueeze(0), torch.tensor([int(item["label"])], dtype=torch.long, device=device)))
        loss = torch.stack(losses).mean()
        optimizer.zero_grad(set_to_none=True)
        loss.backward()
        optimizer.step()
        if step == 1 or step == int(args.steps) or step % int(args.eval_every) == 0:
            calibration = _score_split(model, calibration_rows, device)
            history.append({"step": step, "loss": float(loss.detach().cpu().item()), "calibration_answer": calibration["answer_correct"], "calibration_exact": calibration["exact_correct"], "calibration_mrr": calibration["mrr"]})
            key = (calibration["answer_correct"], calibration["exact_correct"], calibration["mrr"])
            if best_calibration is None or key > best_calibration:
                best_calibration = key
                best_state = {name: value.detach().cpu().clone() for name, value in model.state_dict().items()}
    if best_state is not None:
        model.load_state_dict(best_state)
    summary = {
        "artifact_kind": "stage891_relation_bridge_embedding_scorer",
        "partitions_json": str(Path(args.partitions_json).resolve()),
        "dataset_manifest": str(Path(args.dataset_manifest).resolve()),
        "hash_buckets": int(args.hash_buckets),
        "hash_dim": int(args.hash_dim),
        "hash_salts": {
            "train": str(args.train_hash_salt),
            "calibration": str(args.calibration_hash_salt),
            "eval": str(args.eval_hash_salt),
        },
        "freeze_embeddings": bool(args.freeze_embeddings),
        "parameter_count": sum(parameter.numel() for parameter in model.parameters()),
        "trainable_parameter_count": sum(parameter.numel() for parameter in model.parameters() if parameter.requires_grad),
        "steps": int(args.steps),
        "rows_per_step": int(args.rows_per_step),
        "history": history,
        "train": _score_split(model, train_rows, device),
        "calibration": _score_split(model, calibration_rows, device),
        "eval": _score_split(model, eval_rows, device),
        "decision_hint": "No binary pair_match feature is provided. Frozen mode tests deterministic shared normalized qpair/dpair hash similarity without learning bridge IDs.",
    }
    output = Path(args.output_json)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--partitions-json", required=True)
    parser.add_argument("--dataset-manifest", required=True)
    parser.add_argument("--device", default="cuda" if torch.cuda.is_available() else "cpu")
    parser.add_argument("--hash-buckets", type=int, default=4096)
    parser.add_argument("--hash-dim", type=int, default=16)
    parser.add_argument("--steps", type=int, default=300)
    parser.add_argument("--rows-per-step", type=int, default=64)
    parser.add_argument("--eval-every", type=int, default=25)
    parser.add_argument("--learning-rate", type=float, default=0.005)
    parser.add_argument("--weight-decay", type=float, default=0.01)
    parser.add_argument("--seed", type=int, default=891)
    parser.add_argument("--freeze-embeddings", action="store_true")
    parser.add_argument("--train-hash-salt", default="")
    parser.add_argument("--calibration-hash-salt", default="")
    parser.add_argument("--eval-hash-salt", default="")
    parser.add_argument("--output-json", required=True)
    train(parser.parse_args())


if __name__ == "__main__":
    main()
