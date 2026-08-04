#!/usr/bin/env python3
# Independently review the Stage12643 repo/code CE manifest preflight artifacts.
from __future__ import annotations

import hashlib
import json
import os
from collections import Counter
from pathlib import Path
from typing import Any, Iterable, Mapping

ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12644_repo_code_ce_manifest_independent_review_only"
OUT = ROOT / "runs/local/artifacts" / STAGE
SUMMARY = ROOT / "runs/summaries" / f"{STAGE}.json"

S12643 = ROOT / "runs/local/artifacts/stage12643_repo_code_ce_manifest_preflight_only"
S12643_SUMMARY = ROOT / "runs/summaries/stage12643_repo_code_ce_manifest_preflight_only.json"

EXPECTED_HASHES = {
    "stage12643_summary": "f0601288b358aa021c523c1ad09be1308064104605a353ac09b0f280f94ffcd3",
    "stage12643_contract": "70b4d6888849c13462e2a02f3dfc1e6b31d7eaddd92e224dc0c68287066e6942",
    "stage12643_pointer": "d809d012339d036f226b71e3b9e5a375b565583c6b94b3ca4a08067cfe65d53d",
    "stage12643_private_packet": "8d76368cd50c0205ef32129a39afadef709e1ebc24dee1677e033a8ebe619fa2",
    "stage12643_candidate_rows_bytes": "c627f00695a725359ed88e9a1c1977cc8f25e416953ab902dbe82bdf751e7d42",
}
EXPECTED_STAGE12643_ARTIFACTS = [
    "contract.json",
    "digest_pointer.json",
    "private/repo_code_ce_candidate_manifest.jsonl",
    "private/repo_code_ce_manifest_preflight_packet.json",
    "summary.json",
]
EXPECTED_SPLIT_COUNTS = {"eval": 40, "strict_eval": 39, "train": 121}
REQUIRED_ROW_FIELDS = (
    "row_id",
    "record_type",
    "schema_version",
    "split",
    "objective_family",
    "source_lineage",
    "input",
    "target",
    "loss_mask",
    "authority",
    "anti_cheat",
    "admission",
)
FALSE_FIELDS = (
    "repo_code_knowledge_stage_complete",
    "repo_code_ce_manifest_materialized",
    "repo_code_rows_admitted",
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
)
PUBLIC_FORBIDDEN_SUBSTRINGS = (
    "/data/",
    "/arxiv/",
    "jsonl",
    "row_id",
    "source_ref",
    "raw_stream",
    "stdout.raw",
    "stderr.raw",
    "production_path",
    "patch_path",
    "repository_root",
)
ROW_FORBIDDEN_SUBSTRINGS = (
    "/data/",
    "/arxiv/",
    "\x00",
    "Answer:",
    "PLACEHOLDER",
    "placeholder",
    "TODO",
    "TBD",
    "<fill",
)
NO_AUTHORITY = {
    "training_authorized": False,
    "decoder_ce_authorized": False,
    "runtime_authorized": False,
    "scoring_authorized": False,
    "harness_authorized": False,
    "source_emission_authorized": False,
    "body_emission_authorized": False,
    "gemma_authorized": False,
}
NO_LOSS = {
    "repo_code_ce_candidate": False,
    "decoder_ce": False,
    "denoise_ce": False,
    "runtime_reward": False,
    "structured_aux": False,
}
ALLOWED_SPLITS = set(EXPECTED_SPLIT_COUNTS)


class RepoCodeCeManifestIndependentReviewError(RuntimeError):
    pass


def stable_hash(value: Any) -> str:
    data = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("ascii")
    return hashlib.sha256(data).hexdigest()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise RepoCodeCeManifestIndependentReviewError("json_object_required:" + path.name)
    return value


def read_jsonl_bytes(data: bytes) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line_number, line in enumerate(data.decode("utf-8").splitlines(), start=1):
        if not line:
            continue
        value = json.loads(line)
        if not isinstance(value, dict):
            raise RepoCodeCeManifestIndependentReviewError(f"candidate_row_object_required:{line_number}")
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
            raise RepoCodeCeManifestIndependentReviewError(f"{label}_gate_drift:{field}")


