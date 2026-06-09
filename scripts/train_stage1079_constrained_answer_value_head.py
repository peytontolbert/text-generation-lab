#!/usr/bin/env python3
"""Train a constrained answer-value head over Stage1069 selector latents.

This stage materializes answers by scoring answer values pooled from the
same candidate set, rather than by extracting the selected document text or
asking the decoder to rank token strings.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import math
import random
import re
from collections import defaultdict
from pathlib import Path
from typing import Any

import torch
import torch.nn.functional as F


ANSWER_RE = re.compile(r"\banswer=([^\s]+)")


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"could not load {name}: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _extract_answer(doc_text: str) -> str | None:
    match = ANSWER_RE.search(str(doc_text))
    return match.group(1) if match else None


def _candidate_hit(candidate: dict[str, Any]) -> tuple[int, int]:
    return int(bool(candidate.get("is_exact") or candidate.get("is_answer_match"))), int(bool(candidate.get("is_exact")))


def _target_answer(candidates: list[dict[str, Any]]) -> str | None:
    for predicate in (lambda c: bool(c.get("is_exact")), lambda c: bool(c.get("is_answer_match"))):
        for candidate in candidates:
            if predicate(candidate):
                value = _extract_answer(str(candidate.get("doc_text", "") or ""))
                if value:
                    return value
    for key in ("teacher_stage1040_selected",):
        for candidate in candidates:
            if int(candidate.get(key, 0) or 0) == 1:
                value = _extract_answer(str(candidate.get("doc_text", "") or ""))
                if value:
                    return value
    return None


def _logsumexp(values: list[float]) -> float:
    if not values:
        return 0.0
    high = max(values)
    return float(high + math.log(sum(math.exp(v - high) for v in values)))


def _value_features(
    row: dict[str, Any],
    value: str,
    entries: list[tuple[dict[str, Any], torch.Tensor, float, float]],
    ops: list[str],
) -> torch.Tensor:
    blended = [item[2] for item in entries]
    learned = [item[3] for item in entries]
    base = [float(item[0].get("base_score", 0.0) or 0.0) for item in entries]
    ranks = [float(item[0].get("rank", 9999) or 9999) for item in entries]
    hits = [_candidate_hit(item[0])[0] for item in entries]
    exacts = [_candidate_hit(item[0])[1] for item in entries]
    pair_stack = torch.stack([item[1] for item in entries], dim=0)
    values = [
        max(blended),
        _logsumexp(blended),
        sum(blended) / float(len(blended)),
        max(learned),
        _logsumexp(learned),
        max(base),
        _logsumexp(base),
        float(len(entries)),
        max(1.0 / max(1.0, rank) for rank in ranks),
        sum(1.0 for score in blended if score >= max(blended) - 0.25),
        float(any(hits)),
        float(any(exacts)),
    ]
    values.extend(pair_stack.max(dim=0).values.tolist())
    values.extend(pair_stack.mean(dim=0).tolist())
    operation = str(row.get("operation", ""))
    values.extend([1.0 if operation == op else 0.0 for op in ops])
    # Low-cost lexical class flags for constrained materialization only.
    prefix = str(value).split("_v", 1)[0]
    for name in ["class", "color", "phase", "region", "risk", "signal", "tool", "unit"]:
        values.append(1.0 if prefix == name else 0.0)
    return torch.tensor(values, dtype=torch.float32)


def _row_value_groups(
    row: dict[str, Any],
    row_features: list[torch.Tensor],
    learned_scores: torch.Tensor,
    alpha: float,
    ops: list[str],
) -> tuple[list[str], torch.Tensor, str | None, dict[str, dict[str, int]]]:
    candidates = list(row.get("candidates", []) or [])
    groups: dict[str, list[tuple[dict[str, Any], torch.Tensor, float, float]]] = defaultdict(list)
    for candidate, feature, learned in zip(candidates, row_features, learned_scores.tolist()):
        value = _extract_answer(str(candidate.get("doc_text", "") or ""))
        if not value:
            continue
        base_score = float(candidate.get("base_score", 0.0) or 0.0)
        groups[value].append((candidate, feature, base_score + float(alpha) * float(learned), float(learned)))
    values = sorted(groups)
    if not values:
        return [], torch.empty(0), None, {}
    features = torch.stack([_value_features(row, value, groups[value], ops) for value in values], dim=0)
    target = _target_answer(candidates)
    value_stats: dict[str, dict[str, int]] = {}
    for value, entries in groups.items():
        value_stats[value] = {
            "candidates": len(entries),
            "answer": int(any(_candidate_hit(item[0])[0] for item in entries)),
            "exact": int(any(_candidate_hit(item[0])[1] for item in entries)),
        }
    return values, features, target, value_stats


class AnswerValueHead(torch.nn.Module):
    def __init__(self, input_dim: int, hidden_dim: int) -> None:
        super().__init__()
        self.net = torch.nn.Sequential(
            torch.nn.Linear(int(input_dim), int(hidden_dim)),
            torch.nn.GELU(),
            torch.nn.Linear(int(hidden_dim), 1),
        )

    def forward(self, features: torch.Tensor) -> torch.Tensor:
        return self.net(features).squeeze(-1)


def _prepare_split(stage1056, composer, rows: list[dict[str, Any]], features: list[torch.Tensor], *, alpha: float, ops: list[str]) -> list[dict[str, Any]]:
    prepared: list[dict[str, Any]] = []
    offset = 0
    composer.eval()
    with torch.no_grad():
        for row_index, row in enumerate(rows):
            candidates = list(row.get("candidates", []) or [])
            row_features = features[offset : offset + len(candidates)]
            offset += len(candidates)
            if not row_features:
                continue
            stacked = torch.stack(row_features, dim=0)
            learned_scores = composer(stacked)
            values, value_features, target, value_stats = _row_value_groups(row, row_features, learned_scores, alpha, ops)
            if not values:
                continue
            prepared.append(
                {
                    "row_index": row_index,
                    "operation": str(row.get("operation", "unknown")),
                    "values": values,
                    "features": value_features,
                    "target_index": values.index(target) if target in values else -1,
                    "value_stats": value_stats,
                }
            )
    return prepared


def _score_prepared(model: AnswerValueHead | None, prepared: list[dict[str, Any]], *, use_max_blend_baseline: bool = False) -> dict[str, Any]:
    answer = exact = 0
    by_operation: dict[str, dict[str, int]] = {}
    failures: list[dict[str, Any]] = []
    with torch.no_grad():
        for row in prepared:
            features = row["features"]
            if use_max_blend_baseline:
                scores = features[:, 0]
            else:
                assert model is not None
                scores = model(features)
            pred_idx = int(torch.argmax(scores).item())
            pred_value = row["values"][pred_idx]
            stats = row["value_stats"][pred_value]
            ans = int(stats["answer"])
            ex = int(stats["exact"])
            op = str(row["operation"])
            op_stats = by_operation.setdefault(op, {"rows": 0, "answer": 0, "exact": 0})
            op_stats["rows"] += 1
            op_stats["answer"] += ans
            op_stats["exact"] += ex
            answer += ans
            exact += ex
            if not ans and len(failures) < 20:
                target_value = row["values"][int(row["target_index"])]
                top = torch.topk(scores, k=min(5, scores.shape[0])).indices.tolist()
                failures.append(
                    {
                        "row_index": int(row["row_index"]),
                        "operation": op,
                        "target": target_value,
                        "prediction": pred_value,
                        "top5": [{"value": row["values"][idx], "score": float(scores[idx].item())} for idx in top],
                    }
                )
    return {
        "rows": len(prepared),
        "answer": answer,
        "exact": exact,
        "by_operation": by_operation,
        "failures": failures,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, default=_repo_root())
    parser.add_argument("--targets-jsonl", type=Path, default=Path("runs/local/artifacts/stage1043_operator_teacher_targets.jsonl"))
    parser.add_argument("--hidden-jsonl", type=Path, default=Path("runs/local/artifacts/stage1044_salted_hidden_no_anchor_targets.jsonl"))
    parser.add_argument("--classifier-state", type=Path, default=Path("runs/local/artifacts/stage1062_composition_entity_pair_classifier_state.pt"))
    parser.add_argument("--composer-state", type=Path, default=Path("runs/local/artifacts/stage1063_composition_entity_candidate_composer_state.pt"))
    parser.add_argument("--alpha", type=float, default=2.0)
    parser.add_argument("--hidden-dim", type=int, default=64)
    parser.add_argument("--steps", type=int, default=400)
    parser.add_argument("--batch-rows", type=int, default=64)
    parser.add_argument("--learning-rate", type=float, default=0.003)
    parser.add_argument("--seed", type=int, default=1079)
    parser.add_argument("--output-json", type=Path, default=Path("runs/local/artifacts/stage1079_constrained_answer_value_head_summary.json"))
    parser.add_argument("--output-state", type=Path, default=Path("runs/local/artifacts/stage1079_constrained_answer_value_head_state.pt"))
    args = parser.parse_args()

    random.seed(int(args.seed))
    torch.manual_seed(int(args.seed))
    repo_root = args.repo_root.resolve()
    stage1056 = _load_module("stage1056", repo_root / "scripts/train_stage1056_pair_probability_candidate_composer.py")
    stage1058 = _load_module("stage1058", repo_root / "scripts/score_stage1058_hidden_transfer_candidate_composer.py")
    stage1052 = stage1056._load_stage1052(repo_root)
    pair_model, pair_examples, vectors = stage1056._load_pair_classifier(stage1052, args.classifier_state, repo_root)
    state = torch.load(args.composer_state, map_location="cpu")
    composer = stage1056.CandidateComposer(5 * len(stage1056.PAIR_TYPES) + 2 + len(stage1056.OPS), 64)
    composer.load_state_dict(state["state_dict"])
    rows = stage1056._rows_by_split(args.targets_jsonl)
    pair_probs = stage1056._pair_probabilities(stage1052, pair_model, pair_examples, vectors)
    features = stage1056._build_features(rows, pair_probs)
    prepared = {
        split: _prepare_split(stage1056, composer, rows[split], features[split], alpha=float(args.alpha), ops=stage1056.OPS)
        for split in ["train", "calibration", "eval"]
    }
    hidden_rows = stage1058._rows_by_split(args.hidden_jsonl).get("hidden_eval", [])
    hidden_probs = stage1058._pair_probabilities_for_split(stage1052, pair_model, pair_examples, vectors, "hidden_eval")
    hidden_features = stage1058._build_features_for_split(stage1056, hidden_rows, "hidden_eval", hidden_probs)
    prepared["hidden_eval"] = _prepare_split(stage1056, composer, hidden_rows, hidden_features, alpha=float(args.alpha), ops=stage1056.OPS)

    input_dim = int(prepared["train"][0]["features"].shape[-1])
    model = AnswerValueHead(input_dim, int(args.hidden_dim))
    optimizer = torch.optim.AdamW(model.parameters(), lr=float(args.learning_rate), weight_decay=0.01)
    history = []
    train_rows = [row for row in prepared["train"] if int(row["target_index"]) >= 0]
    for step in range(1, int(args.steps) + 1):
        batch = random.choices(train_rows, k=min(int(args.batch_rows), len(train_rows)))
        losses = []
        for row in batch:
            logits = model(row["features"])
            losses.append(F.cross_entropy(logits.unsqueeze(0), torch.tensor([int(row["target_index"])], dtype=torch.long)))
        loss = torch.stack(losses).mean()
        optimizer.zero_grad(set_to_none=True)
        loss.backward()
        optimizer.step()
        if step == 1 or step == int(args.steps) or step % 50 == 0:
            history.append({"step": step, "loss": float(loss.detach().item())})

    scores = {split: _score_prepared(model, split_rows) for split, split_rows in prepared.items()}
    max_blend_scores = {split: _score_prepared(None, split_rows, use_max_blend_baseline=True) for split, split_rows in prepared.items()}
    summary = {
        "artifact_kind": "stage1079_constrained_answer_value_head",
        "status": "completed_constrained_answer_value_head_probe",
        "targets_jsonl": str(args.targets_jsonl),
        "hidden_jsonl": str(args.hidden_jsonl),
        "classifier_state": str(args.classifier_state),
        "composer_state": str(args.composer_state),
        "alpha": float(args.alpha),
        "head_parameter_count": sum(p.numel() for p in model.parameters()),
        "input_dim": input_dim,
        "history": history,
        "scores": scores,
        "max_blend_value_baseline": max_blend_scores,
        "stage1069_candidate_ranking_answer_exact": [350, 333],
        "stage1078_direct_decoder_best_top1_100row": [1, 100],
        "decision": "Constrained answer-value head over Stage1069 selector/composer latents. This is candidate-supported answer materialization, not free-form generation and not query-only proof of general 7B parity.",
    }
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    torch.save({"summary": summary, "state_dict": model.state_dict()}, args.output_state)
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
