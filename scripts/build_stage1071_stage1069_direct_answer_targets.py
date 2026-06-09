#!/usr/bin/env python3
"""Build direct-answer distillation targets from Stage1069 selected candidates."""

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


def _select_rows(stage1056, composer, rows: list[dict[str, Any]], features: list[torch.Tensor], *, split: str, alpha: float) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    out: list[dict[str, Any]] = []
    answer = exact = parse_ok = 0
    by_operation: dict[str, dict[str, int]] = {}
    offset = 0
    composer.eval()
    with torch.no_grad():
        for row_index, row in enumerate(rows):
            candidates = list(row.get("candidates", []) or [])
            row_features = torch.stack(features[offset : offset + len(candidates)], dim=0)
            offset += len(candidates)
            base_scores = torch.tensor([float(c.get("base_score", 0.0) or 0.0) for c in candidates], dtype=torch.float32)
            learned_scores = composer(row_features)
            pred_idx = int(torch.argmax(base_scores + float(alpha) * learned_scores).item())
            candidate = candidates[pred_idx]
            emitted = _extract_answer(str(candidate.get("doc_text", "") or ""))
            ans, ex = _candidate_hit(candidate)
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
            content = str(emitted or "")
            out.append(
                {
                    "split": split,
                    "row_index": row_index,
                    "operation": op,
                    "task_type": "active_agent_direct_answer",
                    "query_text": row.get("query_text", ""),
                    "encoder_text": row.get("query_text", ""),
                    "selected_candidate_index": pred_idx,
                    "selected_doc_text": candidate.get("doc_text", ""),
                    "expected_content": content,
                    "decoder_text": f"<AK_STRUCTURED> <AK_ACTION_RESPOND> <AK_TASK_TYPE> active_agent_direct_answer <AK_CONTENT> {content} </AK_CONTENT> <AK_END>",
                    "json_decoder_text": json.dumps({"action": "respond", "content": content}, sort_keys=True),
                    "negative_decoder_text": "",
                    "decoder_loss_weight": 1.0,
                    "answer_hit": ans,
                    "exact_hit": ex,
                    "parse_ok": parsed,
                    "alpha": float(alpha),
                }
            )
    return out, {"split": split, "rows": len(rows), "answer": answer, "exact": exact, "parse_ok": parse_ok, "by_operation": by_operation}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, default=_repo_root())
    parser.add_argument("--targets-jsonl", type=Path, default=Path("runs/local/artifacts/stage1043_operator_teacher_targets.jsonl"))
    parser.add_argument("--hidden-jsonl", type=Path, default=Path("runs/local/artifacts/stage1044_salted_hidden_no_anchor_targets.jsonl"))
    parser.add_argument("--classifier-state", type=Path, default=Path("runs/local/artifacts/stage1062_composition_entity_pair_classifier_state.pt"))
    parser.add_argument("--composer-state", type=Path, default=Path("runs/local/artifacts/stage1063_composition_entity_candidate_composer_state.pt"))
    parser.add_argument("--alpha", type=float, default=2.0)
    parser.add_argument("--output-jsonl", type=Path, default=Path("runs/local/artifacts/stage1071_stage1069_direct_answer_targets.jsonl"))
    parser.add_argument("--output-summary", type=Path, default=Path("runs/local/artifacts/stage1071_stage1069_direct_answer_targets_summary.json"))
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
    all_targets: list[dict[str, Any]] = []
    split_summaries: dict[str, Any] = {}
    for split in ["train", "calibration", "eval"]:
        targets, split_summary = _select_rows(stage1056, composer, rows[split], features[split], split=split, alpha=float(args.alpha))
        all_targets.extend(targets)
        split_summaries[split] = split_summary

    hidden_rows = _rows_by_split(args.hidden_jsonl).get("hidden_eval", [])
    hidden_probs = stage1058._pair_probabilities_for_split(stage1052, pair_model, pair_examples, vectors, "hidden_eval")
    hidden_features = stage1058._build_features_for_split(stage1056, hidden_rows, "hidden_eval", hidden_probs)
    hidden_targets, hidden_summary = _select_rows(stage1056, composer, hidden_rows, hidden_features, split="hidden_eval", alpha=float(args.alpha))
    all_targets.extend(hidden_targets)
    split_summaries["hidden_eval"] = hidden_summary

    args.output_jsonl.parent.mkdir(parents=True, exist_ok=True)
    with args.output_jsonl.open("w", encoding="utf-8") as handle:
        for target in all_targets:
            handle.write(json.dumps(target, sort_keys=True) + "\n")
    summary = {
        "artifact_kind": "stage1071_stage1069_direct_answer_targets",
        "status": "completed_stage1069_direct_answer_target_export",
        "targets_jsonl": str(args.targets_jsonl),
        "hidden_jsonl": str(args.hidden_jsonl),
        "output_jsonl": str(args.output_jsonl),
        "rows": len(all_targets),
        "alpha": float(args.alpha),
        "by_split": split_summaries,
        "decision": "Builds direct-answer distillation rows from Stage1069 selected candidates. These targets are for constrained/direct answer training; they do not prove free-form generation by themselves.",
    }
    args.output_summary.parent.mkdir(parents=True, exist_ok=True)
    args.output_summary.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
