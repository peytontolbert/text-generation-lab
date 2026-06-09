#!/usr/bin/env python3
"""Audit remaining Stage1056 composition misses against recoverable positives."""

from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path
from typing import Any

import torch


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"could not load {name}: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _iter_jsonl(path: Path):
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                yield json.loads(line)


def _rows_by_split(path: Path) -> dict[str, list[dict[str, Any]]]:
    rows: dict[str, list[dict[str, Any]]] = {}
    for row in _iter_jsonl(path):
        rows.setdefault(str(row.get("split", "unknown")), []).append(row)
    return rows


def _pair_probs_for_split(stage1052, pair_model, pair_examples: list[dict[str, Any]], vectors: dict[str, torch.Tensor], split: str) -> dict[tuple[str, int, int], dict[str, list[float]]]:
    out: dict[tuple[str, int, int], dict[str, list[float]]] = {}
    pair_model.eval()
    with torch.no_grad():
        for example in pair_examples:
            if str(example.get("split", "")) != split:
                continue
            features = stage1052._features(example, vectors).unsqueeze(0)
            prob = float(torch.sigmoid(pair_model(features)).item())
            key = (split, int(example["row_index"]), int(example["candidate_index"]))
            out.setdefault(key, {}).setdefault(str(example["pair_type"]), []).append(prob)
    return out


def _summarize_probs(probs: dict[str, list[float]]) -> dict[str, dict[str, float]]:
    out: dict[str, dict[str, float]] = {}
    for pair_type, values in sorted(probs.items()):
        xs = [float(x) for x in values]
        out[pair_type] = {
            "n": float(len(xs)),
            "max": max(xs) if xs else 0.0,
            "mean": sum(xs) / float(len(xs) or 1),
            "count_ge_05": float(sum(1 for x in xs if x >= 0.5)),
            "count_ge_07": float(sum(1 for x in xs if x >= 0.7)),
        }
    return out


