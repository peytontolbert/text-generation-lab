#!/usr/bin/env python3
"""Ingest Stage12444 adapter execution returns and gate Level-3 admission.

This stage only reads public-safe executor/private-review return files if they
exist. It never fabricates returns, never emits raw private values, and always
keeps training disabled.
"""
from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12445_adapter_execution_return_ingest_and_level3_gate"
OUT = ROOT / "runs/local/artifacts" / STAGE
SUMMARY = ROOT / "runs/summaries" / f"{STAGE}.json"

STAGE12444 = "stage12444_adapter_execution_request_manifest"
STAGE12444_OUT = ROOT / "runs/local/artifacts" / STAGE12444
STAGE12444_SUMMARY = ROOT / "runs/summaries" / f"{STAGE12444}.json"
EXECUTOR_RETURN_SCHEMA = STAGE12444_OUT / "executor_return_schema.json"
ADAPTER_REQUESTS = STAGE12444_OUT / "adapter_execution_requests.jsonl"
OPEN_SWE_REQUESTS = STAGE12444_OUT / "open_swe_authoritative_replay_batch.jsonl"
EXPECTED_RETURN_MANIFEST = STAGE12444_OUT / "expected_return_manifest.jsonl"

ZERO_TRAINING_COUNTERS: dict[str, bool | int] = {
    "training_allowed": False,
    "emitted_training_rows": 0,
    "sealed_eval_rows_emitted": 0,
}

ADMISSION_PROOF_SLOTS = [
    "same_source_lineage_proof",
    "verifier_relevance_proof",
    "state_delta_codes",
    "state_after_summary_codes",
    "stop_continue_label",
    "non_imitation_policy_action_label",
    "observed_action_imitation_status",
    "policy_label_independence_proof",
    "policy_label_independence_status",
    "counterfactual_action_set",
    "causal_verifier_linkage",
    "protected_overlap_check",
    "leakage_check",
]

TOP_LEVEL_ZERO_PROOF_COUNTERS = [
    "executor_return_record_count",
    "executor_return_valid_count",
    "private_review_return_count",
    "source_adapter_materialization_return_count",
    "open_swe_replay_return_count",
    "private_review_packet_ready_count",
    "policy_label_valid_count",
    "same_source_lineage_pass_count",
    "verifier_relevance_pass_count",
    "policy_label_independence_pass_count",
    "counterfactual_action_set_pass_count",
    "state_delta_correct_count",
    "state_after_summary_codes_pass_count",
    "stop_decision_correct_count",
    "protected_overlap_pass_count",
    "leakage_check_pass_count",
    "causal_verifier_linkage_pass_count",
    "countable_training_supply_delta",
]

PROTECTED_OVERLAP_PASS = {"pass", "passed", "clear", "no_overlap", "protected_clear", True}
LEAKAGE_PASS = {"pass", "passed", "clear", "no_leakage", "public_safe", True}
PROOF_PASS = {"pass", "passed", "proven", "valid", "clear", True}
STOP_CONTINUE_PASS = {"stop", "continue", "complete", "blocked", "needs_more_evidence"}
POLICY_PROOF_REJECT_RE = re.compile(r"\b(imitation|copy|copied|mimic|observed.action|same.as.observed)\b", re.I)
PROPAGATION_RE = re.compile(r"\b(similarity|representative|cluster|nearest|propagat)\b", re.I)

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
                raise ValueError(f"{path}:{line_number} is not a JSON object")
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


def stable_hash(value: Any, n: int = 24) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(f"{STAGE}:{payload}".encode("utf-8")).hexdigest()[:n]


def file_hash(path: Path, n: int = 24) -> str:
    if not path.exists() or not path.is_file():
        return "missing"
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()[:n]


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


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


def expected_return_path_bindings(expected_manifest: list[dict[str, Any]]) -> dict[Path, dict[str, Any]]:
    bindings: dict[Path, dict[str, Any]] = {}
    for row in expected_manifest:
        value = row.get("expected_return_path")
        if not isinstance(value, str) or not value:
            continue
        path = ROOT / value
        bindings[path] = row
    return bindings


