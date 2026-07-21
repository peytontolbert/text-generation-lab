#!/usr/bin/env python3
"""Build Stage12407 prioritized adapter materialization worklist.

This stage consumes only the safe metadata emitted by Stage12406. It emits an
actionable, capped worklist for later materialization/execution stages, but it
does not admit training or eval rows, expose raw content, or run replay.
"""
from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12407_prioritized_adapter_materialization_worklist"
INPUT_CANDIDATES = (
    ROOT
    / "runs/local/artifacts/stage12406_transition_source_expansion_preflight/source_adapter_candidates.jsonl"
)
INPUT_SUMMARY = ROOT / "runs/summaries/stage12406_transition_source_expansion_preflight.json"
OUT = ROOT / "runs/local/artifacts" / STAGE
SUMMARY = ROOT / "runs/summaries" / f"{STAGE}.json"

WORKLIST_NAME = "prioritized_adapter_materialization_worklist.jsonl"
LOCAL_SUMMARY_NAME = "prioritized_adapter_materialization_worklist_summary.json"
ACTION_COUNTS_NAME = "recommended_next_action_counts.json"
FAMILY_COUNTS_NAME = "selected_source_family_counts.json"
GUARDRAIL_NAME = "guardrail_scan.json"

MAX_WORK_ITEMS = 40
MAX_PER_SOURCE_FAMILY = 8
MIN_DIVERSE_FAMILIES = 5

ALLOWED_TARGET_TIERS = {
    "replay_request_pending",
    "replay_calibrated_supervision",
    "level_1_verifier_only_no_patch",
    "level_2_patch_context_no_execution",
    "level_3_single_step_closed_loop_candidate",
}

ALLOWED_ACTIONS = {
    "execute_replay_request",
    "materialize_selected_test_verifier_logs",
    "segment_codex_session_windows",
    "extract_long_context_retrieval_context",
    "hydrate_verifier_observation_status",
    "quarantine_review",
    "skip_sealed_eval",
}

RAW_CONTENT_POLICY: dict[str, bool] = {
    "raw_trajectory_text_emitted": False,
    "raw_commands_emitted": False,
    "raw_outputs_emitted": False,
    "raw_patches_emitted": False,
    "source_text_emitted": False,
    "absolute_paths_emitted": False,
    "urls_emitted": False,
    "issue_bodies_emitted": False,
    "line_contents_emitted": False,
    "patch_diffs_emitted": False,
}

ZERO_ADMISSION_FLAGS: dict[str, bool | int] = {
    "admission": False,
    "training_allowed": False,
    "training_row_count": 0,
    "eval_row_count": 0,
    "admitted_rows": 0,
    "level3_admitted": 0,
    "level4_admitted": 0,
    "patch_trace_admitted": 0,
    "repair_claim_admitted": 0,
    "strict_eval_eligible": 0,
    "source_heldout_admissible": 0,
    "level3_reconstructed_proof": 0,
    "external_comparable_patch_trace_countable": 0,
    "external_fail_to_pass_countable": 0,
    "synthetic_fixture_external_repair_countable": 0,
    "selected_test_full_repair_claim_count": 0,
    "sealed_eval_train_overlap_count": 0,
}

CLAIM_BOUNDARY: dict[str, bool | str] = {
    "boundary": "prioritized_adapter_materialization_worklist_only",
    "training_rows_created": False,
    "eval_rows_created": False,
    "training_admission_claim_emitted": False,
    "eval_admission_claim_emitted": False,
    "level3_claim_emitted": False,
    "level3_admission_claim_emitted": False,
    "patch_trace_claim_emitted": False,
    "repair_claim_emitted": False,
    "source_heldout_admission_claim_emitted": False,
    "replay_executed": False,
    "proof_assistant_invoked": False,
    "raw_content_emitted": False,
    "worklist_action_is_request_only": True,
}

BASE_FORBIDDEN_USE = [
    "training_row",
    "eval_row",
    "level3_admission",
    "level3_claim",
    "patch_trace_admission",
    "repair_claim",
    "raw_content_hydration",
    "source_heldout_admission",
    "replay_result_claim",
]

