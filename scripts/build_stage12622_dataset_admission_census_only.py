#!/usr/bin/env python3
"""Build Stage12622 dataset admission census only.

Stage12621 paused VM implementation and made admitted dataset scale/quality the
critical path. This stage inventories the current admitted/train-ready supply and
remaining scale gap. It does not admit new rows, run training, allocate GPUs,
resume VM work, run replay, or claim Level-3 materialization.
"""
from __future__ import annotations

import hashlib
import json
import os
from collections import Counter
from pathlib import Path
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12622_dataset_admission_census_only"
OUT = ROOT / "runs/local/artifacts" / STAGE
SUMMARY = ROOT / "runs/summaries" / f"{STAGE}.json"
S12621_SUMMARY = ROOT / "runs/summaries/stage12621_no_vm_dataset_admission_realignment.json"
S12376_SUMMARY = ROOT / "runs/summaries/stage12376_combined_train_support_ledger_v11.json"
S12419_SUMMARY = ROOT / "runs/summaries/stage12419_current_dataset_control_board_v17.json"
STRICT_CARD = ROOT / "runs/local/artifacts/strict_long_context_train_ready_plus_audit_v1/strict_long_context_training_dataset_card.json"
BUNDLE_CARD = ROOT / "runs/local/artifacts/strict_software_maintainer_training_bundle_plus_audit_v1/strict_software_maintainer_training_bundle_card.json"
TRAINABLE_SHARDS = ROOT / "configs/software_maintainer/strict_long_context_trainable_shards_with_audit_only_v1.json"
ADMISSION_MANIFEST = ROOT / "runs/local/artifacts/long_context_dataset_admission_manifest_v1/long_context_dataset_admission_manifest.json"
SAMPLED_MANIFEST = ROOT / "runs/local/artifacts/strict_long_context_sampled_manifest_split_plus_audit_groupaware_v1/strict_long_context_sampled_manifest.jsonl"
SPLIT_ROWS = ROOT / "runs/local/artifacts/strict_long_context_split_rows_plus_audit_groupaware_v1/strict_long_context_split_rows.jsonl"
EXPECTED_HASHES = {
    "stage12621_summary": "2ea518b99d33b4c8708de104e856993c8edab0971b651b279de9fc578362bfb9",
    "stage12376_summary": "a7aa3bcae28c5741f1955d2b954744143266bb61d2e824d78343e932cc3b695e",
    "stage12419_summary": "61b8a0541c06cec23ac06d75e5da9679c073d7615b97ee2257748049e4d5d954",
    "strict_long_context_card": "4651e42fb28e7d1c1461bd1010c6b121a9391d8f296ce7c9bbf931b1f6f6f639",
    "strict_software_bundle_card": "3d8a514a2f0cfd68bde9afe3af239be97dd9b3063e39460acc5615eb31803700",
    "trainable_shards_manifest": "27701a98716296f68f317550c0f3d3867d5c9a2edbfceaeaee732b5a19226a1b",
    "admission_manifest": "8cf5bb10e84db65c3adb9c2434af976938c902347f22a9bd0be74275e7b33646",
}
EXPECTED_SPLIT_COUNTS = {"train": 589, "eval": 126, "strict_eval": 36}
EXPECTED_SPLIT_ROW_TOTAL = 751

