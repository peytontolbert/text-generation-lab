#!/usr/bin/env python3
"""Stage12390 audit-only patch-attempt segmentation and policy candidates.

Reads the Stage12389 semantic review records and predecessor safe metadata,
reopens raw Codex sessions only internally by source hash when available, and
emits atomic patch-attempt candidates for manual review. No raw source paths,
commands, outputs, or patch bodies are emitted. No training, Level-3,
patch-trace, strict-eval, or source-heldout admission is performed.
"""
from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12390_patch_attempt_segmenter_and_policy_candidate_builder"
OUT = ROOT / "runs/local/artifacts" / STAGE
SUMMARY = ROOT / "runs/summaries" / f"{STAGE}.json"
CODEX_SESSIONS = Path.home() / ".codex" / "sessions"

STAGE12389_RECORDS = (
    ROOT
    / "runs/local/artifacts/stage12389_transition_candidate_semantic_review"
    / "transition_candidate_semantic_review_records.jsonl"
)
STAGE12389_SUMMARY = ROOT / "runs/summaries/stage12389_transition_candidate_semantic_review.json"
STAGE12388_RECORDS = (
    ROOT
    / "runs/local/artifacts/stage12388_transition_local_candidate_recovery"
    / "transition_local_candidate_recovery_records.jsonl"
)
STAGE12316_RECORDS = (
    ROOT
    / "runs/local/artifacts/stage12316_transition_local_event_joiner"
    / "transition_local_event_join_records.jsonl"
)
STAGE12260_WINDOWS = (
    ROOT
    / "runs/local/artifacts/stage12260_codex_chat_task_boundary_miner"
    / "codex_task_windows.jsonl"
)

VERIFY_HEADS = {
    "pytest",
    "ctest",
    "cargo",
    "npm",
    "pnpm",
    "yarn",
    "node",
    "npx",
    "make",
    "cmake",
    "python",
    "python3",
    "vitest",
    "tsc",
    "go",
    "bash",
}

ATOMIC_PATCH_STATUSES = {"PATCH_APPLIED", "PATCH_FAILED", "PATCH_STATUS_UNKNOWN"}
MIXED_PATCH_STATUS = "MIXED_PATCH_APPLIED_AND_FAILED"

BASE_BLOCKERS = {
    "manual_review_required",
    "policy_label_not_admitted",
    "observed_action_only_not_policy_gold",
    "level3_control_contract_missing",
    "patch_trace_admission_blocked",
    "strict_eval_admission_blocked",
    "source_heldout_admission_blocked",
    "training_admission_blocked",
}


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")


def stable_id(prefix: str, *parts: Any) -> str:
    payload = json.dumps(parts, sort_keys=True, separators=(",", ":"), default=str)
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:20]
    return f"{prefix}_{digest}"


def stable_hash(value: Any) -> str | None:
    if value in (None, "", [], {}):
        return None
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(f"{STAGE}:{payload}".encode("utf-8")).hexdigest()[:24]


def sha1_text(value: str) -> str:
    return hashlib.sha1(value.encode("utf-8")).hexdigest()


def source_file_map() -> dict[str, Path]:
    mapping: dict[str, Path] = {}
    if not CODEX_SESSIONS.exists():
        return mapping
    for path in CODEX_SESSIONS.rglob("*.jsonl"):
        if path.is_file():
            mapping[sha1_text(str(path))] = path
    return mapping


def safe_json(value: Any) -> Any:
    if isinstance(value, str):
        text = value.strip()
        if text.startswith("{") or text.startswith("["):
            try:
                return json.loads(text)
            except Exception:
                return value
    return value


def extract_payload(obj: dict[str, Any]) -> dict[str, Any]:
    payload = obj.get("payload")
    return payload if isinstance(payload, dict) else {}


def command_head(cmd: str) -> str:
    parts = str(cmd or "").strip().split()
    while parts and "=" in parts[0] and not parts[0].startswith(("/", "./")):
        parts = parts[1:]
    if not parts:
        return ""
    head = parts[0].split("/")[-1]
    if head in {"env", "timeout"} and len(parts) > 1:
        head = parts[1].split("/")[-1]
    return head


