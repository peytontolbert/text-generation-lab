#!/usr/bin/env python3
"""Train a tiny operation-conditioned pair-arity router from Stage965 labels."""

from __future__ import annotations

import argparse
import json
import random
from pathlib import Path
from typing import Any

import torch
import torch.nn.functional as F


def iter_jsonl(path: Path):
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                yield json.loads(line)


def load_rows(path: Path) -> dict[str, list[dict[str, Any]]]:
    rows: dict[str, list[dict[str, Any]]] = {"train": [], "calibration": [], "eval": []}
    for row in iter_jsonl(path):
        rows.setdefault(str(row.get("split")), []).append(row)
    return rows


def candidate_hit(candidate: dict[str, Any]) -> tuple[int, int]:
    return int(bool(candidate.get("is_exact") or candidate.get("is_answer_match"))), int(bool(candidate.get("is_exact")))


class PairArityRouter(torch.nn.Module):
    def __init__(self, operations: list[str], hidden_dim: int) -> None:
        super().__init__()
        self.operations = list(operations)
        self.op_to_idx = {op: idx for idx, op in enumerate(self.operations)}
        input_dim = len(self.operations) + 5
        self.net = torch.nn.Sequential(
            torch.nn.Linear(input_dim, hidden_dim),
            torch.nn.Tanh(),
            torch.nn.Linear(hidden_dim, 1),
        )

    def features(self, row: dict[str, Any], candidate: dict[str, Any], device: torch.device) -> torch.Tensor:
        op = str(row.get("operation"))
        one_hot = torch.zeros(len(self.operations), dtype=torch.float32, device=device)
        one_hot[self.op_to_idx[op]] = 1.0
        pair_overlap = float(candidate.get("pair_overlap_count", 0) or 0)
        selected_arity = float(candidate.get("selected_min_pair_overlap", 0) or 0)
        base_score = float(candidate.get("base_score", 0.0) or 0.0)
        rank = float(candidate.get("rank", 9999) or 9999)
        scalars = torch.tensor(
            [
                pair_overlap / 4.0,
                selected_arity / 4.0,
                base_score,
                1.0 / max(1.0, rank),
                1.0 if selected_arity > 0 else 0.0,
            ],
            dtype=torch.float32,
            device=device,
        )
        return torch.cat([one_hot, scalars], dim=0)

    def logit(self, row: dict[str, Any], candidate: dict[str, Any], device: torch.device) -> torch.Tensor:
        return self.net(self.features(row, candidate, device)).squeeze(-1)


def flatten_candidates(rows: list[dict[str, Any]]) -> list[tuple[dict[str, Any], dict[str, Any], float]]:
    examples = []
    for row in rows:
        for candidate in row.get("candidates", []) or []:
            examples.append((row, candidate, float(bool(candidate.get("arity_positive")))))
    return examples


def score_policy(
    model: PairArityRouter,
    rows: list[dict[str, Any]],
    *,
    device: torch.device,
    threshold: float,
    fallback_to_base: bool,
) -> dict[str, Any]:
    answer = exact = recoverable = missing = predicted_positive = 0
    by_operation: dict[str, dict[str, int]] = {}
    with torch.no_grad():
        model.eval()
        for row in rows:
            op = str(row.get("operation"))
            stats = by_operation.setdefault(op, {"rows": 0, "answer": 0, "exact": 0, "predicted_positive_rows": 0, "fallback_rows": 0})
            stats["rows"] += 1
            candidates = list(row.get("candidates", []) or [])
            recoverable += int(any(c.get("is_exact") for c in candidates))
            scored = []
            for candidate in candidates:
                prob = torch.sigmoid(model.logit(row, candidate, device)).item()
                if prob >= threshold:
                    scored.append((candidate, prob))
            if scored:
                predicted_positive += 1
                stats["predicted_positive_rows"] += 1
                pool = [candidate for candidate, _prob in scored]
            elif fallback_to_base:
                stats["fallback_rows"] += 1
                pool = candidates
            else:
                missing += 1
                continue
            if not pool:
                missing += 1
                continue
            top = max(pool, key=lambda c: (float(c.get("base_score", 0.0) or 0.0), -int(c.get("rank", 9999) or 9999)))
            ans, ex = candidate_hit(top)
            answer += ans
            exact += ex
            stats["answer"] += ans
            stats["exact"] += ex
    return {
        "rows": len(rows),
        "answer": answer,
        "exact": exact,
        "recoverable": recoverable,
        "missing": missing,
        "predicted_positive_rows": predicted_positive,
        "threshold": float(threshold),
        "fallback_to_base": bool(fallback_to_base),
        "by_operation": by_operation,
    }


