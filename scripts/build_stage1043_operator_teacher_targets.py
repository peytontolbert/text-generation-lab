#!/usr/bin/env python3
"""Export Stage1040 typed-operator teacher targets for bridge-free training."""

from __future__ import annotations

import argparse
import importlib.util
import json
import re
from pathlib import Path
from typing import Any

import torch


ENTITY_RE = re.compile(r"\b(?:qent|dent|entity)_([A-Za-z0-9]+)\b")
SLOT_RE = re.compile(r"\b(?:qslot|dslot|slot)_([A-Za-z0-9]+)\b")
STATEMENT_ENTITY_RE = re.compile(r"\bstatement=(?:claim\s+)?dent_([A-Za-z0-9]+)\b")
DEFAULT_KIND_RE = re.compile(r"\bdefault\s+([A-Za-z0-9]+)\b")
ANSWER_KIND_RE = re.compile(r"\banswer=([A-Za-z0-9]+)_v[0-9A-Za-z]+\b")
DEFAULT_POLICY_RE = re.compile(r"\bstatement=default\s+([A-Za-z0-9]+)\s+policy\b")


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"could not load module: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _iter_jsonl(path: Path):
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                yield json.loads(line)


def _match_count(*, model, feature_fn, q_values: list[str], d_values: list[str], threshold: float) -> int:
    count = 0
    model.eval()
    with torch.no_grad():
        for q_value in q_values:
            matched = False
            for d_value in d_values:
                prob = torch.sigmoid(model(feature_fn(q_value, d_value).unsqueeze(0))).item()
                matched = matched or float(prob) >= float(threshold)
            count += int(matched)
    return count


def _load_predictions(path: Path) -> dict[tuple[str, int], dict[str, Any]]:
    predictions: dict[tuple[str, int], dict[str, Any]] = {}
    for item in _iter_jsonl(path):
        predictions[(str(item.get("split", "")), int(item.get("row_index", -1)))] = item
    return predictions


