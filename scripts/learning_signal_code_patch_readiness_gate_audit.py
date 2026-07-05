#!/usr/bin/env python3
from __future__ import annotations

from typing import Any

try:
    from learning_signal_code_patch_readiness_builder import GLOBAL_PATCH_PREFLIGHTS, PATCH_ORDER
    from learning_signal_implementation_plan_gate_audit import REQUIRED_FILES, REQUIRED_PLAN_IDS
except ModuleNotFoundError:  # pragma: no cover
    from scripts.learning_signal_code_patch_readiness_builder import GLOBAL_PATCH_PREFLIGHTS, PATCH_ORDER
    from scripts.learning_signal_implementation_plan_gate_audit import REQUIRED_FILES, REQUIRED_PLAN_IDS


def _authority_open(row: dict[str, Any]) -> bool:
    authority = row.get("authority", {})
    return any(value is True for value in authority.values())


def _loss_open(row: dict[str, Any]) -> bool:
    loss_mask = row.get("loss_mask", {})
    return any(value is True for value in loss_mask.values())


def audit_readiness_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    missing_global_preflight_rows = []
    missing_patch_order_rows = []
    missing_required_check_rows = []
    missing_plan_coverage_rows = []
    authority_open_rows = []
    loss_open_rows = []
    opening_rows = []
    bad_route_rows = []

    expected_preflights = set(GLOBAL_PATCH_PREFLIGHTS)
    expected_order = list(PATCH_ORDER)

    for row in rows:
        row_id = row.get("row_id")
        if row.get("route") != "CODE_PATCH_READINESS_ONLY":
            bad_route_rows.append(row_id)
        if _authority_open(row):
            authority_open_rows.append(row_id)
        if _loss_open(row):
            loss_open_rows.append(row_id)
        if any(row.get("anti_cheat", {}).values()):
            opening_rows.append(row_id)
        if set(row.get("global_patch_preflights", [])) != expected_preflights:
            missing_global_preflight_rows.append(row_id)
        if row.get("patch_order") != expected_order:
            missing_patch_order_rows.append(row_id)
        if not row.get("required_checks"):
            missing_required_check_rows.append(row_id)
        coverage = row.get("plan_coverage", {})
        if coverage.get("missing_plan_ids") or coverage.get("missing_files"):
            missing_plan_coverage_rows.append(row_id)

    seen_plan_ids = set()
    seen_files = set()
    for row in rows:
        coverage = row.get("plan_coverage", {})
        seen_plan_ids.update(coverage.get("plan_ids", []))
        seen_files.update(coverage.get("files", []))

    missing_plan_ids = sorted(set(REQUIRED_PLAN_IDS) - seen_plan_ids)
    missing_files = sorted(set(REQUIRED_FILES) - seen_files)
    passed = not any([
        missing_global_preflight_rows,
        missing_patch_order_rows,
        missing_required_check_rows,
        missing_plan_coverage_rows,
        authority_open_rows,
        loss_open_rows,
        opening_rows,
        bad_route_rows,
        missing_plan_ids,
        missing_files,
    ])
    return {
        "passed": passed,
        "rows": len(rows),
        "readiness_gate_pass_rows": len(rows) if passed else 0,
        "missing_global_preflight_rows": missing_global_preflight_rows,
        "missing_patch_order_rows": missing_patch_order_rows,
        "missing_required_check_rows": missing_required_check_rows,
        "missing_plan_coverage_rows": missing_plan_coverage_rows,
        "authority_open_rows": authority_open_rows,
        "loss_open_rows": loss_open_rows,
        "opening_rows": opening_rows,
        "bad_route_rows": bad_route_rows,
        "missing_plan_ids": missing_plan_ids,
        "missing_files": missing_files,
        "missing_plan_id_count": len(missing_plan_ids),
        "missing_file_count": len(missing_files),
        "code_patch_authorized": False,
        "training_authorized": False,
        "decoder_ce_authorized": False,
    }
