#!/usr/bin/env python3
"""Build Stage12447 adapter executor work-order shards.

This stage turns the Stage12446 missing-return production plan into bounded,
per-adapter work orders. It does not execute private replay, inspect raw traces,
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
STAGE = "stage12447_adapter_executor_work_order_shards"
OUT = ROOT / "runs/local/artifacts" / STAGE
SUMMARY = ROOT / "runs/summaries" / f"{STAGE}.json"

STAGE12444 = "stage12444_adapter_execution_request_manifest"
STAGE12445 = "stage12445_adapter_execution_return_ingest_and_level3_gate"
STAGE12446 = "stage12446_adapter_return_production_plan"
STAGE12444_OUT = ROOT / "runs/local/artifacts" / STAGE12444
STAGE12446_OUT = ROOT / "runs/local/artifacts" / STAGE12446
STAGE12444_SUMMARY = ROOT / "runs/summaries" / f"{STAGE12444}.json"
STAGE12445_SUMMARY = ROOT / "runs/summaries" / f"{STAGE12445}.json"
STAGE12446_SUMMARY = ROOT / "runs/summaries" / f"{STAGE12446}.json"

EXPECTED_RETURN_MANIFEST = STAGE12444_OUT / "expected_return_manifest.jsonl"
EXECUTOR_RETURN_SCHEMA = STAGE12444_OUT / "executor_return_schema.json"
PRODUCTION_PLAN = STAGE12446_OUT / "missing_return_production_plan.jsonl"

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
    "path", "paths", "url", "urls", "uri", "command", "command_text", "commands",
    "stdout", "stderr", "output", "outputs", "diff", "patch", "patch_body", "source",
    "source_path", "source_text", "private_locator", "raw", "raw_text", "trace",
    "trace_text", "issue_body",
}
ALLOWED_KEY_CONTEXT_RE = re.compile(
    r"(policy|emitted|forbidden|required|slot|slots|schema|hash|hashes|ref|refs|class|status|proof|reason|contract|request|count|scan)",
    re.I,
)
RAW_LEAK_RE = re.compile(
    r"https?://|www\.|diff --git|@@ |^\+\+\+ |^--- |<<<<<<<|>>>>>>>|"
    r"(?<![A-Za-z0-9_])/(?:[A-Za-z0-9._-]+/){2,}[A-Za-z0-9._-]+|"
    r"\b(?:Traceback \(most recent call last\)|stdout:|stderr:|stack trace|terminal output:|command output:|git clone\s+\S|git apply\s+\S|curl\s+\S|bash -|sh -|python -c)\b",
    re.I | re.M,
)
OVERCLAIM_RE = re.compile(
    r"\b(?:admitted|training row|trainable|accepted row|verified repair|level-3 complete|level3 complete|patch-trace complete|execution succeeded|tests passed|replay succeeded)\b",
    re.I,
)
ALLOWED_OVERCLAIM_CONTEXT_RE = re.compile(
    r"(false|zero|none|blocked|required|future|must not|not |no |fail.closed|fail-closed|policy|guardrail|schema|contract|separate ingest|planning_only|candidate_count|admitted_rows)",
    re.I,
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


def priority_for(row: dict[str, Any]) -> tuple[int, str]:
    adapter_id = str(row.get("adapter_request_id") or "")
    kind = str(row.get("request_kind") or "")
    if adapter_id == "external_repair_trace_fail_to_pass_adapter":
        return 1, "highest_value_external_fail_to_pass_patch_effect_supply"
    if adapter_id == "selected_test_transition_root_batch_non_web_first":
        return 2, "high_value_non_web_selected_test_transition_supply"
    if adapter_id == "codex_session_private_trace_reviewer_representatives":
        return 3, "codex_session_semantic_reconstruction_scale_lane"
    if adapter_id == "web_openhands_llama_private_execution_joiner":
        return 4, "web_gap_execution_joiner_quarantined_from_eval_claims"
    if kind == "private_semantic_review":
        return 5, "representative_review_unblocks_similarity_cluster_admission_only_after_independent_proof"
    if kind == "open_swe_authoritative_replay_micro_pilot":
        return 6, "open_swe_quarantined_replay_micro_pilot_not_eval_eligible"
    return 9, "unknown_low_priority_requires_manual_triage"


def proof_slot_policy() -> dict[str, Any]:
    return {
        "must_prove": [
            "same_source_lineage_proof",
            "verifier_relevance_proof",
            "policy_label_independence_proof",
            "causal_verifier_linkage",
            "state_delta_codes",
            "state_after_summary_codes",
            "stop_continue_label",
            "protected_overlap_check",
            "leakage_check",
        ],
        "must_not_use_as_proof": [
            "candidate discovery alone",
            "same-window patch/verifier co-presence",
            "observed action family as the policy label",
            "similarity cluster membership",
            "PASS_TO_PASS as repair proof",
            "benchmark/public trace material without contamination clearance",
        ],
        "public_return_values": "hashes_enums_counts_status_classes_only",
    }


def build_work_order(row: dict[str, Any], schema: dict[str, Any]) -> dict[str, Any]:
    priority, reason = priority_for(row)
    expected_return_path = str(row.get("expected_return_path") or "")
    return {
        "work_order_id_hash": stable_hash({"work_order": row.get("source_execution_request_id_hash"), "path": expected_return_path}),
        "source_execution_request_id_hash": row.get("source_execution_request_id_hash"),
        "request_kind": row.get("request_kind"),
        "adapter_request_id": row.get("adapter_request_id"),
        "priority_rank": priority,
        "priority_reason": reason,
        "exact_expected_return_path": expected_return_path,
        "expected_return_schema": row.get("expected_return_schema") or schema.get("schema_name"),
        "expected_file_format": row.get("expected_file_format"),
        "required_private_operation": row.get("required_private_operation"),
        "safe_public_return_schema_path": "runs/local/artifacts/stage12446_adapter_return_production_plan/safe_public_return_schema.json",
        "required_proof_slots": row.get("required_proof_slots") or schema.get("required_return_slots") or [],
        "admission_required_proof_slots": row.get("admission_required_proof_slots") or schema.get("admission_required_slots") or [],
        "proof_slot_policy": proof_slot_policy(),
        "executor_contract": {
            "private_raw_inspection_allowed_only_inside_executor": True,
            "public_return_must_not_include_raw_paths_commands_outputs_sources_or_diffs": True,
            "write_return_only_to_exact_expected_return_path": True,
            "one_return_row_must_reference_this_source_execution_request_id_hash": True,
            "stage12445_is_the_only_admission_gate": True,
            "stage12447_admits_nothing": True,
        },
        "target_yield_semantics": "executor may return zero or more reviewed public-safe rows; all countable supply remains zero until Stage12445 validates them",
        "training_allowed": False,
        "admission_allowed": False,
    }


def build_artifact() -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    stage12444 = read_json(STAGE12444_SUMMARY)
    stage12445 = read_json(STAGE12445_SUMMARY)
    stage12446 = read_json(STAGE12446_SUMMARY)
    schema = read_json(EXECUTOR_RETURN_SCHEMA)
    manifest = read_jsonl(EXPECTED_RETURN_MANIFEST)
    plan = read_jsonl(PRODUCTION_PLAN)
    manifest_by_id = {str(row.get("execution_request_id_hash")): row for row in manifest}
    plan_by_id = {str(row.get("source_execution_request_id_hash")): row for row in plan}
    schema_issues: list[str] = []
    if set(manifest_by_id) != set(plan_by_id):
        schema_issues.append("manifest_plan_request_id_set_mismatch")
    for request_id, manifest_row in manifest_by_id.items():
        plan_row = plan_by_id.get(request_id, {})
        if manifest_row.get("expected_return_path") != plan_row.get("expected_return_path"):
            schema_issues.append(f"expected_return_path_mismatch:{request_id}")
        if not manifest_row.get("expected_return_path"):
            schema_issues.append(f"blank_expected_return_path:{request_id}")
        if manifest_row.get("expected_return_schema") != schema.get("schema_name"):
            schema_issues.append(f"expected_schema_mismatch:{request_id}")
    work_orders = sorted((build_work_order(row, schema) for row in plan), key=lambda r: (r["priority_rank"], str(r.get("adapter_request_id") or ""), str(r.get("source_execution_request_id_hash") or "")))
    batch_shards: list[dict[str, Any]] = []
    for priority, rows in sorted(((rank, [r for r in work_orders if r["priority_rank"] == rank]) for rank in {r["priority_rank"] for r in work_orders}), key=lambda x: x[0]):
        batch_shards.append({
            "batch_shard_id_hash": stable_hash({"priority": priority, "rows": [r["work_order_id_hash"] for r in rows]}),
            "priority_rank": priority,
            "work_order_count": len(rows),
            "work_order_id_hashes": [r["work_order_id_hash"] for r in rows],
            "execution_mode": "private_executor_return_materialization_required",
            "training_allowed": False,
            "admission_allowed": False,
        })
    request_kind_counts = Counter(str(row.get("request_kind") or "unknown") for row in work_orders)
    priority_counts = Counter(str(row.get("priority_rank")) for row in work_orders)
    artifact = {
        "stage": STAGE,
        "record_type": "adapter_executor_work_order_shards_public_safe_v1",
        "decision": "work_order_shards_ready_for_private_executor_no_execution_no_admission",
        **ZERO_COUNTERS,
        "work_order_count": len(work_orders),
        "batch_shard_count": len(batch_shards),
        "request_kind_counts": dict(sorted(request_kind_counts.items())),
        "priority_rank_counts": dict(sorted(priority_counts.items())),
        "exact_expected_return_path_count": sum(1 for row in work_orders if row.get("exact_expected_return_path")),
        "unique_expected_return_path_count": len({row.get("exact_expected_return_path") for row in work_orders}),
        "source_stage_gate_status": {
            "stage12444_guardrail_passed": stage12444.get("guardrail_scan_passed") is True,
            "stage12445_guardrail_passed": stage12445.get("guardrail_scan_passed") is True,
            "stage12445_zero_admitted": stage12445.get("admitted_rows") == 0,
            "stage12445_request_binding_enforced": stage12445.get("return_ingest_counters", {}).get("return_file_request_binding_enforced") is True,
            "stage12446_guardrail_passed": stage12446.get("guardrail_scan_passed") is True,
            "stage12446_training_blocked": stage12446.get("training_allowed") is False,
            "stage12446_admission_blocked": stage12446.get("admission_allowed") is False,
            "stage12446_execution_blocked": stage12446.get("execution_allowed") is False,
            "stage12446_no_private_replay": stage12446.get("private_replay_executed") is False,
            "stage12446_no_raw_private_data_inspected": stage12446.get("raw_private_data_inspected") is False,
            "stage12446_no_fabricated_returns": stage12446.get("fabricated_returns") is False,
            "stage12446_zero_level3": stage12446.get("level3_candidate_count") == 0,
        },
        "source_fingerprints": {
            "stage12444_summary_sha256_24": file_hash(STAGE12444_SUMMARY),
            "stage12445_summary_sha256_24": file_hash(STAGE12445_SUMMARY),
            "stage12446_summary_sha256_24": file_hash(STAGE12446_SUMMARY),
            "expected_return_manifest_sha256_24": file_hash(EXPECTED_RETURN_MANIFEST),
            "production_plan_sha256_24": file_hash(PRODUCTION_PLAN),
            "executor_return_schema_sha256_24": file_hash(EXECUTOR_RETURN_SCHEMA),
        },
        "work_order_shards_path": rel(OUT / "adapter_executor_work_order_shards.jsonl"),
        "priority_batch_manifest_path": rel(OUT / "priority_batch_manifest.jsonl"),
        "next_stage_recommendation": "stage12448_executor_shard_scale_and_admission_control_then_stage12449_private_executor_return_files_or_zero_postrun_then_stage12445_rerun",
        "schema_issue_count": len(schema_issues),
        "schema_issues": sorted(set(schema_issues)),
        "claim_boundary": "Work-order sharding only. Stage12447 does not execute private replay, inspect raw data, fabricate returns, admit rows, or emit training rows.",
        "guardrail_scan": {},
        "guardrail_scan_passed": False,
        "raw_leak_count": 0,
        "overclaim_count": 0,
        "summary_hash": "pending",
    }
    guardrail_issues = list(schema_issues)
    if not all(artifact["source_stage_gate_status"].values()):
        guardrail_issues.append("source_stage_gate_status_not_all_true")
    if artifact["exact_expected_return_path_count"] != artifact["work_order_count"]:
        guardrail_issues.append("work_order_missing_expected_return_path")
    if any(not row.get("required_private_operation") for row in work_orders):
        guardrail_issues.append("work_order_missing_required_private_operation")
    if any(not row.get("expected_file_format") for row in work_orders):
        guardrail_issues.append("work_order_missing_expected_file_format")
    if artifact["unique_expected_return_path_count"] != artifact["work_order_count"]:
        guardrail_issues.append("work_order_expected_return_paths_not_unique")
    for key, expected in ZERO_COUNTERS.items():
        if artifact.get(key) != expected:
            guardrail_issues.append(f"zero_counter_mismatch:{key}")
    for name, payload in {"artifact": artifact, "work_orders": work_orders, "batch_shards": batch_shards}.items():
        guardrail_issues.extend(scan_public(name, payload))
    guardrail_scan = {
        "scan_passed": not guardrail_issues,
        "issue_count": len(set(guardrail_issues)),
        "issues": sorted(set(guardrail_issues)),
        "raw_leak_count": len({issue for issue in guardrail_issues if "raw_public_leak" in issue or "forbidden_public_key" in issue}),
        "overclaim_count": len({issue for issue in guardrail_issues if ":overclaim:" in issue}),
        "scan_scope": "stage12447_public_safe_work_order_shards",
        "fail_closed_on_issue": True,
    }
    artifact["guardrail_scan"] = guardrail_scan
    artifact["guardrail_scan_passed"] = guardrail_scan["scan_passed"]
    artifact["raw_leak_count"] = guardrail_scan["raw_leak_count"]
    artifact["overclaim_count"] = guardrail_scan["overclaim_count"]
    artifact["summary_hash"] = stable_hash({key: value for key, value in artifact.items() if key != "summary_hash"})
    return artifact, work_orders, batch_shards, guardrail_scan


def main() -> None:
    artifact, work_orders, batch_shards, guardrail_scan = build_artifact()
    OUT.mkdir(parents=True, exist_ok=True)
    write_json(OUT / f"{STAGE}.json", artifact)
    write_json(OUT / "summary.json", artifact)
    write_json(SUMMARY, artifact)
    write_jsonl(OUT / "adapter_executor_work_order_shards.jsonl", work_orders)
    write_jsonl(OUT / "priority_batch_manifest.jsonl", batch_shards)
    write_json(OUT / "guardrail_scan.json", guardrail_scan)
    print(json.dumps({
        "stage": artifact["stage"],
        "decision": artifact["decision"],
        "work_order_count": artifact["work_order_count"],
        "batch_shard_count": artifact["batch_shard_count"],
        "exact_expected_return_path_count": artifact["exact_expected_return_path_count"],
        "unique_expected_return_path_count": artifact["unique_expected_return_path_count"],
        "training_allowed": artifact["training_allowed"],
        "admission_allowed": artifact["admission_allowed"],
        "level3_candidate_count": artifact["level3_candidate_count"],
        "guardrail_scan_passed": artifact["guardrail_scan_passed"],
        "raw_leak_count": artifact["raw_leak_count"],
        "overclaim_count": artifact["overclaim_count"],
        "schema_issue_count": artifact["schema_issue_count"],
    }, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
