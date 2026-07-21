#!/usr/bin/env python3
"""Revalidate causal proof slots after conservative private extraction.

Stage12514 corrects the weak Stage12513/Stage12504 lineage update. A locator
count can prove a source-stage reference exists, but it is not causal lineage
proof. This stage therefore demotes locator-only same-source updates and emits a
corrected causal-proof blocker ledger for the remaining acquisition work.

No training, admission, Level-3 atom, patch trace, policy label, or official
Stage12503 return is emitted here.
"""
from __future__ import annotations

import hashlib
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12514_causal_proof_revalidation_gate"
OUT = ROOT / "runs/local/artifacts" / STAGE
SUMMARY = ROOT / "runs/summaries" / f"{STAGE}.json"

STAGE12504 = "stage12504_closed_loop_slot_update_from_validated_private_extraction_status"
LEDGER = ROOT / "runs/local/artifacts" / STAGE12504 / "closed_loop_proof_slot_update_ledger.jsonl"

CRITICAL_SLOT_BLOCKERS = {
    "same_source_causal_lineage": "same_source_lineage_locator_only_not_causal",
    "authoritative_state_before": "state_before_summary_codes_present_unproven",
    "state_delta_or_state_after": "state_delta_codes_present_unproven",
    "patch_apply_status": "patch_apply_status_present_unproven",
    "stop_continue": "stop_continue_label_present_unproven",
    "external_patch_effect_proof": "external_patch_effect_proof_missing",
    "independent_policy_label": "independent_policy_label_missing",
}

RAW_LEAK_RE = re.compile(
    r"https?://|www\.|diff --git|@@ |^\+\+\+ |^--- |<<<<<<<|>>>>>>>|"
    r"(?<![A-Za-z0-9_])/(?:[A-Za-z0-9._-]+/){2,}[A-Za-z0-9._-]+|"
    r"\b(?:git clone|git apply|pytest\s|python -c|bash -|sh -|curl\s|"
    r"stdout|stderr|traceback|terminal output|command output|commit:)\b|"
    r"\b[0-9a-f]{40}\b",
    re.IGNORECASE | re.MULTILINE,
)
FALSE_GUARDS = {
    "training_allowed": False,
    "admission_allowed": False,
    "packaging_allowed": False,
    "execution_performed_by_stage": False,
    "hydration_performed_by_stage": False,
    "replay_performed_by_stage": False,
    "network_performed_by_stage": False,
    "policy_label_materialized": False,
    "level3_atom_materialized": False,
    "patch_trace_materialized": False,
    "stage12503_return_file_written": False,
    "candidate_return_file_written": False,
    "raw_source_output_included": False,
    "raw_private_values_revealed": False,
}
ZERO_GUARDS = {
    "training_rows_emitted": 0,
    "admitted_rows": 0,
    "level3_admitted": 0,
    "level3_atom_count": 0,
    "patch_trace_admitted": 0,
    "patch_trace_rows": 0,
    "policy_labels_emitted": 0,
    "proof_rows_emitted": 0,
    "proof_grade_repair_rows": 0,
    "external_repair_credit_count": 0,
    "sealed_eval_rows": 0,
    "stage12503_return_records_written": 0,
    "candidate_return_records_written": 0,
}


class RawLeakError(ValueError):
    pass


def stable_hash(value: Any, n: int = 24) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(f"{STAGE}:{payload}".encode("utf-8")).hexdigest()[:n]


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                value = json.loads(line)
                if isinstance(value, dict):
                    rows.append(value)
    return rows


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")


def scan_raw_leaks(value: Any) -> list[str]:
    issues: list[str] = []
    if isinstance(value, str):
        if RAW_LEAK_RE.search(value):
            issues.append(stable_hash(value))
    elif isinstance(value, dict):
        for child in value.values():
            issues.extend(scan_raw_leaks(child))
    elif isinstance(value, list):
        for child in value:
            issues.extend(scan_raw_leaks(child))
    return issues


def enforce_no_raw_leaks(value: Any) -> None:
    issues = scan_raw_leaks(value)
    if issues:
        raise RawLeakError(f"stage12514 raw leak guard rejected {len(issues)} public field(s)")


def validated_slots(row: dict[str, Any]) -> set[str]:
    updates = row.get("proof_slot_updates") or {}
    return {
        slot
        for slot, status in updates.items()
        if isinstance(status, dict) and status.get("validated_present") is True
    }


def revalidate_row(row: dict[str, Any]) -> dict[str, Any]:
    seen = validated_slots(row)
    demoted: list[str] = []
    blockers: list[str] = []
    if "same_source_causal_lineage" in seen:
        # Stage12513 generated this from source_stage_locator_ref_count only.
        demoted.append("same_source_causal_lineage")
        blockers.append("same_source_lineage_locator_only_not_causal")
    else:
        blockers.append("same_source_lineage_causal_proof_missing")
    blockers.extend([
        "external_patch_effect_proof_missing",
        "independent_policy_label_missing",
        "patch_apply_status_present_unproven",
        "state_before_summary_codes_present_unproven",
        "state_delta_codes_present_unproven",
        "state_delta_codes_required",
        "structured_state_before_codes_required",
    ])
    if "stop_continue" not in seen:
        blockers.append("stop_continue_label_present_unproven")
    out = {
        "record_type": "stage12514_causal_proof_revalidation_record_v1",
        "revalidation_id_hash": stable_hash({"slot_update": row.get("slot_update_id_hash"), "blockers": blockers}),
        "source_stage": row.get("source_stage"),
        "source_kind": row.get("source_kind"),
        "task_family": row.get("task_family"),
        "language_family": row.get("language_family"),
        "request_id_hash": row.get("request_id_hash"),
        "work_item_id_hash": row.get("work_item_id_hash"),
        "packet_id_hash": row.get("packet_id_hash"),
        "root_or_window_hash": row.get("root_or_window_hash"),
        "slot_update_id_hash": row.get("slot_update_id_hash"),
        "validated_extraction_id_hash": row.get("validated_extraction_id_hash"),
        "stage12504_validated_slots_seen": sorted(seen),
        "demoted_slots": sorted(demoted),
        "demotion_reason_codes": ["locator_or_metadata_hash_not_causal_proof"] if demoted else [],
        "corrected_causal_slot_validated_count": 0,
        "corrected_causal_slots_validated": [],
        "corrected_residual_blocker_codes": sorted(set(blockers)),
        "required_next_private_evidence_slots": [
            "same_source_causal_lineage_with_independent_evidence_digest",
            "structured_state_before_codes",
            "state_delta_or_state_after_codes",
            "patch_apply_or_no_patch_status",
            "stop_continue_policy_label",
            "independent_policy_label_and_candidate_action_set",
            "external_patch_effect_or_no_patch_reason",
        ],
        "public_safe_status_only": True,
        **FALSE_GUARDS,
        **ZERO_GUARDS,
    }
    enforce_no_raw_leaks(out)
    return out


