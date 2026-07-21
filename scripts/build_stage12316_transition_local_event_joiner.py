#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12316_transition_local_event_joiner"
OUT = ROOT / "runs/local/artifacts" / STAGE
SUMMARY = ROOT / "runs/summaries" / f"{STAGE}.json"
CODEX_SESSIONS = Path("/home/peyton/.codex/sessions")

JOIN_RECORDS = (
    ROOT
    / "runs/local/artifacts/stage12314_session_candidate_repo_and_state_joiner"
    / "session_candidate_repo_state_join_records.jsonl"
)
WINDOWS = (
    ROOT
    / "runs/local/artifacts/stage12260_codex_chat_task_boundary_miner"
    / "codex_task_windows.jsonl"
)

MAX_RECORDS = 100


def sha1_text(value: str) -> str:
    return hashlib.sha1(value.encode("utf-8")).hexdigest()


def stable_id(prefix: str, *parts: Any) -> str:
    payload = json.dumps(parts, sort_keys=True, separators=(",", ":"), default=str)
    return f"{prefix}_{hashlib.sha256(payload.encode('utf-8')).hexdigest()[:20]}"


def stable_hash(value: Any) -> str | None:
    if value in (None, "", [], {}):
        return None
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(f"{STAGE}:{payload}".encode("utf-8")).hexdigest()[:24]


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")


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


def command_head(cmd: str) -> str:
    parts = str(cmd or "").strip().split()
    return parts[0] if parts else ""


def command_family(head: str, tool_name: str = "") -> str:
    head = (head or "").lower()
    if tool_name == "apply_patch":
        return "EDIT_PATCH"
    if head in {"rg", "grep", "find", "fd", "ls", "cat", "sed", "head", "tail", "jq", "wc", "nl"}:
        return "READ_OR_SEARCH"
    if head in {"pytest", "cargo", "npm", "pnpm", "yarn", "node", "npx", "make", "cmake", "ctest", "go", "python", "python3", "bash"}:
        return "RUN_OR_VERIFY"
    if head == "git":
        return "VERSION_CONTROL"
    if head in {"pip", "uv", "conda", "apt", "brew"}:
        return "ENVIRONMENT_SETUP"
    return "OTHER_ACTION"


def classify_output(text: str) -> tuple[str, int | None]:
    lower = text.lower()
    exit_code = None
    match = re.search(r"(?:exit code|process exited with code)\s*:?\s*(-?\d+)", lower)
    if match:
        try:
            exit_code = int(match.group(1))
        except ValueError:
            exit_code = None
    if "bwrap:" in lower or "operation not permitted" in lower or "network is unreachable" in lower:
        return "ENV_BLOCKED", exit_code
    if "timed out" in lower or "timeout" in lower:
        return "TIMEOUT_OR_HUNG", exit_code
    if exit_code == 0:
        return "PASS_OR_COMMAND_SUCCESS", exit_code
    if exit_code is not None and exit_code != 0:
        return "FAIL_OR_COMMAND_ERROR", exit_code
    if "failed" in lower or "error" in lower or "traceback" in lower:
        return "FAIL_OR_COMMAND_ERROR", exit_code
    if "success" in lower or "passed" in lower:
        return "PASS_OR_COMMAND_SUCCESS", exit_code
    return "UNKNOWN_OUTPUT_STATUS", exit_code


def classify_patch_output(text: str) -> str:
    lower = text.lower()
    if "success. updated" in lower or "successfully applied" in lower:
        return "PATCH_APPLIED"
    if "error" in lower or "failed" in lower or "invalid context" in lower:
        return "PATCH_FAILED"
    return "PATCH_STATUS_UNKNOWN"


def extract_payload(obj: dict[str, Any]) -> dict[str, Any]:
    payload = obj.get("payload")
    return payload if isinstance(payload, dict) else {}


def raw_events_for_window(path: Path, start_line: int, end_line: int) -> list[dict[str, Any]]:
    events = []
    try:
        with path.open("rb") as handle:
            for line_no, raw_line in enumerate(handle, 1):
                if line_no < start_line:
                    continue
                if line_no > end_line:
                    break
                try:
                    obj = json.loads(raw_line.decode("utf-8", errors="ignore"))
                except Exception:
                    continue
                if isinstance(obj, dict):
                    events.append({"line_number": line_no, "obj": obj})
    except Exception:
        return []
    return events


