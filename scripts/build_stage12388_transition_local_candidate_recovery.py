#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12388_transition_local_candidate_recovery"
OUT = ROOT / "runs/local/artifacts" / STAGE
SUMMARY = ROOT / "runs/summaries" / f"{STAGE}.json"
CODEX_SESSIONS = Path.home() / ".codex" / "sessions"

WORKLIST = (
    ROOT
    / "runs/local/artifacts/stage12387_transition_local_materializer_upgrade_worklist/transition_local_materializer_upgrade_worklist.jsonl"
)
STAGE12316 = (
    ROOT
    / "runs/local/artifacts/stage12316_transition_local_event_joiner/transition_local_event_join_records.jsonl"
)
STAGE12314 = (
    ROOT
    / "runs/local/artifacts/stage12314_session_candidate_repo_and_state_joiner/session_candidate_repo_state_join_records.jsonl"
)
WINDOWS = ROOT / "runs/local/artifacts/stage12260_codex_chat_task_boundary_miner/codex_task_windows.jsonl"
MANIFEST = ROOT / "runs/local/artifacts/stage12258_live_codex_chat_reconstruction_index/per_chat_manifest.jsonl"

MAX_ROWS = 94
GENERIC_REPO_LABELS = {"", "unknown", "clone", "repo", "src", "worktree"}
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


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def stable_id(prefix: str, *parts: Any) -> str:
    payload = json.dumps(parts, sort_keys=True, separators=(",", ":"), default=str)
    return f"{prefix}_{hashlib.sha256(payload.encode('utf-8')).hexdigest()[:20]}"


def stable_hash(value: Any) -> str | None:
    if value in (None, "", [], {}):
        return None
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(f"{STAGE}:{payload}".encode("utf-8")).hexdigest()[:24]


def sha1_text(value: str) -> str:
    return hashlib.sha1(value.encode("utf-8")).hexdigest()


def basename_label(path_value: str | None) -> str | None:
    if not path_value:
        return None
    label = str(path_value).rstrip("/").split("/")[-1]
    return label or None


def command_head(cmd: str) -> str:
    parts = str(cmd or "").strip().split()
    if not parts:
        return ""
    head = parts[0].split("/")[-1]
    if "=" in head and len(parts) > 1:
        head = parts[1].split("/")[-1]
    return head


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


def raw_source_map() -> dict[str, Path]:
    mapping: dict[str, Path] = {}
    if not CODEX_SESSIONS.exists():
        return mapping
    for path in CODEX_SESSIONS.rglob("*.jsonl"):
        if path.is_file():
            mapping[sha1_text(str(path))] = path
    return mapping


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
    if "success. updated" in lower or "successfully applied" in lower:
        return "PATCH_APPLIED"
    if "invalid context" in lower or "failed" in lower or "error" in lower:
        return "PATCH_FAILED"
    return "PATCH_STATUS_UNKNOWN"


def index_by(rows: list[dict[str, Any]], key: str) -> dict[str, dict[str, Any]]:
    return {str(row[key]): row for row in rows if row.get(key)}


def source_manifest_by_hash() -> dict[str, dict[str, Any]]:
    return {str(row.get("source_file_hash_compat")): row for row in read_jsonl(MANIFEST) if row.get("source_file_hash_compat")}


def first_hint(row: dict[str, Any], key: str) -> str | None:
    values = row.get(key)
    if isinstance(values, list) and values:
        first = values[0]
        if isinstance(first, list) and first:
            return str(first[0])
        if isinstance(first, tuple) and first:
            return str(first[0])
        if isinstance(first, str):
            return first
    return None


def recover_repo_identity(stage16: dict[str, Any], join: dict[str, Any], manifest: dict[str, Any] | None) -> dict[str, Any]:
    workspace = first_hint(manifest or {}, "workspace_root_hints_top")
    cwd = first_hint(manifest or {}, "cwd_hints_top")
    raw_label = basename_label(workspace) or basename_label(cwd)
    confidence = "none"
    if raw_label and raw_label not in GENERIC_REPO_LABELS:
        confidence = "basename_hint"
    elif raw_label:
        confidence = "low_confidence_generic_basename"
    return {
        "root_id_candidate": join.get("canonical_root_id") or stage16.get("canonical_root_id"),
        "source_root_label": (stage16.get("source_refs") or {}).get("source_root_label") or join.get("source_root_label"),
        "repo_family_candidate": raw_label,
        "repo_family_confidence": confidence,
        "language_candidate": stage16.get("language_family") or join.get("language_family") or (manifest or {}).get("language_family_hint"),
        "raw_cwd_path_emitted": False,
        "raw_workspace_path_emitted": False,
        "workspace_hint_digest": stable_hash(workspace),
        "cwd_hint_digest": stable_hash(cwd),
    }