def rollups(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        grouped[(str(record.get("source_stage")), str(record.get("language_family")), str(record.get("task_family")))].append(record)
    out: list[dict[str, Any]] = []
    for (source_stage, language_family, task_family), rows in sorted(grouped.items()):
        c: Counter[str] = Counter()
        for row in rows:
            c.update(row.get("corrected_residual_blocker_codes") or [])
        item = {
            "record_type": "stage12514_causal_proof_revalidation_rollup_v1",
            "rollup_id_hash": stable_hash({"source": source_stage, "language": language_family, "task": task_family}),
            "source_stage": source_stage,
            "language_family": language_family,
            "task_family": task_family,
            "record_count": len(rows),
            "corrected_blocker_code_counts": dict(sorted(c.items())),
            "recommended_next_action": "reopen_private_source_for_independent_causal_evidence_not_locator_metadata",
            "public_safe_status_only": True,
            **FALSE_GUARDS,
            **ZERO_GUARDS,
        }
        enforce_no_raw_leaks(item)
        out.append(item)
    return out


def build(root: Path = ROOT) -> dict[str, Any]:
    out = root / "runs/local/artifacts" / STAGE
    out.mkdir(parents=True, exist_ok=True)
    ledger = read_jsonl(root / "runs/local/artifacts" / STAGE12504 / "closed_loop_proof_slot_update_ledger.jsonl")
    records = [revalidate_row(row) for row in ledger]
    source_rollups = rollups(records)
    blockers: Counter[str] = Counter()
    demoted: Counter[str] = Counter()
    langs: Counter[str] = Counter()
    tasks: Counter[str] = Counter()
    sources: Counter[str] = Counter()
    for row in records:
        blockers.update(row.get("corrected_residual_blocker_codes") or [])
        demoted.update(row.get("demoted_slots") or [])
        langs[str(row.get("language_family"))] += 1
        tasks[str(row.get("task_family"))] += 1
        sources[str(row.get("source_stage"))] += 1
    summary = {
        "stage": STAGE,
        "record_type": "stage12514_causal_proof_revalidation_summary_v1",
        "decision": "causal_proof_revalidation_demoted_locator_only_lineage_training_and_admission_blocked",
        "claim_boundary": "Revalidation blocker ledger only. Locator-derived Stage12504 same-source updates are demoted from causal proof. No candidate returns, policy labels, Level-3 atoms, patch traces, training rows, or admissions emitted.",
        "input_slot_update_count": len(ledger),
        "revalidation_record_count": len(records),
        "source_stage_rollup_count": len(source_rollups),
        "demoted_slot_counts": dict(sorted(demoted.items())),
        "corrected_causal_slot_validated_count": 0,
        "corrected_blocker_code_counts": dict(sorted(blockers.items())),
        "language_counts": dict(sorted(langs.items())),
        "task_family_counts": dict(sorted(tasks.items())),
        "source_stage_counts": dict(sorted(sources.items())),
        "next_stage": "private_source_reopen_for_independent_causal_evidence_not_locator_metadata",
        "guardrail_scan_passed": True,
        "raw_leak_count": 0,
        **FALSE_GUARDS,
        **ZERO_GUARDS,
    }
    contract = {
        "record_type": "stage12514_causal_proof_revalidation_contract_v1",
        "stage": STAGE,
        "input_stage": STAGE12504,
        "hard_rule": "locator_counts_hashes_templates_and_status_hashes_are_not_causal_proof",
        "demote_locator_only_lineage": True,
        "causal_slots_required_before_training": list(CRITICAL_SLOT_BLOCKERS),
        "public_artifact_policy": "hashes_enums_status_only_no_raw_paths_commands_diffs_source_or_verifier_output",
        **FALSE_GUARDS,
        **ZERO_GUARDS,
    }
    enforce_no_raw_leaks({"summary": summary, "contract": contract, "records": records, "rollups": source_rollups})
    write_jsonl(out / "causal_proof_revalidation_records.jsonl", records)
    write_jsonl(out / "causal_proof_revalidation_source_rollups.jsonl", source_rollups)
    write_json(out / "causal_proof_revalidation_contract.json", contract)
    write_json(out / "guardrail_scan.json", {"stage": STAGE, "scan_passed": True, "raw_leak_count": 0, "raw_leak_issue_hashes": []})
    write_json(out / "summary.json", summary)
    write_json(root / "runs/summaries" / f"{STAGE}.json", summary)
    return summary


def main() -> None:
    build(ROOT)


if __name__ == "__main__":
    main()
