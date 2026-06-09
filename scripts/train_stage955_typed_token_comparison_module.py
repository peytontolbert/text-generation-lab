#!/usr/bin/env python3
"""Train a small typed token-comparison module on the Stage952 patched relation surface."""

from __future__ import annotations

import argparse
import hashlib
import json
import random
from pathlib import Path
from typing import Any

import torch
import torch.nn.functional as F


def iter_jsonl(path: Path):
    with path.open() as f:
        for line in f:
            line = line.strip()
            if line:
                yield json.loads(line)


def rows_by_split(path: Path) -> dict[str, list[dict[str, Any]]]:
    rows: dict[str, list[dict[str, Any]]] = {"train": [], "calibration": [], "eval": []}
    for row in iter_jsonl(path):
        if row.get("operation") == "relation":
            rows.setdefault(str(row.get("split")), []).append(row)
    return rows


def stable_bucket(token: str, buckets: int, salt: str) -> int:
    digest = hashlib.blake2b(f"{salt}:{token}".encode("utf-8"), digest_size=8).digest()
    return int.from_bytes(digest, "little") % int(buckets)


def bridge(candidate: dict[str, Any]) -> dict[str, Any]:
    return candidate.get("bridge", {}) or {}


def query_bridge(row: dict[str, Any]) -> dict[str, Any]:
    return row.get("query_bridge", {}) or {}


def label_index(row: dict[str, Any]) -> int:
    for idx, candidate in enumerate(row.get("candidates", []) or []):
        if candidate.get("is_exact"):
            return idx
    return -1


def candidate_hit(candidate: dict[str, Any]) -> tuple[int, int]:
    return int(bool(candidate.get("is_exact") or candidate.get("is_answer_match"))), int(bool(candidate.get("is_exact")))


class TypedCompare(torch.nn.Module):
    def __init__(self, buckets: int, dim: int) -> None:
        super().__init__()
        self.buckets = int(buckets)
        self.dim = int(dim)
        self.ent = torch.nn.Embedding(self.buckets, self.dim)
        self.pair = torch.nn.Embedding(self.buckets, self.dim)
        self.slot = torch.nn.Embedding(self.buckets, self.dim)
        self.head = torch.nn.Linear(6, 1)
        for emb in [self.ent, self.pair, self.slot]:
            torch.nn.init.normal_(emb.weight, mean=0.0, std=0.02)
        torch.nn.init.zeros_(self.head.bias)
        torch.nn.init.xavier_uniform_(self.head.weight)

    def _max_dot(self, emb: torch.nn.Embedding, q_ids: list[int], d_ids: list[int], device: torch.device) -> torch.Tensor:
        if not q_ids or not d_ids:
            return torch.tensor(0.0, device=device)
        q = emb(torch.tensor(q_ids, dtype=torch.long, device=device))
        d = emb(torch.tensor(d_ids, dtype=torch.long, device=device))
        return torch.matmul(q, d.T).max()

    def candidate_score(self, row: dict[str, Any], candidate: dict[str, Any], device: torch.device, salt: str) -> torch.Tensor:
        qb = query_bridge(row)
        cb = bridge(candidate)
        qent = [stable_bucket(str(x), self.buckets, salt) for x in qb.get("qent", [])]
        dent = [stable_bucket(str(x), self.buckets, salt) for x in cb.get("dent", [])]
        qpair = [stable_bucket(str(x), self.buckets, salt) for x in qb.get("qpair", [])]
        dpair = [stable_bucket(str(x), self.buckets, salt) for x in cb.get("dpair", [])]
        qslot = [stable_bucket(str(x), self.buckets, salt) for x in qb.get("qslot", [])]
        dslot = [stable_bucket(str(x), self.buckets, salt) for x in cb.get("dslot", [])]
        scalars = torch.stack(
            [
                self._max_dot(self.ent, qent, dent, device),
                self._max_dot(self.pair, qpair, dpair, device),
                self._max_dot(self.slot, qslot, dslot, device),
                torch.tensor(float(candidate.get("base_score", 0.0) or 0.0), device=device),
                torch.tensor(float(candidate.get("partition_probability", 0.0) or 0.0), device=device),
                torch.tensor(1.0 / max(1.0, float(candidate.get("rank", 9999) or 9999)), device=device),
            ]
        )
        return self.head(scalars).squeeze(-1)

    def scores(self, row: dict[str, Any], device: torch.device, salt: str) -> torch.Tensor:
        return torch.stack([self.candidate_score(row, candidate, device, salt) for candidate in row.get("candidates", []) or []])