def discover_return_files(expected_manifest: list[dict[str, Any]]) -> list[Path]:
    return [path for path in sorted(expected_return_path_bindings(expected_manifest)) if path.exists() and path.is_file()]


def validate_expected_manifest(
    expected_manifest: list[dict[str, Any]],
    requests: list[dict[str, Any]],
    schema: dict[str, Any],
) -> tuple[list[str], dict[Path, str], dict[str, str]]:
    issues: list[str] = []
    request_by_id = {str(row.get("execution_request_id_hash") or ""): row for row in requests if row.get("execution_request_id_hash")}
    manifest_by_id: dict[str, dict[str, Any]] = {}
    expected_request_by_path: dict[Path, str] = {}
    request_kind_by_id: dict[str, str] = {}
    ids: list[str] = []
    paths: list[str] = []
    for row in expected_manifest:
        request_id = str(row.get("execution_request_id_hash") or "")
        ids.append(request_id)
        if not request_id:
            issues.append("expected_return_manifest_blank_request_id")
            continue
        if request_id in manifest_by_id:
            issues.append("expected_return_manifest_duplicate_request_id")
        manifest_by_id[request_id] = row
        request_kind_by_id[request_id] = str(row.get("request_kind") or "unknown")
        expected_schema = row.get("expected_return_schema")
        if expected_schema != schema.get("schema_name"):
            issues.append(f"expected_return_schema_mismatch:{request_id}")
        value = row.get("expected_return_path")
        if not isinstance(value, str) or not value:
            issues.append(f"expected_return_manifest_blank_path:{request_id}")
            continue
        paths.append(value)
        path = ROOT / value
        try:
            path.relative_to(OUT)
        except ValueError:
            issues.append(f"expected_return_path_outside_stage12445_out:{request_id}")
        expected_request_by_path[path] = request_id
        request_row = request_by_id.get(request_id)
        if not request_row:
            issues.append(f"expected_return_manifest_unknown_request_id:{request_id}")
        else:
            if request_row.get("expected_return_path") != value:
                issues.append(f"expected_return_path_mismatch_with_request_row:{request_id}")
            if request_row.get("expected_return_schema") != expected_schema:
                issues.append(f"expected_return_schema_mismatch_with_request_row:{request_id}")
            if str(request_row.get("request_kind") or "unknown") != request_kind_by_id[request_id]:
                issues.append(f"expected_return_request_kind_mismatch_with_request_row:{request_id}")
    request_ids = set(request_by_id)
    manifest_ids = set(manifest_by_id)
    if request_ids != manifest_ids:
        issues.append("expected_return_manifest_request_id_set_mismatch")
    if len(paths) != len(set(paths)):
        issues.append("expected_return_manifest_duplicate_path")
    if len(ids) != len(expected_manifest):
        issues.append("expected_return_manifest_unparseable_id_count_mismatch")
    return sorted(set(issues)), expected_request_by_path, request_kind_by_id


def load_return_rows(path: Path) -> list[dict[str, Any]]:
    if path.suffix == ".jsonl":
        return read_jsonl(path)
    value = read_json(path)
    if isinstance(value, list):
        return [row for row in value if isinstance(row, dict)]
    if isinstance(value, dict):
        rows = value.get("returns") or value.get("return_rows") or value.get("results") or value.get("rows")
        if isinstance(rows, list):
            return [row for row in rows if isinstance(row, dict)]
        return [value]
    return []


PLACEHOLDER_VALUES = {"unknown", "claimed", "claimed_only", "not_proven", "n/a", "none", "placeholder", ""}
STATUS_ONLY_SLOTS = {
    "same_source_lineage_proof",
    "verifier_relevance_proof",
    "policy_label_independence_proof",
    "policy_label_independence_status",
    "observed_action_imitation_status",
    "causal_verifier_linkage",
    "protected_overlap_check",
    "leakage_check",
}