FALSE_FIELDS = (
    "implementation_ready", "dataset_admission_allowed", "dataset_rows_admitted", "new_rows_admitted",
    "frontier_100m_training_dataset_ready", "source_packet_implementation_allowed", "source_packet_executable",
    "stage12620_allowed", "stage12621_allowed", "stage12622_allowed", "stage12623_allowed",
    "vm_branch_active", "vm_runner_implementation_allowed", "vm_runner_implementation_ready",
    "vm_runner_execution_allowed", "vm_runner_evidence_present", "vm_runner_trustworthy",
    "storage_root_created", "storage_write_performed", "execution_performed", "replay_trustworthy",
    "raw_replay_evidence_present", "trusted_replay_raw_evidence_present", "causal_transition_atoms_present",
    "causal_transition_atoms_allowed", "level3_preflight_allowed", "level_3_materialized",
    "level_3_materialization_allowed", "training_admission_preflight_allowed", "training_admission_allowed",
    "training_admitted", "training_allowed", "training_run_allowed", "gpu_allocation_requested",
    "cuda2_training_allowed", "strict_eval_admitted", "sealed_eval_admitted", "strict_eval_eligible",
    "sealed_eval_eligible", "admission_allowed", "ranking_allowed", "positive_stop",
)
PUBLIC_FORBIDDEN_SUBSTRINGS = (
    "/data/", "/arxiv/", "agentkernel_vm_replay", "/dev/", "selector", "raw_stream",
    "stdout.raw", "stderr.raw", "before_commit_oid", "after_commit_oid", "production_path",
    "production_patch_sha256", "manual_executor_slot_contracts", "slot_1.patch",
    "slot_2.patch", "repository_root", "patch_path", "slot_1/", "slot_2/",
)


class DatasetCensusError(RuntimeError):
    pass


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("ascii")


def stable_hash(value: Any) -> str:
    return sha256_bytes(canonical_bytes(value))


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise DatasetCensusError("json_object_required:" + path.name)
    return value


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    data = json.dumps(value, indent=2, sort_keys=True, ensure_ascii=True).encode("ascii") + b"\n"
    with path.open("wb") as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())


def no_claim_fields() -> dict[str, Any]:
    return {field: False for field in FALSE_FIELDS}


def check_false(record: Mapping[str, Any], label: str) -> None:
    for field in FALSE_FIELDS:
        if field in record and record[field] is not False:
            raise DatasetCensusError(f"{label}_gate_drift:{field}")


def assert_public_sanitized(record: Mapping[str, Any], label: str) -> None:
    encoded = json.dumps(record, sort_keys=True, ensure_ascii=True)
    for needle in PUBLIC_FORBIDDEN_SUBSTRINGS:
        if needle in encoded:
            raise DatasetCensusError(f"{label}_public_leak:{needle}")


def load_pinned_inputs() -> dict[str, dict[str, Any]]:
    inputs = {
        "stage12621_summary": read_json(S12621_SUMMARY),
        "stage12376_summary": read_json(S12376_SUMMARY),
        "stage12419_summary": read_json(S12419_SUMMARY),
        "strict_long_context_card": read_json(STRICT_CARD),
        "strict_software_bundle_card": read_json(BUNDLE_CARD),
        "trainable_shards_manifest": read_json(TRAINABLE_SHARDS),
        "admission_manifest": read_json(ADMISSION_MANIFEST),
    }
    for label, value in inputs.items():
        actual = stable_hash(value)
        if actual != EXPECTED_HASHES[label]:
            raise DatasetCensusError("input_pin_drift:" + label)
    stage12621 = inputs["stage12621_summary"]
    if stage12621.get("decision") != "VM_BRANCH_PAUSED_DATASET_ADMISSION_SCALE_AND_QUALITY_CRITICAL_PATH":
        raise DatasetCensusError("stage12621_decision_drift")
    if stage12621.get("stage12622_dataset_admission_census_only_allowed") is not True:
        raise DatasetCensusError("stage12621_census_only_authorization_missing")
    if stage12621.get("training_allowed") is not False:
        raise DatasetCensusError("stage12621_training_gate_drift")
    if stage12621.get("vm_runner_execution_allowed") is not False:
        raise DatasetCensusError("stage12621_vm_execution_gate_drift")
    return inputs


def count_jsonl_splits(path: Path) -> dict[str, int]:
    counts: Counter[str] = Counter()
    for line in path.read_text(encoding="utf-8").splitlines():
        row = json.loads(line)
        counts[row.get("split") or row.get("package_split") or row.get("dataset_split") or ""] += 1
    return dict(sorted(counts.items()))


