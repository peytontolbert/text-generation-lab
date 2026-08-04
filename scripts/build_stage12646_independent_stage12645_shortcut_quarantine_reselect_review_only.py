#!/usr/bin/env python3
# Independently review Stage12645 shortcut quarantine/reselect artifacts.
from __future__ import annotations

import collections
import hashlib
import json
import os
from pathlib import Path
from typing import Any, Iterable, Mapping

ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12646_independent_stage12645_shortcut_quarantine_reselect_review_only"
OUT = ROOT / "runs/local/artifacts" / STAGE
SUMMARY = ROOT / "runs/summaries" / f"{STAGE}.json"

S12645 = ROOT / "runs/local/artifacts/stage12645_stage8675_symbol_binding_shortcut_quarantine_reselect"
S12645_SUMMARY = ROOT / "runs/summaries/stage12645_stage8675_symbol_binding_shortcut_quarantine_reselect.json"
S12645_SCRIPT = ROOT / "scripts/build_stage12645_stage8675_symbol_binding_shortcut_quarantine_reselect.py"
S12645_TESTS = ROOT / "tests/test_stage12645_stage8675_symbol_binding_shortcut_quarantine_reselect.py"
S8674_MANIFEST = ROOT / "runs/local/artifacts/stage8674_source_backed_symbol_binding_candidate_manifest/source_backed_symbol_binding_candidate_manifest.jsonl"
S12644_SUMMARY = ROOT / "runs/summaries/stage12644_repo_code_ce_manifest_independent_review_only.json"

EXPECTED_HASHES = {
    "stage12645_summary": "5587e3ea6728e7cf56828bc3141cffa2a7eff752f13b456c585a8381ea9ad65e",
    "stage12645_contract": "f74aa7614fc454655b5cd50ad115e92136ee3bbbd14461f963819d19731e92e3",
    "stage12645_pointer": "2ef55a21446396c51208fd9792dd0362e1767450e4aa6136926afd8a20162752",
    "stage12645_private_packet": "1c9b8e0c93a41eee5296c0c71c34ec52a75c30a6bb5c027e3c29b470775c701c",
    "stage12645_repaired_rows_bytes": "2a2d0ff20ceffae0fb44ec90a09d98200a03f49d1f52703b2c0193d0acf548ae",
    "stage12645_quarantine_rows_bytes": "c90048df65d7174189340e7c79d6f9d2ac0d5cd0df86f5bd10f597d9a21d413e",
    "stage12645_script_bytes": "64de542c7aed06fabde4637834b757fd9133b1aaff896bb3a1a4da2aa2b7ac45",
    "stage12645_tests_bytes": "e28efcb8714fcd0e676039e43c318a80a3e0f12bcb748196021b3388ee04294e",
    "stage8674_manifest_bytes": "266b580c7638a8c5edf0c8fe39176fb061f992a85637a1f9318f5b65da15adca",
    "stage12644_summary": "88cbc2130fc5b3bb1b3afc1ab60bd5b47197fb7c74823148e5bddc0a20c019c0",
}
EXPECTED_ORIGINAL_SHORTCUT = {
    "feature": "query_kind",
    "value": "test",
    "majority": 0.8620689655172413,
    "total": 29,
    "dist": {"BIND_TEST_TO_SYMBOL": 25, "RETRIEVE_MORE": 4},
}
EXPECTED_STAGE12645_ARTIFACTS = [
    "contract.json",
    "digest_pointer.json",
    "private/quarantined_source_backed_symbol_binding_rows.jsonl",
    "private/repaired_source_backed_symbol_binding_candidate_manifest.jsonl",
    "private/stage8675_shortcut_quarantine_reselect_packet.json",
    "summary.json",
]
EXPECTED_ACTION_COUNTS = {
    "ABSTAIN_UNBOUND": 16,
    "BIND_CALL_TO_SYMBOL": 16,
    "BIND_IMPORT_TO_MODULE": 16,
    "BIND_TEST_TO_SYMBOL": 16,
    "RETRIEVE_MORE": 16,
}
EXPECTED_SPLIT_COUNTS = {"eval": 24, "strict_eval": 24, "train": 32}
LOSS_MASK = {
    "decoder_ce": False,
    "denoise_ce": False,
    "runtime_reward": False,
    "symbol_binding_ce": False,
    "source_backed_symbol_binding_candidate_ce": False,
}
FALSE_FIELDS = (
    "dataset_rows_admitted",
    "new_rows_admitted",
    "training_admission_allowed",
    "training_allowed",
    "training_run_allowed",
    "training_admitted",
    "strict_eval_admitted",
    "sealed_eval_admitted",
    "implementation_ready",
    "stage12595_allowed",
    "replay_trustworthy",
    "level_3_materialized",
    "gpu_allocation_requested",
    "cuda2_training_allowed",
    "vm_runner_execution_allowed",
    "runtime_authorized",
    "model_execution_authorized_next",
    "source_emission_authorized",
    "body_emission_authorized",
    "decoder_ce_training_authorized_next",
    "transition_head_training_authorized_next",
    "promotion_ready",
    "global_shortcut_preflight_passed",
    "stage8675_original_audit_passed",
    "stage8675_original_shortcut_issue_resolved",
    "repo_code_stage_complete",
)
PUBLIC_FORBIDDEN_SUBSTRINGS = (
    "/data/",
    "/arxiv/",
    "jsonl",
    "row_id",
    "source_row_id",
    "source_ref",
    "old_source_ref_path",
    "raw_stream",
    "stdout.raw",
    "stderr.raw",
    "repository_root",
    "patch_path",
    "production_path",
)


