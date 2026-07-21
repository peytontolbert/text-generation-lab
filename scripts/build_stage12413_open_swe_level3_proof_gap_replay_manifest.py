#!/usr/bin/env python3
"""Build Stage12413 Open-SWE Level-3 proof-gap and replay manifest.

This stage is a no-replay scout over Stage12412 hash-only semantic review
returns and Stage12411 row-lineage replay requests. It emits only safe hashes,
proof-slot statuses, missing proof requirements, replay requirements, and pilot
rankings. It does not read raw parquet rows, execute replay, apply patches, run
tests, or admit training/eval/Level-3/patch-trace rows.
"""
from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12413_open_swe_level3_proof_gap_replay_manifest"
OUT = ROOT / "runs/local/artifacts" / STAGE
SUMMARY = ROOT / "runs/summaries" / f"{STAGE}.json"

STAGE12412_ROWS = (
    ROOT
    / "runs/local/artifacts/stage12412_open_swe_raw_private_semantic_reviewer/"
    "open_swe_raw_private_semantic_review_returns.jsonl"
)
STAGE12412_SUMMARY = ROOT / "runs/summaries/stage12412_open_swe_raw_private_semantic_reviewer.json"
STAGE12411_ROWS = (
    ROOT
    / "runs/local/artifacts/stage12411_open_swe_row_lineage_repaired_replay_requests/"
    "open_swe_row_lineage_repaired_replay_requests.jsonl"
)

LEDGER_NAME = "open_swe_level3_proof_gap_ledger.jsonl"
PILOT_NAME = "open_swe_stage12414_replay_micro_pilot_requests.jsonl"
MANIFEST_NAME = "open_swe_level3_proof_gap_manifest.json"
GUARDRAIL_NAME = "guardrail_scan.json"
SAFE_SCHEMA = "stage12413_open_swe_level3_proof_gap_replay_manifest_v1"

EXPECTED_INPUT_ROWS = 14
MICRO_PILOT_LIMIT = 2
CANDIDATE_HASH_LIMIT = 10

REQUIRED_MISSING_PROOF_SLOTS = [
    "state_before",
    "state_after",
    "patch_application",
    "verifier_relevance",
    "causal_linkage",
    "stop_continue",
    "correct_next_action_policy",
]

SLOT_SOURCE_MAP = {
    "state_before": "state_before",
    "state_after": "state_after",
    "patch_application": "patch_application",
    "verifier_relevance": "verifier_identity",
    "causal_linkage": "causal_linkage",
    "stop_continue": "stop_continue",
    "correct_next_action_policy": "correct_next_action_policy",
}

HASH_ONLY_SUFFICIENCY = {
    "state_before": "environment_replay_required_hash_only_insufficient",
    "state_after": "environment_replay_required_hash_only_insufficient",
    "patch_application": "environment_replay_required_hash_only_insufficient",
    "verifier_relevance": "environment_replay_required_hash_only_insufficient",
    "causal_linkage": "environment_replay_required_hash_only_insufficient",
    "stop_continue": "partial_raw_terminal_hash_possible_policy_still_requires_replay_context",
    "correct_next_action_policy": "environment_replay_required_hash_only_insufficient",
}

STAGE12414_REPLAY_REQUIREMENTS = [
    "checkout_authoritative_state_before",
    "apply_patch",
    "hash_state_after",
    "run_same_verifier_before_after_if_feasible",
    "emit_safe_hashes_status_codes_only",
]

REPLAY_SAFE_RETURN_SCHEMA = [
    "row_ref_hash",
    "state_before_checkout_status",
    "state_before_identity_hash",
    "patch_application_status",
    "state_after_identity_hash",
    "verifier_identity_hash",
    "verifier_before_status_code",
    "verifier_after_status_code",
    "verifier_relevance_status",
    "causal_linkage_status",
    "stop_continue_status",
    "correct_next_action_policy_status",
    "raw_content_policy",
]

