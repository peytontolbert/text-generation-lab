#!/usr/bin/env python3
"""Integrate recovered source-stage locator refs without emitting handoff jobs.

Stage12507 consumes Stage12504 locator work items and Stage12506 recovered
source-stage locator candidates. It writes a patched hash-only worklist that a
future Stage12505 rerun can consume. It does not execute ai_env extraction,
write Stage12503 returns, admit rows, or emit training data.
"""
from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12507_recovered_source_locator_integration_preflight"
OUT = ROOT / "runs/local/artifacts" / STAGE
SUMMARY = ROOT / "runs/summaries" / f"{STAGE}.json"

STAGE12504 = "stage12504_private_extractor_source_locator_worklist"
STAGE12504_WORKLIST = ROOT / "runs/local/artifacts" / STAGE12504 / "private_extractor_source_locator_worklist.jsonl"
STAGE12505 = "stage12505_ai_env_extraction_handoff_or_blocker"
STAGE12505_BLOCKERS = ROOT / "runs/local/artifacts" / STAGE12505 / "ai_env_private_extraction_handoff_blockers.jsonl"
STAGE12506 = "stage12506_source_stage_locator_recovery_preflight"
STAGE12506_CANDIDATES = ROOT / "runs/local/artifacts" / STAGE12506 / "source_stage_locator_recovery_candidates.jsonl"

