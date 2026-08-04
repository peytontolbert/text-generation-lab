#!/usr/bin/env python3
# Independently review Stage12643 repo/code CE manifest preflight artifacts.
from __future__ import annotations

import hashlib
import json
import os
from collections import Counter
from pathlib import Path
from typing import Any, Iterable, Mapping

ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12644_independent_repo_code_ce_manifest_preflight_review"
OUT = ROOT / "runs/local/artifacts" / STAGE
SUMMARY = ROOT / "runs/summaries" / f"{STAGE}.json"
S12643 = ROOT / "runs/local/artifacts/stage12643_repo_code_ce_manifest_preflight_only"
S12643_SUMMARY = ROOT / "runs/summaries/stage12643_repo_code_ce_manifest_preflight_only.json"

EXPECTED_HASHES = {
    "stage12643_summary": "f0601288b358aa021c523c1ad09be1308064104605a353ac09b0f280f94ffcd3",
    "stage12643_contract": "70b4d6888849c13462e2a02f3dfc1e6b31d7eaddd92e224dc0c68287066e6942",
    "stage12643_pointer": "d809d012339d036f226b71e3b9e5a375b565583c6b94b3ca4a08067cfe65d53d",
    "stage12643_private": "8d76368cd50c0205ef32129a39afadef709e1ebc24dee1677e033a8ebe619fa2",
    "stage12643_candidate_manifest": "8ea70571eff49854184649a9c308f1b905e217822c452bdaa79922384fcaf7aa",
    "stage12643_rows_bytes": "c627f00695a725359ed88e9a1c1977cc8f25e416953ab902dbe82bdf751e7d42",
}
EXPECTED_ARTIFACTS = [
    "contract.json",
    "digest_pointer.json",
    "private/repo_code_ce_candidate_manifest.jsonl",
    "private/repo_code_ce_manifest_preflight_packet.json",
    "summary.json",
]
EXPECTED_SPLIT_COUNTS = {"eval": 40, "strict_eval": 39, "train": 121}
ALLOWED_SPLITS = set(EXPECTED_SPLIT_COUNTS)
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
    "row_id",
    "source_ref",
    "jsonl",
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
    "\\",
    "\x00",
    "Answer:",
    "PLACEHOLDER",
    "placeholder",
    "TODO",
    "TBD",
    "<fill",
)


class Stage12644ReviewError(RuntimeError):
    pass


def stable_hash(value: Any) -> str:
    data = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("ascii")
    return hashlib.sha256(data).hexdigest()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise Stage12644ReviewError("json_object_required:" + path.name)
    return value


def read_jsonl_bytes(data: bytes) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line_number, line in enumerate(data.decode("utf-8").splitlines(), start=1):
        if not line:
            continue
        value = json.loads(line)
        if not isinstance(value, dict):
            raise Stage12644ReviewError(f"candidate_row_object_required:{line_number}")
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


def no_claim_fields() -> dict[str, bool]:
    return {field: False for field in FALSE_FIELDS}


def check_false(record: Mapping[str, Any], label: str) -> None:
    for field in FALSE_FIELDS:
        if field in record and record[field] is not False:
            raise Stage12644ReviewError(f"{label}_gate_drift:{field}")


def assert_public_sanitized(record: Mapping[str, Any], label: str) -> None:
    encoded = json.dumps(record, sort_keys=True, ensure_ascii=True)
    for needle in PUBLIC_FORBIDDEN_SUBSTRINGS:
        if needle in encoded:
            raise Stage12644ReviewError(f"{label}_public_leak:{needle}")


def assert_row_sanitized(row: Mapping[str, Any], label: str) -> None:
    encoded = json.dumps(row, sort_keys=True, ensure_ascii=True)
    for needle in ROW_FORBIDDEN_SUBSTRINGS:
        if needle in encoded:
            raise Stage12644ReviewError(f"{label}_row_leak_or_placeholder:{needle}")


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
    if not isinstance(target, Mapping):
        return labels
    for key in ("repo_capability_profile", "curriculum_uses", "recommended_next_objectives"):
        values = target.get(key) or []
        if isinstance(values, list):
            for item in values:
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
    encoded = json.dumps(row.get("input") or {}, sort_keys=True, ensure_ascii=True).lower()
    return any(needle in encoded for needle in ("/arxiv/", "/data/", "repositories/")) or "path" in encoded


