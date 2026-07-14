#!/usr/bin/env python3
from __future__ import annotations

import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
BASE_DIR = ROOT / "runs/local/artifacts/stage11156_cleaned_plus_local_verifier_support_package"
ADMITTED = (
    ROOT
    / "runs/local/artifacts/stage11161_explicit_verifier_transition_admission_audit/admitted_explicit_verifier_transition_rows.jsonl"
)
OUT_DIR = ROOT / "runs/local/artifacts/stage11162_cleaned_plus_explicit_verifier_transition_support_package"

SPLITS = {
    "train": "agentkernel_lite_encdec_train.jsonl",
    "validation": "agentkernel_lite_encdec_validation.jsonl",
    "strict_eval": "agentkernel_lite_encdec_strict_eval.jsonl",
    "stress_eval": "agentkernel_lite_encdec_stress_eval.jsonl",
}


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    base = {split: read_jsonl(BASE_DIR / name) for split, name in SPLITS.items()}
    admitted = read_jsonl(ADMITTED)
    base_ids = {str(row.get("row_id") or "") for rows in base.values() for row in rows}
    base_roots = {str(row.get("source_root_id") or "") for rows in base.values() for row in rows if row.get("source_root_id")}

    blockers: list[dict[str, Any]] = []
    rows_to_add: list[dict[str, Any]] = []
    for row in admitted:
        reasons = []
        if str(row.get("row_id") or "") in base_ids:
            reasons.append("row_id_overlap_base_package")
        if str(row.get("source_root_id") or "") in base_roots:
            reasons.append("source_root_overlap_base_package")
        if reasons:
            blockers.append({"row_id": row.get("row_id"), "source_root_id": row.get("source_root_id"), "blockers": reasons})
            continue
        new_row = dict(row)
        new_row["split"] = "train"
        new_row["split_role"] = "train_support"
        new_row["support_package_stage"] = 11162
        existing = new_row.get("support_provenance") if isinstance(new_row.get("support_provenance"), dict) else {}
        new_row["support_provenance"] = {
            **existing,
            "source_manifest": rel(ADMITTED),
            "support_class": "explicit_verifier_transition_competition",
            "support_role": "train_support_only",
        }
        rows_to_add.append(new_row)

    train = base["train"] + rows_to_add
    write_jsonl(OUT_DIR / SPLITS["train"], train)
    for split in ("validation", "strict_eval", "stress_eval"):
        write_jsonl(OUT_DIR / SPLITS[split], base[split])
    write_jsonl(OUT_DIR / "added_explicit_verifier_transition_rows.jsonl", rows_to_add)

    summary = {
        "stage": 11162,
        "stage_name": "cleaned_plus_explicit_verifier_transition_support_package",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_artifacts": {
            "base_package_dir": rel(BASE_DIR),
            "admitted_rows": rel(ADMITTED),
        },
        "metrics": {
            "train_rows_before": len(base["train"]),
            "train_rows_after": len(train),
            "rows_added": len(rows_to_add),
            "blocked_rows": len(blockers),
            "validation_rows": len(base["validation"]),
            "strict_rows": len(base["strict_eval"]),
            "stress_rows": len(base["stress_eval"]),
            "added_unique_roots": len({row.get("source_root_id") for row in rows_to_add}),
            "added_by_semantic_target": dict(sorted(Counter(str(row.get("semantic_target_value")) for row in rows_to_add).items())),
            "added_by_target_label": dict(sorted(Counter(str(row.get("target_text")) for row in rows_to_add).items())),
            "added_by_task": dict(sorted(Counter(str(row.get("task_type")) for row in rows_to_add).items())),
        },
        "blockers": blockers,
        "decision": "support_package_ready_for_diagnostic_probe" if rows_to_add and not blockers else "support_package_blocked_or_empty",
        "claim_scope": (
            "Adds explicit local verifier-transition competition support rows. Strict/validation/stress rows "
            "are unchanged from cleaned stage11146 via stage11156. This is diagnostic support, not heldout evidence."
        ),
        "outputs": {
            "train_jsonl": rel(OUT_DIR / SPLITS["train"]),
            "validation_jsonl": rel(OUT_DIR / SPLITS["validation"]),
            "strict_jsonl": rel(OUT_DIR / SPLITS["strict_eval"]),
            "stress_jsonl": rel(OUT_DIR / SPLITS["stress_eval"]),
            "added_rows_jsonl": rel(OUT_DIR / "added_explicit_verifier_transition_rows.jsonl"),
            "summary_json": rel(OUT_DIR / "cleaned_plus_explicit_verifier_transition_support_package.json"),
        },
    }
    (OUT_DIR / "cleaned_plus_explicit_verifier_transition_support_package.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
