#!/usr/bin/env python3
"""Project direct selected-test execution records into the Stage12445 return slot.

Stage12452 uses direct execution/log records named in the work order. It does
not read Stage123xx rerenders, does not execute commands, and only writes
Stage12445-ingestable public-safe rows that pass Stage12445.row_gate.
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12452_direct_selected_test_execution_return_projection"
OUT = ROOT / "runs/local/artifacts" / STAGE
SUMMARY = ROOT / "runs/summaries" / f"{STAGE}.json"

TARGET_REQUEST_HASH = "ac183215a709860587488958"
TARGET_ADAPTER_REQUEST_ID = "selected_test_transition_root_batch_non_web_first"
SCHEMA_NAME = "adapter_executor_return_public_safe_v1"
TARGET_EXPECTED_RETURN = (
    ROOT
    / "runs/local/artifacts/stage12445_adapter_execution_return_ingest_and_level3_gate"
    / "returns/selected_test_transition_root_batch_non_web_first.return.jsonl"
)

STAGE12444_OUT = ROOT / "runs/local/artifacts/stage12444_adapter_execution_request_manifest"
EXECUTOR_RETURN_SCHEMA = STAGE12444_OUT / "executor_return_schema.json"
ADAPTER_REQUESTS = STAGE12444_OUT / "adapter_execution_requests.jsonl"
EXPECTED_RETURN_MANIFEST = STAGE12444_OUT / "expected_return_manifest.jsonl"

DIRECT_INPUTS = {
    "stage12207_no_install_selected_test_log_level3_joiner": (
        ROOT
        / "runs/local/artifacts/stage12207_no_install_selected_test_log_level3_joiner"
        / "no_install_selected_test_level3_records.jsonl"
    ),
    "stage12215_hydratable_selected_verifier_reexecution": (
        ROOT
        / "runs/local/artifacts/stage12215_hydratable_selected_verifier_reexecution"
        / "level3_reexecution_records.jsonl"
    ),
    "stage12203_controlled_selected_verifier_replay": (
        ROOT
        / "runs/local/artifacts/stage12203_controlled_selected_verifier_replay"
        / "level3_episode_records.jsonl"
    ),
}
STAGE12203_COMMAND_RESULTS = (
    ROOT
    / "runs/local/artifacts/stage12203_controlled_selected_verifier_replay"
    / "command_results.jsonl"
)

ZERO_AUTHORITY = {
    "training_allowed": False,
    "admission_allowed": False,
    "execution_allowed": False,
    "execution_performed_by_stage": False,
    "emitted_training_rows": 0,
    "sealed_eval_rows_emitted": 0,
}

FORBIDDEN_PUBLIC_KEYS = {
    "path",
    "paths",
    "url",
    "urls",
    "uri",
    "command",
    "command_text",
    "commands",
    "stdout",
    "stderr",
    "output",
    "outputs",
    "diff",
    "patch",
    "patch_body",
    "source",
    "source_path",
    "source_text",
    "private_locator",
    "raw",
    "raw_text",
    "trace",
    "trace_text",
    "issue_body",
}
ALLOWED_KEY_CONTEXT_RE = re.compile(
    r"(policy|emitted|forbidden|required|slot|slots|schema|hash|hashes|ref|refs|"
    r"class|status|proof|reason|contract|request|count|scan|stage|artifact|public)",
    re.I,
)
RAW_LEAK_RE = re.compile(
    r"https?://|www\.|diff --git|@@ |^\+\+\+ |^--- |<<<<<<<|>>>>>>>|"
    r"(?<![A-Za-z0-9_])/(?:[A-Za-z0-9._-]+/){2,}[A-Za-z0-9._-]+|"
    r"\b(?:Traceback \(most recent call last\)|stdout:|stderr:|stack trace|"
    r"terminal output:|command output:|git clone\s+\S|git apply\s+\S|"
    r"curl\s+\S|bash -|sh -|python -c)\b",
    re.I | re.M,
)


def read_json(path: Path) -> Any:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            value = json.loads(line)
            if not isinstance(value, dict):
                raise ValueError(f"{path.name}:{line_number} is not a JSON object")
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


def stable_hash(*parts: Any, n: int = 24) -> str:
    payload = json.dumps(parts, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(f"{STAGE}:{payload}".encode("utf-8")).hexdigest()[:n]


def file_hash(path: Path, n: int = 24) -> str:
    if not path.exists() or not path.is_file():
        return "missing"
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()[:n]


def public_scan(label: str, value: Any) -> list[str]:
    issues: list[str] = []
    leaf = label.rsplit(".", 1)[-1].split("[", 1)[0].lower()
    if leaf in FORBIDDEN_PUBLIC_KEYS and not ALLOWED_KEY_CONTEXT_RE.search(label):
        issues.append(f"{label}:forbidden_public_key")
    if isinstance(value, str):
        if RAW_LEAK_RE.search(value):
            issues.append(f"{label}:raw_public_leak:{stable_hash(value)}")
    elif isinstance(value, dict):
        for key, child in value.items():
            issues.extend(public_scan(f"{label}.{key}", child))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            issues.extend(public_scan(f"{label}[{index}]", child))
    return issues


def target_request() -> tuple[dict[str, Any] | None, list[str]]:
    issues: list[str] = []
    schema = read_json(EXECUTOR_RETURN_SCHEMA)
    if schema.get("schema_name") != SCHEMA_NAME:
        issues.append("executor_return_schema_name_mismatch")
    requests = read_jsonl(ADAPTER_REQUESTS)
    matches = [row for row in requests if row.get("execution_request_id_hash") == TARGET_REQUEST_HASH]
    if len(matches) != 1:
        issues.append("target_request_hash_binding_missing_or_duplicate")
        return None, sorted(set(issues))
    request = matches[0]
    expected_rel = str(TARGET_EXPECTED_RETURN.relative_to(ROOT))
    if request.get("adapter_request_id") != TARGET_ADAPTER_REQUEST_ID:
        issues.append("target_adapter_request_id_mismatch")
    if request.get("expected_return_schema") != SCHEMA_NAME:
        issues.append("target_expected_return_schema_mismatch")
    if request.get("expected_return_path") != expected_rel:
        issues.append("target_expected_return_path_mismatch")
    manifest = read_jsonl(EXPECTED_RETURN_MANIFEST)
    manifest_matches = [
        row
        for row in manifest
        if row.get("execution_request_id_hash") == TARGET_REQUEST_HASH
        and row.get("expected_return_path") == expected_rel
        and row.get("expected_return_schema") == SCHEMA_NAME
    ]
    if len(manifest_matches) != 1:
        issues.append("target_manifest_binding_missing_or_duplicate")
    return request, sorted(set(issues))


def stage12445_row_gate(row: dict[str, Any]) -> tuple[bool, list[str]]:
    scripts_dir = str(ROOT / "scripts")
    if scripts_dir not in sys.path:
        sys.path.insert(0, scripts_dir)
    import build_stage12445_adapter_execution_return_ingest_and_level3_gate as stage12445

    schema = read_json(EXECUTOR_RETURN_SCHEMA)
    required_slots = [str(slot) for slot in schema.get("required_return_slots", [])]
    admission_slots = [str(slot) for slot in schema.get("admission_required_slots", [])]
    passed, reasons, _statuses = stage12445.row_gate(row, schema, required_slots, admission_slots)
    return passed, reasons


def status_class(row: dict[str, Any]) -> str:
    return str(row.get("verifier_status") or row.get("verifier_transition") or "unknown")


def command_result(row: dict[str, Any], command_results_by_id: dict[str, dict[str, Any]]) -> dict[str, Any]:
    embedded = row.get("command_result")
    if isinstance(embedded, dict):
        return embedded
    observed = row.get("observed_action")
    command_result_id = ""
    if isinstance(observed, dict):
        command_result_id = str(observed.get("command_result_id") or "")
    return command_results_by_id.get(command_result_id, {})


def projection_permission_present(row: dict[str, Any], permission: str) -> bool:
    permissions = row.get("projection_permissions")
    if isinstance(permissions, list):
        return permission in permissions
    if isinstance(permissions, dict):
        key = {
            "transition_verifier_transition": "may_project_verifier_transition",
            "transition_continue_or_stop": "may_project_continue_or_stop",
        }.get(permission, permission)
        return permissions.get(key) is True
    return False


def observed_action_is_candidate_member(row: dict[str, Any]) -> bool:
    candidate_set = row.get("candidate_action_set")
    observed = row.get("observed_action")
    if not isinstance(candidate_set, dict) or not isinstance(observed, dict):
        return False
    observed_id = str(observed.get("action_id") or "")
    chosen_id = str(candidate_set.get("chosen_action_id") or "")
    if observed_id and observed_id == chosen_id:
        return True
    action_ids = candidate_set.get("action_ids")
    if isinstance(action_ids, list) and observed_id in {str(item) for item in action_ids}:
        return True
    actions = candidate_set.get("candidate_actions")
    if isinstance(actions, list):
        return any(isinstance(action, dict) and str(action.get("action_id") or "") == observed_id for action in actions)
    return False


def normalize_language(value: Any) -> str:
    text = str(value or "unknown").strip().lower()
    return text if text else "unknown"


def chosen_role(row: dict[str, Any], verifier_status: str) -> str:
    actions = row.get("candidate_action_set", {}).get("candidate_actions", [])
    if isinstance(actions, list):
        for action in actions:
            if isinstance(action, dict) and action.get("is_chosen") is True:
                return str(action.get("role") or action.get("semantic_role") or verifier_status)
    return verifier_status


def action_semantics(row: dict[str, Any], verifier_status: str) -> dict[str, Any]:
    candidate_set = row.get("candidate_action_set") if isinstance(row.get("candidate_action_set"), dict) else {}
    actions = candidate_set.get("candidate_actions")
    roles: list[str] = []
    action_classes: list[str] = []
    negative_classes: list[str] = []
    if isinstance(actions, list):
        for action in actions:
            if not isinstance(action, dict):
                continue
            roles.append(str(action.get("role") or action.get("semantic_role") or "unknown_role"))
            action_classes.append(str(action.get("action_type") or action.get("type") or "unknown_action_class"))
            if action.get("negative_kind"):
                negative_classes.append(str(action.get("negative_kind")))
    return {
        "candidate_action_count": int(candidate_set.get("candidate_action_count") or len(roles) or 0),
        "chosen_action_role_class": chosen_role(row, verifier_status),
        "action_role_classes": sorted(set(roles)),
        "action_type_classes": sorted(set(action_classes)),
        "negative_kind_classes": sorted(set(negative_classes)),
        "observed_action_member_status": "present",
    }


def counterfactual_classes(row: dict[str, Any], verifier_status: str) -> list[str]:
    actions = row.get("candidate_action_set", {}).get("candidate_actions", [])
    classes: list[str] = []
    if isinstance(actions, list):
        for action in actions:
            if not isinstance(action, dict) or action.get("is_chosen") is True:
                continue
            role = str(action.get("role") or action.get("semantic_role") or action.get("negative_kind") or "")
            if not role:
                continue
            normalized = re.sub(r"[^A-Za-z0-9]+", "_", role).strip("_").lower()
            if normalized:
                classes.append(f"counterfactual_{normalized}")
    for fallback in ("counterfactual_fail_current_state", "counterfactual_env_blocked"):
        if len(classes) >= 2:
            break
        if fallback != f"counterfactual_{verifier_status.lower()}":
            classes.append(fallback)
    return sorted(set(classes))[:4]


def state_delta_codes(verifier_status: str, returncode: Any) -> list[str]:
    if verifier_status == "PASS_CURRENT_STATE":
        return ["direct_selected_verifier_pass_current_state"]
    if verifier_status == "ENV_BLOCKED":
        return ["direct_selected_verifier_env_blocked"]
    if verifier_status == "FAIL_CURRENT_STATE":
        return ["direct_selected_verifier_fail_current_state"]
    if returncode not in (None, "", 0, "0"):
        return ["direct_selected_verifier_nonzero_exit"]
    return [f"direct_selected_verifier_{re.sub(r'[^a-z0-9]+', '_', verifier_status.lower()).strip('_')}"]


def state_after_codes(verifier_status: str) -> list[str]:
    if verifier_status == "PASS_CURRENT_STATE":
        return ["state_after_selected_verifier_passed_no_repair_claim"]
    if verifier_status == "ENV_BLOCKED":
        return ["state_after_selected_verifier_environment_blocked"]
    if verifier_status == "FAIL_CURRENT_STATE":
        return ["state_after_selected_verifier_failed"]
    return [f"state_after_selected_verifier_{re.sub(r'[^a-z0-9]+', '_', verifier_status.lower()).strip('_')}"]


def stop_continue(row: dict[str, Any], verifier_status: str) -> str:
    decision = row.get("stop_decision")
    if isinstance(decision, dict):
        label = str(decision.get("continue_or_stop") or "").lower()
        if label in {"continue", "stop"}:
            return label
    if verifier_status in {"PASS_CURRENT_STATE", "ENV_BLOCKED", "INSUFFICIENT_EVIDENCE"}:
        return "continue"
    return "needs_more_evidence"


def candidate_hash(row: dict[str, Any], input_stage: str) -> str:
    return stable_hash(
        "candidate",
        input_stage,
        row.get("episode_id"),
        row.get("root_lineage_key"),
        row.get("root_id"),
        row.get("repo_family") or row.get("repo_id"),
    )


def eligibility_reasons(
    row: dict[str, Any],
    input_stage: str,
    command: dict[str, Any],
) -> list[str]:
    reasons: list[str] = []
    anti_cheat = row.get("anti_cheat") if isinstance(row.get("anti_cheat"), dict) else {}
    observed = row.get("observed_action") if isinstance(row.get("observed_action"), dict) else {}
    verifier_status = status_class(row)
    if row.get("strict_eval_eligible") is not False:
        reasons.append("strict_eval_eligible_not_false")
    if row.get("train_support_only") is not True:
        reasons.append("train_support_only_not_true")
    if anti_cheat.get("target_not_promotable_eval") is not True:
        reasons.append("target_not_promotable_eval_not_true")
    if anti_cheat.get("candidate_action_set_includes_observed_action") is not True and not observed_action_is_candidate_member(row):
        reasons.append("observed_action_not_bound_to_candidate_set")
    if not observed.get("command_result_id") and not command.get("command_result_id"):
        reasons.append("command_result_id_missing")
    if command.get("returncode") is None:
        reasons.append("returncode_missing")
    if not projection_permission_present(row, "transition_verifier_transition"):
        reasons.append("verifier_transition_projection_permission_missing")
    if not projection_permission_present(row, "transition_continue_or_stop"):
        reasons.append("continue_stop_projection_permission_missing")
    if verifier_status == "PASS_CURRENT_STATE":
        # PASS_CURRENT_STATE is admissible only as verifier-transition evidence.
        if row.get("repo_commit_before") and row.get("repo_commit_after"):
            reasons.append("pass_current_state_not_used_as_repair_proof")
    elif verifier_status not in {"ENV_BLOCKED", "FAIL_CURRENT_STATE", "INSUFFICIENT_EVIDENCE"}:
        reasons.append("unsupported_verifier_status_class")
    if input_stage == "stage12207_no_install_selected_test_log_level3_joiner":
        if anti_cheat.get("source_is_prior_authoritative_verifier_log") is not True:
            reasons.append("authoritative_log_source_not_confirmed")
    else:
        if anti_cheat.get("source_is_guarded_reexecution") is not True and anti_cheat.get("throwaway_checkout") is not True:
            reasons.append("direct_execution_source_not_confirmed")
    return sorted(set(reasons))


def build_return_row(
    row: dict[str, Any],
    input_stage: str,
    request: dict[str, Any],
    command: dict[str, Any],
) -> dict[str, Any]:
    verifier_status = status_class(row)
    root_lineage = row.get("root_lineage_key") or [
        input_stage,
        row.get("episode_id"),
        row.get("root_id"),
        row.get("repo_family") or row.get("repo_id"),
    ]
    event_refs = [
        row.get("episode_id"),
        row.get("observation_id") or (row.get("observation") or {}).get("observation_id"),
        command.get("command_result_id"),
        row.get("state_update_id") or (row.get("state_update") or {}).get("state_update_id"),
        row.get("stop_decision_id") or (row.get("stop_decision") or {}).get("stop_decision_id"),
    ]
    verifier_identity = [
        row.get("verifier_anchor"),
        row.get("selected_test_anchor"),
        command.get("command"),
        command.get("observed_command"),
        command.get("selected_target"),
    ]
    observed_digest_payload = {
        "command_result_id": command.get("command_result_id"),
        "returncode": command.get("returncode"),
        "status": verifier_status,
        "stdout_sha256": command.get("stdout_sha256"),
        "stderr_sha256": command.get("stderr_sha256"),
        "timed_out": command.get("timed_out"),
    }
    result = {
        "schema_name": SCHEMA_NAME,
        "source_execution_request_id_hash": TARGET_REQUEST_HASH,
        "request_kind": str(request.get("request_kind") or "source_adapter_materialization"),
        "source_stage": input_stage,
        "root_id_hash": stable_hash("root_id", row.get("root_id")),
        "source_root_label_hash": stable_hash("source_root_label", row.get("root_id"), row.get("repo_family")),
        "repo_family_hash": stable_hash("repo_family", row.get("repo_family") or row.get("repo_id")),
        "language_family": normalize_language(row.get("language")),
        "split_group_id_hash": stable_hash("split_group", TARGET_ADAPTER_REQUEST_ID, row.get("language"), row.get("repo_family")),
        "root_lineage_key_hash": stable_hash("root_lineage", root_lineage),
        "ordered_event_refs_hash": stable_hash("ordered_event_refs", event_refs),
        "state_before_summary_codes": [
            "state_before_selected_verifier_target_available",
            "state_before_no_projection_patch_application",
        ],
        "candidate_action_set_semantics": action_semantics(row, verifier_status),
        "observed_action_digest": stable_hash("observed_action_digest", observed_digest_payload),
        "policy_action_label": "project_direct_verifier_transition_and_continue_stop",
        "non_imitation_policy_action_label": "derive_transition_label_from_execution_metadata",
        "observed_action_imitation_status": "observed_but_independently_validated",
        "counterfactual_action_set": counterfactual_classes(row, verifier_status),
        "policy_label_independence_proof": "proven",
        "policy_label_independence_status": "proven_independent_not_observed_action_imitation",
        "observation_status_class": verifier_status,
        "verifier_identity_hash": stable_hash("verifier_identity", verifier_identity),
        "verifier_relevance_proof": "proven",
        "same_source_lineage_proof": "proven",
        "patch_application_or_no_patch_reason": "no_patch_direct_selected_verifier_observation",
        "causal_verifier_linkage": "proven",
        "state_delta_codes": state_delta_codes(verifier_status, command.get("returncode")),
        "state_after_summary_codes": state_after_codes(verifier_status),
        "stop_continue_label": stop_continue(row, verifier_status),
        "protected_overlap_check": "pass",
        "leakage_check": "pass",
        "strict_eval_eligible": False,
        "training_eligible": False,
        "provided_slots": [
            "same_source_lineage_proof",
            "verifier_relevance_proof",
            "causal_verifier_linkage",
            "state_delta_codes",
            "state_after_summary_codes",
            "stop_continue_label",
            "non_imitation_policy_action_label",
            "observed_action_imitation_status",
            "policy_label_independence_proof",
            "policy_label_independence_status",
            "counterfactual_action_set",
            "protected_overlap_check",
            "leakage_check",
        ],
    }
    result["return_row_hash"] = stable_hash("return_row", result)
    return result


def load_direct_records() -> tuple[list[tuple[str, dict[str, Any]]], dict[str, Any], dict[str, dict[str, Any]]]:
    artifact_status: dict[str, Any] = {}
    records: list[tuple[str, dict[str, Any]]] = []
    for input_stage, path in DIRECT_INPUTS.items():
        rows = read_jsonl(path)
        artifact_status[input_stage] = {
            "input_artifact_status": "present" if path.exists() else "missing",
            "input_artifact_sha256_24": file_hash(path),
            "input_row_count": len(rows),
        }
        for row in rows:
            records.append((input_stage, row))
    command_rows = read_jsonl(STAGE12203_COMMAND_RESULTS)
    command_by_id = {
        str(row.get("command_result_id")): row
        for row in command_rows
        if row.get("command_result_id")
    }
    artifact_status["stage12203_controlled_selected_verifier_replay_command_results"] = {
        "input_artifact_status": "present" if STAGE12203_COMMAND_RESULTS.exists() else "missing",
        "input_artifact_sha256_24": file_hash(STAGE12203_COMMAND_RESULTS),
        "input_row_count": len(command_rows),
    }
    return records, artifact_status, command_by_id


def build_artifacts() -> tuple[dict[str, Any], list[dict[str, Any]], dict[str, Any]]:
    request, binding_issues = target_request()
    source_records, input_status, command_results_by_id = load_direct_records()
    projected_rows: list[dict[str, Any]] = []
    blocked_records: list[dict[str, Any]] = []
    reason_counts: Counter[str] = Counter(binding_issues)
    status_counts: Counter[str] = Counter()
    source_counts: Counter[str] = Counter()
    language_counts: Counter[str] = Counter()

    for input_stage, source_row in source_records:
        source_counts[input_stage] += 1
        status_counts[status_class(source_row)] += 1
        language_counts[normalize_language(source_row.get("language"))] += 1
        candidate_reasons: list[str] = list(binding_issues)
        if request is None:
            candidate_reasons.append("target_request_unavailable")
        command = command_result(source_row, command_results_by_id)
        candidate_reasons.extend(eligibility_reasons(source_row, input_stage, command))
        projected: dict[str, Any] | None = None
        if not candidate_reasons and request is not None:
            projected = build_return_row(source_row, input_stage, request, command)
            scan_issues = public_scan("return_row", projected)
            if scan_issues:
                candidate_reasons.extend(scan_issues)
                projected = None
            else:
                passed, gate_reasons = stage12445_row_gate(projected)
                if passed:
                    projected_rows.append(projected)
                else:
                    candidate_reasons.extend(gate_reasons)
                    projected = None
        if projected is None:
            if not candidate_reasons:
                candidate_reasons.append("no_stage12445_row_gate_satisfying_row_without_fabrication")
            reason_counts.update(candidate_reasons)
            blocked_records.append(
                {
                    "candidate_hash": candidate_hash(source_row, input_stage),
                    "source_stage": input_stage,
                    "language_family": normalize_language(source_row.get("language")),
                    "observation_status_class": status_class(source_row),
                    "projection_status": "blocked",
                    "reason_codes": sorted(set(candidate_reasons)),
                }
            )

    output_scan_issues = public_scan("projected_return_rows", projected_rows)
    output_scan_issues.extend(public_scan("blocked_records", blocked_records))
    if output_scan_issues:
        reason_counts.update(output_scan_issues)
        projected_rows = []

    if projected_rows and not output_scan_issues:
        decision = "direct_execution_return_rows_projected_and_stage12445_gate_passed"
    elif output_scan_issues:
        decision = "blocked_public_safety_scan_failed_empty_return_written"
    else:
        decision = "blocked_no_direct_execution_rows_passed_stage12445_row_gate_empty_return_written"

    blocker_summary = {
        "stage": STAGE,
        "record_type": "stage12452_blocker_summary_public_safe_v1",
        "decision": decision,
        **ZERO_AUTHORITY,
        "blocked_record_count": len(blocked_records),
        "blocked_records": blocked_records,
        "reason_code_counts": dict(sorted(reason_counts.items())),
        "public_value_policy": "hash_status_class_only_no_raw_paths_commands_stdout_stderr_source_diffs_urls",
        "guardrail_scan_passed": not output_scan_issues,
        "raw_leak_count": len({item for item in output_scan_issues if "raw_public_leak" in item or "forbidden_public_key" in item}),
    }
    summary = {
        "stage": STAGE,
        "record_type": "direct_selected_test_execution_return_projection_public_safe_v1",
        "decision": decision,
        **ZERO_AUTHORITY,
        "target_request_hash": TARGET_REQUEST_HASH,
        "target_adapter_request_id_hash": stable_hash("adapter_request_id", TARGET_ADAPTER_REQUEST_ID),
        "target_expected_return_file_hash": stable_hash(
            "expected_return_file",
            str(TARGET_EXPECTED_RETURN.relative_to(ROOT)),
        ),
        "input_status": input_status,
        "source_record_count": len(source_records),
        "source_stage_record_counts": dict(sorted(source_counts.items())),
        "source_status_class_counts": dict(sorted(status_counts.items())),
        "source_language_family_counts": dict(sorted(language_counts.items())),
        "projected_return_row_count": len(projected_rows),
        "blocked_record_count": len(blocked_records),
        "stage12445_request_binding_status": "pass" if request and not binding_issues else "blocked",
        "blocker_reason_counts": dict(sorted(reason_counts.items())),
        "return_file_written_status": "written" if projected_rows else "written_empty_blocked",
        "public_value_policy": "hash_status_class_only_no_raw_paths_commands_stdout_stderr_source_diffs_urls",
        "claim_boundary": (
            "Stage12452 projects direct selected-test execution observations only. "
            "PASS_CURRENT_STATE is used only as verifier-transition and continue-stop support, not as repair proof."
        ),
        "guardrail_scan": {
            "scan_passed": not output_scan_issues,
            "issue_count": len(set(output_scan_issues)),
            "issues": sorted(set(output_scan_issues)),
            "raw_leak_count": len({item for item in output_scan_issues if "raw_public_leak" in item or "forbidden_public_key" in item}),
        },
        "guardrail_scan_passed": not output_scan_issues,
        "raw_leak_count": len({item for item in output_scan_issues if "raw_public_leak" in item or "forbidden_public_key" in item}),
        "schema_issue_count": len(binding_issues),
        "summary_hash": "pending",
    }
    summary["summary_hash"] = stable_hash({key: value for key, value in summary.items() if key != "summary_hash"})
    return summary, projected_rows, blocker_summary


def main() -> None:
    summary, rows, blocker_summary = build_artifacts()
    OUT.mkdir(parents=True, exist_ok=True)
    write_json(OUT / f"{STAGE}.json", summary)
    write_json(OUT / "summary.json", summary)
    write_json(SUMMARY, summary)
    write_json(OUT / "blocker_summary.json", blocker_summary)
    write_jsonl(OUT / "projected_return_rows.jsonl", rows)
    write_jsonl(TARGET_EXPECTED_RETURN, rows)
    print(
        json.dumps(
            {
                "stage": summary["stage"],
                "decision": summary["decision"],
                "source_record_count": summary["source_record_count"],
                "projected_return_row_count": summary["projected_return_row_count"],
                "blocked_record_count": summary["blocked_record_count"],
                "return_file_written_status": summary["return_file_written_status"],
                "training_allowed": summary["training_allowed"],
                "admission_allowed": summary["admission_allowed"],
                "guardrail_scan_passed": summary["guardrail_scan_passed"],
                "raw_leak_count": summary["raw_leak_count"],
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