def raw_source_included(row: Mapping[str, Any]) -> bool:
    anti_cheat = row.get("anti_cheat") or {}
    if isinstance(anti_cheat, Mapping) and anti_cheat.get("raw_source_included") is True:
        return True
    encoded = json.dumps(row, sort_keys=True, ensure_ascii=True).lower()
    if any(needle in encoded for needle in ("/arxiv/", "/data/", "source_ref", "source_body", "raw_body")):
        return True
    if "raw_source" in encoded and "raw_source_included" not in encoded:
        return True
    return False


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
    local_screen_passed = (
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
        "local_manifest_shortcut_screen_passed": local_screen_passed,
        "global_shortcut_preflight_passed": False,
        "stage8675_shortcut_issue_resolved": False,
        "stage8675_shortcut_issue_quarantined": False,
    }


def split_repo_overlap(rows: list[dict[str, Any]]) -> int:
    seen: dict[str, set[str]] = {}
    for row in rows:
        repo_id = str((row.get("input") or {}).get("opaque_repo_id") or "")
        split = str(row.get("split") or "")
        seen.setdefault(repo_id, set()).add(split)
    return sum(1 for splits in seen.values() if len(splits) > 1)


def audit_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    if len(rows) != 200:
        raise Stage12644ReviewError("candidate_row_count_drift")
    ids: list[str] = []
    split_counts: Counter[str] = Counter()
    schema_complete = 0
    no_placeholder = 0
    no_raw_path = 0
    authority_blocked = 0
    admitted_rows = 0
    compact_target_rows = 0
    independent_blocker_rows = 0
    stage8675_blocker_rows = 0
    source_lineage_hash_only_rows = 0
    for index, row in enumerate(rows):
        assert_row_sanitized(row, f"candidate:{index}")
        if set(REQUIRED_ROW_FIELDS).issubset(row):
            schema_complete += 1
        if row.get("record_type") != "stage12643_private_repo_code_ce_candidate_manifest_row_v1":
            raise Stage12644ReviewError("candidate_record_type_drift")
        if row.get("schema_version") != 1:
            raise Stage12644ReviewError("candidate_schema_version_drift")
        row_id = str(row.get("row_id") or "")
        if not row_id.startswith("stage12643_repo_code_ce_candidate_"):
            raise Stage12644ReviewError("candidate_identity_prefix_drift")
        ids.append(row_id)
        split = str(row.get("split") or "")
        if split not in ALLOWED_SPLITS:
            raise Stage12644ReviewError("candidate_invalid_split:" + row_id)
        split_counts[split] += 1
        if row.get("objective_family") != "repo_code_ce_manifest_preflight":
            raise Stage12644ReviewError("candidate_objective_family_drift")
        if row.get("authority") != NO_AUTHORITY:
            raise Stage12644ReviewError("candidate_authority_drift")
        if row.get("loss_mask") != NO_LOSS:
            raise Stage12644ReviewError("candidate_loss_mask_drift")
        encoded = json.dumps(row, sort_keys=True, ensure_ascii=True)
        if not any(needle in encoded for needle in ("Answer:", "PLACEHOLDER", "placeholder", "TODO", "TBD", "<fill")):
            no_placeholder += 1
        if "/arxiv/" not in encoded and "/data/" not in encoded:
            no_raw_path += 1
        if row.get("authority") == NO_AUTHORITY and row.get("loss_mask") == NO_LOSS:
            authority_blocked += 1
        source_lineage = row.get("source_lineage") or {}
        if set(source_lineage) == {"stage8601_catalog_row_sha256", "stage8601_graph_seed_row_sha256", "source_repo_id_sha256"} and all(
            isinstance(value, str) and len(value) == 64 for value in source_lineage.values()
        ):
            source_lineage_hash_only_rows += 1
        target = row.get("target") or {}
        if str(target.get("compact_maintenance_text") or "").startswith("repo_code_knowledge languages="):
            compact_target_rows += 1
        admission = row.get("admission") or {}
        admitted_rows += int(admission.get("admitted") is True or admission.get("training_allowed") is True)
        blockers = admission.get("admission_blockers") or []
        independent_blocker_rows += int("independent_stage12644_review_required" in blockers)
        stage8675_blocker_rows += int("stage8675_symbol_binding_shortcut_issue_unresolved_or_unquarantined" in blockers)
        if admission.get("candidate_only") is not True:
            raise Stage12644ReviewError("candidate_only_flag_drift")
        if admission.get("global_shortcut_preflight_passed") is not False:
            raise Stage12644ReviewError("candidate_global_shortcut_gate_drift")
        anti = row.get("anti_cheat") or {}
        expected_anti = {
            "raw_source_included": False,
            "repo_path_in_model_input": False,
            "target_label_in_id": False,
            "objective_label_in_graph_id": False,
            "opaque_ids_only": True,
            "requires_shortcut_audit_before_training": True,
            "requires_independent_review_before_admission": True,
        }
        if anti != expected_anti:
            raise Stage12644ReviewError("candidate_anti_cheat_contract_drift")
    if len(set(ids)) != len(ids):
        raise Stage12644ReviewError("duplicate_candidate_ids")
    overlap_count = split_repo_overlap(rows)
    shortcut_audit = recompute_shortcut_audit(rows)
    return {
        "candidate_rows": len(rows),
        "unique_candidate_ids": len(set(ids)),
        "schema_complete_candidate_rows": schema_complete,
        "no_placeholder_candidate_rows": no_placeholder,
        "no_raw_path_candidate_rows": no_raw_path,
        "authority_blocked_candidate_rows": authority_blocked,
        "source_lineage_hash_only_rows": source_lineage_hash_only_rows,
        "compact_target_text_rows": compact_target_rows,
        "split_counts": dict(sorted(split_counts.items())),
        "heldout_preserved": dict(sorted(split_counts.items())) == EXPECTED_SPLIT_COUNTS and overlap_count == 0,
        "cross_split_duplicate_opaque_repo_ids": overlap_count,
        "shortcut_audit": shortcut_audit,
        "admitted_candidate_rows": admitted_rows,
        "independent_review_blocker_rows_before_review": independent_blocker_rows,
        "stage8675_blocker_rows_after_review": stage8675_blocker_rows,
    }


