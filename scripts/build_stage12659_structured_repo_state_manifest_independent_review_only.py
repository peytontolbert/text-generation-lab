#!/usr/bin/env python3
# Independently review Stage12658 Structured Repo State candidate manifest without admitting rows.
from __future__ import annotations

import collections
import hashlib
import json
import os
from pathlib import Path
from typing import Any, Iterable, Mapping

ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12659_structured_repo_state_manifest_independent_review_only"
OUT = ROOT / "runs/local/artifacts" / STAGE
SUMMARY = ROOT / "runs/summaries" / f"{STAGE}.json"

S12658 = ROOT / "runs/local/artifacts/stage12658_structured_repo_state_sanitized_candidate_manifest_preflight_only"
S12658_SUMMARY = ROOT / "runs/summaries/stage12658_structured_repo_state_sanitized_candidate_manifest_preflight_only.json"
S12658_MATRIX = S12658 / "sanitized_candidate_matrix.json"
S12658_MANIFEST = S12658 / "private/sanitized_structured_repo_state_candidate_manifest.jsonl"
S12658_EXCLUDED = S12658 / "private/excluded_reference_sources.jsonl"

EXPECTED_HASHES = {
    "stage12658_summary": "3667669ce1b40796088ea90a66725fa7f18a4711246001a520dd4648f291c2d4",
    "stage12658_matrix": "35195c1c94aa627eda9f7563551edf4b0c71cd74229e053fc3abb1e1a02887a3",
    "stage12658_manifest": "1e55841f0a68433e6ca551cdfcfee2d96b73de121f74a721d50d5093898bd794",
    "stage12658_excluded": "06a68cd86907e1b2e06e6527e5ae410fb6961377279cd5fbb330e2ca3bba5803",
}

FALSE_FIELDS = (
    "implementation_ready", "dataset_rows_admitted", "structured_repo_state_rows_admitted",
    "structured_repo_state_admission_ready", "stage12660_allowed", "training_admission_allowed",
    "training_allowed", "training_run_allowed", "training_admitted", "strict_eval_admitted",
    "sealed_eval_admitted", "strict_eval_eligible", "sealed_eval_eligible", "gpu_allocation_requested",
    "cuda2_training_allowed", "vm_runner_execution_allowed", "runtime_authorized", "replay_trustworthy",
    "level_3_materialized", "model_execution_authorized_next", "optimizer_step_authorized",
    "source_emission_authorized", "body_emission_authorized",
)

UPSTREAM_FALSE_FIELDS = tuple(field for field in FALSE_FIELDS if field != "stage12660_allowed") + ("stage12659_allowed",)

PUBLIC_FORBIDDEN_SUBSTRINGS = (
    "/data/", "/arxiv/", "input_text", "target_text", "query_text", "root_id", "state_id",
    "episode_id", "source_lineage", "source_row_id", "jsonl",
)
PRIVATE_FORBIDDEN_SUBSTRINGS = (
    "/data/", "/arxiv/", "\x00", "Answer: placeholder", "input_text", "target_text",
    "query_text", "source_lineage", "source_row_id",
)

EXPECTED_COUNTS = {
    "manifest_rows": 3975,
    "eligible_for_review": 2916,
    "quarantined_rows": 1059,
    "excluded_reference_source_rows": 423,
    "visible_target_quarantines": 750,
}
EXPECTED_STATUS_COUNTS = {
    "candidate_for_independent_review": 2916,
    "quarantined_target_leak_or_later_layer": 949,
    "quarantined_terminal_or_action_policy_state": 110,
}
EXPECTED_FAMILY_COUNTS = {
    "compiled_causal_states": 784,
    "compiled_multitarget_rows": 2407,
    "compiled_root_records": 784,
}
REQUIRED_BLOCKERS = (
    "evidence_sufficiency_labels_missing_or_not_reviewed",
    "state_compression_targets_require_independent_review",
    "verifier_status_state_packets_not_independently_reviewed",
    "hidden_target_leakage_review_not_complete",
    "canonical_eval_and_strict_eval_split_not_materialized",
    "structured_repo_state_admission_manifest_missing",
)
REVIEW_FINDINGS = (
    "sanitized_manifest_counts_match_stage12658_contract",
    "private_path_and_raw_text_scan_clean",
    "quarantine_boundaries_preserved",
    "reference_and_later_layer_sources_excluded",
    "eligible_rows_are_review_candidates_not_trainer_rows",
    "canonical_eval_and_strict_eval_splits_absent",
    "state_and_target_rows_need_root_metadata_enrichment_before_admission",
)


