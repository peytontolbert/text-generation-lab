#!/usr/bin/env python3
"""Build Stage12446 bounded adapter return production plan.

This stage plans the seven public-safe return files that Stage12445 expected
but did not find. It does not execute private replay, inspect raw private data,
fabricate returns, admit rows, or emit training rows.
"""
from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12446_adapter_return_production_plan"
OUT = ROOT / "runs/local/artifacts" / STAGE
SUMMARY = ROOT / "runs/summaries" / f"{STAGE}.json"

STAGE12444 = "stage12444_adapter_execution_request_manifest"
STAGE12445 = "stage12445_adapter_execution_return_ingest_and_level3_gate"
STAGE12444_OUT = ROOT / "runs/local/artifacts" / STAGE12444
STAGE12445_OUT = ROOT / "runs/local/artifacts" / STAGE12445
STAGE12444_SUMMARY = ROOT / "runs/summaries" / f"{STAGE12444}.json"
STAGE12445_SUMMARY = ROOT / "runs/summaries" / f"{STAGE12445}.json"

ADAPTER_REQUESTS = STAGE12444_OUT / "adapter_execution_requests.jsonl"
OPEN_SWE_REQUESTS = STAGE12444_OUT / "open_swe_authoritative_replay_batch.jsonl"
EXECUTOR_RETURN_SCHEMA = STAGE12444_OUT / "executor_return_schema.json"
EXPECTED_RETURN_MANIFEST = STAGE12444_OUT / "expected_return_manifest.jsonl"

