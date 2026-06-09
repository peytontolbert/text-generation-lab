#!/usr/bin/env python3
"""Score candidate rows using Stage1052 learned span-pair probabilities."""

from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path
from typing import Any

import torch


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _load_stage1052(repo_root: Path):
    path = repo_root / "scripts/train_stage1052_contrastive_span_pair_classifier.py"
    spec = importlib.util.spec_from_file_location("stage1052", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"could not load stage1052: {path}")
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
    rows: dict[str, list[dict[str, Any]]] = {"train": [], "calibration": [], "eval": []}
    for row in _iter_jsonl(path):
        split = str(row.get("split", ""))
        if split in rows:
            rows[split].append(row)
    return rows


def _candidate_hit(candidate: dict[str, Any]) -> tuple[int, int]:
    return int(bool(candidate.get("is_exact") or candidate.get("is_answer_match"))), int(bool(candidate.get("is_exact")))


def _pair_probs(stage1052, model, pair_examples: list[dict[str, Any]], vectors: dict[str, torch.Tensor]) -> dict[tuple[str, int, int], dict[str, list[float]]]:
    out: dict[tuple[str, int, int], dict[str, list[float]]] = {}
    model.eval()
    with torch.no_grad():
        for example in pair_examples:
            if int(example.get("is_hidden_transfer", 0)) == 1:
                continue
            split = str(example.get("split", ""))
            if split not in {"train", "calibration", "eval"}:
                continue
            features = stage1052._features(example, vectors).unsqueeze(0)
            prob = float(torch.sigmoid(model(features)).item())
            key = (split, int(example["row_index"]), int(example["candidate_index"]))
            out.setdefault(key, {}).setdefault(str(example["pair_type"]), []).append(prob)
    return out


def _count(values: list[float], threshold: float) -> int:
    return sum(1 for value in values if float(value) >= float(threshold))


def _candidate_pass(operation: str, probs: dict[str, list[float]], threshold: float) -> bool:
    entity_count = _count(probs.get("entity_statement", []), threshold)
    slot_count = _count(probs.get("slot", []), threshold)
    default_answer_count = _count(probs.get("default_answer_kind", []), threshold)
    default_policy_count = _count(probs.get("default_policy_kind", []), threshold)
    if operation == "composition":
        return slot_count >= 2
    if operation == "relation":
        return entity_count >= 1 and slot_count >= 1
    if operation == "counterfactual_false_claim":
        return entity_count >= 1 and slot_count >= 1
    if operation == "exception":
        return (entity_count >= 1 and default_answer_count >= 1) or (default_policy_count >= 1 and default_answer_count >= 1)
    return False