def assert_public_sanitized(record: Mapping[str, Any], label: str) -> None:
    encoded = json.dumps(record, sort_keys=True, ensure_ascii=True)
    for needle in PUBLIC_FORBIDDEN_SUBSTRINGS:
        if needle in encoded:
            raise RepoCodeCeManifestIndependentReviewError(f"{label}_public_leak:{needle}")


def assert_row_sanitized(row: Mapping[str, Any], label: str) -> None:
    encoded = json.dumps(row, sort_keys=True, ensure_ascii=True)
    for needle in ROW_FORBIDDEN_SUBSTRINGS:
        if needle in encoded:
            raise RepoCodeCeManifestIndependentReviewError(f"{label}_row_leak_or_placeholder:{needle}")


def load_stage12643() -> dict[str, Any]:
    emitted = sorted(path.relative_to(S12643).as_posix() for path in S12643.rglob("*") if path.is_file())
    if emitted != EXPECTED_STAGE12643_ARTIFACTS:
        raise RepoCodeCeManifestIndependentReviewError("stage12643_artifact_manifest_drift")
    summary = read_json(S12643 / "summary.json")
    external = read_json(S12643_SUMMARY)
    contract = read_json(S12643 / "contract.json")
    pointer = read_json(S12643 / "digest_pointer.json")
    private = read_json(S12643 / "private/repo_code_ce_manifest_preflight_packet.json")
    rows_bytes = (S12643 / "private/repo_code_ce_candidate_manifest.jsonl").read_bytes()
    if summary != external:
        raise RepoCodeCeManifestIndependentReviewError("stage12643_external_summary_mismatch")
    for label, value in (
        ("stage12643_summary", summary),
        ("stage12643_contract", contract),
        ("stage12643_pointer", pointer),
        ("stage12643_private_packet", private),
    ):
        if stable_hash(value) != EXPECTED_HASHES[label]:
            raise RepoCodeCeManifestIndependentReviewError("stage12643_pin_drift:" + label)
    if sha256_bytes(rows_bytes) != EXPECTED_HASHES["stage12643_candidate_rows_bytes"]:
        raise RepoCodeCeManifestIndependentReviewError("stage12643_rows_hash_drift")
    rows = read_jsonl_bytes(rows_bytes)
    if pointer.get("contract_sha256") != EXPECTED_HASHES["stage12643_contract"]:
        raise RepoCodeCeManifestIndependentReviewError("stage12643_pointer_contract_hash_drift")
    if pointer.get("private_packet_sha256") != EXPECTED_HASHES["stage12643_private_packet"]:
        raise RepoCodeCeManifestIndependentReviewError("stage12643_pointer_private_hash_drift")
    if pointer.get("candidate_manifest_sha256") != stable_hash(rows):
        raise RepoCodeCeManifestIndependentReviewError("stage12643_pointer_candidate_hash_drift")
    if private.get("candidate_manifest_sha256") != stable_hash(rows):
        raise RepoCodeCeManifestIndependentReviewError("stage12643_private_candidate_hash_drift")
    for label, record in (("summary", summary), ("contract", contract), ("pointer", pointer)):
        assert_public_sanitized(record, "stage12643_" + label)
        check_false(record, "stage12643_" + label)
    check_false(private, "stage12643_private")
    return {"summary": summary, "contract": contract, "pointer": pointer, "private": private, "rows": rows}


def iter_strings(value: Any) -> Iterable[str]:
    if isinstance(value, str):
        yield value
    elif isinstance(value, Mapping):
        for item in value.values():
            yield from iter_strings(item)
    elif isinstance(value, list):
        for item in value:
            yield from iter_strings(item)


def target_label_values(row: Mapping[str, Any]) -> set[str]:
    target = row.get("target") or {}
    labels: set[str] = set()
    for key in ("repo_capability_profile", "curriculum_uses", "recommended_next_objectives"):
        for item in target.get(key) or []:
            if isinstance(item, str) and len(item) >= 3:
                labels.add(item.lower())
    return labels


def has_target_label_in_value(labels: set[str], value: Any) -> bool:
    if not labels:
        return False
    for text in iter_strings(value):
        lowered = text.lower()
        if any(label in lowered for label in labels):
            return True
    return False