RAW_CONTENT_POLICY: dict[str, bool] = {
    "raw_parquet_rows_read": False,
    "raw_parquet_row_content_emitted": False,
    "private_locator_values_emitted_publicly": False,
    "raw_locator_values_emitted": False,
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

CLAIM_BOUNDARY: dict[str, bool | str] = {
    "boundary": "stage12413_hash_only_proof_gap_manifest_no_replay_no_admission",
    "raw_locator_emitted": False,
    "raw_row_content_read": False,
    "raw_row_content_emitted": False,
    "replay_executed": False,
    "patch_applied": False,
    "tests_run": False,
    "training_claim": False,
    "eval_claim": False,
    "admission_claim": False,
    "level3_claim": False,
    "repair_claim": False,
    "fail_to_pass_claim": False,
    "patch_trace_claim": False,
}

ZERO_ADMISSION_FLAGS: dict[str, bool | int] = {
    "admission": False,
    "training_allowed": False,
    "training_row_count": 0,
    "eval_row_count": 0,
    "admitted_rows": 0,
    "level3_admitted": 0,
    "patch_trace_admitted": 0,
    "repair_claim_admitted": 0,
    "fail_to_pass_claim_admitted": 0,
    "strict_eval_eligible": 0,
    "source_heldout_admissible": 0,
    "replay_attempted_count": 0,
    "tests_run_count": 0,
    "patch_apply_attempted_count": 0,
}

ABS_PATH_RE = re.compile(r"(?<![A-Za-z0-9_])/(?:[A-Za-z0-9._-]+/){2,}[A-Za-z0-9._-]+")
URL_RE = re.compile(r"https?://|www\.", re.IGNORECASE)
DIFF_RE = re.compile(r"diff --git|@@ |^\+\+\+ |^--- |<<<<<<<|\*\*\* Begin Patch", re.MULTILINE)
HEX_RE = re.compile(r"^[0-9a-f]{12,64}$")
RAW_KEY_RE = re.compile(
    r"(?:^|_)(trajectory|command|output|stdout|stderr|source_text|issue_body|line_content|url|path|diff)(?:$|_)",
    re.IGNORECASE,
)
SAFE_KEY_CONTEXT_RE = re.compile(
    r"(?:status|code|codes|proof|gate|hash|hashes|class|classes|policy|count|counts|"
    r"bucket|ref|refs|emitted|allowed|stage|schema|boundary|flags|requirement|requirements|"
    r"claim|admitted|applied|application|trace)",
    re.IGNORECASE,
)

FORBIDDEN_PUBLIC_KEYS = {
    "source_record_ref",
    "dataset_file",
    "instance_id",
    "trajectory_id",
    "raw_path",
    "url",
    "command_text",
    "stdout",
    "stderr",
    "issue_body",
    "source_text",
    "line_content",
    "raw_parquet_row_content",
    "raw_row",
    "verifier_command",
    "patch_diff",
    "patch_text",
}


def stable_hash(value: Any, n: int = 24) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:n]


def file_hash(path: Path, n: int = 24) -> str:
    if not path.exists():
        return "missing"
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()[:n]


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return value if isinstance(value, dict) else {}


def read_jsonl(path: Path) -> tuple[list[dict[str, Any]], list[str]]:
    rows: list[dict[str, Any]] = []
    issues: list[str] = []
    if not path.exists():
        return rows, [f"missing_input_{path.name}"]
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            if not line.strip():
                continue
            try:
                value = json.loads(line)
            except json.JSONDecodeError:
                issues.append(f"{path.name}_line_{line_number}_invalid_json")
                continue
            if not isinstance(value, dict):
                issues.append(f"{path.name}_line_{line_number}_not_object")
                continue
            rows.append(value)
    return rows, issues


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")


def require_hash(value: Any) -> str:
    text = str(value or "missing")
    return text if HEX_RE.fullmatch(text) else stable_hash(text)


def request_join_key(row: dict[str, Any]) -> str:
    return str(row.get("repair_request_id") or row.get("stage12411_request_hash") or "")


