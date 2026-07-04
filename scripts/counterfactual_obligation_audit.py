#!/usr/bin/env python3
"""Audit counterfactual sibling obligations for curriculum manifests."""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


DEFAULT_REQUIRED_OBLIGATIONS = {
    "POSITIVE_ORIGINAL",
    "EVIDENCE_REMOVED_OR_RETRIEVE",
    "CONTRASTIVE_BOUNDARY_SIBLING",
}

GUARD_REQUIRED_OBLIGATIONS = {
    "POSITIVE_ORIGINAL",
    "EVIDENCE_REMOVED",
    "CONTRADICTORY_EVIDENCE_OR_UNSAFE_TWIN",
    "MIXED_REPLAY",
}


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def obligation_type(row: dict[str, Any]) -> str:
    return str(row.get("obligation_type") or row.get("curriculum_obligation") or row.get("role") or "")


def group_id(row: dict[str, Any]) -> str:
    return str(row.get("counterfactual_group_id") or row.get("sibling_group_id") or row.get("semantic_key") or "")


def required_for_objective(objective_family: str | None) -> set[str]:
    if objective_family and "guard" in objective_family:
        return set(GUARD_REQUIRED_OBLIGATIONS)
    return set(DEFAULT_REQUIRED_OBLIGATIONS)


def audit_rows(rows: list[dict[str, Any]], required: set[str] | None = None) -> dict[str, Any]:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    missing_group_rows = []
    objective_counts: Counter[str] = Counter()
    obligation_counts: Counter[str] = Counter()
    for row in rows:
        objective_counts[str(row.get("objective_family", ""))] += 1
        obligation_counts[obligation_type(row)] += 1
        gid = group_id(row)
        if gid:
            groups[gid].append(row)
        else:
            missing_group_rows.append(str(row.get("row_id", "")))

    missing_obligation_groups = []
    for gid, group_rows in groups.items():
        objective = str(group_rows[0].get("objective_family", ""))
        required_set = required if required is not None else required_for_objective(objective)
        present = {obligation_type(row) for row in group_rows}
        missing = sorted(required_set - present)
        if missing:
            missing_obligation_groups.append(
                {
                    "group_id": gid,
                    "objective_family": objective,
                    "present": sorted(present),
                    "missing": missing,
                    "rows": [str(row.get("row_id", "")) for row in group_rows[:10]],
                }
            )

    return {
        "rows": len(rows),
        "groups": len(groups),
        "objective_counts": dict(objective_counts),
        "obligation_counts": dict(obligation_counts),
        "missing_group_rows": len(missing_group_rows),
        "missing_group_row_examples": missing_group_rows[:100],
        "missing_obligation_groups": len(missing_obligation_groups),
        "missing_obligation_group_examples": missing_obligation_groups[:100],
        "counterfactual_obligations_complete": not missing_group_rows and not missing_obligation_groups,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--required", nargs="*", default=None)
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()
    required = set(args.required) if args.required else None
    card = audit_rows(read_jsonl(args.manifest), required=required)
    text = json.dumps(card, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
    print(text, end="")
    return 0 if card["counterfactual_obligations_complete"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
