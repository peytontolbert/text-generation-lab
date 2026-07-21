#!/usr/bin/env python3
"""Build Stage12411 Open-SWE row-lineage-repaired replay requests.

This stage upgrades Open-SWE replay requests from Stage12408 artifact-level
hashes to Stage12404 row-level lineage joined to the private Stage12410 locator
index. It does not read raw parquet rows, execute replay, emit raw locator
values, or admit training/eval/Level-3 rows.
"""
from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12411_open_swe_row_lineage_repaired_replay_requests"
OUT = ROOT / "runs/local/artifacts" / STAGE
SUMMARY = ROOT / "runs/summaries" / f"{STAGE}.json"

STAGE12404_ROWS = ROOT / "runs/local/artifacts/stage12404_open_swe_replay_state_reconstruction_request/open_swe_replay_state_reconstruction_request_items.jsonl"
STAGE12410_PRIVATE = ROOT / "runs/local/private/stage12410_private_open_swe_locator_index_preflight_qc/open_swe_raw_locator_index.private.jsonl"
STAGE12410_SUMMARY = ROOT / "runs/summaries/stage12410_private_open_swe_locator_index_preflight_qc.json"

ROWS_NAME = "open_swe_row_lineage_repaired_replay_requests.jsonl"
MANIFEST_NAME = "open_swe_row_lineage_repaired_replay_request_manifest.json"
GUARDRAIL_NAME = "guardrail_scan.json"
SAFE_SCHEMA = "stage12411_row_lineage_repaired_replay_request_v1"

RAW_CONTENT_POLICY = {
    "raw_parquet_rows_read": False,
    "private_locator_values_emitted_publicly": False,
    "raw_trajectory_text_emitted": False,
    "raw_commands_emitted": False,
    "raw_outputs_emitted": False,
    "raw_patches_emitted": False,
    "source_text_emitted": False,
    "absolute_paths_emitted": False,
    "raw_dataset_paths_emitted": False,
    "urls_emitted": False,
    "issue_bodies_emitted": False,
    "line_contents_emitted": False,
    "patch_diffs_emitted": False,
}
CLAIM_BOUNDARY = {
    "boundary": "row_lineage_repaired_request_only",
    "raw_locator_emitted": False,
    "raw_row_content_read": False,
    "replay_executed": False,
    "training_claim": False,
    "admission_claim": False,
    "level3_claim": False,
    "repair_claim": False,
    "fail_to_pass_claim": False,
    "patch_trace_claim": False,
}
ZERO_ADMISSION_FLAGS = {
    "admission": False,
    "training_allowed": False,
    "training_row_count": 0,
    "eval_row_count": 0,
    "admitted_rows": 0,
    "replay_attempted_count": 0,
    "replay_succeeded_safe_status_count": 0,
    "level3_admitted": 0,
    "patch_trace_admitted": 0,
    "repair_claim_admitted": 0,
    "fail_to_pass_claim_admitted": 0,
    "strict_eval_eligible": 0,
    "source_heldout_admissible": 0,
}
PROOF_SLOTS = [
    "state_before",
    "action",
    "observation",
    "verifier_identity",
    "verifier_output_class",
    "patch_application",
    "causal_linkage",
    "state_after",
    "stop_continue",
    "correct_next_action_policy",
]
ABS_PATH_RE = re.compile(r"(?<![A-Za-z0-9_])/(?:[A-Za-z0-9._-]+/){2,}[A-Za-z0-9._-]+")
URL_RE = re.compile(r"https?://|www\.", re.IGNORECASE)
DIFF_RE = re.compile(r"diff --git|@@ |^\+\+\+ |^--- |<<<<<<<", re.MULTILINE)


def stable_hash(value: Any, n: int = 24) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(payload.encode()).hexdigest()[:n]


def file_hash(path: Path, n: int = 24) -> str | None:
    if not path.exists():
        return None
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()[:n]


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        value = json.loads(path.read_text())
    except Exception:
        return {}
    return value if isinstance(value, dict) else {}


