#!/usr/bin/env python3
"""Independently review Stage12681 precise links without admitting training."""
from __future__ import annotations

import collections
import hashlib
import json
import os
from pathlib import Path
from typing import Any, Iterable, Mapping

ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12682_precise_link_independent_review_only"
OUT = ROOT / "runs/local/artifacts" / STAGE
SUMMARY = ROOT / "runs/summaries" / f"{STAGE}.json"

S12681_SUMMARY = ROOT / "runs/summaries/stage12681_precise_symbol_doc_test_link_materialization_preflight_only.json"
S12681_AUDIT = ROOT / "runs/local/artifacts/stage12681_precise_symbol_doc_test_link_materialization_preflight_only/precise_symbol_doc_test_link_materialization_audit.json"
S12681_CONTRACT = ROOT / "runs/local/artifacts/stage12681_precise_symbol_doc_test_link_materialization_preflight_only/contract.json"
S12681_ROWS = ROOT / "runs/local/artifacts/stage12681_precise_symbol_doc_test_link_materialization_preflight_only/private/precise_symbol_doc_test_link_rows.jsonl"

EXPECTED_HASHES = {
    "stage12681_summary": "d76446ff872b3348e13479835ce0dbf4b64e370348ceb2f5040e8edada75fb14",
    "stage12681_audit": "c18c891adf4a3ce46d780a55400a381fef90224f08b48f83bbd253f050b3ec3e",
    "stage12681_contract": "242c27ff9793b769f6507b8c73c2b4eb3e8390fea21ca49253ac6e954cef7e05",
    "stage12681_rows": "72f98d82de6b4b43280e854ac3fe74430918ccf0c41cf5c44c4e77ebe5029ca7",
}
EXPECTED_OBJECTIVE_COUNTS = {
    "precise_build_symbol_reference_link": 2410,
    "precise_doc_symbol_reference_link": 5898,
    "precise_symbol_definition_file_link": 45308,
    "precise_test_symbol_reference_link": 18841,
}
EXPECTED_SPLIT_COUNTS = {"eval": 16110, "strict_eval": 15085, "train": 41262}
SUPPORTED_DEFINITION_TYPE = "symbol_to_defining_source_file"
SUPPORTED_REFERENCE_TYPES = {
    "precise_build_symbol_reference_link": "build_config_literal_symbol_reference_to_code_file",
    "precise_doc_symbol_reference_link": "doc_literal_symbol_reference_to_code_file",
    "precise_test_symbol_reference_link": "test_literal_symbol_reference_to_code_file",
}
FALSE_FIELDS = (
    "implementation_ready", "stage12683_allowed", "training_allowed", "training_run_allowed",
    "training_admitted", "gpu_allocation_requested", "cuda2_training_allowed", "vm_runner_execution_allowed",
    "runtime_authorized", "replay_trustworthy", "level_3_materialized", "model_execution_authorized_next",
    "optimizer_step_authorized", "source_emission_authorized", "body_emission_authorized",
    "sealed_eval_admitted", "sealed_eval_eligible", "strict_eval_admitted", "strict_eval_eligible",
    "strict_eval_authorized", "sealed_eval_authorized", "loss_authorized", "compiler_execution_authorized",
)
UPSTREAM_FALSE_FIELDS = tuple(field for field in FALSE_FIELDS if field != "stage12683_allowed") + ("stage12682_allowed",)
FORBIDDEN_SUBSTRINGS = ("/data/", "/arxiv/", "PLACEHOLDER", "placeholder", "TODO", "TBD", "Answer:", "<fill", "\x00")


class Stage12682ReviewError(RuntimeError):
    pass


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def stable_hash(value: Any) -> str:
    data = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("ascii")
    return hashlib.sha256(data).hexdigest()


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise Stage12682ReviewError("json_object_required:" + path.name)
    return value


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            value = json.loads(line)
            if not isinstance(value, dict):
                raise Stage12682ReviewError(f"jsonl_object_required:{line_number}")
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


