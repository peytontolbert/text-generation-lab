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

TARGET_SURFACES = [
    "edit_localization",
    "patch_operator",
    "file_plan",
    "symbol_binding",
    "verifier_repair",
    "action_sequence",
    "needs_verification",
    "retrieval_coverage",
]

COMMIT_SIZE_BUCKETS = {
    "small": {
        "changed_file_range": "1-3",
        "use": ["structured_labels", "localized_context", "bounded_decoder_candidate_if_clean"],
    },
    "medium": {
        "changed_file_range": "4-10",
        "use": ["structured_labels", "clustered_units", "selective_bounded_decoder_candidate"],
    },
    "large": {
        "changed_file_range": "10+",
        "use": ["decompose_first", "retrieval_context", "repo_graph_signal", "verifier_planning"],
    },
}

REQUIRED_FILTER_SIGNALS = [
    "semantic_similarity_to_commit_message",
    "test_overlap_or_test_reference",
    "import_call_dependency_proximity",
    "executable_logic_change",
    "identifier_introduced_and_consumed",
    "generated_or_vendor_or_lockfile_detector",
    "formatting_or_rename_only_detector",
    "config_schema_dependency_required",
]

REQUIRED_UNIT_LABELS = ["core", "supporting", "incidental", "noise"]

CONTRACT_ROWS = [
    {
        "contract_id": "commit_admission_filter",
        "purpose": "Reject merge/generated/vendor/format-only/lockfile-only commits before learning-signal construction.",
        "required_fields": ["repo_id", "commit_sha", "parent_sha", "changed_files", "commit_message", "admission_route"],
        "acceptance_checks": ["merge_commit_rejected", "generated_vendor_filtered", "format_only_filtered", "license_provenance_present"],
    },
    {
        "contract_id": "commit_size_policy",
        "purpose": "Route small, medium, and large commits into different supervision paths instead of treating every commit as one example.",
        "required_fields": ["changed_file_count", "diff_line_count", "size_bucket", "allowed_training_uses"],
        "acceptance_checks": ["small_medium_large_thresholds_present", "large_commit_decoder_blocked", "medium_commit_segmentation_required"],
    },
    {
        "contract_id": "commit_decomposition",
        "purpose": "Split commits into file clusters, symbol clusters, hunk groups, and test-code pairs.",
        "required_fields": ["cluster_id", "cluster_type", "member_files", "member_hunks", "dependency_links"],
        "acceptance_checks": ["cluster_members_nonempty", "dependency_links_present", "unrelated_cluster_separated"],
    },
    {
        "contract_id": "hunk_relevance_filter",
        "purpose": "Classify each hunk as core, supporting, incidental, or noise using evidence-based filter signals.",
        "required_fields": ["hunk_id", "relevance_label", "filter_scores", "kept_for_unit"],
        "acceptance_checks": ["all_filter_signals_present", "all_relevance_labels_supported", "noise_hunks_not_decoder_targets"],
    },
    {
        "contract_id": "causal_edit_unit_schema",
        "purpose": "Emit coherent causal edit units with enough evidence to explain why the kept patch fragment belongs together.",
        "required_fields": ["unit_id", "intent", "core_hunks", "supporting_hunks", "dropped_hunks", "behavioral_closure_rationale"],
        "acceptance_checks": ["core_hunks_present", "supporting_hunks_optional_but_explained", "behavioral_closure_checked"],
    },
    {
        "contract_id": "structured_label_extraction",
        "purpose": "Convert causal units into typed supervision for maintainer heads before any decoder target is considered.",
        "required_fields": ["target_surfaces", "operator_labels", "edit_targets", "test_targets", "retrieval_targets"],
        "acceptance_checks": ["target_surfaces_present", "operator_label_nonempty", "edit_localization_nonempty", "verifier_target_present"],
    },
    {
        "contract_id": "counterfactual_sibling_generation",
        "purpose": "Generate contrastive siblings from each causal unit so the model learns decision boundaries, not commit memorization.",
        "required_fields": ["sibling_group_id", "positive_original", "evidence_removed", "distractor_added", "ambiguous_retrieve_more"],
        "acceptance_checks": ["positive_and_negative_siblings_present", "evidence_removed_flips_route", "distractor_not_selected"],
    },
    {
        "contract_id": "bounded_decoder_target_gate",
        "purpose": "Allow decoder targets only for compact, low-entropy, localized units after structured labels and gates pass.",
        "required_fields": ["decoder_candidate_allowed", "target_line_count", "target_file_count", "entropy_risk", "localization_confidence"],
        "acceptance_checks": ["decoder_ce_still_closed", "large_commit_decoder_blocked", "compact_target_thresholds_present"],
    },
    {
        "contract_id": "provenance_locked_eval_boundary",
        "purpose": "Keep source lineage, license/security filters, contamination checks, and locked eval separation attached to every mined unit.",
        "required_fields": ["source_provenance", "license_route", "contamination_status", "locked_eval_exclusion", "gate_status"],
        "acceptance_checks": ["source_provenance_present", "contamination_pass_required", "locked_eval_not_mined"],
    },
    {
        "contract_id": "quality_metric_feedback",
        "purpose": "Judge the miner by downstream structured-head signal quality rather than raw commit volume.",
        "required_fields": ["quality_metrics", "expected_downstream_surfaces", "reject_reasons"],
        "acceptance_checks": ["localization_metric_defined", "operator_metric_defined", "verifier_metric_defined", "junk_ranker_route_defined"],
    },
]


