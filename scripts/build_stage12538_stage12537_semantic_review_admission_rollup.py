#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import importlib.util
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12538_stage12537_semantic_review_admission_rollup"
OUT = ROOT / "runs/local/artifacts" / STAGE
SUMMARY = ROOT / "runs/summaries" / f"{STAGE}.json"

STAGE12534_SCRIPT = ROOT / "scripts/build_stage12534_fresh_hydratable_verifier_observation_admission_gate.py"
STAGE12534_SUMMARY = ROOT / "runs/summaries/stage12534_fresh_hydratable_verifier_observation_admission_gate.json"
STAGE12536_SUMMARY = ROOT / "runs/summaries/stage12536_stage12535_semantic_risk_audit.json"
STAGE12536_REPAIR = (
    ROOT
    / "runs/local/artifacts/stage12536_stage12535_semantic_risk_audit"
    / "stage12535_exact_repair_requirements.json"
)
STAGE12537_SUMMARY = (
    ROOT / "runs/summaries/stage12537_command_output_verifier_observation_materialization_preflight.json"
)
STAGE12537_CANDIDATES = (
    ROOT
    / "runs/local/artifacts/stage12537_command_output_verifier_observation_materialization_preflight"
    / "real_command_output_verifier_observation_candidate_rows.jsonl"
)
STAGE12537_BLOCKERS = (
    ROOT
    / "runs/local/artifacts/stage12537_command_output_verifier_observation_materialization_preflight"
    / "real_command_output_verifier_observation_blocker_worklist.jsonl"
)

TARGET_TRAIN_SUPPORT_FLOOR = 500
ADMITTED_ROWS_NAME = "stage12537_semantic_review_admitted_train_support_rows.jsonl"
REJECTED_ROWS_NAME = "stage12537_semantic_review_rejected_rows.jsonl"
VALIDATION_AUDIT_NAME = "stage12537_semantic_review_validation_audit.json"
GAP_WORKLIST_NAME = "remaining_gap_source_expansion_worklist.jsonl"
ROLLUP_NAME = "stage12537_semantic_review_admission_rollup.json"

RISKY_FIELDS = (
    "strict_eval_eligible",
    "source_heldout_admissible",
    "level3_admitted",
    "level4_admitted",
    "patch_trace_admitted",
    "repair_claim_admitted",
    "fail_to_pass_claim_admitted",
    "counts_toward_unbounded_patch_trace_floor",
    "counts_toward_strict_eval_floor",
    "counts_toward_source_heldout_floor",
    "training_allowed",
)
REQUIRED_COMMAND_OUTPUT_FIELDS = (
    "actual_verifier_command_output_observation_provenance",
    "verifier_command_ref_hash",
    "command_result_id_hash",
    "verifier_exit_status_class",
    "verifier_stdout_hash",
    "verifier_stderr_hash",
    "verifier_output_hash",
    "verifier_observation_hash",
    "target_binding_class",
    "target_binding_rule_id_hash",
)
ALLOWED_TARGET_BINDING = "target_semantic_value_from_observed_verifier_result_status"
MAX_TARGET_SHARE_FOR_SMALL_BATCH = 0.50
MIN_TARGET_CLASSES_FOR_COUNTABLE_SMALL_BATCH = 3
MIN_TARGET_CLASS_COUNT_FOR_COUNTABLE_SMALL_BATCH = 2


def stable_hash(value: Any, n: int = 24) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(f"{STAGE}:{payload}".encode("utf-8")).hexdigest()[:n]


def file_hash(path: Path, n: int = 24) -> str:
    if not path.exists():
        return "missing"
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()[:n]


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    value = json.loads(path.read_text(encoding="utf-8"))
    return value if isinstance(value, dict) else {}


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8", errors="replace") as handle:
        for line_no, line in enumerate(handle, 1):
            if not line.strip():
                continue
            value = json.loads(line)
            if isinstance(value, dict):
                value["__line_no"] = line_no
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