def false_fields() -> dict[str, bool]:
    return {field: False for field in FALSE_FIELDS}


def check_false(record: Mapping[str, Any], label: str, fields: tuple[str, ...]) -> None:
    for field in fields:
        if record.get(field) is not False:
            raise Stage12682ReviewError(f"{label}_gate_drift:{field}")


def assert_no_forbidden(value: Any, label: str) -> None:
    encoded = json.dumps(value, sort_keys=True, ensure_ascii=True) if not isinstance(value, str) else value
    for needle in FORBIDDEN_SUBSTRINGS:
        if needle in encoded:
            raise Stage12682ReviewError(f"{label}_forbidden_substring:{needle}")


def load_inputs() -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], list[dict[str, Any]]]:
    paths = {
        "stage12681_summary": S12681_SUMMARY,
        "stage12681_audit": S12681_AUDIT,
        "stage12681_contract": S12681_CONTRACT,
        "stage12681_rows": S12681_ROWS,
    }
    for label, path in paths.items():
        if sha256_bytes(path.read_bytes()) != EXPECTED_HASHES[label]:
            raise Stage12682ReviewError("pin_drift:" + label)
    summary, audit, contract = read_json(S12681_SUMMARY), read_json(S12681_AUDIT), read_json(S12681_CONTRACT)
    for label, record in (("summary", summary), ("audit", audit), ("contract", contract)):
        check_false(record, "stage12681_" + label, UPSTREAM_FALSE_FIELDS)
    if summary.get("recommended_next_stage") != STAGE or audit.get("next_required_action") != STAGE:
        raise Stage12682ReviewError("stage12681_next_action_drift")
    rows = read_jsonl(S12681_ROWS)
    if len(rows) != 72457:
        raise Stage12682ReviewError("row_count_drift")
    return summary, audit, contract, rows


def _add_endpoint(mapping: dict[str, set[str]], value: Any, split: str) -> None:
    if isinstance(value, str) and value:
        mapping[value].add(split)