def summarize_window(path: Path, window: dict[str, Any]) -> dict[str, Any]:
    events = raw_events_for_window(path, int(window["start_line"]), int(window["end_line"]))
    call_context_by_id: dict[str, dict[str, str]] = {}
    for event in events:
        payload = extract_payload(event["obj"])
        tool_name = str(payload.get("name") or "")
        call_id = str(payload.get("call_id") or payload.get("id") or "")
        args = safe_json(payload.get("arguments"))
        args = args if isinstance(args, dict) else {}
        head = command_head(str(args.get("cmd") or ""))
        if call_id and (tool_name or head):
            family = command_family(head, tool_name)
            call_context_by_id[call_id] = {
                "tool_name": tool_name,
                "command_head": head,
                "family": family,
            }

    action_counts: Counter[str] = Counter()
    output_status_counts: Counter[str] = Counter()
    patch_status_counts: Counter[str] = Counter()
    verifier_status_sequence = []
    patch_line_numbers = []
    verifier_line_numbers = []
    task_complete_seen = False
    read_or_search_seen = False

    for event in events:
        payload = extract_payload(event["obj"])
        event_type = str(event["obj"].get("type") or "")
        payload_type = str(payload.get("type") or "")
        tool_name = str(payload.get("name") or "")
        call_id = str(payload.get("call_id") or payload.get("id") or "")
        args = safe_json(payload.get("arguments"))
        args = args if isinstance(args, dict) else {}
        head = command_head(str(args.get("cmd") or ""))
        call_context = call_context_by_id.get(call_id) if call_id else None
        if call_context and not tool_name:
            tool_name = call_context.get("tool_name") or tool_name
        if call_context and not head:
            head = call_context.get("command_head") or head
        family = (call_context or {}).get("family") or command_family(head, tool_name)
        has_output = "output" in payload
        if payload_type == "task_complete" or event_type == "task_complete":
            task_complete_seen = True
        if tool_name or head:
            action_counts[family] += 1
            if family == "READ_OR_SEARCH":
                read_or_search_seen = True
            if family == "EDIT_PATCH":
                patch_line_numbers.append(event["line_number"])
        if has_output:
            output_text = str(payload.get("output") or "")
            status, exit_code = classify_output(output_text)
            output_status_counts[status] += 1
            if family == "EDIT_PATCH":
                patch_status_counts[classify_patch_output(output_text)] += 1
            if family == "RUN_OR_VERIFY":
                verifier_line_numbers.append(event["line_number"])
                verifier_status_sequence.append(
                    {
                        "line_offset_hash": stable_hash(event["line_number"] - int(window["start_line"])),
                        "command_head_hash": stable_hash(head),
                        "verifier_family": "RUN_OR_VERIFY",
                        "observation_status_class": status,
                        "exit_code_class": "ZERO" if exit_code == 0 else ("NONZERO" if exit_code is not None else "UNKNOWN"),
                    }
                )

    patch_before_verifier = bool(
        patch_line_numbers
        and verifier_line_numbers
        and min(patch_line_numbers) < max(verifier_line_numbers)
    )
    state_codes = []
    if read_or_search_seen:
        state_codes.append("SOURCE_OR_CONTEXT_INSPECTED")
    if patch_line_numbers:
        state_codes.append("PATCH_REF_OBSERVED")
    if verifier_line_numbers:
        state_codes.append("VERIFIER_OBSERVED")
    if patch_before_verifier:
        state_codes.append("PATCH_BEFORE_VERIFIER_ORDER_OBSERVED")
    if task_complete_seen:
        state_codes.append("TERMINAL_TASK_COMPLETE_SIGNAL_OBSERVED")

    patch_apply_status = "NO_PATCH_OBSERVED"
    if patch_status_counts:
        if patch_status_counts["PATCH_APPLIED"]:
            patch_apply_status = "PATCH_APPLIED"
        elif patch_status_counts["PATCH_FAILED"]:
            patch_apply_status = "PATCH_FAILED"
        else:
            patch_apply_status = "PATCH_STATUS_UNKNOWN"

    stop_continue = "STOP_SIGNAL_OBSERVED" if task_complete_seen else "CONTINUE_OR_UNKNOWN"
    verifier_status = "NO_VERIFIER_OBSERVED"
    if verifier_status_sequence:
        if any(v["observation_status_class"] == "FAIL_OR_COMMAND_ERROR" for v in verifier_status_sequence):
            verifier_status = "VERIFIER_FAILURE_OBSERVED"
        elif any(v["observation_status_class"] == "ENV_BLOCKED" for v in verifier_status_sequence):
            verifier_status = "VERIFIER_ENV_BLOCKED_OBSERVED"
        elif any(v["observation_status_class"] == "TIMEOUT_OR_HUNG" for v in verifier_status_sequence):
            verifier_status = "VERIFIER_TIMEOUT_OBSERVED"
        elif any(v["observation_status_class"] == "PASS_OR_COMMAND_SUCCESS" for v in verifier_status_sequence):
            verifier_status = "VERIFIER_PASS_OBSERVED"
        else:
            verifier_status = "VERIFIER_STATUS_UNKNOWN"

    if patch_apply_status == "PATCH_APPLIED" and verifier_status == "VERIFIER_PASS_OBSERVED":
        rule_id = "RULE_PATCH_APPLIED_THEN_VERIFIER_PASS"
    elif patch_apply_status == "PATCH_APPLIED" and verifier_status == "VERIFIER_FAILURE_OBSERVED":
        rule_id = "RULE_PATCH_APPLIED_THEN_VERIFIER_FAIL"
    elif patch_apply_status == "NO_PATCH_OBSERVED" and verifier_status.startswith("VERIFIER_"):
        rule_id = "RULE_NO_PATCH_VERIFIER_OBSERVATION"
    elif patch_apply_status == "PATCH_FAILED":
        rule_id = "RULE_PATCH_APPLICATION_FAILED"
    else:
        rule_id = None

    transition_key = None
    if rule_id:
        transition_key = stable_id(
            "transition_function",
            rule_id,
            sorted(state_codes),
            verifier_status,
            patch_apply_status,
            stop_continue,
        )

    return {
        "event_count_internal": len(events),
        "action_family_counts": dict(action_counts),
        "output_status_counts": dict(output_status_counts),
        "patch_status_counts": dict(patch_status_counts),
        "state_before_summary_codes": sorted(set(state_codes)),
        "patch_apply_status": patch_apply_status,
        "verifier_status_class": verifier_status,
        "verifier_observation_sequence": verifier_status_sequence[-6:],
        "state_delta_codes": [
            code
            for code, present in [
                ("PATCH_THEN_VERIFIER_OBSERVED", patch_before_verifier),
                ("TERMINAL_SIGNAL_AFTER_WINDOW", task_complete_seen),
            ]
            if present
        ],
        "stop_continue_label": stop_continue,
        "semantic_rule_id": rule_id,
        "transition_function_key": transition_key,
        "raw_text_emitted": False,
        "raw_command_text_emitted": False,
        "raw_tool_output_emitted": False,
        "raw_patch_body_emitted": False,
    }