def load_stage12534_module():
    spec = importlib.util.spec_from_file_location("stage12534_validator_for_stage12538", STAGE12534_SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def truthy(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return value > 0
    if isinstance(value, str):
        return value.lower() in {"true", "1", "yes"}
    return False


def risky_claims(row: dict[str, Any]) -> list[str]:
    admission = row.get("admission") if isinstance(row.get("admission"), dict) else {}
    claims = []
    for field in RISKY_FIELDS:
        if field == "training_allowed":
            if row.get(field) is not False or admission.get(field) not in (None, False):
                claims.append(field)
        elif truthy(row.get(field)) or truthy(admission.get(field)):
            claims.append(field)
    return claims


def semantic_candidate_issues(row: dict[str, Any]) -> list[str]:
    issues = []
    for field in REQUIRED_COMMAND_OUTPUT_FIELDS:
        if field not in row:
            issues.append(f"missing_{field}")
    if row.get("actual_verifier_command_output_observation_provenance") is not True:
        issues.append("actual_verifier_command_output_observation_provenance_not_true")
    if row.get("target_binding_class") != ALLOWED_TARGET_BINDING:
        issues.append("target_binding_not_observed_verifier_status")
    if row.get("target_semantic_value") != row.get("verifier_status"):
        issues.append("target_not_bound_to_observed_verifier_status")
    if row.get("stage12534_constraint_preflight_passed") is not True:
        issues.append("stage12534_preflight_flag_not_true")
    issues.extend(risky_claims(row))
    return sorted(set(issues))


def duplicate_conflict_audit(rows: list[dict[str, Any]]) -> dict[str, Any]:
    conflicts: list[dict[str, Any]] = []
    duplicate_same_target: list[dict[str, Any]] = []
    for field, reason in (
        ("verifier_observation_hash", "same_verifier_observation_hash_reused_with_different_target"),
        ("command_result_id_hash", "same_command_result_hash_reused_with_different_target"),
        ("verifier_output_hash", "same_verifier_output_hash_reused_with_different_target"),
    ):
        targets_by_value: dict[str, set[str]] = defaultdict(set)
        refs_by_value: dict[str, list[str]] = defaultdict(list)
        for row in rows:
            value = str(row.get(field) or "")
            if not value:
                continue
            targets_by_value[value].add(str(row.get("target_semantic_value") or "unknown"))
            refs_by_value[value].append(str(row.get("candidate_ref_hash") or stable_hash(row)))
        for value, targets in targets_by_value.items():
            refs = sorted(refs_by_value[value])[:10]
            if len(targets) > 1:
                conflicts.append(
                    {
                        "reason": reason,
                        "digest_hash": stable_hash({field: value}),
                        "target_values": sorted(targets),
                        "candidate_ref_hashes": refs,
                    }
                )
            elif len(refs_by_value[value]) > 1 and field == "verifier_output_hash":
                duplicate_same_target.append(
                    {
                        "reason": "same_verifier_output_hash_reused_with_same_target_requires_collapse_or_block",
                        "digest_hash": stable_hash({field: value}),
                        "target_values": sorted(targets),
                        "candidate_ref_hashes": refs,
                    }
                )
    return {
        "duplicate_conflict_count": len(conflicts),
        "duplicate_same_target_output_count": len(duplicate_same_target),
        "conflicts": conflicts[:50],
        "duplicate_same_target_outputs": duplicate_same_target[:50],
    }


def target_balance_audit(rows: list[dict[str, Any]]) -> dict[str, Any]:
    counts = Counter(str(row.get("target_semantic_value") or "unknown") for row in rows)
    total = sum(counts.values())
    max_share = max(counts.values()) / total if total else 0.0
    min_count = min(counts.values()) if counts else 0
    passed = bool(rows) and max_share <= MAX_TARGET_SHARE_FOR_SMALL_BATCH and len(counts) >= MIN_TARGET_CLASSES_FOR_COUNTABLE_SMALL_BATCH and min_count >= MIN_TARGET_CLASS_COUNT_FOR_COUNTABLE_SMALL_BATCH
    return {
        "passed": passed,
        "row_count": total,
        "target_counts": dict(sorted(counts.items())),
        "max_target_share": round(max_share, 6),
        "target_class_count": len(counts),
        "min_target_class_count": min_count,
        "required_max_target_share": MAX_TARGET_SHARE_FOR_SMALL_BATCH,
        "required_target_class_count": MIN_TARGET_CLASSES_FOR_COUNTABLE_SMALL_BATCH,
        "required_min_target_class_count": MIN_TARGET_CLASS_COUNT_FOR_COUNTABLE_SMALL_BATCH,
    }


def selected_test_scope_audit(rows: list[dict[str, Any]]) -> dict[str, Any]:
    scoped = []
    for row in rows:
        source_stage = str(row.get("source_stage") or "").lower()
        if "selected" in source_stage:
            scoped.append(str(row.get("candidate_ref_hash") or stable_hash(row)))
    return {
        "passed": not scoped,
        "selected_test_scoped_row_count": len(scoped),
        "selected_test_scoped_candidate_ref_hashes": scoped[:50],
    }


def command_observation_join_audit(rows: list[dict[str, Any]]) -> dict[str, Any]:
    missing = []
    for row in rows:
        if not row.get("command_observation_join_hash"):
            missing.append(str(row.get("candidate_ref_hash") or stable_hash(row)))
    return {
        "passed": not missing,
        "missing_command_observation_join_hash_count": len(missing),
        "missing_candidate_ref_hashes": missing[:50],
    }


def sanitize_admitted_row(row: dict[str, Any], stage12534_ref: dict[str, Any]) -> dict[str, Any]:
    return {
        "stage": STAGE,
        "record_type": "stage12537_semantic_review_train_support_only_row_v1",
        "candidate_ref_hash": row["candidate_ref_hash"],
        "source_stage": row["source_stage"],
        "source_line_hash": row["source_line_hash"],
        "root_lineage_key_hash": row["root_lineage_key_hash"],
        "repo_family_hash": row["repo_family_hash"],
        "language_family": row["language_family"],
        "task_projection": row["task_projection"],
        "target_semantic_value": row["target_semantic_value"],
        "verifier_status": row["verifier_status"],
        "actual_verifier_command_output_observation_provenance": True,
        "verifier_command_ref_hash": row["verifier_command_ref_hash"],
        "command_result_id_hash": row["command_result_id_hash"],
        "verifier_exit_status_class": row["verifier_exit_status_class"],
        "verifier_stdout_hash": row["verifier_stdout_hash"],
        "verifier_stderr_hash": row["verifier_stderr_hash"],
        "verifier_output_hash": row["verifier_output_hash"],
        "verifier_observation_hash": row["verifier_observation_hash"],
        "target_binding_class": row["target_binding_class"],
        "target_binding_rule_id_hash": row["target_binding_rule_id_hash"],
        "source_lineage_checked": True,
        "hydratable_verifier_observation_candidate": True,
        "semantic_review_admission": "admitted_train_support_only",
        "stage12534_validation_passed": True,
        "stage12534_validator_candidate_ref_hash": stage12534_ref["candidate_ref_hash"],
        "countable_train_support": True,
        "training_allowed": False,
        "strict_eval_eligible": False,
        "source_heldout_admissible": False,
        "level3_admitted": False,
        "patch_trace_admitted": False,
        "repair_claim_admitted": False,
        "fail_to_pass_claim_admitted": False,
        "gemma_or_product_claim": False,
    }


def worklist_action(reason: str) -> str:
    actions = {
        "unsupported_or_forbidden_target_status_for_stage12537_preflight": (
            "Re-extract only PASS_CURRENT_STATE, FAIL_CURRENT_STATE, or INSUFFICIENT_EVIDENCE verifier statuses "
            "from real command-result records; route other statuses to a non-training diagnostic lane."
        ),
        "missing_actual_verifier_command_output_observation_provenance": (
            "Acquire or reconstruct command_result_id, exit-status class, stdout/stderr digest, and observation digest "
            "before re-submitting the source rows."
        ),
        "controlled_fixture_like_not_materialized": (
            "Replace fixture-like examples with non-fixture public/local verifier executions before any train-support admission."
        ),
        "derived_sanitized_projection_lacks_independent_command_output_hash_provenance": (
            "Return to the underlying raw command-result source instead of Stage12418 projection rows."
        ),
        "projection_rows_lack_stdout_stderr_digest_fields_required_by_stage12537": (
            "Mine direct verifier-observation rows with stdout and stderr digest fields, not projection-only records."
        ),
        "stage12535_declares_public_local_repo_metadata_hash_only_source": (
            "Expand Stage12535 replacements from metadata inventory into real verifier command-output observations."
        ),
        "stage12535_rows_lack_real_command_output_observation_hashes": (
            "Fill command invocation, command result, stdout/stderr, combined output, and observation hashes."
        ),
        "stage12535_target_labels_match_deterministic_rotation_pattern": (
            "Bind labels to observed verifier statuses and discard index-rotated labels."
        ),
    }
    return actions.get(reason, "Re-materialize this source lane through Stage12534-compatible command-output evidence.")


def remaining_gap_worklist(
    stage12536_summary: dict[str, Any],
    stage12537_blockers: list[dict[str, Any]],
    remaining_gap: int,
) -> list[dict[str, Any]]:
    counts = Counter(reason for row in stage12537_blockers for reason in row.get("blocked_reasons", []))
    for reason in stage12536_summary.get("semantic_grounding", {}).get("weak_reasons", []):
        counts[str(reason)] += int(stage12536_summary.get("demotion", {}).get("blocked_row_count") or 0)
    rows = []
    for priority, (reason, count) in enumerate(counts.most_common(), 1):
        source = "stage12536_stage12535_blocker" if reason.startswith("stage12535_") else "stage12537_blocker"
        rows.append(
            {
                "stage": STAGE,
                "record_type": "remaining_gap_source_expansion_work_item_v1",
                "priority": priority,
                "blocker_reason": reason,
                "blocked_row_count": count,
                "source_blocker_class": source,
                "remaining_gap_to_500_at_rollup": remaining_gap,
                "recommended_next_action": worklist_action(reason),
                "training_allowed": False,
                "countable_train_support": False,
                "level3_admitted": False,
                "patch_trace_admitted": False,
                "repair_claim_admitted": False,
                "fail_to_pass_claim_admitted": False,
                "strict_eval_eligible": False,
                "source_heldout_admissible": False,
            }
        )
    return rows


def count_by(rows: list[dict[str, Any]], field: str) -> dict[str, int]:
    return dict(sorted(Counter(str(row.get(field) or "unknown") for row in rows).items()))


def build() -> dict[str, Any]:
    OUT.mkdir(parents=True, exist_ok=True)
    stage12534 = load_stage12534_module()
    s12534 = read_json(STAGE12534_SUMMARY)
    s12536 = read_json(STAGE12536_SUMMARY)
    s12537 = read_json(STAGE12537_SUMMARY)
    repair = read_json(STAGE12536_REPAIR)
    candidates = read_jsonl(STAGE12537_CANDIDATES)
    blockers = read_jsonl(STAGE12537_BLOCKERS)

    stage12534_result = stage12534.validate_supply_rows(
        candidates,
        stage12534.read_jsonl(stage12534.STAGE12533_REPAIRED_ROWS),
    )
    accepted_by_ref = {row["candidate_ref_hash"]: row for row in stage12534_result["accepted_rows"]}
    semantic_rejected = []
    prelim_admitted = []
    for row in candidates:
        issues = semantic_candidate_issues(row)
        stage12534_ref = accepted_by_ref.get(stage12534.stable_hash(row))
        if stage12534_ref is None:
            issues.append("stage12534_validation_failed")
        if issues:
            semantic_rejected.append(
                {
                    "stage": STAGE,
                    "record_type": "stage12537_semantic_review_rejection_v1",
                    "candidate_ref_hash": row.get("candidate_ref_hash") or stable_hash(row),
                    "stage12534_validator_ref_hash": stage12534.stable_hash(row),
                    "blocked_reasons": sorted(set(issues)),
                    "countable_train_support": False,
                    "training_allowed": False,
                    "level3_admitted": False,
                    "patch_trace_admitted": False,
                    "repair_claim_admitted": False,
                    "fail_to_pass_claim_admitted": False,
                    "strict_eval_eligible": False,
                    "source_heldout_admissible": False,
                }
            )
        else:
            prelim_admitted.append(sanitize_admitted_row(row, stage12534_ref))

    conflict_audit = duplicate_conflict_audit(prelim_admitted)
    target_balance = target_balance_audit(prelim_admitted)
    selected_scope = selected_test_scope_audit(prelim_admitted)
    command_join = command_observation_join_audit(prelim_admitted)
    collapse = stage12534.collapse_audit(prelim_admitted)
    guardrail = stage12534.guardrail_scan(prelim_admitted, semantic_rejected)
    batch_block_reasons = []
    if conflict_audit["duplicate_conflict_count"]:
        batch_block_reasons.append("stage12538_duplicate_conflicting_command_or_observation_hash")
    if conflict_audit["duplicate_same_target_output_count"]:
        batch_block_reasons.append("stage12538_duplicate_output_hash_requires_collapse_or_block")
    if not target_balance["passed"]:
        batch_block_reasons.append("stage12538_target_balance_failed")
    if not selected_scope["passed"]:
        batch_block_reasons.append("stage12538_selected_test_scope_not_countable_without_explicit_policy")
    if not command_join["passed"]:
        batch_block_reasons.append("stage12538_command_observation_join_hash_missing")
    if collapse["collapse_group_count"]:
        batch_block_reasons.append("stage12538_collapse_group_failed")
    if not guardrail["scan_passed"]:
        batch_block_reasons.append("stage12538_raw_guardrail_failed")
    if batch_block_reasons:
        semantic_rejected.extend(
            {
                "stage": STAGE,
                "record_type": "stage12537_semantic_review_rejection_v1",
                "candidate_ref_hash": row["candidate_ref_hash"],
                "blocked_reasons": sorted(set(batch_block_reasons)),
                "countable_train_support": False,
                "training_allowed": False,
                "level3_admitted": False,
                "patch_trace_admitted": False,
                "repair_claim_admitted": False,
                "fail_to_pass_claim_admitted": False,
                "strict_eval_eligible": False,
                "source_heldout_admissible": False,
            }
            for row in prelim_admitted
        )
        admitted: list[dict[str, Any]] = []
    else:
        admitted = prelim_admitted

    stage12533_total = int(s12534.get("countable_train_support_count") or 0)
    current_total = stage12533_total + len(admitted)
    remaining_gap = max(0, TARGET_TRAIN_SUPPORT_FLOOR - current_total)
    worklist = remaining_gap_worklist(s12536, blockers, remaining_gap)

    admitted_path = OUT / ADMITTED_ROWS_NAME
    rejected_path = OUT / REJECTED_ROWS_NAME
    audit_path = OUT / VALIDATION_AUDIT_NAME
    worklist_path = OUT / GAP_WORKLIST_NAME
    rollup_path = OUT / ROLLUP_NAME

    write_jsonl(admitted_path, admitted)
    write_jsonl(rejected_path, semantic_rejected)
    write_jsonl(worklist_path, worklist)

    audit = {
        "stage": STAGE,
        "record_type": "stage12537_semantic_review_validation_audit_v1",
        "stage12534_validator_result": {
            "input_row_count": len(candidates),
            "accepted_rows": len(stage12534_result["accepted_rows"]),
            "rejected_rows": len(stage12534_result["rejected_rows"]),
            "guardrail_scan_passed": stage12534_result["guardrail_scan"]["scan_passed"],
            "raw_leak_count": stage12534_result["guardrail_scan"]["raw_leak_count"],
            "collapse_group_count": stage12534_result["anti_collapse"]["collapse_group_count"],
        },
        "stage12538_semantic_review": {
            "admitted_train_support_only_rows": len(admitted),
            "rejected_rows": len(semantic_rejected),
            "duplicate_conflict_count": conflict_audit["duplicate_conflict_count"],
            "post_admission_collapse_group_count": collapse["collapse_group_count"],
            "guardrail_scan_passed": guardrail["scan_passed"],
            "raw_leak_count": guardrail["raw_leak_count"],
        },
        "duplicate_conflict_audit": conflict_audit,
        "target_balance_audit": target_balance,
        "selected_test_scope_audit": selected_scope,
        "command_observation_join_audit": command_join,
        "batch_block_reasons": sorted(set(batch_block_reasons)),
        "anti_collapse": collapse,
        "guardrail_scan": guardrail,
        "repair_requirements_checked": bool(repair.get("required_before_any_training_claim")),
        "input_hashes": {
            "stage12534_summary": file_hash(STAGE12534_SUMMARY),
            "stage12536_summary": file_hash(STAGE12536_SUMMARY),
            "stage12536_repair_requirements": file_hash(STAGE12536_REPAIR),
            "stage12537_summary": file_hash(STAGE12537_SUMMARY),
            "stage12537_candidates": file_hash(STAGE12537_CANDIDATES),
            "stage12537_blockers": file_hash(STAGE12537_BLOCKERS),
        },
    }
    write_json(audit_path, audit)

    decision = (
        "stage12537_rows_admitted_train_support_only_below_500_floor"
        if admitted
        else "fail_closed_no_stage12537_rows_admitted"
    )
    summary = {
        "stage": STAGE,
        "record_type": "stage12537_semantic_review_admission_rollup_v1",
        "decision": decision,
        "claim_boundary": (
            "Stage12538 is a semantic review/admission rollup for Stage12537 command-output verifier-observation "
            "candidates. Accepted rows are train-support-only below the 500 floor. This stage grants no training run "
            "permission, no Level3/Level4 admission, no patch-trace credit, no repair or fail-to-pass credit, no "
            "strict-eval/source-heldout eligibility, and no Gemma/product progress claim."
        ),
        "source_inventory": {
            "stage12537_candidate_rows": len(candidates),
            "stage12537_blocker_rows": len(blockers),
            "stage12536_demoted_rows": int(s12536.get("demotion", {}).get("blocked_row_count") or 0),
        },
        "admission_counts": {
            "stage12534_validation_passed_rows": len(stage12534_result["accepted_rows"]),
            "semantic_review_admitted_train_support_only_rows": len(admitted),
            "semantic_review_rejected_rows": len(semantic_rejected),
        },
        "countable_train_support": {
            "prior_stage12533_countable_total": stage12533_total,
            "admitted_stage12538_train_support_only_rows": len(admitted),
            "current_countable_total": current_total,
            "target_floor": TARGET_TRAIN_SUPPORT_FLOOR,
            "remaining_gap_to_500": remaining_gap,
        },
        "countable_train_support_count": current_total,
        "new_countable_train_support_count": len(admitted),
        "remaining_gap_to_500": remaining_gap,
        "countable_only_language_counts": count_by(admitted, "language_family"),
        "countable_only_projection_counts": count_by(admitted, "task_projection"),
        "countable_only_target_counts": count_by(admitted, "target_semantic_value"),
        "guardrail_scan_passed": guardrail["scan_passed"] and stage12534_result["guardrail_scan"]["scan_passed"],
        "raw_leak_count": guardrail["raw_leak_count"] + stage12534_result["guardrail_scan"]["raw_leak_count"],
        "duplicate_observation_or_command_conflict_count": conflict_audit["duplicate_conflict_count"],
        "duplicate_same_target_output_count": conflict_audit["duplicate_same_target_output_count"],
        "target_balance_audit": target_balance,
        "selected_test_scope_audit": selected_scope,
        "command_observation_join_audit": command_join,
        "batch_block_reasons": sorted(set(batch_block_reasons)),
        "post_admission_collapse_group_count": collapse["collapse_group_count"],
        "stage12534_validation_passed": len(stage12534_result["rejected_rows"]) == 0,
        "actual_command_output_provenance_required": True,
        "target_binding_required": ALLOWED_TARGET_BINDING,
        "training_allowed": False,
        "countable_train_support_only": bool(admitted),
        "level3_admitted_rows": 0,
        "patch_trace_admitted_rows": 0,
        "repair_claim_admitted_rows": 0,
        "fail_to_pass_claim_admitted_rows": 0,
        "strict_eval_eligible_count": 0,
        "source_heldout_admissible_count": 0,
        "gemma_or_product_claims": 0,
        "training_blockers": [
            "training_allowed_false_until_500_countable_train_support_floor",
            "remaining_gap_to_500_not_closed",
            "no_level3_patch_trace_repair_strict_sourceheldout_or_product_claims_by_stage12538_policy",
            *sorted(set(batch_block_reasons)),
        ],
        "remaining_gap_worklist": {
            "work_item_count": len(worklist),
            "worklist_ref": str(worklist_path.relative_to(ROOT)),
            "top_blocker_reasons": [
                {"reason": row["blocker_reason"], "blocked_row_count": row["blocked_row_count"]}
                for row in worklist[:5]
            ],
        },
        "artifact_refs": {
            "admitted_rows": str(admitted_path.relative_to(ROOT)),
            "rejected_rows": str(rejected_path.relative_to(ROOT)),
            "validation_audit": str(audit_path.relative_to(ROOT)),
            "remaining_gap_worklist": str(worklist_path.relative_to(ROOT)),
            "rollup": str(rollup_path.relative_to(ROOT)),
            "summary": str(SUMMARY.relative_to(ROOT)),
        },
        "input_hashes": audit["input_hashes"],
        "upstream_decisions": {
            "stage12534": s12534.get("decision"),
            "stage12536": s12536.get("decision"),
            "stage12537": s12537.get("decision"),
        },
        "next_stage": "expand_command_output_verifier_observation_sources_from_remaining_gap_worklist",
    }
    write_json(rollup_path, summary)
    write_json(SUMMARY, summary)
    return summary


def main() -> None:
    build()


if __name__ == "__main__":
    main()