def _score_composition_rows(
    stage1056,
    composer,
    rows: list[dict[str, Any]],
    split: str,
    pair_probs: dict[tuple[str, int, int], dict[str, list[float]]],
    alpha: float,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    stats = {
        "rows": 0,
        "positive_present": 0,
        "answer": 0,
        "exact": 0,
        "base_answer": 0,
        "base_exact": 0,
        "misses_with_positive_present": 0,
    }
    misses: list[dict[str, Any]] = []
    composer.eval()
    with torch.no_grad():
        for row_index, row in enumerate(rows):
            if str(row.get("operation", "")) != "composition":
                continue
            candidates = list(row.get("candidates", []) or [])
            if not candidates:
                continue
            stats["rows"] += 1
            row_features = torch.stack(
                [
                    stage1056._aggregate_features(row, candidate, pair_probs.get((split, row_index, candidate_index), {}))
                    for candidate_index, candidate in enumerate(candidates)
                ],
                dim=0,
            )
            base_scores = torch.tensor([float(c.get("base_score", 0.0) or 0.0) for c in candidates], dtype=torch.float32)
            learned_scores = composer(row_features)
            pred_idx = int(torch.argmax(base_scores + float(alpha) * learned_scores).item())
            base_idx = int(torch.argmax(base_scores).item())
            positive_indices = [idx for idx, candidate in enumerate(candidates) if bool(candidate.get("is_exact") or candidate.get("is_answer_match"))]
            exact_indices = [idx for idx, candidate in enumerate(candidates) if bool(candidate.get("is_exact"))]
            stats["positive_present"] += int(bool(positive_indices))
            stats["answer"] += int(pred_idx in positive_indices)
            stats["exact"] += int(pred_idx in exact_indices)
            stats["base_answer"] += int(base_idx in positive_indices)
            stats["base_exact"] += int(base_idx in exact_indices)
            if positive_indices and pred_idx not in positive_indices:
                stats["misses_with_positive_present"] += 1
                oracle_idx = positive_indices[0]
                pred_probs = pair_probs.get((split, row_index, pred_idx), {})
                oracle_probs = pair_probs.get((split, row_index, oracle_idx), {})
                misses.append(
                    {
                        "split": split,
                        "row_index": row_index,
                        "query_text": row.get("query_text", ""),
                        "candidate_count": len(candidates),
                        "pred_idx": pred_idx,
                        "oracle_idx": oracle_idx,
                        "pred_base_score": float(base_scores[pred_idx].item()),
                        "oracle_base_score": float(base_scores[oracle_idx].item()),
                        "pred_learned_score": float(learned_scores[pred_idx].item()),
                        "oracle_learned_score": float(learned_scores[oracle_idx].item()),
                        "pred_doc_text": candidates[pred_idx].get("doc_text", ""),
                        "oracle_doc_text": candidates[oracle_idx].get("doc_text", ""),
                        "pred_pair_probs": _summarize_probs(pred_probs),
                        "oracle_pair_probs": _summarize_probs(oracle_probs),
                    }
                )
    return stats, misses


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, default=_repo_root())
    parser.add_argument("--targets-jsonl", type=Path, default=Path("runs/local/artifacts/stage1043_operator_teacher_targets.jsonl"))
    parser.add_argument("--hidden-jsonl", type=Path, default=Path("runs/local/artifacts/stage1044_salted_hidden_no_anchor_targets.jsonl"))
    parser.add_argument("--classifier-state", type=Path, default=Path("runs/local/artifacts/stage1052_contrastive_span_pair_classifier_state.pt"))
    parser.add_argument("--composer-state", type=Path, default=Path("runs/local/artifacts/stage1056_pair_probability_candidate_composer_state.pt"))
    parser.add_argument("--output-json", type=Path, default=Path("runs/local/artifacts/stage1060_composition_gap_audit_summary.json"))
    parser.add_argument("--output-jsonl", type=Path, default=Path("runs/local/artifacts/stage1060_composition_gap_audit_misses.jsonl"))
    args = parser.parse_args()

    repo_root = args.repo_root.resolve()
    stage1056 = _load_module("stage1056", repo_root / "scripts/train_stage1056_pair_probability_candidate_composer.py")
    stage1052 = stage1056._load_stage1052(repo_root)
    pair_model, pair_examples, vectors = stage1056._load_pair_classifier(stage1052, args.classifier_state, repo_root)
    composer_state = torch.load(args.composer_state, map_location="cpu")
    composer = stage1056.CandidateComposer(5 * len(stage1056.PAIR_TYPES) + 2 + len(stage1056.OPS), 64)
    composer.load_state_dict(composer_state["state_dict"])
    alpha = float(composer_state["summary"]["calibration_selected"]["alpha"])

    rows = stage1056._rows_by_split(args.targets_jsonl)
    pair_probs = stage1056._pair_probabilities(stage1052, pair_model, pair_examples, vectors)
    eval_stats, eval_misses = _score_composition_rows(stage1056, composer, rows["eval"], "eval", pair_probs, alpha)
    hidden_rows = _rows_by_split(args.hidden_jsonl).get("hidden_eval", [])
    hidden_probs = _pair_probs_for_split(stage1052, pair_model, pair_examples, vectors, "hidden_eval")
    hidden_stats, hidden_misses = _score_composition_rows(stage1056, composer, hidden_rows, "hidden_eval", hidden_probs, alpha)

    all_misses = eval_misses + hidden_misses
    summary = {
        "artifact_kind": "stage1060_composition_gap_audit",
        "status": "completed_composition_gap_audit",
        "selected_alpha": alpha,
        "eval_composition": eval_stats,
        "hidden_composition": hidden_stats,
        "miss_jsonl": str(args.output_jsonl),
        "decision": "Audits recoverable composition rows missed by the Stage1056 learned composer. The gap is rows where the positive candidate is present but the learned slot/entity aggregate still chooses a competing composition candidate.",
    }
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    with args.output_jsonl.open("w", encoding="utf-8") as handle:
        for miss in all_misses:
            handle.write(json.dumps(miss, sort_keys=True) + "\n")
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
