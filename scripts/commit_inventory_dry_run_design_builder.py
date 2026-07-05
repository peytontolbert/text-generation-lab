#!/usr/bin/env python3
from __future__ import annotations

from collections import Counter
from typing import Any

try:
    from scripts.model_output_packet_telemetry_contract_builder import AUTHORITY_CLOSED
except ModuleNotFoundError:  # pragma: no cover
    from model_output_packet_telemetry_contract_builder import AUTHORITY_CLOSED

LOSS_MASK_CLOSED = {
    "decoder_ce": False,
    "denoise_ce": False,
    "runtime_reward": False,
    "heldout_eval_metric": False,
}

INVENTORY_FIELDS = [
    "repo_id",
    "repo_path_alias",
    "source_inventory_id",
    "source_provenance_id",
    "license_route",
    "contamination_route",
    "locked_eval_exclusion",
    "commit_count_cap",
    "branch_policy",
    "commit_metadata_fields",
    "diff_stat_fields",
    "size_bucket_policy",
    "admission_filters",
    "redaction_policy",
    "output_manifest_schema",
]

COMMIT_METADATA_FIELDS = [
    "commit_sha",
    "parent_sha",
    "author_time_bucket",
    "commit_message_hash",
    "commit_message_summary_features",
    "changed_file_count",
    "diff_line_count",
    "test_file_touch_count",
    "config_file_touch_count",
    "generated_vendor_lockfile_touch_count",
]

CAPS_AND_BOUNDS = {
    "repositories_per_dry_run": 0,
    "commits_read_per_repo": 0,
    "diff_bodies_read": 0,
    "patch_bodies_emitted": 0,
    "training_rows_emitted": 0,
    "max_future_inventory_repositories_per_batch": 25,
    "max_future_commit_headers_per_repo": 200,
    "max_future_diffstat_only_commits_per_repo": 100,
}

DESIGN_ROWS = [
    {
        "design_id": "inventory_source_gate_inputs",
        "purpose": "Require source lineage, provenance, license/security, contamination, locked-eval, cluster, and junk/OOD gates before any repo can be inventoried later.",
        "required_fields": ["source_inventory_id", "source_provenance_id", "license_route", "contamination_route", "locked_eval_exclusion", "gate_status"],
        "acceptance_checks": ["all_source_gates_declared", "locked_eval_excluded", "contamination_required_before_future_walk"],
    },
    {
        "design_id": "dry_run_caps_and_authority",
        "purpose": "Keep this stage as schema/caps only with zero repository walks, zero commit reads, and zero row emission.",
        "required_fields": ["repositories_per_dry_run", "commits_read_per_repo", "diff_bodies_read", "training_rows_emitted"],
        "acceptance_checks": ["repository_walk_count_zero", "commit_read_count_zero", "training_row_count_zero"],
    },
    {
        "design_id": "future_commit_header_inventory_schema",
        "purpose": "Define commit-header and diffstat fields for a later authorized inventory pass without reading those commits now.",
        "required_fields": COMMIT_METADATA_FIELDS,
        "acceptance_checks": ["commit_header_fields_declared", "message_hash_not_raw_message_required", "diffstat_not_patch_body"],
    },
    {
        "design_id": "future_size_bucket_and_admission_policy",
        "purpose": "Route future commits by size and admission filters before any causal edit-unit construction.",
        "required_fields": ["size_bucket_policy", "admission_filters", "reject_routes", "hold_routes"],
        "acceptance_checks": ["small_medium_large_buckets_declared", "merge_commit_reject_route", "generated_vendor_lockfile_route"],
    },
    {
        "design_id": "future_output_manifest_schema",
        "purpose": "Define future inventory output as metadata only, never source bodies, patch bodies, training rows, or decoder targets.",
        "required_fields": ["repo_inventory_card", "commit_header_card", "diffstat_card", "quality_route_card"],
        "acceptance_checks": ["no_patch_body_fields", "no_decoder_target_fields", "no_train_split_fields"],
    },
]