def value_present(value: Any) -> bool:
    if value in (None, "", [], {}):
        return False
    if isinstance(value, str) and value.strip().lower() in PLACEHOLDER_VALUES:
        return False
    if isinstance(value, list):
        return any(value_present(item) for item in value)
    if isinstance(value, dict):
        status = value.get("status") or value.get("proof_status") or value.get("check_status")
        if isinstance(status, str) and status.strip().lower() in PLACEHOLDER_VALUES:
            return False
        return bool(value)
    return True


def slot_present(row: dict[str, Any], slot: str) -> bool:
    if slot in row and value_present(row.get(slot)):
        return True
    if slot in STATUS_ONLY_SLOTS:
        status = row.get("slot_status")
        if isinstance(status, dict) and status.get(slot) in ("proven", "pass", "not_imitation", "observed_but_independently_validated", "proven_independent_not_observed_action_imitation"):
            return True
    return False


def status_value(row: dict[str, Any], slot: str) -> Any:
    value = row.get(slot)
    if isinstance(value, dict):
        return value.get("status") or value.get("proof_status") or value.get("check_status")
    return value


def status_pass(value: Any, allowed: set[Any]) -> bool:
    if value in allowed:
        return True
    if isinstance(value, str) and value.strip().lower() in allowed:
        return True
    return False


def row_gate(row: dict[str, Any], schema: dict[str, Any], required_slots: list[str], admission_slots: list[str]) -> tuple[bool, list[str], dict[str, str]]:
    reasons: list[str] = []
    statuses: dict[str, str] = {}

    required_missing = [slot for slot in required_slots if not slot_present(row, slot)]
    admission_missing = [slot for slot in admission_slots if not slot_present(row, slot)]
    required_properties = [str(prop) for prop in schema.get("required_properties", [])] if isinstance(schema.get("required_properties"), list) else []
    required_property_missing = [prop for prop in required_properties if not value_present(row.get(prop))]
    if required_property_missing:
        reasons.append("missing_executor_return_schema_required_properties")
    if schema.get("additional_properties_allowed") is False:
        allowed_keys = set(schema.get("allowed_properties") or required_slots)
        extra_keys = sorted(str(key) for key in row if key not in allowed_keys)
        if extra_keys:
            reasons.append("additional_properties_not_allowed")
    if row.get("schema_name") != schema.get("schema_name"):
        reasons.append("schema_name_mismatch")
    if not row.get("source_execution_request_id_hash"):
        reasons.append("source_execution_request_id_hash_missing")
    for hash_field in schema.get("non_empty_hash_fields_required", []):
        if not isinstance(row.get(hash_field), str) or not row.get(hash_field):
            reasons.append(f"non_empty_hash_field_missing:{hash_field}")
    if required_missing:
        reasons.append("missing_executor_return_schema_required_slots")
    if admission_missing:
        reasons.append("missing_admission_required_slots")

    scan_issues = public_scan("return_row", row)
    if scan_issues:
        reasons.append("raw_public_leakage_scan_failed")

    protected = status_value(row, "protected_overlap_check")
    leakage = status_value(row, "leakage_check")
    if not status_pass(protected, PROTECTED_OVERLAP_PASS):
        reasons.append("protected_overlap_check_failed")
    if not status_pass(leakage, LEAKAGE_PASS):
        reasons.append("leakage_check_failed")

    required_status_enums = schema.get("required_status_enums") if isinstance(schema.get("required_status_enums"), dict) else {}
    for slot in ADMISSION_PROOF_SLOTS:
        value = status_value(row, slot)
        if slot in required_status_enums:
            passed = status_pass(value, set(required_status_enums[slot]))
        elif slot == "stop_continue_label":
            passed = status_pass(value, STOP_CONTINUE_PASS)
        elif slot == "counterfactual_action_set":
            passed = isinstance(row.get(slot), list) and len([item for item in row.get(slot, []) if value_present(item)]) >= 2
        elif slot in {"state_delta_codes", "state_after_summary_codes"}:
            passed = isinstance(row.get(slot), list) and len([item for item in row.get(slot, []) if value_present(item)]) >= 1
        elif slot == "non_imitation_policy_action_label":
            passed = isinstance(row.get(slot), str) and value_present(row.get(slot))
        else:
            passed = status_pass(value, PROOF_PASS)
        statuses[f"{slot}_passed"] = str(bool(passed)).lower()
        if not passed:
            reasons.append(f"{slot}_proof_failed")

    policy_value = json.dumps(row.get("policy_label_independence_proof"), sort_keys=True, default=str)
    if POLICY_PROOF_REJECT_RE.search(policy_value):
        reasons.append("non_imitation_policy_proof_failed")

    proof_payload = json.dumps(
        {slot: row.get(slot) for slot in ADMISSION_PROOF_SLOTS if slot in row},
        sort_keys=True,
        default=str,
    )
    if PROPAGATION_RE.search(proof_payload):
        reasons.append("similarity_or_representative_propagation_used_as_proof")

    return not reasons, sorted(set(reasons)), statuses