def build_census(inputs: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    ledger = inputs["stage12376_summary"]
    control = inputs["stage12419_summary"]
    strict_card = inputs["strict_long_context_card"]
    bundle_card = inputs["strict_software_bundle_card"]
    manifest = inputs["trainable_shards_manifest"]
    admission_manifest = inputs["admission_manifest"]
    strict_compile = strict_card.get("compile_summary", {})
    bundle_compile = bundle_card.get("long_context_summary", {}).get("compile_summary", {})
    selected = manifest.get("selected_shards", [])
    ready_count = sum(1 for row in selected if row.get("ready_for_training") is True)
    missing_count = sum(1 for row in selected if row.get("missing_required_outputs"))
    acceptance_counts = dict(sorted(Counter(row.get("acceptance_mode") for row in selected).items()))
    pack_token_total = sum(int(row.get("pack_token_count") or 0) for row in selected)
    target_audit_count_total = sum(int(row.get("target_audit_count") or 0) for row in selected)
    split_counts = count_jsonl_splits(SPLIT_ROWS)
    sampled_split_counts = count_jsonl_splits(SAMPLED_MANIFEST)
    expected = {
        "selected_shard_count": 14,
        "training_ready_shard_count": 14,
        "strict_builder_shard_count": 10,
        "audit_only_direct_shard_count": 4,
        "full_context_trainer_rows": 11,
        "retrieval_rows": 729,
        "authoritative_ledger_admitted_train_support_tasks": 158,
        "authoritative_ledger_remaining_gap_to_500": 342,
        "control_board_countable_supply_tasks": 190,
        "control_board_remaining_gap_to_500": 310,
        "control_board_stage12385_baseline_tasks": 172,
        "control_board_net_new_direct_real_log_rows": 18,
        "derived_sanitized_projection_rows": 292,
        "derived_countable_as_new_train_support_rows": 0,
        "stage12376_selected_test_rows_admitted_after_audit": 67,
        "stage12376_selected_test_rows_superseded_from_base": 3,
        "stage12376_selected_test_rows_quarantined_after_audit": 52,
        "dataset_admission_manifest_dataset_count": 52,
        "dataset_admission_manifest_catalog_patch_candidate_count": 30,
        "split_rows_total": 751,
    }
    if manifest.get("selected_shard_count") != expected["selected_shard_count"]:
        raise DatasetCensusError("selected_shard_count_drift")
    if manifest.get("training_ready_shard_count") != expected["training_ready_shard_count"]:
        raise DatasetCensusError("training_ready_shard_count_drift")
    if ready_count != expected["training_ready_shard_count"]:
        raise DatasetCensusError("ready_row_count_drift")
    if missing_count != 0:
        raise DatasetCensusError("missing_required_outputs_present")
    if acceptance_counts != {"audit_only_direct": 4, "strict_builder": 10}:
        raise DatasetCensusError("acceptance_mode_count_drift")
    if strict_compile.get("full_context_rows") != expected["full_context_trainer_rows"]:
        raise DatasetCensusError("strict_full_context_row_drift")
    if strict_compile.get("retrieval_rows") != expected["retrieval_rows"]:
        raise DatasetCensusError("strict_retrieval_row_drift")
    if bundle_compile.get("full_context_rows") != expected["full_context_trainer_rows"]:
        raise DatasetCensusError("bundle_full_context_row_drift")
    if ledger.get("current_admitted_train_support_tasks") != expected["authoritative_ledger_admitted_train_support_tasks"]:
        raise DatasetCensusError("ledger_admitted_count_drift")
    if ledger.get("remaining_gap_to_500") != expected["authoritative_ledger_remaining_gap_to_500"]:
        raise DatasetCensusError("ledger_remaining_gap_drift")
    if control.get("training_allowed") is not False or ledger.get("training_allowed") is not False:
        raise DatasetCensusError("authoritative_training_gate_drift")
    countable = control.get("countable_train_support", {})
    derived = control.get("derived_projection_lane", {})
    if countable.get("stage12417_current_admitted_train_support_tasks") != expected["control_board_countable_supply_tasks"]:
        raise DatasetCensusError("control_board_countable_supply_drift")
    if countable.get("remaining_gap_to_500") != expected["control_board_remaining_gap_to_500"]:
        raise DatasetCensusError("control_board_remaining_gap_drift")
    if countable.get("stage12385_baseline_tasks") != expected["control_board_stage12385_baseline_tasks"]:
        raise DatasetCensusError("control_board_baseline_drift")
    if countable.get("stage12416_net_new_direct_real_log_rows") != expected["control_board_net_new_direct_real_log_rows"]:
        raise DatasetCensusError("control_board_net_new_drift")
    if derived.get("stage12418_sanitized_projection_rows") != expected["derived_sanitized_projection_rows"]:
        raise DatasetCensusError("derived_projection_row_drift")
    if derived.get("stage12418_countable_as_new_train_support_rows") != expected["derived_countable_as_new_train_support_rows"]:
        raise DatasetCensusError("derived_countable_row_drift")
    if ledger.get("selected_test_rows_admitted_after_audit") != expected["stage12376_selected_test_rows_admitted_after_audit"]:
        raise DatasetCensusError("ledger_selected_test_admitted_drift")
    if ledger.get("selected_test_rows_superseded_from_base") != expected["stage12376_selected_test_rows_superseded_from_base"]:
        raise DatasetCensusError("ledger_superseded_drift")
    if ledger.get("selected_test_rows_quarantined_after_audit") != expected["stage12376_selected_test_rows_quarantined_after_audit"]:
        raise DatasetCensusError("ledger_quarantined_drift")
    if admission_manifest.get("dataset_count") != expected["dataset_admission_manifest_dataset_count"]:
        raise DatasetCensusError("admission_manifest_dataset_count_drift")
    if len(admission_manifest.get("catalog_patch_candidates", [])) != expected["dataset_admission_manifest_catalog_patch_candidate_count"]:
        raise DatasetCensusError("admission_manifest_catalog_candidate_drift")
    expected_routes = {
        "PAPER_SUPPORT_ONLY": 22,
        "STRICT_TRACE_EPISODE_IMPORT": 1,
        "TRACE_SUPPORT_ONLY": 1,
        "EVAL_ONLY": 3,
        "RETRIEVAL_AUX_ONLY": 3,
        "REJECT_GENERIC": 10,
        "REJECT_UNKNOWN": 12,
    }
    if admission_manifest.get("route_counts") != expected_routes:
        raise DatasetCensusError("admission_manifest_route_count_drift")
    if split_counts != EXPECTED_SPLIT_COUNTS or sampled_split_counts != EXPECTED_SPLIT_COUNTS:
        raise DatasetCensusError("split_count_drift")
    if sum(split_counts.values()) != expected["split_rows_total"] or sum(sampled_split_counts.values()) != expected["split_rows_total"]:
        raise DatasetCensusError("split_total_drift")
    return {
        "record_type": "stage12622_dataset_admission_census_v1",
        **expected,
        "manifest_ready_row_count": ready_count,
        "manifest_missing_required_outputs_count": missing_count,
        "manifest_acceptance_mode_counts": acceptance_counts,
        "manifest_pack_token_total": pack_token_total,
        "manifest_target_audit_count_total": target_audit_count_total,
        "strict_plus_audit_memory_rows": strict_compile.get("memory_rows"),
        "strict_plus_audit_trainer_rows": strict_compile.get("trainer_rows"),
        "split_rows_total": expected["split_rows_total"],
        "sampled_manifest_rows_total": expected["split_rows_total"],
        "split_counts": split_counts,
        "sampled_manifest_split_counts": sampled_split_counts,
        "strict_plus_audit_accepted_pack_count": strict_compile.get("train_ready_audit_summary", {}).get("accepted_pack_count"),
        "strict_plus_audit_included_shard_count": strict_compile.get("train_ready_audit_summary", {}).get("included_shard_count"),
        "control_board_remaining_gap_to_500": expected["control_board_remaining_gap_to_500"],
        "control_board_stage12385_baseline_tasks": expected["control_board_stage12385_baseline_tasks"],
        "control_board_net_new_direct_real_log_rows": expected["control_board_net_new_direct_real_log_rows"],
        "derived_sanitized_projection_rows": expected["derived_sanitized_projection_rows"],
        "derived_countable_as_new_train_support_rows": expected["derived_countable_as_new_train_support_rows"],
        "stage12376_selected_test_rows_admitted_after_audit": expected["stage12376_selected_test_rows_admitted_after_audit"],
        "stage12376_selected_test_rows_superseded_from_base": expected["stage12376_selected_test_rows_superseded_from_base"],
        "stage12376_selected_test_rows_quarantined_after_audit": expected["stage12376_selected_test_rows_quarantined_after_audit"],
        "dataset_admission_manifest_dataset_count": expected["dataset_admission_manifest_dataset_count"],
        "dataset_admission_manifest_route_counts": expected_routes,
        "dataset_admission_manifest_catalog_patch_candidate_count": expected["dataset_admission_manifest_catalog_patch_candidate_count"],
        "global_training_allowed_by_authoritative_ledgers": False,
        "dataset_admission_census_only": True,
        "new_admission_performed": False,
        "frontier_100m_training_dataset_ready": False,
        "vm_required_for_this_census": False,
    }


def build_census_packet(inputs: Mapping[str, Mapping[str, Any]]) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    census = build_census(inputs)
    private = {
        "record_type": "stage12622_private_dataset_admission_census_only_v1",
        **no_claim_fields(),
        "source_hashes": EXPECTED_HASHES,
        "dataset_admission_census_only": True,
        "vm_branch_remains_paused": True,
        "stage12623_dataset_gap_plan_only_allowed": True,
        "census": census,
        "decision": "DATASET_ADMISSION_CENSUS_RECORDED_SCALE_GAP_REMAINS_BLOCKING",
    }
    contract = {
        "record_type": "stage12622_public_dataset_admission_census_only_v1",
        **no_claim_fields(),
        "stage12621_summary_sha256": EXPECTED_HASHES["stage12621_summary"],
        "stage12376_summary_sha256": EXPECTED_HASHES["stage12376_summary"],
        "stage12419_summary_sha256": EXPECTED_HASHES["stage12419_summary"],
        "trainable_shards_manifest_sha256": EXPECTED_HASHES["trainable_shards_manifest"],
        "admission_manifest_sha256": EXPECTED_HASHES["admission_manifest"],
        "dataset_census_sha256": stable_hash(census),
        "private_dataset_admission_census_sha256": stable_hash(private),
        "dataset_admission_census_only": True,
        "vm_branch_remains_paused": True,
        "stage12623_dataset_gap_plan_only_allowed": True,
        "claim_boundary": {
            "census": "current_dataset_scale_and_quality_inventory_only",
            "new_admission": "not_authorized",
            "training": "not_authorized",
            "vm": "paused_not_used_for_census",
            "replay": "not_executed",
        },
    }
    summary = {
        "record_type": "stage12622_public_dataset_admission_census_only_summary_v1",
        **no_claim_fields(),
        "stage": STAGE,
        "decision": "DATASET_ADMISSION_CENSUS_RECORDED_SCALE_GAP_REMAINS_BLOCKING",
        "stage12621_summary_sha256": EXPECTED_HASHES["stage12621_summary"],
        "stage12376_summary_sha256": EXPECTED_HASHES["stage12376_summary"],
        "stage12419_summary_sha256": EXPECTED_HASHES["stage12419_summary"],
        "trainable_shards_manifest_sha256": EXPECTED_HASHES["trainable_shards_manifest"],
        "admission_manifest_sha256": EXPECTED_HASHES["admission_manifest"],
        "dataset_census_sha256": stable_hash(census),
        "private_dataset_admission_census_sha256": stable_hash(private),
        "dataset_admission_census_only": True,
        "vm_branch_remains_paused": True,
        "stage12623_dataset_gap_plan_only_allowed": True,
        "selected_shard_count": census["selected_shard_count"],
        "training_ready_shard_count": census["training_ready_shard_count"],
        "strict_builder_shard_count": census["strict_builder_shard_count"],
        "audit_only_direct_shard_count": census["audit_only_direct_shard_count"],
        "manifest_missing_required_outputs_count": census["manifest_missing_required_outputs_count"],
        "manifest_pack_token_total": census["manifest_pack_token_total"],
        "full_context_trainer_rows": census["full_context_trainer_rows"],
        "retrieval_rows": census["retrieval_rows"],
        "split_rows_total": census["split_rows_total"],
        "split_train_rows": census["split_counts"]["train"],
        "split_eval_rows": census["split_counts"]["eval"],
        "split_strict_eval_rows": census["split_counts"]["strict_eval"],
        "authoritative_ledger_admitted_train_support_tasks": census["authoritative_ledger_admitted_train_support_tasks"],
        "authoritative_ledger_remaining_gap_to_500": census["authoritative_ledger_remaining_gap_to_500"],
        "control_board_countable_supply_tasks": census["control_board_countable_supply_tasks"],
        "control_board_remaining_gap_to_500": census["control_board_remaining_gap_to_500"],
        "derived_sanitized_projection_rows": census["derived_sanitized_projection_rows"],
        "derived_countable_as_new_train_support_rows": census["derived_countable_as_new_train_support_rows"],
        "stage12376_selected_test_rows_admitted_after_audit": census["stage12376_selected_test_rows_admitted_after_audit"],
        "stage12376_selected_test_rows_quarantined_after_audit": census["stage12376_selected_test_rows_quarantined_after_audit"],
        "dataset_admission_manifest_dataset_count": census["dataset_admission_manifest_dataset_count"],
        "dataset_admission_manifest_catalog_patch_candidate_count": census["dataset_admission_manifest_catalog_patch_candidate_count"],
        "frontier_100m_training_dataset_ready": False,
        "downstream_blockers": [
            "admitted_train_support_scale_below_500_target",
            "current_full_context_trainer_rows_only_11",
            "dataset_gap_plan_not_materialized",
            "new_admission_review_not_performed",
            "frontier_training_admission_absent",
            "training_admission_forbidden",
        ],
    }
    for label, record in (("summary", summary), ("contract", contract)):
        check_false(record, "stage12622_" + label)
        assert_public_sanitized(record, "stage12622_" + label)
    check_false(private, "stage12622_private")
    return summary, contract, private


def build(out: Path = OUT, summary_path: Path = SUMMARY) -> dict[str, Any]:
    inputs = load_pinned_inputs()
    summary, contract, private = build_census_packet(inputs)
    pointer = {
        "record_type": "stage12622_public_private_dataset_admission_census_only_pointer_v1",
        **no_claim_fields(),
        "stage12621_summary_sha256": EXPECTED_HASHES["stage12621_summary"],
        "contract_sha256": stable_hash(contract),
        "private_dataset_admission_census_sha256": stable_hash(private),
        "dataset_admission_census_only": True,
        "vm_branch_remains_paused": True,
        "stage12623_dataset_gap_plan_only_allowed": True,
    }
    check_false(pointer, "stage12622_pointer")
    assert_public_sanitized(pointer, "stage12622_pointer")
    write_json(out / "contract.json", contract)
    write_json(out / "digest_pointer.json", pointer)
    write_json(out / "private/dataset_admission_census_only.json", private)
    write_json(out / "summary.json", summary)
    write_json(summary_path, summary)
    return summary


if __name__ == "__main__":
    print(json.dumps(build(), sort_keys=True))
