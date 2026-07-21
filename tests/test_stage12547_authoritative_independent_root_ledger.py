from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/build_stage12547_authoritative_independent_root_ledger.py"
SPEC = importlib.util.spec_from_file_location("stage12547", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def row(lineage: str | None, **updates: object) -> dict[str, object]:
    value: dict[str, object] = {
        "root_lineage_key_hash": lineage,
        "repo_family_hash": "repo-a",
        "language_family": "python",
        "bucket": "train_support_only",
        "countable_train_support": True,
        "source_stage": "fixture",
    }
    value.update(updates)
    return value


def test_deduplicates_projections_and_sources_by_lineage() -> None:
    result = MODULE.build_ledger({
        "a": [row("lineage-a", task_projection="next"), row("lineage-a", task_projection="stop")],
        "b": [row("lineage-a", task_projection="verifier"), row("lineage-b")],
    })
    assert len(result["ledger"]) == 2
    first = next(item for item in result["ledger"] if item["canonical_identity"] == "lineage-a")
    assert first["materialized_row_count"] == 3
    assert first["countable_projection_row_count"] == 3


def test_root_alias_connects_sources_but_conflicting_lineages_fail_closed() -> None:
    result = MODULE.build_ledger({
        "a": [row("lineage-a", root_id_hash="root-1")],
        "b": [row("lineage-b", root_id_hash="root-1")],
    })
    assert result["ledger"] == []
    assert len(result["unresolved"]) == 2
    assert {item["reason"] for item in result["unresolved"]} == {"ambiguous_multiple_lineages_for_identity_component"}


def test_missing_identity_is_exposed_not_counted() -> None:
    result = MODULE.build_ledger({"a": [row(None)]})
    assert result["ledger"] == []
    assert result["unresolved"][0]["reason"] == "missing_root_and_lineage_identity"


def test_level3_claim_cannot_union_proof_across_rows() -> None:
    result = MODULE.build_ledger({"a": [
        row("lineage-a", level3_admitted=True, same_source_lineage_proof=True, state_before="before", observed_action="patch"),
        row("lineage-a", verifier_status="FAIL_TO_PASS", state_delta="fixed"),
    ]})
    item = result["ledger"][0]
    assert item["claimed_level3_or_repair"] is True
    assert item["same_row_causal_proof_present"] is False
    assert item["level3_repair_credit"] is False
    assert item["category"] == "verifier_observation_auxiliary"


def test_presence_only_causal_claim_is_rejected() -> None:
    claimed = row(
        "lineage-a",
        level3_admitted=True,
        same_source_lineage_proof=True,
        state_before_summary_codes=["failing"],
        observed_action_digest="patch-hash",
        observation_status_class="fail_to_pass",
        state_delta_codes=["selected_test_now_passes"],
    )
    result = MODULE.build_ledger({"a": [claimed]})
    assert result["ledger"][0]["level3_repair_credit"] is False
    assert "before_status_not_behavior_failure" in result["ledger"][0]["category_reasons"]


def test_structural_same_verifier_patch_effect_proof_grants_one_root_credit() -> None:
    proved = row(
        "lineage-a",
        level3_admitted=True,
        same_source_lineage_proof=True,
        source_provenance_class="external_repo_commit_pair",
        controlled_fixture_like=False,
        synthetic_source=False,
        state_before_summary_codes=["failing"],
        observed_action_digest="patch-hash",
        observation_status_class="fail_to_pass",
        state_delta_codes=["same_verifier_now_passes"],
        verifier_before_status="FAIL_CURRENT_STATE",
        verifier_after_status="PASS_CURRENT_STATE",
        verifier_before_identity_hash="v" * 64,
        verifier_after_identity_hash="v" * 64,
        test_tree_before_hash="t" * 64,
        test_tree_after_hash="t" * 64,
        patch_changed_test_files_count=0,
        patch_apply_status="APPLIED",
        revert_restores_failure=True,
        ordered_events=[
            "BEFORE_VERIFIER_RESULT",
            "PATCH_APPLY",
            "AFTER_VERIFIER_RESULT",
        ],
        protected_overlap_audit_pass=True,
        protected_overlap_count=0,
    )
    result = MODULE.build_ledger({"a": [proved, dict(proved, task_projection="stop")]})
    assert len(result["ledger"]) == 1
    assert result["ledger"][0]["category"] == "causal_repair_patch_trace"
    assert result["ledger"][0]["level3_repair_credit"] is True


def test_requested_orders_are_non_root_controls() -> None:
    result = MODULE.build_ledger({"stage12448_executor_lane_orders": [{"target_candidate_floor": 100}]})
    assert result["ledger"] == []
    assert result["unresolved"] == []
    assert len(result["controls"]) == 1


def test_requested_category_partition_is_root_level() -> None:
    result = MODULE.build_ledger({"a": [
        row("aux", verifier_status="PASS_CURRENT_STATE"),
        row("sealed", strict_eval_eligible=True),
        row("safe", target_semantic_value="PASS_TO_PASS"),
        row("negative", verifier_status="INSUFFICIENT_EVIDENCE"),
    ]})
    assert result["coverage"]["category"] == {
        "negative": 1,
        "safe_refactor": 1,
        "sealed_transition": 1,
        "verifier_observation_auxiliary": 1,
    }


def test_repository_materialization_reports_27_not_101_projection_rows() -> None:
    materialized = {name: MODULE.read_jsonl(path) for name, path in MODULE.MATERIALIZED_FILES.items()}
    result = MODULE.build_ledger(materialized)
    assert len(materialized["stage12533_countable_rows"]) == 101
    assert len(result["ledger"]) == 27
    assert result["coverage"]["language"] == {
        "c_cpp": 2,
        "python": 14,
        "rust": 5,
        "web_js_ts_html": 6,
    }
    assert not any(item["level3_repair_credit"] for item in result["ledger"])


def test_source_native_alias_merges_stage12203_and_stage12204_views() -> None:
    ledger = [
        {
            "canonical_identity": "0e1d4e5d1b1f67ea75049c5f",
            "identity_basis": "lineage",
            "root_aliases": [],
            "lineage_aliases": ["0e1d4e5d1b1f67ea75049c5f"],
            "category": "verifier_observation_auxiliary",
            "category_reasons": [],
            "language_family": "python",
            "split": "train_support_only",
            "source_stages": ["stage12203"],
            "source_materializations": ["a"],
            "source_row_refs": ["a:1"],
            "materialized_row_count": 2,
            "countable_projection_row_count": 2,
            "demoted_projection_row_count": 0,
            "claimed_level3_or_repair": False,
            "same_row_causal_proof_present": False,
            "level3_repair_credit": False,
            "training_allowed": False,
        },
        {
            "canonical_identity": "e91dbb35c01782aa28493abb",
            "identity_basis": "lineage",
            "root_aliases": [],
            "lineage_aliases": ["e91dbb35c01782aa28493abb"],
            "category": "verifier_observation_auxiliary",
            "category_reasons": [],
            "language_family": "python",
            "split": "train_support_only",
            "source_stages": ["stage12204"],
            "source_materializations": ["b"],
            "source_row_refs": ["b:1"],
            "materialized_row_count": 2,
            "countable_projection_row_count": 2,
            "demoted_projection_row_count": 0,
            "claimed_level3_or_repair": False,
            "same_row_causal_proof_present": False,
            "level3_repair_credit": False,
            "training_allowed": False,
        },
    ]
    canonical, audit = MODULE.canonicalize_known_aliases(ledger)
    assert len(canonical) == 1
    assert canonical[0]["identity_basis"] == "source_native_episode_alias"
    assert canonical[0]["countable_projection_row_count"] == 4
    assert audit[0]["decision"] == "aliases_merged"


def test_legacy_group_demotion_is_reaudited_per_row_not_propagated() -> None:
    rows = [
        {
            "root_lineage_key_hash": "root-a",
            "collapse_demoted_from_countable": True,
            "task_projection": "transition_candidate_selection",
            "target_semantic_value": "candidate_selected_test_backed",
        },
        {
            "root_lineage_key_hash": "root-a",
            "collapse_demoted_from_countable": True,
            "task_projection": "transition_next_action",
            "target_semantic_value": "action_run_selected_verifier",
        },
        {
            "root_lineage_key_hash": "root-a",
            "collapse_demoted_from_countable": True,
            "task_projection": "transition_verifier_transition",
            "target_semantic_value": "status_pass_current_state",
        },
    ]
    audit = MODULE.demotion_reaudit(rows)
    assert audit[0]["generic_target_outside_candidate_selection"] is False
    assert audit[0]["distinct_target_count"] == 3
    assert audit[0]["reaudit_decision"].startswith("legacy_group_rule_false_positive")
    assert audit[0]["restoration_authorized"] is False


def test_repository_canonical_counts_separate_candidates_from_causal_credit(tmp_path) -> None:
    old_out, old_summary = MODULE.OUT, MODULE.SUMMARY
    try:
        MODULE.OUT = tmp_path / "out"
        MODULE.SUMMARY = tmp_path / "summary.json"
        assert MODULE.main() == 0
        summary = MODULE.read_json(MODULE.SUMMARY)
    finally:
        MODULE.OUT, MODULE.SUMMARY = old_out, old_summary

    assert summary["stage_local_identifiable_root_count"] == 27
    assert summary["canonical_materialized_candidate_root_count"] == 26
    assert summary["legacy_flagged_countable_auxiliary_root_count"] == 13
    assert summary["legacy_demoted_only_root_count_pending_reaudit"] == 13
    assert summary["legacy_demotion_false_positive_candidate_root_count"] == 13
    assert summary["accepted_causal_campaign_root_count"] == 0
    assert summary["accepted_causal_campaign_gap_to_500"] == 500
    assert summary["coverage"]["category"]["causal_repair_patch_trace"] == 0
    assert summary["coverage"]["category"]["sealed_transition"] == 0
    assert summary["training_allowed"] is False