def extract_action_context(events: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    context: dict[str, dict[str, Any]] = {}
    for event in events:
        payload = extract_payload(event["obj"])
        call_id = str(payload.get("call_id") or payload.get("id") or "")
        tool_name = str(payload.get("name") or "")
        args = safe_json(payload.get("arguments"))
        args = args if isinstance(args, dict) else {}
        cmd_head = command_head(str(args.get("cmd") or ""))
        if call_id and (tool_name or cmd_head):
            context[call_id] = {
                "tool_name": tool_name,
                "command_head": cmd_head,
                "line_number": event["line_number"],
            }
    return context


def recover_transition_candidates(events: list[dict[str, Any]], start_line: int) -> dict[str, Any]:
    context = extract_action_context(events)
    verifier_events: list[dict[str, Any]] = []
    patch_events: list[dict[str, Any]] = []
    terminal_seen = False
    read_seen = False
    for event in events:
        payload = extract_payload(event["obj"])
        payload_type = str(payload.get("type") or "")
        event_type = str(event["obj"].get("type") or "")
        if payload_type == "task_complete" or event_type == "task_complete":
            terminal_seen = True
        call_id = str(payload.get("call_id") or payload.get("id") or "")
        info = context.get(call_id, {})
        tool_name = str(payload.get("name") or info.get("tool_name") or "")
        head = str(info.get("command_head") or "")
        if head in {"rg", "grep", "find", "sed", "cat", "ls", "jq", "head", "tail", "nl"}:
            read_seen = True
        if "output" not in payload:
            continue
        out = str(payload.get("output") or "")
        status_class, exit_code_class = output_status(out)
        if tool_name == "apply_patch":
            patch_events.append(
                {
                    "line_offset_hash": stable_hash(event["line_number"] - start_line),
                    "patch_apply_status": patch_status(out),
                    "raw_patch_body_emitted": False,
                    "raw_tool_output_emitted": False,
                }
            )
        if head in VERIFY_HEADS:
            verifier_events.append(
                {
                    "line_offset_hash": stable_hash(event["line_number"] - start_line),
                    "command_head_hash": stable_hash(head),
                    "command_head_family": head,
                    "observation_status_class": status_class,
                    "exit_code_class": exit_code_class,
                    "raw_command_text_emitted": False,
                    "raw_tool_output_emitted": False,
                }
            )
    verifier_statuses = [row["observation_status_class"] for row in verifier_events]
    patch_statuses = [row["patch_apply_status"] for row in patch_events]
    if "PATCH_APPLIED" in patch_statuses and "PATCH_FAILED" in patch_statuses:
        patch_apply = "MIXED_PATCH_APPLIED_AND_FAILED"
    elif "PATCH_APPLIED" in patch_statuses:
        patch_apply = "PATCH_APPLIED"
    elif "PATCH_FAILED" in patch_statuses:
        patch_apply = "PATCH_FAILED"
    elif patch_events:
        patch_apply = "PATCH_STATUS_UNKNOWN"
    else:
        patch_apply = "NO_PATCH_OBSERVED"
    if "FAIL_OR_COMMAND_ERROR" in verifier_statuses:
        verifier_status = "VERIFIER_FAILURE_OBSERVED"
    elif "ENV_BLOCKED" in verifier_statuses:
        verifier_status = "VERIFIER_ENV_BLOCKED_OBSERVED"
    elif "TIMEOUT_OR_HUNG" in verifier_statuses:
        verifier_status = "VERIFIER_TIMEOUT_OBSERVED"
    elif "PASS_OR_COMMAND_SUCCESS" in verifier_statuses:
        verifier_status = "VERIFIER_PASS_OBSERVED"
    elif verifier_events:
        verifier_status = "VERIFIER_STATUS_UNKNOWN"
    else:
        verifier_status = "NO_VERIFIER_OBSERVED"
    transition = "REVIEW_REQUIRED"
    if patch_apply == "MIXED_PATCH_APPLIED_AND_FAILED":
        transition = f"MIXED_PATCH_STATUS_WITH_{verifier_status}_REVIEW"
    elif patch_apply == "PATCH_APPLIED" and verifier_status == "VERIFIER_PASS_OBSERVED":
        transition = "PATCH_APPLIED_WITH_VERIFIER_PASS_REVIEW"
    elif patch_apply == "PATCH_APPLIED" and verifier_status == "VERIFIER_FAILURE_OBSERVED":
        transition = "PATCH_APPLIED_WITH_VERIFIER_FAIL_REVIEW"
    elif patch_apply == "NO_PATCH_OBSERVED" and verifier_status.startswith("VERIFIER_"):
        transition = "NO_PATCH_WITH_VERIFIER_OBSERVATION_REVIEW"
    elif patch_apply == "PATCH_FAILED":
        transition = "PATCH_APPLICATION_FAILED_REVIEW"
    state_update = []
    if read_seen:
        state_update.append("SOURCE_OR_CONTEXT_INSPECTED")
    if patch_events:
        state_update.append("PATCH_EVENT_OBSERVED")
    if verifier_events:
        state_update.append("VERIFIER_EVENT_OBSERVED")
    if terminal_seen:
        state_update.append("TERMINAL_SIGNAL_OBSERVED")
    return {
        "command_result_candidate": {
            "verifier_event_count": len(verifier_events),
            "verifier_events_tail": verifier_events[-6:],
            "patch_event_count": len(patch_events),
            "patch_events_tail": patch_events[-4:],
            "raw_command_text_emitted": False,
            "raw_tool_output_emitted": False,
            "raw_patch_body_emitted": False,
        },
        "state_update_candidate": {
            "state_update_codes": sorted(set(state_update)),
            "review_required": True,
        },
        "stop_decision_candidate": {
            "stop_continue_label": "STOP_SIGNAL_OBSERVED" if terminal_seen else "CONTINUE_OR_UNKNOWN",
            "review_required": True,
        },
        "verifier_transition_candidate": {
            "candidate_label": transition,
            "patch_apply_status": patch_apply,
            "verifier_status_class": verifier_status,
            "review_required": True,
            "not_fail_to_pass_proof": True,
        },
    }



def split_blockers(original: list[str], identity: dict[str, Any], transition: dict[str, Any]) -> tuple[list[str], list[str]]:
    resolved: list[str] = []
    remaining = set(original)
    if identity.get("root_id_candidate") and identity.get("language_candidate") and identity.get("repo_family_candidate"):
        resolved.append("repo_identity_candidate_recovered_review_required")
        remaining.add("repo_identity_semantic_review_required")
    command_result = transition.get("command_result_candidate") or {}
    state_update = transition.get("state_update_candidate") or {}
    stop_decision = transition.get("stop_decision_candidate") or {}
    verifier_transition = transition.get("verifier_transition_candidate") or {}
    if command_result.get("verifier_event_count") and "level3_control_contract_missing" in remaining:
        resolved.append("level3_control_contract_missing::command_result_candidate_recovered")
    if state_update.get("state_update_codes") and "state_delta_semantic_review_required" in remaining:
        resolved.append("state_delta_candidate_recovered_review_required")
    if stop_decision.get("stop_continue_label"):
        resolved.append("stop_decision_candidate_recovered_review_required")
    if verifier_transition.get("candidate_label") not in (None, "REVIEW_REQUIRED") and "verifier_identity_or_transition_missing" in remaining:
        remaining.remove("verifier_identity_or_transition_missing")
        resolved.append("verifier_identity_or_transition_missing")
        remaining.add("verifier_transition_semantic_review_required")
    return sorted(remaining), sorted(set(resolved))

def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    worklist_rows = [
        row
        for row in read_jsonl(WORKLIST)
        if row.get("source_name") == "stage12316_transition_local_join"
    ][:MAX_ROWS]
    stage16_by_id = {str(row.get("transition_local_join_id")): row for row in read_jsonl(STAGE12316)}
    join_by_id = index_by(read_jsonl(STAGE12314), "join_record_id")
    windows_by_id = index_by(read_jsonl(WINDOWS), "task_window_id")
    manifests = source_manifest_by_hash()
    raw_map = raw_source_map()

    recovered: list[dict[str, Any]] = []
    blocker_counts: Counter[str] = Counter()
    repo_counts: Counter[str] = Counter()
    transition_counts: Counter[str] = Counter()
    confidence_counts: Counter[str] = Counter()
    for item in worklist_rows:
        refs = item.get("stage12316_refs") if isinstance(item.get("stage12316_refs"), dict) else {}
        join_id = refs.get("source_join_record_id")
        stage16 = stage16_by_id.get(str(item.get("source_row_id"))) or {}
        join = join_by_id.get(str(join_id)) or {}
        task_window_id = stage16.get("task_window_id") or join.get("task_window_id")
        window = windows_by_id.get(str(task_window_id)) or {}
        source_hash = (
            ((stage16.get("source_refs") or {}).get("source_file_hash_compat"))
            or ((join.get("source_refs") or {}).get("source_file_hash_compat"))
            or window.get("source_file_hash_compat")
        )
        manifest = manifests.get(str(source_hash))
        raw_path = raw_map.get(str(source_hash)) if source_hash else None
        blockers = []
        if not stage16:
            blockers.append("stage12316_record_missing")
        if not join:
            blockers.append("stage12314_join_missing")
        if not window:
            blockers.append("task_window_missing")
        if not raw_path:
            blockers.append("raw_session_unavailable")
        identity = recover_repo_identity(stage16, join, manifest)
        if identity.get("repo_family_confidence") != "basename_hint":
            blockers.append("repo_family_low_confidence")
        events = read_raw_window(raw_path, int(window.get("start_line") or 0), int(window.get("end_line") or 0)) if raw_path and window else []
        if not events:
            blockers.append("raw_window_event_recovery_failed")
        transition = recover_transition_candidates(events, int(window.get("start_line") or 0)) if events else {}
        vt = (transition.get("verifier_transition_candidate") or {}).get("candidate_label")
        if vt in (None, "REVIEW_REQUIRED"):
            blockers.append("verifier_transition_candidate_uninformative")
        old_blockers = sorted(set(blockers + item.get("blocker_classes", [])))
        remaining_blockers, resolved_blockers = split_blockers(old_blockers, identity, transition)
        record = {
            "stage": STAGE,
            "recovery_record_id": stable_id("stage12388", item.get("worklist_id"), item.get("source_row_id")),
            "source_worklist_id": item.get("worklist_id"),
            "source_stage12316_id": item.get("source_row_id"),
            "source_join_record_id": join_id,
            "task_window_id": task_window_id,
            "identity_recovery": identity,
            "transition_recovery": transition,
            "review_boundary": {
                "training_allowed": False,
                "level3_admitted": False,
                "patch_trace_admitted": False,
                "strict_eval_eligible": False,
                "source_heldout_admissible": False,
                "semantic_review_required": True,
                "manual_policy_label_review_required": True,
            },
            "raw_visibility": {
                "raw_source_path_emitted": False,
                "raw_cwd_path_emitted": False,
                "raw_command_text_emitted": False,
                "raw_tool_output_emitted": False,
                "raw_patch_body_emitted": False,
                "raw_source_text_emitted": False,
                "raw_session_reopened_internally": bool(raw_path),
            },
            "resolved_blocker_candidates": resolved_blockers,
            "blocked_reasons": remaining_blockers,
        }
        recovered.append(record)
        blocker_counts.update(record["blocked_reasons"])
        repo_counts[identity.get("repo_family_candidate") or "missing"] += 1
        confidence_counts[identity.get("repo_family_confidence") or "missing"] += 1
        transition_counts[vt or "missing"] += 1

    write_jsonl(OUT / "transition_local_candidate_recovery_records.jsonl", recovered)
    summary = {
        "stage": STAGE,
        "decision": "transition_local_candidate_recovery_complete_training_still_blocked",
        "claim_boundary": "Recovered safe candidate identity/command/state/stop fields for review only. Self-repo dominated QC scaffold; no Level-3, patch-trace, strict-eval, scale-progress, or training admission.",
        "training_allowed": False,
        "records": len(recovered),
        "new_training_rows_emitted": 0,
        "level3_admitted": 0,
        "patch_trace_admitted": 0,
        "strict_eval_eligible": 0,
        "source_diversity_claim_allowed": False,
        "scale_progress_claim_allowed": False,
        "self_repo_dominated_qc_scaffold": True,
        "repo_family_candidate_counts": dict(repo_counts),
        "repo_family_confidence_counts": dict(confidence_counts),
        "verifier_transition_candidate_counts": dict(transition_counts),
        "blocked_reason_counts": dict(blocker_counts),
        "next_stage": {
            "stage": "stage12389_transition_candidate_semantic_review",
            "purpose": "Review Stage12388 candidate records for policy-valid chosen action, state delta validity, verifier transition semantics, and admissible Level-3 row construction.",
            "training_allowed": False,
        },
    }
    write_json(OUT / "transition_local_candidate_recovery_summary.json", summary)
    write_json(SUMMARY, summary)
    (OUT / "TRANSITION_LOCAL_CANDIDATE_RECOVERY_STAGE12388.md").write_text(
        "# Stage12388 Transition-Local Candidate Recovery\n\n"
        "This stage recovers safe candidate identity, command-result, state-update, stop-decision, and verifier-transition fields for review only.\n\n"
        f"Records: {len(recovered)}\n\n"
        f"Verifier transition candidates: `{json.dumps(dict(transition_counts), sort_keys=True)}`\n\n"
        "No rows are admitted for training. Manual semantic review remains required before Level-3 construction.\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
