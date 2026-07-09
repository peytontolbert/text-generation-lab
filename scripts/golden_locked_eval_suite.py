from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

LOCKED_ROLES = {"locked_regression", "hidden_final", "promotion_only"}
TRAIN_FORBIDDEN_ROLES = {"locked_regression", "hidden_final", "promotion_only", "holdout_only"}


def pack_id(pack: dict[str, Any], idx: int = 0) -> str:
    return str(pack.get("task_pack_id") or pack.get("locked_eval_id") or pack.get("source_id") or f"pack_{idx}")


def validate_pack(pack: dict[str, Any], *, idx: int = 0) -> dict[str, Any]:
    failures: list[str] = []
    split_role = str(pack.get("split_role") or "")
    if split_role not in LOCKED_ROLES:
        failures.append("split_role_not_locked")
    if pack.get("train_eligible") is not False:
        failures.append("train_eligible_not_false")
    if pack.get("promotion_only") is not True and split_role != "hidden_final":
        failures.append("promotion_only_not_true")
    if not pack.get("source_id"):
        failures.append("missing_source_id")
    if not pack.get("lineage_hash"):
        failures.append("missing_lineage_hash")
    if not isinstance(pack.get("thresholds"), dict) or not pack.get("thresholds"):
        failures.append("missing_thresholds")
    if not isinstance(pack.get("slice_tags"), list) or not pack.get("slice_tags"):
        failures.append("missing_slice_tags")
    if split_role in TRAIN_FORBIDDEN_ROLES and not pack.get("blocked_training_reason"):
        failures.append("missing_blocked_training_reason")
    return {
        "task_pack_id": pack_id(pack, idx),
        "source_id": pack.get("source_id"),
        "split_role": split_role,
        "train_eligible": pack.get("train_eligible"),
        "promotion_only": pack.get("promotion_only"),
        "hidden_final": bool(pack.get("hidden_final")),
        "slice_tags": pack.get("slice_tags", []),
        "failures": failures,
        "passed": not failures,
    }


def validate_suite(packs: list[dict[str, Any]]) -> dict[str, Any]:
    records = [validate_pack(pack, idx=idx) for idx, pack in enumerate(packs)]
    locked_source_ids = sorted({str(record["source_id"]) for record in records if record.get("source_id")})
    slice_tags = sorted({tag for record in records for tag in record.get("slice_tags", [])})
    failures = [record for record in records if not record["passed"]]
    return {
        "packs": len(packs),
        "records": records,
        "locked_source_ids": locked_source_ids,
        "metrics": {
            "packs": len(packs),
            "passed_packs": len(records) - len(failures),
            "failed_packs": len(failures),
            "train_eligible_packs": sum(int(record.get("train_eligible") is True) for record in records),
            "promotion_only_packs": sum(int(record.get("promotion_only") is True) for record in records),
            "hidden_final_packs": sum(int(record.get("hidden_final") is True) for record in records),
            "locked_source_ids": len(locked_source_ids),
            "slice_tags": slice_tags,
        },
        "passed": not failures and bool(records),
    }


def builder_exclusion_decision(row: dict[str, Any], locked_source_ids: set[str]) -> dict[str, Any]:
    source_id = str(row.get("source_id") or "")
    lineage = row.get("source_lineage") if isinstance(row.get("source_lineage"), dict) else {}
    candidate_ids = {source_id}
    if isinstance(row.get("source_ids"), list):
        candidate_ids.update(str(value) for value in row["source_ids"] if value)
    for key, value in lineage.items():
        if (key.endswith("source_id") or key in {"source_id", "lineage_hash"}) and value:
            candidate_ids.add(str(value))
    candidate_ids.discard("")
    matched_locked_ids = sorted(candidate_ids & locked_source_ids)
    blocked = bool(matched_locked_ids) or row.get("split_role") in TRAIN_FORBIDDEN_ROLES
    return {
        "row_id": row.get("row_id") or row.get("candidate_id") or row.get("id"),
        "blocked_from_training": bool(blocked),
        "reason": "locked_eval_source_never_mined_into_training" if blocked else "not_locked_eval_source",
        "matched_locked_source_ids": matched_locked_ids,
    }


def load_locked_source_ids_from_exclusions(path: Path) -> set[str]:
    locked: set[str] = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        if row.get("blocked_from_training") is True and row.get("source_id"):
            locked.add(str(row["source_id"]))
    return locked


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate golden locked eval packs and emit locked source exclusions.")
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()
    data = read_json(args.manifest)
    packs = data.get("benchmark_packs", data if isinstance(data, list) else [])
    card = validate_suite(packs)
    text = json.dumps(card, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
    print(text, end="")


if __name__ == "__main__":
    main()