def repo_path_in_input(row: Mapping[str, Any]) -> bool:
    encoded = json.dumps(row.get("input") or {}, sort_keys=True, ensure_ascii=True)
    return any(needle in encoded for needle in ("/arxiv/", "/data/", "repositories/")) or "path" in encoded.lower()


def raw_source_included(row: Mapping[str, Any]) -> bool:
    anti_cheat = row.get("anti_cheat") or {}
    if anti_cheat.get("raw_source_included") is True:
        return True
    encoded = json.dumps(row, sort_keys=True, ensure_ascii=True).lower()
    if any(needle in encoded for needle in ("/arxiv/", "/data/", "source_ref", "source_body", "raw_body")):
        return True
    if "raw_source" in encoded and "raw_source_included" not in encoded:
        return True
    return False


def split_repo_overlap(rows: list[dict[str, Any]]) -> int:
    seen: dict[str, set[str]] = {}
    for row in rows:
        repo_id = str((row.get("input") or {}).get("opaque_repo_id") or "")
        split = str(row.get("split"))
        seen.setdefault(repo_id, set()).add(split)
    return sum(1 for splits in seen.values() if len(splits) > 1)


def recompute_shortcut_audit(rows: list[dict[str, Any]]) -> dict[str, Any]:
    target_label_in_id_rows = 0
    repo_path_in_model_input_rows = 0
    raw_source_included_rows = 0
    objective_label_in_graph_id_rows = 0
    opaque_ids_only_rows = 0
    for row in rows:
        labels = target_label_values(row)
        if has_target_label_in_value(labels, str(row.get("row_id") or "")):
            target_label_in_id_rows += 1
        if repo_path_in_input(row):
            repo_path_in_model_input_rows += 1
        if raw_source_included(row):
            raw_source_included_rows += 1
        graph_shape = ((row.get("input") or {}).get("graph_shape") or {})
        if has_target_label_in_value(labels, graph_shape):
            objective_label_in_graph_id_rows += 1
        opaque_repo_id = str((row.get("input") or {}).get("opaque_repo_id") or "")
        if opaque_repo_id.startswith("repo_") and not repo_path_in_input(row):
            opaque_ids_only_rows += 1
    local_passed = (
        target_label_in_id_rows == 0
        and repo_path_in_model_input_rows == 0
        and raw_source_included_rows == 0
        and objective_label_in_graph_id_rows == 0
        and opaque_ids_only_rows == len(rows)
    )
    return {
        "target_label_in_id_rows": target_label_in_id_rows,
        "repo_path_in_model_input_rows": repo_path_in_model_input_rows,
        "raw_source_included_rows": raw_source_included_rows,
        "objective_label_in_graph_id_rows": objective_label_in_graph_id_rows,
        "opaque_ids_only_rows": opaque_ids_only_rows,
        "local_manifest_shortcut_screen_passed": local_passed,
        "global_shortcut_preflight_passed": False,
        "stage8675_shortcut_issue_resolved": False,
        "stage8675_shortcut_issue_quarantined": False,
    }


