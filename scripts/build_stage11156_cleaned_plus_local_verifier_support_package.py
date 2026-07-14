#!/usr/bin/env python3
"""Append admitted local verifier-transition support rows to cleaned package."""

from __future__ import annotations

import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
BASE_DIR = ROOT / "runs/local/artifacts/stage11146_singleton_strict_quarantine_successor"
ADMITTED = (
    ROOT
    / "runs/local/artifacts/stage11155_local_verifier_transition_admission_audit/admitted_local_verifier_transition_rows.jsonl"
)
OUT_DIR = ROOT / "runs/local/artifacts/stage11156_cleaned_plus_local_verifier_support_package"

SPLITS = {
    "train": "agentkernel_lite_encdec_train.jsonl",
    "validation": "agentkernel_lite_encdec_validation.jsonl",
    "strict_eval": "agentkernel_lite_encdec_strict_eval.jsonl",
    "stress_eval": "agentkernel_lite_encdec_stress_eval.jsonl",
}


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.exists():
        return rows
    with path.open() as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w") as f:
        for row in rows:
            f.write(json.dumps(row, sort_keys=True) + "\n")


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    base = {split: read_jsonl(BASE_DIR / name) for split, name in SPLITS.items()}
    admitted = read_jsonl(ADMITTED)
    base_train_ids = {row.get("row_id") for row in base["train"]}
    base_eval_ids = {
        row.get("row_id")
        for split in ("validation", "strict_eval", "stress_eval")
        for row in base[split]
    }
    base_roots = {
        row.get("source_root_id")
        for split_rows in base.values()
        for row in split_rows
        if row.get("source_root_id")
    }
    blockers: list[dict[str, Any]] = []
    rows_to_add = []
    for row in admitted:
        reasons = []
        if row.get("row_id") in base_train_ids:
            reasons.append("row_id_overlap_train")
        if row.get("row_id") in base_eval_ids:
            reasons.append("row_id_overlap_eval")
        if row.get("source_root_id") in base_roots:
            reasons.append("source_root_overlap_existing_package")
        if reasons:
            blockers.append({"row_id": row.get("row_id"), "blockers": reasons})
        else:
            new_row = dict(row)
            new_row["split"] = "train"
            new_row["split_role"] = "train_support"
            new_row["support_package_stage"] = 11156
            new_row.setdefault("support_provenance", {})
            new_row["support_provenance"] = {
                **(new_row["support_provenance"] if isinstance(new_row["support_provenance"], dict) else {}),
                "source_manifest": str(ADMITTED.relative_to(ROOT)),
                "support_class": "local_repo_pass_to_pass_verifier_transition_guardrail",
                "support_role": "train_support_only",
            }
            rows_to_add.append(new_row)

    train = base["train"] + rows_to_add
    write_jsonl(OUT_DIR / SPLITS["train"], train)
    for split in ("validation", "strict_eval", "stress_eval"):
        write_jsonl(OUT_DIR / SPLITS[split], base[split])
    write_jsonl(OUT_DIR / "added_local_verifier_transition_rows.jsonl", rows_to_add)

    summary = {
        "stage": 11156,
        "stage_name": "cleaned_plus_local_verifier_support_package",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_artifacts": {
            "base_package_dir": str(BASE_DIR.relative_to(ROOT)),
            "admitted_rows": str(ADMITTED.relative_to(ROOT)),
        },
        "metrics": {
            "train_rows_before": len(base["train"]),
            "train_rows_after": len(train),
            "rows_added": len(rows_to_add),
            "blocked_rows": len(blockers),
            "validation_rows": len(base["validation"]),
            "strict_rows": len(base["strict_eval"]),
            "stress_rows": len(base["stress_eval"]),
            "added_by_target": dict(sorted(Counter(str(r.get("target_text")) for r in rows_to_add).items())),
            "added_by_task": dict(sorted(Counter(str(r.get("task_type")) for r in rows_to_add).items())),
            "added_unique_roots": len({r.get("source_root_id") for r in rows_to_add}),
        },
        "blockers": blockers,
        "decision": "support_package_ready_for_diagnostic_probe" if rows_to_add and not blockers else "support_package_blocked_or_empty",
        "claim_scope": (
            "Adds local PASS_TO_PASS verifier-transition guardrail support only. "
            "Strict/validation/stress rows are unchanged from cleaned stage11146."
        ),
        "outputs": {
            "train_jsonl": str((OUT_DIR / SPLITS["train"]).relative_to(ROOT)),
            "validation_jsonl": str((OUT_DIR / SPLITS["validation"]).relative_to(ROOT)),
            "strict_jsonl": str((OUT_DIR / SPLITS["strict_eval"]).relative_to(ROOT)),
            "stress_jsonl": str((OUT_DIR / SPLITS["stress_eval"]).relative_to(ROOT)),
            "added_rows_jsonl": str((OUT_DIR / "added_local_verifier_transition_rows.jsonl").relative_to(ROOT)),
            "summary_json": str((OUT_DIR / "cleaned_plus_local_verifier_support_package.json").relative_to(ROOT)),
        },
    }
    (OUT_DIR / "cleaned_plus_local_verifier_support_package.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n"
    )
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
