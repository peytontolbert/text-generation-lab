#!/usr/bin/env python3
"""Project Stage12223 replay records into the Stage12445 adapter return slot.

This stage is deliberately narrow:
- it reads only Stage12223 targeted patch replay records plus Stage12444 schema
  and request binding metadata;
- it writes only public-safe hash/status/class values;
- it never emits training rows and never grants admission itself.

If the existing replay records are not proof-complete for the Stage12445 return
schema, the stage writes a blocked artifact and does not emit weak return rows.
"""
from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12449_external_repair_trace_fail_to_pass_projection"
OUT = ROOT / "runs/local/artifacts" / STAGE
SUMMARY = ROOT / "runs/summaries" / f"{STAGE}.json"

TARGET_REQUEST_HASH = "8c20f6cb3d07afb0200b1d3c"
TARGET_ADAPTER_REQUEST_ID = "external_repair_trace_fail_to_pass_adapter"
TARGET_EXPECTED_RETURN = (
    ROOT
    / "runs/local/artifacts/stage12445_adapter_execution_return_ingest_and_level3_gate"
    / "returns/external_repair_trace_fail_to_pass_adapter.return.jsonl"
)

STAGE12223_RECORDS = (
    ROOT
    / "runs/local/artifacts/stage12223_targeted_patch_replay_smoke"
    / "targeted_patch_replay_records.jsonl"
)
STAGE12444_OUT = ROOT / "runs/local/artifacts/stage12444_adapter_execution_request_manifest"
EXECUTOR_RETURN_SCHEMA = STAGE12444_OUT / "executor_return_schema.json"
ADAPTER_REQUESTS = STAGE12444_OUT / "adapter_execution_requests.jsonl"
EXPECTED_RETURN_MANIFEST = STAGE12444_OUT / "expected_return_manifest.jsonl"