def validate_stage12643(stage12643: Mapping[str, Any]) -> dict[str, Any]:
    summary = stage12643["summary"]
    contract = stage12643["contract"]
    private = stage12643["private"]
    rows = stage12643["rows"]
    if summary.get("decision") != "REPO_CODE_CE_CANDIDATE_MANIFEST_BUILT_NOT_ADMITTED_NO_TRAINING":
        raise RepoCodeCeManifestIndependentReviewError("stage12643_decision_drift")
    if summary.get("candidate_rows") != 200 or summary.get("schema_complete_candidate_rows") != 200:
        raise RepoCodeCeManifestIndependentReviewError("stage12643_schema_count_drift")
    if summary.get("no_placeholder_candidate_rows") != 200 or summary.get("no_raw_path_candidate_rows") != 200:
        raise RepoCodeCeManifestIndependentReviewError("stage12643_clean_count_drift")
    if summary.get("authority_blocked_candidate_rows") != 200 or summary.get("model_ready_training_rows") != 0:
        raise RepoCodeCeManifestIndependentReviewError("stage12643_authority_count_drift")
    if summary.get("split_counts") != EXPECTED_SPLIT_COUNTS or summary.get("heldout_preserved") is not True:
        raise RepoCodeCeManifestIndependentReviewError("stage12643_heldout_summary_drift")
    if summary.get("next_required_action") != "stage12644_independent_repo_code_ce_manifest_preflight_review_or_stage8675_shortcut_quarantine":
        raise RepoCodeCeManifestIndependentReviewError("stage12643_next_action_drift")
    for field in (
        "training_allowed",
        "dataset_rows_admitted",
        "repo_code_ce_manifest_materialized",
        "repo_code_knowledge_stage_complete",
        "strict_eval_admitted",
        "sealed_eval_admitted",
        "stage8675_shortcut_issue_resolved",
        "stage8675_shortcut_issue_quarantined",
    ):
        if summary.get(field) is not False:
            raise RepoCodeCeManifestIndependentReviewError("stage12643_forbidden_summary_gate_drift:" + field)
    if summary.get("repo_code_ce_candidate_manifest_materialized") is not True:
        raise RepoCodeCeManifestIndependentReviewError("stage12643_candidate_manifest_marker_missing")

    ids = []
    split_counts: Counter[str] = Counter()
    schema_complete_rows = 0
    placeholder_rows = 0
    raw_path_rows = 0
    authority_blocked_rows = 0
    stale_shortcut_field_rows = 0
    local_shortcut_true_rows = 0
    global_shortcut_false_rows = 0
    compact_text_rows = 0
    source_lineage_hash_rows = 0
    language_counts: Counter[str] = Counter()
    build_system_counts: Counter[str] = Counter()
    for row in rows:
        if not set(REQUIRED_ROW_FIELDS) <= set(row):
            raise RepoCodeCeManifestIndependentReviewError("candidate_required_field_missing")
        schema_complete_rows += 1
        ids.append(str(row["row_id"]))
        if not str(row["row_id"]).startswith("stage12643_repo_code_ce_candidate_"):
            raise RepoCodeCeManifestIndependentReviewError("candidate_identity_prefix_drift")
        if row.get("record_type") != "stage12643_private_repo_code_ce_candidate_manifest_row_v1":
            raise RepoCodeCeManifestIndependentReviewError("candidate_record_type_drift")
        if row.get("schema_version") != 1 or row.get("objective_family") != "repo_code_ce_manifest_preflight":
            raise RepoCodeCeManifestIndependentReviewError("candidate_schema_or_objective_drift")
        if row.get("split") not in ALLOWED_SPLITS:
            raise RepoCodeCeManifestIndependentReviewError("candidate_split_drift")
        split_counts.update([str(row["split"])])
        encoded = json.dumps(row, sort_keys=True, ensure_ascii=True)
        if any(needle in encoded for needle in ("Answer:", "PLACEHOLDER", "placeholder", "TODO", "TBD", "<fill")):
            placeholder_rows += 1
        if "/arxiv/" in encoded or "/data/" in encoded:
            raw_path_rows += 1
        assert_row_sanitized(row, "stage12643_candidate")
        if row.get("authority") == NO_AUTHORITY and row.get("loss_mask") == NO_LOSS:
            authority_blocked_rows += 1
        admission = row.get("admission") if isinstance(row.get("admission"), dict) else {}
        stale_shortcut_field_rows += int("shortcut_preflight_passed" in admission)
        local_shortcut_true_rows += int(admission.get("local_manifest_shortcut_screen_passed") is True)
        global_shortcut_false_rows += int(admission.get("global_shortcut_preflight_passed") is False)
        for gate in ("admitted", "training_allowed"):
            if admission.get(gate) is not False:
                raise RepoCodeCeManifestIndependentReviewError("candidate_admission_gate_drift:" + gate)
        if admission.get("candidate_only") is not True or admission.get("schema_preflight_passed") is not True:
            raise RepoCodeCeManifestIndependentReviewError("candidate_preflight_marker_drift")
        target = row.get("target") if isinstance(row.get("target"), dict) else {}
        text = target.get("compact_maintenance_text")
        compact_text_rows += int(isinstance(text, str) and text.startswith("repo_code_knowledge languages="))
        source_lineage = row.get("source_lineage") if isinstance(row.get("source_lineage"), dict) else {}
        source_lineage_hash_rows += int(
            len(str(source_lineage.get("stage8601_catalog_row_sha256") or "")) == 64
            and len(str(source_lineage.get("stage8601_graph_seed_row_sha256") or "")) == 64
            and len(str(source_lineage.get("source_repo_id_sha256") or "")) == 64
        )
        input_state = row.get("input") if isinstance(row.get("input"), dict) else {}
        for language in input_state.get("language_families") or []:
            language_counts.update([str(language)])
        for build_system in input_state.get("build_system_families") or []:
            build_system_counts.update([str(build_system)])

    if len(rows) != 200 or len(set(ids)) != 200:
        raise RepoCodeCeManifestIndependentReviewError("candidate_row_count_or_identity_drift")
    if dict(sorted(split_counts.items())) != EXPECTED_SPLIT_COUNTS:
        raise RepoCodeCeManifestIndependentReviewError("candidate_split_count_drift")
    if split_repo_overlap(rows) != 0:
        raise RepoCodeCeManifestIndependentReviewError("candidate_cross_split_overlap")
    shortcut_audit = recompute_shortcut_audit(rows)
    if shortcut_audit != contract.get("shortcut_audit"):
        raise RepoCodeCeManifestIndependentReviewError("stage12643_shortcut_audit_mismatch")
    private_audit = private.get("preflight_audit") if isinstance(private.get("preflight_audit"), dict) else {}
    if private_audit.get("cross_split_duplicate_opaque_repo_ids") != 0:
        raise RepoCodeCeManifestIndependentReviewError("stage12643_private_overlap_drift")
    if private_audit.get("shortcut_audit") != shortcut_audit:
        raise RepoCodeCeManifestIndependentReviewError("stage12643_private_shortcut_audit_mismatch")
    if (
        schema_complete_rows != 200
        or placeholder_rows != 0
        or raw_path_rows != 0
        or authority_blocked_rows != 200
        or stale_shortcut_field_rows != 0
        or local_shortcut_true_rows != 200
        or global_shortcut_false_rows != 200
        or compact_text_rows != 200
        or source_lineage_hash_rows != 200
    ):
        raise RepoCodeCeManifestIndependentReviewError("candidate_row_invariant_drift")
    return {
        "candidate_rows": len(rows),
        "unique_candidate_ids": len(set(ids)),
        "schema_complete_rows": schema_complete_rows,
        "placeholder_rows": placeholder_rows,
        "raw_path_rows": raw_path_rows,
        "authority_blocked_rows": authority_blocked_rows,
        "split_counts": dict(sorted(split_counts.items())),
        "cross_split_duplicate_opaque_repo_ids": split_repo_overlap(rows),
        "shortcut_audit": shortcut_audit,
        "stale_shortcut_field_rows": stale_shortcut_field_rows,
        "local_shortcut_true_rows": local_shortcut_true_rows,
        "global_shortcut_false_rows": global_shortcut_false_rows,
        "compact_text_rows": compact_text_rows,
        "source_lineage_hash_rows": source_lineage_hash_rows,
        "language_family_counts": dict(sorted(language_counts.items())),
        "build_system_family_counts": dict(sorted(build_system_counts.items())),
    }


