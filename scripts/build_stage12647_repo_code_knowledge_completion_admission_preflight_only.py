#!/usr/bin/env python3
# Complete/admit the reviewed repo/code knowledge curriculum layer without authorizing training.
from __future__ import annotations

import collections
import hashlib
import json
import os
from pathlib import Path
from typing import Any, Iterable, Mapping

ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12647_repo_code_knowledge_completion_admission_preflight_only"
OUT = ROOT / "runs/local/artifacts" / STAGE
SUMMARY = ROOT / "runs/summaries" / f"{STAGE}.json"

S12642_SUMMARY = ROOT / "runs/summaries/stage12642_repo_code_knowledge_completion_audit_only.json"
S12644 = ROOT / "runs/local/artifacts/stage12644_repo_code_ce_manifest_independent_review_only"
S12644_SUMMARY = ROOT / "runs/summaries/stage12644_repo_code_ce_manifest_independent_review_only.json"
S12643_ROWS = ROOT / "runs/local/artifacts/stage12643_repo_code_ce_manifest_preflight_only/private/repo_code_ce_candidate_manifest.jsonl"
S12646 = ROOT / "runs/local/artifacts/stage12646_independent_stage12645_shortcut_quarantine_reselect_review_only"
S12646_SUMMARY = ROOT / "runs/summaries/stage12646_independent_stage12645_shortcut_quarantine_reselect_review_only.json"
S12645_REPAIRED = ROOT / "runs/local/artifacts/stage12645_stage8675_symbol_binding_shortcut_quarantine_reselect/private/repaired_source_backed_symbol_binding_candidate_manifest.jsonl"
S12645_QUARANTINE = ROOT / "runs/local/artifacts/stage12645_stage8675_symbol_binding_shortcut_quarantine_reselect/private/quarantined_source_backed_symbol_binding_rows.jsonl"

EXPECTED_HASHES = {
    "stage12642_summary": "58148cedcb8cc7f0f1592110900beab27f6b5100b3a02c9125fe189eeac7d3c9",
    "stage12644_summary": "88cbc2130fc5b3bb1b3afc1ab60bd5b47197fb7c74823148e5bddc0a20c019c0",
    "stage12644_contract": "ad4411b60b1eb7b6d54a3f71a514ab8008fb1890204e9ac1f0bd7cfce2ecc87c",
    "stage12644_pointer": "2ac2db03766c5ad8711ec2c47eb54a85605857e9a9e895ba7109cf72a5438e8b",
    "stage12644_private": "4540da568588f40b79959f20c0402f74c0e972e4878bcc311d4acfaeab943459",
    "stage12643_rows_bytes": "c627f00695a725359ed88e9a1c1977cc8f25e416953ab902dbe82bdf751e7d42",
    "stage12646_summary": "98ba44132e3608f440530128b2aeb1fc1662ec8c799cbf932405ec4682c0dd2c",
    "stage12646_contract": "bb0e30295de0f619b3bd8c3a6461cb1ce0d16edf3f7a0a59d1c701350ae8557f",
    "stage12646_pointer": "6b23aa57cf53a34790e85eba8bbf859d2b88e76ecc7f25586e4e82f19170f319",
    "stage12646_private": "e7a3f38a8f0dda8f3b00b13894bfab1efb097eadc3c06440c7e7caba9387773c",
    "stage12645_repaired_rows_bytes": "2a2d0ff20ceffae0fb44ec90a09d98200a03f49d1f52703b2c0193d0acf548ae",
    "stage12645_quarantine_rows_bytes": "c90048df65d7174189340e7c79d6f9d2ac0d5cd0df86f5bd10f597d9a21d413e",
}
EXPECTED_STAGE12644_ARTIFACTS = [
    "contract.json",
    "digest_pointer.json",
    "private/repo_code_ce_manifest_independent_review_only.json",
    "public_review_card.json",
    "summary.json",
]
EXPECTED_STAGE12646_ARTIFACTS = [
    "contract.json",
    "digest_pointer.json",
    "private/independent_stage12645_shortcut_quarantine_review_only.json",
    "public_review_card.json",
    "summary.json",
]
CE_SPLITS = {"eval": 40, "strict_eval": 39, "train": 121}
SYMBOL_SPLITS = {"eval": 24, "strict_eval": 24, "train": 32}
ADMITTED_SPLITS = {"eval": 64, "strict_eval": 63, "train": 153}
SYMBOL_ACTIONS = {
    "ABSTAIN_UNBOUND": 16,
    "BIND_CALL_TO_SYMBOL": 16,
    "BIND_IMPORT_TO_MODULE": 16,
    "BIND_TEST_TO_SYMBOL": 16,
    "RETRIEVE_MORE": 16,
}
FORBIDDEN_TRUE_FIELDS = (
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
)
PUBLIC_FORBIDDEN_SUBSTRINGS = (
    "/data/",
    "/arxiv/",
    "jsonl",
    "row_id",
    "source_row_id",
    "source_ref",
    "raw_stream",
    "stdout.raw",
    "stderr.raw",
    "repository_root",
    "patch_path",
    "production_path",
)
ROW_FORBIDDEN_SUBSTRINGS = ("/data/", "/arxiv/", "\x00", "Answer:", "PLACEHOLDER", "placeholder", "TODO", "TBD", "<fill")