def missing_return_counters(
    expected_manifest: list[dict[str, Any]],
    return_rows_by_request: Counter[str],
    present_return_requests: set[str] | None = None,
) -> dict[str, Any]:
    present_return_requests = present_return_requests or set()
    by_kind = Counter(str(row.get("request_kind") or "unknown") for row in expected_manifest)
    missing_by_kind: Counter[str] = Counter()
    empty_by_kind: Counter[str] = Counter()
    for row in expected_manifest:
        req = str(row.get("execution_request_id_hash") or "")
        if not req or req not in present_return_requests:
            missing_by_kind[str(row.get("request_kind") or "unknown")] += 1
        elif return_rows_by_request.get(req, 0) == 0:
            empty_by_kind[str(row.get("request_kind") or "unknown")] += 1
    present_count = sum(
        1
        for row in expected_manifest
        if str(row.get("execution_request_id_hash") or "") in present_return_requests
    )
    nonempty_count = sum(
        1
        for row in expected_manifest
        if return_rows_by_request.get(str(row.get("execution_request_id_hash") or ""), 0) > 0
    )
    return {
        "expected_return_count": len(expected_manifest),
        "present_return_file_count": present_count,
        "empty_return_file_count": max(0, present_count - nonempty_count),
        "found_return_file_count": nonempty_count,
        "missing_return_file_count": sum(missing_by_kind.values()),
        "missing_return_count_by_kind": dict(sorted(missing_by_kind.items())),
        "empty_return_count_by_kind": dict(sorted(empty_by_kind.items())),
    }


