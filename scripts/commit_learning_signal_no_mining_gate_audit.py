#!/usr/bin/env python3
from __future__ import annotations

from typing import Any

try:
    from commit_learning_signal_contract_builder import (
        COMMIT_SIZE_BUCKETS,
        REQUIRED_FILTER_SIGNALS,
        REQUIRED_UNIT_LABELS,
        TARGET_SURFACES,
    )
except ModuleNotFoundError:  # pragma: no cover
    from scripts.commit_learning_signal_contract_builder import (
        COMMIT_SIZE_BUCKETS,
        REQUIRED_FILTER_SIGNALS,
        REQUIRED_UNIT_LABELS,
        TARGET_SURFACES,
    )

REQUIRED_CONTRACT_IDS = {
    "commit_admission_filter",
    "commit_size_policy",
    "commit_decomposition",
    "hunk_relevance_filter",
    "causal_edit_unit_schema",
    "structured_label_extraction",
    "counterfactual_sibling_generation",
    "bounded_decoder_target_gate",
    "provenance_locked_eval_boundary",
    "quality_metric_feedback",
}

REQUIRED_ANTI_CHEAT_KEYS = {
    "walks_arxiv_repositories",
    "reads_git_commits_now",
    "emits_training_rows_now",
    "opens_training",
    "opens_decoder_ce",
    "contains_patch_body_target",
    "uses_locked_eval_as_source",
}


def _open_values(mapping: dict[str, Any]) -> bool:
    return any(value is True for value in mapping.values())


def audit_commit_contract_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    missing_required_fields = []
    missing_acceptance_checks = []
    missing_filter_signal_rows = []
    missing_unit_label_rows = []
    missing_size_policy_rows = []
    missing_target_surface_rows = []
    missing_anti_cheat_rows = []
    authority_open_rows = []
    loss_open_rows = []
    opening_rows = []
    bad_route_rows = []
    decoder_target_policy_fail_rows = []
    source_gate_fail_rows = []

    for row in rows:
        row_id = row.get("row_id")
        if row.get("route") != "CONTRACT_ONLY_NO_MINING":
            bad_route_rows.append(row_id)
        if not row.get("required_fields"):
            missing_required_fields.append(row_id)
        if not row.get("acceptance_checks"):
            missing_acceptance_checks.append(row_id)
        if set(REQUIRED_FILTER_SIGNALS) - set(row.get("required_filter_signals", [])):
            missing_filter_signal_rows.append(row_id)
        if set(REQUIRED_UNIT_LABELS) - set(row.get("required_unit_labels", [])):
            missing_unit_label_rows.append(row_id)
        if set(COMMIT_SIZE_BUCKETS) - set(row.get("commit_size_buckets", {})):
            missing_size_policy_rows.append(row_id)
        if set(TARGET_SURFACES) - set(row.get("target_surfaces", [])):
            missing_target_surface_rows.append(row_id)
        anti_cheat = row.get("anti_cheat", {})
        if set(REQUIRED_ANTI_CHEAT_KEYS) - set(anti_cheat):
            missing_anti_cheat_rows.append(row_id)
        if _open_values(row.get("authority", {})):
            authority_open_rows.append(row_id)
        if _open_values(row.get("loss_mask", {})):
            loss_open_rows.append(row_id)
        if _open_values(anti_cheat):
            opening_rows.append(row_id)
        if row.get("contract_id") == "bounded_decoder_target_gate":
            checks = set(row.get("acceptance_checks", []))
            if "decoder_ce_still_closed" not in checks or "large_commit_decoder_blocked" not in checks:
                decoder_target_policy_fail_rows.append(row_id)
        if row.get("contract_id") == "provenance_locked_eval_boundary":
            fields = set(row.get("required_fields", []))
            checks = set(row.get("acceptance_checks", []))
            required_fields = {"source_provenance", "contamination_status", "locked_eval_exclusion", "gate_status"}
            required_checks = {"source_provenance_present", "contamination_pass_required", "locked_eval_not_mined"}
            if required_fields - fields or required_checks - checks:
                source_gate_fail_rows.append(row_id)

    contract_ids = {row.get("contract_id") for row in rows}
    missing_contract_ids = sorted(REQUIRED_CONTRACT_IDS - contract_ids)
    passed = not any([
        missing_required_fields,
        missing_acceptance_checks,
        missing_filter_signal_rows,
        missing_unit_label_rows,
        missing_size_policy_rows,
        missing_target_surface_rows,
        missing_anti_cheat_rows,
        authority_open_rows,
        loss_open_rows,
        opening_rows,
        bad_route_rows,
        decoder_target_policy_fail_rows,
        source_gate_fail_rows,
        missing_contract_ids,
    ])
    return {
        "passed": passed,
        "rows": len(rows),
        "gate_pass_rows": len(rows) if passed else 0,
        "missing_required_fields": missing_required_fields,
        "missing_acceptance_checks": missing_acceptance_checks,
        "missing_filter_signal_rows": missing_filter_signal_rows,
        "missing_unit_label_rows": missing_unit_label_rows,
        "missing_size_policy_rows": missing_size_policy_rows,
        "missing_target_surface_rows": missing_target_surface_rows,
        "missing_anti_cheat_rows": missing_anti_cheat_rows,
        "authority_open_rows": authority_open_rows,
        "loss_open_rows": loss_open_rows,
        "opening_rows": opening_rows,
        "bad_route_rows": bad_route_rows,
        "decoder_target_policy_fail_rows": decoder_target_policy_fail_rows,
        "source_gate_fail_rows": source_gate_fail_rows,
        "missing_contract_ids": missing_contract_ids,
        "missing_contract_id_count": len(missing_contract_ids),
        "commit_mining_authorized": False,
        "arxiv_repository_walk_authorized": False,
        "training_authorized": False,
        "decoder_ce_authorized": False,
    }