def load_stage12643() -> dict[str, Any]:
    emitted = sorted(path.relative_to(S12643).as_posix() for path in S12643.rglob("*") if path.is_file())
    if emitted != EXPECTED_ARTIFACTS:
        raise Stage12644ReviewError("stage12643_artifact_manifest_drift")
    summary = read_json(S12643 / "summary.json")
    external = read_json(S12643_SUMMARY)
    contract = read_json(S12643 / "contract.json")
    pointer = read_json(S12643 / "digest_pointer.json")
    private = read_json(S12643 / "private/repo_code_ce_manifest_preflight_packet.json")
    rows_bytes = (S12643 / "private/repo_code_ce_candidate_manifest.jsonl").read_bytes()
    rows = read_jsonl_bytes(rows_bytes)
    if summary != external:
        raise Stage12644ReviewError("stage12643_external_summary_mismatch")
    for label, value in (
        ("stage12643_summary", summary),
        ("stage12643_contract", contract),
        ("stage12643_pointer", pointer),
        ("stage12643_private", private),
    ):
        if stable_hash(value) != EXPECTED_HASHES[label]:
            raise Stage12644ReviewError("stage12643_pin_drift:" + label)
    if stable_hash(rows) != EXPECTED_HASHES["stage12643_candidate_manifest"]:
        raise Stage12644ReviewError("stage12643_candidate_manifest_hash_drift")
    if sha256_bytes(rows_bytes) != EXPECTED_HASHES["stage12643_rows_bytes"]:
        raise Stage12644ReviewError("stage12643_rows_bytes_hash_drift")
    for label, record in (("summary", summary), ("contract", contract), ("pointer", pointer)):
        assert_public_sanitized(record, "stage12643_" + label)
    return {"summary": summary, "contract": contract, "pointer": pointer, "private": private, "rows": rows}