def build_stage12411_index(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    by_key: dict[str, dict[str, Any]] = {}
    for row in rows:
        key = request_join_key(row)
        if key:
            by_key[key] = row
        request_hash = stable_hash(row)
        by_key.setdefault(request_hash, row)
    return by_key


def priority_bucket(causal_linkage_status: str) -> int:
    if causal_linkage_status == "patch_and_verifier_co_present_ordered_not_causal_proof":
        return 0
    if causal_linkage_status == "verifier_before_patch_not_causal_proof":
        return 1
    return 2


def slot_status(row: dict[str, Any], slot: str) -> dict[str, Any]:
    slots = row.get("proof_slot_statuses")
    source_slot = SLOT_SOURCE_MAP[slot]
    value = slots.get(source_slot) if isinstance(slots, dict) else None
    if not isinstance(value, dict):
        return {
            "proof_proven": False,
            "proof_status": "blocked_required_safe_evidence_missing",
            "status_code": "blocked_required_safe_evidence_missing",
            "evidence_class": "missing_safe_status",
            "proof_ref_hash": "missing",
        }
    return {
        "proof_proven": bool(value.get("proof_proven") is True),
        "proof_status": str(value.get("proof_status") or "blocked_required_safe_evidence_missing"),
        "status_code": str(value.get("status_code") or "blocked_required_safe_evidence_missing"),
        "evidence_class": str(value.get("evidence_class") or "missing_safe_status"),
        "proof_ref_hash": require_hash(value.get("proof_ref_hash")),
    }


def missing_proof_requirements(row: dict[str, Any]) -> list[dict[str, Any]]:
    requirements: list[dict[str, Any]] = []
    for slot in REQUIRED_MISSING_PROOF_SLOTS:
        status = slot_status(row, slot)
        requirements.append(
            {
                "proof_slot": slot,
                "proof_proven": False,
                "current_proof_status": status["proof_status"],
                "current_status_code": status["status_code"],
                "current_evidence_class": status["evidence_class"],
                "safe_proof_ref_hash": status["proof_ref_hash"],
                "hash_only_raw_inspection_sufficiency": HASH_ONLY_SUFFICIENCY[slot],
                "required_next_evidence_class": "environment_replay_safe_hash_status_only",
            }
        )
    return requirements


def safe_row_hashes(row: dict[str, Any], request: dict[str, Any] | None) -> dict[str, str]:
    return {
        "row_ref_hash": require_hash(row.get("raw_row_hash_only_digest")),
        "source_record_ref_hash": require_hash(row.get("source_record_ref_hash")),
        "instance_ref_hash": require_hash(row.get("instance_ref_hash")),
        "trajectory_ref_hash": require_hash(row.get("trajectory_ref_hash")),
        "repo_family_hash": require_hash(row.get("repo_family_hash")),
        "dataset_file_hash": require_hash(row.get("dataset_file_hash")),
        "stage12411_request_hash": require_hash(row.get("stage12411_request_hash")),
        "stage12411_request_row_hash": require_hash(stable_hash(request) if request else "missing"),
    }


def build_ledger_row(
    row: dict[str, Any],
    request: dict[str, Any] | None,
    rank: int,
    priority: int,
) -> dict[str, Any]:
    return {
        "record_type": "open_swe_level3_proof_gap_ledger_row",
        "stage": STAGE,
        "safe_schema_version": SAFE_SCHEMA,
        "row_hashes": safe_row_hashes(row, request),
        "blocked_status": "blocked_no_training_no_eval_no_level3_no_patch_trace",
        "semantic_review_status": str(row.get("semantic_review_status") or "missing"),
        "patch_application_status": str(row.get("patch_application_status") or "missing"),
        "causal_linkage_status": str(row.get("causal_linkage_status") or "missing"),
        "stop_continue_status": str(row.get("stop_continue_status") or "missing"),
        "proof_gap_status": "level3_required_proofs_missing_replay_required",
        "missing_proof_requirements": missing_proof_requirements(row),
        "stage12414_replay_requirements": STAGE12414_REPLAY_REQUIREMENTS,
        "stage12414_safe_return_schema": REPLAY_SAFE_RETURN_SCHEMA,
        "pilot_ranking": {
            "rank": rank,
            "priority_bucket": priority,
            "priority_reason": str(row.get("causal_linkage_status") or "missing"),
            "micro_pilot_selected": rank <= MICRO_PILOT_LIMIT,
            "candidate_hash_list_selected": rank <= CANDIDATE_HASH_LIMIT,
        },
        "raw_content_policy": RAW_CONTENT_POLICY,
        "claim_boundary": CLAIM_BOUNDARY,
        "zero_admission_flags": ZERO_ADMISSION_FLAGS,
    }


def build_pilot_request(ledger_row: dict[str, Any]) -> dict[str, Any]:
    ranking = ledger_row["pilot_ranking"]
    return {
        "record_type": "open_swe_stage12414_replay_micro_pilot_request",
        "stage": STAGE,
        "target_next_stage": "stage12414_open_swe_authoritative_replay_micro_pilot",
        "safe_schema_version": SAFE_SCHEMA,
        "request_hash": stable_hash(
            {
                "row_hashes": ledger_row["row_hashes"],
                "rank": ranking["rank"],
                "requirements": STAGE12414_REPLAY_REQUIREMENTS,
            }
        ),
        "row_hashes": ledger_row["row_hashes"],
        "pilot_ranking": ranking,
        "blocked_status": ledger_row["blocked_status"],
        "missing_proof_requirements": ledger_row["missing_proof_requirements"],
        "stage12414_replay_requirements": STAGE12414_REPLAY_REQUIREMENTS,
        "stage12414_safe_return_schema": REPLAY_SAFE_RETURN_SCHEMA,
        "allowed_public_return_boundary": "safe_hashes_and_status_codes_only",
        "disallowed_public_returns": [
            "raw_paths",
            "urls",
            "commands",
            "outputs",
            "patches",
            "diffs",
            "source_text",
            "issue_bodies",
        ],
        "raw_content_policy": RAW_CONTENT_POLICY,
        "claim_boundary": CLAIM_BOUNDARY,
        "zero_admission_flags": ZERO_ADMISSION_FLAGS,
    }


def assert_zero_admission(value: dict[str, Any]) -> list[str]:
    issues: list[str] = []
    required = {
        "training_allowed": False,
        "training_row_count": 0,
        "eval_row_count": 0,
        "admitted_rows": 0,
        "level3_admitted": 0,
        "patch_trace_admitted": 0,
        "repair_claim_admitted": 0,
        "fail_to_pass_claim_admitted": 0,
        "strict_eval_eligible": 0,
        "source_heldout_admissible": 0,
    }
    for key, expected in required.items():
        if value.get(key) != expected:
            issues.append(f"{key}_not_{expected}")
    return issues


def raw_key_issues(value: Any, path: str = "$") -> list[str]:
    issues: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            key_text = str(key)
            if key_text in FORBIDDEN_PUBLIC_KEYS:
                issues.append(f"{path}.{key_text}_forbidden_key")
            elif RAW_KEY_RE.search(key_text) and not SAFE_KEY_CONTEXT_RE.search(key_text):
                issues.append(f"{path}.{key_text}_rawish_key_without_safe_context")
            issues.extend(raw_key_issues(child, f"{path}.{key_text}"))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            issues.extend(raw_key_issues(child, f"{path}[{index}]"))
    return issues


def scan_public_artifacts(paths: list[Path]) -> dict[str, Any]:
    issues: list[dict[str, Any]] = []
    parsed_json_values = 0
    scanned_jsonl_rows = 0
    for path in paths:
        text = path.read_text(encoding="utf-8")
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
            '"repair_claim_admitted": 1',
            '"fail_to_pass_claim_admitted": 1',
            '"strict_eval_eligible": 1',
            '"source_heldout_admissible": 1',
            '"replay_executed": true',
            '"patch_applied": true',
            '"tests_run": true',
        ):
            if raw_claim in text:
                issues.append({"artifact": path.name, "issue": f"forbidden_claim_{raw_claim}"})
        if path.suffix == ".jsonl":
            for line_number, line in enumerate(text.splitlines(), 1):
                if not line.strip():
                    continue
                scanned_jsonl_rows += 1
                try:
                    value = json.loads(line)
                except json.JSONDecodeError:
                    issues.append({"artifact": path.name, "issue": f"line_{line_number}_invalid_json"})
                    continue
                for key_issue in raw_key_issues(value):
                    issues.append({"artifact": path.name, "issue": key_issue})
        else:
            try:
                value = json.loads(text)
            except json.JSONDecodeError:
                issues.append({"artifact": path.name, "issue": "invalid_json"})
                continue
            parsed_json_values += 1
            for key_issue in raw_key_issues(value):
                issues.append({"artifact": path.name, "issue": key_issue})
    return {
        "scan_passed": not issues,
        "issues": issues,
        "scanned_artifact_count": len(paths),
        "scanned_jsonl_rows": scanned_jsonl_rows,
        "parsed_json_values": parsed_json_values,
    }


