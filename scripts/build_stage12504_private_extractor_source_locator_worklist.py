#!/usr/bin/env python3
"""Build hash-only source locator work for Stage12503 extraction returns.

Stage12504 does not create private semantic extraction returns. It inspects
repo-local artifact files for hash co-occurrence evidence that can guide a
trusted/private extractor to the relevant source records. Public outputs contain
only hashes, stage IDs, counters, and blocker/status enums.
"""
from __future__ import annotations

import hashlib
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12504_private_extractor_source_locator_worklist"
OUT = ROOT / "runs/local/artifacts" / STAGE
SUMMARY = ROOT / "runs/summaries" / f"{STAGE}.json"

STAGE12500 = "stage12500_closed_loop_candidate_packet_router"
STAGE12500_OUT = ROOT / "runs/local/artifacts" / STAGE12500
PACKETS = STAGE12500_OUT / "closed_loop_candidate_packets.jsonl"
WORKLIST = STAGE12500_OUT / "closed_loop_materialization_worklist.jsonl"

STAGE12502 = "stage12502_authoritative_private_semantic_extraction_request_preflight"
STAGE12502_OUT = ROOT / "runs/local/artifacts" / STAGE12502
STAGE12502_SUMMARY = ROOT / "runs/summaries" / f"{STAGE12502}.json"
REQUESTS = STAGE12502_OUT / "private_semantic_extraction_requests.jsonl"

STAGE12503 = "stage12503_private_semantic_extraction_return_validator"
STAGE12503_SUMMARY = ROOT / "runs/summaries" / f"{STAGE12503}.json"

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
    "stage12503_return_materialized": False,
}
ZERO_GUARDS = {
    "training_rows_emitted": 0,
    "admitted_rows": 0,
    "level3_admitted": 0,
    "level3_atom_count": 0,
    "patch_trace_admitted": 0,
    "patch_trace_rows": 0,
    "stage12496_return_records_written": 0,
    "stage12503_return_records_written": 0,
    "policy_labels_emitted": 0,
    "proof_rows_emitted": 0,
    "proof_grade_repair_rows": 0,
    "external_repair_credit_count": 0,
    "sealed_eval_rows": 0,
}

SOURCE_FILE_SUFFIXES = {".json", ".jsonl"}
CONTEXT_STAGES = {
    STAGE12500,
    STAGE12502,
    STAGE12503,
}


def stable_hash(value: Any, n: int = 24) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(f"{STAGE}:{payload}".encode("utf-8")).hexdigest()[:n]


def file_hash(path: Path, n: int = 24) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()[:n]


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    value = json.loads(path.read_text(encoding="utf-8"))
    return value if isinstance(value, dict) else {}


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


def source_files_for_stage(stage: str) -> list[Path]:
    stage_dir = ROOT / "runs/local/artifacts" / stage
    if not stage_dir.exists():
        return []
    return sorted(
        path
        for path in stage_dir.rglob("*")
        if path.is_file() and path.suffix in SOURCE_FILE_SUFFIXES
    )


def safe_lookup_hashes(request: dict[str, Any], packet: dict[str, Any] | None, work: dict[str, Any] | None) -> dict[str, str]:
    values = {
        "request_id_hash": request.get("request_id_hash"),
        "audit_item_id_hash": request.get("audit_item_id_hash"),
        "work_item_id_hash": request.get("work_item_id_hash"),
        "packet_id_hash": request.get("packet_id_hash"),
        "root_or_window_hash": request.get("root_or_window_hash"),
    }
    if packet:
        values.update(
            {
                "row_id_hash": packet.get("row_id_hash"),
                "source_ref_hash": packet.get("source_ref_hash"),
                "source_row_id_hash": packet.get("source_row_id_hash"),
            }
        )
    if work:
        values["work_root_or_window_hash"] = work.get("root_or_window_hash")
    return {
        key: value
        for key, value in values.items()
        if isinstance(value, str) and re.fullmatch(r"[0-9a-f]{12,64}", value)
    }


