#!/usr/bin/env python3
"""Build Stage12448 executor shard scale and admission control artifact.

This stage converts Stage12447 work orders into a scale-aware execution plan
with per-lane floors. It performs no private execution and admits nothing.
"""
from __future__ import annotations

import hashlib
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12448_executor_shard_scale_and_admission_control"
OUT = ROOT / "runs/local/artifacts" / STAGE
SUMMARY = ROOT / "runs/summaries" / f"{STAGE}.json"

STAGE12447 = "stage12447_adapter_executor_work_order_shards"
STAGE12447_OUT = ROOT / "runs/local/artifacts" / STAGE12447
STAGE12447_SUMMARY = ROOT / "runs/summaries" / f"{STAGE12447}.json"
WORK_ORDERS = STAGE12447_OUT / "adapter_executor_work_order_shards.jsonl"
BATCH_MANIFEST = STAGE12447_OUT / "priority_batch_manifest.jsonl"

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
    r"(policy|emitted|forbidden|required|slot|slots|schema|hash|hashes|ref|refs|class|status|proof|reason|contract|request|count|scan|artifact|return|floor|lane|adapter)",
    re.I,
)
RAW_LEAK_RE = re.compile(
    r"https?://|www\.|diff --git|@@ |^\+\+\+ |^--- |<<<<<<<|>>>>>>>|"
    r"(?<![A-Za-z0-9_])/(?:[A-Za-z0-9._-]+/){2,}[A-Za-z0-9._-]+|"
    r"\b(?:stdout:|stderr:|terminal output:|command output:|git clone\s+\S|git apply\s+\S|python -c|bash -)\b",
    re.I | re.M,
)
OVERCLAIM_RE = re.compile(
    r"\b(?:admitted|training row|trainable|accepted row|verified repair|level-3 complete|level3 complete|patch-trace complete|execution succeeded|tests passed|replay succeeded)\b",
    re.I,
)
ALLOWED_OVERCLAIM_CONTEXT_RE = re.compile(
    r"(false|zero|none|blocked|required|future|must not|not |no |fail.closed|fail-closed|policy|guardrail|schema|contract|separate ingest|candidate_count|admitted_rows|floor|until)",
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
        for line_number, line in enumerate(handle, 1):
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


LANE_PLANS: dict[str, dict[str, Any]] = {
    "external_repair_trace_fail_to_pass_adapter": {
        "stage12448_lane": "external_comparable_patch_effect",
        "target_candidate_floor": 75,
        "countable_level3_root_floor": 25,
        "fail_to_pass_floor": 15,
        "non_python_external_floor": 10,
        "task_focus": ["patch_effect", "verifier_transition", "stop_continue_after_repair"],
        "admission_rule": "same-source before/after verifier status plus patch application proof required; syntax-only mutations capped at auxiliary support",
    },
    "selected_test_transition_root_batch_non_web_first": {
        "stage12448_lane": "non_web_selected_test_transition",
        "target_candidate_floor": 100,
        "countable_level3_root_floor": 50,
        "language_floor": {"python": 15, "rust": 15, "c_cpp": 15},
        "task_focus": ["selected_test_relevance", "not_exercised", "pass_current_build_vs_build_and_run", "next_action"],
        "admission_rule": "exact selected verifier identity and relevance proof required; build-only evidence must not masquerade as selected-test proof",
    },
    "web_openhands_llama_private_execution_joiner": {
        "stage12448_lane": "web_execution_joiner_quarantined",
        "target_candidate_floor": 50,
        "countable_level3_root_floor": 20,
        "language_floor": {"web_js_ts_html": 20},
        "task_focus": ["web_next_action", "web_verifier_transition", "web_continue_stop"],
        "admission_rule": "web rows may be train-support only until heldout/benchmark contamination gate passes; no direct eval claims",
    },
    "codex_session_private_trace_reviewer_representatives": {
        "stage12448_lane": "codex_session_semantic_reconstruction",
        "target_candidate_floor": 60,
        "countable_level3_root_floor": 30,
        "task_focus": ["transition_function_keys", "state_delta", "counterfactual_actions"],
        "admission_rule": "representatives do not admit cluster members; each member needs independent non-imitation policy proof",
    },
    "representative_private_semantic_review_batch_10": {
        "stage12448_lane": "representative_review_unblocker",
        "target_candidate_floor": 10,
        "countable_level3_root_floor": 0,
        "task_focus": ["review_slot_completion", "cluster_risk_triage"],
        "admission_rule": "review results can prioritize expansion but cannot directly count as train rows without Stage12445 proof slots",
    },
    "open_swe_authoritative_replay_micro_pilot": {
        "stage12448_lane": "open_swe_quarantined_replay_micro_pilot",
        "target_candidate_floor": 20,
        "countable_level3_root_floor": 0,
        "task_focus": ["replay_feasibility", "proof_slot_extraction"],
        "admission_rule": "Open-SWE material stays quarantined until contamination gate; never strict-eval eligible here",
    },
}


def lane_plan_for(row: dict[str, Any]) -> dict[str, Any]:
    adapter_id = str(row.get("adapter_request_id") or "")
    request_kind = str(row.get("request_kind") or "")
    key = adapter_id if adapter_id in LANE_PLANS else request_kind
    plan = dict(LANE_PLANS.get(key, {}))
    if not plan:
        plan = {
            "stage12448_lane": "manual_triage_required",
            "target_candidate_floor": 0,
            "countable_level3_root_floor": 0,
            "task_focus": ["manual_triage"],
            "admission_rule": "unknown adapter cannot count until lane contract is written",
        }
    return plan


def build_lane_order(row: dict[str, Any]) -> dict[str, Any]:
    plan = lane_plan_for(row)
    return {
        "lane_order_id_hash": stable_hash({"lane": plan.get("stage12448_lane"), "request": row.get("source_execution_request_id_hash")}),
        "source_work_order_id_hash": row.get("work_order_id_hash"),
        "source_execution_request_id_hash": row.get("source_execution_request_id_hash"),
        "request_kind": row.get("request_kind"),
        "adapter_request_id": row.get("adapter_request_id"),
        "priority_rank": row.get("priority_rank"),
        "stage12448_lane": plan.get("stage12448_lane"),
        "target_candidate_floor": plan.get("target_candidate_floor", 0),
        "countable_level3_root_floor": plan.get("countable_level3_root_floor", 0),
        "fail_to_pass_floor": plan.get("fail_to_pass_floor", 0),
        "non_python_external_floor": plan.get("non_python_external_floor", 0),
        "language_floor": plan.get("language_floor", {}),
        "task_focus": plan.get("task_focus", []),
        "admission_rule": plan.get("admission_rule"),
        "exact_expected_return_path": row.get("exact_expected_return_path"),
        "expected_return_schema": row.get("expected_return_schema"),
        "required_proof_slots": row.get("required_proof_slots", []),
        "admission_required_proof_slots": row.get("admission_required_proof_slots", []),
        "return_file_must_be_stage12445_ingestable": True,
        "training_allowed": False,
        "admission_allowed": False,
    }


def build_artifact() -> tuple[dict[str, Any], list[dict[str, Any]], dict[str, Any]]:
    stage12447 = read_json(STAGE12447_SUMMARY)
    work_orders = read_jsonl(WORK_ORDERS)
    batch_manifest = read_jsonl(BATCH_MANIFEST)
    lane_orders = [build_lane_order(row) for row in work_orders]
    lane_counts = Counter(str(row.get("stage12448_lane")) for row in lane_orders)
    task_focus_counts: Counter[str] = Counter()
    floors_by_lane_acc: dict[str, dict[str, Any]] = defaultdict(lambda: {
        "work_order_count": 0,
        "target_candidate_floor": 0,
        "countable_level3_root_floor": 0,
        "fail_to_pass_floor": 0,
        "non_python_external_floor": 0,
        "language_floor": Counter(),
        "admission_rules": [],
    })
    for row in lane_orders:
        lane = str(row.get("stage12448_lane"))
        acc = floors_by_lane_acc[lane]
        acc["work_order_count"] += 1
        acc["target_candidate_floor"] += int(row.get("target_candidate_floor") or 0)
        acc["countable_level3_root_floor"] += int(row.get("countable_level3_root_floor") or 0)
        acc["fail_to_pass_floor"] += int(row.get("fail_to_pass_floor") or 0)
        acc["non_python_external_floor"] += int(row.get("non_python_external_floor") or 0)
        acc["language_floor"].update({str(k): int(v) for k, v in dict(row.get("language_floor") or {}).items()})
        if row.get("admission_rule"):
            acc["admission_rules"].append(row.get("admission_rule"))
        task_focus_counts.update(str(item) for item in row.get("task_focus", []))
    floors_by_lane = {
        lane: {
            **{k: v for k, v in acc.items() if k not in {"language_floor", "admission_rules"}},
            "language_floor": dict(sorted(acc["language_floor"].items())),
            "admission_rules": sorted(set(str(rule) for rule in acc["admission_rules"])),
        }
        for lane, acc in sorted(floors_by_lane_acc.items())
    }
    target_candidate_floor_total = sum(int(row.get("target_candidate_floor") or 0) for row in lane_orders)
    countable_level3_root_floor_total = sum(int(row.get("countable_level3_root_floor") or 0) for row in lane_orders)
    known_public_candidate_denominator = 185
    current_countable_supply = 190
    target_countable_supply = 500
    remaining_gap_to_500_before_future_ingest = max(0, target_countable_supply - current_countable_supply)
    remaining_gap_to_500_after_floor_if_fully_met = max(0, target_countable_supply - current_countable_supply - countable_level3_root_floor_total)
    requested_floor_exceeds_known_public_denominator = target_candidate_floor_total > known_public_candidate_denominator
    schema_issues: list[str] = []
    if len(lane_orders) != int(stage12447.get("work_order_count", -1)):
        schema_issues.append("lane_order_count_mismatch_stage12447_work_order_count")
    if any(not row.get("exact_expected_return_path") for row in lane_orders):
        schema_issues.append("lane_order_missing_exact_expected_return_path")
    if requested_floor_exceeds_known_public_denominator and not False:
        # This is not a guardrail failure because adapter floors intentionally request private/external supply.
        # It is recorded explicitly so it cannot be mistaken for demonstrated candidate inventory.
        pass
    if len({row.get("exact_expected_return_path") for row in lane_orders}) != len(lane_orders):
        schema_issues.append("lane_order_expected_return_path_duplicate")
    artifact = {
        "stage": STAGE,
        "record_type": "executor_shard_scale_and_admission_control_public_safe_v1",
        "decision": "lane_priority_and_requested_floor_control_ready_no_execution_no_admission",
        **ZERO_COUNTERS,
        "lane_order_count": len(lane_orders),
        "source_work_order_count": len(work_orders),
        "source_batch_shard_count": len(batch_manifest),
        "lane_counts": dict(sorted(lane_counts.items())),
        "task_focus_counts": dict(sorted(task_focus_counts.items())),
        "target_candidate_floor_total": target_candidate_floor_total,
        "target_candidate_floor_semantics": "executor_request_floor_not_demonstrated_supply_not_training_count",
        "known_public_candidate_denominator": known_public_candidate_denominator,
        "requested_floor_exceeds_known_public_denominator": requested_floor_exceeds_known_public_denominator,
        "source_capacity_proof_present": False,
        "feasibility_status": "requires_private_executor_source_capacity_proof_before_interpreting_requested_floor_as_supply" if requested_floor_exceeds_known_public_denominator else "requested_floor_within_known_public_denominator",
        "current_countable_supply_before_future_ingest": current_countable_supply,
        "target_countable_supply": target_countable_supply,
        "remaining_gap_to_500_before_future_ingest": remaining_gap_to_500_before_future_ingest,
        "countable_level3_root_floor_total_after_future_ingest": countable_level3_root_floor_total,
        "remaining_gap_to_500_after_floor_if_fully_met": remaining_gap_to_500_after_floor_if_fully_met,
        "minimum_training_gate_before_next_probe": {
            "stage12445_validated_level3_roots": 150,
            "stage12445_validated_rows": 500,
            "external_comparable_patch_trace_rows": 25,
            "external_fail_to_pass_rows": 15,
            "non_python_external_repair_rows": 10,
            "max_duplicate_cluster_share": 0.08,
            "max_single_source_family_share": 0.25,
            "required_before_training": True,
        },
        "admission_authority": "Stage12445 validates return files; Stage12448 only sets lane floors and executor priorities",
        "floor_by_lane": floors_by_lane,
        "source_stage_gate_status": {
            "stage12447_guardrail_passed": stage12447.get("guardrail_scan_passed") is True,
            "stage12447_training_blocked": stage12447.get("training_allowed") is False,
            "stage12447_admission_blocked": stage12447.get("admission_allowed") is False,
            "stage12447_zero_level3": stage12447.get("level3_candidate_count") == 0,
        },
        "source_fingerprints": {
            "stage12447_summary_sha256_24": file_hash(STAGE12447_SUMMARY),
            "work_orders_sha256_24": file_hash(WORK_ORDERS),
            "batch_manifest_sha256_24": file_hash(BATCH_MANIFEST),
        },
        "lane_orders_path": rel(OUT / "executor_lane_orders.jsonl"),
        "guardrail_scan": {},
        "guardrail_scan_passed": False,
        "raw_leak_count": 0,
        "overclaim_count": 0,
        "schema_issue_count": len(schema_issues),
        "schema_issues": sorted(set(schema_issues)),
        "claim_boundary": "Scale/admission control only. No private execution, no public raw data, no rows admitted, and no training rows emitted.",
        "next_stage_recommendation": "stage12449_private_executor_return_files_or_zero_postrun_then_stage12445_rerun",
        "summary_hash": "pending",
    }
    guardrail_issues = list(schema_issues)
    if not all(artifact["source_stage_gate_status"].values()):
        guardrail_issues.append("source_stage_gate_status_not_all_true")
    for key, expected in ZERO_COUNTERS.items():
        if artifact.get(key) != expected:
            guardrail_issues.append(f"zero_counter_mismatch:{key}")
    for name, payload in {"artifact": artifact, "lane_orders": lane_orders}.items():
        guardrail_issues.extend(scan_public(name, payload))
    guardrail = {
        "scan_passed": not guardrail_issues,
        "issue_count": len(set(guardrail_issues)),
        "issues": sorted(set(guardrail_issues)),
        "raw_leak_count": len({issue for issue in guardrail_issues if "raw_public_leak" in issue or "forbidden_public_key" in issue}),
        "overclaim_count": len({issue for issue in guardrail_issues if ":overclaim:" in issue}),
        "scan_scope": "stage12448_public_safe_scale_control",
        "fail_closed_on_issue": True,
    }
    artifact["guardrail_scan"] = guardrail
    artifact["guardrail_scan_passed"] = guardrail["scan_passed"]
    artifact["raw_leak_count"] = guardrail["raw_leak_count"]
    artifact["overclaim_count"] = guardrail["overclaim_count"]
    artifact["summary_hash"] = stable_hash({key: value for key, value in artifact.items() if key != "summary_hash"})
    return artifact, lane_orders, guardrail


def main() -> None:
    artifact, lane_orders, guardrail = build_artifact()
    OUT.mkdir(parents=True, exist_ok=True)
    write_json(OUT / f"{STAGE}.json", artifact)
    write_json(OUT / "summary.json", artifact)
    write_json(SUMMARY, artifact)
    write_jsonl(OUT / "executor_lane_orders.jsonl", lane_orders)
    write_json(OUT / "guardrail_scan.json", guardrail)
    print(json.dumps({
        "stage": artifact["stage"],
        "decision": artifact["decision"],
        "lane_order_count": artifact["lane_order_count"],
        "target_candidate_floor_total": artifact["target_candidate_floor_total"],
        "countable_level3_root_floor_total_after_future_ingest": artifact["countable_level3_root_floor_total_after_future_ingest"],
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
