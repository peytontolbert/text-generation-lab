#!/usr/bin/env python3
"""Patch relation rows with query-side qslot aliases for Stage952 diagnostics."""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path
from typing import Any


def iter_jsonl(path: Path):
    with path.open() as f:
        for line in f:
            line = line.strip()
            if line:
                yield json.loads(line)


def dslots(candidate: dict[str, Any]) -> list[str]:
    return [str(x) for x in ((candidate.get("bridge", {}) or {}).get("dslot", []) or []) if str(x)]


def patch_relation_row(row: dict[str, Any]) -> tuple[dict[str, Any], bool]:
    if row.get("operation") != "relation":
        return row, False
    row = json.loads(json.dumps(row))
    candidates = list(row.get("candidates", []) or [])
    positive_slots = sorted({slot for candidate in candidates if candidate.get("is_exact") for slot in dslots(candidate)})
    if not positive_slots:
        return row, False
    query_bridge = dict(row.get("query_bridge", {}) or {})
    query_bridge["qslot"] = positive_slots
    row["query_bridge"] = query_bridge
    qslot_tokens = " ".join(f"qslot_{slot}" for slot in positive_slots)
    query_text = str(row.get("query_text", "") or "")
    if "latent_relation_query_slot=" not in query_text:
        row["query_text"] = f"{query_text} latent_relation_query_slot={qslot_tokens}".strip()
    for candidate in candidates:
        bridge = dict(candidate.get("bridge", {}) or {})
        bridge["qslot"] = positive_slots
        bridge["slot_suffix_match"] = bool(set(positive_slots).intersection(dslots(candidate)))
        candidate["bridge"] = bridge
    row["stage952_relation_qslot_patch"] = {
        "positive_dslot_targets": positive_slots,
        "caveat": "diagnostic patch uses materialized relation slot targets; accepted model claims require deriving qslot from relation text without answer leakage",
    }
    return row, True


def score_slot_oracle(rows: list[dict[str, Any]]) -> dict[str, int]:
    answer = exact = recoverable = missing = 0
    for row in rows:
        candidates = list(row.get("candidates", []) or [])
        exact_candidates = [c for c in candidates if c.get("is_exact")]
        if exact_candidates:
            recoverable += 1
        pool = [
            c
            for c in candidates
            if (c.get("bridge", {}) or {}).get("slot_suffix_match")
            and (c.get("bridge", {}) or {}).get("entity_suffix_match")
            and (c.get("bridge", {}) or {}).get("pair_suffix_match")
        ]
        if not pool:
            missing += 1
            continue
        top = max(pool, key=lambda c: (float(c.get("base_score", 0.0) or 0.0), -int(c.get("rank", 9999) or 9999)))
        answer += int(bool(top.get("is_exact") or top.get("is_answer_match")))
        exact += int(bool(top.get("is_exact")))
    return {"rows": len(rows), "answer": answer, "exact": exact, "recoverable": recoverable, "missing": missing}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-targets-jsonl", type=Path, default=Path("runs/local/artifacts/stage923_stage918_bridge_teacher_targets.jsonl"))
    parser.add_argument("--output-targets-jsonl", type=Path, default=Path("runs/local/artifacts/stage952_relation_query_slot_patched_targets.jsonl"))
    parser.add_argument("--output-summary", type=Path, default=Path("runs/local/artifacts/stage952_relation_query_slot_patch_summary.json"))
    args = parser.parse_args()

    patched_rows: list[dict[str, Any]] = []
    relation_by_split: dict[str, list[dict[str, Any]]] = defaultdict(list)
    patch_counts = defaultdict(lambda: {"rows": 0, "patched": 0})
    for row in iter_jsonl(args.input_targets_jsonl):
        patched, changed = patch_relation_row(row)
        split = str(patched.get("split"))
        if patched.get("operation") == "relation":
            patch_counts[split]["rows"] += 1
            patch_counts[split]["patched"] += int(changed)
            relation_by_split[split].append(patched)
        patched_rows.append(patched)

    args.output_targets_jsonl.parent.mkdir(parents=True, exist_ok=True)
    with args.output_targets_jsonl.open("w") as f:
        for row in patched_rows:
            f.write(json.dumps(row, sort_keys=True) + "\n")

    split_stats = {}
    for split, rows in sorted(relation_by_split.items()):
        qslot_rows = sum(1 for row in rows if (row.get("query_bridge", {}) or {}).get("qslot"))
        slot_match_candidates = sum(
            1
            for row in rows
            for candidate in row.get("candidates", []) or []
            if (candidate.get("bridge", {}) or {}).get("slot_suffix_match")
        )
        split_stats[split] = {
            **patch_counts[split],
            "qslot_rows": qslot_rows,
            "slot_match_candidates": slot_match_candidates,
            "slot_entity_pair_oracle": score_slot_oracle(rows),
        }

    summary = {
        "artifact_kind": "stage952_relation_query_slot_patch",
        "status": "diagnostic_surface_patch_no_model_frontier_change",
        "inputs": {"targets_jsonl": str(args.input_targets_jsonl)},
        "outputs": {"patched_targets_jsonl": str(args.output_targets_jsonl)},
        "baseline": {
            "stage944_relation_answer_exact": [52, 52],
            "stage950_entity_pair_diagnostic_answer_exact": [82, 82],
            "stage950_qslot_value_oracle_answer_exact": [100, 100],
        },
        "split_stats": split_stats,
        "decision": "Materialized a relation query-slot patched target surface. This is diagnostic until qslot aliases are generated from relation text by the surface builder rather than copied from positive eval slots.",
        "next_steps": [
            {
                "stage": "Stage953",
                "target": "train_relation_on_query_slot_patched_surface",
                "acceptance": "Relation >52/52 and global >252/235 without external suffix-equality scoring.",
            }
        ],
    }
    args.output_summary.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"output": str(args.output_summary), "eval": split_stats.get("eval")}, indent=2))


if __name__ == "__main__":
    main()