def build_inventory_design_rows() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for row in DESIGN_ROWS:
        rows.append({
            "row_id": f"stage8865_commit_inventory_dry_run_design::{row['design_id']}",
            "semantic_key": f"commit_inventory_dry_run_design:{row['design_id']}",
            "source_stage": "stage8865_from_stage8863_gap_walk",
            "objective_family": "commit_inventory_dry_run_design",
            "split": "design",
            "route": "DRY_RUN_DESIGN_ONLY_NO_REPO_WALK",
            "design_id": row["design_id"],
            "purpose": row["purpose"],
            "required_fields": row["required_fields"],
            "acceptance_checks": row["acceptance_checks"],
            "inventory_fields": INVENTORY_FIELDS,
            "commit_metadata_fields": COMMIT_METADATA_FIELDS,
            "caps_and_bounds": CAPS_AND_BOUNDS,
            "authority": dict(AUTHORITY_CLOSED),
            "loss_mask": dict(LOSS_MASK_CLOSED),
            "anti_cheat": {
                "walks_arxiv_repositories": False,
                "reads_git_commits_now": False,
                "reads_diff_bodies_now": False,
                "emits_patch_bodies": False,
                "emits_training_rows_now": False,
                "opens_training": False,
                "opens_decoder_ce": False,
                "uses_locked_eval_as_source": False,
            },
            "hard_blockers": [
                "dry_run_design_only",
                "no_arxiv_repository_walk_authorized",
                "no_commit_reads_authorized",
                "no_diff_body_reads_authorized",
                "training_not_authorized",
                "decoder_ce_not_authorized",
            ],
        })
    return rows


def build_card(rows: list[dict[str, Any]]) -> dict[str, Any]:
    missing_required_fields = 0
    missing_acceptance_checks = 0
    missing_inventory_fields = 0
    missing_commit_fields = 0
    bad_caps_rows = 0
    authority_open_rows = 0
    loss_open_rows = 0
    opening_rows = 0
    bad_route_rows = 0
    for row in rows:
        if row.get("route") != "DRY_RUN_DESIGN_ONLY_NO_REPO_WALK":
            bad_route_rows += 1
        if not row.get("required_fields"):
            missing_required_fields += 1
        if not row.get("acceptance_checks"):
            missing_acceptance_checks += 1
        if set(INVENTORY_FIELDS) - set(row.get("inventory_fields", [])):
            missing_inventory_fields += 1
        if set(COMMIT_METADATA_FIELDS) - set(row.get("commit_metadata_fields", [])):
            missing_commit_fields += 1
        caps = row.get("caps_and_bounds", {})
        if any(caps.get(key) != 0 for key in ["repositories_per_dry_run", "commits_read_per_repo", "diff_bodies_read", "patch_bodies_emitted", "training_rows_emitted"]):
            bad_caps_rows += 1
        if any((row.get("authority") or {}).values()):
            authority_open_rows += 1
        if any((row.get("loss_mask") or {}).values()):
            loss_open_rows += 1
        if any((row.get("anti_cheat") or {}).values()):
            opening_rows += 1
    failing = {
        "missing_required_fields": missing_required_fields,
        "missing_acceptance_checks": missing_acceptance_checks,
        "missing_inventory_fields": missing_inventory_fields,
        "missing_commit_fields": missing_commit_fields,
        "bad_caps_rows": bad_caps_rows,
        "authority_open_rows": authority_open_rows,
        "loss_open_rows": loss_open_rows,
        "opening_rows": opening_rows,
        "bad_route_rows": bad_route_rows,
    }
    return {
        "rows": len(rows),
        "design_counts": dict(sorted(Counter(row["design_id"] for row in rows).items())),
        "inventory_fields": INVENTORY_FIELDS,
        "commit_metadata_fields": COMMIT_METADATA_FIELDS,
        "caps_and_bounds": CAPS_AND_BOUNDS,
        **failing,
        "dry_run_design_ready_rows": len(rows) if rows and all(value == 0 for value in failing.values()) else 0,
        "arxiv_repository_walk_authorized": False,
        "commit_reads_authorized": False,
        "commit_mining_authorized": False,
        "training_authorized": False,
        "decoder_ce_authorized": False,
        "passed": bool(rows) and all(value == 0 for value in failing.values()),
    }
