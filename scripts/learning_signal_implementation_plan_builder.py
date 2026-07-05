from __future__ import annotations

from collections import Counter
from typing import Any

try:
    from scripts.learning_signal_contract_builder import (
        COUNTERFACTUAL_OBLIGATIONS,
        FILE_TOUCHPOINTS,
        LOSS_WEIGHTING_REQUIREMENTS,
        REPRESENTATION_REQUIREMENTS,
        REQUIRED_TELEMETRY,
        STRUCTURED_TARGET_FIELDS,
    )
    from scripts.model_output_packet_telemetry_contract_builder import AUTHORITY_CLOSED
except ModuleNotFoundError:
    from learning_signal_contract_builder import (
        COUNTERFACTUAL_OBLIGATIONS,
        FILE_TOUCHPOINTS,
        LOSS_WEIGHTING_REQUIREMENTS,
        REPRESENTATION_REQUIREMENTS,
        REQUIRED_TELEMETRY,
        STRUCTURED_TARGET_FIELDS,
    )
    from model_output_packet_telemetry_contract_builder import AUTHORITY_CLOSED

LOSS_MASK_CLOSED = {
    "decoder_ce": False,
    "denoise_ce": False,
    "runtime_reward": False,
    "heldout_eval_metric": False,
}

PLAN_ROWS = [
    {
        "plan_id": "typed_input_serialization",
        "file": "legacy_src/agentkernel_lite/training_data.py",
        "planned_changes": [
            "add typed row sections for objective, evidence, counterfactual family, loss target, and decisive features",
            "preserve field-local evidence-to-target links without exposing target labels",
            "add sibling_group_id and counterfactual_role as metadata excluded from model-visible text unless explicitly whitelisted",
            "add tests proving row_id, target labels, decoder targets, source paths, and opaque IDs are excluded from model input",
        ],
        "acceptance_checks": [
            "typed_serialization_contains_required_markers",
            "target_label_absence_check",
            "row_id_absence_check",
            "counterfactual_metadata_present_not_leaking",
        ],
    },
    {
        "plan_id": "counterfactual_sibling_manifest_gate",
        "file": "legacy_src/agentkernel_lite/training_data.py",
        "planned_changes": [
            "add manifest-level sibling group validator",
            "require positive, evidence-removed, boundary, misleading-evidence, and junk/OOD roles for structured-head rows",
            "emit per-field sibling coverage cards before trainer accepts a manifest",
        ],
        "acceptance_checks": [
            "all_counterfactual_obligations_present",
            "one_label_flip_boundary_check",
            "evidence_removed_routes_to_retrieve_or_abstain",
        ],
    },
    {
        "plan_id": "structured_head_telemetry",
        "file": "legacy_src/agentkernel_lite/training_loop.py",
        "planned_changes": [
            "extend structured aux telemetry with row-field logits including confidence, entropy, and margin",
            "emit high-confidence wrong row reports by field/split",
            "emit field exact by split and by field/cell",
            "emit structured confusion matrices for every active head",
        ],
        "acceptance_checks": [
            "row_field_logits_jsonl_written",
            "row_field_losses_jsonl_written",
            "high_confidence_wrong_jsonl_written",
            "confusion_matrix_written",
        ],
    },
    {
        "plan_id": "gradient_and_loss_weight_telemetry",
        "file": "legacy_src/agentkernel_lite/training_loop.py",
        "planned_changes": [
            "log per-row gradient norm or supported approximation for structured probes",
            "log per-module gradient norms for active structured heads and shared encoder",
            "log declared loss weights and measured loss contribution by objective",
            "fail mixed-objective training if decoder_ce is active without explicit authorization",
        ],
        "acceptance_checks": [
            "per_module_gradient_norms_written",
            "loss_weight_contribution_written",
            "decoder_ce_mixed_loss_blocked_without_authority",
        ],
    },
    {
        "plan_id": "telemetry_metric_helpers",
        "file": "scripts/training_telemetry_metrics.py",
        "planned_changes": [
            "reuse margin_confidence_entropy for every row-field logit row",
            "add confusion matrix summarizer if missing from training loop",
            "add high-confidence wrong summarizer by field and split",
            "extend token loss maps with decoder surface failure tags for decoder-only probes",
        ],
        "acceptance_checks": [
            "margin_confidence_entropy_unit_test",
            "high_confidence_wrong_unit_test",
            "token_loss_map_unit_test",
        ],
    },
    {
        "plan_id": "structured_head_target_mapping",
        "file": "legacy_src/agentkernel_lite/modeling_transformer.py",
        "planned_changes": [
            "verify structured head names remain aligned with loss masks and clean_state fields",
            "document which policy heads are regression/BCE-style and which structured heads are CE-style",
            "add shape assertions for active structured heads in training tests",
        ],
        "acceptance_checks": [
            "structured_head_loss_mask_alignment_check",
            "structured_head_shape_check",
            "policy_head_type_documented",
        ],
    },
]