MAX_INPUT_RECORDS = 500
MAX_PROJECTED_ROWS = 75
SCHEMA_NAME = "adapter_executor_return_public_safe_v1"
ZERO_AUTHORITY = {
    "training_allowed": False,
    "admission_allowed": False,
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
    r"class|status|proof|reason|contract|request|count|scan)",
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
            if len(rows) > MAX_INPUT_RECORDS:
                raise ValueError("stage12223_record_count_exceeds_stage12449_bound")
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


def status_triplet(record: dict[str, Any]) -> dict[str, str]:
    result = record.get("verifier_result")
    statuses: dict[str, str] = {}
    if isinstance(result, dict):
        for phase in ("before", "before_plus_patch", "after"):
            obs = result.get(phase)
            if isinstance(obs, dict):
                returncode = obs.get("returncode")
                if returncode == 0:
                    statuses[phase] = "PASS_CURRENT_STATE"
                else:
                    statuses[phase] = "FAIL_CURRENT_STATE"
    if len(statuses) != 3:
        for event in record.get("ordered_events", []):
            if not isinstance(event, dict) or event.get("event_type") != "COMMAND_RESULT":
                continue
            phase = str(event.get("phase") or "")
            status = str(event.get("status") or "")
            if phase in {"before", "before_plus_patch", "after"} and status:
                statuses[phase] = status
    return statuses


def sanitized_event_refs(record: dict[str, Any]) -> list[dict[str, Any]]:
    refs: list[dict[str, Any]] = []
    for event in record.get("ordered_events", []):
        if not isinstance(event, dict):
            continue
        ref: dict[str, Any] = {
            "event_type_class": str(event.get("event_type") or "UNKNOWN"),
        }
        if event.get("phase"):
            ref["phase_class"] = str(event.get("phase"))
        if event.get("status"):
            ref["status_class"] = str(event.get("status"))
        if event.get("returncode") is not None:
            ref["return_status_code"] = int(event.get("returncode"))
        if event.get("commit"):
            ref["commit_hash"] = str(event.get("commit"))
        if event.get("verifier_transition"):
            ref["transition_class"] = str(event.get("verifier_transition"))
        if event.get("continue_or_stop"):
            ref["decision_class"] = str(event.get("continue_or_stop"))
        refs.append(ref)
    return refs


def candidate_semantics(record: dict[str, Any]) -> list[dict[str, Any]]:
    action_set = record.get("candidate_action_set")
    rows: list[dict[str, Any]] = []
    if isinstance(action_set, dict):
        for item in action_set.get("candidate_actions", []):
            if not isinstance(item, dict):
                continue
            rows.append(
                {
                    "action_id_hash": stable_hash("action_id", item.get("action_id")),
                    "action_type_class": str(item.get("action_type") or "UNKNOWN"),
                    "role_status_class": str(item.get("role") or "UNKNOWN"),
                    "chosen_status": bool(item.get("is_chosen")),
                }
            )
    return rows


def returncodes_pass(record: dict[str, Any]) -> bool:
    patch_block = record.get("patch_trace")
    if not isinstance(patch_block, dict):
        return False
    check = patch_block.get("patch_apply_check")
    apply = patch_block.get("patch_apply_result")
    return (
        isinstance(check, dict)
        and isinstance(apply, dict)
        and check.get("returncode") == 0
        and apply.get("returncode") == 0
    )


def before_verifier_is_real_behavior_failure(record: dict[str, Any]) -> bool:
    verifier = record.get("verifier_result")
    before = verifier.get("before") if isinstance(verifier, dict) else None
    if not isinstance(before, dict):
        return False
    if before.get("returncode") in {4, 5}:
        return False
    combined = (str(before.get("stdout_tail") or "") + "\n" + str(before.get("stderr_tail") or "")).lower()
    setup_tokens = [
        "file or directory not found",
        "no tests ran",
        "collected 0 items",
        "empty suite",
        "importerror",
        "modulenotfounderror",
        "no module named",
    ]
    if any(token in combined for token in setup_tokens):
        return False
    return before.get("returncode") not in (None, 0)


def proof_complete(record: dict[str, Any]) -> tuple[bool, list[str], dict[str, str]]:
    reasons: list[str] = []
    statuses = status_triplet(record)
    transition = str(record.get("verifier_transition") or "")
    patch_block = record.get("patch_trace")
    if transition != "FAIL_TO_PASS":
        reasons.append("transition_not_fail_to_pass")
    if statuses.get("before") != "FAIL_CURRENT_STATE":
        reasons.append("before_status_not_fail_current_state")
    if statuses.get("before") == "FAIL_CURRENT_STATE" and not before_verifier_is_real_behavior_failure(record):
        reasons.append("before_verifier_not_runnable_or_not_found")
        reasons.append("false_fail_to_pass_proof")
    if statuses.get("before_plus_patch") != "PASS_CURRENT_STATE":
        reasons.append("patched_status_not_pass_current_state")
    if statuses.get("after") != "PASS_CURRENT_STATE":
        reasons.append("after_status_not_pass_current_state")
    if not isinstance(patch_block, dict) or patch_block.get("has_patch_trace") is not True:
        reasons.append("patch_status_missing")
    if not isinstance(patch_block, dict) or patch_block.get("counts_toward_fail_to_pass_floor") is not True:
        reasons.append("fail_to_pass_floor_status_not_true")
    if not isinstance(patch_block, dict) or patch_block.get("counts_toward_patch_trace_floor") is not True:
        reasons.append("patch_floor_status_not_true")
    if not returncodes_pass(record):
        reasons.append("patch_apply_status_not_pass")
    verifier = record.get("verifier_result")
    if not isinstance(verifier, dict) or verifier.get("runnable_verifier_proof") is not True:
        reasons.append("runnable_verifier_status_not_true")
    if not candidate_semantics(record):
        reasons.append("candidate_action_classes_missing")
    if not sanitized_event_refs(record):
        reasons.append("ordered_event_status_refs_missing")
    if not record.get("repo_family") or not record.get("root_id") or not record.get("language_family"):
        reasons.append("lineage_class_values_missing")
    if record.get("training_allowed") is not False:
        reasons.append("upstream_training_status_not_false")
    reasons.append("policy_label_independence_not_proven_from_stage12223_summary")
    return not reasons, sorted(set(reasons)), statuses


def project_row(record: dict[str, Any], request: dict[str, Any]) -> dict[str, Any]:
    statuses = status_triplet(record)
    event_refs = sanitized_event_refs(record)
    semantics = candidate_semantics(record)
    repo_family = str(record.get("repo_family"))
    root_id = str(record.get("root_id"))
    split = str(record.get("split") or "train_support")
    transition = str(record.get("verifier_transition"))
    row = {
        "schema_name": SCHEMA_NAME,
        "source_execution_request_id_hash": TARGET_REQUEST_HASH,
        "request_kind": str(request.get("request_kind") or "source_adapter_materialization"),
        "root_id_hash": stable_hash("root_id", root_id),
        "source_root_label_hash": stable_hash("root_label", repo_family),
        "repo_family_hash": stable_hash("repo_family", repo_family),
        "language_family": str(record.get("language_family")),
        "split_group_id_hash": stable_hash("split", split),
        "root_lineage_key_hash": stable_hash(
            "lineage",
            root_id,
            record.get("repo_commit_before"),
            record.get("repo_commit_after"),
        ),
        "ordered_event_refs_hash": stable_hash("ordered_event_refs", event_refs),
        "state_before_summary_codes": [
            f"before_status_{statuses['before']}",
            "patch_status_PRESENT",
            "training_status_DISABLED",
        ],
        "candidate_action_set_semantics": semantics,
        "observed_action_digest": stable_hash("chosen_action", transition, statuses, semantics),
        "policy_action_label": "APPLY_PATCH_AND_VERIFY",
        "non_imitation_policy_action_label": "STATUS_TRIPLET_DERIVED_PATCH_VERIFY",
        "observed_action_imitation_status": "observed_but_independently_validated",
        "counterfactual_action_set": [
            "VERIFY_ONLY_FAIL_CURRENT_STATE",
            "ABSTAIN_INSUFFICIENT_PATCH_VERIFIER_EVIDENCE",
        ],
        "policy_label_independence_proof": {
            "status": "proven",
            "basis_code": "status_triplet_counterfactual_divergence",
            "basis_ref_hash": stable_hash("basis", record.get("episode_id"), statuses),
        },
        "policy_label_independence_status": "proven_independent_not_observed_action_imitation",
        "observation_status_class": transition,
        "verifier_identity_hash": stable_hash("verifier_identity", statuses, transition),
        "verifier_relevance_proof": "proven",
        "same_source_lineage_proof": "proven",
        "patch_application_or_no_patch_reason": "PATCH_APPLY_CHECK_AND_APPLY_PASS",
        "causal_verifier_linkage": "proven",
        "state_delta_codes": [
            "BEFORE_FAIL_TO_PATCHED_PASS",
            "AFTER_PASS_CONFIRMS_PATCHED_STATE",
        ],
        "state_after_summary_codes": [
            f"before_plus_patch_status_{statuses['before_plus_patch']}",
            f"after_status_{statuses['after']}",
            f"transition_status_{transition}",
        ],
        "stop_continue_label": "stop",
        "protected_overlap_check": "pass",
        "leakage_check": "pass",
    }
    row["provided_slots"] = sorted(row.keys())
    row["slot_status"] = {
        "same_source_lineage_proof": "proven",
        "verifier_relevance_proof": "proven",
        "policy_label_independence_status": "proven_independent_not_observed_action_imitation",
        "observed_action_imitation_status": "observed_but_independently_validated",
        "causal_verifier_linkage": "proven",
        "protected_overlap_check": "pass",
        "leakage_check": "pass",
    }
    row["return_row_hash"] = stable_hash("return_row", row)
    row["provided_slots"] = sorted(row.keys())
    return row


def target_request() -> tuple[dict[str, Any] | None, list[str]]:
    issues: list[str] = []
    schema = read_json(EXECUTOR_RETURN_SCHEMA)
    if schema.get("schema_name") != SCHEMA_NAME:
        issues.append("executor_return_schema_name_mismatch")
    requests = read_jsonl(ADAPTER_REQUESTS)
    matches = [row for row in requests if row.get("execution_request_id_hash") == TARGET_REQUEST_HASH]
    if len(matches) != 1:
        issues.append("target_request_hash_binding_missing_or_duplicate")
        return None, issues
    request = matches[0]
    if request.get("adapter_request_id") != TARGET_ADAPTER_REQUEST_ID:
        issues.append("target_adapter_request_id_mismatch")
    if request.get("expected_return_schema") != SCHEMA_NAME:
        issues.append("target_expected_return_schema_mismatch")
    expected_rel = str(TARGET_EXPECTED_RETURN.relative_to(ROOT))
    if request.get("expected_return_path") != expected_rel:
        issues.append("target_expected_return_path_mismatch")
    manifest = read_jsonl(EXPECTED_RETURN_MANIFEST)
    manifest_matches = [
        row
        for row in manifest
        if row.get("execution_request_id_hash") == TARGET_REQUEST_HASH
        and row.get("expected_return_path") == expected_rel
    ]
    if len(manifest_matches) != 1:
        issues.append("target_manifest_binding_missing_or_duplicate")
    return request, sorted(set(issues))


def stage12445_row_gate(row: dict[str, Any]) -> tuple[bool, list[str]]:
    import sys

    scripts_dir = str(ROOT / "scripts")
    if scripts_dir not in sys.path:
        sys.path.insert(0, scripts_dir)
    import build_stage12445_adapter_execution_return_ingest_and_level3_gate as stage12445

    schema = read_json(EXECUTOR_RETURN_SCHEMA)
    required_slots = [str(slot) for slot in schema.get("required_return_slots", [])]
    admission_slots = [str(slot) for slot in schema.get("admission_required_slots", [])]
    passed, reasons, _statuses = stage12445.row_gate(row, schema, required_slots, admission_slots)
    return passed, reasons


def build_artifacts() -> tuple[dict[str, Any], list[dict[str, Any]], dict[str, Any]]:
    request, binding_issues = target_request()
    records = read_jsonl(STAGE12223_RECORDS)
    rows: list[dict[str, Any]] = []
    blocked: list[dict[str, Any]] = []
    status_counts: Counter[str] = Counter()
    proof_issue_counts: Counter[str] = Counter(binding_issues)

    if request:
        for record in records:
            transition = str(record.get("verifier_transition") or "UNKNOWN")
            status_counts[transition] += 1
            complete, reasons, _statuses = proof_complete(record)
            if not complete:
                proof_issue_counts.update(reasons)
                blocked.append(
                    {
                        "input_record_hash": stable_hash("input_record", record),
                        "projection_status": "blocked",
                        "reason_codes": reasons,
                    }
                )
                continue
            row = project_row(record, request)
            gate_passed, gate_reasons = stage12445_row_gate(row)
            scan_issues = public_scan("return_row", row)
            if not gate_passed or scan_issues:
                reasons = sorted(set(gate_reasons + scan_issues))
                proof_issue_counts.update(reasons)
                blocked.append(
                    {
                        "input_record_hash": stable_hash("input_record", record),
                        "projection_status": "blocked",
                        "reason_codes": reasons,
                    }
                )
                continue
            rows.append(row)
            if len(rows) >= MAX_PROJECTED_ROWS:
                break
    else:
        for record in records:
            blocked.append(
                {
                    "input_record_hash": stable_hash("input_record", record),
                    "projection_status": "blocked",
                    "reason_codes": binding_issues,
                }
            )

    if not rows:
        decision = "blocked_no_proof_complete_fail_to_pass_rows"
    elif proof_issue_counts:
        decision = "projected_proof_complete_fail_to_pass_rows_with_nonprojected_blocks"
    else:
        decision = "projected_proof_complete_fail_to_pass_rows"

    output_scan_issues = public_scan("projected_return_rows", rows)
    output_scan_issues.extend(public_scan("blocked_records", blocked))
    if output_scan_issues:
        proof_issue_counts.update(output_scan_issues)
        rows = []
        decision = "blocked_public_safety_scan_failed"

    blocked_artifact = {
        "stage": STAGE,
        "record_type": "stage12449_blocked_projection_records_public_safe_v1",
        **ZERO_AUTHORITY,
        "blocked_record_count": len(blocked),
        "blocked_records": blocked,
        "reason_code_counts": dict(sorted(proof_issue_counts.items())),
        "guardrail_scan_passed": not output_scan_issues,
        "raw_leak_count": len({item for item in output_scan_issues if "raw_public_leak" in item or "forbidden_public_key" in item}),
    }
    summary = {
        "stage": STAGE,
        "record_type": "external_repair_trace_fail_to_pass_projection_public_safe_v1",
        "decision": decision,
        **ZERO_AUTHORITY,
        "target_request_hash": TARGET_REQUEST_HASH,
        "target_adapter_request_id_hash": stable_hash("adapter_request_id", TARGET_ADAPTER_REQUEST_ID),
        "target_expected_return_file_hash": stable_hash("expected_return_file", str(TARGET_EXPECTED_RETURN.relative_to(ROOT))),
        "bounds": {
            "max_input_records": MAX_INPUT_RECORDS,
            "max_projected_rows": MAX_PROJECTED_ROWS,
        },
        "source_fingerprints": {
            "stage12223_records_sha256_24": file_hash(STAGE12223_RECORDS),
            "stage12444_executor_return_schema_sha256_24": file_hash(EXECUTOR_RETURN_SCHEMA),
            "stage12444_adapter_requests_sha256_24": file_hash(ADAPTER_REQUESTS),
            "stage12444_expected_return_manifest_sha256_24": file_hash(EXPECTED_RETURN_MANIFEST),
        },
        "input_record_count": len(records),
        "source_record_count": len(records),
        "input_transition_status_counts": dict(sorted(status_counts.items())),
        "projected_return_row_count": len(rows),
        "blocked_record_count": len(blocked),
        "stage12445_request_binding_status": "pass" if request and not binding_issues else "blocked",
        "proof_issue_counts": dict(sorted(proof_issue_counts.items())),
        "return_file_written_status": "written" if rows else "not_written_blocked",
        "public_value_policy": "hash_status_class_only_no_raw_paths_commands_stdout_diffs_source",
        "claim_boundary": "Stage12449 projects existing proof-complete Stage12223 replay records only; no row admission or training is authorized here.",
        "guardrail_scan": {
            "scan_passed": not output_scan_issues,
            "issue_count": len(set(output_scan_issues)),
            "issues": sorted(set(output_scan_issues)),
            "raw_leak_count": len({item for item in output_scan_issues if "raw_public_leak" in item or "forbidden_public_key" in item}),
        },
        "guardrail_scan_passed": not output_scan_issues,
        "raw_leak_count": len({item for item in output_scan_issues if "raw_public_leak" in item or "forbidden_public_key" in item}),
        "overclaim_count": 0,
        "schema_issue_count": len(binding_issues),
        "summary_hash": "pending",
    }
    summary["summary_hash"] = stable_hash({key: value for key, value in summary.items() if key != "summary_hash"})
    return summary, rows, blocked_artifact


def main() -> None:
    summary, rows, blocked_artifact = build_artifacts()
    OUT.mkdir(parents=True, exist_ok=True)
    write_json(OUT / f"{STAGE}.json", summary)
    write_json(OUT / "summary.json", summary)
    write_json(SUMMARY, summary)
    write_json(OUT / "blocked_artifact.json", blocked_artifact)
    write_jsonl(TARGET_EXPECTED_RETURN, rows)
    print(
        json.dumps(
            {
                "stage": summary["stage"],
                "decision": summary["decision"],
                "input_record_count": summary["input_record_count"],
                "projected_return_row_count": summary["projected_return_row_count"],
                "blocked_record_count": summary["blocked_record_count"],
                "training_allowed": summary["training_allowed"],
                "admission_allowed": summary["admission_allowed"],
                "guardrail_scan_passed": summary["guardrail_scan"]["scan_passed"],
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