CONTEXT_ONLY_STAGES = {
    "stage12500_closed_loop_candidate_packet_router",
    "stage12502_authoritative_private_semantic_extraction_request_preflight",
    "stage12503_private_semantic_extraction_return_validator",
    STAGE12504,
    STAGE12505,
    STAGE12506,
    STAGE,
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
    "stage12503_return_materialized": False,
    "stage12503_return_file_written": False,
    "handoff_jobs_emitted": False,
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
    "handoff_job_count": 0,
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
        raise RawLeakError(f"stage12507 raw leak guard rejected {len(issues)} public field(s)")


def recovered_refs(candidate: dict[str, Any]) -> list[dict[str, Any]]:
    refs: list[dict[str, Any]] = []
    source_stage = candidate.get("source_stage")
    for ref in candidate.get("source_stage_locator_refs") or []:
        if ref.get("artifact_stage") != source_stage:
            continue
        if ref.get("artifact_stage") in CONTEXT_ONLY_STAGES:
            continue
        if ref.get("public_safe_hash_locator_only") is not True:
            continue
        if ref.get("raw_locator_values_emitted") is not False:
            continue
        refs.append(
            {
                "record_type": "stage12507_integrated_source_stage_locator_ref_v1",
                "locator_id_hash": ref.get("locator_id_hash"),
                "artifact_stage": ref.get("artifact_stage"),
                "artifact_locator_hash": ref.get("artifact_locator_hash"),
                "artifact_file_role_hash": ref.get("artifact_file_role_hash"),
                "artifact_content_hash": ref.get("artifact_content_hash"),
                "row_locator_hash": ref.get("row_locator_hash"),
                "matched_lookup_key_names": ref.get("matched_row_key_names") or ref.get("matched_lookup_key_names") or [],
                "recovery_method": ref.get("recovery_method"),
                "integrated_from_stage": STAGE12506,
                "public_safe_hash_locator_only": True,
                "raw_locator_values_emitted": False,
            }
        )
    return refs


def by_request(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for row in rows:
        request_id = row.get("request_id_hash")
        if isinstance(request_id, str):
            out[request_id] = row
    return out


def context_locator_records(row: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        locator
        for locator in row.get("hash_locator_records") or []
        if locator.get("artifact_stage") in CONTEXT_ONLY_STAGES
    ]


def build(root: Path = ROOT) -> dict[str, Any]:
    out = root / "runs/local/artifacts" / STAGE
    out.mkdir(parents=True, exist_ok=True)

    work_items = read_jsonl(root / STAGE12504_WORKLIST.relative_to(ROOT)) if STAGE12504_WORKLIST.is_absolute() else read_jsonl(root / STAGE12504_WORKLIST)
    blockers = by_request(read_jsonl(root / STAGE12505_BLOCKERS.relative_to(ROOT))) if STAGE12505_BLOCKERS.is_absolute() else by_request(read_jsonl(root / STAGE12505_BLOCKERS))
    candidates = by_request(read_jsonl(root / STAGE12506_CANDIDATES.relative_to(ROOT))) if STAGE12506_CANDIDATES.is_absolute() else by_request(read_jsonl(root / STAGE12506_CANDIDATES))

    patched: list[dict[str, Any]] = []
    blocked: list[dict[str, Any]] = []
    for item in work_items:
        request_id = item.get("request_id_hash")
        candidate = candidates.get(request_id)
        blocker = blockers.get(request_id)
        refs = recovered_refs(candidate or {})
        blocker_codes: list[str] = []
        if item.get("materialization_environment") != "ai_env":
            blocker_codes.append("stage12504_materialization_environment_not_ai_env")
        if not blocker:
            blocker_codes.append("stage12505_blocker_missing_for_request")
        if not candidate:
            blocker_codes.append("stage12506_recovery_candidate_missing")
        if not refs:
            blocker_codes.append("recovered_original_source_stage_locator_refs_missing")
        if item.get("source_stage") in CONTEXT_ONLY_STAGES or not item.get("source_stage"):
            blocker_codes.append("source_stage_missing_or_context_only")

        common = {
            "request_id_hash": request_id,
            "audit_item_id_hash": item.get("audit_item_id_hash"),
            "work_item_id_hash": item.get("work_item_id_hash"),
            "packet_id_hash": item.get("packet_id_hash"),
            "root_or_window_hash": item.get("root_or_window_hash"),
            "source_stage": item.get("source_stage"),
            "source_kind": item.get("source_kind"),
            "task_family": item.get("task_family"),
            "language_family": item.get("language_family"),
            "materialization_environment": "ai_env",
            "forbidden_materialization_environments": ["trellis"],
            "raw_private_values_revealed": False,
            "raw_locator_values_emitted": False,
            "public_safe_hash_locator_only": True,
            **FALSE_GUARDS,
            **ZERO_GUARDS,
        }
        if blocker_codes:
            row = {
                "record_type": "stage12507_recovered_source_locator_integration_blocker_v1",
                "integration_blocker_id_hash": stable_hash({"request": request_id, "blockers": sorted(blocker_codes)}),
                "integration_decision": "blocked_recovered_source_locator_integration_incomplete",
                "blocker_codes": sorted(set(blocker_codes)),
                "context_locator_ref_count": len(context_locator_records(item)),
                "recovered_source_stage_locator_ref_count": len(refs),
                "patched_work_item_emitted": False,
                **common,
            }
            enforce_no_raw_leaks(row)
            blocked.append(row)
            continue

        merged_locators = [*item.get("hash_locator_records", []), *refs]
        row = {
            **item,
            "record_type": "stage12507_patched_private_extractor_source_locator_work_item_v1",
            "patched_locator_work_item_id_hash": stable_hash({"request": request_id, "refs": refs}),
            "source_stage_locator_recovery_stage": STAGE12506,
            "source_stage_locator_recovery_ready": True,
            "source_stage_locator_ref_count": len(refs),
            "context_locator_ref_count": len(context_locator_records(item)),
            "hash_locator_records": merged_locators,
            "hash_locator_count": len(merged_locators),
            "stage12505_rerun_ready": True,
            "stage12505_handoff_emitted_by_stage12507": False,
            "claim_boundary": "Patched hash-only locator work item for future Stage12505 rerun. Not semantic proof, not ai_env execution, not admission, not training.",
            **common,
        }
        enforce_no_raw_leaks(row)
        patched.append(row)

    all_rows = [*patched, *blocked]
    leak_issues = scan_raw_leaks({"patched": patched, "blocked": blocked})
    if leak_issues:
        raise RawLeakError("stage12507 raw leak guard rejected public outputs")

    blocker_counts = Counter()
    for row in blocked:
        blocker_counts.update(row.get("blocker_codes") or [])
    source_counts = Counter(row.get("source_stage") for row in all_rows)
    task_counts = Counter(row.get("task_family") for row in all_rows)
    language_counts = Counter(row.get("language_family") for row in all_rows)
    integrated_ref_count = sum(row.get("source_stage_locator_ref_count", 0) for row in patched)

    contract = {
        "record_type": "stage12507_recovered_source_locator_integration_contract_v1",
        "stage": STAGE,
        "input_stages": [STAGE12504, STAGE12505, STAGE12506],
        "materialization_environment": "ai_env",
        "forbidden_materialization_environments": ["trellis"],
        "public_artifact_policy": "hashes_stage_ids_enums_only_no_raw_paths_commands_diffs_source_or_verifier_output",
        "handoff_policy": "stage12507_does_not_emit_handoff_jobs_rerun_stage12505_on_patched_worklist",
        "semantic_proof_policy": "locator_recovery_is_not_private_semantic_extraction_or_level3_proof",
        **FALSE_GUARDS,
        **ZERO_GUARDS,
    }
    guardrail = {
        "stage": STAGE,
        "scan_passed": True,
        "raw_leak_count": 0,
        "raw_leak_issue_hashes": [],
        "scanned_outputs": [
            "patched_private_extractor_source_locator_worklist.jsonl",
            "recovered_source_locator_integration_blockers.jsonl",
            "recovered_source_locator_integration_contract.json",
        ],
    }
    decision = (
        "recovered_source_locator_integration_ready_for_stage12505_rerun_no_training_or_handoff"
        if patched and not blocked
        else "partial_recovered_source_locator_integration_remaining_blocked_no_training_or_handoff"
        if patched
        else "blocked_recovered_source_locator_integration_no_training_or_handoff"
    )
    summary = {
        "stage": STAGE,
        "record_type": "stage12507_recovered_source_locator_integration_summary_v1",
        "decision": decision,
        "claim_boundary": "Stage12507 only integrates recovered hash-only source-stage locators into a patched worklist. It is not extraction, proof, Level-3 admission, or training.",
        "input_work_item_count": len(work_items),
        "stage12505_blocker_count": len(blockers),
        "stage12506_candidate_count": len(candidates),
        "patched_work_item_count": len(patched),
        "integration_blocker_count": len(blocked),
        "integrated_source_stage_locator_ref_count": integrated_ref_count,
        "blocker_code_counts": dict(sorted(blocker_counts.items())),
        "source_stage_counts": dict(sorted(source_counts.items())),
        "task_family_counts": dict(sorted(task_counts.items())),
        "language_counts": dict(sorted(language_counts.items())),
        "context_only_promoted_count": 0,
        "materialization_environment": "ai_env",
        "forbidden_materialization_environments": ["trellis"],
        "guardrail_scan_passed": True,
        "raw_leak_count": 0,
        "next_stage": "rerun_stage12505_against_stage12507_patched_worklist_or_patch_stage12504_canonically",
        **FALSE_GUARDS,
        **ZERO_GUARDS,
    }
    enforce_no_raw_leaks({"contract": contract, "guardrail": guardrail, "summary": summary})
    write_jsonl(out / "patched_private_extractor_source_locator_worklist.jsonl", patched)
    write_jsonl(out / "recovered_source_locator_integration_blockers.jsonl", blocked)
    write_json(out / "recovered_source_locator_integration_contract.json", contract)
    write_json(out / "guardrail_scan.json", guardrail)
    write_json(out / "summary.json", summary)
    write_json(root / "runs/summaries" / f"{STAGE}.json", summary)
    return summary


def main() -> None:
    build(ROOT)


if __name__ == "__main__":
    main()