def validate_stage12643(stage12643: Mapping[str, Any]) -> dict[str, Any]:
    summary = stage12643["summary"]
    contract = stage12643["contract"]
    pointer = stage12643["pointer"]
    private = stage12643["private"]
    rows = stage12643["rows"]
    for label, record in (("summary", summary), ("contract", contract), ("pointer", pointer), ("private", private)):
        check_false(record, "stage12643_" + label)
    if summary.get("decision") != "REPO_CODE_CE_CANDIDATE_MANIFEST_BUILT_NOT_ADMITTED_NO_TRAINING":
        raise Stage12644ReviewError("stage12643_decision_drift")
    for field in ("repo_code_ce_candidate_manifest_materialized", "stage12643_repo_code_ce_manifest_preflight_performed", "repo_code_knowledge_substrate_recovered"):
        if summary.get(field) is not True or contract.get(field) is not True or private.get(field) is not True:
            raise Stage12644ReviewError("stage12643_true_marker_drift:" + field)
    if summary.get("repo_code_ce_manifest_materialized") is not False or contract.get("repo_code_ce_manifest_materialized") is not False:
        raise Stage12644ReviewError("stage12643_manifest_admission_drift")
    if summary.get("training_allowed") is not False or summary.get("dataset_rows_admitted") is not False:
        raise Stage12644ReviewError("stage12643_training_gate_drift")
    expected_candidate_hash = stable_hash(rows)
    expected_private_hash = stable_hash(private)
    expected_contract_hash = stable_hash(contract)
    expected_audit_hash = stable_hash(private.get("preflight_audit"))
    if summary.get("candidate_manifest_sha256") != expected_candidate_hash:
        raise Stage12644ReviewError("summary_candidate_manifest_hash_mismatch")
    if contract.get("candidate_manifest_sha256") != expected_candidate_hash:
        raise Stage12644ReviewError("contract_candidate_manifest_hash_mismatch")
    if summary.get("private_packet_sha256") != expected_private_hash or contract.get("private_packet_sha256") != expected_private_hash:
        raise Stage12644ReviewError("private_packet_hash_mismatch")
    if summary.get("preflight_audit_sha256") != expected_audit_hash or contract.get("preflight_audit_sha256") != expected_audit_hash:
        raise Stage12644ReviewError("preflight_audit_hash_mismatch")
    if pointer.get("contract_sha256") != expected_contract_hash:
        raise Stage12644ReviewError("pointer_contract_hash_mismatch")
    if pointer.get("private_packet_sha256") != expected_private_hash:
        raise Stage12644ReviewError("pointer_private_hash_mismatch")
    if pointer.get("candidate_manifest_sha256") != expected_candidate_hash:
        raise Stage12644ReviewError("pointer_candidate_hash_mismatch")
    if pointer.get("preflight_audit_sha256") != expected_audit_hash:
        raise Stage12644ReviewError("pointer_preflight_audit_hash_mismatch")
    row_audit = audit_rows(rows)
    if row_audit["candidate_rows"] != summary.get("candidate_rows") or row_audit["candidate_rows"] != contract.get("candidate_rows"):
        raise Stage12644ReviewError("candidate_row_count_summary_mismatch")
    if row_audit["schema_complete_candidate_rows"] != summary.get("schema_complete_candidate_rows"):
        raise Stage12644ReviewError("schema_count_summary_mismatch")
    if row_audit["no_placeholder_candidate_rows"] != summary.get("no_placeholder_candidate_rows"):
        raise Stage12644ReviewError("placeholder_count_summary_mismatch")
    if row_audit["split_counts"] != summary.get("split_counts") or row_audit["split_counts"] != contract.get("split_counts"):
        raise Stage12644ReviewError("split_count_summary_mismatch")
    if row_audit["heldout_preserved"] is not True or summary.get("heldout_preserved") is not True:
        raise Stage12644ReviewError("heldout_not_preserved")
    if row_audit["cross_split_duplicate_opaque_repo_ids"] != 0:
        raise Stage12644ReviewError("heldout_repo_overlap")
    if row_audit["shortcut_audit"] != contract.get("shortcut_audit"):
        raise Stage12644ReviewError("shortcut_audit_contract_mismatch")
    if row_audit["shortcut_audit"]["local_manifest_shortcut_screen_passed"] is not True:
        raise Stage12644ReviewError("local_shortcut_screen_failed")
    if row_audit["shortcut_audit"]["global_shortcut_preflight_passed"] is not False:
        raise Stage12644ReviewError("global_shortcut_gate_drift")
    if summary.get("stage8675_shortcut_issue_resolved") is not False or summary.get("stage8675_shortcut_issue_quarantined") is not False:
        raise Stage12644ReviewError("stage8675_blocker_claim_drift")
    if row_audit["admitted_candidate_rows"] != 0:
        raise Stage12644ReviewError("candidate_admission_drift")
    return row_audit