def locator_records_for_request(
    request: dict[str, Any],
    packet: dict[str, Any] | None,
    work: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    stages = sorted({request.get("source_stage"), *(CONTEXT_STAGES)})
    lookup_hashes = safe_lookup_hashes(request, packet, work)
    records: list[dict[str, Any]] = []
    for stage in stages:
        if not isinstance(stage, str) or not stage:
            continue
        for artifact in source_files_for_stage(stage):
            text = artifact.read_text(encoding="utf-8", errors="replace")
            matched_keys = sorted(key for key, value in lookup_hashes.items() if value in text)
            if not matched_keys:
                continue
            rel = artifact.relative_to(ROOT)
            records.append(
                {
                    "record_type": "stage12504_hash_only_artifact_locator_v1",
                    "locator_id_hash": stable_hash(
                        {
                            "request": request.get("request_id_hash"),
                            "stage": stage,
                            "artifact": str(rel),
                            "matches": matched_keys,
                        }
                    ),
                    "artifact_stage": stage,
                    "artifact_locator_hash": stable_hash({"artifact": str(rel), "content": file_hash(artifact)}),
                    "artifact_file_role_hash": stable_hash({"stage": stage, "role": artifact.name}),
                    "artifact_content_hash": file_hash(artifact),
                    "matched_lookup_key_names": matched_keys,
                    "matched_lookup_key_count": len(matched_keys),
                    "raw_locator_values_emitted": False,
                    "public_safe_hash_locator_only": True,
                }
            )
    # Deduplicate by locator hash while preserving deterministic order.
    deduped: dict[str, dict[str, Any]] = {}
    for record in records:
        deduped.setdefault(record["locator_id_hash"], record)
    return list(deduped.values())


def build_work_item(
    request: dict[str, Any],
    packet: dict[str, Any] | None,
    work: dict[str, Any] | None,
) -> dict[str, Any]:
    locators = locator_records_for_request(request, packet, work)
    lookup_hashes = safe_lookup_hashes(request, packet, work)
    blocker_codes: list[str] = []
    if packet is None:
        blocker_codes.append("stage12500_packet_context_missing")
    if work is None:
        blocker_codes.append("stage12500_work_item_context_missing")
    if not locators:
        blocker_codes.append("no_hash_overlap_locator_found_in_local_artifacts")
    if not lookup_hashes.get("source_ref_hash") or not lookup_hashes.get("source_row_id_hash"):
        blocker_codes.append("source_ref_or_source_row_hash_missing")

    ready = not blocker_codes
    locator_match_counter = Counter()
    for locator in locators:
        locator_match_counter.update(locator["matched_lookup_key_names"])

    return {
        "record_type": "stage12504_private_extractor_source_locator_work_item_v1",
        "locator_work_item_id_hash": stable_hash({"request": request.get("request_id_hash"), "kind": "locator_work"}),
        "request_id_hash": request.get("request_id_hash"),
        "audit_item_id_hash": request.get("audit_item_id_hash"),
        "work_item_id_hash": request.get("work_item_id_hash"),
        "packet_id_hash": request.get("packet_id_hash"),
        "root_or_window_hash": request.get("root_or_window_hash"),
        "source_stage": request.get("source_stage"),
        "source_kind": request.get("source_kind"),
        "task_family": request.get("task_family"),
        "language_family": request.get("language_family"),
        "stage12503_expected_return_record_type": "stage12503_authoritative_private_semantic_extraction_return_v1",
        "stage12503_return_file_role_hash": stable_hash(
            {
                "stage": STAGE12502,
                "role": "private_semantic_extraction_returns.jsonl",
            }
        ),
        "requested_private_extraction_slots": sorted(request.get("requested_private_extraction_slots") or []),
        "hash_lookup_keys": lookup_hashes,
        "hash_locator_records": locators,
        "hash_locator_count": len(locators),
        "locator_match_key_counts": dict(sorted(locator_match_counter.items())),
        "source_locator_worklist_ready": ready,
        "blocker_codes": sorted(set(blocker_codes)),
        "materialization_environment": "ai_env",
        "required_private_extractor_actions": [
            "execute_inside_ai_env_not_trellis",
            "resolve_hash_locators_inside_trusted_private_workspace",
            "inspect_raw_source_command_patch_verifier_material_privately",
            "emit_only_stage12503_authoritative_private_semantic_extraction_return_v1",
            "emit_hashes_enums_statuses_only",
            "do_not_emit_policy_labels_training_rows_level3_atoms_or_patch_traces",
        ],
        "required_stage12503_return_fields": [
            "source_locator_hash",
            "causal_review_hash",
            "extracted_slot_statuses",
            "extracted_slot_proof_hashes",
            "patch_apply_status_enum",
            "stop_continue_status_enum",
        ],
        "forbidden_public_outputs": [
            "raw_paths",
            "raw_commands",
            "raw_diffs",
            "raw_source_text",
            "raw_verifier_output",
            "private_values",
            "policy_labels",
            "training_rows",
            "level3_atoms",
            "patch_traces",
        ],
        "raw_private_values_revealed": False,
        "raw_locator_values_emitted": False,
        "public_safe_hash_locator_only": True,
        **FALSE_GUARDS,
        **ZERO_GUARDS,
    }


def blocker_record(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "record_type": "stage12504_source_locator_blocker_v1",
        "blocker_id_hash": stable_hash({"request": row.get("request_id_hash"), "blockers": row.get("blocker_codes")}),
        "request_id_hash": row.get("request_id_hash"),
        "audit_item_id_hash": row.get("audit_item_id_hash"),
        "work_item_id_hash": row.get("work_item_id_hash"),
        "packet_id_hash": row.get("packet_id_hash"),
        "root_or_window_hash": row.get("root_or_window_hash"),
        "source_stage": row.get("source_stage"),
        "source_kind": row.get("source_kind"),
        "task_family": row.get("task_family"),
        "language_family": row.get("language_family"),
        "blocker_codes": row.get("blocker_codes"),
        "public_safe_status_only": True,
        "raw_private_values_revealed": False,
        **FALSE_GUARDS,
        **ZERO_GUARDS,
    }


def grouped_locator_summary(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[(row["language_family"], row["task_family"])].append(row)
    records: list[dict[str, Any]] = []
    for (language, task), items in sorted(grouped.items()):
        locator_count = sum(item["hash_locator_count"] for item in items)
        ready_count = sum(1 for item in items if item["source_locator_worklist_ready"])
        blockers = Counter()
        for item in items:
            blockers.update(item["blocker_codes"])
        records.append(
            {
                "record_type": "stage12504_locator_group_summary_v1",
                "group_id_hash": stable_hash({"language": language, "task": task}),
                "language_family": language,
                "task_family": task,
                "request_count": len(items),
                "source_locator_ready_count": ready_count,
                "blocked_count": len(items) - ready_count,
                "hash_locator_count": locator_count,
                "blocker_code_counts": dict(sorted(blockers.items())),
                **FALSE_GUARDS,
                **ZERO_GUARDS,
            }
        )
    return records


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    stage12502_summary = read_json(STAGE12502_SUMMARY)
    stage12503_summary = read_json(STAGE12503_SUMMARY)
    requests = read_jsonl(REQUESTS)
    packets = {row.get("packet_id_hash"): row for row in read_jsonl(PACKETS)}
    work_items = {row.get("work_item_id_hash"): row for row in read_jsonl(WORKLIST)}

    worklist = [
        build_work_item(
            request,
            packets.get(request.get("packet_id_hash")),
            work_items.get(request.get("work_item_id_hash")),
        )
        for request in requests
    ]
    ready = [row for row in worklist if row["source_locator_worklist_ready"]]
    blockers = [blocker_record(row) for row in worklist if not row["source_locator_worklist_ready"]]
    groups = grouped_locator_summary(worklist)

    all_locators = [locator for row in worklist for locator in row["hash_locator_records"]]
    language_counts = Counter(row["language_family"] for row in worklist)
    task_counts = Counter(row["task_family"] for row in worklist)
    source_stage_counts = Counter(row["source_stage"] for row in worklist)
    blocker_counts = Counter()
    locator_stage_counts = Counter()
    for row in worklist:
        blocker_counts.update(row["blocker_codes"])
    for locator in all_locators:
        locator_stage_counts[locator["artifact_stage"]] += 1

    outputs = {
        "worklist": worklist,
        "ready": ready,
        "blockers": blockers,
        "groups": groups,
    }
    leak_issues = scan_raw_leaks(outputs)
    guardrail = {
        "stage": STAGE,
        "scan_passed": not leak_issues,
        "raw_leak_count": len(leak_issues),
        "raw_leak_issue_hashes": leak_issues[:40],
        "scanned_outputs": [
            "private_extractor_source_locator_worklist.jsonl",
            "private_extractor_source_locator_ready.jsonl",
            "private_extractor_source_locator_blockers.jsonl",
            "private_extractor_source_locator_groups.jsonl",
        ],
    }

    summary = {
        "stage": STAGE,
        "record_type": "stage12504_private_extractor_source_locator_worklist_summary_v1",
        "decision": (
            "trusted_private_extractor_hash_locator_worklist_ready_training_and_admission_blocked"
            if ready
            else "blocked_no_local_hash_locator_support_for_private_extractor"
        ),
        "claim_boundary": (
            "Stage12504 provides hash-only local artifact locator work items for a trusted/private "
            "extractor. It does not inspect or publish raw source values, does not produce Stage12503 "
            "returns, and does not admit Level-3 atoms, patch traces, policy labels, or training rows."
        ),
        "source_stage": STAGE12502,
        "stage12502_decision": stage12502_summary.get("decision"),
        "stage12503_decision": stage12503_summary.get("decision"),
        "input_request_count": len(requests),
        "locator_work_item_count": len(worklist),
        "source_locator_ready_count": len(ready),
        "source_locator_blocked_count": len(blockers),
        "hash_locator_record_count": len(all_locators),
        "max_hash_locators_per_request": max((row["hash_locator_count"] for row in worklist), default=0),
        "language_counts": dict(sorted(language_counts.items())),
        "task_family_counts": dict(sorted(task_counts.items())),
        "source_stage_counts": dict(sorted(source_stage_counts.items())),
        "locator_artifact_stage_counts": dict(sorted(locator_stage_counts.items())),
        "blocker_code_counts": dict(sorted(blocker_counts.items())),
        "group_count": len(groups),
        "public_artifact_policy": "hashes_stage_ids_enums_only_no_raw_paths_commands_diffs_source_or_verifier_output",
        "stage12503_return_record_type_required": "stage12503_authoritative_private_semantic_extraction_return_v1",
        "stage12503_return_file_role_hash": stable_hash(
            {
                "stage": STAGE12502,
                "role": "private_semantic_extraction_returns.jsonl",
            }
        ),
        "guardrail_scan_passed": guardrail["scan_passed"],
        "raw_leak_count": guardrail["raw_leak_count"],
        "event_local_promoted_count": 0,
        "materialization_environment": "ai_env",
        "forbidden_materialization_environments": ["trellis"],
        "next_stage": "trusted_private_extractor_execute_stage12504_locators_in_ai_env_then_rerun_stage12503",
        **FALSE_GUARDS,
        **ZERO_GUARDS,
    }

    write_jsonl(OUT / "private_extractor_source_locator_worklist.jsonl", worklist)
    write_jsonl(OUT / "private_extractor_source_locator_ready.jsonl", ready)
    write_jsonl(OUT / "private_extractor_source_locator_blockers.jsonl", blockers)
    write_jsonl(OUT / "private_extractor_source_locator_groups.jsonl", groups)
    write_json(OUT / "guardrail_scan.json", guardrail)
    write_json(OUT / "summary.json", summary)
    write_json(SUMMARY, summary)


if __name__ == "__main__":
    main()