BASE_BLOCKERS = [
    "blocked_worklist_only_no_rows_admitted",
    "blocked_no_training_rows_created",
    "blocked_no_eval_rows_created",
    "blocked_no_level3_admission",
    "blocked_no_patch_trace_admission",
    "blocked_raw_content_not_emitted",
    "blocked_replay_not_executed_by_stage12407",
    "fail_closed_if_uncertain",
]

ABS_PATH_RE = re.compile(r"(?<![A-Za-z0-9_])/(?:[A-Za-z0-9._-]+/){2,}[A-Za-z0-9._-]+")
URL_RE = re.compile(r"https?://|www\.", re.IGNORECASE)
MULTILINE_RE = re.compile(r"[\r\n]")
HEX_RE = re.compile(r"^[0-9a-f]{12,64}$")


def stable_hash(value: Any, n: int = 24) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:n]


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def read_jsonl(path: Path) -> tuple[list[dict[str, Any]], list[str]]:
    rows: list[dict[str, Any]] = []
    issues: list[str] = []
    if not path.exists():
        return rows, ["missing_stage12406_source_adapter_candidates"]
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            if not line.strip():
                continue
            try:
                value = json.loads(line)
            except json.JSONDecodeError:
                issues.append(f"candidate_line_{line_number}_invalid_json")
                continue
            if not isinstance(value, dict):
                issues.append(f"candidate_line_{line_number}_not_object")
                continue
            rows.append(value)
    return rows, issues


def safe_int(value: Any) -> int:
    if isinstance(value, bool):
        return 0
    if isinstance(value, int):
        return max(0, value)
    return 0


def candidate_zero_admission_safe(row: dict[str, Any], index: int) -> list[str]:
    issues: list[str] = []
    flags = row.get("zero_admission_flags") if isinstance(row.get("zero_admission_flags"), dict) else {}
    for key, expected in ZERO_ADMISSION_FLAGS.items():
        if flags.get(key) != expected:
            issues.append(f"candidate_{index}_zero_admission_flags_{key}_mismatch")
        if row.get(key) != expected:
            issues.append(f"candidate_{index}_{key}_not_false_or_zero")
    return issues


def candidate_raw_policy_safe(row: dict[str, Any], index: int) -> list[str]:
    issues: list[str] = []
    policy = row.get("raw_content_policy") if isinstance(row.get("raw_content_policy"), dict) else {}
    for key, expected in RAW_CONTENT_POLICY.items():
        if policy.get(key) is not expected:
            issues.append(f"candidate_{index}_raw_content_policy_{key}_mismatch")
    return issues