def review_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    objective_counts = dict(sorted(collections.Counter(str(row.get("objective_family")) for row in rows).items()))
    split_counts = dict(sorted(collections.Counter(str(row.get("split")) for row in rows).items()))
    if objective_counts != EXPECTED_OBJECTIVE_COUNTS:
        raise Stage12682ReviewError("objective_count_drift")
    if split_counts != EXPECTED_SPLIT_COUNTS:
        raise Stage12682ReviewError("split_count_drift")

    row_ids: set[str] = set()
    semantic_hashes: collections.Counter[str] = collections.Counter()
    target_hashes: collections.Counter[str] = collections.Counter()
    target_splits: dict[str, set[str]] = collections.defaultdict(set)
    input_targets: dict[str, set[str]] = collections.defaultdict(set)
    input_row_counts: collections.Counter[str] = collections.Counter()
    repo_splits: dict[str, set[str]] = collections.defaultdict(set)
    endpoint_splits: dict[str, set[str]] = collections.defaultdict(set)
    file_id_digests: dict[str, set[str]] = collections.defaultdict(set)
    definition_files: dict[tuple[str, str], set[tuple[str, str]]] = collections.defaultdict(set)
    definition_rows: collections.Counter[tuple[str, str]] = collections.Counter()
    reference_rows: collections.Counter[tuple[str, str]] = collections.Counter()
    duplicate_row_ids = schema_error_rows = authority_open_rows = 0
    raw_source_body_rows = absolute_path_rows = forbidden_marker_rows = 0
    unsupported_link_type_rows = evidence_mismatch_rows = input_target_leak_rows = evidence_target_leak_rows = 0
    quality_claim_error_rows = definition_reference_provenance_claim_rows = 0

    for row in rows:
        row_id, split, objective = str(row.get("row_id")), str(row.get("split")), str(row.get("objective_family"))
        duplicate_row_ids += int(row_id in row_ids)
        row_ids.add(row_id)
        input_state = row.get("input_state")
        expected = row.get("expected_output")
        evidence = row.get("evidence")
        authority = row.get("authority")
        quality = row.get("quality")
        if not all(isinstance(value, dict) for value in (input_state, expected, evidence, authority, quality)):
            schema_error_rows += 1
            continue
        repo = str(evidence.get("repo_digest") or input_state.get("opaque_repo_id") or "")
        symbol = str(input_state.get("symbol_name_digest") or "")
        if not repo or not symbol or split not in EXPECTED_SPLIT_COUNTS:
            schema_error_rows += 1
        repo_splits[repo].add(split)
        if any(value is not False for value in authority.values()):
            authority_open_rows += 1
        raw_source_body_rows += int(evidence.get("raw_source_body_included") is not False)
        absolute_path_rows += int(evidence.get("absolute_path_included") is not False)
        encoded = json.dumps(row, sort_keys=True, ensure_ascii=True)
        forbidden_marker_rows += int(any(needle in encoded for needle in FORBIDDEN_SUBSTRINGS))
        quality_claim_error_rows += int(
            quality.get("source_body_read_for_extraction_only") is not True
            or quality.get("requires_independent_review_before_training") is not True
            or quality.get("precise_link_derived_from_literal_symbol_reference") is not True
        )

        key = (repo, symbol)
        if objective == "precise_symbol_definition_file_link":
            definition_reference_provenance_claim_rows += int(quality.get("precise_link_derived_from_literal_symbol_reference") is True)
            file_id, digest = expected.get("defining_file_id"), expected.get("defining_file_digest")
            unsupported_link_type_rows += int(expected.get("definition_link_type") != SUPPORTED_DEFINITION_TYPE)
            evidence_mismatch_rows += int(evidence.get("defining_file_digest") != digest)
            definition_files[key].add((str(file_id), str(digest)))
            definition_rows[key] += 1
        elif objective in SUPPORTED_REFERENCE_TYPES:
            file_id, digest = expected.get("linked_code_file_id"), expected.get("linked_code_file_digest")
            unsupported_link_type_rows += int(expected.get("reference_link_type") != SUPPORTED_REFERENCE_TYPES[objective])
            evidence_mismatch_rows += int(evidence.get("linked_code_file_digest") != digest)
            reference_rows[key] += 1
            ref_id, ref_digest = input_state.get("reference_file_id"), evidence.get("reference_file_digest")
            file_id_digests[str(ref_id)].add(str(ref_digest))
            _add_endpoint(endpoint_splits, ref_id, split)
            _add_endpoint(endpoint_splits, ref_digest, split)
        else:
            unsupported_link_type_rows += 1
            file_id = digest = None
        file_id_digests[str(file_id)].add(str(digest))
        _add_endpoint(endpoint_splits, file_id, split)
        _add_endpoint(endpoint_splits, digest, split)

        input_values = {str(value) for value in input_state.values() if isinstance(value, (str, int, float, bool))}
        target_values = {str(value) for value in expected.values() if isinstance(value, (str, int, float, bool))}
        evidence_values = {str(value) for value in evidence.values() if isinstance(value, (str, int, float, bool))}
        input_target_leak_rows += int(bool(input_values.intersection(target_values)))
        evidence_target_leak_rows += int(bool(evidence_values.intersection(target_values)))
        semantic_hashes[stable_hash({"split": split, "objective": objective, "input_state": input_state, "expected_output": expected, "evidence": evidence})] += 1
        target_key = stable_hash({"objective": objective, "expected_output": expected})
        input_key = stable_hash({"objective": objective, "input_state": input_state})
        target_hashes[target_key] += 1
        target_splits[target_key].add(split)
        input_targets[input_key].add(target_key)
        input_row_counts[input_key] += 1

    ambiguous_keys = {key for key, files in definition_files.items() if len(files) > 1}
    missing_definition_reference_rows = sum(count for key, count in reference_rows.items() if key not in definition_files)
    ambiguous_definition_rows = sum(definition_rows[key] for key in ambiguous_keys)
    ambiguous_reference_rows = sum(reference_rows[key] for key in ambiguous_keys)
    conflicting_inputs = {key for key, targets in input_targets.items() if len(targets) > 1}
    return {
        "precise_link_rows_reviewed": len(rows),
        "objective_counts": objective_counts,
        "split_counts": split_counts,
        "duplicate_row_ids": duplicate_row_ids,
        "schema_error_rows": schema_error_rows,
        "authority_open_rows": authority_open_rows,
        "raw_source_body_rows": raw_source_body_rows,
        "absolute_path_rows": absolute_path_rows,
        "forbidden_marker_rows": forbidden_marker_rows,
        "unsupported_link_type_rows": unsupported_link_type_rows,
        "evidence_mismatch_rows": evidence_mismatch_rows,
        "quality_claim_error_rows": quality_claim_error_rows,
        "definition_reference_provenance_claim_rows": definition_reference_provenance_claim_rows,
        "input_target_leak_rows": input_target_leak_rows,
        "evidence_target_leak_rows": evidence_target_leak_rows,
        "file_identity_conflict_ids": sum(1 for digests in file_id_digests.values() if len(digests) > 1),
        "cross_split_repo_digest_groups": sum(1 for splits in repo_splits.values() if len(splits) > 1),
        "cross_split_endpoint_groups": sum(1 for splits in endpoint_splits.values() if len(splits) > 1),
        "semantic_duplicate_excess_rows": sum(count - 1 for count in semantic_hashes.values() if count > 1),
        "semantic_duplicate_signatures": sum(1 for count in semantic_hashes.values() if count > 1),
        "target_duplicate_instances": sum(count for count in target_hashes.values() if count > 1),
        "target_duplicate_excess_rows": sum(count - 1 for count in target_hashes.values() if count > 1),
        "target_duplicate_signatures": sum(1 for count in target_hashes.values() if count > 1),
        "target_signatures_cross_split": sum(1 for splits in target_splits.values() if len(splits) > 1),
        "identical_input_multiple_target_groups": len(conflicting_inputs),
        "identical_input_multiple_target_rows": sum(input_row_counts[key] for key in conflicting_inputs),
        "maximum_targets_for_identical_input": max((len(targets) for targets in input_targets.values()), default=0),
        "symbol_keys_with_multiple_definition_files": len(ambiguous_keys),
        "ambiguous_definition_rows": ambiguous_definition_rows,
        "ambiguous_reference_rows": ambiguous_reference_rows,
        "missing_definition_reference_rows": missing_definition_reference_rows,
    }