def build_review(stage12643: Mapping[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    row_audit = validate_stage12643(stage12643)
    checks = [
        {"check_id": "stage12643_public_and_private_hashes_pinned", "status": "passed"},
        {"check_id": "stage12643_artifact_manifest_exact", "status": "passed", "artifact_count": len(EXPECTED_STAGE12643_ARTIFACTS)},
        {"check_id": "candidate_rows_are_200_unique_schema_complete_rows", "status": "passed"},
        {"check_id": "candidate_rows_are_private_and_non_placeholder", "status": "passed"},
        {"check_id": "heldout_opaque_repo_ids_are_split_disjoint", "status": "passed"},
        {"check_id": "shortcut_counters_independently_recomputed", "status": "passed"},
        {"check_id": "local_manifest_shortcut_screen_passed_global_shortcut_gate_blocked", "status": "passed"},
        {"check_id": "authority_and_loss_masks_block_training_decoder_runtime", "status": "passed"},
        {"check_id": "public_artifacts_have_no_private_leaks", "status": "passed"},
        {"check_id": "stage8675_remains_unresolved_or_unquarantined", "status": "passed"},
        {"check_id": "training_eval_replay_level3_gpu_vm_forbidden", "status": "passed"},
    ]
    review = {
        "record_type": "stage12644_repo_code_ce_manifest_independent_review_v1",
        "review_scope": "repo_code_ce_manifest_independent_review_only",
        "reviewed_stage": "stage12643_repo_code_ce_manifest_preflight_only",
        "reviewed_hashes": EXPECTED_HASHES,
        "review_checks": checks,
        "review_check_count": len(checks),
        "review_status": "independent_review_passed_candidate_manifest_remains_private_no_admission",
        "candidate_rows_independently_reviewed": row_audit["candidate_rows"],
        "unique_candidate_ids_after_review": row_audit["unique_candidate_ids"],
        "schema_complete_rows_after_review": row_audit["schema_complete_rows"],
        "placeholder_rows_after_review": row_audit["placeholder_rows"],
        "raw_path_rows_after_review": row_audit["raw_path_rows"],
        "authority_blocked_rows_after_review": row_audit["authority_blocked_rows"],
        "split_counts_after_review": row_audit["split_counts"],
        "cross_split_duplicate_opaque_repo_ids_after_review": row_audit["cross_split_duplicate_opaque_repo_ids"],
        "shortcut_audit_after_review": row_audit["shortcut_audit"],
        "stale_shortcut_field_rows_after_review": row_audit["stale_shortcut_field_rows"],
        "compact_text_rows_after_review": row_audit["compact_text_rows"],
        "source_lineage_hash_rows_after_review": row_audit["source_lineage_hash_rows"],
        "candidate_rows_admitted_after_review": False,
        "training_allowed_after_review": False,
        "strict_eval_admitted_after_review": False,
        "sealed_eval_admitted_after_review": False,
        "level_3_materialized_after_review": False,
        "replay_trustworthy_after_review": False,
        "stage8675_shortcut_issue_resolved_after_review": False,
        "stage8675_shortcut_issue_quarantined_after_review": False,
        "required_next_gate": "stage8675_symbol_binding_shortcut_quarantine_or_reselect_before_admission",
    }
    card = {
        "record_type": "stage12644_public_repo_code_ce_manifest_review_card_v1",
        "review_status": review["review_status"],
        "candidate_rows_independently_reviewed": row_audit["candidate_rows"],
        "schema_complete_rows_after_review": row_audit["schema_complete_rows"],
        "placeholder_rows_after_review": row_audit["placeholder_rows"],
        "raw_path_rows_after_review": row_audit["raw_path_rows"],
        "authority_blocked_rows_after_review": row_audit["authority_blocked_rows"],
        "split_counts_after_review": row_audit["split_counts"],
        "cross_split_duplicate_opaque_repo_ids_after_review": row_audit["cross_split_duplicate_opaque_repo_ids"],
        "shortcut_audit_after_review": row_audit["shortcut_audit"],
        "candidate_rows_admitted_after_review": False,
        "training_allowed_after_review": False,
    }
    assert_public_sanitized(card, "stage12644_card")
    return review, card


def build_packet(stage12643: Mapping[str, Any]) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]]:
    review, card = build_review(stage12643)
    true_fields = {
        "stage12644_repo_code_ce_manifest_independent_review_only": True,
        "stage12644_repo_code_ce_manifest_independent_review_performed": True,
        "repo_code_ce_candidate_manifest_reviewed": True,
        "repo_code_knowledge_substrate_recovered": True,
        "independent_review_passed": True,
    }
    private = {
        "record_type": "stage12644_private_repo_code_ce_manifest_independent_review_only_v1",
        **no_claim_fields(),
        **true_fields,
        "review": review,
        "public_review_card_sha256": stable_hash(card),
        "decision": "REPO_CODE_CE_MANIFEST_INDEPENDENT_REVIEW_PASSED_NO_ADMISSION_OR_TRAINING",
    }
    contract = {
        "record_type": "stage12644_public_repo_code_ce_manifest_independent_review_contract_v1",
        **no_claim_fields(),
        **true_fields,
        "review_sha256": stable_hash(review),
        "public_review_card_sha256": stable_hash(card),
        "private_review_packet_sha256": stable_hash(private),
        "candidate_rows_independently_reviewed": review["candidate_rows_independently_reviewed"],
        "schema_complete_rows_after_review": review["schema_complete_rows_after_review"],
        "split_counts_after_review": review["split_counts_after_review"],
        "cross_split_duplicate_opaque_repo_ids_after_review": review["cross_split_duplicate_opaque_repo_ids_after_review"],
        "shortcut_audit_after_review": review["shortcut_audit_after_review"],
        "claim_boundary": {
            "independent_review": "passed_for_private_candidate_manifest_preflight",
            "row_admission": "not_performed",
            "training": "not_authorized",
            "decoder_ce": "not_authorized",
            "repo_code_stage": "not_complete",
            "stage8675": "shortcut_issue_still_blocks_admission_until_repaired_or_quarantined",
        },
    }
    summary = {
        "record_type": "stage12644_public_repo_code_ce_manifest_independent_review_summary_v1",
        **no_claim_fields(),
        **true_fields,
        "stage": STAGE,
        "decision": "REPO_CODE_CE_MANIFEST_INDEPENDENT_REVIEW_PASSED_NO_ADMISSION_OR_TRAINING",
        "review_sha256": stable_hash(review),
        "public_review_card_sha256": stable_hash(card),
        "private_review_packet_sha256": stable_hash(private),
        "candidate_rows_independently_reviewed": review["candidate_rows_independently_reviewed"],
        "schema_complete_rows_after_review": review["schema_complete_rows_after_review"],
        "placeholder_rows_after_review": review["placeholder_rows_after_review"],
        "raw_path_rows_after_review": review["raw_path_rows_after_review"],
        "authority_blocked_rows_after_review": review["authority_blocked_rows_after_review"],
        "split_counts_after_review": review["split_counts_after_review"],
        "cross_split_duplicate_opaque_repo_ids_after_review": review["cross_split_duplicate_opaque_repo_ids_after_review"],
        "local_manifest_shortcut_screen_passed_after_review": True,
        "global_shortcut_preflight_passed_after_review": False,
        "stage8675_shortcut_issue_resolved_after_review": False,
        "stage8675_shortcut_issue_quarantined_after_review": False,
        "model_ready_training_rows": 0,
        "repo_code_ce_training_rows_admitted": 0,
        "next_required_action": "stage12645_stage8675_symbol_binding_shortcut_quarantine_or_reselect",
    }
    for label, record in (("summary", summary), ("contract", contract)):
        check_false(record, "stage12644_" + label)
        assert_public_sanitized(record, "stage12644_" + label)
    check_false(private, "stage12644_private")
    return summary, contract, private, card