def classify_action(row: dict[str, Any]) -> tuple[str, str, float, list[str], list[str], list[str]]:
    family = str(row.get("source_family") or "unknown")
    current_tier = str(row.get("current_tier") or row.get("candidate_proof_tier_now") or "unknown")
    count = safe_int(row.get("observed_count_estimate"))
    blockers = list(BASE_BLOCKERS)
    reasons: list[str] = []

    if current_tier == "quarantine":
        blockers.append("blocked_candidate_already_quarantined")
        return (
            "quarantine_review",
            "level_1_verifier_only_no_patch",
            10.0,
            ["quarantine_only", "fail_closed_review_required"],
            ["quarantine basis reviewed using safe metadata only", "confirm no training/eval/raw-content path"],
            blockers,
        )

    if current_tier == "sealed_eval_only":
        blockers.append("blocked_sealed_eval_only_never_train")
        return (
            "skip_sealed_eval",
            "level_1_verifier_only_no_patch",
            5.0,
            ["sealed_eval_only", "skip_record_only"],
            ["sealed-eval exclusion remains explicit", "no downstream materialization task is created"],
            blockers,
        )

    if family in {"open_swe", "bears"} and current_tier == "replay_request_pending":
        blockers.extend(["blocked_replay_request_only_no_replay_result", "blocked_future_executor_must_return_safe_status_only"])
        score = 100.0 + min(count, 5000) / 500.0
        return (
            "execute_replay_request",
            "replay_calibrated_supervision",
            score,
            ["replay_request_pending", f"{family}_request_source", "high_priority_capped"],
            [
                "safe replay request reference",
                "executor provenance hash",
                "redacted verifier status class",
                "state/action/observation ref hashes",
                "no raw command/output/patch body",
            ],
            blockers,
        )

    if family == "selected_test" and count >= 3:
        blockers.extend(["blocked_selected_test_verifier_logs_not_materialized", "blocked_no_patch_trace_or_full_repair_claim"])
        score = 90.0 + min(count, 2000) / 200.0
        return (
            "materialize_selected_test_verifier_logs",
            "level_1_verifier_only_no_patch",
            score,
            ["selected_test", "adequate_count", "verifier_log_materialization"],
            [
                "selected test identity hash",
                "verifier log ref hash",
                "pass/fail/status class",
                "selected-test scope proof",
                "patch trace exclusion proof",
            ],
            blockers,
        )

    if family == "codex_session_windows":
        blockers.extend(["blocked_session_window_not_segmented", "blocked_state_action_observation_not_recovered"])
        score = 70.0 + min(count, 5000) / 250.0
        reasons = ["codex_session_windows", "segment_windows", "weak_until_state_action_observation_recovered"]
        if count >= 100:
            reasons.append("large_count_medium_high")
        return (
            "segment_codex_session_windows",
            "level_2_patch_context_no_execution",
            score,
            reasons,
            [
                "window boundary hashes",
                "state-before ref hash",
                "action ref hash",
                "observation/status ref hash",
                "stop/continue status class",
            ],
            blockers,
        )

    if family in {"strict_long_context", "multitarget_bootstrap"}:
        blockers.extend(["blocked_context_only_no_execution", "blocked_retrieval_context_not_yet_extracted"])
        score = 45.0 + min(count, 3000) / 300.0
        return (
            "extract_long_context_retrieval_context",
            "level_2_patch_context_no_execution",
            score,
            [family, "context_only", "medium_low_priority"],
            [
                "retrieval context ref hash",
                "query/window boundary hash",
                "source-family split proof",
                "sealed-eval exclusion proof",
            ],
            blockers,
        )

    blockers.extend(["blocked_generic_candidate_needs_verifier_observation_hydration", "blocked_not_high_priority_family"])
    score = 30.0 + min(count, 1000) / 500.0
    return (
        "hydrate_verifier_observation_status",
        "level_1_verifier_only_no_patch",
        score,
        ["generic_safe_metadata", "verifier_observation_status_hydration"],
        [
            "verifier observation ref hash",
            "status class",
            "verifier identity hash",
            "no patch-trace admission proof",
        ],
        blockers,
    )


def build_work_item(row: dict[str, Any], source_index: int) -> dict[str, Any]:
    action, target_tier, score, reasons, evidence, blockers = classify_action(row)
    family = str(row.get("source_family") or "unknown")
    ref_hash = str(row.get("source_ref_hash") or row.get("source_record_ref_hash") or stable_hash({"source_index": source_index}))
    work_basis = {
        "stage": STAGE,
        "source_index": source_index,
        "source_adapter_ref_hash": ref_hash,
        "action": action,
        "target": target_tier,
    }
    return {
        "stage": STAGE,
        "record_type": "prioritized_adapter_materialization_work_item",
        "work_item_id": f"{STAGE}::{stable_hash(work_basis, 20)}",
        "source_adapter_ref_hash": ref_hash,
        "source_family": family,
        "source_stage": str(row.get("source_stage") or "unknown"),
        "observed_count_estimate": safe_int(row.get("observed_count_estimate")),
        "current_proof_tier": str(row.get("current_tier") or row.get("candidate_proof_tier_now") or "unknown"),
        "target_next_proof_tier": target_tier,
        "recommended_next_action": action,
        "priority_score": round(float(score), 4),
        "priority_reason_codes": reasons,
        "required_evidence_to_upgrade": evidence,
        "allowed_use": [
            "materialization_worklist_planning_only",
            "safe_hash_count_status_metadata_only",
            "future_stage_request_routing",
        ],
        "forbidden_use": BASE_FORBIDDEN_USE,
        "blockers": sorted(set(blockers + list(row.get("blockers") or row.get("blocker_codes") or []))),
        "raw_content_policy": RAW_CONTENT_POLICY,
        "claim_boundary": CLAIM_BOUNDARY,
        "zero_admission_flags": ZERO_ADMISSION_FLAGS,
        **ZERO_ADMISSION_FLAGS,
    }


