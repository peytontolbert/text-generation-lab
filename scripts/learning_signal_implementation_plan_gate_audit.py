from __future__ import annotations

from collections import Counter
from typing import Any

REQUIRED_PLAN_IDS = {
    "typed_input_serialization",
    "counterfactual_sibling_manifest_gate",
    "structured_head_telemetry",
    "gradient_and_loss_weight_telemetry",
    "telemetry_metric_helpers",
    "structured_head_target_mapping",
}

REQUIRED_FILES = {
    "legacy_src/agentkernel_lite/training_data.py",
    "legacy_src/agentkernel_lite/training_loop.py",
    "scripts/training_telemetry_metrics.py",
    "legacy_src/agentkernel_lite/modeling_transformer.py",
}


def audit_plan_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    plan_ids = {str(row.get("plan_id")) for row in rows}
    files = {str(row.get("file")) for row in rows}
    missing_plan_ids = sorted(REQUIRED_PLAN_IDS - plan_ids)
    missing_files = sorted(REQUIRED_FILES - files)
    missing_change_rows = 0
    missing_acceptance_rows = 0
    missing_contract_rows = 0
    authority_open_rows = 0
    loss_open_rows = 0
    opening_rows = 0
    bad_route_rows = 0
    for row in rows:
        if not row.get("planned_changes"):
            missing_change_rows += 1
        if not row.get("acceptance_checks"):
            missing_acceptance_rows += 1
        if not (row.get("contract_requirements") or {}).get("required_telemetry"):
            missing_contract_rows += 1
        if any((row.get("authority") or {}).values()):
            authority_open_rows += 1
        if any((row.get("loss_mask") or {}).values()):
            loss_open_rows += 1
        if any((row.get("anti_cheat") or {}).values()):
            opening_rows += 1
        if row.get("route") != "IMPLEMENTATION_PLAN_ONLY":
            bad_route_rows += 1
    failing = {
        "missing_plan_id_count": len(missing_plan_ids),
        "missing_file_count": len(missing_files),
        "missing_change_rows": missing_change_rows,
        "missing_acceptance_rows": missing_acceptance_rows,
        "missing_contract_rows": missing_contract_rows,
        "authority_open_rows": authority_open_rows,
        "loss_open_rows": loss_open_rows,
        "opening_rows": opening_rows,
        "bad_route_rows": bad_route_rows,
    }
    return {
        "rows": len(rows),
        "file_counts": dict(sorted(Counter(row.get("file") for row in rows).items())),
        "plan_counts": dict(sorted(Counter(row.get("plan_id") for row in rows).items())),
        "missing_plan_ids": missing_plan_ids,
        "missing_files": missing_files,
        **failing,
        "plan_gate_pass_rows": len(rows) if rows and all(value == 0 for value in failing.values()) else 0,
        "training_authorized": False,
        "decoder_ce_authorized": False,
        "passed": bool(rows) and all(value == 0 for value in failing.values()),
    }
