#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import random
from typing import Any

import torch
import torch.nn.functional as F


KINDS = ("ent", "pair", "slot", "claim", "proof")


def _iter_jsonl(path: Path) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def _rows_by_split(rows: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    out = {"train": [], "calibration": [], "eval": []}
    for row in rows:
        split = str(row.get("split", ""))
        if split in out:
            out[split].append(row)
    return out


def _bucket(value: str, buckets: int, *, salt: str) -> int:
    if not value:
        return 0
    digest = hashlib.blake2b(f"{salt}:{value}".encode("utf-8"), digest_size=8).digest()
    return 1 + (int.from_bytes(digest, "little") % max(1, int(buckets) - 1))


def _make_tables(buckets: int, dim: int, seed: int) -> dict[str, torch.Tensor]:
    generator = torch.Generator(device="cpu")
    generator.manual_seed(int(seed))
    tables = {}
    for kind in KINDS:
        table = torch.randn((int(buckets), int(dim)), generator=generator)
        table[0].zero_()
        tables[kind] = F.normalize(table, dim=-1)
    return tables


def _max_similarity(table: torch.Tensor, left: list[str], right: list[str], *, buckets: int, salt: str) -> float:
    if not left or not right:
        return 0.0
    left_ids = [_bucket(value, buckets, salt=salt) for value in left]
    right_ids = [_bucket(value, buckets, salt=salt) for value in right]
    best = -1.0
    for left_id in left_ids:
        for right_id in right_ids:
            score = float((table[left_id] * table[right_id]).sum().item())
            best = max(best, score)
    return best


def _operation_list(rows: dict[str, list[dict[str, Any]]]) -> list[str]:
    return sorted({str(row.get("operation", "") or "unknown") for split_rows in rows.values() for row in split_rows})


def _label(candidates: list[dict[str, Any]]) -> int:
    for index, candidate in enumerate(candidates):
        if bool(candidate.get("is_exact")):
            return index
    for index, candidate in enumerate(candidates):
        if bool(candidate.get("is_answer_match")):
            return index
    return -1


def _candidate_features(
    row: dict[str, Any],
    candidate: dict[str, Any],
    *,
    rank: int,
    selected_count: int,
    operations: list[str],
    tables: dict[str, torch.Tensor],
    buckets: int,
    hash_salt_prefix: str,
) -> list[float]:
    bridge = dict(candidate.get("bridge", {}) or {})
    sims = []
    presences = []
    for kind in KINDS:
        q_values = list(bridge.get(f"q{kind}", []) or [])
        d_values = list(bridge.get(f"d{kind}", []) or [])
        sims.append(_max_similarity(tables[kind], q_values, d_values, buckets=int(buckets), salt=f"{hash_salt_prefix}:{kind}"))
        presences.extend([1.0 if q_values else 0.0, 1.0 if d_values else 0.0])
    op = str(row.get("operation", "") or "unknown")
    op_features = [1.0 if op == candidate_op else 0.0 for candidate_op in operations]
    return [
        float(candidate.get("base_score", 0.0) or 0.0),
        float(candidate.get("partition_probability", 0.0) or 0.0),
        float(rank) / float(max(1, selected_count)),
        1.0 / float(max(1, rank)),
        *sims,
        *presences,
        *op_features,
    ]


def _prepare_split(
    split_rows: list[dict[str, Any]],
    *,
    operations: list[str],
    tables: dict[str, torch.Tensor],
    buckets: int,
    hash_salt_prefix: str,
) -> list[dict[str, Any]]:
    out = []
    for row in split_rows:
        candidates = list(row.get("candidates", []) or [])
        selected_count = len(candidates)
        features = [
            _candidate_features(
                row,
                candidate,
                rank=index + 1,
                selected_count=selected_count,
                operations=operations,
                tables=tables,
                buckets=int(buckets),
                hash_salt_prefix=hash_salt_prefix,
            )
            for index, candidate in enumerate(candidates)
        ]
        out.append({"row": row, "features": features, "label": _label(candidates)})
    return out


class BindingHead(torch.nn.Module):
    def __init__(self, input_dim: int, hidden_dim: int) -> None:
        super().__init__()
        if int(hidden_dim) <= 0:
            self.net = torch.nn.Linear(int(input_dim), 1)
        else:
            self.net = torch.nn.Sequential(
                torch.nn.Linear(int(input_dim), int(hidden_dim)),
                torch.nn.GELU(),
                torch.nn.Linear(int(hidden_dim), 1),
            )
        for module in self.modules():
            if isinstance(module, torch.nn.Linear):
                torch.nn.init.xavier_uniform_(module.weight)
                torch.nn.init.zeros_(module.bias)

    def forward(self, features: torch.Tensor) -> torch.Tensor:
        return self.net(features).squeeze(-1)


def _score_split(model: BindingHead, rows: list[dict[str, Any]], device: torch.device) -> dict[str, Any]:
    answer = exact = recoverable_answer = recoverable_exact = base_answer = base_exact = 0
    mrr = 0.0
    by_operation: dict[str, dict[str, int]] = {}
    with torch.no_grad():
        for item in rows:
            row = item["row"]
            candidates = list(row.get("candidates", []) or [])
            if not candidates:
                continue
            op = str(row.get("operation", "") or "unknown")
            stats = by_operation.setdefault(op, {"examples": 0, "answer": 0, "exact": 0, "base_answer": 0, "base_exact": 0})
            stats["examples"] += 1
            features = torch.tensor(item["features"], dtype=torch.float32, device=device)
            scores = model(features).detach().cpu()
            base_scores = torch.tensor([float(candidate.get("base_score", 0.0) or 0.0) for candidate in candidates])
            order = sorted(range(len(candidates)), key=lambda idx: (-float(scores[idx].item()), idx))
            base_order = sorted(range(len(candidates)), key=lambda idx: (-float(base_scores[idx].item()), idx))
            label = int(item["label"])
            if label >= 0:
                mrr += 1.0 / float(order.index(label) + 1)
            recoverable_answer += int(any(bool(c.get("is_exact")) or bool(c.get("is_answer_match")) for c in candidates))
            recoverable_exact += int(any(bool(c.get("is_exact")) for c in candidates))
            top = candidates[order[0]]
            base_top = candidates[base_order[0]]
            top_answer = bool(top.get("is_exact")) or bool(top.get("is_answer_match"))
            base_top_answer = bool(base_top.get("is_exact")) or bool(base_top.get("is_answer_match"))
            answer += int(top_answer)
            exact += int(bool(top.get("is_exact")))
            base_answer += int(base_top_answer)
            base_exact += int(bool(base_top.get("is_exact")))
            stats["answer"] += int(top_answer)
            stats["exact"] += int(bool(top.get("is_exact")))
            stats["base_answer"] += int(base_top_answer)
            stats["base_exact"] += int(bool(base_top.get("is_exact")))
    total = len(rows)
    return {
        "examples": total,
        "answer_correct": answer,
        "exact_correct": exact,
        "answer_recoverable": recoverable_answer,
        "exact_recoverable": recoverable_exact,
        "base_answer_correct": base_answer,
        "base_exact_correct": base_exact,
        "mrr": mrr / float(total or 1),
        "by_operation": by_operation,
    }


def train(args: argparse.Namespace) -> dict[str, Any]:
    random.seed(int(args.seed))
    torch.manual_seed(int(args.seed))
    device = torch.device(str(args.device))
    rows = _rows_by_split(_iter_jsonl(Path(args.targets_jsonl)))
    operations = _operation_list(rows)
    tables = _make_tables(int(args.hash_buckets), int(args.hash_dim), int(args.seed))
    prepared = {
        split: _prepare_split(
            split_rows,
            operations=operations,
            tables=tables,
            buckets=int(args.hash_buckets),
            hash_salt_prefix=str(
                {
                    "train": args.train_hash_salt,
                    "calibration": args.calibration_hash_salt,
                    "eval": args.eval_hash_salt,
                }[split]
            ),
        )
        for split, split_rows in rows.items()
    }
    input_dim = len(prepared["train"][0]["features"][0])
    model = BindingHead(input_dim, int(args.hidden_dim)).to(device)
    optimizer = torch.optim.AdamW(model.parameters(), lr=float(args.learning_rate), weight_decay=float(args.weight_decay))
    train_rows = [row for row in prepared["train"] if int(row["label"]) >= 0]
    order = list(range(len(train_rows)))
    best_state = None
    best_key = None
    history = []
    for step in range(1, int(args.steps) + 1):
        random.shuffle(order)
        losses = []
        for row_id in order[: int(args.rows_per_step)]:
            item = train_rows[row_id]
            scores = model(torch.tensor(item["features"], dtype=torch.float32, device=device))
            losses.append(F.cross_entropy(scores.unsqueeze(0), torch.tensor([int(item["label"])], dtype=torch.long, device=device)))
        loss = torch.stack(losses).mean()
        optimizer.zero_grad(set_to_none=True)
        loss.backward()
        optimizer.step()
        if step == 1 or step == int(args.steps) or step % int(args.eval_every) == 0:
            calibration = _score_split(model, prepared["calibration"], device)
            history.append({"step": step, "loss": float(loss.detach().cpu().item()), "calibration_answer": calibration["answer_correct"], "calibration_exact": calibration["exact_correct"], "calibration_mrr": calibration["mrr"]})
            key = (calibration["answer_correct"], calibration["exact_correct"], calibration["mrr"])
            if best_key is None or key > best_key:
                best_key = key
                best_state = {name: value.detach().cpu().clone() for name, value in model.state_dict().items()}
    if best_state is not None:
        model.load_state_dict(best_state)
    summary = {
        "artifact_kind": "stage908_broad_binding_comparison_head",
        "targets_jsonl": str(Path(args.targets_jsonl).resolve()),
        "operations": operations,
        "hash_buckets": int(args.hash_buckets),
        "hash_dim": int(args.hash_dim),
        "hash_salts": {
            "train": str(args.train_hash_salt),
            "calibration": str(args.calibration_hash_salt),
            "eval": str(args.eval_hash_salt),
        },
        "hidden_dim": int(args.hidden_dim),
        "parameter_count": sum(parameter.numel() for parameter in model.parameters()),
        "input_dim": input_dim,
        "steps": int(args.steps),
        "rows_per_step": int(args.rows_per_step),
        "history": history,
        "train": _score_split(model, prepared["train"], device),
        "calibration": _score_split(model, prepared["calibration"], device),
        "eval": _score_split(model, prepared["eval"], device),
        "decision_hint": "Uses frozen deterministic suffix-similarity features for ent/pair/slot/claim/proof plus base/prob/rank/op. No binary equality flags are provided.",
    }
    output = Path(args.output_json)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--targets-jsonl", required=True)
    parser.add_argument("--device", default="cpu")
    parser.add_argument("--hash-buckets", type=int, default=65536)
    parser.add_argument("--hash-dim", type=int, default=64)
    parser.add_argument("--hidden-dim", type=int, default=16)
    parser.add_argument("--steps", type=int, default=400)
    parser.add_argument("--rows-per-step", type=int, default=128)
    parser.add_argument("--eval-every", type=int, default=50)
    parser.add_argument("--learning-rate", type=float, default=0.005)
    parser.add_argument("--weight-decay", type=float, default=0.01)
    parser.add_argument("--seed", type=int, default=908)
    parser.add_argument("--train-hash-salt", default="")
    parser.add_argument("--calibration-hash-salt", default="")
    parser.add_argument("--eval-hash-salt", default="")
    parser.add_argument("--output-json", required=True)
    train(parser.parse_args())


if __name__ == "__main__":
    main()