def validate_work_item(row: dict[str, Any], index: int) -> list[str]:
    issues: list[str] = []
    required = [
        "work_item_id",
        "source_adapter_ref_hash",
        "source_family",
        "source_stage",
        "observed_count_estimate",
        "current_proof_tier",
        "target_next_proof_tier",
        "recommended_next_action",
        "priority_score",
        "priority_reason_codes",
        "required_evidence_to_upgrade",
        "allowed_use",
        "forbidden_use",
        "blockers",
        "raw_content_policy",
        "claim_boundary",
        "zero_admission_flags",
    ]
    for key in required:
        if key not in row:
            issues.append(f"work_item_{index}_missing_{key}")
    if row.get("target_next_proof_tier") not in ALLOWED_TARGET_TIERS:
        issues.append(f"work_item_{index}_target_tier_not_allowed")
    if row.get("target_next_proof_tier") == "level_3_single_step_closed_loop_candidate":
        issues.append(f"work_item_{index}_level3_target_disallowed")
    if row.get("recommended_next_action") not in ALLOWED_ACTIONS:
        issues.append(f"work_item_{index}_action_not_allowed")
    if row.get("current_proof_tier") == "sealed_eval_only" and row.get("recommended_next_action") != "skip_sealed_eval":
        issues.append(f"work_item_{index}_sealed_eval_not_skip_only")
    if row.get("current_proof_tier") == "quarantine" and row.get("recommended_next_action") != "quarantine_review":
        issues.append(f"work_item_{index}_quarantine_not_review_only")
    if not isinstance(row.get("priority_score"), (int, float)):
        issues.append(f"work_item_{index}_priority_score_not_numeric")
    if not isinstance(row.get("priority_reason_codes"), list) or not row.get("priority_reason_codes"):
        issues.append(f"work_item_{index}_missing_priority_reason_codes")
    if not isinstance(row.get("required_evidence_to_upgrade"), list) or not row.get("required_evidence_to_upgrade"):
        issues.append(f"work_item_{index}_missing_required_evidence_to_upgrade")
    if not isinstance(row.get("source_adapter_ref_hash"), str) or not HEX_RE.match(row["source_adapter_ref_hash"]):
        issues.append(f"work_item_{index}_source_adapter_ref_hash_not_hash")
    for key, expected in RAW_CONTENT_POLICY.items():
        if row.get("raw_content_policy", {}).get(key) is not expected:
            issues.append(f"work_item_{index}_raw_content_policy_{key}_mismatch")
    for key, expected in CLAIM_BOUNDARY.items():
        if row.get("claim_boundary", {}).get(key) != expected:
            issues.append(f"work_item_{index}_claim_boundary_{key}_mismatch")
    for key, expected in ZERO_ADMISSION_FLAGS.items():
        if row.get("zero_admission_flags", {}).get(key) != expected:
            issues.append(f"work_item_{index}_zero_admission_flags_{key}_mismatch")
        if row.get(key) != expected:
            issues.append(f"work_item_{index}_{key}_not_false_or_zero")
    forbidden = set(row.get("forbidden_use") or [])
    for value in ["training_row", "eval_row", "level3_admission", "raw_content_hydration", "replay_result_claim"]:
        if value not in forbidden:
            issues.append(f"work_item_{index}_forbidden_use_missing_{value}")
    return issues


