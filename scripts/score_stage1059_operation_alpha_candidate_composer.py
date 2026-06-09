#!/usr/bin/env python3
"""Calibrate Stage1056 candidate-composer blend alpha per operation."""

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


def _candidate_hit(candidate: dict[str, Any]) -> tuple[int, int]:
    return int(bool(candidate.get("is_exact") or candidate.get("is_answer_match"))), int(bool(candidate.get("is_exact")))


def _score_rows(model, rows: list[dict[str, Any]], features: list[torch.Tensor], alpha_by_op: dict[str, float]) -> dict[str, Any]:
    answer = exact = base_answer = base_exact = 0
    by_operation: dict[str, dict[str, int]] = {}
    offset = 0
    model.eval()
    with torch.no_grad():
        for row in rows:
            candidates = list(row.get("candidates", []) or [])
            row_features = torch.stack(features[offset : offset + len(candidates)], dim=0)
            offset += len(candidates)
            op = str(row.get("operation", "unknown"))
            alpha = float(alpha_by_op.get(op, alpha_by_op.get("*", 0.0)))
            scores = model(row_features)
            base_scores = torch.tensor([float(c.get("base_score", 0.0) or 0.0) for c in candidates], dtype=torch.float32)
            blend = base_scores + alpha * scores
            pred_idx = int(torch.argmax(blend).item())
            base_idx = int(torch.argmax(base_scores).item())
            ans, ex = _candidate_hit(candidates[pred_idx])
            bans, bex = _candidate_hit(candidates[base_idx])
            stats = by_operation.setdefault(op, {"rows": 0, "answer": 0, "exact": 0, "base_answer": 0, "base_exact": 0, "alpha": alpha})
            stats["rows"] += 1
            stats["answer"] += ans
            stats["exact"] += ex
            stats["base_answer"] += bans
            stats["base_exact"] += bex
            answer += ans
            exact += ex
            base_answer += bans
            base_exact += bex
    return {"rows": len(rows), "answer": answer, "exact": exact, "base_answer": base_answer, "base_exact": base_exact, "alpha_by_operation": alpha_by_op, "by_operation": by_operation}


def _score_one_op(model, rows: list[dict[str, Any]], features: list[torch.Tensor], operation: str, alpha: float) -> tuple[int, int]:
    answer = exact = 0
    offset = 0
    model.eval()
    with torch.no_grad():
        for row in rows:
            candidates = list(row.get("candidates", []) or [])
            row_features = torch.stack(features[offset : offset + len(candidates)], dim=0)
            offset += len(candidates)
            if str(row.get("operation", "")) != operation:
                continue
            scores = model(row_features)
            base_scores = torch.tensor([float(c.get("base_score", 0.0) or 0.0) for c in candidates], dtype=torch.float32)
            pred_idx = int(torch.argmax(base_scores + float(alpha) * scores).item())
            ans, ex = _candidate_hit(candidates[pred_idx])
            answer += ans
            exact += ex
    return answer, exact


def _pair_probs_for_hidden(stage1052, pair_model, pair_examples: list[dict[str, Any]], vectors: dict[str, torch.Tensor], split: str) -> dict[tuple[str, int, int], dict[str, list[float]]]:
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


