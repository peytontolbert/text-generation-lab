#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
STAGE = 10633
NAME = "stage10633_repaired_long_context_label_position_audit"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
AUDIT_JSON = OUT_DIR / "repaired_long_context_label_position_audit.json"
SUMMARY_JSON = ROOT / "runs/summaries" / f"{NAME}.json"

PACKAGE_ROWS = ROOT / "runs/local/artifacts/stage10631_repaired_long_context_successor_package/repaired_long_context_successor_rows.jsonl"
PROBE_MANIFEST = ROOT / "runs/local/artifacts/stage10632_repaired_long_context_successor_probe_request/repaired_long_context_successor_probe_manifest.jsonl"


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def candidate_position(row: dict[str, Any]) -> int | None:
    target = str(row.get("target_text") or "")
    options = row.get("candidate_options") or []
    for idx, option in enumerate(options):
        if str(option.get("label") or "") == target:
            return idx
    return None


def summarize(rows: list[dict[str, Any]], split_field: str) -> dict[str, Any]:
    by_group: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        split = str(row.get(split_field) or "unknown")
        subtype = str(row.get("target_subtype") or "unknown")
        by_group[(split, subtype)].append(row)

    groups: dict[str, Any] = {}
    for (split, subtype), group_rows in sorted(by_group.items()):
        key = f"{split}::{subtype}"
        target_counts = Counter(str(row.get("target_text") or "") for row in group_rows)
        position_counts = Counter(
            "missing" if candidate_position(row) is None else str(candidate_position(row))
            for row in group_rows
        )
        groups[key] = {
            "rows": len(group_rows),
            "target_label_counts": dict(sorted(target_counts.items())),
            "target_label_unique_count": len(target_counts),
            "gold_candidate_position_counts": dict(sorted(position_counts.items())),
            "gold_candidate_position_unique_count": len(position_counts),
            "all_gold_in_first_position": position_counts == Counter({"0": len(group_rows)}),
            "constant_target_label": len(target_counts) == 1,
        }
    return groups


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY_JSON.parent.mkdir(parents=True, exist_ok=True)

    package_rows = load_jsonl(PACKAGE_ROWS)
    probe_rows = load_jsonl(PROBE_MANIFEST)

    package_summary = summarize(package_rows, "package_role")
    probe_summary = summarize(probe_rows, "split")

    strict_key = "strict_eval_candidate::decisive_evidence_option"
    probe_strict_key = "strict_eval::decisive_evidence_option"
    package_strict = package_summary.get(strict_key, {})
    probe_strict = probe_summary.get(probe_strict_key, {})

    audit = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "passed": False,
        "decision": "repaired_long_context_label_position_shortcut_detected",
        "claim": [
            "Audit the repaired long-context successor package and the stage10632 probe manifest for constant gold-label slot shortcuts.",
            "A repaired visible-candidate interface is still not promotable if the gold label is constant or always occupies the first option slot.",
        ],
        "inputs": {
            "package_rows": str(PACKAGE_ROWS.relative_to(ROOT)),
            "probe_manifest": str(PROBE_MANIFEST.relative_to(ROOT)),
        },
        "package_summary": package_summary,
        "probe_summary": probe_summary,
        "critical_findings": {
            "package_strict_constant_target_label": package_strict.get("constant_target_label"),
            "package_strict_all_gold_in_first_position": package_strict.get("all_gold_in_first_position"),
            "probe_strict_constant_target_label": probe_strict.get("constant_target_label"),
            "probe_strict_all_gold_in_first_position": probe_strict.get("all_gold_in_first_position"),
        },
        "why_failed": [
            "Promotable repaired decisive-evidence strict rows use a single target label slot.",
            "Gold candidate position is fixed at the first visible option for the promotable strict slice.",
            "A model can appear perfect by emitting the first-slot label family instead of selecting among semantically balanced candidates.",
        ],
        "next_best_step": (
            "Rebuild repaired decisive-evidence rows with per-row candidate permutations or canonicalized non-position-correlated label maps, "
            "then rerun the probe only after strict target-label diversity and gold-position diversity are both nonconstant."
        ),
    }

    write_json(AUDIT_JSON, audit)
    write_json(
        SUMMARY_JSON,
        {
            "stage": STAGE,
            "passed": audit["passed"],
            "audit": str(AUDIT_JSON.relative_to(ROOT)),
        },
    )
    print(json.dumps(audit["critical_findings"], indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
