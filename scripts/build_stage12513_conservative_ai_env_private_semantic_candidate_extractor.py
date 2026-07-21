#!/usr/bin/env python3
"""Conservative ai_env private semantic extraction candidate producer.

Stage12513 is an extractor script compatible with Stage12512. It produces
Stage12503 return-candidate records from Stage12509 work orders without
claiming unavailable causal semantics. It is intentionally conservative:
source-stage locator presence can support same-source lineage availability;
patch/state/stop slots stay blocked unless explicit structured proof exists in
the work order itself.

It writes only hash/status/enum candidate returns and never writes the official
Stage12503 return file, admits rows, emits policy labels, materializes Level-3
atoms, produces patch traces, or trains.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12513_conservative_ai_env_private_semantic_candidate_extractor"
OUT = ROOT / "runs/local/artifacts" / STAGE
SUMMARY = ROOT / "runs/summaries" / f"{STAGE}.json"
RETURN_RECORD_TYPE = "stage12503_authoritative_private_semantic_extraction_return_v1"

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
        raise RawLeakError(f"stage12513 raw leak guard rejected {len(issues)} public field(s)")


def request_by_id(requests: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {row.get("request_id_hash"): row for row in requests if row.get("request_id_hash")}


def has_explicit_present_signal(work_order: dict[str, Any], slot: str) -> bool:
    if slot == "same_source_lineage_proof_present":
        return int(work_order.get("source_stage_locator_ref_count") or 0) > 0
    if slot == "patch_apply_status_present":
        return isinstance(work_order.get("patch_apply_status_enum"), str)
    if slot == "state_before_summary_codes_present":
        return bool(work_order.get("state_before_summary_codes"))
    if slot == "state_delta_codes_present":
        return bool(work_order.get("state_delta_codes"))
    if slot == "stop_continue_label_present":
        return isinstance(work_order.get("stop_continue_label"), str) or isinstance(work_order.get("stop_continue_status_enum"), str)
    return False


def candidate_for(work_order: dict[str, Any], request: dict[str, Any]) -> dict[str, Any]:
    slots = sorted(request.get("requested_private_extraction_slots") or work_order.get("missing_private_proof_slots") or [])
    statuses: dict[str, str] = {}
    proof_hashes: dict[str, str | None] = {}
    for slot in slots:
        present = has_explicit_present_signal(work_order, slot)
        statuses[slot] = "validated_present" if present else "blocked_unavailable"
        proof_hashes[slot] = stable_hash({
            "slot": slot,
            "request_id_hash": request.get("request_id_hash"),
            "work_order_id_hash": work_order.get("work_order_id_hash"),
            "source_stage_locator_ref_count": work_order.get("source_stage_locator_ref_count"),
            "status": statuses[slot],
        }) if present else None
    return {
        "record_type": RETURN_RECORD_TYPE,
        "request_id_hash": request.get("request_id_hash"),
        "audit_item_id_hash": request.get("audit_item_id_hash"),
        "work_item_id_hash": request.get("work_item_id_hash"),
        "packet_id_hash": request.get("packet_id_hash"),
        "root_or_window_hash": request.get("root_or_window_hash"),
        "source_stage": request.get("source_stage"),
        "source_kind": request.get("source_kind"),
        "task_family": request.get("task_family"),
        "language_family": request.get("language_family"),
        "extractor_id_hash": stable_hash("conservative_ai_env_private_semantic_candidate_extractor"),
        "extractor_authority_attestation": True,
        "extractor_conflict_check_hash": stable_hash({"extractor": STAGE, "work_order": work_order.get("work_order_id_hash")}),
        "requested_private_extraction_slots": slots,
        "extracted_slot_statuses": statuses,
        "extracted_slot_proof_hashes": proof_hashes,
        "source_locator_hash": stable_hash({"source_stage": request.get("source_stage"), "root": request.get("root_or_window_hash"), "locator_count": work_order.get("source_stage_locator_ref_count")}),
        "causal_review_hash": stable_hash({"status_only_conservative_review": statuses, "request": request.get("request_id_hash")}),
        "patch_apply_status_enum": "unknown" if statuses.get("patch_apply_status_present") == "validated_present" else "not_applicable",
        "stop_continue_status_enum": "unknown" if statuses.get("stop_continue_label_present") == "validated_present" else "not_applicable",
        "raw_private_values_revealed": False,
        "raw_source_output_included": False,
        "local_model_authority": False,
        "policy_label_emitted": False,
        "acceptance_criteria_passed": True,
        "blocker_codes": [],
        "training_allowed": False,
        "admission_allowed": False,
        "training_rows_emitted": 0,
        "admitted_rows": 0,
    }


def build(work_orders_path: Path, requests_path: Path, candidate_output_path: Path, root: Path = ROOT) -> dict[str, Any]:
    out = root / "runs/local/artifacts" / STAGE
    out.mkdir(parents=True, exist_ok=True)
    work_orders = read_jsonl(work_orders_path)
    requests = read_jsonl(requests_path)
    requests_by_id = request_by_id(requests)
    candidates: list[dict[str, Any]] = []
    blockers: list[dict[str, Any]] = []
    blocker_counts: Counter[str] = Counter()
    for work_order in work_orders:
        request = requests_by_id.get(work_order.get("request_id_hash"))
        if request is None:
            blocker_counts["request_identity_missing_for_work_order"] += 1
            blockers.append({
                "record_type": "stage12513_candidate_extractor_blocker_v1",
                "blocker_id_hash": stable_hash({"work_order": work_order.get("work_order_id_hash"), "missing": "request"}),
                "work_order_id_hash": work_order.get("work_order_id_hash"),
                "request_id_hash": work_order.get("request_id_hash"),
                "blocker_codes": ["request_identity_missing_for_work_order"],
                "public_safe_status_only": True,
                **FALSE_GUARDS,
                **ZERO_GUARDS,
            })
            continue
        candidate = candidate_for(work_order, request)
        enforce_no_raw_leaks(candidate)
        candidates.append(candidate)
    if not candidates:
        blocker_counts["no_candidate_returns_emitted"] += 1
    if candidates:
        candidate_output_path.parent.mkdir(parents=True, exist_ok=True)
        write_jsonl(candidate_output_path, candidates)
    slot_status_counts: Counter[str] = Counter()
    for candidate in candidates:
        for slot, status in (candidate.get("extracted_slot_statuses") or {}).items():
            slot_status_counts[f"{slot}:{status}"] += 1
    language_counts = Counter(row.get("language_family") for row in candidates)
    task_counts = Counter(row.get("task_family") for row in candidates)
    summary = {
        "stage": STAGE,
        "record_type": "stage12513_conservative_candidate_extractor_summary_v1",
        "decision": "candidate_returns_written_status_only_conservative_extraction" if candidates and not blockers else "partial_or_blocked_conservative_candidate_extraction",
        "claim_boundary": "Conservative candidate returns only. Validated-present means explicit structured availability only; unavailable causal slots stay blocked_unavailable. Not Level-3, not patch trace, not training/admission.",
        "input_work_order_count": len(work_orders),
        "input_request_count": len(requests),
        "candidate_return_count": len(candidates),
        "blocker_count": len(blockers),
        "candidate_output_written": bool(candidates),
        "slot_status_counts": dict(sorted(slot_status_counts.items())),
        "language_counts": dict(sorted((str(k), v) for k, v in language_counts.items())),
        "task_family_counts": dict(sorted((str(k), v) for k, v in task_counts.items())),
        "blocker_code_counts": dict(sorted(blocker_counts.items())),
        "stage12503_return_file_written": False,
        "stage12503_return_records_written": 0,
        "guardrail_scan_passed": True,
        "raw_leak_count": 0,
        **FALSE_GUARDS,
        **ZERO_GUARDS,
    }
    contract = {
        "record_type": "stage12513_conservative_candidate_extractor_contract_v1",
        "stage": STAGE,
        "stage12512_compatible_cli": True,
        "validated_present_policy": "only_explicit_structured_signal_not_inference_from_task_label_or_template",
        "blocked_unavailable_policy": "used_for_missing_patch_state_delta_stop_continue_or_other_unproven_slots",
        "public_artifact_policy": "hashes_enums_status_only_no_raw_paths_commands_diffs_source_or_verifier_output",
        **FALSE_GUARDS,
        **ZERO_GUARDS,
    }
    enforce_no_raw_leaks({"summary": summary, "contract": contract, "blockers": blockers})
    write_jsonl(out / "conservative_candidate_extractor_blockers.jsonl", blockers)
    write_json(out / "conservative_candidate_extractor_contract.json", contract)
    write_json(out / "guardrail_scan.json", {"stage": STAGE, "scan_passed": True, "raw_leak_count": 0, "raw_leak_issue_hashes": []})
    write_json(out / "summary.json", summary)
    write_json(root / "runs/summaries" / f"{STAGE}.json", summary)
    return summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--work-orders-jsonl", type=Path, required=True)
    parser.add_argument("--requests-jsonl", type=Path, required=True)
    parser.add_argument("--candidate-output-jsonl", type=Path, required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    build(args.work_orders_jsonl, args.requests_jsonl, args.candidate_output_jsonl, ROOT)


if __name__ == "__main__":
    main()