def _score_split(rows: list[dict[str, Any]], split: str, pair_probs: dict[tuple[str, int, int], dict[str, list[float]]], threshold: float, use_ops: set[str]) -> dict[str, Any]:
    answer = exact = base_answer = base_exact = 0
    by_operation: dict[str, dict[str, int]] = {}
    for row_index, row in enumerate(rows):
        candidates = list(row.get("candidates", []) or [])
        if not candidates:
            continue
        operation = str(row.get("operation", ""))
        stats = by_operation.setdefault(operation, {"rows": 0, "answer": 0, "exact": 0, "base_answer": 0, "base_exact": 0, "predicted_rows": 0})
        stats["rows"] += 1
        base_idx = max(range(len(candidates)), key=lambda idx: (float(candidates[idx].get("base_score", 0.0) or 0.0), -idx))
        pool = []
        if operation in use_ops:
            for candidate_index in range(len(candidates)):
                probs = pair_probs.get((split, row_index, candidate_index), {})
                if _candidate_pass(operation, probs, threshold):
                    pool.append(candidate_index)
        pred_idx = max(pool, key=lambda idx: (float(candidates[idx].get("base_score", 0.0) or 0.0), -idx)) if pool else base_idx
        stats["predicted_rows"] += int(bool(pool))
        ans, ex = _candidate_hit(candidates[pred_idx])
        bans, bex = _candidate_hit(candidates[base_idx])
        answer += ans
        exact += ex
        base_answer += bans
        base_exact += bex
        stats["answer"] += ans
        stats["exact"] += ex
        stats["base_answer"] += bans
        stats["base_exact"] += bex
    return {"rows": len(rows), "answer": answer, "exact": exact, "base_answer": base_answer, "base_exact": base_exact, "threshold": float(threshold), "use_ops": sorted(use_ops), "by_operation": by_operation}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, default=_repo_root())
    parser.add_argument("--targets-jsonl", type=Path, default=Path("runs/local/artifacts/stage1043_operator_teacher_targets.jsonl"))
    parser.add_argument("--pair-jsonl", type=Path, default=Path("runs/local/artifacts/stage1051_contrastive_span_pair_targets.jsonl"))
    parser.add_argument("--classifier-state", type=Path, default=Path("runs/local/artifacts/stage1052_contrastive_span_pair_classifier_state.pt"))
    parser.add_argument("--output-json", type=Path, default=Path("runs/local/artifacts/stage1053_pair_classifier_candidate_policy_summary.json"))
    args = parser.parse_args()

    stage1052 = _load_stage1052(args.repo_root.resolve())
    state = torch.load(args.classifier_state, map_location="cpu")
    pair_examples = list(_iter_jsonl(args.pair_jsonl))
    all_spans = sorted({str(ex["query_span"]) for ex in pair_examples} | {str(ex["doc_span"]) for ex in pair_examples})
    retrieval_eval = stage1052._load_retrieval_eval(args.repo_root.resolve())
    base_model, tokenizer, _ = retrieval_eval._load_model(Path(state["summary"]["bundle_dir"]).resolve(), repo_root=args.repo_root.resolve(), device=torch.device("cpu"))
    base_model.eval()
    vectors = stage1052._encode_texts(retrieval_eval, tokenizer, base_model, all_spans, max_tokens=32, batch_size=128, device=torch.device("cpu"))
    sample_features = stage1052._features(pair_examples[0], vectors)
    model = stage1052.PairClassifier(int(sample_features.shape[-1]), int(state["summary"]["head_parameter_count"] > 0 and 128))
    model.load_state_dict(state["state_dict"])
    probs = _pair_probs(stage1052, model, pair_examples, vectors)
    rows = _rows_by_split(args.targets_jsonl)
    thresholds = [0.3, 0.4, 0.5, 0.6, 0.7]
    operation_sets = [
        {"composition", "relation", "counterfactual_false_claim", "exception"},
        {"composition", "exception"},
        {"relation", "counterfactual_false_claim", "exception"},
        {"relation", "exception"},
        {"exception"},
    ]
    best_cal = None
    best_eval = None
    for threshold in thresholds:
        for use_ops in operation_sets:
            cal = _score_split(rows["calibration"], "calibration", probs, threshold, use_ops)
            key = (cal["answer"], cal["exact"])
            if best_cal is None or key > (best_cal["answer"], best_cal["exact"]):
                best_cal = cal
                best_eval = _score_split(rows["eval"], "eval", probs, threshold, use_ops)
    assert best_cal is not None and best_eval is not None
    summary = {
        "artifact_kind": "stage1053_pair_classifier_candidate_policy",
        "status": "completed_pair_classifier_candidate_policy_probe",
        "targets_jsonl": str(args.targets_jsonl),
        "pair_jsonl": str(args.pair_jsonl),
        "classifier_state": str(args.classifier_state),
        "calibration_selected": best_cal,
        "eval_for_calibration_selected": best_eval,
        "stage976_answer_exact": [282, 265],
        "decision": "Candidate policy from Stage1052 learned span-pair probabilities. Uses no bridge fields, char comparator, suffix set intersection, or pair anchors as candidate-scoring inputs.",
    }
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