def build_artifact() -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    stage12444_summary = read_json(STAGE12444_SUMMARY)
    schema = read_json(EXECUTOR_RETURN_SCHEMA)
    required_slots = [str(slot) for slot in schema.get("required_return_slots", [])]
    admission_slots = [str(slot) for slot in schema.get("admission_required_slots", [])]
    requests = read_jsonl(ADAPTER_REQUESTS) + read_jsonl(OPEN_SWE_REQUESTS)
    expected_manifest = read_jsonl(EXPECTED_RETURN_MANIFEST)
    if not expected_manifest:
        expected_manifest = [
            {
                "execution_request_id_hash": row.get("execution_request_id_hash"),
                "request_kind": row.get("request_kind"),
                "expected_return_path": row.get("expected_return_path"),
            }
            for row in requests
        ]
    schema_issues: list[str] = []
    guardrail_issues: list[str] = []
    manifest_issues, expected_request_by_path, request_kind_by_id = validate_expected_manifest(expected_manifest, requests, schema)
    schema_issues.extend(manifest_issues)
    expected_request_ids = set(request_kind_by_id)
    open_swe_request_ids = {rid for rid, kind in request_kind_by_id.items() if kind == "open_swe_authoritative_replay_micro_pilot"}
    return_files = discover_return_files(expected_manifest) if not manifest_issues else []

    file_records: list[dict[str, Any]] = []
    admitted_records: list[dict[str, Any]] = []
    rejected_reason_counts: Counter[str] = Counter()
    total_return_rows = 0

    if not required_slots:
        schema_issues.append("stage12444_executor_return_schema_required_slots_missing")
    if not admission_slots:
        schema_issues.append("stage12444_executor_return_schema_admission_required_slots_missing")

    for path in return_files:
        rows = load_return_rows(path)
        path_hash = stable_hash(rel(path))
        row_count = len(rows)
        total_return_rows += row_count
        file_scan_issues: list[str] = []
        expected_request_id_for_file = expected_request_by_path.get(path)
        if not expected_request_id_for_file:
            file_scan_issues.append("return_file_not_bound_to_expected_manifest")
        for row in rows:
            passed, reasons, statuses = row_gate(row, schema, required_slots, admission_slots)
            request_id = str(row.get("source_execution_request_id_hash") or "")
            if request_id not in expected_request_ids:
                reasons = sorted(set(reasons + ["unknown_or_unsolicited_execution_request_id"]))
                passed = False
            if expected_request_id_for_file and request_id != expected_request_id_for_file:
                reasons = sorted(set(reasons + ["return_file_request_id_binding_mismatch"]))
                passed = False
            if request_id in open_swe_request_ids:
                if row.get("training_eligible") is not False or row.get("strict_eval_eligible") is not False:
                    reasons = sorted(set(reasons + ["open_swe_quarantine_fields_not_false"]))
                    passed = False
                if row.get("benchmark_material_status") != "benchmark_or_trace_material_quarantined_until_contamination_gate":
                    reasons = sorted(set(reasons + ["open_swe_benchmark_quarantine_status_missing"]))
                    passed = False
            file_scan_issues.extend(public_scan("return_row", row))
            if passed:
                admitted_records.append(
                    {
                        "admission_record_id_hash": stable_hash({"file": rel(path), "row": stable_hash(row)}),
                        "return_file_path_hash": path_hash,
                        "return_file_sha256_24": file_hash(path),
                        "return_row_hash": stable_hash(row),
                        "schema_required_slot_count": len(required_slots),
                        "admission_required_slot_count": len(admission_slots),
                        "admission_status": "admitted_level3_candidate",
                        "proof_statuses": statuses,
                        "training_allowed": False,
                    }
                )
            else:
                rejected_reason_counts.update(reasons)
        guardrail_issues.extend(file_scan_issues)
        file_records.append(
            {
                "return_file_record_id_hash": path_hash,
                "return_file_sha256_24": file_hash(path),
                "return_row_count": row_count,
                "public_scan_passed": not file_scan_issues,
                "public_scan_issue_count": len(set(file_scan_issues)),
            }
        )

    return_rows_by_request = Counter()
    # Re-read matched return rows cheaply to compute partial-return coverage by request.
    for path in return_files:
        expected_request_id_for_file = expected_request_by_path.get(path)
        for row in load_return_rows(path):
            request_id = str(row.get("source_execution_request_id_hash") or "")
            if request_id and expected_request_id_for_file and request_id == expected_request_id_for_file:
                return_rows_by_request[request_id] += 1
    present_return_requests = {
        request_id
        for path in return_files
        if (request_id := expected_request_by_path.get(path))
    }
    missing_counters = missing_return_counters(expected_manifest, return_rows_by_request, present_return_requests)
    guardrail_issues.extend(schema_issues)
    pre_output_guardrail_passed = not guardrail_issues
    admitted_count = len(admitted_records) if pre_output_guardrail_passed else 0
    request_kind_counts = Counter(str(row.get("request_kind") or "unknown") for row in requests)
    top_level_return_counters = {key: 0 for key in TOP_LEVEL_ZERO_PROOF_COUNTERS}
    top_level_return_counters.update(
        {
            "executor_return_record_count": total_return_rows,
            "executor_return_valid_count": admitted_count,
            "private_review_return_count": 0,
            "source_adapter_materialization_return_count": 0,
            "open_swe_replay_return_count": 0,
            "countable_training_supply_delta": 0,
        }
    )
    if not pre_output_guardrail_passed:
        admitted_records = []

    artifact = {
        "stage": STAGE,
        "record_type": "adapter_execution_return_ingest_and_level3_gate_public_safe_v1",
        "decision": "no_return_files_found_zero_admitted" if not return_files else "return_files_ingested_level3_gate_applied",
        **ZERO_TRAINING_COUNTERS,
        "admission_allowed": False,
        "admitted_rows": admitted_count,
        "level3_candidate_count": admitted_count,
        "countable_new_rows": 0,
        **top_level_return_counters,
        "level4_candidate_count": 0,
        "patch_trace_candidate_count": 0,
        "source_fingerprints": {
            "stage12444_summary_sha256_24": file_hash(STAGE12444_SUMMARY),
            "executor_return_schema_sha256_24": file_hash(EXECUTOR_RETURN_SCHEMA),
            "adapter_execution_requests_sha256_24": file_hash(ADAPTER_REQUESTS),
            "open_swe_authoritative_replay_batch_sha256_24": file_hash(OPEN_SWE_REQUESTS),
            "expected_return_manifest_sha256_24": file_hash(EXPECTED_RETURN_MANIFEST),
            "expected_return_manifest_validated_sha256_24": file_hash(EXPECTED_RETURN_MANIFEST),
        },
        "source_stage_gate_status": {
            "stage12444_guardrail_passed": stage12444_summary.get("guardrail_scan_passed") is True,
            "stage12444_training_blocked": stage12444_summary.get("training_allowed") is False,
            "stage12444_admission_blocked": stage12444_summary.get("admission_allowed") is False,
            "stage12444_executor_return_schema_present": bool(required_slots and admission_slots),
            "expected_return_manifest_valid": not manifest_issues,
        },
        "executor_return_schema": {
            "schema_name": schema.get("schema_name"),
            "required_return_slot_count": len(required_slots),
            "admission_required_slot_count": len(admission_slots),
            "schema_hash": stable_hash(schema),
            "additional_properties_allowed": schema.get("additional_properties_allowed"),
            "per_slot_required_status": schema.get("per_slot_required_status"),
            "required_status_enums": schema.get("required_status_enums"),
        },
        "required_gate_policy_schema": {
            "all_executor_return_schema_required_slots_present": True,
            "all_admission_required_slots_present": True,
            "raw_public_leakage_scan_passed": True,
            "protected_overlap_check_passed": True,
            "same_source_lineage_proof_passed": True,
            "verifier_relevance_proof_passed": True,
            "state_delta_proof_passed": True,
            "stop_continue_proof_passed": True,
            "non_imitation_policy_proof_passed": True,
            "similarity_or_representative_propagation_not_used_as_proof": True,
        },
        "return_ingest_counters": {
            **missing_counters,
            "return_row_count": total_return_rows,
            "request_kind_counts": dict(sorted(request_kind_counts.items())),
            "expected_return_manifest_count": len(expected_manifest),
            "expected_return_manifest_issue_count": len(manifest_issues),
            "return_file_request_binding_enforced": True,
            "return_rows_by_request_count": dict(sorted(return_rows_by_request.items())),
            "admitted_return_row_count": admitted_count,
            "rejected_return_row_count": max(0, total_return_rows - admitted_count),
            "rejected_reason_counts": dict(sorted(rejected_reason_counts.items())),
        },
        "output_artifact_counts": {
            "return_file_manifest_rows": len(file_records),
            "admitted_level3_candidate_rows": admitted_count,
        },
        "guardrail_scan": {},
        "guardrail_scan_passed": False,
        "raw_leak_count": 0,
        "schema_issue_count": len(schema_issues),
        "schema_issues": schema_issues,
        "public_output_policy": "hash_status_count_schema_only_no_raw_private_values",
        "claim_boundary": "Return ingest and Level-3 validation gate only. Training remains disabled and no training rows are emitted; validated candidates require a later admission/packaging decision before countable training supply.",
        "summary_hash": "pending",
    }
    public_payload_issues = public_scan("artifact", artifact)
    public_payload_issues.extend(public_scan("return_file_manifest", file_records))
    public_payload_issues.extend(public_scan("admitted_level3_candidates", admitted_records))
    guardrail_issues.extend(public_payload_issues)
    if artifact.get("admission_allowed") is not False:
        guardrail_issues.append("admission_allowed_must_remain_false_in_ingest_gate")
    guardrail_scan = {
        "scan_passed": not guardrail_issues,
        "issue_count": len(set(guardrail_issues)),
        "issues": sorted(set(guardrail_issues)),
        "raw_leak_count": len({issue for issue in guardrail_issues if "raw_public_leak" in issue or "forbidden_public_key" in issue}),
        "scan_scope": "stage12445_public_outputs_and_return_rows_hash_status_count_schema_only",
    }
    if not guardrail_scan["scan_passed"]:
        admitted_records = []
        artifact["admission_allowed"] = False
        artifact["admitted_rows"] = 0
        artifact["level3_candidate_count"] = 0
        artifact["countable_new_rows"] = 0
        artifact["return_ingest_counters"]["admitted_return_row_count"] = 0
        artifact["return_ingest_counters"]["rejected_return_row_count"] = total_return_rows
        artifact["output_artifact_counts"]["admitted_level3_candidate_rows"] = 0
    artifact["guardrail_scan"] = guardrail_scan
    artifact["guardrail_scan_passed"] = guardrail_scan["scan_passed"]
    artifact["raw_leak_count"] = guardrail_scan["raw_leak_count"]
    artifact["summary_hash"] = stable_hash({key: value for key, value in artifact.items() if key != "summary_hash"})
    return artifact, file_records, admitted_records, guardrail_scan


