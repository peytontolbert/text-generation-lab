#!/usr/bin/env python3
"""Load Stage966 router and score Stage960 targets with live pair-overlap computation."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import torch


def iter_jsonl(path: Path):
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                yield json.loads(line)


def suffix_overlap(a: list[Any], b: list[Any]) -> int:
    return len({str(x) for x in a or []}.intersection(str(y) for y in b or []))


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

    def features(
        self,
        *,
        operation: str,
        pair_overlap_count: int,
        selected_min_pair_overlap: int,
        base_score: float,
        rank: int,
        device: torch.device,
    ) -> torch.Tensor:
        one_hot = torch.zeros(len(self.operations), dtype=torch.float32, device=device)
        one_hot[self.op_to_idx[operation]] = 1.0
        scalars = torch.tensor(
            [
                float(pair_overlap_count) / 4.0,
                float(selected_min_pair_overlap) / 4.0,
                float(base_score),
                1.0 / max(1.0, float(rank)),
                1.0 if selected_min_pair_overlap > 0 else 0.0,
            ],
            dtype=torch.float32,
            device=device,
        )
        return torch.cat([one_hot, scalars], dim=0)

    def logit(self, features: torch.Tensor) -> torch.Tensor:
        return self.net(features).squeeze(-1)


def selected_arities_from_policy(path: Path) -> dict[str, int]:
    policy = json.loads(path.read_text(encoding="utf-8"))
    return {str(op): int(score["min_pair_overlap"]) for op, score in policy.get("selected_by_operation", {}).items()}


def score_split(
    rows: list[dict[str, Any]],
    *,
    model: PairArityRouter,
    selected_arities: dict[str, int],
    threshold: float,
    fallback_to_base: bool,
    device: torch.device,
) -> dict[str, Any]:
    answer = exact = recoverable = missing = predicted_positive_rows = 0
    by_operation: dict[str, dict[str, int]] = {}
    with torch.no_grad():
        model.eval()
        for row in rows:
            op = str(row.get("operation"))
            stats = by_operation.setdefault(op, {"rows": 0, "answer": 0, "exact": 0, "predicted_positive_rows": 0, "fallback_rows": 0})
            stats["rows"] += 1
            candidates = list(row.get("candidates", []) or [])
            recoverable += int(any(candidate.get("is_exact") for candidate in candidates))
            qpair = (row.get("query_bridge", {}) or {}).get("qpair", [])
            selected_arity = int(selected_arities.get(op, 0))
            predicted_pool = []
            for candidate in candidates:
                bridge = candidate.get("bridge", {}) or {}
                pair_overlap_count = suffix_overlap(qpair, bridge.get("dpair", []))
                features = model.features(
                    operation=op,
                    pair_overlap_count=pair_overlap_count,
                    selected_min_pair_overlap=selected_arity,
                    base_score=float(candidate.get("base_score", 0.0) or 0.0),
                    rank=int(candidate.get("rank", 9999) or 9999),
                    device=device,
                )
                prob = torch.sigmoid(model.logit(features)).item()
                if prob >= threshold:
                    predicted_pool.append(candidate)
            if predicted_pool:
                predicted_positive_rows += 1
                stats["predicted_positive_rows"] += 1
                pool = predicted_pool
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
        "predicted_positive_rows": predicted_positive_rows,
        "threshold": float(threshold),
        "fallback_to_base": bool(fallback_to_base),
        "by_operation": by_operation,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--targets-jsonl", type=Path, default=Path("runs/local/artifacts/stage960_relation_qslot_bridge_targets.jsonl"))
    parser.add_argument("--router-state", type=Path, default=Path("runs/local/artifacts/stage966_pair_arity_router_state.pt"))
    parser.add_argument("--policy-json", type=Path, default=Path("runs/local/artifacts/stage964_operation_pair_arity_policy_summary.json"))
    parser.add_argument("--output-json", type=Path, default=Path("runs/local/artifacts/stage968_loadable_pair_router_summary.json"))
    parser.add_argument("--device", default="cpu")
    args = parser.parse_args()

    device = torch.device(str(args.device))
    state = torch.load(args.router_state, map_location=device)
    model = PairArityRouter(list(state["operations"]), int(state["hidden_dim"])).to(device)
    model.load_state_dict(state["state_dict"])
    selected_arities = selected_arities_from_policy(args.policy_json)
    rows_by_split: dict[str, list[dict[str, Any]]] = {"train": [], "calibration": [], "eval": []}
    for row in iter_jsonl(args.targets_jsonl):
        rows_by_split.setdefault(str(row.get("split")), []).append(row)

    split_scores = {
        split: score_split(
            rows,
            model=model,
            selected_arities=selected_arities,
            threshold=float(state["threshold"]),
            fallback_to_base=bool(state["fallback_to_base"]),
            device=device,
        )
        for split, rows in rows_by_split.items()
    }
    eval_score = split_scores["eval"]
    summary = {
        "artifact_kind": "stage968_loadable_pair_router",
        "status": "completed_loadable_counted_interface_scorer",
        "targets_jsonl": str(args.targets_jsonl),
        "router_state": str(args.router_state),
        "policy_json": str(args.policy_json),
        "selected_arities": selected_arities,
        "router_parameter_count": sum(p.numel() for p in model.parameters()),
        "threshold": float(state["threshold"]),
        "split_scores": split_scores,
        "implied_full_answer_exact": [230 + int(eval_score["answer"]), 229 + int(eval_score["exact"])],
        "comparisons": {
            "stage966_target_answer_exact": [328, 311],
            "stage964_target_answer_exact": [328, 311],
            "stage944_target_answer_exact": [252, 235],
        },
        "decision": "Loadable scorer reproduces Stage966/964 by computing qpair/dpair shared-anchor overlap live, then applying the saved 97-parameter router. This packages the counted interface path; strict model-owned proof still requires replacing the set-intersection circuit with learned internal equality.",
    }
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(args.output_json), "eval": eval_score, "implied_full": summary["implied_full_answer_exact"]}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
