#!/usr/bin/env python3
"""Build a larger Transition-5K-v1 package from admitted support-row sources.

This is a data/package stage, not a training run. It deliberately expands beyond
Stage11945 while preserving root-level split isolation and anti-leak checks.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import shutil
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "runs/local/artifacts"
SUMMARIES = ROOT / "runs/summaries"
STAGE = 11955
NAME = "stage11955_transition_5k_v1_multisource_package"
OUT = ART / NAME
SUMMARY = OUT / "transition_5k_v1_multisource_package.json"
RECORDS = OUT / "verified_transition_records_5k_v1.jsonl"
ROWS = OUT / "transition_projection_rows_5k_v1.jsonl"
ADMITTED_ROWS = OUT / "admitted_source_rows.jsonl"
REJECTED_ROWS = OUT / "rejected_source_rows.jsonl"

INVENTORY = ART / "stage11944_transition_1k_v2_source_inventory_and_plan/source_inventory.jsonl"
OLD_TRANSITION_ROWS = ART / "stage11897_transition_record_projection_rows/transition_projection_rows.jsonl"
GEMMA_GAP_ROWS = ART / "stage11943_transition_gemma_gap_atlas/transition_gemma_gap_rows.jsonl"

stage11945_spec = importlib.util.spec_from_file_location(
    "stage11945_builder",
    ROOT / "scripts/build_stage11945_transition_1k_v2_multisource_package.py",
)
stage11945 = importlib.util.module_from_spec(stage11945_spec)
assert stage11945_spec and stage11945_spec.loader
stage11945_spec.loader.exec_module(stage11945)  # type: ignore[union-attr]

projection = stage11945.projection


def now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def rel(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def stable_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def root_split(root: str) -> str:
    bucket = int(hashlib.sha256(root.encode("utf-8")).hexdigest()[:8], 16) % 100
    if bucket < 74:
        return "train"
    if bucket < 87:
        return "validation"
    return "strict_eval"


def source_priority(row: dict[str, Any]) -> tuple[int, int, int, int]:
    """Prefer sources with options, verifier anchors, task breadth, and roots."""
    task_count = len(row.get("task_counts") or {})
    return (
        int(row.get("opaque_option_rows") or 0),
        int(row.get("verifier_or_selected_test_rows") or 0),
        task_count,
        int(row.get("unique_roots") or 0),
    )


def normalize_record(record: dict[str, Any], source_path: str, old_root_overlap: bool) -> dict[str, Any]:
    out = dict(record)
    old_id = str(out.get("record_id") or "")
    out["record_id"] = old_id.replace("stage11945::", "stage11955::", 1) if old_id.startswith("stage11945::") else f"stage11955::{stable_hash(old_id)}::{old_id}"
    out["provenance"] = dict(out.get("provenance") or {})
    out["provenance"].update(
        {
            "compiler": NAME,
            "source_artifact": source_path,
            "old_transition_root_overlap": old_root_overlap,
            "transition_5k_v1": True,
        }
    )
    out["gate_status"] = dict(out.get("gate_status") or {})
    out["gate_status"]["transition_5k_v1_admission"] = True
    return out


def candidate_status(record: dict[str, Any]) -> str:
    return str(((record.get("verifier_result") or {}).get("verifier_status")) or "UNKNOWN")


def row_id(row: dict[str, Any]) -> str:
    return str(row.get("row_id") or row.get("id") or "")


def main() -> None:
    inventory = [item for item in read_jsonl(INVENTORY) if item.get("rows", 0) > 0]
    inventory = sorted(inventory, key=source_priority, reverse=True)
    old_roots = {str(row.get("root_id")) for row in read_jsonl(OLD_TRANSITION_ROWS)}
    gemma_gap = read_jsonl(GEMMA_GAP_ROWS)
    gap_language_task = Counter(
        (
            str(row.get("language_family") or "unknown"),
            str(row.get("task_type") or "unknown"),
        )
        for row in gemma_gap
        if row.get("winner") == "gemma_only" or row.get("comparison_bucket") == "gemma_only"
    )

    admitted_records: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    seen_row_ids: set[str] = set()
    seen_source_rows: set[str] = set()
    root_split_map: dict[str, str] = {}
    root_row_counts: Counter[str] = Counter()
    root_task_counts: Counter[tuple[str, str]] = Counter()
    lang_counts: Counter[str] = Counter()
    source_counts: Counter[str] = Counter()
    status_counts: Counter[str] = Counter()

    max_records = 1500
    per_language_caps = {
        "c_cpp": 360,
        "python": 360,
        "rust": 360,
        "web_js_ts_html": 520,
    }
    per_source_cap = 180
    per_root_cap = 12
    per_root_task_cap = 3

    for src in inventory:
        if len(admitted_records) >= max_records:
            break
        source_path = str(src["path"])
        path = ROOT / source_path
        for row in read_jsonl(path):
            if len(admitted_records) >= max_records:
                break
            if source_counts[source_path] >= per_source_cap:
                rejected.append({"source_path": source_path, "row_id": row.get("row_id"), "failures": ["source_cap_reached"]})
                continue
            rid = str(row.get("row_id") or "")
            if rid in seen_source_rows:
                rejected.append({"source_path": source_path, "row_id": rid, "failures": ["duplicate_global_source_row_id"]})
                continue
            record, failures = stage11945.admit_row(row, source_path, old_roots, seen_row_ids)
            if not record:
                rejected.append(
                    {
                        "source_path": source_path,
                        "row_id": rid,
                        "root_id": stage11945.root_id(row),
                        "language_family": stage11945.language(row),
                        "task_type": stage11945.task_type(row),
                        "failures": failures,
                    }
                )
                seen_source_rows.add(rid)
                continue
            lang = str(record["task_intent"]["language_family"])
            root = str(record["task_intent"]["root_id"])
            task = str(record["task_intent"]["task_family"])
            status = candidate_status(record)
            if lang_counts[lang] >= per_language_caps.get(lang, 0):
                rejected.append({"source_path": source_path, "row_id": rid, "root_id": root, "language_family": lang, "task_type": task, "failures": ["language_cap_reached"]})
                seen_source_rows.add(rid)
                continue
            if root_row_counts[root] >= per_root_cap:
                rejected.append({"source_path": source_path, "row_id": rid, "root_id": root, "language_family": lang, "task_type": task, "failures": ["root_cap_reached"]})
                seen_source_rows.add(rid)
                continue
            if root_task_counts[(root, task)] >= per_root_task_cap:
                rejected.append({"source_path": source_path, "row_id": rid, "root_id": root, "language_family": lang, "task_type": task, "failures": ["root_task_cap_reached"]})
                seen_source_rows.add(rid)
                continue
            split = "train" if root in old_roots else root_split_map.setdefault(root, root_split(root))
            record = normalize_record(record, source_path, root in old_roots)
            record["split"] = split
            record["provenance"]["split_rule"] = "old_transition_overlap->train else sha256(root_id)%100 train<74 validation<87 strict_else"
            record["provenance"]["transition_5k_gap_priority"] = gap_language_task.get((lang, f"transition_{task}"), 0)
            admitted_records.append(record)
            seen_source_rows.add(rid)
            lang_counts[lang] += 1
            source_counts[source_path] += 1
            root_row_counts[root] += 1
            root_task_counts[(root, task)] += 1
            status_counts[status] += 1

    projected_rows: list[dict[str, Any]] = []
    projection_failures: list[dict[str, Any]] = []
    for rec in admitted_records:
        rows, failures = projection.project_record(rec)
        if failures:
            projection_failures.append({"record_id": rec.get("record_id"), "failures": failures})
        for row in rows:
            split = rec["split"]
            row["split"] = split
            row["package_split"] = split
            row["train_support_only"] = split == "train"
            row["strict_eval_eligible"] = split == "strict_eval"
            row["source_heldout_admissible"] = split in {"validation", "strict_eval"} and not rec["provenance"].get("old_transition_root_overlap")
            row["old_transition_root_overlap"] = bool(rec["provenance"].get("old_transition_root_overlap"))
            row["stage11955_transition_5k_v1"] = True
            row["row_id"] = row["row_id"].replace("stage11897::", "stage11955::", 1)
            projected_rows.append(row)

    duplicate_row_ids = [rid for rid, count in Counter(row_id(row) for row in projected_rows).items() if count > 1]
    root_splits: dict[str, set[str]] = defaultdict(set)
    for row in projected_rows:
        root_splits[str(row.get("root_id"))].add(str(row.get("split")))
    split_violations = {root: sorted(splits) for root, splits in root_splits.items() if len(splits) > 1}

    pre_option_leaks: list[str] = []
    for row in projected_rows:
        gold = str((row.get("standalone_projection_source") or {}).get("gold_value") or "")
        if gold and len(gold) > 2 and gold not in {"CONTINUE", "ABSTAIN"}:
            before = str(row.get("prompt_text") or "").split("\nCANDIDATES\n", 1)[0]
            if gold in before:
                pre_option_leaks.append(row_id(row))

    write_jsonl(RECORDS, admitted_records)
    write_jsonl(ROWS, projected_rows)
    write_jsonl(
        ADMITTED_ROWS,
        [
            {
                "record_id": record["record_id"],
                "source_row_id": record["provenance"]["source_row_id"],
                "source_artifact": record["provenance"]["source_artifact"],
                "split": record["split"],
                "root_id": record["task_intent"]["root_id"],
                "language_family": record["task_intent"]["language_family"],
                "task_family": record["task_intent"]["task_family"],
                "verifier_status": candidate_status(record),
                "old_transition_root_overlap": bool(record["provenance"].get("old_transition_root_overlap")),
            }
            for record in admitted_records
        ],
    )
    write_jsonl(REJECTED_ROWS, rejected)

    record_split_counts = Counter(record["split"] for record in admitted_records)
    row_split_counts = Counter(row["split"] for row in projected_rows)
    counts = {
        "source_files_considered": len(inventory),
        "admitted_records": len(admitted_records),
        "projected_rows": len(projected_rows),
        "expected_projected_rows": len(admitted_records) * 4,
        "unique_roots": len(root_row_counts),
        "record_split_counts": dict(record_split_counts),
        "row_split_counts": dict(row_split_counts),
        "language_record_counts": dict(Counter(record["task_intent"]["language_family"] for record in admitted_records)),
        "language_row_counts": dict(Counter(row["language_family"] for row in projected_rows)),
        "task_record_counts": dict(Counter(record["task_intent"]["task_family"] for record in admitted_records)),
        "transition_task_row_counts": dict(Counter(row["task_type"] for row in projected_rows)),
        "verifier_status_counts": dict(status_counts),
        "source_file_record_counts_top20": dict(source_counts.most_common(20)),
        "old_transition_overlap_records": sum(1 for record in admitted_records if record["provenance"].get("old_transition_root_overlap")),
        "rejected_rows": len(rejected),
    }
    rejection_reason_counts = Counter(reason for item in rejected for reason in item.get("failures", []))

    min_language_records = min((counts["language_record_counts"].get(lang, 0) for lang in ("c_cpp", "python", "rust", "web_js_ts_html")), default=0)
    status_floor = {
        "PASS_CURRENT_BUILD": counts["verifier_status_counts"].get("PASS_CURRENT_BUILD", 0),
        "PASS_CURRENT_BUILD_AND_RUN": counts["verifier_status_counts"].get("PASS_CURRENT_BUILD_AND_RUN", 0),
        "PASS_CURRENT_STATE": counts["verifier_status_counts"].get("PASS_CURRENT_STATE", 0),
        "PASS_TO_PASS": counts["verifier_status_counts"].get("PASS_TO_PASS", 0),
        "VERIFIER_REMOVED": counts["verifier_status_counts"].get("VERIFIER_REMOVED", 0),
    }
    passed = (
        5000 <= len(projected_rows) <= 7000
        and len(admitted_records) >= 1250
        and len(root_row_counts) >= 250
        and min_language_records >= 250
        and record_split_counts.get("train", 0) > 0
        and record_split_counts.get("validation", 0) > 0
        and record_split_counts.get("strict_eval", 0) > 0
        and not projection_failures
        and not duplicate_row_ids
        and not split_violations
        and not pre_option_leaks
    )
    weak_balance = {
        "min_language_records": min_language_records,
        "status_floor": status_floor,
        "status_targets_met_500_each": all(value >= 500 for value in status_floor.values()),
    }
    artifact = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now(),
        "passed": passed,
        "decision": "transition_5k_v1_package_ready_for_probe_request" if passed else "transition_5k_v1_package_needs_more_source_supply_or_balance",
        "counts": counts,
        "balance_audit": weak_balance,
        "audits": {
            "projection_failures": projection_failures[:20],
            "projection_failure_count": len(projection_failures),
            "duplicate_row_ids": duplicate_row_ids[:20],
            "duplicate_row_id_count": len(duplicate_row_ids),
            "root_split_violations": dict(list(split_violations.items())[:20]),
            "root_split_violation_count": len(split_violations),
            "pre_options_target_value_leaks": pre_option_leaks[:20],
            "pre_options_target_value_leak_count": len(pre_option_leaks),
            "rejection_reason_counts": dict(rejection_reason_counts),
        },
        "source_artifacts": {
            "inventory": rel(INVENTORY),
            "old_transition_rows": rel(OLD_TRANSITION_ROWS),
            "gemma_gap_rows": rel(GEMMA_GAP_ROWS),
        },
        "outputs": {
            "summary": rel(SUMMARY),
            "records": rel(RECORDS),
            "rows": rel(ROWS),
            "admitted_rows": rel(ADMITTED_ROWS),
            "rejected_rows": rel(REJECTED_ROWS),
        },
        "claim_boundary": [
            "This is a package/admission artifact only; it is not a model improvement.",
            "Old transition-overlap roots are train-only support and are not source-heldout evidence.",
            "If balance targets fail, the next step is source acquisition/materialization, not training on the package as-is.",
        ],
    }
    write_json(SUMMARY, artifact)
    SUMMARIES.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(SUMMARY, SUMMARIES / f"{NAME}.json")
    print(
        json.dumps(
            {
                "decision": artifact["decision"],
                "passed": passed,
                "counts": counts,
                "balance_audit": weak_balance,
                "audit_summary": {
                    key: value
                    for key, value in artifact["audits"].items()
                    if key.endswith("_count") or key == "rejection_reason_counts"
                },
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