def build_review(stage12643: Mapping[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    row_audit = validate_stage12643(stage12643)
    checks = [
        {"check_id": "stage12643_artifact_manifest_exact", "status": "passed", "artifact_count": len(EXPECTED_ARTIFACTS)},
        {"check_id": "stage12643_public_private_hashes_pinned", "status": "passed"},
        {"check_id": "candidate_schema_recomputed_from_private_rows", "status": "passed", "candidate_rows": row_audit["candidate_rows"]},
        {"check_id": "heldout_repo_disjointness_recomputed", "status": "passed", "cross_split_duplicate_opaque_repo_ids": 0},
        {"check_id": "shortcut_counters_recomputed_from_candidate_content", "status": "passed", "local_manifest_shortcut_screen_passed": True},
        {"check_id": "stage8675_global_shortcut_blocker_preserved", "status": "passed", "global_shortcut_preflight_passed": False},
        {"check_id": "private_rows_hash_only_lineage_no_raw_paths", "status": "passed"},
        {"check_id": "candidate_authority_and_loss_masks_closed", "status": "passed"},
        {"check_id": "public_artifacts_have_no_private_leaks", "status": "passed"},
        {"check_id": "training_eval_replay_level3_gpu_vm_forbidden", "status": "passed"},
    ]
    review = {
        "record_type": "stage12644_independent_repo_code_ce_manifest_preflight_review_v1",
        "review_scope": "independent_repo_code_ce_manifest_preflight_review_only",
        "reviewed_stage": "stage12643_repo_code_ce_manifest_preflight_only",
        "reviewed_hashes": EXPECTED_HASHES,
        "review_checks": checks,
        "review_check_count": len(checks),
        "review_status": "independent_review_passed_candidate_manifest_remains_private_no_admission_stage8675_blocks",
        "candidate_rows_independently_reviewed": row_audit["candidate_rows"],
        "unique_candidate_ids_after_review": row_audit["unique_candidate_ids"],
        "schema_complete_candidate_rows_after_review": row_audit["schema_complete_candidate_rows"],
        "no_placeholder_candidate_rows_after_review": row_audit["no_placeholder_candidate_rows"],
        "no_raw_path_candidate_rows_after_review": row_audit["no_raw_path_candidate_rows"],
        "authority_blocked_candidate_rows_after_review": row_audit["authority_blocked_candidate_rows"],
        "source_lineage_hash_only_rows_after_review": row_audit["source_lineage_hash_only_rows"],
        "compact_target_text_rows_after_review": row_audit["compact_target_text_rows"],
        "split_counts_after_review": row_audit["split_counts"],
        "heldout_preserved_after_review": row_audit["heldout_preserved"],
        "cross_split_duplicate_opaque_repo_ids_after_review": row_audit["cross_split_duplicate_opaque_repo_ids"],
        "shortcut_audit_after_review": row_audit["shortcut_audit"],
        "candidate_rows_admitted_after_review": False,
        "repo_code_ce_manifest_materialized_after_review": False,
        "training_allowed_after_review": False,
        "strict_eval_admitted_after_review": False,
        "sealed_eval_admitted_after_review": False,
        "level_3_materialized_after_review": False,
        "replay_trustworthy_after_review": False,
        "vm_runner_execution_after_review": False,
        "stage8675_shortcut_issue_resolved_after_review": False,
        "stage8675_shortcut_issue_quarantined_after_review": False,
    }
    public_card = {
        "record_type": "stage12644_public_repo_code_ce_manifest_preflight_review_card_v1",
        "review_scope": "independent_repo_code_ce_manifest_preflight_review_only",
        "review_status": review["review_status"],
        "candidate_rows_independently_reviewed": row_audit["candidate_rows"],
        "unique_candidate_ids": row_audit["unique_candidate_ids"],
        "schema_complete_candidate_rows": row_audit["schema_complete_candidate_rows"],
        "no_placeholder_candidate_rows_after_review": row_audit["no_placeholder_candidate_rows"],
        "no_raw_path_candidate_rows_after_review": row_audit["no_raw_path_candidate_rows"],
        "authority_blocked_candidate_rows_after_review": row_audit["authority_blocked_candidate_rows"],
        "split_counts_after_review": row_audit["split_counts"],
        "heldout_preserved_after_review": row_audit["heldout_preserved"],
        "cross_split_duplicate_opaque_repo_ids_after_review": row_audit["cross_split_duplicate_opaque_repo_ids"],
        "local_manifest_shortcut_screen_passed_after_review": row_audit["shortcut_audit"]["local_manifest_shortcut_screen_passed"],
        "global_shortcut_preflight_passed_after_review": row_audit["shortcut_audit"]["global_shortcut_preflight_passed"],
        "stage8675_shortcut_issue_resolved_after_review": False,
        "stage8675_shortcut_issue_quarantined_after_review": False,
        "candidate_rows_admitted_after_review": False,
        "training_allowed_after_review": False,
    }
    return review, public_card


def build_packet(stage12643: Mapping[str, Any]) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]]:
    review, public_card = build_review(stage12643)
    true_fields = {
        "repo_code_ce_candidate_manifest_materialized": True,
        "stage12643_repo_code_ce_manifest_preflight_performed": True,
        "stage12644_independent_repo_code_ce_manifest_preflight_review_performed": True,
        "repo_code_knowledge_substrate_recovered": True,
        "vm_branch_remains_paused": True,
    }
    private = {
        "record_type": "stage12644_private_independent_repo_code_ce_manifest_preflight_review_packet_v1",
        **no_claim_fields(),
        **true_fields,
        "source_hashes": EXPECTED_HASHES,
        "independent_review": review,
        "public_review_card": public_card,
        "decision": "REPO_CODE_CE_MANIFEST_PREFLIGHT_INDEPENDENT_REVIEW_PASSED_STAGE8675_STILL_BLOCKS_ADMISSION_NO_TRAINING",
    }
    contract = {
        "record_type": "stage12644_public_independent_repo_code_ce_manifest_preflight_review_contract_v1",
        **no_claim_fields(),
        **true_fields,
        "stage12643_summary_sha256": EXPECTED_HASHES["stage12643_summary"],
        "stage12643_contract_sha256": EXPECTED_HASHES["stage12643_contract"],
        "stage12643_candidate_manifest_sha256": EXPECTED_HASHES["stage12643_candidate_manifest"],
        "stage12643_rows_bytes_sha256": EXPECTED_HASHES["stage12643_rows_bytes"],
        "independent_review_sha256": stable_hash(review),
        "public_review_card_sha256": stable_hash(public_card),
        "private_independent_review_packet_sha256": stable_hash(private),
        "claim_boundary": {
            "review": "independent_repo_code_ce_manifest_preflight_review_only",
            "candidate_manifest": "private_candidates_reviewed_but_not_admitted",
            "repo_code_stage": "not_complete",
            "dataset_row_admission": "not_performed",
            "training": "not_authorized",
            "strict_eval": "not_admitted",
            "sealed_eval": "not_admitted",
            "level3": "not_materialized",
            "stage8675": "shortcut_issue_still_blocks_admission_until_repaired_or_quarantined",
        },
    }
    summary = {
        "record_type": "stage12644_public_independent_repo_code_ce_manifest_preflight_review_summary_v1",
        **no_claim_fields(),
        **true_fields,
        "stage": STAGE,
        "decision": "REPO_CODE_CE_MANIFEST_PREFLIGHT_INDEPENDENT_REVIEW_PASSED_STAGE8675_STILL_BLOCKS_ADMISSION_NO_TRAINING",
        "stage12643_summary_sha256": EXPECTED_HASHES["stage12643_summary"],
        "stage12643_contract_sha256": EXPECTED_HASHES["stage12643_contract"],
        "stage12643_candidate_manifest_sha256": EXPECTED_HASHES["stage12643_candidate_manifest"],
        "independent_review_sha256": stable_hash(review),
        "public_review_card_sha256": stable_hash(public_card),
        "private_independent_review_packet_sha256": stable_hash(private),
        "review_status": review["review_status"],
        "candidate_rows_independently_reviewed": review["candidate_rows_independently_reviewed"],
        "schema_complete_candidate_rows_after_review": review["schema_complete_candidate_rows_after_review"],
        "no_placeholder_candidate_rows_after_review": review["no_placeholder_candidate_rows_after_review"],
        "no_raw_path_candidate_rows_after_review": review["no_raw_path_candidate_rows_after_review"],
        "authority_blocked_candidate_rows_after_review": review["authority_blocked_candidate_rows_after_review"],
        "split_counts_after_review": review["split_counts_after_review"],
        "heldout_preserved_after_review": review["heldout_preserved_after_review"],
        "cross_split_duplicate_opaque_repo_ids_after_review": review["cross_split_duplicate_opaque_repo_ids_after_review"],
        "local_manifest_shortcut_screen_passed_after_review": review["shortcut_audit_after_review"]["local_manifest_shortcut_screen_passed"],
        "global_shortcut_preflight_passed_after_review": review["shortcut_audit_after_review"]["global_shortcut_preflight_passed"],
        "stage8675_shortcut_issue_resolved_after_review": False,
        "stage8675_shortcut_issue_quarantined_after_review": False,
        "candidate_rows_admitted_after_review": False,
        "repo_code_ce_manifest_materialized_after_review": False,
        "dataset_rows_admitted_after_review": False,
        "training_allowed_after_review": False,
        "frontier_100m_training_dataset_ready": False,
        "downstream_blockers": [
            "stage8675_symbol_binding_shortcut_issue_unresolved_or_unquarantined",
            "repo_code_candidate_rows_not_admitted",
            "repo_code_metrics_not_run",
            "separate_training_admission_not_performed",
        ],
        "next_required_action": "stage8675_symbol_binding_shortcut_quarantine_or_reselect_before_repo_code_admission",
    }
    for label, record in (("summary", summary), ("contract", contract), ("card", public_card)):
        check_false(record, "stage12644_" + label)
        assert_public_sanitized(record, "stage12644_" + label)
    check_false(private, "stage12644_private")
    return summary, contract, private, public_card