class Stage12646ReviewError(RuntimeError):
    pass


def stable_hash(value: Any) -> str:
    data = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("ascii")
    return hashlib.sha256(data).hexdigest()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise Stage12646ReviewError("json_object_required:" + path.name)
    return value


def read_jsonl_bytes(data: bytes) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line_number, line in enumerate(data.decode("utf-8").splitlines(), start=1):
        if not line:
            continue
        value = json.loads(line)
        if not isinstance(value, dict):
            raise Stage12646ReviewError(f"jsonl_object_required:{line_number}")
        rows.append(value)
    return rows


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    data = json.dumps(value, indent=2, sort_keys=True, ensure_ascii=True).encode("ascii") + b"\n"
    with path.open("wb") as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())


def fsync_dir(path: Path) -> None:
    fd = os.open(str(path), os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def no_claim_fields() -> dict[str, Any]:
    return {field: False for field in FALSE_FIELDS}


def check_false(record: Mapping[str, Any], label: str) -> None:
    for field in FALSE_FIELDS:
        if field in record and record[field] is not False:
            raise Stage12646ReviewError(f"{label}_gate_drift:{field}")


def assert_public_sanitized(record: Mapping[str, Any], label: str) -> None:
    encoded = json.dumps(record, sort_keys=True, ensure_ascii=True)
    for needle in PUBLIC_FORBIDDEN_SUBSTRINGS:
        if needle in encoded:
            raise Stage12646ReviewError(f"{label}_public_leak:{needle}")


def leaves(value: Any) -> Iterable[Any]:
    if isinstance(value, dict):
        for item in value.values():
            yield from leaves(item)
    elif isinstance(value, list):
        for item in value:
            yield from leaves(item)
    else:
        yield value


def stable_text(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def feature_value(row: Mapping[str, Any], feature: str) -> Any:
    graph = row.get("graph_input") or {}
    query = row.get("query") or {}
    if feature == "query_kind":
        return graph.get("query_kind")
    if feature == "source_file_is_test":
        return str((query.get("features") or {}).get("source_file_is_test"))
    for node in graph.get("nodes") or []:
        if node.get("node_type") == "file":
            return str((node.get("features") or {}).get(feature))
    return None


def recompute_control_audit(rows: list[dict[str, Any]]) -> dict[str, Any]:
    actions: collections.Counter[str] = collections.Counter()
    splits: collections.Counter[str] = collections.Counter()
    visible_target_hits = []
    forbidden = []
    missing = []
    shortcut = []
    for row in rows:
        clean = row.get("clean_state") or {}
        actions.update([str(clean.get("binding_action"))])
        splits.update([str(row.get("split"))])
        source_lineage = row.get("source_lineage") or {}
        retrieval_control = row.get("retrieval_control") or {}
        for key in ("graph_nodes_source_id", "graph_nodes_lineage_hash", "graph_spans_source_id", "graph_spans_lineage_hash"):
            if not source_lineage.get(key):
                missing.append({"row_hash": stable_hash(row), "missing": key})
        for key in ("bm25_top5_recall", "dense_top5_recall", "hybrid_rrf_top5_recall"):
            if key not in retrieval_control:
                missing.append({"row_hash": stable_hash(row), "missing": "retrieval_control." + key})
        if retrieval_control.get("bm25_top5_recall", 0) < 0.90:
            missing.append({"row_hash": stable_hash(row), "missing": "bm25_recall_floor"})
        visible = {key: row[key] for key in ("graph_input", "query", "source_lineage", "retrieval_control") if key in row}
        visible_text = stable_text(visible)
        for value in leaves(clean):
            if isinstance(value, str) and len(value) >= 4 and value in visible_text:
                visible_target_hits.append({"row_hash": stable_hash(row), "target_string_hash": hashlib.sha256(value.encode()).hexdigest()})
                break
        for key, value in (row.get("authority") or {}).items():
            if value is True:
                forbidden.append({"row_hash": stable_hash(row), "field": "authority." + key})
        for key in LOSS_MASK:
            if (row.get("loss_mask") or {}).get(key) is True:
                forbidden.append({"row_hash": stable_hash(row), "field": "loss_mask." + key})
    for feature in ("query_kind", "source_file_is_test", "import_count_bucket", "definition_count_bucket", "call_count_bucket", "path_depth_bucket", "is_test"):
        table: dict[Any, collections.Counter[str]] = collections.defaultdict(collections.Counter)
        for row in rows:
            action = (row.get("clean_state") or {}).get("binding_action")
            table[feature_value(row, feature)][action] += 1
        for value, counter in table.items():
            total = sum(counter.values())
            if total >= 10:
                majority = max(counter.values()) / total
                if majority > 0.80:
                    shortcut.append({"feature": feature, "value": value, "majority": majority, "total": total, "dist": dict(counter)})
    failures = []
    if not rows:
        failures.append("no_rows")
    if missing:
        failures.append(f"missing_required_controls:{len(missing)}")
    if visible_target_hits:
        failures.append(f"visible_target_hits:{len(visible_target_hits)}")
    if forbidden:
        failures.append(f"forbidden_authority_or_loss:{len(forbidden)}")
    if len(set(actions.values())) != 1:
        failures.append("actions_not_balanced")
    if shortcut:
        failures.append(f"shortcut_feature_cells:{len(shortcut)}")
    return {
        "rows": len(rows),
        "actions": dict(sorted(actions.items())),
        "splits": dict(sorted(splits.items())),
        "missing_required_controls": len(missing),
        "visible_target_hits": len(visible_target_hits),
        "forbidden_authority_or_loss": len(forbidden),
        "shortcut_feature_cells": len(shortcut),
        "failures": failures,
        "shortcut": shortcut,
    }


def load_stage12645() -> dict[str, Any]:
    emitted = sorted(path.relative_to(S12645).as_posix() for path in S12645.rglob("*") if path.is_file())
    if emitted != EXPECTED_STAGE12645_ARTIFACTS:
        raise Stage12646ReviewError("stage12645_artifact_manifest_drift")
    summary = read_json(S12645 / "summary.json")
    external = read_json(S12645_SUMMARY)
    contract = read_json(S12645 / "contract.json")
    pointer = read_json(S12645 / "digest_pointer.json")
    private = read_json(S12645 / "private/stage8675_shortcut_quarantine_reselect_packet.json")
    repaired_bytes = (S12645 / "private/repaired_source_backed_symbol_binding_candidate_manifest.jsonl").read_bytes()
    quarantine_bytes = (S12645 / "private/quarantined_source_backed_symbol_binding_rows.jsonl").read_bytes()
    original_bytes = S8674_MANIFEST.read_bytes()
    stage12644 = read_json(S12644_SUMMARY)
    if summary != external:
        raise Stage12646ReviewError("stage12645_external_summary_mismatch")
    for label, value in (
        ("stage12645_summary", summary),
        ("stage12645_contract", contract),
        ("stage12645_pointer", pointer),
        ("stage12645_private_packet", private),
        ("stage12644_summary", stage12644),
    ):
        if stable_hash(value) != EXPECTED_HASHES[label]:
            raise Stage12646ReviewError("pin_drift:" + label)
    for label, data in (
        ("stage12645_repaired_rows_bytes", repaired_bytes),
        ("stage12645_quarantine_rows_bytes", quarantine_bytes),
        ("stage12645_script_bytes", S12645_SCRIPT.read_bytes()),
        ("stage12645_tests_bytes", S12645_TESTS.read_bytes()),
        ("stage8674_manifest_bytes", original_bytes),
    ):
        if sha256_bytes(data) != EXPECTED_HASHES[label]:
            raise Stage12646ReviewError("pin_drift:" + label)
    repaired = read_jsonl_bytes(repaired_bytes)
    quarantine = read_jsonl_bytes(quarantine_bytes)
    original = read_jsonl_bytes(original_bytes)
    if pointer.get("contract_sha256") != stable_hash(contract):
        raise Stage12646ReviewError("stage12645_pointer_contract_hash_drift")
    if pointer.get("private_packet_sha256") != stable_hash(private):
        raise Stage12646ReviewError("stage12645_pointer_private_hash_drift")
    if pointer.get("repaired_manifest_sha256") != stable_hash(repaired):
        raise Stage12646ReviewError("stage12645_pointer_repaired_hash_drift")
    if pointer.get("quarantine_manifest_sha256") != stable_hash(quarantine):
        raise Stage12646ReviewError("stage12645_pointer_quarantine_hash_drift")
    for label, record in (("summary", summary), ("contract", contract), ("pointer", pointer)):
        assert_public_sanitized(record, "stage12645_" + label)
        check_false(record, "stage12645_" + label)
    check_false(private, "stage12645_private")
    return {"summary": summary, "contract": contract, "pointer": pointer, "private": private, "repaired": repaired, "quarantine": quarantine, "original": original}


def validate_stage12645(stage12645: Mapping[str, Any]) -> dict[str, Any]:
    summary = stage12645["summary"]
    contract = stage12645["contract"]
    private = stage12645["private"]
    repaired = stage12645["repaired"]
    quarantine = stage12645["quarantine"]
    original = stage12645["original"]
    if summary.get("decision") != "STAGE8675_SHORTCUT_QUARANTINED_BY_SUCCESSOR_RESELECT_NO_ADMISSION_OR_TRAINING":
        raise Stage12646ReviewError("stage12645_decision_drift")
    for field in ("training_allowed", "dataset_rows_admitted", "global_shortcut_preflight_passed", "stage8675_original_audit_passed", "stage8675_original_shortcut_issue_resolved"):
        if summary.get(field) is not False:
            raise Stage12646ReviewError("stage12645_forbidden_gate_drift:" + field)
    if summary.get("next_required_action") != STAGE:
        raise Stage12646ReviewError("stage12645_next_action_drift")
    if len(original) != 125 or len(repaired) != 80 or len(quarantine) != 45:
        raise Stage12646ReviewError("row_count_drift")
    original_hashes = {stable_hash(row) for row in original}
    repaired_hashes = {stable_hash(row) for row in repaired}
    quarantine_hashes = {str(record.get("row_sha256")) for record in quarantine}
    if len(original_hashes) != 125 or len(repaired_hashes) != 80 or len(quarantine_hashes) != 45:
        raise Stage12646ReviewError("row_hash_uniqueness_drift")
    if not repaired_hashes <= original_hashes:
        raise Stage12646ReviewError("repaired_rows_not_subset_of_stage8674")
    if not quarantine_hashes <= original_hashes:
        raise Stage12646ReviewError("quarantine_rows_not_subset_of_stage8674")
    if repaired_hashes & quarantine_hashes:
        raise Stage12646ReviewError("repaired_quarantine_overlap")
    if repaired_hashes | quarantine_hashes != original_hashes:
        raise Stage12646ReviewError("stage8674_partition_not_complete")
    original_audit = recompute_control_audit(original)
    repaired_audit = recompute_control_audit(repaired)
    if original_audit["shortcut_feature_cells"] != 1 or original_audit["failures"] != ["shortcut_feature_cells:1"]:
        raise Stage12646ReviewError("original_audit_recompute_drift")
    if not isinstance(original_audit.get("shortcut"), list) or len(original_audit["shortcut"]) != 1:
        raise Stage12646ReviewError("original_shortcut_detail_missing")
    if original_audit["shortcut"][0] != EXPECTED_ORIGINAL_SHORTCUT:
        raise Stage12646ReviewError("original_shortcut_detail_drift")
    if repaired_audit["shortcut_feature_cells"] != 0 or repaired_audit["failures"] != []:
        raise Stage12646ReviewError("repaired_audit_recompute_failed")
    if repaired_audit["actions"] != EXPECTED_ACTION_COUNTS:
        raise Stage12646ReviewError("repaired_action_count_drift")
    if repaired_audit["splits"] != EXPECTED_SPLIT_COUNTS:
        raise Stage12646ReviewError("repaired_split_count_drift")
    if private.get("repaired_audit") != repaired_audit:
        raise Stage12646ReviewError("private_repaired_audit_mismatch")
    if contract.get("repaired_action_counts") != repaired_audit["actions"] or contract.get("repaired_split_counts") != repaired_audit["splits"]:
        raise Stage12646ReviewError("contract_repaired_counts_mismatch")
    for record in quarantine:
        if record.get("training_allowed") is not False or record.get("dataset_rows_admitted") is not False:
            raise Stage12646ReviewError("quarantine_authority_drift")
        encoded = json.dumps(record, sort_keys=True)
        if "/arxiv/" in encoded or "/data/" in encoded or "source_row_id" in encoded:
            raise Stage12646ReviewError("quarantine_private_leak")
    return {
        "original_rows_reviewed": len(original),
        "repaired_rows_reviewed": len(repaired),
        "quarantined_rows_reviewed": len(quarantine),
        "repaired_action_counts": repaired_audit["actions"],
        "repaired_split_counts": repaired_audit["splits"],
        "original_shortcut_feature_cells": original_audit["shortcut_feature_cells"],
        "repaired_shortcut_feature_cells": repaired_audit["shortcut_feature_cells"],
        "partition_complete": True,
        "repaired_rows_are_stage8674_subset": True,
        "quarantine_rows_are_stage8674_subset": True,
        "repaired_and_quarantine_disjoint": True,
    }


def build_review(stage12645: Mapping[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    audit = validate_stage12645(stage12645)
    checks = [
        {"check_id": "stage12645_public_and_private_hashes_pinned", "status": "passed"},
        {"check_id": "stage12645_artifact_manifest_exact", "status": "passed", "artifact_count": len(EXPECTED_STAGE12645_ARTIFACTS)},
        {"check_id": "repaired_and_quarantined_rows_partition_stage8674", "status": "passed"},
        {"check_id": "repaired_rows_recompute_stage8675_shortcut_rule_zero_cells", "status": "passed"},
        {"check_id": "original_stage8675_failure_preserved_not_mutated", "status": "passed"},
        {"check_id": "quarantine_records_hash_only_no_authority", "status": "passed"},
        {"check_id": "public_artifacts_have_no_private_leaks", "status": "passed"},
        {"check_id": "training_eval_replay_level3_gpu_vm_forbidden", "status": "passed"},
    ]
    review = {
        "record_type": "stage12646_independent_stage12645_shortcut_quarantine_reselect_review_v1",
        "review_scope": "independent_stage12645_shortcut_quarantine_reselect_review_only",
        "reviewed_stage": "stage12645_stage8675_symbol_binding_shortcut_quarantine_reselect",
        "reviewed_hashes": EXPECTED_HASHES,
        "review_checks": checks,
        "review_check_count": len(checks),
        "review_status": "independent_review_passed_successor_shortcut_quarantine_reselect_no_admission",
        **audit,
        "candidate_rows_admitted_after_review": False,
        "training_allowed_after_review": False,
        "strict_eval_admitted_after_review": False,
        "sealed_eval_admitted_after_review": False,
        "level_3_materialized_after_review": False,
        "required_next_gate": "stage12647_repo_code_knowledge_completion_admission_preflight_only",
    }
    card = {
        "record_type": "stage12646_public_shortcut_quarantine_reselect_review_card_v1",
        "review_status": review["review_status"],
        "original_rows_reviewed": audit["original_rows_reviewed"],
        "repaired_rows_reviewed": audit["repaired_rows_reviewed"],
        "quarantined_rows_reviewed": audit["quarantined_rows_reviewed"],
        "repaired_action_counts": audit["repaired_action_counts"],
        "repaired_split_counts": audit["repaired_split_counts"],
        "original_shortcut_feature_cells": audit["original_shortcut_feature_cells"],
        "repaired_shortcut_feature_cells": audit["repaired_shortcut_feature_cells"],
        "partition_complete": True,
        "repaired_rows_are_stage8674_subset": audit["repaired_rows_are_stage8674_subset"],
        "quarantine_rows_are_stage8674_subset": audit["quarantine_rows_are_stage8674_subset"],
        "repaired_and_quarantine_disjoint": audit["repaired_and_quarantine_disjoint"],
        "candidate_rows_admitted_after_review": False,
        "training_allowed_after_review": False,
    }
    assert_public_sanitized(card, "stage12646_card")
    return review, card


def build_packet(stage12645: Mapping[str, Any]) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]]:
    review, card = build_review(stage12645)
    true_fields = {
        "stage12646_independent_shortcut_quarantine_review_only": True,
        "stage12646_independent_shortcut_quarantine_review_performed": True,
        "stage8675_successor_shortcut_issue_reviewed": True,
        "stage8675_successor_manifest_stage8675_rule_passed_after_review": True,
        "independent_review_passed": True,
    }
    private = {
        "record_type": "stage12646_private_independent_stage12645_shortcut_quarantine_review_only_v1",
        **no_claim_fields(),
        **true_fields,
        "review": review,
        "public_review_card_sha256": stable_hash(card),
        "decision": "STAGE12645_SHORTCUT_QUARANTINE_RESELECT_INDEPENDENT_REVIEW_PASSED_NO_ADMISSION_OR_TRAINING",
    }
    contract = {
        "record_type": "stage12646_public_independent_stage12645_shortcut_quarantine_review_contract_v1",
        **no_claim_fields(),
        **true_fields,
        "review_sha256": stable_hash(review),
        "public_review_card_sha256": stable_hash(card),
        "private_review_packet_sha256": stable_hash(private),
        "repaired_rows_reviewed": review["repaired_rows_reviewed"],
        "quarantined_rows_reviewed": review["quarantined_rows_reviewed"],
        "repaired_action_counts": review["repaired_action_counts"],
        "repaired_split_counts": review["repaired_split_counts"],
        "repaired_shortcut_feature_cells": review["repaired_shortcut_feature_cells"],
        "claim_boundary": {
            "successor_reselect": "independently_reviewed_passed_same_shortcut_rule",
            "original_stage8675": "historical_failure_preserved",
            "row_admission": "not_performed",
            "training": "not_authorized",
            "next": "repo_code_knowledge_completion_admission_preflight",
        },
    }
    summary = {
        "record_type": "stage12646_public_independent_stage12645_shortcut_quarantine_review_summary_v1",
        **no_claim_fields(),
        **true_fields,
        "stage": STAGE,
        "decision": "STAGE12645_SHORTCUT_QUARANTINE_RESELECT_INDEPENDENT_REVIEW_PASSED_NO_ADMISSION_OR_TRAINING",
        "review_sha256": stable_hash(review),
        "public_review_card_sha256": stable_hash(card),
        "private_review_packet_sha256": stable_hash(private),
        "original_rows_reviewed": review["original_rows_reviewed"],
        "repaired_rows_reviewed": review["repaired_rows_reviewed"],
        "quarantined_rows_reviewed": review["quarantined_rows_reviewed"],
        "repaired_action_counts": review["repaired_action_counts"],
        "repaired_split_counts": review["repaired_split_counts"],
        "original_shortcut_feature_cells": review["original_shortcut_feature_cells"],
        "repaired_shortcut_feature_cells": review["repaired_shortcut_feature_cells"],
        "partition_complete": True,
        "repaired_rows_are_stage8674_subset": review["repaired_rows_are_stage8674_subset"],
        "quarantine_rows_are_stage8674_subset": review["quarantine_rows_are_stage8674_subset"],
        "repaired_and_quarantine_disjoint": review["repaired_and_quarantine_disjoint"],
        "model_ready_training_rows": 0,
        "repo_code_ce_training_rows_admitted": 0,
        "symbol_binding_training_rows_admitted": 0,
        "next_required_action": "stage12647_repo_code_knowledge_completion_admission_preflight_only",
    }
    for label, record in (("summary", summary), ("contract", contract)):
        check_false(record, "stage12646_" + label)
        assert_public_sanitized(record, "stage12646_" + label)
    check_false(private, "stage12646_private")
    return summary, contract, private, card


def build(out: Path = OUT, summary_path: Path = SUMMARY) -> dict[str, Any]:
    summary, contract, private, card = build_packet(load_stage12645())
    pointer = {
        "record_type": "stage12646_public_independent_stage12645_shortcut_quarantine_review_pointer_v1",
        **no_claim_fields(),
        "stage12646_independent_shortcut_quarantine_review_only": True,
        "stage12646_independent_shortcut_quarantine_review_performed": True,
        "stage8675_successor_shortcut_issue_reviewed": True,
        "stage8675_successor_manifest_stage8675_rule_passed_after_review": True,
        "independent_review_passed": True,
        "contract_sha256": stable_hash(contract),
        "private_review_packet_sha256": stable_hash(private),
        "public_review_card_sha256": stable_hash(card),
        "review_sha256": stable_hash(private["review"]),
    }
    check_false(pointer, "stage12646_pointer")
    assert_public_sanitized(pointer, "stage12646_pointer")
    write_json(out / "contract.json", contract)
    write_json(out / "digest_pointer.json", pointer)
    write_json(out / "private/independent_stage12645_shortcut_quarantine_review_only.json", private)
    write_json(out / "public_review_card.json", card)
    write_json(out / "summary.json", summary)
    write_json(summary_path, summary)
    fsync_dir(out / "private")
    fsync_dir(out)
    fsync_dir(summary_path.parent)
    return summary


if __name__ == "__main__":
    print(json.dumps(build(), sort_keys=True))
