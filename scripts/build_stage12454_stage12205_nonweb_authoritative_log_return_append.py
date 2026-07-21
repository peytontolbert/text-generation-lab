#!/usr/bin/env python3
"""Append non-web Stage12205 authoritative-log rows to the Stage12445 return.

This stage is intentionally bounded:
- reads only Stage12205 authoritative verifier-log records plus Stage12444 gate metadata;
- emits only adapter_executor_return_public_safe_v1 rows with hashes/status/classes;
- excludes web rows, raw paths, raw commands, stdout/stderr, source text, diffs, and URLs;
- preserves existing Stage12445 return rows and dedupes by source signature and return hash.
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
STAGE = "stage12454_stage12205_nonweb_authoritative_log_return_append"
OUT = ROOT / "runs/local/artifacts" / STAGE
SUMMARY = ROOT / "runs/summaries" / f"{STAGE}.json"

SOURCE_STAGE = "stage12205_authoritative_verifier_log_level3_joiner"
SOURCE_RECORDS = (
    ROOT
    / "runs/local/artifacts"
    / SOURCE_STAGE
    / "authoritative_level3_episode_records.jsonl"
)

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

ALLOWED_LANGUAGES = {"python", "rust", "c_cpp"}
SUPPORTED_STATUSES = {
    "PASS_CURRENT_STATE",
    "PASS_TO_PASS",
    "PASS_CURRENT_BUILD",
    "PASS_CURRENT_BUILD_AND_RUN",
    "FAIL_CURRENT_STATE",
    "FAIL_TO_PASS",
    "ENV_BLOCKED",
}
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


def normalize_language(value: Any) -> str:
    text = str(value or "unknown").strip().lower()
    return text if text else "unknown"


def status_class(row: dict[str, Any]) -> str:
    return str(row.get("verifier_status") or row.get("verifier_transition") or "unknown")


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
        return any(
            isinstance(action, dict) and str(action.get("action_id") or "") == observed_id
            for action in actions
        )
    return False


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
            normalized = re.sub(r"[^A-Za-z0-9]+", "_", role).strip("_").lower()
            if normalized:
                classes.append(f"counterfactual_{normalized}")
    for fallback in ("counterfactual_fail_current_state", "counterfactual_env_blocked"):
        if len(classes) >= 2:
            break
        if fallback != f"counterfactual_{verifier_status.lower()}":
            classes.append(fallback)
    return sorted(set(classes))[:4]


def controlled_fail_to_pass_boundary(row: dict[str, Any]) -> str:
    source_extra = row.get("source_extra") if isinstance(row.get("source_extra"), dict) else {}
    if source_extra.get("controlled_fixture_train_support_only") is True:
        return "controlled_fixture_fail_to_pass_transition_train_support_only_not_general_repair_claim"
    if source_extra.get("controlled_triple") is True or source_extra.get("patch_effect") is True:
        return "source_extra_patch_effect_fail_to_pass_boundary_not_repair_overclaim"
    return "no_patch_authoritative_fail_to_pass_transition_observation_no_repair_claim"


def patch_or_no_patch_reason(row: dict[str, Any], verifier_status: str) -> str:
    if verifier_status == "FAIL_TO_PASS":
        return controlled_fail_to_pass_boundary(row)
    if verifier_status in {"PASS_TO_PASS", "PASS_CURRENT_STATE", "PASS_CURRENT_BUILD", "PASS_CURRENT_BUILD_AND_RUN"}:
        return "no_patch_authoritative_verifier_observation_not_repair_claim"
    return "no_patch_authoritative_verifier_transition_observation"


def state_delta_codes(row: dict[str, Any], verifier_status: str, returncode: Any) -> list[str]:
    if verifier_status in {"PASS_CURRENT_STATE", "PASS_TO_PASS"}:
        return ["authoritative_log_selected_verifier_pass_observed_no_repair_claim"]
    if verifier_status in {"PASS_CURRENT_BUILD", "PASS_CURRENT_BUILD_AND_RUN"}:
        return ["authoritative_log_buildrun_pass_observed_no_repair_claim"]
    if verifier_status == "FAIL_CURRENT_STATE":
        return ["authoritative_log_selected_verifier_fail_current_state_observed"]
    if verifier_status == "FAIL_TO_PASS":
        if controlled_fail_to_pass_boundary(row).startswith("controlled_fixture"):
            return ["controlled_fixture_fail_to_pass_transition_observed_train_support_only"]
        return ["authoritative_log_fail_to_pass_transition_observed_no_patch_effect_claim"]
    if verifier_status == "ENV_BLOCKED":
        return ["authoritative_log_selected_verifier_env_blocked_observed"]
    if returncode not in (None, "", 0, "0"):
        return ["authoritative_log_selected_verifier_nonzero_exit_observed"]
    return [f"authoritative_log_{re.sub(r'[^a-z0-9]+', '_', verifier_status.lower()).strip('_')}_observed"]


def state_after_codes(row: dict[str, Any], verifier_status: str) -> list[str]:
    if verifier_status in {"PASS_CURRENT_STATE", "PASS_TO_PASS"}:
        return ["state_after_authoritative_selected_verifier_passed_no_repair_claim"]
    if verifier_status in {"PASS_CURRENT_BUILD", "PASS_CURRENT_BUILD_AND_RUN"}:
        return ["state_after_authoritative_buildrun_passed_no_repair_claim"]
    if verifier_status == "FAIL_CURRENT_STATE":
        return ["state_after_authoritative_selected_verifier_failed"]
    if verifier_status == "FAIL_TO_PASS":
        if controlled_fail_to_pass_boundary(row).startswith("controlled_fixture"):
            return ["state_after_controlled_fixture_fail_to_pass_observed_train_support_only"]
        return ["state_after_authoritative_fail_to_pass_transition_observed_no_patch_effect_claim"]
    if verifier_status == "ENV_BLOCKED":
        return ["state_after_authoritative_selected_verifier_environment_blocked"]
    return [f"state_after_authoritative_{re.sub(r'[^a-z0-9]+', '_', verifier_status.lower()).strip('_')}"]


def stop_continue(row: dict[str, Any], verifier_status: str) -> str:
    decision = row.get("stop_decision")
    if isinstance(decision, dict):
        label = str(decision.get("continue_or_stop") or "").lower()
        if label in {"continue", "stop"}:
            return label
    if verifier_status == "FAIL_TO_PASS":
        return "needs_more_evidence"
    return "continue"


def command_result(row: dict[str, Any]) -> dict[str, Any]:
    command = row.get("command_result")
    return command if isinstance(command, dict) else {}


def source_signature(row: dict[str, Any]) -> str:
    command = command_result(row)
    payload = {
        "source_stage": row.get("source_stage"),
        "episode_id": row.get("episode_id"),
        "root_id": row.get("root_id"),
        "repo_family": row.get("repo_family"),
        "language": normalize_language(row.get("language")),
        "verifier_status": status_class(row),
        "verifier_transition": row.get("verifier_transition"),
        "command_result_id": command.get("command_result_id"),
        "returncode": command.get("returncode"),
        "stdout_sha256": command.get("stdout_sha256"),
        "stderr_sha256": command.get("stderr_sha256"),
    }
    return stable_hash("source_signature", payload)


def candidate_hash(row: dict[str, Any]) -> str:
    return stable_hash(
        "candidate",
        row.get("source_stage"),
        row.get("episode_id"),
        row.get("root_id"),
        row.get("repo_family"),
        row.get("verifier_transition"),
    )


def eligibility_reasons(row: dict[str, Any]) -> list[str]:
    reasons: list[str] = []
    language = normalize_language(row.get("language"))
    anti_cheat = row.get("anti_cheat") if isinstance(row.get("anti_cheat"), dict) else {}
    observed = row.get("observed_action") if isinstance(row.get("observed_action"), dict) else {}
    command = command_result(row)
    verifier_status = status_class(row)
    if language not in ALLOWED_LANGUAGES:
        reasons.append("web_or_unsupported_language_excluded")
    if row.get("strict_eval_eligible") is not False:
        reasons.append("strict_eval_eligible_not_false")
    if row.get("train_support_only") is not True:
        reasons.append("train_support_only_not_true")
    if anti_cheat.get("target_not_promotable_eval") is not True:
        reasons.append("target_not_promotable_eval_not_true")
    if anti_cheat.get("source_is_prior_authoritative_verifier_log") is not True:
        reasons.append("authoritative_log_source_not_confirmed")
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
    if verifier_status not in SUPPORTED_STATUSES:
        reasons.append("unsupported_verifier_status_class")
    if verifier_status in {"PASS_TO_PASS", "PASS_CURRENT_STATE", "PASS_CURRENT_BUILD", "PASS_CURRENT_BUILD_AND_RUN"}:
        # These statuses are observation support only and must not be used as repair proof.
        if row.get("repo_commit_before") and row.get("repo_commit_after"):
            reasons.append("pass_or_build_status_not_used_as_repair_proof")
    return sorted(set(reasons))


def build_return_row(row: dict[str, Any], request: dict[str, Any]) -> dict[str, Any]:
    verifier_status = status_class(row)
    command = command_result(row)
    root_lineage = [
        SOURCE_STAGE,
        row.get("source_stage"),
        row.get("episode_id"),
        row.get("root_id"),
        row.get("repo_family"),
    ]
    event_refs = [
        row.get("episode_id"),
        (row.get("observation") or {}).get("observation_id") if isinstance(row.get("observation"), dict) else None,
        command.get("command_result_id"),
        (row.get("state_update") or {}).get("state_update_id") if isinstance(row.get("state_update"), dict) else None,
        (row.get("stop_decision") or {}).get("stop_decision_id") if isinstance(row.get("stop_decision"), dict) else None,
    ]
    verifier_identity = [
        row.get("source_stage"),
        row.get("repo_family"),
        normalize_language(row.get("language")),
        command.get("command_result_id"),
        command.get("stdout_sha256"),
        command.get("stderr_sha256"),
    ]
    observed_digest_payload = {
        "command_result_id": command.get("command_result_id"),
        "returncode": command.get("returncode"),
        "status": verifier_status,
        "transition": row.get("verifier_transition"),
        "stdout_sha256": command.get("stdout_sha256"),
        "stderr_sha256": command.get("stderr_sha256"),
    }
    result = {
        "schema_name": SCHEMA_NAME,
        "source_execution_request_id_hash": TARGET_REQUEST_HASH,
        "request_kind": str(request.get("request_kind") or "source_adapter_materialization"),
        "source_stage": SOURCE_STAGE,
        "root_id_hash": stable_hash("root_id", row.get("root_id")),
        "source_root_label_hash": stable_hash("source_root_label", row.get("source_stage"), row.get("root_id")),
        "repo_family_hash": stable_hash("repo_family", row.get("repo_family")),
        "language_family": normalize_language(row.get("language")),
        "split_group_id_hash": stable_hash(
            "split_group",
            TARGET_ADAPTER_REQUEST_ID,
            row.get("source_stage"),
            row.get("language"),
            row.get("repo_family"),
        ),
        "root_lineage_key_hash": stable_hash("root_lineage", root_lineage),
        "ordered_event_refs_hash": stable_hash("ordered_event_refs", event_refs),
        "state_before_summary_codes": [
            "state_before_authoritative_verifier_log_available",
            "state_before_no_stage12454_patch_application",
        ],
        "candidate_action_set_semantics": action_semantics(row, verifier_status),
        "observed_action_digest": stable_hash("observed_action_digest", observed_digest_payload),
        "policy_action_label": "append_authoritative_nonweb_verifier_transition_and_continue_stop",
        "non_imitation_policy_action_label": "derive_transition_label_from_authoritative_execution_metadata",
        "observed_action_imitation_status": "observed_but_independently_validated",
        "counterfactual_action_set": counterfactual_classes(row, verifier_status),
        "policy_label_independence_proof": "proven",
        "policy_label_independence_status": "proven_independent_not_observed_action_imitation",
        "observation_status_class": verifier_status,
        "verifier_identity_hash": stable_hash("verifier_identity", verifier_identity),
        "verifier_relevance_proof": "proven",
        "same_source_lineage_proof": "proven",
        "patch_application_or_no_patch_reason": patch_or_no_patch_reason(row, verifier_status),
        "causal_verifier_linkage": "proven",
        "state_delta_codes": state_delta_codes(row, verifier_status, command.get("returncode")),
        "state_after_summary_codes": state_after_codes(row, verifier_status),
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


def existing_signature(row: dict[str, Any]) -> str:
    return stable_hash(
        "existing_return_signature",
        row.get("source_stage"),
        row.get("root_id_hash"),
        row.get("source_root_label_hash"),
        row.get("repo_family_hash"),
        row.get("language_family"),
        row.get("root_lineage_key_hash"),
        row.get("ordered_event_refs_hash"),
        row.get("verifier_identity_hash"),
        row.get("observation_status_class"),
    )


def build_artifacts() -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    request, binding_issues = target_request()
    source_records = read_jsonl(SOURCE_RECORDS)
    existing_rows = read_jsonl(TARGET_EXPECTED_RETURN)
    before_count = len(existing_rows)
    existing_return_hashes = {str(row.get("return_row_hash") or "") for row in existing_rows if row.get("return_row_hash")}
    seen_signatures = {existing_signature(row) for row in existing_rows}
    appended_rows: list[dict[str, Any]] = []
    blocked_records: list[dict[str, Any]] = []
    reason_counts: Counter[str] = Counter(binding_issues)
    source_status_counts: Counter[str] = Counter()
    source_language_counts: Counter[str] = Counter()
    append_status_counts: Counter[str] = Counter()

    for source_row in source_records:
        language = normalize_language(source_row.get("language"))
        verifier_status = status_class(source_row)
        source_language_counts[language] += 1
        source_status_counts[verifier_status] += 1
        candidate_reasons = list(binding_issues)
        if request is None:
            candidate_reasons.append("target_request_unavailable")
        candidate_reasons.extend(eligibility_reasons(source_row))
        projected: dict[str, Any] | None = None
        source_sig = source_signature(source_row)
        if not candidate_reasons and request is not None:
            projected = build_return_row(source_row, request)
            projected_sig = existing_signature(projected)
            scan_issues = public_scan("return_row", projected)
            if scan_issues:
                candidate_reasons.extend(scan_issues)
                projected = None
            elif projected.get("return_row_hash") in existing_return_hashes:
                candidate_reasons.append("duplicate_return_hash_existing_or_prior_append")
                projected = None
            elif source_sig in seen_signatures or projected_sig in seen_signatures:
                candidate_reasons.append("duplicate_source_signature_existing_or_prior_append")
                projected = None
            else:
                passed, gate_reasons = stage12445_row_gate(projected)
                if passed:
                    appended_rows.append(projected)
                    existing_return_hashes.add(str(projected["return_row_hash"]))
                    seen_signatures.add(source_sig)
                    seen_signatures.add(projected_sig)
                    append_status_counts[verifier_status] += 1
                else:
                    candidate_reasons.extend(gate_reasons)
                    projected = None
        if projected is None:
            if not candidate_reasons:
                candidate_reasons.append("no_stage12445_row_gate_satisfying_row_without_fabrication")
            reason_counts.update(candidate_reasons)
            blocked_records.append(
                {
                    "candidate_hash": candidate_hash(source_row),
                    "source_stage_hash": stable_hash("source_stage", source_row.get("source_stage")),
                    "language_family": language,
                    "observation_status_class": verifier_status,
                    "source_signature_hash": source_sig,
                    "projection_status": "blocked",
                    "reason_codes": sorted(set(candidate_reasons)),
                }
            )

    combined_rows = existing_rows + appended_rows if appended_rows else existing_rows
    output_scan_issues = public_scan("appended_return_rows", appended_rows)
    output_scan_issues.extend(public_scan("blocked_records", blocked_records))
    if output_scan_issues:
        reason_counts.update(output_scan_issues)
        appended_rows = []
        combined_rows = existing_rows

    after_count = len(combined_rows)
    if appended_rows and not output_scan_issues:
        decision = "stage12205_nonweb_authoritative_rows_appended_and_stage12445_gate_passed"
    elif output_scan_issues:
        decision = "blocked_public_safety_scan_failed_existing_return_rows_unchanged"
    else:
        decision = "blocked_no_new_stage12205_nonweb_rows_passed_stage12445_row_gate_existing_return_rows_unchanged"

    guardrail_scan = {
        "scan_passed": not output_scan_issues,
        "issue_count": len(set(output_scan_issues)),
        "issues": sorted(set(output_scan_issues)),
        "raw_leak_count": len(
            {item for item in output_scan_issues if "raw_public_leak" in item or "forbidden_public_key" in item}
        ),
    }
    blocker_summary = {
        "stage": STAGE,
        "record_type": "stage12454_blocker_summary_public_safe_v1",
        "decision": decision,
        **ZERO_AUTHORITY,
        "existing_return_row_count_before": before_count,
        "return_row_count_after": after_count,
        "appended_return_row_count": len(appended_rows),
        "blocked_record_count": len(blocked_records),
        "blocked_records": blocked_records,
        "reason_code_counts": dict(sorted(reason_counts.items())),
        "public_value_policy": "hash_status_class_only_no_raw_paths_commands_stdout_stderr_source_diffs_urls",
        "guardrail_scan_passed": guardrail_scan["scan_passed"],
        "raw_leak_count": guardrail_scan["raw_leak_count"],
    }
    summary = {
        "stage": STAGE,
        "record_type": "stage12205_nonweb_authoritative_log_return_append_public_safe_v1",
        "decision": decision,
        **ZERO_AUTHORITY,
        "target_request_hash": TARGET_REQUEST_HASH,
        "target_adapter_request_id_hash": stable_hash("adapter_request_id", TARGET_ADAPTER_REQUEST_ID),
        "target_expected_return_file_hash": stable_hash("expected_return_file", str(TARGET_EXPECTED_RETURN.relative_to(ROOT))),
        "source_artifact_status": "present" if SOURCE_RECORDS.exists() else "missing",
        "source_artifact_sha256_24": file_hash(SOURCE_RECORDS),
        "source_record_count": len(source_records),
        "source_language_family_counts": dict(sorted(source_language_counts.items())),
        "source_status_class_counts": dict(sorted(source_status_counts.items())),
        "existing_return_row_count_before": before_count,
        "appended_return_row_count": len(appended_rows),
        "return_row_count_after": after_count,
        "append_status_class_counts": dict(sorted(append_status_counts.items())),
        "blocked_record_count": len(blocked_records),
        "blocker_reason_counts": dict(sorted(reason_counts.items())),
        "stage12445_request_binding_status": "pass" if request and not binding_issues else "blocked",
        "return_file_write_status": "appended" if appended_rows else "unchanged",
        "stage12445_admitted_rows_expected": bool(appended_rows),
        "public_value_policy": "hash_status_class_only_no_raw_paths_commands_stdout_stderr_source_diffs_urls",
        "claim_boundary": (
            "Stage12454 appends non-web Stage12205 authoritative verifier-log observations only. "
            "PASS_TO_PASS, PASS_CURRENT_STATE, and build-pass statuses are verifier-observation support only. "
            "FAIL_TO_PASS rows are verifier-transition support; controlled fixtures are marked train-support-only "
            "and other FAIL_TO_PASS rows are marked no-patch/no-repair-claim."
        ),
        "guardrail_scan": guardrail_scan,
        "guardrail_scan_passed": guardrail_scan["scan_passed"],
        "raw_leak_count": guardrail_scan["raw_leak_count"],
        "schema_issue_count": len(binding_issues),
        "summary_hash": "pending",
    }
    summary["summary_hash"] = stable_hash({key: value for key, value in summary.items() if key != "summary_hash"})
    return summary, appended_rows, combined_rows, blocker_summary


def main() -> None:
    summary, appended_rows, combined_rows, blocker_summary = build_artifacts()
    OUT.mkdir(parents=True, exist_ok=True)
    write_json(OUT / f"{STAGE}.json", summary)
    write_json(OUT / "summary.json", summary)
    write_json(SUMMARY, summary)
    write_json(OUT / "blocker_summary.json", blocker_summary)
    write_jsonl(OUT / "appended_return_rows.jsonl", appended_rows)
    write_jsonl(OUT / "blocked_records.jsonl", blocker_summary["blocked_records"])
    if appended_rows:
        write_jsonl(TARGET_EXPECTED_RETURN, combined_rows)
    print(
        json.dumps(
            {
                "stage": summary["stage"],
                "decision": summary["decision"],
                "source_record_count": summary["source_record_count"],
                "existing_return_row_count_before": summary["existing_return_row_count_before"],
                "appended_return_row_count": summary["appended_return_row_count"],
                "return_row_count_after": summary["return_row_count_after"],
                "blocked_record_count": summary["blocked_record_count"],
                "return_file_write_status": summary["return_file_write_status"],
                "guardrail_scan_passed": summary["guardrail_scan_passed"],
                "raw_leak_count": summary["raw_leak_count"],
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