def main() -> None:
    artifact, file_records, admitted_records, guardrail_scan = build_artifact()
    OUT.mkdir(parents=True, exist_ok=True)
    write_json(OUT / f"{STAGE}.json", artifact)
    write_json(OUT / "summary.json", artifact)
    write_json(SUMMARY, artifact)
    write_jsonl(OUT / "return_file_manifest.jsonl", file_records)
    write_jsonl(OUT / "admitted_level3_candidates.jsonl", admitted_records)
    write_json(OUT / "guardrail_scan.json", guardrail_scan)
    print(json.dumps({
        "stage": artifact["stage"],
        "decision": artifact["decision"],
        "expected_return_count": artifact["return_ingest_counters"]["expected_return_count"],
        "found_return_file_count": artifact["return_ingest_counters"]["found_return_file_count"],
        "missing_return_file_count": artifact["return_ingest_counters"]["missing_return_file_count"],
        "return_row_count": artifact["return_ingest_counters"]["return_row_count"],
        "admitted_rows": artifact["admitted_rows"],
        "level3_candidate_count": artifact["level3_candidate_count"],
        "countable_new_rows": artifact["countable_new_rows"],
        "training_allowed": artifact["training_allowed"],
        "emitted_training_rows": artifact["emitted_training_rows"],
        "guardrail_scan_passed": artifact["guardrail_scan_passed"],
        "raw_leak_count": artifact["raw_leak_count"],
        "executor_return_record_count": artifact["executor_return_record_count"],
        "executor_return_valid_count": artifact["executor_return_valid_count"],
        "schema_issue_count": artifact["schema_issue_count"],
    }, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
