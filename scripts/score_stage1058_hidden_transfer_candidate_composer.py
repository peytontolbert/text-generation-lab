#!/usr/bin/env python3
"""Score the Stage1056 learned candidate composer on salted hidden rows."""

from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path
from typing import Any

import torch


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _load_stage1056(repo_root: Path):
    path = repo_root / "scripts/train_stage1056_pair_probability_candidate_composer.py"
    spec = importlib.util.spec_from_file_location("stage1056", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"could not load stage1056: {path}")
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


def _pair_probabilities_for_split(stage1052, model, pair_examples: list[dict[str, Any]], vectors: dict[str, torch.Tensor], split: str) -> dict[tuple[str, int, int], dict[str, list[float]]]:
    out: dict[tuple[str, int, int], dict[str, list[float]]] = {}
    model.eval()
    with torch.no_grad():
        for example in pair_examples:
            if str(example.get("split", "")) != split:
                continue
            features = stage1052._features(example, vectors).unsqueeze(0)
            prob = float(torch.sigmoid(model(features)).item())
            key = (split, int(example["row_index"]), int(example["candidate_index"]))
            out.setdefault(key, {}).setdefault(str(example["pair_type"]), []).append(prob)
    return out


def _build_features_for_split(stage1056, rows: list[dict[str, Any]], split: str, pair_probs: dict[tuple[str, int, int], dict[str, list[float]]]) -> list[torch.Tensor]:
    features: list[torch.Tensor] = []
    for row_index, row in enumerate(rows):
        for candidate_index, candidate in enumerate(list(row.get("candidates", []) or [])):
            features.append(stage1056._aggregate_features(row, candidate, pair_probs.get((split, row_index, candidate_index), {})))
    return features


def _positive_present(rows: list[dict[str, Any]]) -> dict[str, Any]:
    by_operation: dict[str, dict[str, int]] = {}
    total = 0
    for row in rows:
        op = str(row.get("operation", "unknown"))
        present = int(any(bool(c.get("is_exact") or c.get("is_answer_match")) for c in list(row.get("candidates", []) or [])))
        total += present
        stats = by_operation.setdefault(op, {"rows": 0, "positive_present": 0})
        stats["rows"] += 1
        stats["positive_present"] += present
    return {"rows": len(rows), "positive_present": total, "by_operation": by_operation}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, default=_repo_root())
    parser.add_argument("--hidden-jsonl", type=Path, default=Path("runs/local/artifacts/stage1044_salted_hidden_no_anchor_targets.jsonl"))
    parser.add_argument("--composer-state", type=Path, default=Path("runs/local/artifacts/stage1056_pair_probability_candidate_composer_state.pt"))
    parser.add_argument("--classifier-state", type=Path, default=Path("runs/local/artifacts/stage1052_contrastive_span_pair_classifier_state.pt"))
    parser.add_argument("--output-json", type=Path, default=Path("runs/local/artifacts/stage1058_hidden_transfer_pair_probability_composer_summary.json"))
    args = parser.parse_args()

    repo_root = args.repo_root.resolve()
    stage1056 = _load_stage1056(repo_root)
    stage1052 = stage1056._load_stage1052(repo_root)
    pair_model, pair_examples, vectors = stage1056._load_pair_classifier(stage1052, args.classifier_state, repo_root)
    composer_state = torch.load(args.composer_state, map_location="cpu")
    input_dim = 5 * len(stage1056.PAIR_TYPES) + 2 + len(stage1056.OPS)
    composer = stage1056.CandidateComposer(input_dim, 64)
    composer.load_state_dict(composer_state["state_dict"])
    composer.eval()

    rows_by_split = _rows_by_split(args.hidden_jsonl)
    hidden_rows = rows_by_split.get("hidden_eval", [])
    pair_probs = _pair_probabilities_for_split(stage1052, pair_model, pair_examples, vectors, "hidden_eval")
    features = _build_features_for_split(stage1056, hidden_rows, "hidden_eval", pair_probs)
    selected_alpha = float(composer_state["summary"]["calibration_selected"]["alpha"])
    hidden_score = stage1056._score_split(composer, hidden_rows, features, selected_alpha)
    base_score = stage1056._score_split(composer, hidden_rows, features, 0.0)
    positives = _positive_present(hidden_rows)

    summary = {
        "artifact_kind": "stage1058_hidden_transfer_pair_probability_composer",
        "status": "completed_hidden_transfer_probe",
        "hidden_jsonl": str(args.hidden_jsonl),
        "classifier_state": str(args.classifier_state),
        "composer_state": str(args.composer_state),
        "selected_alpha_from_stage1056": selected_alpha,
        "hidden_positive_present": positives,
        "hidden_base_score": base_score,
        "hidden_composer_score": hidden_score,
        "composer_eval_answer_exact": [
            composer_state["summary"]["eval_for_calibration_selected"]["answer"],
            composer_state["summary"]["eval_for_calibration_selected"]["exact"],
        ],
        "decision": "Transfer-only scoring of the Stage1056 learned pair-probability composer on Stage1044 salted hidden no-anchor rows. No hidden retraining, bridge fields, char comparator, suffix set intersection, or pair anchors are candidate-scoring inputs.",
    }
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