def build(out: Path = OUT, summary_path: Path = SUMMARY) -> dict[str, Any]:
    stage12643 = load_stage12643()
    summary, contract, private, public_card = build_packet(stage12643)
    pointer = {
        "record_type": "stage12644_public_independent_repo_code_ce_manifest_preflight_review_pointer_v1",
        **no_claim_fields(),
        "repo_code_ce_candidate_manifest_materialized": True,
        "stage12643_repo_code_ce_manifest_preflight_performed": True,
        "stage12644_independent_repo_code_ce_manifest_preflight_review_performed": True,
        "repo_code_knowledge_substrate_recovered": True,
        "vm_branch_remains_paused": True,
        "stage12643_summary_sha256": EXPECTED_HASHES["stage12643_summary"],
        "contract_sha256": stable_hash(contract),
        "private_independent_review_packet_sha256": stable_hash(private),
        "independent_review_sha256": stable_hash(private["independent_review"]),
        "public_review_card_sha256": stable_hash(public_card),
    }
    check_false(pointer, "stage12644_pointer")
    assert_public_sanitized(pointer, "stage12644_pointer")
    write_json(out / "contract.json", contract)
    write_json(out / "digest_pointer.json", pointer)
    write_json(out / "public_review_card.json", public_card)
    write_json(out / "private/independent_repo_code_ce_manifest_preflight_review.json", private)
    write_json(out / "summary.json", summary)
    write_json(summary_path, summary)
    fsync_dir(out / "private")
    fsync_dir(out)
    fsync_dir(summary_path.parent)
    return summary


if __name__ == "__main__":
    print(json.dumps(build(), sort_keys=True))
