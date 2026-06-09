#!/usr/bin/env python3
"""Export no-anchor schema-count teacher scores from the learned char comparator."""

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


def _match_count(model, feature_fn, q_values: list[str], d_values: list[str], threshold: float) -> int:
    count = 0
    with torch.no_grad():
        for q_value in q_values:
            matched = False
            for d_value in d_values:
                prob = torch.sigmoid(model(feature_fn(q_value, d_value).unsqueeze(0))).item()
                matched = matched or float(prob) >= float(threshold)
            count += int(matched)
    return count


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, default=_repo_root())
    parser.add_argument("--targets-jsonl", type=Path, default=Path("runs/local/artifacts/stage1013_no_anchor_targets.jsonl"))
    parser.add_argument("--char-state", type=Path, default=Path("runs/local/artifacts/stage1024_char_schema_equality_counted_state.pt"))
    parser.add_argument("--output-jsonl", type=Path, default=Path("runs/local/artifacts/stage1028_schema_count_teacher_targets.jsonl"))
    parser.add_argument("--output-summary", type=Path, default=Path("runs/local/artifacts/stage1028_schema_count_teacher_targets_summary.json"))
    args = parser.parse_args()

    stage1024 = _load_module(args.repo_root.resolve() / "scripts/train_stage1023_char_schema_equality.py", "stage1024_char_eq")
    state = torch.load(args.char_state, map_location="cpu")
    entity_model = stage1024.CharEq(int(state["dim"]), int(state["hidden_dim"]))
    slot_model = stage1024.CharEq(int(state["dim"]), int(state["hidden_dim"]))
    entity_model.load_state_dict(state["entity_model_state"])
    slot_model.load_state_dict(state["slot_model_state"])
    entity_model.eval()
    slot_model.eval()
    policy = {key: tuple(int(x) for x in value) for key, value in dict(state["schema_policy"]).items()}
    entity_threshold = float(state["entity_threshold"])
    slot_threshold = float(state["slot_threshold"])

    rows = candidates = active_rows = positive_teacher_candidates = exact_positive_teacher_candidates = 0
    by_split_operation: dict[str, dict[str, dict[str, int]]] = {}
    args.output_jsonl.parent.mkdir(parents=True, exist_ok=True)
    with args.output_jsonl.open("w", encoding="utf-8") as out:
        for row in _iter_jsonl(args.targets_jsonl):
            rows += 1
            split = str(row.get("split", "unknown"))
            op = str(row.get("operation", "unknown"))
            ent_min, slot_min = policy.get(op, (0, 0))
            active = op in policy
            active_rows += int(active)
            stats = by_split_operation.setdefault(split, {}).setdefault(
                op,
                {"rows": 0, "candidates": 0, "active_rows": 0, "positive_teacher_candidates": 0, "exact_positive_teacher_candidates": 0},
            )
            stats["rows"] += 1
            stats["active_rows"] += int(active)
            q_ent = ENTITY_RE.findall(str(row.get("query_text", "") or ""))
            q_slot = SLOT_RE.findall(str(row.get("query_text", "") or ""))
            new_candidates = []
            for candidate in list(row.get("candidates", []) or []):
                candidates += 1
                stats["candidates"] += 1
                score = 0.0
                ent_matches = 0
                slot_matches = 0
                if active:
                    doc = str(candidate.get("doc_text", "") or "")
                    ent_matches = _match_count(entity_model, stage1024._features, q_ent, ENTITY_RE.findall(doc), entity_threshold) if ent_min > 0 else ent_min
                    slot_matches = _match_count(slot_model, stage1024._features, q_slot, SLOT_RE.findall(doc), slot_threshold) if slot_min > 0 else slot_min
                    score = float(ent_matches >= ent_min and slot_matches >= slot_min)
                positive_teacher_candidates += int(score >= 1.0)
                exact_positive_teacher_candidates += int(score >= 1.0 and bool(candidate.get("is_exact")))
                stats["positive_teacher_candidates"] += int(score >= 1.0)
                stats["exact_positive_teacher_candidates"] += int(score >= 1.0 and bool(candidate.get("is_exact")))
                cand = dict(candidate)
                cand["schema_entity_match_count"] = int(ent_matches)
                cand["schema_slot_match_count"] = int(slot_matches)
                cand["teacher_bridge_score"] = float(score)
                new_candidates.append(cand)
            out_row = dict(row)
            out_row["stage1028_teacher"] = {
                "primitive": "stage1024_learned_char_schema_count",
                "schema_policy": {key: list(value) for key, value in policy.items()},
                "teacher_bridge_score": "1 if learned char entity/slot match counts satisfy operation policy else 0",
            }
            out_row["candidates"] = new_candidates
            out.write(json.dumps(out_row, sort_keys=True) + "\n")

    summary = {
        "artifact_kind": "stage1028_schema_count_teacher_targets",
        "status": "completed_schema_count_teacher_export",
        "source_targets_jsonl": str(args.targets_jsonl),
        "char_state": str(args.char_state),
        "output_jsonl": str(args.output_jsonl),
        "schema_policy": {key: list(value) for key, value in policy.items()},
        "entity_threshold": entity_threshold,
        "slot_threshold": slot_threshold,
        "rows": rows,
        "candidates": candidates,
        "active_rows": active_rows,
        "positive_teacher_candidates": positive_teacher_candidates,
        "exact_positive_teacher_candidates": exact_positive_teacher_candidates,
        "by_split_operation": by_split_operation,
        "decision": "Exports Stage1024 learned char schema-count positives as teacher_bridge_score for 100M encoder/retrieval distillation. Teacher uses no pair anchors and no deterministic suffix set intersection at target-export time.",
    }
    args.output_summary.parent.mkdir(parents=True, exist_ok=True)
    args.output_summary.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
