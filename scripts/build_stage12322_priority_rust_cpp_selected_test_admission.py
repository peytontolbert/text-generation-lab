#!/usr/bin/env python3
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12322_priority_rust_cpp_selected_test_admission"
OUT = ROOT / "runs/local/artifacts" / STAGE
SUMMARY = ROOT / "runs/summaries" / f"{STAGE}.json"

STAGE12130 = ROOT / "runs/local/artifacts/stage12130_selected_test_train_support_package/train_support_rows.jsonl"
STAGE12149 = ROOT / "runs/local/artifacts/stage12149_corrected_selected_test_row_materialization_package/corrected_selected_test_rows.jsonl"
STAGE12150 = ROOT / "runs/local/artifacts/stage12150_corrected_selected_test_materialization_audit/row_materialization_blocker_audit.json"

CPP_PRIORITY = {"Neargye/magic_enum", "fastfloat/fast_float"}
RUST_PRIORITY_ROOTS = {
    "stage12118::rust::010::assert_rs_predicates_rs",
    "stage12118::rust::017::dtolnay_anyhow",
    "stage12118::rust::044::toml_rs_toml",
}
REQUIRED_ANTI_CHEAT = {
    "deterministic_option_shuffle": True,
    "target_label_not_visible_before_options": True,
    "target_value_not_visible_before_options": True,
}


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")


def anti_cheat_pass(row: dict[str, Any]) -> tuple[bool, list[str]]:
    anti = row.get("anti_cheat") or {}
    blockers = []
    for key, expected in REQUIRED_ANTI_CHEAT.items():
        if anti.get(key) is not expected:
            blockers.append(f"anti_cheat_{key}_not_{expected}")
    return not blockers, blockers


def source_hash_ok(row: dict[str, Any]) -> bool:
    text = json.dumps(row, sort_keys=True)
    return "source_hash" in text and "test_hash" in text


def verifier_ref_ok(row: dict[str, Any]) -> bool:
    text = json.dumps(row, sort_keys=True)
    return "command_logs" in text or "selected_test_success" in text or "verifier" in text


def normalize_row(row: dict[str, Any], source_stage: str, root_id: str, repo_family: str) -> tuple[dict[str, Any], list[str]]:
    blockers = []
    ok, anti_blockers = anti_cheat_pass(row)
    blockers.extend(anti_blockers)
    if not row.get("commit_sha") and "Commit:" not in (row.get("input_text") or ""):
        blockers.append("commit_sha_missing")
    if not source_hash_ok(row):
        blockers.append("source_or_test_hash_ref_missing")
    if not verifier_ref_ok(row):
        blockers.append("selected_verifier_log_or_ref_missing")
    if row.get("strict_eval_eligible") is True or row.get("source_heldout_admissible") is True:
        blockers.append("unexpected_eval_or_source_heldout_claim")
    options = row.get("opaque_options") or []
    if len(options) < 2:
        blockers.append("singleton_or_missing_options")
    if (row.get("anti_cheat") or {}).get("singleton_options") is True:
        blockers.append("anti_cheat_singleton_options_true")
    normalized = {
        "stage": STAGE,
        "record_type": "priority_selected_test_train_support_row",
        "row_id": f"stage12322::{source_stage}::{row.get('row_id') or row.get('source_row_id') or len(json.dumps(row))}",
        "source_stage": source_stage,
        "source_row_id": row.get("row_id"),
        "root_id": root_id,
        "repo_family": repo_family,
        "language_family": row.get("language_family"),
        "task_family": row.get("task_family") or row.get("task_type"),
        "input_text": row.get("input_text") or row.get("prompt_text"),
        "opaque_options": options,
        "bounded_choice_target_label": row.get("bounded_choice_target_label"),
        "decoder_text": row.get("decoder_text"),
        "loss_mask": row.get("loss_mask") or {},
        "source_refs": {
            "commit_sha": row.get("commit_sha"),
            "root_lineage_key": row.get("root_lineage_key"),
            "source_root_id": row.get("source_root_id"),
            "source_bundle_id": row.get("source_bundle_id"),
            "raw_source_emitted": False,
            "raw_verifier_log_emitted": False,
        },
        "admission": {
            "training_allowed": not blockers,
            "train_support_allowed": not blockers,
            "strict_eval_eligible": False,
            "source_heldout_admissible": False,
            "level3_admitted": False,
            "patch_trace_admitted": False,
            "repair_claim_admitted": False,
            "reason": "selected-test train-support only; no strict/source-heldout/repair claim",
        },
        "blocked_reasons": sorted(set(blockers)),
    }
    return normalized, blockers


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    rows = []
    blocked = []

    for row in read_jsonl(STAGE12130):
        repo = row.get("repo_family")
        if repo not in CPP_PRIORITY:
            continue
        normalized, blockers = normalize_row(row, "stage12130", row.get("root_id") or repo, repo)
        if blockers:
            blocked.append(normalized)
        else:
            rows.append(normalized)

    audit = json.loads(STAGE12150.read_text(encoding="utf-8")) if STAGE12150.exists() else {}
    audit_passed = bool(audit.get("passed") and audit.get("blocker_row_count") == 0)
    for row in read_jsonl(STAGE12149):
        root_id = row.get("root_id")
        if root_id not in RUST_PRIORITY_ROOTS:
            continue
        normalized, blockers = normalize_row(row, "stage12149", root_id, row.get("repo_family") or root_id)
        if not audit_passed:
            normalized["blocked_reasons"].append("stage12150_audit_not_passed")
        if normalized["blocked_reasons"]:
            normalized["admission"]["training_allowed"] = False
            normalized["admission"]["train_support_allowed"] = False
            blocked.append(normalized)
        else:
            rows.append(normalized)

    write_jsonl(OUT / "priority_rust_cpp_selected_test_train_support_rows.jsonl", rows)
    if blocked:
        write_jsonl(OUT / "priority_rust_cpp_selected_test_blocked_rows.jsonl", blocked)

    lang_counts = Counter(row.get("language_family") or "unknown" for row in rows)
    root_counts = Counter(row.get("root_id") or row.get("repo_family") for row in rows)
    task_counts = Counter(row.get("task_family") or "unknown" for row in rows)
    blocked_reasons = Counter()
    for row in blocked:
        blocked_reasons.update(row.get("blocked_reasons") or [])
    summary = {
        "stage": STAGE,
        "decision": "priority_rust_cpp_selected_test_train_support_admission_complete",
        "claim_boundary": "Train-support-only selected-test rows. No strict eval, source-heldout, Level-3, patch-trace, or repair claim.",
        "training_allowed": bool(rows),
        "admitted_train_support_rows": len(rows),
        "blocked_rows": len(blocked),
        "target_rows": 25,
        "language_counts": dict(lang_counts),
        "root_counts": dict(root_counts),
        "task_family_counts": dict(task_counts),
        "blocked_reason_counts": dict(blocked_reasons),
        "stage12150_audit_passed": audit_passed,
        "next_stage": {
            "stage": "stage12324_combined_train_support_ledger",
            "purpose": "Combine Stage12320 and Stage12322 admitted train-support counters and remaining gap to 500.",
            "training_allowed": False,
        },
    }
    (OUT / "priority_rust_cpp_selected_test_admission_summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (OUT / "PRIORITY_RUST_CPP_SELECTED_TEST_ADMISSION_STAGE12322.md").write_text(
        "# Stage12322 Priority Rust/C++ Selected-Test Admission\n\n"
        "This stage admits only train-support selected-test rows from priority Rust/C++ roots. It does not admit eval or repair rows.\n",
        encoding="utf-8",
    )
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