def build_packet() -> tuple[dict[str, Any], dict[str, Any], list[dict[str, Any]]]:
    summary81, audit81, contract81, rows = load_inputs()
    review = review_rows(rows)
    hard_hygiene_passed = all(review[key] == 0 for key in (
        "duplicate_row_ids", "schema_error_rows", "authority_open_rows", "raw_source_body_rows",
        "absolute_path_rows", "forbidden_marker_rows", "unsupported_link_type_rows", "evidence_mismatch_rows",
        "quality_claim_error_rows", "input_target_leak_rows", "file_identity_conflict_ids",
        "cross_split_repo_digest_groups", "cross_split_endpoint_groups", "missing_definition_reference_rows",
    ))
    label_precision_passed = (
        review["symbol_keys_with_multiple_definition_files"] == 0
        and review["identical_input_multiple_target_groups"] == 0
        and review["evidence_target_leak_rows"] == 0
        and review["definition_reference_provenance_claim_rows"] == 0
    )
    shortcut_review_passed = review["semantic_duplicate_excess_rows"] == 0 and review["target_signatures_cross_split"] == 0
    decision = "BLOCKED_PRECISE_LINK_LABEL_LEAKAGE_AMBIGUITY_AND_SPLIT_CONTAMINATION"
    summary = {
        "record_type": "stage12682_public_precise_link_independent_review_summary_v1",
        "stage": STAGE,
        "decision": decision,
        "upstream_stage": summary81["stage"],
        "upstream_rows_sha256": contract81["rows_sha256"],
        "hygiene_review_passed": hard_hygiene_passed,
        "label_precision_review_passed": label_precision_passed,
        "shortcut_review_passed": shortcut_review_passed,
        "materialization_review_passed": hard_hygiene_passed,
        "training_admission_review_passed": False,
        "semantic_repair_required": not label_precision_passed,
        "split_repair_required": review["cross_split_endpoint_groups"] > 0,
        "shortcut_repair_required": not shortcut_review_passed,
        "recommended_next_stage": "stage12683_precise_link_semantic_repair_preflight_only",
        "training_source_rows_admitted": 0,
        **{key: review[key] for key in review if key not in {"objective_counts", "split_counts"}},
        "split_counts": review["split_counts"],
        **false_fields(),
    }
    audit = {
        "record_type": "stage12682_precise_link_independent_review_audit_v1",
        "stage": STAGE,
        "decision": decision,
        "input_hashes": EXPECTED_HASHES,
        "upstream_objective_counts": audit81["objective_counts"],
        "review": review,
        "hygiene_review_passed": hard_hygiene_passed,
        "label_precision_review_passed": label_precision_passed,
        "shortcut_review_passed": shortcut_review_passed,
        "training_source_rows_admitted": 0,
        "next_required_action": summary["recommended_next_stage"],
        **false_fields(),
    }
    checks = [
        {"check_id": "stage12681_hash_pins", "status": "passed", "count": len(EXPECTED_HASHES)},
        {"check_id": "schema_authority_and_hygiene", "status": "passed" if hard_hygiene_passed else "blocked", "count": 0},
        {"check_id": "unambiguous_symbol_definition_links", "status": "passed" if label_precision_passed else "blocked", "count": review["symbol_keys_with_multiple_definition_files"]},
        {"check_id": "duplicate_and_cross_split_shortcuts", "status": "passed" if shortcut_review_passed else "blocked", "count": review["target_signatures_cross_split"]},
        {"check_id": "training_authority", "status": "blocked", "count": 0},
    ]
    for label, value in (("summary", summary), ("audit", audit), ("checks", checks)):
        assert_no_forbidden(value, label)
    return summary, audit, checks