def candidate_actions_from_counts(action_counts: dict[str, int]) -> list[dict[str, Any]]:
    canonical = ["READ_OR_SEARCH", "RUN_OR_VERIFY", "EDIT_PATCH", "VERSION_CONTROL", "ENVIRONMENT_SETUP", "OTHER_ACTION"]
    # Keep the candidate set neutral. Observed counts are audit-only and emitted outside model-visible candidates.
    return [{"action_type": action} for action in canonical]


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    join_records = read_jsonl(JOIN_RECORDS)[:MAX_RECORDS]
    windows = {row["task_window_id"]: row for row in read_jsonl(WINDOWS)}
    source_map = source_file_map()

    records: list[dict[str, Any]] = []
    for join in join_records:
        task_window_id = join.get("task_window_id")
        source_hash = ((join.get("source_refs") or {}).get("source_file_hash_compat"))
        window = windows.get(str(task_window_id), {})
        raw_path = source_map.get(str(source_hash)) if source_hash else None
        blockers = []
        if not raw_path:
            blockers.append("raw_source_session_unavailable_for_internal_semantic_extraction")
        if not window:
            blockers.append("task_window_missing")

        semantic = summarize_window(raw_path, window) if raw_path and window else {}
        if not semantic.get("semantic_rule_id"):
            blockers.append("semantic_rule_id_not_deterministically_assignable")
        if not semantic.get("transition_function_key"):
            blockers.append("transition_function_key_not_deterministically_assignable")
        if semantic.get("verifier_status_class") in {None, "NO_VERIFIER_OBSERVED", "VERIFIER_STATUS_UNKNOWN"}:
            blockers.append("verifier_status_not_training_grade")
        if semantic.get("patch_apply_status") in {None, "PATCH_STATUS_UNKNOWN"}:
            blockers.append("patch_apply_status_not_training_grade")
        # Observed actions are facts for analysis; they are not gold next-action labels.
        blockers.append("chosen_action_policy_label_not_admitted_from_observed_order")
        blockers.append("state_delta_needs_semantic_review_before_training")
        blockers.append("repo_family_still_not_semantically_recovered")

        action_counts = semantic.get("action_family_counts") or {}
        record = {
            "stage": STAGE,
            "record_type": "transition_local_event_join_record",
            "transition_local_join_id": stable_id("stage12316", join.get("join_record_id"), task_window_id),
            "source_join_record_id": join.get("join_record_id"),
            "candidate_id": join.get("candidate_id"),
            "task_window_id": task_window_id,
            "canonical_root_id": join.get("canonical_root_id"),
            "language_family": join.get("language_family"),
            "source_refs": {
                "source_file_hash_compat": source_hash,
                "source_root_label": join.get("source_root_label"),
                "raw_source_reopened_internally": bool(raw_path),
                "source_path_emitted": False,
                "raw_text_emitted": False,
                "raw_command_text_emitted": False,
                "raw_tool_output_emitted": False,
                "raw_patch_body_emitted": False,
            },
            "state_before_summary_codes": semantic.get("state_before_summary_codes") or [],
            "candidate_action_set": {
                "actions": candidate_actions_from_counts(action_counts),
                "model_visible_policy_label": False,
                "raw_command_text_emitted": False,
                "raw_tool_output_emitted": False,
                "raw_patch_body_emitted": False,
            },
            "candidate_action_audit_only": {
                "observed_action_family_counts": action_counts,
                "model_visible": False,
            },
            "chosen_action": {
                "status": "observed_action_sequence_only_not_policy_gold",
                "model_visible": False,
            },
            "observation": {
                "verifier_status_class": semantic.get("verifier_status_class"),
                "patch_apply_status": semantic.get("patch_apply_status"),
                "output_status_counts": semantic.get("output_status_counts") or {},
                "verifier_observation_sequence": semantic.get("verifier_observation_sequence") or [],
            },
            "state_delta_codes": semantic.get("state_delta_codes") or [],
            "stop_continue_label": semantic.get("stop_continue_label"),
            "semantic_rule_id": semantic.get("semantic_rule_id"),
            "transition_function_key": semantic.get("transition_function_key"),
            "internal_semantic_extraction": {
                "raw_was_inspected": bool(raw_path),
                "raw_was_emitted": False,
                "event_count_internal": semantic.get("event_count_internal") or 0,
            },
            "admission": {
                "training_allowed": False,
                "level3_admitted": False,
                "patch_trace_admitted": False,
                "strict_eval_eligible": False,
                "source_heldout_admissible": False,
                "reason": "semantic classes are useful but observed action/order is not a policy gold label and state/repo proof remains incomplete",
            },
            "blocked_reasons": sorted(set(blockers)),
        }
        records.append(record)

    write_jsonl(OUT / "transition_local_event_join_records.jsonl", records)

    blocker_counts: Counter[str] = Counter()
    rule_counts: Counter[str] = Counter()
    verifier_counts: Counter[str] = Counter()
    patch_counts: Counter[str] = Counter()
    action_nonzero: Counter[str] = Counter()
    for record in records:
        blocker_counts.update(record.get("blocked_reasons") or [])
        rule_counts[record.get("semantic_rule_id") or "MISSING"] += 1
        verifier_counts[(record.get("observation") or {}).get("verifier_status_class") or "MISSING"] += 1
        patch_counts[(record.get("observation") or {}).get("patch_apply_status") or "MISSING"] += 1
        for action in ((record.get("candidate_action_set") or {}).get("actions") or []):
            if action.get("observed_in_window"):
                action_nonzero[action.get("action_type") or "unknown"] += 1

    train_grade = [
        record
        for record in records
        if record.get("semantic_rule_id")
        and record.get("transition_function_key")
        and "verifier_status_not_training_grade" not in (record.get("blocked_reasons") or [])
    ]
    summary = {
        "stage": STAGE,
        "decision": "transition_local_semantic_classes_extracted_training_still_blocked",
        "claim_boundary": "Internal raw session inspection produced safe semantic classes only. No raw text/commands/output/patch body emitted and no training/eval admission.",
        "training_allowed": False,
        "records": len(records),
        "training_rows_emitted": 0,
        "level3_admitted": 0,
        "patch_trace_admitted": 0,
        "train_grade_after_policy_label_review": 0,
        "semantic_rule_candidate_records": len(train_grade),
        "verifier_status_counts": dict(verifier_counts),
        "patch_apply_status_counts": dict(patch_counts),
        "semantic_rule_counts": dict(rule_counts),
        "observed_action_family_nonzero_counts": dict(action_nonzero),
        "blocked_reason_counts": dict(blocker_counts),
        "next_stage": {
            "stage": "stage12318_policy_label_and_state_delta_review",
            "purpose": "Review semantic candidates for genuine policy labels, state delta validity, repo-family recovery, and leakage-safe transition-function keys.",
            "training_allowed": False,
        },
    }
    (OUT / "transition_local_event_join_summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (OUT / "TRANSITION_LOCAL_EVENT_JOINER_STAGE12316.md").write_text(
        "# Stage12316 Transition-Local Event Joiner\n\n"
        "This stage internally reopens raw Codex session JSONL files by source hash and emits only safe semantic classes.\n\n"
        "It still admits zero rows because observed tool order is not a policy gold label, repo family remains unrecovered, and state deltas require semantic review.\n",
        encoding="utf-8",
    )
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