def build_commit_learning_signal_rows() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for row in CONTRACT_ROWS:
        rows.append({
            "row_id": f"stage8855_commit_learning_signal_contract::{row['contract_id']}",
            "semantic_key": f"commit_learning_signal_contract:{row['contract_id']}",
            "source_stage": "stage8855_recovered_from_commit_mining_guidance",
            "objective_family": "commit_learning_signal_contract",
            "split": "contract",
            "route": "CONTRACT_ONLY_NO_MINING",
            "contract_id": row["contract_id"],
            "purpose": row["purpose"],
            "required_fields": row["required_fields"],
            "acceptance_checks": row["acceptance_checks"],
            "target_surfaces": TARGET_SURFACES,
            "commit_size_buckets": COMMIT_SIZE_BUCKETS,
            "required_filter_signals": REQUIRED_FILTER_SIGNALS,
            "required_unit_labels": REQUIRED_UNIT_LABELS,
            "authority": dict(AUTHORITY_CLOSED),
            "loss_mask": dict(LOSS_MASK_CLOSED),
            "anti_cheat": {
                "walks_arxiv_repositories": False,
                "reads_git_commits_now": False,
                "emits_training_rows_now": False,
                "opens_training": False,
                "opens_decoder_ce": False,
                "contains_patch_body_target": False,
                "uses_locked_eval_as_source": False,
            },
            "hard_blockers": [
                "contract_only",
                "no_arxiv_repository_walk_authorized",
                "no_commit_mining_authorized_by_this_stage",
                "training_not_authorized",
                "decoder_ce_not_authorized",
            ],
        })
    return rows


def build_card(rows: list[dict[str, Any]]) -> dict[str, Any]:
    missing_required_fields = 0
    missing_acceptance_checks = 0
    missing_filter_signal_rows = 0
    missing_size_policy_rows = 0
    missing_target_surface_rows = 0
    authority_open_rows = 0
    loss_open_rows = 0
    opening_rows = 0
    bad_route_rows = 0
    for row in rows:
        if row.get("route") != "CONTRACT_ONLY_NO_MINING":
            bad_route_rows += 1
        if not row.get("required_fields"):
            missing_required_fields += 1
        if not row.get("acceptance_checks"):
            missing_acceptance_checks += 1
        if set(REQUIRED_FILTER_SIGNALS) - set(row.get("required_filter_signals", [])):
            missing_filter_signal_rows += 1
        if set(COMMIT_SIZE_BUCKETS) - set(row.get("commit_size_buckets", {})):
            missing_size_policy_rows += 1
        if set(TARGET_SURFACES) - set(row.get("target_surfaces", [])):
            missing_target_surface_rows += 1
        if any((row.get("authority") or {}).values()):
            authority_open_rows += 1
        if any((row.get("loss_mask") or {}).values()):
            loss_open_rows += 1
        if any((row.get("anti_cheat") or {}).values()):
            opening_rows += 1
    failing = {
        "missing_required_fields": missing_required_fields,
        "missing_acceptance_checks": missing_acceptance_checks,
        "missing_filter_signal_rows": missing_filter_signal_rows,
        "missing_size_policy_rows": missing_size_policy_rows,
        "missing_target_surface_rows": missing_target_surface_rows,
        "authority_open_rows": authority_open_rows,
        "loss_open_rows": loss_open_rows,
        "opening_rows": opening_rows,
        "bad_route_rows": bad_route_rows,
    }
    return {
        "rows": len(rows),
        "contract_counts": dict(sorted(Counter(row["contract_id"] for row in rows).items())),
        "target_surfaces": TARGET_SURFACES,
        "commit_size_buckets": COMMIT_SIZE_BUCKETS,
        "required_filter_signals": REQUIRED_FILTER_SIGNALS,
        "required_unit_labels": REQUIRED_UNIT_LABELS,
        **failing,
        "contract_ready_rows": len(rows) if rows and all(value == 0 for value in failing.values()) else 0,
        "commit_mining_authorized": False,
        "arxiv_repository_walk_authorized": False,
        "training_authorized": False,
        "decoder_ce_authorized": False,
        "passed": bool(rows) and all(value == 0 for value in failing.values()),
    }