def main() -> None:
    stage12412_rows, row_issues = read_jsonl(STAGE12412_ROWS)
    stage12411_rows, request_issues = read_jsonl(STAGE12411_ROWS)
    stage12412_summary = read_json(STAGE12412_SUMMARY)
    schema_issues = row_issues + request_issues
    if len(stage12412_rows) != EXPECTED_INPUT_ROWS:
        schema_issues.append(f"stage12412_input_rows_expected_{EXPECTED_INPUT_ROWS}_got_{len(stage12412_rows)}")
    if int(stage12412_summary.get("raw_parquet_rows_read_internal_count") or 0) != EXPECTED_INPUT_ROWS:
        schema_issues.append("stage12412_summary_raw_private_review_count_mismatch")

    request_index = build_stage12411_index(stage12411_rows)
    ranked_source_rows = sorted(
        stage12412_rows,
        key=lambda row: (
            priority_bucket(str(row.get("causal_linkage_status") or "")),
            str(row.get("raw_row_hash_only_digest") or ""),
        ),
    )

    ledger_rows: list[dict[str, Any]] = []
    missing_stage12411_joins = 0
    for rank, row in enumerate(ranked_source_rows, 1):
        request = request_index.get(request_join_key(row))
        if request is None:
            missing_stage12411_joins += 1
        priority = priority_bucket(str(row.get("causal_linkage_status") or ""))
        ledger_rows.append(build_ledger_row(row, request, rank, priority))

    pilot_rows = [build_pilot_request(row) for row in ledger_rows[:MICRO_PILOT_LIMIT]]
    top_candidate_hashes = [
        {
            "rank": row["pilot_ranking"]["rank"],
            "priority_bucket": row["pilot_ranking"]["priority_bucket"],
            "priority_reason": row["pilot_ranking"]["priority_reason"],
            "row_hashes": row["row_hashes"],
        }
        for row in ledger_rows[:CANDIDATE_HASH_LIMIT]
    ]

    proof_slot_counts: dict[str, Counter[str]] = {slot: Counter() for slot in REQUIRED_MISSING_PROOF_SLOTS}
    for row in ledger_rows:
        for requirement in row["missing_proof_requirements"]:
            proof_slot_counts[requirement["proof_slot"]][requirement["current_status_code"]] += 1

    causal_counts = Counter(str(row.get("causal_linkage_status") or "missing") for row in stage12412_rows)
    blocked_count = len(ledger_rows)
    manifest: dict[str, Any] = {
        "record_type": "open_swe_level3_proof_gap_manifest",
        "stage": STAGE,
        "safe_schema_version": SAFE_SCHEMA,
        "decision": "fail_closed_no_replay_proof_gap_manifest_zero_admission",
        "input_rows": len(stage12412_rows),
        "stage12411_request_rows": len(stage12411_rows),
        "stage12411_join_missing_count": missing_stage12411_joins,
        "blocked_rows": blocked_count,
        "training_allowed": False,
        "training_row_count": 0,
        "eval_row_count": 0,
        "admitted_rows": 0,
        "level3_admitted": 0,
        "patch_trace_admitted": 0,
        "repair_claim_admitted": 0,
        "fail_to_pass_claim_admitted": 0,
        "strict_eval_eligible": 0,
        "source_heldout_admissible": 0,
        "replay_attempted_count": 0,
        "patch_apply_attempted_count": 0,
        "tests_run_count": 0,
        "causal_linkage_status_counts": dict(sorted(causal_counts.items())),
        "required_missing_proof_slots": REQUIRED_MISSING_PROOF_SLOTS,
        "hash_only_raw_inspection_sufficiency_by_slot": HASH_ONLY_SUFFICIENCY,
        "stage12414_replay_requirements": STAGE12414_REPLAY_REQUIREMENTS,
        "stage12414_safe_return_schema": REPLAY_SAFE_RETURN_SCHEMA,
        "micro_pilot_request_count": len(pilot_rows),
        "micro_pilot_limit": MICRO_PILOT_LIMIT,
        "top_candidate_hash_count": len(top_candidate_hashes),
        "top_candidate_hash_limit": CANDIDATE_HASH_LIMIT,
        "top_candidate_hashes": top_candidate_hashes,
        "proof_slot_status_counts": {slot: dict(counter) for slot, counter in proof_slot_counts.items()},
        "raw_content_policy": RAW_CONTENT_POLICY,
        "claim_boundary": CLAIM_BOUNDARY,
        "zero_admission_flags": ZERO_ADMISSION_FLAGS,
        "schema_issues": schema_issues,
        "schema_issue_count": len(schema_issues),
        "source_stage_artifact_hashes": {
            "stage12412_rows_hash": file_hash(STAGE12412_ROWS),
            "stage12412_summary_hash": file_hash(STAGE12412_SUMMARY),
            "stage12411_rows_hash": file_hash(STAGE12411_ROWS),
        },
    }
    manifest["zero_admission_schema_issues"] = assert_zero_admission(manifest)
    manifest["schema_issue_count"] += len(manifest["zero_admission_schema_issues"])

    ledger_path = OUT / LEDGER_NAME
    pilot_path = OUT / PILOT_NAME
    manifest_path = OUT / MANIFEST_NAME
    guardrail_path = OUT / GUARDRAIL_NAME
    write_jsonl(ledger_path, ledger_rows)
    write_jsonl(pilot_path, pilot_rows)
    write_json(manifest_path, manifest)

    guardrail_scan = scan_public_artifacts([ledger_path, pilot_path, manifest_path])
    write_json(guardrail_path, guardrail_scan)

    summary = dict(manifest)
    summary.update(
        {
            "record_type": "open_swe_level3_proof_gap_replay_manifest_summary",
            "generated_artifact_count": 4,
            "generated_artifact_name_hashes": {
                "ledger": file_hash(ledger_path),
                "micro_pilot_requests": file_hash(pilot_path),
                "manifest": file_hash(manifest_path),
                "guardrail": file_hash(guardrail_path),
            },
            "guardrail_scan": guardrail_scan,
            "guardrail_issue_count": len(guardrail_scan["issues"]),
        }
    )
    summary["schema_issue_count"] = int(summary.get("schema_issue_count") or 0)
    if guardrail_scan["issues"]:
        summary["schema_issue_count"] += len(guardrail_scan["issues"])
    write_json(SUMMARY, summary)

    print(
        json.dumps(
            {
                "stage": STAGE,
                "input_rows": len(stage12412_rows),
                "blocked_rows": blocked_count,
                "micro_pilot_request_count": len(pilot_rows),
                "top_candidate_hash_count": len(top_candidate_hashes),
                "training_allowed": False,
                "admitted_rows": 0,
                "level3_admitted": 0,
                "patch_trace_admitted": 0,
                "guardrail_issue_count": len(guardrail_scan["issues"]),
                "schema_issue_count": summary["schema_issue_count"],
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