def score_split(model: TypedCompare, rows: list[dict[str, Any]], device: torch.device, alpha: float, salt: str) -> dict[str, Any]:
    answer = exact = recoverable = missing = 0
    mrr = 0.0
    with torch.no_grad():
        model.eval()
        for row in rows:
            candidates = row.get("candidates", []) or []
            if not candidates:
                continue
            label = label_index(row)
            if label >= 0:
                recoverable += 1
            module_scores = model.scores(row, device, salt).detach().cpu()
            base_scores = torch.tensor([float(c.get("base_score", 0.0) or 0.0) for c in candidates])
            scores = base_scores + float(alpha) * module_scores
            order = sorted(range(len(candidates)), key=lambda i: (-float(scores[i].item()), i))
            if label >= 0:
                mrr += 1.0 / float(order.index(label) + 1)
            if not order:
                missing += 1
                continue
            ans, ex = candidate_hit(candidates[order[0]])
            answer += ans
            exact += ex
    return {
        "rows": len(rows),
        "answer": answer,
        "exact": exact,
        "recoverable": recoverable,
        "missing": missing,
        "mrr": mrr / float(len(rows) or 1),
        "alpha": float(alpha),
    }


def train(args: argparse.Namespace) -> dict[str, Any]:
    random.seed(int(args.seed))
    torch.manual_seed(int(args.seed))
    device = torch.device(str(args.device))
    rows = rows_by_split(Path(args.targets_jsonl))
    model = TypedCompare(int(args.hash_buckets), int(args.embedding_dim)).to(device)
    opt = torch.optim.AdamW(model.parameters(), lr=float(args.learning_rate), weight_decay=float(args.weight_decay))
    train_rows = [row for row in rows["train"] if label_index(row) >= 0]
    if not train_rows:
        raise ValueError("no train relation rows with exact labels")
    history = []
    best_state = None
    best_key = None
    alphas = [float(x) for x in str(args.alpha_sweep).split(",") if x.strip()]
    for step in range(1, int(args.steps) + 1):
        batch = random.choices(train_rows, k=int(args.rows_per_step))
        losses = []
        model.train()
        for row in batch:
            label = label_index(row)
            if label < 0:
                continue
            scores = model.scores(row, device, str(args.hash_salt))
            losses.append(F.cross_entropy(scores.unsqueeze(0), torch.tensor([label], dtype=torch.long, device=device)))
        loss = torch.stack(losses).mean()
        opt.zero_grad(set_to_none=True)
        loss.backward()
        opt.step()
        if step == 1 or step == int(args.steps) or step % int(args.eval_every) == 0:
            cal = [score_split(model, rows["calibration"], device, alpha, str(args.hash_salt)) for alpha in alphas]
            selected = max(cal, key=lambda r: (r["answer"], r["exact"], r["mrr"]))
            history.append({"step": step, "loss": float(loss.detach().cpu().item()), "selected_calibration": selected})
            key = (selected["answer"], selected["exact"], selected["mrr"])
            if best_key is None or key > best_key:
                best_key = key
                best_state = {k: v.detach().cpu().clone() for k, v in model.state_dict().items()}
    if best_state is not None:
        model.load_state_dict(best_state)
    calibration = [score_split(model, rows["calibration"], device, alpha, str(args.hash_salt)) for alpha in alphas]
    selected = max(calibration, key=lambda r: (r["answer"], r["exact"], r["mrr"]))
    eval_selected = score_split(model, rows["eval"], device, float(selected["alpha"]), str(args.hash_salt))
    summary = {
        "artifact_kind": "stage955_typed_token_comparison_module",
        "targets_jsonl": str(Path(args.targets_jsonl).resolve()),
        "hash_buckets": int(args.hash_buckets),
        "embedding_dim": int(args.embedding_dim),
        "parameter_count": sum(p.numel() for p in model.parameters()),
        "steps": int(args.steps),
        "rows_per_step": int(args.rows_per_step),
        "history": history,
        "calibration_sweep": calibration,
        "calibration_selected": selected,
        "eval_with_calibration_selected": eval_selected,
        "stage944_relation_answer_exact": [52, 52],
        "stage944_nonrelation_answer_exact": [200, 183],
        "stage944_preserved_else_policy_answer_exact": [200 + eval_selected["answer"], 183 + eval_selected["exact"]],
        "caveat": "Uses Stage952 diagnostic qslot-patched relation surface. Accepted 100M-relevant claim requires qslot aliases generated from relation text without copied eval positive slots.",
    }
    output = Path(args.output_json)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    print(json.dumps(summary, indent=2, sort_keys=True))
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--targets-jsonl", default="runs/local/artifacts/stage952_relation_query_slot_patched_targets.jsonl")
    parser.add_argument("--device", default="cpu")
    parser.add_argument("--hash-buckets", type=int, default=4096)
    parser.add_argument("--embedding-dim", type=int, default=8)
    parser.add_argument("--hash-salt", default="stage955")
    parser.add_argument("--steps", type=int, default=240)
    parser.add_argument("--rows-per-step", type=int, default=32)
    parser.add_argument("--eval-every", type=int, default=60)
    parser.add_argument("--learning-rate", type=float, default=0.01)
    parser.add_argument("--weight-decay", type=float, default=0.001)
    parser.add_argument("--alpha-sweep", default="0,0.1,0.25,0.5,0.75,1,1.5,2,3,4,6,8,10")
    parser.add_argument("--seed", type=int, default=955)
    parser.add_argument("--output-json", required=True)
    train(parser.parse_args())


if __name__ == "__main__":
    main()
