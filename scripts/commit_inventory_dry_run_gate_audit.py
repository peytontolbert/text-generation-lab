#!/usr/bin/env python3
from __future__ import annotations

from typing import Any

try:
    from commit_inventory_dry_run_design_builder import COMMIT_METADATA_FIELDS, INVENTORY_FIELDS
except ModuleNotFoundError:  # pragma: no cover
    from scripts.commit_inventory_dry_run_design_builder import COMMIT_METADATA_FIELDS, INVENTORY_FIELDS

REQUIRED_DESIGN_IDS = {
    "inventory_source_gate_inputs",
    "dry_run_caps_and_authority",
    "future_commit_header_inventory_schema",
    "future_size_bucket_and_admission_policy",
    "future_output_manifest_schema",
}

REQUIRED_ZERO_CAP_KEYS = {
    "repositories_per_dry_run",
    "commits_read_per_repo",
    "diff_bodies_read",
    "patch_bodies_emitted",
    "training_rows_emitted",
}

REQUIRED_ANTI_CHEAT_KEYS = {
    "walks_arxiv_repositories",
    "reads_git_commits_now",
    "reads_diff_bodies_now",
    "emits_patch_bodies",
    "emits_training_rows_now",
    "opens_training",
    "opens_decoder_ce",
    "uses_locked_eval_as_source",
}


def _open_values(mapping: dict[str, Any]) -> bool:
    return any(value is True for value in mapping.values())


def audit_inventory_design_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    missing_required_fields = []
    missing_acceptance_checks = []
    missing_inventory_fields = []
    missing_commit_fields = []
    missing_zero_caps = []
    missing_anti_cheat_rows = []
    authority_open_rows = []
    loss_open_rows = []
    opening_rows = []
    bad_route_rows = []
    patch_body_field_rows = []
    train_field_rows = []

    for row in rows:
        row_id = row.get("row_id")
        if row.get("route") != "DRY_RUN_DESIGN_ONLY_NO_REPO_WALK":
            bad_route_rows.append(row_id)
        if not row.get("required_fields"):
            missing_required_fields.append(row_id)
        if not row.get("acceptance_checks"):
            missing_acceptance_checks.append(row_id)
        if set(INVENTORY_FIELDS) - set(row.get("inventory_fields", [])):
            missing_inventory_fields.append(row_id)
        if set(COMMIT_METADATA_FIELDS) - set(row.get("commit_metadata_fields", [])):
            missing_commit_fields.append(row_id)
        caps = row.get("caps_and_bounds", {})
        if any(caps.get(key) != 0 for key in REQUIRED_ZERO_CAP_KEYS):
            missing_zero_caps.append(row_id)
        anti_cheat = row.get("anti_cheat", {})
        if set(REQUIRED_ANTI_CHEAT_KEYS) - set(anti_cheat):
            missing_anti_cheat_rows.append(row_id)
        if _open_values(row.get("authority", {})):
            authority_open_rows.append(row_id)
        if _open_values(row.get("loss_mask", {})):
            loss_open_rows.append(row_id)
        if _open_values(anti_cheat):
            opening_rows.append(row_id)
        all_fields = set(row.get("required_fields", [])) | set(row.get("inventory_fields", [])) | set(row.get("commit_metadata_fields", []))
        if any("patch_body" in field or field == "diff_body" for field in all_fields):
            patch_body_field_rows.append(row_id)
        if any(field in {"train_split", "decoder_target", "patch_target"} for field in all_fields):
            train_field_rows.append(row_id)

    design_ids = {row.get("design_id") for row in rows}
    missing_design_ids = sorted(REQUIRED_DESIGN_IDS - design_ids)
    passed = not any([
        missing_required_fields,
        missing_acceptance_checks,
        missing_inventory_fields,
        missing_commit_fields,
        missing_zero_caps,
        missing_anti_cheat_rows,
        authority_open_rows,
        loss_open_rows,
        opening_rows,
        bad_route_rows,
        patch_body_field_rows,
        train_field_rows,
        missing_design_ids,
    ])
    return {
        "passed": passed,
        "rows": len(rows),
        "gate_pass_rows": len(rows) if passed else 0,
        "missing_required_fields": missing_required_fields,
        "missing_acceptance_checks": missing_acceptance_checks,
        "missing_inventory_fields": missing_inventory_fields,
        "missing_commit_fields": missing_commit_fields,
        "missing_zero_caps": missing_zero_caps,
        "missing_anti_cheat_rows": missing_anti_cheat_rows,
        "authority_open_rows": authority_open_rows,
        "loss_open_rows": loss_open_rows,
        "opening_rows": opening_rows,
        "bad_route_rows": bad_route_rows,
        "patch_body_field_rows": patch_body_field_rows,
        "train_field_rows": train_field_rows,
        "missing_design_ids": missing_design_ids,
        "missing_design_id_count": len(missing_design_ids),
        "arxiv_repository_walk_authorized": False,
        "commit_reads_authorized": False,
        "commit_mining_authorized": False,
        "training_authorized": False,
        "decoder_ce_authorized": False,
    }
