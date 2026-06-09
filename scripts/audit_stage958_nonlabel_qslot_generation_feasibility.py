#!/usr/bin/env python3
"""Audit whether relation qslot aliases can be generated without eval labels."""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


REL_RE = re.compile(r"query=\S+\s+([A-Za-z0-9_\-]+)")


def iter_jsonl(path: Path):
    with path.open() as f:
        for line in f:
            line = line.strip()
            if line:
                yield json.loads(line)


def relation_text(query_text: str) -> str:
    match = REL_RE.search(query_text)
    return match.group(1) if match else "unknown"


def dslots(candidate: dict[str, Any]) -> list[str]:
    return [str(x) for x in ((candidate.get("bridge", {}) or {}).get("dslot", []) or []) if str(x)]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--targets-jsonl", type=Path, default=Path("runs/local/artifacts/stage923_stage918_bridge_teacher_targets.jsonl"))
    parser.add_argument("--output", type=Path, default=Path("runs/local/artifacts/stage958_nonlabel_qslot_generation_feasibility_summary.json"))
    args = parser.parse_args()

    relation_rows: dict[str, list[dict[str, Any]]] = defaultdict(list)
    positive_slots_by_split_relation: dict[str, dict[str, Counter]] = defaultdict(lambda: defaultdict(Counter))
    all_doc_slots_by_split_relation: dict[str, dict[str, Counter]] = defaultdict(lambda: defaultdict(Counter))
    opaque_doc_relation_names = Counter()

    for row in iter_jsonl(args.targets_jsonl):
        if row.get("operation") != "relation":
            continue
        split = str(row.get("split"))
        rel = relation_text(str(row.get("query_text", "") or ""))
        relation_rows[split].append(row)
        for candidate in row.get("candidates", []) or []:
            for slot in dslots(candidate):
                all_doc_slots_by_split_relation[split][rel][slot] += 1
                if candidate.get("is_exact"):
                    positive_slots_by_split_relation[split][rel][slot] += 1
            doc_text = str(candidate.get("doc_text", "") or "")
            if " linked_to " in doc_text or "relation=" in doc_text:
                opaque_doc_relation_names["has_relation_surface"] += 1
            else:
                opaque_doc_relation_names["opaque_dslot_only"] += 1

    split_summary = {}
    for split, rows in sorted(relation_rows.items()):
        rel_counts = Counter(relation_text(str(row.get("query_text", "") or "")) for row in rows)
        qslot_rows = sum(1 for row in rows if (row.get("query_bridge", {}) or {}).get("qslot"))
        exact_rows = sum(1 for row in rows if any(c.get("is_exact") for c in row.get("candidates", []) or []))
        split_summary[split] = {
            "rows": len(rows),
            "relation_text_counts": dict(sorted(rel_counts.items())),
            "query_qslot_rows": qslot_rows,
            "exact_recoverable_rows": exact_rows,
            "positive_slot_distinct_by_relation": {
                rel: len(counter) for rel, counter in sorted(positive_slots_by_split_relation[split].items())
            },
            "all_doc_slot_distinct_by_relation": {
                rel: len(counter) for rel, counter in sorted(all_doc_slots_by_split_relation[split].items())
            },
        }

    transfer = {}
    splits = sorted(relation_rows)
    for a in splits:
        for b in splits:
            if a >= b:
                continue
            key = f"{a}_vs_{b}"
            transfer[key] = {}
            rels = set(positive_slots_by_split_relation[a]) | set(positive_slots_by_split_relation[b])
            for rel in sorted(rels):
                sa = set(positive_slots_by_split_relation[a][rel])
                sb = set(positive_slots_by_split_relation[b][rel])
                transfer[key][rel] = {
                    "positive_slot_overlap": len(sa & sb),
                    "left_distinct": len(sa),
                    "right_distinct": len(sb),
                }

    summary = {
        "artifact_kind": "stage958_nonlabel_qslot_generation_feasibility",
        "status": "diagnostic_current_artifacts_insufficient_for_nonlabel_qslot_generation",
        "targets_jsonl": str(args.targets_jsonl),
        "split_summary": split_summary,
        "positive_slot_transfer": transfer,
        "doc_relation_surface_audit": dict(opaque_doc_relation_names),
        "decision": (
            "Current relation target artifacts do not contain enough non-label information to regenerate eval qslot aliases. "
            "Relation query text exposes the relation name, but candidate docs expose only opaque split-local dslot ids; train positive dslot ids do not transfer across held-out split salts."
        ),
        "next_steps": [
            {
                "stage": "Stage959",
                "target": "patch_surface_builder_relation_qslot",
                "goal": "Modify the source surface/hardener so relation query rows emit side-invariant qslot aliases before split-local hashing and before candidate labels are materialized.",
            },
            {
                "stage": "Stage960",
                "target": "rebuild_relation_targets_with_nonlabel_qslot",
                "goal": "Regenerate train/calibration/eval targets and rerun Stage956 equality primitive under the Stage957 contract.",
            },
        ],
    }
    args.output.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"output": str(args.output), "split_summary": split_summary, "transfer": transfer}, indent=2)[:8000])


if __name__ == "__main__":
    main()
