#!/usr/bin/env python3
"""Materialize constrained answers from Stage1069 learned-composer selections."""

from __future__ import annotations

import argparse
import importlib.util
import json
import re
from pathlib import Path
from typing import Any

import torch


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


def _extract_answer(doc_text: str) -> str | None:
    match = ANSWER_RE.search(str(doc_text))
    return match.group(1) if match else None


def _select_and_materialize(
    stage1056,
    composer,
    rows: list[dict[str, Any]],
    features: list[torch.Tensor],
    *,
    split: str,
    alpha: float,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    answer = exact = parse_ok = 0
    by_operation: dict[str, dict[str, int]] = {}
    outputs: list[dict[str, Any]] = []
    offset = 0
    composer.eval()
    with torch.no_grad():
        for row_index, row in enumerate(rows):
            candidates = list(row.get("candidates", []) or [])
            row_features = torch.stack(features[offset : offset + len(candidates)], dim=0)
            offset += len(candidates)
            base_scores = torch.tensor([float(c.get("base_score", 0.0) or 0.0) for c in candidates], dtype=torch.float32)
            learned_scores = composer(row_features)
            blend_scores = base_scores + float(alpha) * learned_scores
            pred_idx = int(torch.argmax(blend_scores).item())
            candidate = candidates[pred_idx]
            ans, ex = _candidate_hit(candidate)
            emitted = _extract_answer(str(candidate.get("doc_text", "") or ""))
            parsed = emitted is not None
            op = str(row.get("operation", "unknown"))
            stats = by_operation.setdefault(op, {"rows": 0, "answer": 0, "exact": 0, "parse_ok": 0})
            stats["rows"] += 1
            stats["answer"] += ans
            stats["exact"] += ex
            stats["parse_ok"] += int(parsed)
            answer += ans
            exact += ex
            parse_ok += int(parsed)
            outputs.append(
                {
                    "split": split,
                    "row_index": row_index,
                    "operation": op,
                    "predicted_candidate_index": pred_idx,
                    "emitted_answer": emitted,
                    "parse_ok": parsed,
                    "answer_hit": ans,
                    "exact_hit": ex,
                    "base_score": float(base_scores[pred_idx].item()),
                    "learned_score": float(learned_scores[pred_idx].item()),
                    "blend_score": float(blend_scores[pred_idx].item()),
                    "alpha": float(alpha),
                }
            )
    return {
        "split": split,
        "rows": len(rows),
        "answer": answer,
        "exact": exact,
        "parse_ok": parse_ok,
        "by_operation": by_operation,
    }, outputs


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, default=_repo_root())
    parser.add_argument("--targets-jsonl", type=Path, default=Path("runs/local/artifacts/stage1043_operator_teacher_targets.jsonl"))
    parser.add_argument("--hidden-jsonl", type=Path, default=Path("runs/local/artifacts/stage1044_salted_hidden_no_anchor_targets.jsonl"))
    parser.add_argument("--classifier-state", type=Path, default=Path("runs/local/artifacts/stage1062_composition_entity_pair_classifier_state.pt"))
    parser.add_argument("--composer-state", type=Path, default=Path("runs/local/artifacts/stage1063_composition_entity_candidate_composer_state.pt"))
    parser.add_argument("--alpha", type=float, default=2.0)
    parser.add_argument("--output-json", type=Path, default=Path("runs/local/artifacts/stage1070_stage1069_constrained_answer_materialization_summary.json"))
    parser.add_argument("--outputs-jsonl", type=Path, default=Path("runs/local/artifacts/stage1070_stage1069_constrained_answer_materialization_outputs.jsonl"))
    args = parser.parse_args()

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
    eval_summary, eval_outputs = _select_and_materialize(stage1056, composer, rows["eval"], features["eval"], split="eval", alpha=float(args.alpha))

    hidden_rows = _rows_by_split(args.hidden_jsonl).get("hidden_eval", [])
    hidden_probs = stage1058._pair_probabilities_for_split(stage1052, pair_model, pair_examples, vectors, "hidden_eval")
    hidden_features = stage1058._build_features_for_split(stage1056, hidden_rows, "hidden_eval", hidden_probs)
    hidden_summary, hidden_outputs = _select_and_materialize(stage1056, composer, hidden_rows, hidden_features, split="hidden_eval", alpha=float(args.alpha))

    outputs = eval_outputs + hidden_outputs
    summary = {
        "artifact_kind": "stage1070_stage1069_constrained_answer_materialization",
        "status": "completed_stage1069_constrained_answer_materialization",
        "targets_jsonl": str(args.targets_jsonl),
        "hidden_jsonl": str(args.hidden_jsonl),
        "classifier_state": str(args.classifier_state),
        "composer_state": str(args.composer_state),
        "alpha": float(args.alpha),
        "eval": eval_summary,
        "hidden_eval": hidden_summary,
        "outputs_jsonl": str(args.outputs_jsonl),
        "decision": "Constrained answer materialization extracts answer=<value> from Stage1069 selected candidates. This validates typed answer emission from the learned-composer candidate policy, not free-form generation.",
    }
    args.outputs_jsonl.parent.mkdir(parents=True, exist_ok=True)
    with args.outputs_jsonl.open("w", encoding="utf-8") as handle:
        for output in outputs:
            handle.write(json.dumps(output, sort_keys=True) + "\n")
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