def read_jsonl(path: Path) -> tuple[list[dict[str, Any]], list[str]]:
    rows: list[dict[str, Any]] = []
    issues: list[str] = []
    if not path.exists():
        return rows, [f"missing_{path.name}"]
    for i, line in enumerate(path.read_text().splitlines(), 1):
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            issues.append(f"{path.name}_line_{i}_invalid_json")
            continue
        if isinstance(value, dict):
            rows.append(value)
        else:
            issues.append(f"{path.name}_line_{i}_not_object")
    return rows, issues


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w") as f:
        for row in rows:
            f.write(json.dumps(row, sort_keys=True) + "\n")


def proof_slots() -> dict[str, dict[str, Any]]:
    return {
        slot: {
            "proof_status": "blocked",
            "proof_proven": False,
            "evidence_class": "row_locator_hash_lineage_not_semantic_replay_proof",
            "proof_ref_hash": "missing",
            "status_code": f"blocked_{slot}_requires_raw_private_semantic_reviewer",
        }
        for slot in PROOF_SLOTS
    }


def private_index_by_hash(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {str(row.get("source_record_ref_hash") or ""): row for row in rows if row.get("source_record_ref_hash")}


def build_row(row: dict[str, Any], private_by_hash: dict[str, dict[str, Any]], rank: int) -> dict[str, Any]:
    refs = row.get("source_digest_refs") if isinstance(row.get("source_digest_refs"), dict) else {}
    source_ref_hash = str(refs.get("source_record_ref_hash") or "missing")
    private = private_by_hash.get(source_ref_hash)
    private_match = private is not None
    basis = {"stage12404_request_id": row.get("request_id"), "source_record_ref_hash": source_ref_hash, "rank": rank}
    blockers = [
        "blocked_request_only_no_replay_executed",
        "blocked_raw_private_semantic_reviewer_required",
        "blocked_missing_authoritative_state_before",
        "blocked_missing_authoritative_state_after",
        "blocked_missing_patch_application_proof",
        "blocked_missing_verifier_relevance_proof",
        "blocked_missing_causal_verifier_linkage",
        "blocked_missing_stop_continue_proof",
        "co_presence_order_candidate_not_causality",
        "fail_closed_if_uncertain",
    ]
    if not private_match:
        blockers.append("blocked_private_locator_index_match_missing")
    return {
        "repair_request_id": f"{STAGE}::{stable_hash(basis, 20)}",
        "record_type": "open_swe_row_lineage_repaired_replay_request",
        "source_stage": "stage12404_open_swe_replay_state_reconstruction_request",
        "stage12404_request_id": row.get("request_id"),
        "stage12404_request_hash": stable_hash(row.get("request_id") or "missing", 24),
        "stage12404_source_record_ref_hash": source_ref_hash,
        "stage12327_private_ref_hash": refs.get("stage12327_private_ref_hash") or "missing",
        "safe_schema_version": SAFE_SCHEMA,
        "language_family": row.get("language") or "unknown",
        "repo_family_hash": row.get("repo_hash") or "missing",
        "source_record_ref_hash": source_ref_hash,
        "instance_ref_hash": refs.get("instance_ref_hash") or "missing",
        "trajectory_ref_hash": refs.get("trajectory_ref_hash") or "missing",
        "model_patch_ref_hash": refs.get("model_patch_ref_hash") or "missing",
        "stage12402_digest_item_hash": refs.get("stage12402_digest_item_hash") or "missing",
        "stage12402_event_digest_hash": refs.get("stage12402_event_digest_hash") or "missing",
        "stage12403_window_id_hash": refs.get("stage12403_window_id_hash") or "missing",
        "source_window_id_hash": refs.get("stage12403_window_id_hash") or "missing",
        "event_ref_hashes": row.get("event_ref_hashes") or [],
        "event_ref_count": int(row.get("event_ref_count") or len(row.get("event_ref_hashes") or [])),
        "window_event_ordinals": row.get("window_event_ordinals") or [],
        "window_anchor_ordinal": row.get("window_anchor_ordinal") or 0,
        "private_locator_match_status": "matched_private_locator_hash" if private_match else "missing_private_locator_hash",
        "private_locator_index_ref_hash": stable_hash(private.get("private_locator_id") if private else "missing", 24),
        "private_locator_ref_hash": stable_hash(private.get("private_locator_id") if private else "missing", 24),
        "private_locator_match_count": 1 if private_match else 0,
        "dataset_ref_hash": private.get("dataset_file_hash") if private else "missing",
        "dataset_file_hash": private.get("dataset_file_hash") if private else "missing",
        "trajectory_family_hash": private.get("trajectory_family_hash") if private else "missing",
        "private_locator_values_emitted_publicly": False,
        "window_type": row.get("window_type") or "unknown",
        "candidate_window_type": row.get("candidate_window_type") or row.get("window_type") or "unknown",
        "window_anchor_class": row.get("window_anchor_class") or "unknown",
        "required_executor_return_schema_version": "stage12412_safe_raw_private_semantic_review_return_v1",
        "requested_safe_return_schema": [
            "state_before_identity_hash",
            "chosen_action_ref_hash",
            "observation_ref_hash",
            "verifier_identity_hash",
            "verifier_output_class",
            "patch_application_status",
            "state_after_identity_hash",
            "stop_continue_status",
            "causal_linkage_status",
            "raw_content_policy",
        ],
        "required_reconstruction_tasks": row.get("required_reconstruction_tasks") or {},
        "required_reconstruction_task_classes": sorted((row.get("required_reconstruction_tasks") or {}).keys()),
        "request_readiness_status": "row_locator_hash_repaired_semantic_proofs_missing" if private_match else "row_locator_hash_unresolved",
        "target_next_stage": "raw_private_semantic_reviewer_candidate",
        "execution_attempt_status": "not_attempted",
        "replay_outcome_status": "not_run",
        "level3_status": "level3_still_blocked",
        "proof_slot_statuses": proof_slots(),
        "blockers": sorted(set(blockers)),
        "raw_content_policy": RAW_CONTENT_POLICY,
        "claim_boundary": CLAIM_BOUNDARY,
        "zero_admission_flags": ZERO_ADMISSION_FLAGS,
    }


def scan_public(paths: list[Path]) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    for path in paths:
        text = path.read_text()
        if ABS_PATH_RE.search(text):
            issues.append({"artifact": path.name, "issue": "absolute_path_pattern"})
        if URL_RE.search(text):
            issues.append({"artifact": path.name, "issue": "url_pattern"})
        if DIFF_RE.search(text):
            issues.append({"artifact": path.name, "issue": "diff_like_pattern"})
        for raw_claim in (
            '"training_allowed": true',
            '"admitted_rows": 1',
            '"level3_admitted": 1',
            '"patch_trace_admitted": 1',
            '"replay_executed": true',
            '"raw_locator_emitted": true',
        ):
            if raw_claim in text:
                issues.append({"artifact": path.name, "issue": "forbidden_claim", "claim_hash": stable_hash(raw_claim, 16)})
    return issues


def validate(rows: list[dict[str, Any]]) -> list[str]:
    issues: list[str] = []
    for i, row in enumerate(rows, 1):
        if row.get("execution_attempt_status") != "not_attempted":
            issues.append(f"row_{i}_execution_attempted")
        if row.get("replay_outcome_status") != "not_run":
            issues.append(f"row_{i}_replay_not_run_mismatch")
        if row.get("level3_status") != "level3_still_blocked":
            issues.append(f"row_{i}_level3_not_blocked")
        for key, expected in ZERO_ADMISSION_FLAGS.items():
            if row.get("zero_admission_flags", {}).get(key) != expected:
                issues.append(f"row_{i}_zero_flag_{key}_mismatch")
        for key, expected in RAW_CONTENT_POLICY.items():
            if row.get("raw_content_policy", {}).get(key) is not expected:
                issues.append(f"row_{i}_raw_policy_{key}_mismatch")
        for slot, proof in row.get("proof_slot_statuses", {}).items():
            if slot not in PROOF_SLOTS or proof.get("proof_proven") is not False:
                issues.append(f"row_{i}_proof_slot_{slot}_invalid")
    return issues


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    stage12404_rows, issues = read_jsonl(STAGE12404_ROWS)
    private_rows, private_issues = read_jsonl(STAGE12410_PRIVATE)
    issues.extend(private_issues)
    private_by_hash = private_index_by_hash(private_rows)
    output_rows = [build_row(row, private_by_hash, rank) for rank, row in enumerate(stage12404_rows, 1)]
    issues.extend(validate(output_rows))

    rows_path = OUT / ROWS_NAME
    manifest_path = OUT / MANIFEST_NAME
    write_jsonl(rows_path, output_rows)
    manifest = {
        "stage": STAGE,
        "record_type": "open_swe_row_lineage_repaired_replay_request_manifest",
        "input_stage12404_hash": file_hash(STAGE12404_ROWS),
        "input_private_locator_index_hash": file_hash(STAGE12410_PRIVATE),
        "stage12410_summary_hash": file_hash(STAGE12410_SUMMARY),
        "output_bundle_hash": stable_hash(output_rows),
        "private_locator_values_emitted_publicly": False,
        "raw_content_policy": RAW_CONTENT_POLICY,
        "claim_boundary": CLAIM_BOUNDARY,
        "zero_admission_flags": ZERO_ADMISSION_FLAGS,
    }
    write_json(manifest_path, manifest)
    guardrail_issues = scan_public([rows_path, manifest_path])
    write_json(OUT / GUARDRAIL_NAME, {"scan_passed": not guardrail_issues, "issues": guardrail_issues})

    lang_counts = Counter(row.get("language_family") or "unknown" for row in output_rows)
    match_counts = Counter(row.get("private_locator_match_status") or "unknown" for row in output_rows)
    decision = "fail_closed_row_lineage_repaired_replay_requests_ready_for_raw_private_semantic_review"
    if issues or guardrail_issues:
        decision = "fail_closed_row_lineage_repaired_replay_requests_blocked_by_qc_issue"
    summary = {
        "stage": STAGE,
        "record_type": "open_swe_row_lineage_repaired_replay_request_summary",
        "decision": decision,
        "input_stage12404_request_rows": len(stage12404_rows),
        "private_locator_index_rows": len(private_rows),
        "output_repaired_request_rows": len(output_rows),
        "private_locator_matched_rows": match_counts.get("matched_private_locator_hash", 0),
        "private_locator_missing_rows": match_counts.get("missing_private_locator_hash", 0),
        "language_family_counts": dict(sorted(lang_counts.items())),
        "raw_parquet_rows_read_count": 0,
        "private_locator_values_emitted_publicly": False,
        "raw_content_emitted_count": 0,
        "replay_attempted_count": 0,
        "admitted_rows": 0,
        "training_allowed": False,
        "training_row_count": 0,
        "eval_row_count": 0,
        "level3_admitted": 0,
        "patch_trace_admitted": 0,
        "repair_claim_admitted": 0,
        "fail_to_pass_claim_admitted": 0,
        "strict_eval_eligible": 0,
        "source_heldout_admissible": 0,
        "input_stage12410_private_locator_rows": len(private_rows),
        "input_stage12404_unique_source_record_ref_hashes": len({(r.get("source_digest_refs") or {}).get("source_record_ref_hash") for r in stage12404_rows if isinstance(r.get("source_digest_refs"), dict)}),
        "row_lineage_request_rows": len(output_rows),
        "private_locator_unmatched_rows": match_counts.get("missing_private_locator_hash", 0),
        "duplicate_source_record_ref_hashes": max(0, len(stage12404_rows) - len({(r.get("source_digest_refs") or {}).get("source_record_ref_hash") for r in stage12404_rows if isinstance(r.get("source_digest_refs"), dict)})),
        "replay_succeeded_safe_status_count": 0,
        "schema_issue_count": len(issues),
        "schema_issues": issues,
        "guardrail_issue_count": len(guardrail_issues),
        "guardrail_issues": guardrail_issues,
        "raw_leak_count": len(guardrail_issues),
        "next_stage_required": "stage12412_raw_private_semantic_reviewer_must_prove_state_patch_verifier_causality_before_any_admission",
        "raw_content_policy": RAW_CONTENT_POLICY,
        "claim_boundary": CLAIM_BOUNDARY,
        "zero_admission_flags": ZERO_ADMISSION_FLAGS,
    }
    write_json(SUMMARY, summary)


if __name__ == "__main__":
    main()