def build(out: Path = OUT, summary_path: Path = SUMMARY) -> dict[str, Any]:
    summary, audit, checks = build_packet()
    private = {"record_type": "stage12682_private_precise_link_review_packet_v1", "stage": STAGE, "audit_sha256": stable_hash(audit), "checks_sha256": stable_hash(checks), **false_fields()}
    contract = {"record_type": "stage12682_precise_link_review_contract_v1", "stage": STAGE, "decision": summary["decision"], "upstream_rows_sha256": summary["upstream_rows_sha256"], "audit_sha256": stable_hash(audit), "private_packet_sha256": stable_hash(private), "recommended_next_stage": summary["recommended_next_stage"], **false_fields()}
    pointer = {"record_type": "stage12682_digest_pointer_v1", "stage": STAGE, "summary_sha256": stable_hash(summary), "contract_sha256": stable_hash(contract), "private_packet_sha256": stable_hash(private), "audit_sha256": stable_hash(audit), **false_fields()}
    for label, value in (("private", private), ("contract", contract), ("pointer", pointer)):
        assert_no_forbidden(value, label)
    write_json(out / "summary.json", summary)
    write_json(out / "precise_link_independent_review_audit.json", audit)
    write_jsonl(out / "private/precise_link_independent_review_checks.jsonl", checks)
    write_json(out / "private/precise_link_independent_review_packet.json", private)
    write_json(out / "contract.json", contract)
    write_json(out / "digest_pointer.json", pointer)
    write_json(summary_path, summary)
    fsync_dir(out)
    fsync_dir(out / "private")
    fsync_dir(summary_path.parent)
    return summary


if __name__ == "__main__":
    print(json.dumps(build(), indent=2, sort_keys=True, ensure_ascii=True))
