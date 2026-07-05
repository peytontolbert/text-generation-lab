from __future__ import annotations

from collections import Counter
from typing import Any

try:
    from scripts.learning_signal_implementation_plan_gate_audit import REQUIRED_FILES, REQUIRED_PLAN_IDS
    from scripts.model_output_packet_telemetry_contract_builder import AUTHORITY_CLOSED
except ModuleNotFoundError:
    from learning_signal_implementation_plan_gate_audit import REQUIRED_FILES, REQUIRED_PLAN_IDS
    from model_output_packet_telemetry_contract_builder import AUTHORITY_CLOSED

LOSS_MASK_CLOSED = {
    "decoder_ce": False,
    "denoise_ce": False,
    "runtime_reward": False,
    "heldout_eval_metric": False,
}

GLOBAL_PATCH_PREFLIGHTS = [
    "inspect_git_status_before_edit",
    "isolate_learning_signal_files_only",
    "add_or_update_tests_before_behavior_claim",
    "no_training_run_in_patch_stage",
    "no_decoder_ce_authority_opened",
    "no_manifest_mining_or_data_expansion",
    "preserve_existing_recovery_artifacts",
    "record_acceptance_commands",
]

PATCH_ORDER = [
    "tests_first",
    "training_telemetry_metrics_helpers",
    "training_data_serialization_and_sibling_gate",
    "training_loop_telemetry_and_loss_weight_guards",
    "modeling_transformer_mapping_assertions",
    "focused_tests",
    "registry_spine_reconciliation",
]

READINESS_ROWS = [
    {
        "readiness_id": "tests_first_contract",
        "file": "tests/",
        "required_checks": [
            "test_typed_serialization_no_label_leak",
            "test_counterfactual_sibling_gate",
            "test_structured_telemetry_outputs",
            "test_decoder_ce_mixed_loss_blocked",
            "test_structured_head_mapping",
        ],
    },
    {
        "readiness_id": "training_data_patch_readiness",
        "file": "legacy_src/agentkernel_lite/training_data.py",
        "required_checks": [
            "row_id_absence_check",
            "target_label_absence_check",
            "typed_marker_presence_check",
            "counterfactual_metadata_nonleaking_check",
        ],
    },
    {
        "readiness_id": "training_loop_patch_readiness",
        "file": "legacy_src/agentkernel_lite/training_loop.py",
        "required_checks": [
            "row_field_logits_written",
            "row_field_losses_written",
            "high_confidence_wrong_written",
            "loss_weight_contribution_written",
            "decoder_ce_mixed_loss_blocked_without_authority",
        ],
    },
    {
        "readiness_id": "telemetry_helpers_patch_readiness",
        "file": "scripts/training_telemetry_metrics.py",
        "required_checks": [
            "margin_confidence_entropy_unit_test",
            "confusion_summary_unit_test",
            "high_confidence_wrong_unit_test",
            "token_loss_map_unit_test",
        ],
    },
    {
        "readiness_id": "modeling_transformer_mapping_readiness",
        "file": "legacy_src/agentkernel_lite/modeling_transformer.py",
        "required_checks": [
            "structured_head_shape_check",
            "loss_mask_to_head_alignment_check",
            "policy_head_type_documented",
        ],
    },
]


def build_readiness_rows(plan_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    plan_ids = sorted({str(row.get("plan_id")) for row in plan_rows})
    files = sorted({str(row.get("file")) for row in plan_rows})
    rows: list[dict[str, Any]] = []
    for item in READINESS_ROWS:
        rows.append({
            "row_id": f"stage8851_code_patch_readiness::{item['readiness_id']}",
            "semantic_key": f"learning_signal_code_patch_readiness:{item['readiness_id']}",
            "source_stage": "stage8851_from_stage8847_learning_signal_implementation_plan",
            "objective_family": "learning_signal_code_patch_readiness_checklist",
            "split": "readiness",
            "route": "CODE_PATCH_READINESS_ONLY",
            "readiness_id": item["readiness_id"],
            "file": item["file"],
            "required_checks": item["required_checks"],
            "global_patch_preflights": GLOBAL_PATCH_PREFLIGHTS,
            "patch_order": PATCH_ORDER,
            "plan_coverage": {
                "plan_ids": plan_ids,
                "files": files,
                "missing_plan_ids": sorted(REQUIRED_PLAN_IDS - set(plan_ids)),
                "missing_files": sorted(REQUIRED_FILES - set(files)),
            },
            "authority": dict(AUTHORITY_CLOSED),
            "loss_mask": dict(LOSS_MASK_CLOSED),
            "anti_cheat": {
                "applies_code_patch_now": False,
                "opens_training": False,
                "opens_decoder_ce": False,
                "runs_model": False,
                "changes_dataset": False,
            },
            "hard_blockers": [
                "readiness_checklist_only",
                "no_code_patch_authorized_by_this_stage",
                "training_not_authorized",
                "decoder_ce_not_authorized",
            ],
        })
    return rows


def build_card(rows: list[dict[str, Any]]) -> dict[str, Any]:
    missing_global_preflight_rows = 0
    missing_patch_order_rows = 0
    missing_required_check_rows = 0
    missing_plan_coverage_rows = 0
    authority_open_rows = 0
    loss_open_rows = 0
    opening_rows = 0
    bad_route_rows = 0
    for row in rows:
        if set(GLOBAL_PATCH_PREFLIGHTS) - set(row.get("global_patch_preflights", [])):
            missing_global_preflight_rows += 1
        if set(PATCH_ORDER) - set(row.get("patch_order", [])):
            missing_patch_order_rows += 1
        if not row.get("required_checks"):
            missing_required_check_rows += 1
        coverage = row.get("plan_coverage") or {}
        if coverage.get("missing_plan_ids") or coverage.get("missing_files"):
            missing_plan_coverage_rows += 1
        if any((row.get("authority") or {}).values()):
            authority_open_rows += 1
        if any((row.get("loss_mask") or {}).values()):
            loss_open_rows += 1
        if any((row.get("anti_cheat") or {}).values()):
            opening_rows += 1
        if row.get("route") != "CODE_PATCH_READINESS_ONLY":
            bad_route_rows += 1
    failing = {
        "missing_global_preflight_rows": missing_global_preflight_rows,
        "missing_patch_order_rows": missing_patch_order_rows,
        "missing_required_check_rows": missing_required_check_rows,
        "missing_plan_coverage_rows": missing_plan_coverage_rows,
        "authority_open_rows": authority_open_rows,
        "loss_open_rows": loss_open_rows,
        "opening_rows": opening_rows,
        "bad_route_rows": bad_route_rows,
    }
    return {
        "rows": len(rows),
        "file_counts": dict(sorted(Counter(row.get("file") for row in rows).items())),
        **failing,
        "code_patch_readiness_rows": len(rows) if rows and all(value == 0 for value in failing.values()) else 0,
        "code_patch_authorized": False,
        "training_authorized": False,
        "decoder_ce_authorized": False,
        "passed": bool(rows) and all(value == 0 for value in failing.values()),
    }