def train(args: argparse.Namespace) -> dict[str, Any]:
    random.seed(int(args.seed))
    torch.manual_seed(int(args.seed))
    device = torch.device(str(args.device))
    rows = load_rows(Path(args.teacher_jsonl))
    operations = sorted({str(row.get("operation")) for split_rows in rows.values() for row in split_rows})
    model = PairArityRouter(operations, int(args.hidden_dim)).to(device)
    opt = torch.optim.AdamW(model.parameters(), lr=float(args.learning_rate), weight_decay=float(args.weight_decay))
    train_examples = flatten_candidates(rows["train"])
    if bool(args.include_calibration_in_train):
        train_examples += flatten_candidates(rows["calibration"])
    if not train_examples:
        raise ValueError("no training examples")

    positive_weight = float(args.positive_weight)
    history = []
    for step in range(1, int(args.steps) + 1):
        batch = random.choices(train_examples, k=int(args.batch_size))
        logits = []
        labels = []
        for row, candidate, label in batch:
            logits.append(model.logit(row, candidate, device))
            labels.append(label)
        logit_tensor = torch.stack(logits)
        label_tensor = torch.tensor(labels, dtype=torch.float32, device=device)
        weights = torch.where(label_tensor > 0.5, torch.full_like(label_tensor, positive_weight), torch.ones_like(label_tensor))
        loss = F.binary_cross_entropy_with_logits(logit_tensor, label_tensor, weight=weights)
        opt.zero_grad(set_to_none=True)
        loss.backward()
        opt.step()
        if step == 1 or step == int(args.steps) or step % int(args.eval_every) == 0:
            history.append({"step": step, "loss": float(loss.detach().cpu().item())})

    thresholds = [float(x) for x in str(args.threshold_sweep).split(",") if x.strip()]
    calibration = [
        score_policy(model, rows["calibration"], device=device, threshold=threshold, fallback_to_base=bool(args.fallback_to_base))
        for threshold in thresholds
    ]
    selected = max(calibration, key=lambda score: (score["answer"], score["exact"], -abs(score["predicted_positive_rows"] - 187)))
    eval_score = score_policy(
        model,
        rows["eval"],
        device=device,
        threshold=float(selected["threshold"]),
        fallback_to_base=bool(args.fallback_to_base),
    )
    model_state_path = Path(args.model_state)
    model_state_path.parent.mkdir(parents=True, exist_ok=True)
    torch.save(
        {
            "state_dict": model.state_dict(),
            "operations": operations,
            "hidden_dim": int(args.hidden_dim),
            "threshold": float(selected["threshold"]),
            "fallback_to_base": bool(args.fallback_to_base),
            "feature_contract": [
                "operation_one_hot",
                "pair_overlap_count / 4",
                "selected_min_pair_overlap / 4",
                "base_score",
                "rank_reciprocal",
                "active_pair_policy_flag",
            ],
        },
        model_state_path,
    )
    summary = {
        "artifact_kind": "stage966_pair_arity_router",
        "status": "completed_learned_router_probe",
        "teacher_jsonl": str(Path(args.teacher_jsonl)),
        "model_state": str(model_state_path),
        "operations": operations,
        "parameter_count": sum(p.numel() for p in model.parameters()),
        "hidden_dim": int(args.hidden_dim),
        "steps": int(args.steps),
        "batch_size": int(args.batch_size),
        "positive_weight": positive_weight,
        "history": history,
        "calibration_sweep": calibration,
        "calibration_selected": selected,
        "eval_with_calibration_selected": eval_score,
        "implied_full_answer_exact": [230 + eval_score["answer"], 229 + eval_score["exact"]],
        "comparisons": {
            "stage944_target_answer_exact": [252, 235],
            "stage964_target_answer_exact": [328, 311],
            "stage964_implied_full_answer_exact": [558, 540],
        },
        "caveat": "Uses pair_overlap_count as a declared primitive feature. This tests learned arity/fallback routing, not learned token equality.",
    }
    output = Path(args.output_json)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(output), "eval": eval_score, "implied_full": summary["implied_full_answer_exact"], "params": summary["parameter_count"]}, indent=2, sort_keys=True))
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--teacher-jsonl", default="runs/local/artifacts/stage965_operation_pair_arity_teacher.jsonl")
    parser.add_argument("--output-json", default="runs/local/artifacts/stage966_pair_arity_router_summary.json")
    parser.add_argument("--model-state", default="runs/local/artifacts/stage966_pair_arity_router_state.pt")
    parser.add_argument("--device", default="cpu")
    parser.add_argument("--hidden-dim", type=int, default=8)
    parser.add_argument("--steps", type=int, default=400)
    parser.add_argument("--batch-size", type=int, default=128)
    parser.add_argument("--eval-every", type=int, default=100)
    parser.add_argument("--learning-rate", type=float, default=0.02)
    parser.add_argument("--weight-decay", type=float, default=0.001)
    parser.add_argument("--positive-weight", type=float, default=4.0)
    parser.add_argument("--threshold-sweep", default="0.05,0.1,0.15,0.2,0.25,0.3,0.35,0.4,0.45,0.5,0.55,0.6,0.65,0.7,0.75,0.8,0.85,0.9,0.95")
    parser.add_argument("--fallback-to-base", action="store_true", default=True)
    parser.add_argument("--include-calibration-in-train", action="store_true")
    parser.add_argument("--seed", type=int, default=966)
    train(parser.parse_args())


if __name__ == "__main__":
    main()