def build(out: Path = OUT, summary_path: Path = SUMMARY) -> dict[str, Any]:
    stage12643 = load_stage12643()
    summary, contract, private, card = build_packet(stage12643)
    pointer = {
        "record_type": "stage12644_public_repo_code_ce_manifest_independent_review_pointer_v1",
        **no_claim_fields(),
        "stage12644_repo_code_ce_manifest_independent_review_only": True,
        "stage12644_repo_code_ce_manifest_independent_review_performed": True,
        "repo_code_ce_candidate_manifest_reviewed": True,
        "repo_code_knowledge_substrate_recovered": True,
        "independent_review_passed": True,
        "contract_sha256": stable_hash(contract),
        "private_review_packet_sha256": stable_hash(private),
        "public_review_card_sha256": stable_hash(card),
        "review_sha256": stable_hash(private["review"]),
    }
    check_false(pointer, "stage12644_pointer")
    assert_public_sanitized(pointer, "stage12644_pointer")
    write_json(out / "contract.json", contract)
    write_json(out / "digest_pointer.json", pointer)
    write_json(out / "private/repo_code_ce_manifest_independent_review_only.json", private)
    write_json(out / "public_review_card.json", card)
    write_json(out / "summary.json", summary)
    write_json(summary_path, summary)
    fsync_dir(out / "private")
    fsync_dir(out)
    fsync_dir(summary_path.parent)
    return summary


if __name__ == "__main__":
    print(json.dumps(build(), sort_keys=True))