def build_plan_rows(contract_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    target_fields = sorted({row.get("target_field") for row in contract_rows if row.get("target_field")})
    rows: list[dict[str, Any]] = []
    for plan in PLAN_ROWS:
        rows.append({
            "row_id": f"stage8847_learning_signal_plan::{plan['plan_id']}",
            "semantic_key": f"learning_signal_implementation_plan:{plan['plan_id']}",
            "source_stage": "stage8847_from_stage8844_learning_signal_contract",
            "objective_family": "learning_signal_dataset_trainer_implementation_plan",
            "split": "plan",
            "route": "IMPLEMENTATION_PLAN_ONLY",
            "plan_id": plan["plan_id"],
            "file": plan["file"],
            "target_fields": target_fields,
            "planned_changes": plan["planned_changes"],
            "acceptance_checks": plan["acceptance_checks"],
            "contract_requirements": {
                "structured_target_fields": STRUCTURED_TARGET_FIELDS,
                "counterfactual_obligations": COUNTERFACTUAL_OBLIGATIONS,
                "required_telemetry": REQUIRED_TELEMETRY,
                "representation_requirements": REPRESENTATION_REQUIREMENTS,
                "loss_weighting_requirements": LOSS_WEIGHTING_REQUIREMENTS,
                "file_touchpoints": FILE_TOUCHPOINTS,
            },
            "authority": dict(AUTHORITY_CLOSED),
            "loss_mask": dict(LOSS_MASK_CLOSED),
            "anti_cheat": {
                "modifies_training_now": False,
                "opens_training": False,
                "opens_decoder_ce": False,
                "runs_model": False,
                "contains_model_output": False,
            },
            "hard_blockers": [
                "implementation_plan_only",
                "no_code_patch_authorized_by_this_stage",
                "training_not_authorized",
                "decoder_ce_not_authorized",
            ],
        })
    return rows


def build_card(rows: list[dict[str, Any]]) -> dict[str, Any]:
    missing_change_rows = 0
    missing_acceptance_rows = 0
    missing_contract_rows = 0
    authority_open_rows = 0
    loss_open_rows = 0
    opening_rows = 0
    for row in rows:
        requirements = row.get("contract_requirements") or {}
        if not row.get("planned_changes"):
            missing_change_rows += 1
        if not row.get("acceptance_checks"):
            missing_acceptance_rows += 1
        if set(STRUCTURED_TARGET_FIELDS) - set(requirements.get("structured_target_fields", [])):
            missing_contract_rows += 1
        if set(REQUIRED_TELEMETRY) - set(requirements.get("required_telemetry", [])):
            missing_contract_rows += 1
        if any((row.get("authority") or {}).values()):
            authority_open_rows += 1
        if any((row.get("loss_mask") or {}).values()):
            loss_open_rows += 1
        if any((row.get("anti_cheat") or {}).values()):
            opening_rows += 1
    failing = {
        "missing_change_rows": missing_change_rows,
        "missing_acceptance_rows": missing_acceptance_rows,
        "missing_contract_rows": missing_contract_rows,
        "authority_open_rows": authority_open_rows,
        "loss_open_rows": loss_open_rows,
        "opening_rows": opening_rows,
    }
    return {
        "rows": len(rows),
        "file_counts": dict(sorted(Counter(row.get("file") for row in rows).items())),
        **failing,
        "implementation_plan_ready_rows": len(rows) if rows and all(value == 0 for value in failing.values()) else 0,
        "training_authorized": False,
        "decoder_ce_authorized": False,
        "passed": bool(rows) and all(value == 0 for value in failing.values()),
    }