class Stage12659ReviewError(RuntimeError):
    pass


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def stable_hash(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("ascii")).hexdigest()


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise Stage12659ReviewError("json_object_required:" + path.name)
    return value


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            value = json.loads(line)
            if not isinstance(value, dict):
                raise Stage12659ReviewError(f"jsonl_object_required:{path.name}:{line_number}")
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
            stream.write(json.dumps(row, sort_keys=True, ensure_ascii=True).encode("ascii") + b"\n")
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


def check_false(record: Mapping[str, Any], label: str, fields: tuple[str, ...] = FALSE_FIELDS) -> None:
    for field in fields:
        if record.get(field) is not False:
            raise Stage12659ReviewError(f"{label}_gate_drift:{field}")


def assert_no_forbidden(value: Any, label: str, needles: tuple[str, ...]) -> None:
    encoded = json.dumps(value, sort_keys=True, ensure_ascii=True) if not isinstance(value, str) else value
    for needle in needles:
        if needle in encoded:
            raise Stage12659ReviewError(f"{label}_leak:{needle}")


def load_inputs() -> dict[str, Any]:
    for label, path in (
        ("stage12658_summary", S12658_SUMMARY), ("stage12658_matrix", S12658_MATRIX),
        ("stage12658_manifest", S12658_MANIFEST), ("stage12658_excluded", S12658_EXCLUDED),
    ):
        if sha256_bytes(path.read_bytes()) != EXPECTED_HASHES[label]:
            raise Stage12659ReviewError("pin_drift:" + label)
    summary = read_json(S12658_SUMMARY)
    matrix = read_json(S12658_MATRIX)
    manifest = read_jsonl(S12658_MANIFEST)
    excluded = read_jsonl(S12658_EXCLUDED)
    check_false(summary, "stage12658_summary", UPSTREAM_FALSE_FIELDS)
    check_false(matrix, "stage12658_matrix", UPSTREAM_FALSE_FIELDS)
    if summary.get("next_required_action") != STAGE:
        raise Stage12659ReviewError("stage12658_next_action_drift")
    return {"summary": summary, "matrix": matrix, "manifest": manifest, "excluded": excluded}