ZERO_COUNTERS: dict[str, bool | int] = {
    "training_allowed": False,
    "admission_allowed": False,
    "execution_allowed": False,
    "execution_performed_by_stage": False,
    "private_replay_executed": False,
    "raw_private_data_inspected": False,
    "fabricated_returns": False,
    "admitted_rows": 0,
    "emitted_training_rows": 0,
    "countable_new_rows": 0,
    "level3_candidate_count": 0,
    "level4_candidate_count": 0,
    "patch_trace_candidate_count": 0,
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
    r"class|status|proof|reason|contract|request|count|scan|location|file|name|"
    r"operation|stage|summary|fingerprint|input|artifact)",
    re.IGNORECASE,
)
RAW_LEAK_RE = re.compile(
    r"https?://|www\.|diff --git|@@ |^\+\+\+ |^--- |<<<<<<<|>>>>>>>|"
    r"(?<![A-Za-z0-9_])/(?:[A-Za-z0-9._-]+/){2,}[A-Za-z0-9._-]+|"
    r"\b(?:Traceback \(most recent call last\)|stdout:|stderr:|stack trace|"
    r"terminal output:|command output:|git clone\s+\S|git apply\s+\S|"
    r"curl\s+\S|bash -|sh -|python -c)\b",
    re.IGNORECASE | re.MULTILINE,
)
OVERCLAIM_RE = re.compile(
    r"\b(?:admitted|training row|trainable|accepted row|verified repair|"
    r"level-3 complete|level3 complete|patch-trace complete|execution succeeded|"
    r"tests passed|replay succeeded)\b",
    re.IGNORECASE,
)
ALLOWED_OVERCLAIM_CONTEXT_RE = re.compile(
    r"(false|zero|none|blocked|required|future|must not|not |no |fail.closed|"
    r"fail-closed|policy|guardrail|schema|contract|separate ingest|do_not|"
    r"planning_only|counter|candidate_count|admitted_rows)",
    re.IGNORECASE,
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


def safe_slug(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_]+", "_", value).strip("_").lower()[:96] or "unknown"


def scan_public(label: str, value: Any) -> list[str]:
    issues: list[str] = []
    leaf = label.rsplit(".", 1)[-1].split("[", 1)[0].lower()
    if leaf in FORBIDDEN_PUBLIC_KEYS and not ALLOWED_KEY_CONTEXT_RE.search(label):
        issues.append(f"{label}:forbidden_public_key")
    if isinstance(value, str):
        if RAW_LEAK_RE.search(value):
            issues.append(f"{label}:raw_public_leak:{stable_hash(value)}")
        for match in OVERCLAIM_RE.finditer(value):
            context = value[max(0, match.start() - 80): min(len(value), match.end() + 80)]
            if not ALLOWED_OVERCLAIM_CONTEXT_RE.search(context):
                issues.append(f"{label}:overclaim:{stable_hash(context)}")
    elif isinstance(value, dict):
        for key, child in value.items():
            issues.extend(scan_public(f"{label}.{key}", child))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            issues.extend(scan_public(f"{label}[{index}]", child))
    return issues


def request_private_operation(request: dict[str, Any]) -> dict[str, Any]:
    kind = str(request.get("request_kind") or "unknown")
    adapter_id = str(request.get("adapter_request_id") or "")
    if kind == "private_semantic_review":
        operation = "private_semantic_review_return_materialization"
        instructions = [
            "Use only authorized private review packet refs.",
            "Return only hash/status/class fields.",
            "Prove representative row slots independently; do not propagate cluster similarity as proof.",
        ]
    elif kind == "open_swe_authoritative_replay_micro_pilot":
        operation = "authorized_private_replay_proof_slot_materialization"
        instructions = [
            "Run private replay only in the authorized executor lane outside this planning stage.",
            "Populate proof slots from authorized replay observations as hashes/status/classes only.",
            "Keep benchmark material quarantined until the separate contamination gate passes.",
        ]
    elif adapter_id == "external_repair_trace_fail_to_pass_adapter":
        operation = "private_external_repair_trace_adapter_materialization"
        instructions = [
            "Join fail-to-pass repair evidence to same-source lineage and verifier identity.",
            "Return comparable before/after verifier proof statuses without raw command or output text.",
        ]
    elif adapter_id == "selected_test_transition_root_batch_non_web_first":
        operation = "private_selected_test_transition_root_materialization"
        instructions = [
            "Materialize selected-test transition roots with exact verifier/test identity hashes.",
            "Prove exercised versus not-exercised status without exposing private test names or outputs.",
        ]
    elif adapter_id == "web_openhands_llama_private_execution_joiner":
        operation = "private_web_execution_joiner_materialization"
        instructions = [
            "Join web execution evidence to canonical state/action records.",
            "Exclude heldout roots and public benchmark identity leakage before projection.",
        ]
    else:
        operation = "private_source_adapter_materialization"
        instructions = [
            "Materialize same-source transition candidates from authorized private refs.",
            "Derive root lineage and split group before review or materialization.",
        ]
    return {
        "operation_name": operation,
        "required_executor_boundary": "private_authorized_executor_only_not_stage12446",
        "instructions": instructions,
    }


def expected_return_file(request: dict[str, Any]) -> dict[str, str]:
    kind = safe_slug(str(request.get("request_kind") or "unknown"))
    request_hash = str(request.get("execution_request_id_hash") or stable_hash(request))
    adapter = safe_slug(str(request.get("adapter_request_id") or request.get("stage12413_request_hash") or "request"))
    filename = f"{kind}__{adapter}__{request_hash}__public_return.json"
    location = STAGE12445_OUT / "external_returns" / filename
    return {
        "expected_return_file_name": filename,
        "expected_stage12445_ingest_location": rel(location),
        "expected_file_format": "single JSON object or JSONL rows matching safe_public_return_schema",
    }


def safe_public_return_schema(schema: dict[str, Any]) -> dict[str, Any]:
    required_slots = [str(slot) for slot in schema.get("required_return_slots", [])]
    admission_slots = [str(slot) for slot in schema.get("admission_required_slots", [])]
    return {
        "schema_name": schema.get("schema_name") or "adapter_executor_return_public_safe_v1",
        "public_value_policy": "hashes_enums_counts_status_classes_only_no_raw_private_values",
        "additional_properties_allowed": False,
        "required_return_slots": required_slots,
        "admission_required_slots": admission_slots,
        "non_empty_hash_fields_required": schema.get("non_empty_hash_fields_required") or [],
        "required_status_enums": schema.get("required_status_enums") or {},
        "required_top_level_metadata": [
            "schema_name",
            "source_execution_request_id_hash",
            "request_kind",
            "return_row_hash",
            "slot_status",
            "provided_slots",
        ],
        "forbidden_public_payloads": [
            "raw text",
            "private locators",
            "paths",
            "urls",
            "commands",
            "terminal output",
            "diffs",
            "patch bodies",
            "source code bodies",
            "issue bodies",
        ],
        "level3_counting_allowed_in_return_file": False,
        "admission_requires_stage12445_ingest_gate": True,
    }


def build_plan_row(request: dict[str, Any], expected_return: dict[str, Any], schema: dict[str, Any]) -> dict[str, Any]:
    manifest_request = {
        **request,
        "execution_request_id_hash": expected_return.get("execution_request_id_hash"),
        "request_kind": expected_return.get("request_kind"),
    }
    required_slots = [str(slot) for slot in request.get("required_return_slots") or schema.get("required_return_slots", [])]
    admission_slots = [str(slot) for slot in request.get("admission_required_slots") or schema.get("admission_required_slots", [])]
    return {
        "plan_row_id_hash": stable_hash({"plan": manifest_request, "expected_return_path": expected_return.get("expected_return_path")}),
        "source_execution_request_id_hash": expected_return.get("execution_request_id_hash"),
        "request_kind": expected_return.get("request_kind"),
        "adapter_request_id": request.get("adapter_request_id"),
        "expected_return_path": expected_return.get("expected_return_path"),
        "expected_return_schema": expected_return.get("expected_return_schema"),
        "expected_file_format": "JSONL rows matching adapter_executor_return_public_safe_v1 at the exact Stage12444 path",
        "required_private_operation": request_private_operation(manifest_request),
        "required_proof_slots": required_slots,
        "admission_required_proof_slots": admission_slots,
        "proof_slot_count": len(required_slots),
        "admission_required_proof_slot_count": len(admission_slots),
        "safe_public_return_schema_name": schema.get("schema_name"),
        "return_file_status": "missing_requires_private_executor_materialization",
        "stage12446_execution_status": "not_executed_planning_only",
        "training_allowed": False,
        "admission_allowed": False,
    }


def build_artifact() -> tuple[dict[str, Any], list[dict[str, Any]], dict[str, Any], dict[str, Any]]:
    stage12444_summary = read_json(STAGE12444_SUMMARY)
    stage12445_summary = read_json(STAGE12445_SUMMARY)
    schema = read_json(EXECUTOR_RETURN_SCHEMA)
    adapter_requests = read_jsonl(ADAPTER_REQUESTS)
    open_swe_requests = read_jsonl(OPEN_SWE_REQUESTS)
    expected_manifest = read_jsonl(EXPECTED_RETURN_MANIFEST)
    requests = adapter_requests + open_swe_requests
    requests_by_id = {
        str(row.get("execution_request_id_hash") or ""): row
        for row in requests
        if row.get("execution_request_id_hash")
    }

    plan_rows = [
        build_plan_row(requests_by_id.get(str(expected.get("execution_request_id_hash") or ""), {}), expected, schema)
        for expected in expected_manifest
    ]
    request_kind_counts = Counter(str(row.get("request_kind") or "unknown") for row in expected_manifest)
    planned_by_kind = Counter(str(row.get("request_kind") or "unknown") for row in plan_rows)
    missing_by_kind = stage12445_summary.get("return_ingest_counters", {}).get("missing_return_count_by_kind", {})
    if not isinstance(missing_by_kind, dict):
        missing_by_kind = {}

    safe_schema = safe_public_return_schema(schema)
    schema_issues: list[str] = []
    missing_request_ids = [
        str(row.get("execution_request_id_hash") or "")
        for row in expected_manifest
        if str(row.get("execution_request_id_hash") or "") not in requests_by_id
    ]
    request_kind_mismatches = [
        str(row.get("execution_request_id_hash") or "")
        for row in expected_manifest
        if str(row.get("execution_request_id_hash") or "") in requests_by_id
        and str(requests_by_id[str(row.get("execution_request_id_hash") or "")].get("request_kind") or "unknown")
        != str(row.get("request_kind") or "unknown")
    ]
    plan_path_mismatches = [
        str(row.get("source_execution_request_id_hash") or "")
        for row, expected in zip(plan_rows, expected_manifest)
        if row.get("expected_return_path") != expected.get("expected_return_path")
    ]
    if len(expected_manifest) != int(stage12445_summary.get("return_ingest_counters", {}).get("expected_return_count", -1)):
        schema_issues.append("request_count_mismatch_with_stage12445_expected_return_count")
    if len(expected_manifest) != len(requests):
        schema_issues.append("expected_return_manifest_count_mismatch_with_stage12444_requests")
    if missing_request_ids:
        schema_issues.append("expected_return_manifest_request_id_missing_from_stage12444_requests")
    if request_kind_mismatches:
        schema_issues.append("expected_return_manifest_request_kind_mismatch_with_stage12444_requests")
    if plan_path_mismatches:
        schema_issues.append("production_plan_expected_return_path_mismatch_with_stage12444_manifest")
    if any(plan_row.get("return_file_status") != "missing_requires_private_executor_materialization" for plan_row in plan_rows):
        schema_issues.append("non_missing_plan_row_status")
    if not safe_schema["required_return_slots"] or not safe_schema["admission_required_slots"]:
        schema_issues.append("safe_public_return_schema_missing_required_slots")
    if stage12445_summary.get("level3_candidate_count") != 0:
        schema_issues.append("stage12445_level3_candidate_count_not_zero_fail_closed")
    if stage12445_summary.get("training_allowed") is not False or stage12445_summary.get("admission_allowed") is not False:
        schema_issues.append("stage12445_training_or_admission_not_blocked")

    artifact = {
        "stage": STAGE,
        "record_type": "adapter_return_production_plan_public_safe_v1",
        "decision": "production_plan_ready_for_private_executor_no_execution_no_admission",
        **ZERO_COUNTERS,
        "expected_return_count": len(expected_manifest),
        "planned_missing_return_file_count": len(plan_rows),
        "found_return_file_count_from_stage12445": stage12445_summary.get("return_ingest_counters", {}).get("found_return_file_count", 0),
        "missing_return_file_count_from_stage12445": stage12445_summary.get("return_ingest_counters", {}).get("missing_return_file_count", len(plan_rows)),
        "request_kind_counts": dict(sorted(request_kind_counts.items())),
        "planned_missing_return_count_by_kind": dict(sorted(planned_by_kind.items())),
        "missing_return_count_by_kind": dict(sorted(planned_by_kind.items())),
        "stage12445_missing_return_count_by_kind": dict(sorted((str(key), int(value)) for key, value in missing_by_kind.items())),
        "proof_slot_count": len(safe_schema["required_return_slots"]),
        "admission_required_proof_slot_count": len(safe_schema["admission_required_slots"]),
        "safe_public_return_schema_hash": stable_hash(safe_schema),
        "production_plan_path": rel(OUT / "missing_return_production_plan.jsonl"),
        "safe_public_return_schema_path": rel(OUT / "safe_public_return_schema.json"),
        "source_fingerprints": {
            "stage12444_summary_sha256_24": file_hash(STAGE12444_SUMMARY),
            "stage12445_summary_sha256_24": file_hash(STAGE12445_SUMMARY),
            "adapter_execution_requests_sha256_24": file_hash(ADAPTER_REQUESTS),
            "open_swe_authoritative_replay_batch_sha256_24": file_hash(OPEN_SWE_REQUESTS),
            "executor_return_schema_sha256_24": file_hash(EXECUTOR_RETURN_SCHEMA),
            "expected_return_manifest_sha256_24": file_hash(EXPECTED_RETURN_MANIFEST),
        },
        "source_stage_gate_status": {
            "stage12444_guardrail_passed": stage12444_summary.get("guardrail_scan_passed") is True,
            "stage12444_training_blocked": stage12444_summary.get("training_allowed") is False,
            "stage12444_admission_blocked": stage12444_summary.get("admission_allowed") is False,
            "stage12445_guardrail_passed": stage12445_summary.get("guardrail_scan_passed") is True,
            "stage12445_training_blocked": stage12445_summary.get("training_allowed") is False,
            "stage12445_admission_blocked": stage12445_summary.get("admission_allowed") is False,
            "stage12445_zero_level3_candidates": stage12445_summary.get("level3_candidate_count") == 0,
        },
        "public_output_policy": "planning_only_hash_status_count_schema_file_names_no_private_values",
        "claim_boundary": "Plans missing return production only. Stage12446 does not execute private replay, inspect private data, fabricate returns, admit rows, or emit training rows.",
        "schema_issue_count": len(schema_issues),
        "schema_issues": schema_issues,
        "guardrail_scan": {},
        "guardrail_scan_passed": False,
        "raw_leak_count": 0,
        "overclaim_count": 0,
        "summary_hash": "pending",
    }

    guardrail_issues = list(schema_issues)
    if not all(artifact["source_stage_gate_status"].values()):
        guardrail_issues.append("source_stage_gate_status_not_all_true")
    for key, expected in ZERO_COUNTERS.items():
        if artifact.get(key) != expected:
            guardrail_issues.append(f"zero_counter_mismatch:{key}")
    if dict(sorted(planned_by_kind.items())) != dict(sorted((str(key), int(value)) for key, value in missing_by_kind.items())):
        guardrail_issues.append("planned_missing_counts_do_not_match_stage12445_missing_counts")
    public_payloads = {
        "artifact": artifact,
        "missing_return_production_plan": plan_rows,
        "safe_public_return_schema": safe_schema,
    }
    for name, payload in public_payloads.items():
        guardrail_issues.extend(scan_public(name, payload))

    guardrail_scan = {
        "scan_passed": not guardrail_issues,
        "issue_count": len(set(guardrail_issues)),
        "issues": sorted(set(guardrail_issues)),
        "raw_leak_count": len({issue for issue in guardrail_issues if "raw_public_leak" in issue or "forbidden_public_key" in issue}),
        "overclaim_count": len({issue for issue in guardrail_issues if ":overclaim:" in issue}),
        "scan_scope": "stage12446_public_safe_return_production_plan",
        "fail_closed_on_issue": True,
    }
    artifact["guardrail_scan"] = guardrail_scan
    artifact["guardrail_scan_passed"] = guardrail_scan["scan_passed"]
    artifact["raw_leak_count"] = guardrail_scan["raw_leak_count"]
    artifact["overclaim_count"] = guardrail_scan["overclaim_count"]
    artifact["summary_hash"] = stable_hash({key: value for key, value in artifact.items() if key != "summary_hash"})
    return artifact, plan_rows, safe_schema, guardrail_scan


def main() -> None:
    artifact, plan_rows, safe_schema, guardrail_scan = build_artifact()
    OUT.mkdir(parents=True, exist_ok=True)
    write_json(OUT / f"{STAGE}.json", artifact)
    write_json(OUT / "summary.json", artifact)
    write_json(SUMMARY, artifact)
    write_jsonl(OUT / "missing_return_production_plan.jsonl", plan_rows)
    write_jsonl(OUT / "expected_return_manifest_plan.jsonl", plan_rows)
    write_json(OUT / "safe_public_return_schema.json", safe_schema)
    write_json(OUT / "guardrail_scan.json", guardrail_scan)
    print(json.dumps({
        "stage": artifact["stage"],
        "decision": artifact["decision"],
        "expected_return_count": artifact["expected_return_count"],
        "planned_missing_return_file_count": artifact["planned_missing_return_file_count"],
        "planned_missing_return_count_by_kind": artifact["planned_missing_return_count_by_kind"],
        "training_allowed": artifact["training_allowed"],
        "admission_allowed": artifact["admission_allowed"],
        "emitted_training_rows": artifact["emitted_training_rows"],
        "level3_candidate_count": artifact["level3_candidate_count"],
        "guardrail_scan_passed": artifact["guardrail_scan_passed"],
        "raw_leak_count": artifact["raw_leak_count"],
        "overclaim_count": artifact["overclaim_count"],
        "schema_issue_count": artifact["schema_issue_count"],
    }, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