class Stage12647AdmissionError(RuntimeError):
    pass


def stable_hash(value: Any) -> str:
    data = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("ascii")
    return hashlib.sha256(data).hexdigest()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise Stage12647AdmissionError("json_object_required:" + path.name)
    return value


def read_jsonl_bytes(data: bytes) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line_number, line in enumerate(data.decode("utf-8").splitlines(), start=1):
        if not line:
            continue
        value = json.loads(line)
        if not isinstance(value, dict):
            raise Stage12647AdmissionError(f"jsonl_object_required:{line_number}")
        rows.append(value)
    return rows


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    data = json.dumps(value, indent=2, sort_keys=True, ensure_ascii=True).encode("ascii") + b"\n"
    with path.open("wb") as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())


def write_jsonl(path: Path, rows: Iterable[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("wb") as stream:
        for row in rows:
            stream.write(json.dumps(row, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("ascii") + b"\n")
        stream.flush()
        os.fsync(stream.fileno())


def fsync_dir(path: Path) -> None:
    fd = os.open(str(path), os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def false_training_fields() -> dict[str, Any]:
    return {field: False for field in FORBIDDEN_TRUE_FIELDS}


def check_no_training(record: Mapping[str, Any], label: str) -> None:
    for field in FORBIDDEN_TRUE_FIELDS:
        if record.get(field) is not False:
            raise Stage12647AdmissionError(f"{label}_training_gate_drift:{field}")


def assert_public_sanitized(record: Mapping[str, Any], label: str) -> None:
    encoded = json.dumps(record, sort_keys=True, ensure_ascii=True)
    for needle in PUBLIC_FORBIDDEN_SUBSTRINGS:
        if needle in encoded:
            raise Stage12647AdmissionError(f"{label}_public_leak:{needle}")


def assert_row_sanitized(row: Mapping[str, Any], label: str) -> None:
    encoded = json.dumps(row, sort_keys=True, ensure_ascii=True)
    for needle in ROW_FORBIDDEN_SUBSTRINGS:
        if needle in encoded:
            raise Stage12647AdmissionError(f"{label}_row_leak_or_placeholder:{needle}")


def split_counts(rows: Iterable[Mapping[str, Any]]) -> dict[str, int]:
    counts: collections.Counter[str] = collections.Counter(str(row.get("split")) for row in rows)
    return dict(sorted(counts.items()))


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


def recompute_stage8675_shortcuts(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    shortcut = []
    for feature in ("query_kind", "source_file_is_test", "import_count_bucket", "definition_count_bucket", "call_count_bucket", "path_depth_bucket", "is_test"):
        table: dict[Any, collections.Counter[str]] = collections.defaultdict(collections.Counter)
        for row in rows:
            action = (row.get("clean_state") or {}).get("binding_action")
            table[feature_value(row, feature)][str(action)] += 1
        for value, counter in table.items():
            total = sum(counter.values())
            if total >= 10:
                majority = max(counter.values()) / total
                if majority > 0.80:
                    shortcut.append({"feature": feature, "value": value, "majority": majority, "total": total, "dist": dict(counter)})
    return shortcut


def load_inputs() -> dict[str, Any]:
    stage12642 = read_json(S12642_SUMMARY)
    if stable_hash(stage12642) != EXPECTED_HASHES["stage12642_summary"]:
        raise Stage12647AdmissionError("pin_drift:stage12642_summary")
    if stage12642.get("repo_code_knowledge_substrate_recovered") is not True:
        raise Stage12647AdmissionError("stage12642_substrate_not_recovered")
    if stage12642.get("repo_code_knowledge_stage_complete") is not False:
        raise Stage12647AdmissionError("stage12642_completion_already_claimed")

    if sorted(path.relative_to(S12644).as_posix() for path in S12644.rglob("*") if path.is_file()) != EXPECTED_STAGE12644_ARTIFACTS:
        raise Stage12647AdmissionError("stage12644_artifact_manifest_drift")
    stage12644_summary = read_json(S12644 / "summary.json")
    if stage12644_summary != read_json(S12644_SUMMARY):
        raise Stage12647AdmissionError("stage12644_summary_external_mismatch")
    for label, path in (
        ("stage12644_summary", S12644 / "summary.json"),
        ("stage12644_contract", S12644 / "contract.json"),
        ("stage12644_pointer", S12644 / "digest_pointer.json"),
        ("stage12644_private", S12644 / "private/repo_code_ce_manifest_independent_review_only.json"),
    ):
        if stable_hash(read_json(path)) != EXPECTED_HASHES[label]:
            raise Stage12647AdmissionError("pin_drift:" + label)
    if stage12644_summary.get("independent_review_passed") is not True or stage12644_summary.get("candidate_rows_independently_reviewed") != 200:
        raise Stage12647AdmissionError("stage12644_review_not_passed")
    if stage12644_summary.get("stage8675_shortcut_issue_quarantined_after_review") is not False:
        raise Stage12647AdmissionError("stage12644_unexpected_shortcut_state")
    ce_bytes = S12643_ROWS.read_bytes()
    if sha256_bytes(ce_bytes) != EXPECTED_HASHES["stage12643_rows_bytes"]:
        raise Stage12647AdmissionError("pin_drift:stage12643_rows_bytes")
    ce_rows = read_jsonl_bytes(ce_bytes)

    if sorted(path.relative_to(S12646).as_posix() for path in S12646.rglob("*") if path.is_file()) != EXPECTED_STAGE12646_ARTIFACTS:
        raise Stage12647AdmissionError("stage12646_artifact_manifest_drift")
    stage12646_summary = read_json(S12646 / "summary.json")
    if stage12646_summary != read_json(S12646_SUMMARY):
        raise Stage12647AdmissionError("stage12646_summary_external_mismatch")
    for label, path in (
        ("stage12646_summary", S12646 / "summary.json"),
        ("stage12646_contract", S12646 / "contract.json"),
        ("stage12646_pointer", S12646 / "digest_pointer.json"),
        ("stage12646_private", S12646 / "private/independent_stage12645_shortcut_quarantine_review_only.json"),
    ):
        if stable_hash(read_json(path)) != EXPECTED_HASHES[label]:
            raise Stage12647AdmissionError("pin_drift:" + label)
    if stage12646_summary.get("independent_review_passed") is not True or stage12646_summary.get("repaired_shortcut_feature_cells") != 0:
        raise Stage12647AdmissionError("stage12646_review_not_passed")
    repaired_bytes = S12645_REPAIRED.read_bytes()
    quarantine_bytes = S12645_QUARANTINE.read_bytes()
    if sha256_bytes(repaired_bytes) != EXPECTED_HASHES["stage12645_repaired_rows_bytes"]:
        raise Stage12647AdmissionError("pin_drift:stage12645_repaired_rows_bytes")
    if sha256_bytes(quarantine_bytes) != EXPECTED_HASHES["stage12645_quarantine_rows_bytes"]:
        raise Stage12647AdmissionError("pin_drift:stage12645_quarantine_rows_bytes")
    repaired_rows = read_jsonl_bytes(repaired_bytes)
    quarantine_rows = read_jsonl_bytes(quarantine_bytes)
    for label, record in (("stage12644_summary", stage12644_summary), ("stage12646_summary", stage12646_summary)):
        check_no_training(record, label)
        assert_public_sanitized(record, label)
    return {
        "stage12642": stage12642,
        "stage12644_summary": stage12644_summary,
        "stage12646_summary": stage12646_summary,
        "ce_rows": ce_rows,
        "repaired_rows": repaired_rows,
        "quarantine_rows": quarantine_rows,
    }


def audit_inputs(inputs: Mapping[str, Any]) -> dict[str, Any]:
    stage12644_summary = inputs["stage12644_summary"]
    stage12646_summary = inputs["stage12646_summary"]
    if stage12644_summary.get("candidate_rows_independently_reviewed") != 200:
        raise Stage12647AdmissionError("stage12644_reviewed_count_drift")
    if stage12644_summary.get("placeholder_rows_after_review") != 0 or stage12644_summary.get("raw_path_rows_after_review") != 0:
        raise Stage12647AdmissionError("stage12644_cleanliness_drift")
    if stage12644_summary.get("cross_split_duplicate_opaque_repo_ids_after_review") != 0:
        raise Stage12647AdmissionError("stage12644_heldout_overlap_drift")
    if stage12646_summary.get("repaired_rows_reviewed") != 80 or stage12646_summary.get("quarantined_rows_reviewed") != 45:
        raise Stage12647AdmissionError("stage12646_reviewed_count_drift")
    if stage12646_summary.get("repaired_shortcut_feature_cells") != 0 or stage12646_summary.get("partition_complete") is not True:
        raise Stage12647AdmissionError("stage12646_shortcut_or_partition_drift")
    if stage12646_summary.get("repaired_rows_are_stage8674_subset") is not True or stage12646_summary.get("quarantine_rows_are_stage8674_subset") is not True:
        raise Stage12647AdmissionError("stage12646_subset_drift")
    if stage12646_summary.get("repaired_and_quarantine_disjoint") is not True:
        raise Stage12647AdmissionError("stage12646_disjoint_drift")
    ce_rows = list(inputs["ce_rows"])
    repaired_rows = list(inputs["repaired_rows"])
    quarantine_rows = list(inputs["quarantine_rows"])
    if len(ce_rows) != 200 or split_counts(ce_rows) != CE_SPLITS:
        raise Stage12647AdmissionError("ce_row_count_or_split_drift")
    if len(repaired_rows) != 80 or split_counts(repaired_rows) != SYMBOL_SPLITS:
        raise Stage12647AdmissionError("symbol_row_count_or_split_drift")
    if len(quarantine_rows) != 45:
        raise Stage12647AdmissionError("quarantine_row_count_drift")
    ce_repo_splits: dict[str, set[str]] = {}
    for row in ce_rows:
        assert_row_sanitized(row, "ce")
        admission = row.get("admission") or {}
        if admission.get("local_manifest_shortcut_screen_passed") is not True or admission.get("global_shortcut_preflight_passed") is not False:
            raise Stage12647AdmissionError("ce_shortcut_gate_drift")
        if admission.get("admitted") is not False or admission.get("training_allowed") is not False:
            raise Stage12647AdmissionError("ce_preexisting_admission_drift")
        if any(value is True for value in (row.get("authority") or {}).values()) or any(value is True for value in (row.get("loss_mask") or {}).values()):
            raise Stage12647AdmissionError("ce_authority_or_loss_drift")
        opaque = str((row.get("input") or {}).get("opaque_repo_id") or "")
        ce_repo_splits.setdefault(opaque, set()).add(str(row.get("split")))
    if sum(1 for splits in ce_repo_splits.values() if len(splits) > 1) != 0 or len(ce_repo_splits) != 200:
        raise Stage12647AdmissionError("ce_heldout_overlap")

    actions = collections.Counter()
    repaired_hashes = set()
    for row in repaired_rows:
        # Stage12645 repaired rows are private source-backed rows and may retain private lineage paths.
        # Stage12647 admits only hash-only ledger records for them, so public/private boundary is checked on outputs.
        repaired_hashes.add(stable_hash(row))
        actions.update([str((row.get("clean_state") or {}).get("binding_action"))])
        if any(value is True for value in (row.get("authority") or {}).values()) or any(value is True for value in (row.get("loss_mask") or {}).values()):
            raise Stage12647AdmissionError("symbol_authority_or_loss_drift")
    if dict(sorted(actions.items())) != SYMBOL_ACTIONS:
        raise Stage12647AdmissionError("symbol_action_balance_drift")
    if recompute_stage8675_shortcuts(repaired_rows):
        raise Stage12647AdmissionError("symbol_shortcut_regression")
    quarantine_hashes = {str(row.get("row_sha256")) for row in quarantine_rows}
    if repaired_hashes & quarantine_hashes:
        raise Stage12647AdmissionError("quarantined_rows_admitted")
    return {
        "repo_code_ce_rows_reviewed_for_admission": len(ce_rows),
        "symbol_binding_rows_reviewed_for_admission": len(repaired_rows),
        "quarantined_rows_excluded": len(quarantine_rows),
        "repo_code_ce_split_counts": split_counts(ce_rows),
        "symbol_binding_split_counts": split_counts(repaired_rows),
        "admitted_split_counts": ADMITTED_SPLITS,
        "symbol_action_counts": dict(sorted(actions.items())),
        "ce_cross_split_duplicate_opaque_repo_ids": 0,
        "symbol_shortcut_feature_cells_after_recompute": 0,
    }


def admitted_records(inputs: Mapping[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for index, row in enumerate(inputs["ce_rows"], start=1):
        rows.append({
            "record_type": "stage12647_private_admitted_repo_code_knowledge_row_v1",
            "admitted_row_id": f"stage12647_repo_code_ce_admitted_{index:04d}",
            "admission_family": "repo_code_ce",
            "source_stage": "stage12643_reviewed_by_stage12644",
            "source_row_sha256": stable_hash(row),
            "split": row["split"],
            "objective_family": row["objective_family"],
            "input_state_sha256": stable_hash(row.get("input") or {}),
            "target_state_sha256": stable_hash(row.get("target") or {}),
            "source_lineage_sha256": stable_hash(row.get("source_lineage") or {}),
            "repo_code_knowledge_admitted": True,
            "training_allowed": False,
        })
    for index, row in enumerate(inputs["repaired_rows"], start=1):
        rows.append({
            "record_type": "stage12647_private_admitted_repo_code_knowledge_row_v1",
            "admitted_row_id": f"stage12647_symbol_binding_admitted_{index:04d}",
            "admission_family": "source_backed_symbol_binding",
            "source_stage": "stage12645_reviewed_by_stage12646",
            "source_row_sha256": stable_hash(row),
            "split": row["split"],
            "objective_family": row["objective_family"],
            "binding_action": (row.get("clean_state") or {}).get("binding_action"),
            "graph_input_sha256": stable_hash(row.get("graph_input") or {}),
            "query_sha256": stable_hash(row.get("query") or {}),
            "source_lineage_sha256": stable_hash(row.get("source_lineage") or {}),
            "repo_code_knowledge_admitted": True,
            "training_allowed": False,
        })
    if len(rows) != 280 or split_counts(rows) != ADMITTED_SPLITS:
        raise Stage12647AdmissionError("admitted_manifest_count_or_split_drift")
    if len({row["source_row_sha256"] for row in rows}) != 280:
        raise Stage12647AdmissionError("admitted_source_hash_collision")
    return rows


def build_packet(inputs: Mapping[str, Any]) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any], list[dict[str, Any]]]:
    audit = audit_inputs(inputs)
    admitted = admitted_records(inputs)
    admitted_hash = stable_hash(admitted)
    completion_checks = [
        {"check_id": "stage12642_prior_blockers_reconciled", "status": "passed"},
        {"check_id": "stage12644_repo_code_ce_manifest_review_passed", "status": "passed"},
        {"check_id": "stage12646_stage8675_successor_review_passed", "status": "passed"},
        {"check_id": "repo_code_ce_rows_schema_heldout_shortcut_clean", "status": "passed"},
        {"check_id": "source_backed_symbol_rows_reselected_shortcut_clean", "status": "passed"},
        {"check_id": "quarantined_stage8674_rows_excluded", "status": "passed"},
        {"check_id": "private_admitted_manifest_materialized_hash_only", "status": "passed"},
        {"check_id": "training_eval_level3_gpu_vm_remain_forbidden", "status": "passed"},
    ]
    true_fields = {
        "stage12647_completion_admission_preflight_passed": True,
        "repo_code_knowledge_stage_complete": True,
        "repo_code_rows_admitted": True,
        "dataset_rows_admitted": True,
        "new_rows_admitted": True,
    }
    private = {
        "record_type": "stage12647_private_repo_code_knowledge_completion_admission_packet_v1",
        **false_training_fields(),
        **true_fields,
        "reviewed_input_hashes": EXPECTED_HASHES,
        "completion_checks": completion_checks,
        "input_audit": audit,
        "admitted_manifest_sha256": admitted_hash,
        "admitted_rows": len(admitted),
        "claim_boundary": {
            "repo_code_knowledge": "complete_and_dataset_rows_admitted",
            "training": "not_authorized_separate_admission_required",
            "strict_eval": "not_admitted",
            "sealed_eval": "not_admitted",
            "level_3": "not_materialized",
        },
    }
    contract = {
        "record_type": "stage12647_public_repo_code_knowledge_completion_admission_contract_v1",
        **false_training_fields(),
        **true_fields,
        "completion_check_count": len(completion_checks),
        "repo_code_ce_rows_admitted": audit["repo_code_ce_rows_reviewed_for_admission"],
        "symbol_binding_rows_admitted": audit["symbol_binding_rows_reviewed_for_admission"],
        "repo_code_knowledge_rows_admitted": len(admitted),
        "quarantined_rows_excluded": audit["quarantined_rows_excluded"],
        "admitted_split_counts": audit["admitted_split_counts"],
        "symbol_action_counts": audit["symbol_action_counts"],
        "stage12647_private_packet_sha256": stable_hash(private),
        "stage12647_admitted_manifest_sha256": admitted_hash,
        "model_ready_training_rows": 0,
        "separate_training_admission_required": True,
    }
    summary = {
        "record_type": "stage12647_public_repo_code_knowledge_completion_admission_summary_v1",
        **false_training_fields(),
        **true_fields,
        "stage": STAGE,
        "decision": "REPO_CODE_KNOWLEDGE_COMPLETION_ADMISSION_PREFLIGHT_PASSED_NO_TRAINING",
        "repo_code_knowledge_rows_admitted": len(admitted),
        "repo_code_ce_rows_admitted": audit["repo_code_ce_rows_reviewed_for_admission"],
        "symbol_binding_rows_admitted": audit["symbol_binding_rows_reviewed_for_admission"],
        "quarantined_rows_excluded": audit["quarantined_rows_excluded"],
        "admitted_split_counts": audit["admitted_split_counts"],
        "repo_code_ce_split_counts": audit["repo_code_ce_split_counts"],
        "symbol_binding_split_counts": audit["symbol_binding_split_counts"],
        "symbol_action_counts": audit["symbol_action_counts"],
        "ce_cross_split_duplicate_opaque_repo_ids": audit["ce_cross_split_duplicate_opaque_repo_ids"],
        "symbol_shortcut_feature_cells_after_recompute": audit["symbol_shortcut_feature_cells_after_recompute"],
        "reviewed_repo_code_ce_manifest": True,
        "reviewed_stage8675_successor_shortcut_quarantine": True,
        "original_stage8675_history_mutated": False,
        "stage8675_original_audit_passed": False,
        "stage8675_successor_manifest_stage8675_rule_passed": True,
        "model_ready_training_rows": 0,
        "separate_training_admission_required": True,
        "stage12647_private_packet_sha256": stable_hash(private),
        "stage12647_contract_sha256": stable_hash(contract),
        "stage12647_admitted_manifest_sha256": admitted_hash,
        "next_required_action": "separate_training_admission_preflight_only",
    }
    pointer = {
        "record_type": "stage12647_public_repo_code_knowledge_completion_admission_pointer_v1",
        **false_training_fields(),
        **true_fields,
        "contract_sha256": stable_hash(contract),
        "private_packet_sha256": stable_hash(private),
        "admitted_manifest_sha256": admitted_hash,
    }
    for label, record in (("summary", summary), ("contract", contract), ("pointer", pointer)):
        check_no_training(record, label)
        assert_public_sanitized(record, label)
    check_no_training(private, "private")
    return summary, contract, private, pointer, admitted


def build(out: Path = OUT, summary_path: Path = SUMMARY) -> dict[str, Any]:
    summary, contract, private, pointer, admitted = build_packet(load_inputs())
    write_json(out / "contract.json", contract)
    write_json(out / "digest_pointer.json", pointer)
    write_json(out / "private/repo_code_knowledge_completion_admission_packet.json", private)
    write_jsonl(out / "private/admitted_repo_code_knowledge_rows.jsonl", admitted)
    write_json(out / "summary.json", summary)
    write_json(summary_path, summary)
    fsync_dir(out / "private")
    fsync_dir(out)
    fsync_dir(summary_path.parent)
    return summary


if __name__ == "__main__":
    print(json.dumps(build(), sort_keys=True))