def command_head_class(head: str | None) -> str:
    value = str(head or "").lower().split("/")[-1]
    if value in {"pytest"}:
        return "PYTHON_TEST"
    if value in {"python", "python3"}:
        return "PYTHON"
    if value in {"npm", "pnpm", "yarn", "node", "npx", "vitest", "tsc"}:
        return "JS_OR_TS"
    if value == "cargo":
        return "RUST"
    if value in {"make", "cmake", "ctest"}:
        return "BUILD_TOOL"
    if value == "go":
        return "GO"
    if value == "bash":
        return "SHELL"
    if value in VERIFY_HEADS:
        return "VERIFIER_LIKE"
    return "OTHER_OR_UNKNOWN"


def output_status(text: str) -> tuple[str, str]:
    lower = text.lower()
    exit_code = "UNKNOWN"
    match = re.search(r"(?:process exited with code|exit code|returncode)[:= ]+(-?\d+)", lower)
    if match:
        exit_code = "ZERO" if match.group(1) == "0" else "NONZERO"
    if "bwrap:" in lower or "operation not permitted" in lower or "network is unreachable" in lower:
        return "ENV_BLOCKED", exit_code
    if "timeout" in lower or "timed out" in lower:
        return "TIMEOUT_OR_HUNG", exit_code
    if exit_code == "ZERO":
        return "PASS_OR_COMMAND_SUCCESS", exit_code
    if exit_code == "NONZERO":
        return "FAIL_OR_COMMAND_ERROR", exit_code
    if "traceback" in lower or "assertionerror" in lower or " failed" in lower or "error:" in lower:
        return "FAIL_OR_COMMAND_ERROR", exit_code
    if "passed" in lower or "success" in lower:
        return "PASS_OR_COMMAND_SUCCESS", exit_code
    return "UNKNOWN_OUTPUT_STATUS", exit_code


def patch_status(text: str) -> str:
    lower = text.lower()
    if "success. updated" in lower or "successfully applied" in lower or lower.strip() == "done!":
        return "PATCH_APPLIED"
    if "invalid context" in lower or "failed" in lower or "error" in lower:
        return "PATCH_FAILED"
    return "PATCH_STATUS_UNKNOWN"


def read_raw_window(path: Path, start_line: int, end_line: int) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    try:
        with path.open("rb") as handle:
            for line_number, raw_line in enumerate(handle, 1):
                if line_number < start_line:
                    continue
                if line_number > end_line:
                    break
                try:
                    obj = json.loads(raw_line.decode("utf-8", errors="ignore"))
                except Exception:
                    continue
                if isinstance(obj, dict):
                    events.append({"line_number": line_number, "obj": obj})
    except Exception:
        return []
    return events


def index_by(rows: list[dict[str, Any]], key: str) -> dict[str, dict[str, Any]]:
    return {str(row[key]): row for row in rows if row.get(key)}


def source_hash_for(
    review: dict[str, Any],
    recovery: dict[str, Any] | None,
    stage16: dict[str, Any] | None,
    window: dict[str, Any] | None,
) -> str | None:
    if stage16:
        refs = stage16.get("source_refs") if isinstance(stage16.get("source_refs"), dict) else {}
        if refs.get("source_file_hash_compat"):
            return str(refs["source_file_hash_compat"])
    if window and window.get("source_file_hash_compat"):
        return str(window["source_file_hash_compat"])
    if recovery:
        refs = recovery.get("source_refs") if isinstance(recovery.get("source_refs"), dict) else {}
        if refs.get("source_file_hash_compat"):
            return str(refs["source_file_hash_compat"])
    return review.get("source_file_hash_compat")