def review_manifest(manifest: list[dict[str, Any]], excluded: list[dict[str, Any]]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    assert_no_forbidden(manifest, "private_manifest", PRIVATE_FORBIDDEN_SUBSTRINGS)
    status_counts = dict(sorted(collections.Counter(str(row.get("candidate_status")) for row in manifest).items()))
    family_counts = dict(sorted(collections.Counter(str(row.get("source_row_family")) for row in manifest).items()))
    split_counts = dict(sorted(collections.Counter(str(row.get("canonical_split")) for row in manifest).items()))
    label_counts = dict(sorted(collections.Counter(str(row.get("state_label_type")) for row in manifest).items()))
    eligible = sum(1 for row in manifest if row.get("eligible_for_stage12659_review") is True)
    trainer_consumable = sum(1 for row in manifest if row.get("trainer_consumable") is True)
    admitted = sum(1 for row in manifest if row.get("row_admitted") is True)
    nonzero_weight = sum(1 for row in manifest if row.get("loss_weight") not in {0, 0.0})
    visible = sum(1 for row in manifest if row.get("source_target_visible") is True)
    missing_quarantine = [row.get("candidate_id") for row in manifest if row.get("candidate_status") != "candidate_for_independent_review" and not row.get("quarantine_reasons")]
    bad_eligible = [row.get("candidate_id") for row in manifest if row.get("eligible_for_stage12659_review") is True and row.get("candidate_status") != "candidate_for_independent_review"]
    unknown_metadata_rows = sum(
        1 for row in manifest
        if row.get("source_row_family") in {"compiled_causal_states", "compiled_multitarget_rows"}
        and (row.get("repo_family_bucket") == "unknown" or row.get("language_family") == "unknown")
    )
    excluded_rows = sum(int(row.get("row_count") or 0) for row in excluded)
    if len(manifest) != EXPECTED_COUNTS["manifest_rows"]:
        raise Stage12659ReviewError("manifest_count_drift")
    if eligible != EXPECTED_COUNTS["eligible_for_review"]:
        raise Stage12659ReviewError("eligible_count_drift")
    if len(manifest) - eligible != EXPECTED_COUNTS["quarantined_rows"]:
        raise Stage12659ReviewError("quarantine_count_drift")
    if excluded_rows != EXPECTED_COUNTS["excluded_reference_source_rows"]:
        raise Stage12659ReviewError("excluded_count_drift")
    if visible != EXPECTED_COUNTS["visible_target_quarantines"]:
        raise Stage12659ReviewError("visible_target_count_drift")
    if status_counts != EXPECTED_STATUS_COUNTS:
        raise Stage12659ReviewError("status_count_drift")
    if family_counts != EXPECTED_FAMILY_COUNTS:
        raise Stage12659ReviewError("family_count_drift")
    if trainer_consumable or admitted or nonzero_weight:
        raise Stage12659ReviewError("admission_or_training_row_drift")
    if missing_quarantine or bad_eligible:
        raise Stage12659ReviewError("quarantine_boundary_drift")
    audit = {
        "record_type": "stage12659_structured_repo_state_manifest_review_audit_v1",
        "review_decision": "PASS_AS_SANITIZED_REVIEW_CANDIDATE_MANIFEST_NOT_ADMISSION",
        "manifest_rows": len(manifest),
        "eligible_for_review_rows": eligible,
        "quarantined_rows": len(manifest) - eligible,
        "excluded_reference_source_rows": excluded_rows,
        "source_target_visible_quarantined_rows": visible,
        "trainer_consumable_rows": trainer_consumable,
        "row_admitted_count": admitted,
        "nonzero_loss_weight_rows": nonzero_weight,
        "candidate_status_counts": status_counts,
        "source_row_family_counts": family_counts,
        "canonical_split_counts": split_counts,
        "state_label_type_counts": label_counts,
        "rows_missing_repo_or_language_metadata_before_admission": unknown_metadata_rows,
        "findings": list(REVIEW_FINDINGS),
        "remaining_blockers": list(REQUIRED_BLOCKERS),
        "next_required_action": "stage12660_structured_repo_state_reviewed_candidate_enrichment_preflight_only",
        **false_fields(),
    }
    review_rows = [
        {"check_id": "counts", "status": "pass", "detail": "manifest/exclusion/status counts match pinned Stage12658"},
        {"check_id": "leak_scan", "status": "pass", "detail": "private manifest has no configured raw text, path, lineage, or placeholder markers"},
        {"check_id": "quarantine_boundary", "status": "pass", "detail": "quarantined rows are not eligible; eligible rows are not trainer consumable"},
        {"check_id": "split_readiness", "status": "blocked", "detail": "only train_candidate split exists; eval and strict_eval are not materialized"},
        {"check_id": "metadata_enrichment", "status": "blocked", "detail": "state/target candidate rows still need root metadata enrichment before admission"},
        {"check_id": "label_review", "status": "blocked", "detail": "evidence sufficiency, compression, and verifier-status labels still require independent review"},
    ]
    return audit, review_rows


def build_packet() -> tuple[dict[str, Any], dict[str, Any], list[dict[str, Any]]]:
    loaded = load_inputs()
    audit, review_rows = review_manifest(loaded["manifest"], loaded["excluded"])
    summary = {
        "record_type": "stage12659_public_structured_repo_state_manifest_review_summary_v1",
        "stage": STAGE,
        "decision": audit["review_decision"],
        "stage12658_manifest_independently_reviewed": True,
        "sanitized_manifest_safe_to_use_as_review_input": True,
        "structured_repo_state_admission_manifest_allowed_next": False,
        "manifest_rows_reviewed": audit["manifest_rows"],
        "eligible_for_review_rows": audit["eligible_for_review_rows"],
        "quarantined_rows": audit["quarantined_rows"],
        "excluded_reference_source_rows": audit["excluded_reference_source_rows"],
        "rows_missing_repo_or_language_metadata_before_admission": audit["rows_missing_repo_or_language_metadata_before_admission"],
        "blocking_issue_count": len(REQUIRED_BLOCKERS),
        "next_required_action": audit["next_required_action"],
        **false_fields(),
    }
    matrix = {
        "record_type": "stage12659_structured_repo_state_manifest_review_matrix_v1",
        "stage": STAGE,
        "review_checks": review_rows,
        "findings": list(REVIEW_FINDINGS),
        "remaining_blockers": list(REQUIRED_BLOCKERS),
        "next_required_action": audit["next_required_action"],
        **false_fields(),
    }
    for label, record in (("summary", summary), ("matrix", matrix)):
        assert_no_forbidden(record, label, PUBLIC_FORBIDDEN_SUBSTRINGS)
    return summary, audit, review_rows


def build(out: Path = OUT, summary_path: Path = SUMMARY) -> dict[str, Any]:
    summary, audit, review_rows = build_packet()
    private = {
        "record_type": "stage12659_private_structured_repo_state_manifest_review_packet_v1",
        "stage": STAGE,
        "stage12658_manifest_sha256": EXPECTED_HASHES["stage12658_manifest"],
        "review_audit_sha256": stable_hash(audit),
        "review_rows_sha256": stable_hash(review_rows),
        "remaining_blockers": list(REQUIRED_BLOCKERS),
        **false_fields(),
    }
    contract = {
        "record_type": "stage12659_structured_repo_state_manifest_review_contract_v1",
        "stage": STAGE,
        "decision": summary["decision"],
        "upstream_stage": "stage12658_structured_repo_state_sanitized_candidate_manifest_preflight_only",
        "recommended_next_stage": summary["next_required_action"],
        "private_packet_sha256": stable_hash(private),
        "review_audit_sha256": stable_hash(audit),
        **false_fields(),
    }
    pointer = {
        "record_type": "stage12659_structured_repo_state_manifest_review_digest_pointer_v1",
        "stage": STAGE,
        "summary_sha256": stable_hash(summary),
        "contract_sha256": stable_hash(contract),
        "private_packet_sha256": stable_hash(private),
        "review_audit_sha256": stable_hash(audit),
        "review_rows_sha256": stable_hash(review_rows),
        **false_fields(),
    }
    for label, record in (("summary", summary), ("contract", contract), ("pointer", pointer)):
        assert_no_forbidden(record, label, PUBLIC_FORBIDDEN_SUBSTRINGS)
    out.mkdir(parents=True, exist_ok=True)
    write_json(out / "summary.json", summary)
    write_json(out / "contract.json", contract)
    write_json(out / "digest_pointer.json", pointer)
    write_json(out / "review_audit.json", audit)
    write_json(out / "private/structured_repo_state_manifest_review_packet.json", private)
    write_jsonl(out / "private/review_checks.jsonl", review_rows)
    write_json(summary_path, summary)
    fsync_dir(out)
    fsync_dir(out / "private")
    fsync_dir(summary_path.parent)
    return summary


def main() -> None:
    print(json.dumps(build(), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
