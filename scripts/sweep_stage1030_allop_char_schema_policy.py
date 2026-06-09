#!/usr/bin/env python3
"""Sweep learned char schema-count policies for every operation."""

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


def _rows_by_split(path: Path) -> dict[str, list[dict[str, Any]]]:
    rows = {"train": [], "calibration": [], "eval": []}
    for row in _iter_jsonl(path):
        split = str(row.get("split", ""))
        rows.setdefault(split, []).append(row)
    return rows


def _hit(candidate: dict[str, Any]) -> tuple[int, int]:
    return int(bool(candidate.get("is_exact") or candidate.get("is_answer_match"))), int(bool(candidate.get("is_exact")))


def _base_idx(candidates: list[dict[str, Any]]) -> int:
    return max(
        range(len(candidates)),
        key=lambda i: (float(candidates[i].get("base_score", 0.0) or 0.0), -int(candidates[i].get("rank", 9999) or 9999), -i),
    )


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


def _score_row(entity_model, slot_model, feature_fn, row: dict[str, Any], policy: tuple[int, int] | None, entity_threshold: float, slot_threshold: float) -> tuple[int, str]:
    candidates = list(row.get("candidates", []) or [])
    if not candidates:
        return 0, "missing"
    if policy is None:
        return _base_idx(candidates), "base"
    ent_min, slot_min = policy
    q_ent = ENTITY_RE.findall(str(row.get("query_text", "") or ""))
    q_slot = SLOT_RE.findall(str(row.get("query_text", "") or ""))
    pool = []
    for idx, candidate in enumerate(candidates):
        doc = str(candidate.get("doc_text", "") or "")
        ent_matches = _match_count(entity_model, feature_fn, q_ent, ENTITY_RE.findall(doc), entity_threshold) if ent_min > 0 else ent_min
        slot_matches = _match_count(slot_model, feature_fn, q_slot, SLOT_RE.findall(doc), slot_threshold) if slot_min > 0 else slot_min
        if ent_matches >= ent_min and slot_matches >= slot_min:
            pool.append(idx)
    if not pool:
        return _base_idx(candidates), "fallback_base"
    return max(pool, key=lambda i: (float(candidates[i].get("base_score", 0.0) or 0.0), -int(candidates[i].get("rank", 9999) or 9999), -i)), "char_schema"


def _score_split(entity_model, slot_model, feature_fn, rows: list[dict[str, Any]], policy_by_operation: dict[str, tuple[int, int] | None], entity_threshold: float, slot_threshold: float):
    answer = exact = base_answer = base_exact = recoverable_answer = recoverable_exact = 0
    by_operation: dict[str, dict[str, int]] = {}
    policy_details: dict[str, dict[str, int]] = {}
    for row in rows:
        candidates = list(row.get("candidates", []) or [])
        if not candidates:
            continue
        op = str(row.get("operation", "unknown"))
        stats = by_operation.setdefault(op, {"rows": 0, "answer": 0, "exact": 0, "base_answer": 0, "base_exact": 0, "recoverable_answer": 0, "recoverable_exact": 0})
        stats["rows"] += 1
        pred, detail = _score_row(entity_model, slot_model, feature_fn, row, policy_by_operation.get(op), entity_threshold, slot_threshold)
        policy_details.setdefault(op, {}).setdefault(detail, 0)
        policy_details[op][detail] += 1
        base = _base_idx(candidates)
        ans, ex = _hit(candidates[pred])
        bans, bex = _hit(candidates[base])
        answer += ans
        exact += ex
        base_answer += bans
        base_exact += bex
        recoverable_answer += int(any(_hit(candidate)[0] for candidate in candidates))
        recoverable_exact += int(any(_hit(candidate)[1] for candidate in candidates))
        stats["answer"] += ans
        stats["exact"] += ex
        stats["base_answer"] += bans
        stats["base_exact"] += bex
        stats["recoverable_answer"] += int(any(_hit(candidate)[0] for candidate in candidates))
        stats["recoverable_exact"] += int(any(_hit(candidate)[1] for candidate in candidates))
    return {
        "rows": len(rows),
        "answer": answer,
        "exact": exact,
        "base_answer": base_answer,
        "base_exact": base_exact,
        "recoverable_answer": recoverable_answer,
        "recoverable_exact": recoverable_exact,
        "by_operation": by_operation,
        "policy_details": policy_details,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, default=_repo_root())
    parser.add_argument("--targets-jsonl", type=Path, default=Path("runs/local/artifacts/stage1013_no_anchor_targets.jsonl"))
    parser.add_argument("--char-state", type=Path, default=Path("runs/local/artifacts/stage1024_char_schema_equality_counted_state.pt"))
    parser.add_argument("--max-entity-min", type=int, default=3)
    parser.add_argument("--max-slot-min", type=int, default=3)
    parser.add_argument("--output-json", type=Path, default=Path("runs/local/artifacts/stage1030_allop_char_schema_policy_sweep_summary.json"))
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
    rows = _rows_by_split(args.targets_jsonl)

    operations = sorted({str(row.get("operation", "unknown")) for row in rows["calibration"]})
    policy_grid: list[tuple[int, int] | None] = [None]
    for ent_min in range(int(args.max_entity_min) + 1):
        for slot_min in range(int(args.max_slot_min) + 1):
            policy_grid.append((ent_min, slot_min))

    selected: dict[str, tuple[int, int] | None] = {}
    calibration_sweeps: dict[str, list[dict[str, Any]]] = {}
    for op in operations:
        op_rows = [row for row in rows["calibration"] if str(row.get("operation", "unknown")) == op]
        scores = []
        for policy in policy_grid:
            score = _score_split(entity_model, slot_model, stage1024._features, op_rows, {op: policy}, entity_threshold, slot_threshold)
            scores.append({"policy": None if policy is None else list(policy), "score": score})
        best = max(scores, key=lambda item: (item["score"]["answer"], item["score"]["exact"], -999 if item["policy"] is None else item["policy"][0] + item["policy"][1]))
        selected[op] = None if best["policy"] is None else tuple(int(x) for x in best["policy"])
        calibration_sweeps[op] = scores

    calibration = _score_split(entity_model, slot_model, stage1024._features, rows["calibration"], selected, entity_threshold, slot_threshold)
    eval_score = _score_split(entity_model, slot_model, stage1024._features, rows["eval"], selected, entity_threshold, slot_threshold)
    train_score = _score_split(entity_model, slot_model, stage1024._features, rows["train"], selected, entity_threshold, slot_threshold)
    summary = {
        "artifact_kind": "stage1030_allop_char_schema_policy_sweep",
        "status": "completed_all_operation_char_schema_policy_sweep",
        "targets_jsonl": str(args.targets_jsonl),
        "char_state": str(args.char_state),
        "entity_threshold": entity_threshold,
        "slot_threshold": slot_threshold,
        "selected_policy_by_operation": {op: None if policy is None else list(policy) for op, policy in selected.items()},
        "train": train_score,
        "calibration": calibration,
        "eval": eval_score,
        "stage1025_eval_answer_exact": [334, 317],
        "implied_full_answer_exact": [int(eval_score["answer"]), int(eval_score["exact"])],
        "decision": "Sweeps whether the counted learned char schema-equality/count module should apply beyond composition/relation. Policies are selected on calibration per operation and evaluated on the no-anchor eval split.",
    }
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