def call_context(events: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    context: dict[str, dict[str, Any]] = {}
    for event in events:
        payload = extract_payload(event["obj"])
        call_id = str(payload.get("call_id") or payload.get("id") or "")
        tool_name = str(payload.get("name") or "")
        args = safe_json(payload.get("arguments"))
        args = args if isinstance(args, dict) else {}
        head = command_head(str(args.get("cmd") or ""))
        if call_id and (tool_name or head):
            context[call_id] = {
                "tool_name": tool_name,
                "command_head": head,
                "command_head_hash": stable_hash(head),
                "command_head_class": command_head_class(head),
            }
    return context


def extract_atomic_events(events: list[dict[str, Any]], start_line: int) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    context = call_context(events)
    patch_events: list[dict[str, Any]] = []
    verifier_events: list[dict[str, Any]] = []
    for event in events:
        payload = extract_payload(event["obj"])
        if "output" not in payload:
            continue
        call_id = str(payload.get("call_id") or payload.get("id") or "")
        info = context.get(call_id, {})
        tool_name = str(payload.get("name") or info.get("tool_name") or "")
        head = str(info.get("command_head") or "")
        output_text = str(payload.get("output") or "")
        line_number = int(event["line_number"])
        line_offset = line_number - start_line
        if tool_name == "apply_patch":
            patch_events.append(
                {
                    "kind": "patch",
                    "line_number_internal": line_number,
                    "order_hash": stable_hash(["patch", line_offset]),
                    "patch_apply_status": patch_status(output_text),
                }
            )
        if head in VERIFY_HEADS:
            status_class, exit_code_class = output_status(output_text)
            verifier_events.append(
                {
                    "kind": "verifier",
                    "line_number_internal": line_number,
                    "order_hash": stable_hash(["verifier", line_offset]),
                    "command_head_hash": info.get("command_head_hash") or stable_hash(head),
                    "command_head_class": info.get("command_head_class") or command_head_class(head),
                    "observation_status_class": status_class,
                    "exit_code_class": exit_code_class,
                }
            )
    return patch_events, verifier_events


def verifier_after_patch_status(verifiers: list[dict[str, Any]]) -> str:
    statuses = [str(v.get("observation_status_class") or "") for v in verifiers]
    if "FAIL_OR_COMMAND_ERROR" in statuses:
        return "VERIFIER_FAILURE_OBSERVED"
    if "ENV_BLOCKED" in statuses:
        return "VERIFIER_ENV_BLOCKED_OBSERVED"
    if "TIMEOUT_OR_HUNG" in statuses:
        return "VERIFIER_TIMEOUT_OBSERVED"
    if "PASS_OR_COMMAND_SUCCESS" in statuses:
        return "VERIFIER_PASS_OBSERVED"
    if statuses:
        return "VERIFIER_STATUS_UNKNOWN"
    return "NO_VERIFIER_AFTER_PATCH_OBSERVED"


def select_verifier(verifiers: list[dict[str, Any]], status: str) -> dict[str, Any]:
    priority_by_status = {
        "VERIFIER_FAILURE_OBSERVED": "FAIL_OR_COMMAND_ERROR",
        "VERIFIER_ENV_BLOCKED_OBSERVED": "ENV_BLOCKED",
        "VERIFIER_TIMEOUT_OBSERVED": "TIMEOUT_OR_HUNG",
        "VERIFIER_PASS_OBSERVED": "PASS_OR_COMMAND_SUCCESS",
    }
    target = priority_by_status.get(status)
    selected = next((v for v in verifiers if v.get("observation_status_class") == target), None) if target else None
    selected = selected or (verifiers[0] if verifiers else None)
    if not selected:
        return {
            "status": "missing",
            "command_head_hash": None,
            "command_head_class": None,
            "verifier_event_order_hash": None,
            "selection_rule": "no_after_patch_verifier_observed",
            "raw_command_text_emitted": False,
            "raw_tool_output_emitted": False,
        }
    return {
        "status": "selected_for_manual_review",
        "command_head_hash": selected.get("command_head_hash"),
        "command_head_class": selected.get("command_head_class"),
        "verifier_event_order_hash": selected.get("order_hash"),
        "selection_rule": "first_after_patch_matching_aggregate_status_else_first_after_patch",
        "raw_command_text_emitted": False,
        "raw_tool_output_emitted": False,
    }


def segment_patch_attempts_from_raw(
    raw_path: Path | None,
    window: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[str]]:
    blockers: list[str] = []
    if not raw_path:
        return [], ["raw_session_unavailable_for_atomic_segmentation"]
    if not window:
        return [], ["task_window_missing_for_atomic_segmentation"]
    events = read_raw_window(raw_path, int(window.get("start_line") or 0), int(window.get("end_line") or 0))
    if not events:
        return [], ["raw_window_event_recovery_failed_for_atomic_segmentation"]
    patches, verifiers = extract_atomic_events(events, int(window.get("start_line") or 0))
    if not patches:
        return [], ["no_patch_attempt_events_found"]

    segments: list[dict[str, Any]] = []
    for index, patch in enumerate(patches):
        next_patch_line = patches[index + 1]["line_number_internal"] if index + 1 < len(patches) else None
        after_patch = [
            verifier
            for verifier in verifiers
            if int(verifier["line_number_internal"]) > int(patch["line_number_internal"])
            and (next_patch_line is None or int(verifier["line_number_internal"]) < int(next_patch_line))
        ]
        status = verifier_after_patch_status(after_patch)
        segments.append(
            {
                "patch_attempt_index": index,
                "patch_apply_status": patch["patch_apply_status"],
                "verifier_after_patch_status": status,
                "event_order_hashes": {
                    "patch_event_order_hash": patch["order_hash"],
                    "verifier_after_patch_order_hashes": [v["order_hash"] for v in after_patch[-6:]],
                    "next_patch_boundary_order_hash": stable_hash(["patch", next_patch_line]) if next_patch_line else None,
                    "raw_line_numbers_emitted": False,
                },
                "selected_verifier_identity_candidate": select_verifier(after_patch, status),
                "verifier_after_patch_event_count": len(after_patch),
                "segmentation_source": "raw_session_internal",
            }
        )
    return segments, blockers


def fallback_segments_from_recovery(recovery: dict[str, Any] | None) -> tuple[list[dict[str, Any]], list[str]]:
    if not recovery:
        return [], ["recovery_record_missing_for_tail_fallback"]
    transition = recovery.get("transition_recovery") if isinstance(recovery.get("transition_recovery"), dict) else {}
    command_result = (
        transition.get("command_result_candidate")
        if isinstance(transition.get("command_result_candidate"), dict)
        else {}
    )
    patches = command_result.get("patch_events_tail") if isinstance(command_result.get("patch_events_tail"), list) else []
    verifiers = (
        command_result.get("verifier_events_tail")
        if isinstance(command_result.get("verifier_events_tail"), list)
        else []
    )
    if not patches:
        return [], ["no_patch_attempt_events_found_in_recovery_tail"]
    segments: list[dict[str, Any]] = []
    status = verifier_after_patch_status(
        [
            {"observation_status_class": verifier.get("observation_status_class")}
            for verifier in verifiers
            if isinstance(verifier, dict)
        ]
    )
    selected = None
    if verifiers:
        first = next((v for v in verifiers if isinstance(v, dict)), None)
        if first:
            selected = {
                "status": "selected_for_manual_review",
                "command_head_hash": first.get("command_head_hash"),
                "command_head_class": command_head_class(first.get("command_head_family")),
                "verifier_event_order_hash": first.get("line_offset_hash"),
                "selection_rule": "recovery_tail_first_verifier_hash_only",
                "raw_command_text_emitted": False,
                "raw_tool_output_emitted": False,
            }
    for index, patch in enumerate(patches):
        if not isinstance(patch, dict):
            continue
        segments.append(
            {
                "patch_attempt_index": index,
                "patch_apply_status": str(patch.get("patch_apply_status") or "PATCH_STATUS_UNKNOWN"),
                "verifier_after_patch_status": status,
                "event_order_hashes": {
                    "patch_event_order_hash": patch.get("line_offset_hash"),
                    "verifier_after_patch_order_hashes": [
                        verifier.get("line_offset_hash") for verifier in verifiers[-6:] if isinstance(verifier, dict)
                    ],
                    "next_patch_boundary_order_hash": None,
                    "raw_line_numbers_emitted": False,
                },
                "selected_verifier_identity_candidate": selected
                or {
                    "status": "missing",
                    "command_head_hash": None,
                    "command_head_class": None,
                    "verifier_event_order_hash": None,
                    "selection_rule": "no_recovery_tail_verifier_observed",
                    "raw_command_text_emitted": False,
                    "raw_tool_output_emitted": False,
                },
                "verifier_after_patch_event_count": len(verifiers),
                "segmentation_source": "stage12388_tail_fallback",
            }
        )
    return segments, ["raw_atomic_segmentation_unavailable_tail_fallback_review_required"]


def opaque_label(candidate_id: str, role: str) -> str:
    return stable_id("opaque_policy_label", candidate_id, role)


def policy_candidate_set(candidate_id: str, patch_attempt_index: int) -> dict[str, Any]:
    roles = [
        ("observed_patch_attempt_policy_unproven", None),
        ("hard_negative", "pre_patch_verifier_observation"),
        ("hard_negative", "later_patch_attempt_boundary"),
        ("hard_negative", "context_read_or_search_only"),
        ("hard_negative", "environment_or_setup_action"),
    ]
    return {
        "proposal_id": stable_id("stage12390_policy_candidate_set", candidate_id),
        "patch_attempt_index": patch_attempt_index,
        "review_required": True,
        "policy_gold_admitted": False,
        "selected_policy_label": None,
        "observed_action_order_only": True,
        "opaque_labels": [
            {
                "opaque_label": opaque_label(candidate_id, f"{role}:{hard_negative_role}"),
                "role": role,
                "hard_negative_role": hard_negative_role,
            }
            for role, hard_negative_role in roles
        ],
        "raw_command_text_emitted": False,
        "raw_tool_output_emitted": False,
        "raw_patch_body_emitted": False,
    }


def source_ids(
    review: dict[str, Any],
    recovery: dict[str, Any] | None,
    stage16: dict[str, Any] | None,
    source_hash: str | None,
) -> dict[str, Any]:
    return {
        "source_semantic_review_record_id": review.get("semantic_review_record_id"),
        "source_recovery_record_id": review.get("source_recovery_record_id") or (recovery or {}).get("recovery_record_id"),
        "source_stage12316_id": review.get("source_stage12316_id") or (recovery or {}).get("source_stage12316_id"),
        "source_join_record_id": review.get("source_join_record_id") or (recovery or {}).get("source_join_record_id"),
        "source_transition_local_join_id": (stage16 or {}).get("transition_local_join_id"),
        "task_window_id": review.get("task_window_id") or (recovery or {}).get("task_window_id"),
        "source_file_hash_compat": source_hash,
    }


def blockers_for_candidate(
    review: dict[str, Any],
    segment: dict[str, Any],
    segmentation_blockers: list[str],
    source_row_patch_status: str | None,
) -> list[str]:
    blockers = set(BASE_BLOCKERS)
    blockers.update(str(item) for item in review.get("remaining_blockers") or [])
    blockers.update(segmentation_blockers)
    patch_apply = str(segment.get("patch_apply_status") or "")
    verifier_status = str(segment.get("verifier_after_patch_status") or "")
    if source_row_patch_status == MIXED_PATCH_STATUS:
        blockers.discard("mixed_patch_status_repair_transition_rejected")
        blockers.add("source_row_mixed_patch_status_segmented_into_atomic_attempts")
    if patch_apply not in ATOMIC_PATCH_STATUSES:
        blockers.add("non_atomic_patch_status_rejected")
    if patch_apply == "PATCH_FAILED":
        blockers.add("patch_failed_attempt_not_training_grade")
    if patch_apply == "PATCH_STATUS_UNKNOWN":
        blockers.add("patch_status_unknown_manual_review_required")
    if verifier_status != "VERIFIER_PASS_OBSERVED":
        blockers.add("verifier_after_patch_not_pass_manual_review_required")
    blockers.add("verifier_relevance_semantic_review_required")
    blockers.add("state_delta_semantic_review_required")
    blockers.add("repo_identity_semantic_review_required")
    return sorted(blockers)


def build_candidate(
    review: dict[str, Any],
    recovery: dict[str, Any] | None,
    stage16: dict[str, Any] | None,
    source_hash: str | None,
    segment: dict[str, Any],
    segmentation_blockers: list[str],
) -> dict[str, Any]:
    source_row_patch_status = (
        ((review.get("semantic_reviews") or {}).get("transition_hard_rules") or {}).get("patch_apply_status")
    )
    candidate_id = stable_id(
        "stage12390_patch_attempt",
        review.get("semantic_review_record_id"),
        segment.get("patch_attempt_index"),
        segment.get("event_order_hashes"),
    )
    blockers = blockers_for_candidate(review, segment, segmentation_blockers, source_row_patch_status)
    policy_set = policy_candidate_set(candidate_id, int(segment["patch_attempt_index"]))
    return {
        "stage": STAGE,
        "record_type": "patch_attempt_policy_candidate_review_record",
        "patch_attempt_candidate_id": candidate_id,
        "source_ids": source_ids(review, recovery, stage16, source_hash),
        "source_review_recommendation": review.get("recommendation"),
        "source_review_status_class": review.get("review_status_class"),
        "repo_family": review.get("repo_family"),
        "patch_attempt_index": segment["patch_attempt_index"],
        "patch_apply_status": segment["patch_apply_status"],
        "verifier_after_patch_status": segment["verifier_after_patch_status"],
        "event_order_hashes": segment["event_order_hashes"],
        "selected_verifier_identity_candidate": segment["selected_verifier_identity_candidate"],
        "policy_candidate_set_proposal": policy_set,
        "segmentation": {
            "segmentation_source": segment.get("segmentation_source"),
            "source_row_patch_apply_status": source_row_patch_status,
            "source_row_mixed_status_segmented": source_row_patch_status == MIXED_PATCH_STATUS,
            "atomic_patch_attempt_candidate": segment.get("patch_apply_status") in ATOMIC_PATCH_STATUSES,
            "mixed_patch_status_candidate_emitted": segment.get("patch_apply_status") == MIXED_PATCH_STATUS,
            "verifier_after_patch_event_count": segment.get("verifier_after_patch_event_count"),
        },
        "remaining_blockers": blockers,
        "review_required": True,
        "training_allowed": False,
        "admission": {
            "training_allowed": False,
            "train_support_allowed": False,
            "level3_admitted": False,
            "patch_trace_admitted": False,
            "strict_eval_eligible": False,
            "source_heldout_admissible": False,
            "policy_candidate_set_admitted": False,
            "new_training_row_emitted": False,
        },
        "raw_visibility": {
            "raw_source_path_emitted": False,
            "raw_cwd_path_emitted": False,
            "raw_workspace_path_emitted": False,
            "raw_command_text_emitted": False,
            "raw_tool_output_emitted": False,
            "raw_patch_body_emitted": False,
            "raw_source_text_emitted": False,
        },
    }


def blocked_source_record(
    review: dict[str, Any],
    recovery: dict[str, Any] | None,
    stage16: dict[str, Any] | None,
    source_hash: str | None,
    blockers: list[str],
) -> dict[str, Any]:
    return {
        "stage": STAGE,
        "record_type": "blocked_patch_attempt_source_row",
        "blocked_source_row_id": stable_id("stage12390_blocked_source", review.get("semantic_review_record_id")),
        "source_ids": source_ids(review, recovery, stage16, source_hash),
        "blocked_reasons": sorted(set(blockers)),
        "review_required": True,
        "training_allowed": False,
        "admission": {
            "training_allowed": False,
            "level3_admitted": False,
            "patch_trace_admitted": False,
            "strict_eval_eligible": False,
            "source_heldout_admissible": False,
            "new_training_row_emitted": False,
        },
        "raw_visibility": {
            "raw_source_path_emitted": False,
            "raw_command_text_emitted": False,
            "raw_tool_output_emitted": False,
            "raw_patch_body_emitted": False,
            "raw_source_text_emitted": False,
        },
    }


def write_markdown(summary: dict[str, Any]) -> None:
    lines = [
        "# Stage12390 Patch Attempt Segmenter And Policy Candidate Builder",
        "",
        "Audit-only segmentation of patch attempts into manual-review policy candidate proposals.",
        "",
        f"Source review records: `{summary['source_records']}`",
        f"Patch-attempt candidates: `{summary['patch_attempt_candidates']}`",
        f"Blocked source rows: `{summary['blocked_source_rows']}`",
        f"Training allowed: `{summary['training_allowed']}`",
        "",
        "No Level-3, patch-trace, strict-eval, source-heldout, or training admission is emitted.",
        "Mixed aggregate patch-status rows are accepted only when represented as atomic patch-attempt candidates.",
    ]
    (OUT / "PATCH_ATTEMPT_SEGMENTER_AND_POLICY_CANDIDATE_BUILDER_STAGE12390.md").write_text(
        "\n".join(lines) + "\n",
        encoding="utf-8",
    )


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    review_rows = read_jsonl(STAGE12389_RECORDS)
    source_summary = read_json(STAGE12389_SUMMARY)
    recovery_by_id = index_by(read_jsonl(STAGE12388_RECORDS), "recovery_record_id")
    stage16_by_id = index_by(read_jsonl(STAGE12316_RECORDS), "transition_local_join_id")
    windows_by_id = index_by(read_jsonl(STAGE12260_WINDOWS), "task_window_id")
    raw_sources = source_file_map()

    candidates: list[dict[str, Any]] = []
    blocked_sources: list[dict[str, Any]] = []
    for review in review_rows:
        recovery_id = str(review.get("source_recovery_record_id") or "")
        stage16_id = str(review.get("source_stage12316_id") or "")
        task_window_id = str(review.get("task_window_id") or "")
        recovery = recovery_by_id.get(recovery_id)
        stage16 = stage16_by_id.get(stage16_id)
        window = windows_by_id.get(task_window_id)
        source_hash = source_hash_for(review, recovery, stage16, window)
        raw_path = raw_sources.get(str(source_hash)) if source_hash else None

        segments, blockers = segment_patch_attempts_from_raw(raw_path, window or {})
        if not segments:
            fallback_segments, fallback_blockers = fallback_segments_from_recovery(recovery)
            segments = fallback_segments
            blockers = blockers + fallback_blockers

        if not segments:
            blocked_sources.append(blocked_source_record(review, recovery, stage16, source_hash, blockers))
            continue

        for segment in segments:
            candidates.append(build_candidate(review, recovery, stage16, source_hash, segment, blockers))

    policy_proposals = [
        {
            "stage": STAGE,
            "patch_attempt_candidate_id": row["patch_attempt_candidate_id"],
            "source_review_recommendation": row.get("source_review_recommendation"),
            "source_review_status_class": row.get("source_review_status_class"),
            "source_ids": row["source_ids"],
            "policy_candidate_set_proposal": row["policy_candidate_set_proposal"],
            "review_required": True,
            "training_allowed": False,
        }
        for row in candidates
    ]
    manual_review_packets = [row for row in candidates if row.get("source_review_recommendation") == "needs_manual_review"]
    hard_rejected_audit_candidates = [row for row in candidates if row.get("source_review_recommendation") == "rejected_for_stage12390"]

    patch_status_counts = Counter(str(row["patch_apply_status"]) for row in candidates)
    verifier_status_counts = Counter(str(row["verifier_after_patch_status"]) for row in candidates)
    repo_family_counts = Counter(str(row.get("repo_family")) for row in candidates)
    manual_review_unique_source_records = len({row["source_ids"].get("source_semantic_review_record_id") for row in manual_review_packets})
    hard_rejected_unique_source_records = len({row["source_ids"].get("source_semantic_review_record_id") for row in hard_rejected_audit_candidates})
    blocker_counts: Counter[str] = Counter()
    segmentation_source_counts: Counter[str] = Counter()
    policy_role_counts: Counter[str] = Counter()
    source_recommendation_counts = Counter(str(row.get("source_review_recommendation")) for row in candidates)
    mixed_source_segmented = 0
    for row in candidates:
        blocker_counts.update(row["remaining_blockers"])
        segmentation_source_counts[row["segmentation"]["segmentation_source"] or "missing"] += 1
        if row["segmentation"]["source_row_mixed_status_segmented"]:
            mixed_source_segmented += 1
        for label in row["policy_candidate_set_proposal"]["opaque_labels"]:
            policy_role_counts[label.get("hard_negative_role") or label.get("role") or "missing"] += 1

    non_atomic_candidates = [
        row["patch_attempt_candidate_id"]
        for row in candidates
        if row["patch_apply_status"] == MIXED_PATCH_STATUS
        or not row["segmentation"].get("atomic_patch_attempt_candidate")
    ]
    summary = {
        "stage": STAGE,
        "decision": "audit_only_patch_attempt_candidates_built_for_manual_review_no_training",
        "claim_boundary": (
            "Segmented patch attempts and policy candidate set proposals only. No raw source paths, raw commands, "
            "raw outputs, raw patch bodies, Level-3 admission, patch-trace admission, strict/source-heldout "
            "admission, or training rows."
        ),
        "source_stage": source_summary.get("stage") or "stage12389_transition_candidate_semantic_review",
        "source_records": len(review_rows),
        "patch_attempt_candidates": len(candidates),
        "policy_candidate_set_proposals": len(policy_proposals),
        "manual_review_policy_candidate_packets": len(manual_review_packets),
        "hard_rejected_audit_only_candidates": len(hard_rejected_audit_candidates),
        "source_review_recommendation_counts": dict(source_recommendation_counts),
        "manual_review_unique_source_records": manual_review_unique_source_records,
        "hard_rejected_unique_source_records": hard_rejected_unique_source_records,
        "repo_family_counts": dict(repo_family_counts),
        "blocked_source_rows": len(blocked_sources),
        "training_allowed": False,
        "new_training_rows_emitted": 0,
        "level3_admitted": 0,
        "patch_trace_admitted": 0,
        "strict_eval_eligible": 0,
        "source_heldout_admissible": 0,
        "review_required": True,
        "global_admission_boundary": {
            "training_allowed": False,
            "per_row_training_allowed_required": False,
            "level3_admission_allowed": False,
            "patch_trace_admission_allowed": False,
            "strict_eval_admission_allowed": False,
            "source_heldout_admission_allowed": False,
            "raw_source_path_emission_allowed": False,
            "raw_command_emission_allowed": False,
            "raw_output_emission_allowed": False,
            "raw_patch_body_emission_allowed": False,
        },
        "patch_apply_status_counts": dict(patch_status_counts),
        "verifier_after_patch_status_counts": dict(verifier_status_counts),
        "segmentation_source_counts": dict(segmentation_source_counts),
        "remaining_blocker_counts": dict(blocker_counts),
        "policy_role_counts": dict(policy_role_counts),
        "mixed_source_rows_segmented_candidate_count": mixed_source_segmented,
        "mixed_patch_status_candidates_emitted": patch_status_counts.get(MIXED_PATCH_STATUS, 0),
        "non_atomic_candidate_count": len(non_atomic_candidates),
        "non_atomic_candidate_ids": non_atomic_candidates[:20],
        "guardrail_passed": len(non_atomic_candidates) == 0 and patch_status_counts.get(MIXED_PATCH_STATUS, 0) == 0,
        "manual_review_packet_boundary": {
            "manual_review_packets_come_only_from_stage12389_needs_manual_review": True,
            "hard_rejected_candidates_are_audit_only_not_training_negatives": True
        },
        "next_stage": {
            "purpose": "Manual semantic review of the Stage12389 needs_manual_review patch-attempt packets only; hard-rejected candidates remain audit-only.",
            "training_allowed": False,
            "auto_admission_allowed": False,
            "required_before_any_training": [
                "manual_policy_label_selection",
                "manual_verifier_relevance_review",
                "manual_state_delta_review",
                "manual_repo_identity_review",
                "separate_non_training_artifact_from_any_future_admission_stage",
            ],
        },
    }

    write_jsonl(OUT / "patch_attempt_policy_candidate_records.jsonl", candidates)
    write_jsonl(OUT / "policy_candidate_set_proposals.jsonl", policy_proposals)
    write_jsonl(OUT / "manual_review_policy_candidate_packets.jsonl", manual_review_packets)
    write_jsonl(OUT / "hard_rejected_audit_only_patch_attempt_candidates.jsonl", hard_rejected_audit_candidates)
    write_jsonl(OUT / "blocked_patch_attempt_source_rows.jsonl", blocked_sources)
    write_json(OUT / "patch_attempt_segmenter_and_policy_candidate_builder_summary.json", summary)
    write_markdown(summary)
    write_json(SUMMARY, summary)


if __name__ == "__main__":
    main()