def select_work_items(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    sorted_items = sorted(
        items,
        key=lambda row: (
            -float(row["priority_score"]),
            str(row["recommended_next_action"]),
            str(row["source_family"]),
            str(row["work_item_id"]),
        ),
    )
    selected: list[dict[str, Any]] = []
    selected_ids: set[str] = set()
    family_counts: Counter[str] = Counter()

    best_by_family: dict[str, dict[str, Any]] = {}
    for item in sorted_items:
        best_by_family.setdefault(str(item["source_family"]), item)
    for item in sorted(best_by_family.values(), key=lambda row: -float(row["priority_score"]))[:MIN_DIVERSE_FAMILIES]:
        family = str(item["source_family"])
        if len(selected) >= MAX_WORK_ITEMS or family_counts[family] >= MAX_PER_SOURCE_FAMILY:
            continue
        selected.append(item)
        selected_ids.add(str(item["work_item_id"]))
        family_counts[family] += 1

    for item in sorted_items:
        if len(selected) >= MAX_WORK_ITEMS:
            break
        item_id = str(item["work_item_id"])
        family = str(item["source_family"])
        if item_id in selected_ids or family_counts[family] >= MAX_PER_SOURCE_FAMILY:
            continue
        selected.append(item)
        selected_ids.add(item_id)
        family_counts[family] += 1
    return sorted(selected, key=lambda row: (-float(row["priority_score"]), str(row["work_item_id"])))


def scan_value(value: Any, artifact: str, issues: list[dict[str, Any]], key_path: str = "") -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            child_path = f"{key_path}.{key}" if key_path else str(key)
            scan_value(child, artifact, issues, child_path)
        return
    if isinstance(value, list):
        for list_index, child in enumerate(value):
            scan_value(child, artifact, issues, f"{key_path}[{list_index}]")
        return
    if not isinstance(value, str):
        return
    if ABS_PATH_RE.search(value):
        issues.append({"artifact": artifact, "issue": "absolute_path_string", "key_hash": stable_hash(key_path, 16)})
    if URL_RE.search(value):
        issues.append({"artifact": artifact, "issue": "url_string", "key_hash": stable_hash(key_path, 16)})
    if MULTILINE_RE.search(value):
        issues.append({"artifact": artifact, "issue": "multiline_string", "key_hash": stable_hash(key_path, 16)})


def guardrail_scan(paths: list[Path]) -> dict[str, Any]:
    issues: list[dict[str, Any]] = []
    parsed_json_values = 0
    scanned_jsonl_rows = 0
    for path in paths:
        text = path.read_text(encoding="utf-8")
        if ABS_PATH_RE.search(text):
            issues.append({"artifact": path.name, "issue": "absolute_path_pattern"})
        if URL_RE.search(text):
            issues.append({"artifact": path.name, "issue": "url_pattern"})
        if path.suffix == ".jsonl":
            for line_number, line in enumerate(text.splitlines(), 1):
                if not line.strip():
                    continue
                scanned_jsonl_rows += 1
                try:
                    value = json.loads(line)
                except json.JSONDecodeError:
                    issues.append({"artifact": path.name, "issue": "invalid_jsonl", "line": line_number})
                    continue
                scan_value(value, path.name, issues, f"line[{line_number}]")
            continue
        try:
            value = json.loads(text)
        except json.JSONDecodeError:
            issues.append({"artifact": path.name, "issue": "invalid_json"})
            continue
        parsed_json_values += 1
        scan_value(value, path.name, issues)
    return {
        "scan_passed": not issues,
        "issues": issues,
        "scanned_artifact_count": len(paths),
        "parsed_json_values": parsed_json_values,
        "scanned_jsonl_rows": scanned_jsonl_rows,
    }


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)

    input_summary = read_json(INPUT_SUMMARY)
    candidates, input_parse_issues = read_jsonl(INPUT_CANDIDATES)
    schema_issues = list(input_parse_issues)
    guardrail_issues: list[str] = []

    if input_summary.get("training_allowed") is not False:
        guardrail_issues.append("stage12406_summary_training_allowed_not_false")
    if input_summary.get("training_row_count") != 0:
        guardrail_issues.append("stage12406_summary_training_row_count_not_zero")
    if input_summary.get("admitted_rows") != 0:
        guardrail_issues.append("stage12406_summary_admitted_rows_not_zero")
    if input_summary.get("raw_leak_count") not in (0, None):
        guardrail_issues.append("stage12406_summary_raw_leak_count_not_zero")

    candidate_items: list[dict[str, Any]] = []
    rejected_candidate_indexes: set[int] = set()
    for index, row in enumerate(candidates, 1):
        row_issues = []
        row_issues.extend(candidate_zero_admission_safe(row, index))
        row_issues.extend(candidate_raw_policy_safe(row, index))
        if row.get("record_type") != "source_adapter_candidate":
            row_issues.append(f"candidate_{index}_record_type_not_source_adapter_candidate")
        if safe_int(row.get("training_row_count")) or safe_int(row.get("eval_row_count")):
            row_issues.append(f"candidate_{index}_training_or_eval_rows_present")
        if row.get("candidate_proof_tier_now") == "level3_reconstructed_proof":
            row_issues.append(f"candidate_{index}_level3_candidate_not_admitted")
        if row_issues:
            schema_issues.extend(row_issues)
            rejected_candidate_indexes.add(index)
            continue
        candidate_items.append(build_work_item(row, index))

    selected = select_work_items(candidate_items)
    selected_schema_issues = [issue for index, row in enumerate(selected, 1) for issue in validate_work_item(row, index)]
    schema_issues.extend(selected_schema_issues)

    family_counts = Counter(str(row["source_family"]) for row in selected)
    action_counts = Counter(str(row["recommended_next_action"]) for row in selected)
    target_tier_counts = Counter(str(row["target_next_proof_tier"]) for row in selected)
    for action in ALLOWED_ACTIONS:
        action_counts.setdefault(action, 0)
    for tier in ALLOWED_TARGET_TIERS:
        target_tier_counts.setdefault(tier, 0)

    cap_violations: list[str] = []
    if len(selected) > MAX_WORK_ITEMS:
        cap_violations.append("selected_work_item_count_exceeds_40")
    for family, count in family_counts.items():
        if count > MAX_PER_SOURCE_FAMILY:
            cap_violations.append(f"source_family_{stable_hash(family, 12)}_exceeds_cap")
    available_families = {str(item["source_family"]) for item in candidate_items}
    if len(available_families) >= MIN_DIVERSE_FAMILIES and len(family_counts) < MIN_DIVERSE_FAMILIES:
        cap_violations.append("selected_family_diversity_below_5")
    sealed_non_skip = sum(
        1
        for row in selected
        if row.get("current_proof_tier") == "sealed_eval_only" and row.get("recommended_next_action") != "skip_sealed_eval"
    )
    if sealed_non_skip:
        cap_violations.append("sealed_eval_non_skip_work_items_present")

    worklist_path = OUT / WORKLIST_NAME
    local_summary_path = OUT / LOCAL_SUMMARY_NAME
    action_counts_path = OUT / ACTION_COUNTS_NAME
    family_counts_path = OUT / FAMILY_COUNTS_NAME
    guardrail_path = OUT / GUARDRAIL_NAME

    write_jsonl(worklist_path, selected)
    write_json(action_counts_path, dict(sorted(action_counts.items())))
    write_json(family_counts_path, dict(sorted(family_counts.items())))

    selected_source_ref_hashes = [row["source_adapter_ref_hash"] for row in selected]
    estimated_records_under_selected = sum(safe_int(row.get("observed_count_estimate")) for row in selected)
    summary = {
        "stage": STAGE,
        "decision": "pending_guardrail_scan",
        "input_candidates_path": "runs/local/artifacts/stage12406_transition_source_expansion_preflight/source_adapter_candidates.jsonl",
        "input_summary_path": "runs/summaries/stage12406_transition_source_expansion_preflight.json",
        "input_candidate_count": len(candidates),
        "eligible_candidate_count": len(candidate_items),
        "selected_work_item_count": len(selected),
        "skipped_candidate_count": len(candidates) - len(selected),
        "skipped_due_to_input_schema_or_guardrail_count": len(rejected_candidate_indexes),
        "counts_by_source_family": dict(sorted(family_counts.items())),
        "counts_by_recommended_next_action": dict(sorted(action_counts.items())),
        "counts_by_target_next_proof_tier": dict(sorted(target_tier_counts.items())),
        "estimated_records_under_selected_work_items": estimated_records_under_selected,
        "selected_source_adapter_ref_hashes": selected_source_ref_hashes,
        "available_source_family_count": len(available_families),
        "selected_source_family_count": len(family_counts),
        "cap_policy": {
            "max_work_items": MAX_WORK_ITEMS,
            "max_per_source_family": MAX_PER_SOURCE_FAMILY,
            "min_source_family_diversity_if_available": MIN_DIVERSE_FAMILIES,
            "admit_level3_targets": False,
            "sealed_eval_only_policy": "skip_records_only",
        },
        "cap_violation_count": len(cap_violations),
        "cap_violations": cap_violations,
        "schema_issue_count": len(schema_issues),
        "schema_issues": schema_issues,
        "guardrail_issue_count": len(guardrail_issues),
        "guardrail_issues": guardrail_issues,
        "raw_leak_findings": [],
        "raw_leak_count": 0,
        "claim_boundary": CLAIM_BOUNDARY,
        "raw_content_policy": RAW_CONTENT_POLICY,
        "zero_admission_flags": ZERO_ADMISSION_FLAGS,
        "zero_admission": not schema_issues and not guardrail_issues and not cap_violations,
        "training_allowed": False,
        "training_row_count": 0,
        "eval_row_count": 0,
        "admission": False,
        "admitted_rows": 0,
        "level3_admitted": 0,
        "level4_admitted": 0,
        "patch_trace_admitted": 0,
        "repair_claim_admitted": 0,
        "strict_eval_eligible": 0,
        "source_heldout_admissible": 0,
        "level3_reconstructed_proof": 0,
        "external_comparable_patch_trace_countable": 0,
        "external_fail_to_pass_countable": 0,
        "synthetic_fixture_external_repair_countable": 0,
        "selected_test_full_repair_claim_count": 0,
        "sealed_eval_train_overlap_count": 0,
        "generated_artifacts": [WORKLIST_NAME, LOCAL_SUMMARY_NAME, ACTION_COUNTS_NAME, FAMILY_COUNTS_NAME, GUARDRAIL_NAME],
    }
    write_json(local_summary_path, summary)

    guardrail = guardrail_scan([worklist_path, action_counts_path, family_counts_path, local_summary_path])
    write_json(guardrail_path, guardrail)

    final_guardrail_issues = list(guardrail_issues)
    final_raw_leak_findings = list(guardrail["issues"])
    decision = "fail_closed_prioritized_adapter_worklist_ready_no_admission"
    if schema_issues or final_guardrail_issues or cap_violations or final_raw_leak_findings:
        decision = "fail_closed_prioritized_adapter_worklist_blocked_schema_guardrail_or_cap_issue"

    final_summary = {
        **summary,
        "decision": decision,
        "guardrail_scan": guardrail,
        "guardrail_issue_count": len(final_guardrail_issues) + len(final_raw_leak_findings),
        "guardrail_issues": final_guardrail_issues,
        "raw_leak_findings": final_raw_leak_findings,
        "raw_leak_count": len(final_raw_leak_findings),
        "zero_admission": decision == "fail_closed_prioritized_adapter_worklist_ready_no_admission",
    }
    write_json(local_summary_path, final_summary)
    write_json(SUMMARY, final_summary)


if __name__ == "__main__":
    main()