def _build_features_for_split(stage1056, rows: list[dict[str, Any]], split: str, pair_probs: dict[tuple[str, int, int], dict[str, list[float]]]) -> list[torch.Tensor]:
    features: list[torch.Tensor] = []
    for row_index, row in enumerate(rows):
        for candidate_index, candidate in enumerate(list(row.get("candidates", []) or [])):
            features.append(stage1056._aggregate_features(row, candidate, pair_probs.get((split, row_index, candidate_index), {})))
    return features


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, default=_repo_root())
    parser.add_argument("--targets-jsonl", type=Path, default=Path("runs/local/artifacts/stage1043_operator_teacher_targets.jsonl"))
    parser.add_argument("--hidden-jsonl", type=Path, default=Path("runs/local/artifacts/stage1044_salted_hidden_no_anchor_targets.jsonl"))
    parser.add_argument("--classifier-state", type=Path, default=Path("runs/local/artifacts/stage1052_contrastive_span_pair_classifier_state.pt"))
    parser.add_argument("--composer-state", type=Path, default=Path("runs/local/artifacts/stage1056_pair_probability_candidate_composer_state.pt"))
    parser.add_argument("--alpha-sweep", default="0,0.02,0.05,0.08,0.1,0.15,0.2,0.3,0.5,0.75,1.0")
    parser.add_argument("--output-json", type=Path, default=Path("runs/local/artifacts/stage1059_operation_alpha_candidate_composer_summary.json"))
    args = parser.parse_args()

    repo_root = args.repo_root.resolve()
    stage1056 = _load_module("stage1056", repo_root / "scripts/train_stage1056_pair_probability_candidate_composer.py")
    stage1052 = stage1056._load_stage1052(repo_root)
    pair_model, pair_examples, vectors = stage1056._load_pair_classifier(stage1052, args.classifier_state, repo_root)
    composer_state = torch.load(args.composer_state, map_location="cpu")
    input_dim = 5 * len(stage1056.PAIR_TYPES) + 2 + len(stage1056.OPS)
    composer = stage1056.CandidateComposer(input_dim, 64)
    composer.load_state_dict(composer_state["state_dict"])
    composer.eval()

    rows = stage1056._rows_by_split(args.targets_jsonl)
    pair_probs = stage1056._pair_probabilities(stage1052, pair_model, pair_examples, vectors)
    features = stage1056._build_features(rows, pair_probs)
    hidden_rows = _rows_by_split(args.hidden_jsonl).get("hidden_eval", [])
    hidden_probs = _pair_probs_for_hidden(stage1052, pair_model, pair_examples, vectors, "hidden_eval")
    hidden_features = _build_features_for_split(stage1056, hidden_rows, "hidden_eval", hidden_probs)

    alphas = [float(x) for x in str(args.alpha_sweep).split(",") if x.strip()]
    selected_by_operation: dict[str, float] = {}
    calibration_choices: dict[str, list[dict[str, Any]]] = {}
    for operation in stage1056.OPS:
        choices = []
        for alpha in alphas:
            answer, exact = _score_one_op(composer, rows["calibration"], features["calibration"], operation, alpha)
            choices.append({"operation": operation, "alpha": alpha, "answer": answer, "exact": exact})
        best = max(choices, key=lambda item: (item["answer"], item["exact"], -abs(float(item["alpha"]))))
        selected_by_operation[operation] = float(best["alpha"])
        calibration_choices[operation] = choices

    summary = {
        "artifact_kind": "stage1059_operation_alpha_candidate_composer",
        "status": "completed_operation_alpha_candidate_composer_probe",
        "targets_jsonl": str(args.targets_jsonl),
        "hidden_jsonl": str(args.hidden_jsonl),
        "classifier_state": str(args.classifier_state),
        "composer_state": str(args.composer_state),
        "selected_alpha_by_operation": selected_by_operation,
        "calibration_for_selected": _score_rows(composer, rows["calibration"], features["calibration"], selected_by_operation),
        "eval_for_selected": _score_rows(composer, rows["eval"], features["eval"], selected_by_operation),
        "hidden_eval_for_selected": _score_rows(composer, hidden_rows, hidden_features, selected_by_operation),
        "stage1056_single_alpha_eval_answer_exact": [
            composer_state["summary"]["eval_for_calibration_selected"]["answer"],
            composer_state["summary"]["eval_for_calibration_selected"]["exact"],
        ],
        "stage1058_single_alpha_hidden_answer_exact": [343, 326],
        "calibration_choices_by_operation": calibration_choices,
        "decision": "Per-operation alpha calibration for the fixed Stage1056 learned composer. This changes only calibration-time blending, not pair classifier or composer weights.",
    }
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