def _candidate_operator_targets(
    *,
    row: dict[str, Any],
    candidate: dict[str, Any],
    entity_model,
    slot_model,
    feature_fn,
    entity_threshold: float,
    slot_threshold: float,
) -> dict[str, Any]:
    operation = str(row.get("operation", "") or "")
    query = str(row.get("query_text", "") or "")
    doc = str(candidate.get("doc_text", "") or "")
    q_ent = ENTITY_RE.findall(query)
    q_slot = SLOT_RE.findall(query)
    d_ent_all = ENTITY_RE.findall(doc)
    d_slot_all = SLOT_RE.findall(doc)
    statement_entities = STATEMENT_ENTITY_RE.findall(doc)
    default_kinds = set(DEFAULT_KIND_RE.findall(query))
    answer_kinds = set(ANSWER_KIND_RE.findall(doc))
    policy_kinds = set(DEFAULT_POLICY_RE.findall(doc))

    entity_match_count = _match_count(
        model=entity_model,
        feature_fn=feature_fn,
        q_values=q_ent,
        d_values=d_ent_all,
        threshold=entity_threshold,
    )
    statement_entity_match_count = _match_count(
        model=entity_model,
        feature_fn=feature_fn,
        q_values=q_ent,
        d_values=statement_entities,
        threshold=entity_threshold,
    )
    slot_match_count = _match_count(
        model=slot_model,
        feature_fn=feature_fn,
        q_values=q_slot,
        d_values=d_slot_all,
        threshold=slot_threshold,
    )
    default_kind_match = int(bool(default_kinds.intersection(answer_kinds))) if default_kinds else 0
    default_policy_match = int(bool(default_kinds.intersection(policy_kinds))) if default_kinds else 0

    composition_pass = int(operation == "composition" and entity_match_count >= 1 and slot_match_count >= 2)
    relation_pass = int(operation == "relation" and statement_entity_match_count >= 1 and slot_match_count >= 1)
    counterfactual_pass = int(operation == "counterfactual_false_claim" and statement_entity_match_count >= 1 and slot_match_count >= 1)
    if operation == "exception":
        if q_ent:
            exception_pass = int(statement_entity_match_count >= 1 and default_kind_match >= 1)
        else:
            exception_pass = int(default_policy_match >= 1 and default_kind_match >= 1)
    else:
        exception_pass = 0
    teacher_operator_score = max(composition_pass, relation_pass, counterfactual_pass, exception_pass)

    return {
        "teacher_entity_match_count": int(entity_match_count),
        "teacher_statement_entity_match_count": int(statement_entity_match_count),
        "teacher_slot_match_count": int(slot_match_count),
        "teacher_default_kind_match": int(default_kind_match),
        "teacher_default_policy_match": int(default_policy_match),
        "teacher_composition_slot_count_pass": int(composition_pass),
        "teacher_relation_source_role_pass": int(relation_pass),
        "teacher_counterfactual_statement_entity_slot_pass": int(counterfactual_pass),
        "teacher_exception_source_or_default_kind_pass": int(exception_pass),
        "teacher_operator_score": float(teacher_operator_score),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, default=_repo_root())
    parser.add_argument("--targets-jsonl", type=Path, default=Path("runs/local/artifacts/stage1013_no_anchor_targets.jsonl"))
    parser.add_argument("--char-state", type=Path, default=Path("runs/local/artifacts/stage1024_char_schema_equality_counted_state.pt"))
    parser.add_argument(
        "--stage1040-predictions",
        type=Path,
        default=Path("runs/local/artifacts/stage1040_100m_no_anchor_role_char_schema_source_kind_policy_hybrid_predictions.jsonl"),
    )
    parser.add_argument("--output-jsonl", type=Path, default=Path("runs/local/artifacts/stage1043_operator_teacher_targets.jsonl"))
    parser.add_argument("--output-summary", type=Path, default=Path("runs/local/artifacts/stage1043_operator_teacher_targets_summary.json"))
    args = parser.parse_args()

    stage1024 = _load_module(args.repo_root.resolve() / "scripts/train_stage1023_char_schema_equality.py", "stage1024_char_eq")
    state = torch.load(args.char_state, map_location="cpu")
    entity_model = stage1024.CharEq(int(state["dim"]), int(state["hidden_dim"]))
    slot_model = stage1024.CharEq(int(state["dim"]), int(state["hidden_dim"]))
    entity_model.load_state_dict(state["entity_model_state"])
    slot_model.load_state_dict(state["slot_model_state"])
    entity_model.eval()
    slot_model.eval()
    entity_threshold = float(state["entity_threshold"])
    slot_threshold = float(state["slot_threshold"])
    predictions = _load_predictions(args.stage1040_predictions)

    rows = candidates = selected_candidates = positive_operator_candidates = 0
    by_split_operation: dict[str, dict[str, dict[str, int]]] = {}
    args.output_jsonl.parent.mkdir(parents=True, exist_ok=True)
    with args.output_jsonl.open("w", encoding="utf-8") as out:
        row_counters: dict[str, int] = {}
        for row in _iter_jsonl(args.targets_jsonl):
            rows += 1
            split = str(row.get("split", "unknown"))
            split_row_index = row_counters.get(split, 0)
            row_counters[split] = split_row_index + 1
            operation = str(row.get("operation", "unknown"))
            prediction = predictions.get((split, split_row_index), {})
            selected_index = int(prediction.get("predicted_candidate_index", -1))
            stats = by_split_operation.setdefault(split, {}).setdefault(
                operation,
                {
                    "rows": 0,
                    "candidates": 0,
                    "positive_operator_candidates": 0,
                    "selected_candidates": 0,
                    "selected_answer_hits": 0,
                    "selected_exact_hits": 0,
                },
            )
            stats["rows"] += 1
            new_candidates = []
            for candidate_index, candidate in enumerate(list(row.get("candidates", []) or [])):
                candidates += 1
                stats["candidates"] += 1
                targets = _candidate_operator_targets(
                    row=row,
                    candidate=candidate,
                    entity_model=entity_model,
                    slot_model=slot_model,
                    feature_fn=stage1024._features,
                    entity_threshold=entity_threshold,
                    slot_threshold=slot_threshold,
                )
                is_selected = int(candidate_index == selected_index)
                selected_candidates += is_selected
                positive_operator_candidates += int(targets["teacher_operator_score"] >= 1.0)
                stats["positive_operator_candidates"] += int(targets["teacher_operator_score"] >= 1.0)
                stats["selected_candidates"] += is_selected
                stats["selected_answer_hits"] += int(is_selected and bool(candidate.get("is_answer_match") or candidate.get("is_exact")))
                stats["selected_exact_hits"] += int(is_selected and bool(candidate.get("is_exact")))
                cand = dict(candidate)
                cand.update(targets)
                cand["teacher_stage1040_selected"] = is_selected
                cand["teacher_candidate_value_score"] = float(is_selected)
                new_candidates.append(cand)
            out_row = dict(row)
            out_row["stage1043_teacher"] = {
                "primitive": "stage1040_typed_operator_interface",
                "source_predictions": str(args.stage1040_predictions),
                "operator_targets": [
                    "statement_entity_match_count",
                    "slot_match_count",
                    "composition_slot_count_pass",
                    "relation_source_role_pass",
                    "counterfactual_statement_entity_slot_pass",
                    "exception_source_or_default_kind_pass",
                    "stage1040_selected_candidate",
                ],
                "eval_time_contract": "train encoder/operator heads from these targets; do not call char comparator, bridge fields, suffix intersection, or pair anchors at bridge-free eval",
            }
            out_row["candidates"] = new_candidates
            out.write(json.dumps(out_row, sort_keys=True) + "\n")

    summary = {
        "artifact_kind": "stage1043_operator_teacher_targets",
        "status": "completed_operator_teacher_target_export",
        "source_targets_jsonl": str(args.targets_jsonl),
        "char_state": str(args.char_state),
        "stage1040_predictions": str(args.stage1040_predictions),
        "output_jsonl": str(args.output_jsonl),
        "entity_threshold": entity_threshold,
        "slot_threshold": slot_threshold,
        "rows": rows,
        "candidates": candidates,
        "selected_candidates": selected_candidates,
        "positive_operator_candidates": positive_operator_candidates,
        "by_split_operation": by_split_operation,
        "decision": "Exports rich Stage1040 typed-operator teacher targets for bridge-free 100M encoder/operator-head training. This is a training target artifact, not an eval-time comparator claim.",
    }
    args.output_summary.parent.mkdir(parents=True, exist_ok=True)
    args.output_summary.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
