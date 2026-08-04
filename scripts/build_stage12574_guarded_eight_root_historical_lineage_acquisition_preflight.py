#!/usr/bin/env python3
"""Build the deny-only eight-root historical-lineage acquisition preflight."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12574_guarded_eight_root_historical_lineage_acquisition_preflight"
OUT = ROOT / "runs/local/artifacts" / STAGE
SUMMARY = ROOT / "runs/summaries" / f"{STAGE}.json"
SOURCE = (
    ROOT
    / "runs/local/artifacts/stage12573_source_native_lineage_resolution_ledger"
    / "source_native_lineage_resolution_ledger.json"
)
SOURCE_ERA_FILES = {
    "stage11576_atlas": ROOT / "runs/local/artifacts/stage11576_web_fresh_source_candidate_atlas/web_fresh_source_candidate_atlas.json",
    "stage11576_root_records": ROOT / "runs/local/artifacts/stage11576_web_fresh_source_candidate_atlas/web_fresh_source_candidate_roots.jsonl",
}
PINNED_STAGE12573_FILE_SHA256 = "3c0a1d68edfaeb3c1b9c3bab97efd0d9692a855c2f8b9c72cf3aed8e346a61ec"
PINNED_STAGE12573_SUMMARY_RECORD_SHA256 = "e982c826bc81a00276add3faa3bbd87f328578ee7268e8ea6a5d8a7e01cf0964"
PINNED_STAGE12573_MAPPING_ROW_SET_SHA256 = "eee6d15d577d82f6c4072a1b3bf221afd36420c0358de8ff354c52a84d38ba60"
PINNED_SOURCE_ERA_FILE_SHA256 = {
    "stage11576_atlas": "981ab4d8934c38f5047e9edc7f6aa3e91b4c0fef3e52da51e1cdba82beb75e56",
    "stage11576_root_records": "b42c576a0cd952c34e94a8907b8b404954307aade8f367bacd4fe991d53e77d9",
}
UNRESOLVED_ROOT_SET_SHA256 = "954c086b4fcacac79f5cc45353419e2717f99f16292ab843701c3c85dbe5d019"
DIGEST_RE = re.compile(r"^[0-9a-f]{64}\Z")
AUTHORITY_FIELDS = (
    "authorization_allowed", "admission_allowed", "training_allowed",
    "replay_allowed", "gpu_allowed", "execution_authorized", "root_credit",
    "repair_credit", "level3_credit", "strict_eval_eligible",
)
CLEARANCE_FIELDS = (
    "protected_universe_resolved", "protected_clearance", "use_clearance",
)
DENY_FIELDS = (*AUTHORITY_FIELDS, *CLEARANCE_FIELDS)
ZERO = {field: False for field in DENY_FIELDS}
SOURCE_NATIVE_PROOF_SLOTS = (
    "original_lineage_record_pin_sha256",
    "canonical_repo_sha256",
    "immutable_revision_sha256",
    "tree_binding_sha256",
    "path_binding_sha256",
    "blob_binding_sha256",
    "content_binding_sha256",
    "constructor_commitment_join_sha256",
)
DIAGNOSTIC_PROOF_SLOT = "current_checkout_observation_sha256"
AUTHORITY_PROOF_SLOT = "independent_authority_status_sha256"
ALL_PROOF_SLOTS = (*SOURCE_NATIVE_PROOF_SLOTS, DIAGNOSTIC_PROOF_SLOT, AUTHORITY_PROOF_SLOT)
EVIDENCE_FIELDS = {
    "opaque_root_identity_sha256", "stage12573_ledger_row_sha256",
    "source_era_artifact_set_sha256", *ALL_PROOF_SLOTS, "evidence_row_sha256",
}
STAGE12573_FIELDS = {
    "stage", "record_type", "decision", "source_stage", "source_record_type",
    "source_file_sha256", "source_summary_record_sha256", "canonical_root_count",
    "canonical_root_set_sha256", "mapping_row_count",
    "source_native_lineage_verified_count", "unresolved_historical_binding_count",
    "independently_authorized_count", "mapping_rows", "mapping_row_set_sha256",
    "protected_content_emitted", "blocking_reasons", "non_authorizing_conditions",
    "summary_record_sha256", *DENY_FIELDS,
}
STAGE12573_ROW_FIELDS = {
    "opaque_root_identity_sha256", "stage12572_census_row_sha256",
    "resolution_basis_sha256", "source_native_lineage_evidence_sha256",
    "resolution_status", "ledger_row_sha256", *DENY_FIELDS,
}
FORBIDDEN_KEYS = {
    "stage12105_root_key", "root_id", "repo", "canonical_repo", "path", "blob",
    "content", "commit", "revision", "label", "gold", "gold_label", "gold_patch",
    "outcome", "reward", "target", "target_label", "target_text", "protected_content",
}


def stable_hash(value: Any) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(encoded.encode()).hexdigest()


def file_sha256(path: Path) -> str | None:
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected object: {path}")
    return value


def _digest(value: Any) -> bool:
    return isinstance(value, str) and DIGEST_RE.fullmatch(value) is not None


def _body(value: Mapping[str, Any], digest_field: str) -> dict[str, Any]:
    return {key: child for key, child in value.items() if key != digest_field}


def _forbidden_reasons(value: Any, location: str = "$") -> list[str]:
    reasons: list[str] = []
    if isinstance(value, Mapping):
        for key, child in value.items():
            normalized = str(key).lower()
            if normalized in FORBIDDEN_KEYS:
                reasons.append(f"forbidden_field:{location}.{normalized}")
            reasons.extend(_forbidden_reasons(child, f"{location}.{normalized}"))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            reasons.extend(_forbidden_reasons(child, f"{location}[{index}]"))
    return sorted(set(reasons))


def _source_era_set_sha256(pins: Mapping[str, str]) -> str:
    return stable_hash(dict(sorted(pins.items())))


def _constructor_join(evidence: Mapping[str, Any]) -> str:
    return stable_hash({
        "opaque_root_identity_sha256": evidence["opaque_root_identity_sha256"],
        **{slot: evidence[slot] for slot in SOURCE_NATIVE_PROOF_SLOTS[:-1]},
    })


def build_preflight(
    source: Mapping[str, Any], *, source_file_sha256: str | None,
    source_era_file_sha256: Mapping[str, str | None] | None,
    evidence_rows: Sequence[Mapping[str, Any]] = (),
) -> dict[str, Any]:
    blockers: list[str] = []
    source_pin = (
        PINNED_STAGE12573_FILE_SHA256
        if source_file_sha256 == PINNED_STAGE12573_FILE_SHA256 else None
    )
    era_pins_valid = (
        isinstance(source_era_file_sha256, Mapping)
        and set(source_era_file_sha256) == set(PINNED_SOURCE_ERA_FILE_SHA256)
        and all(source_era_file_sha256.get(key) == value for key, value in PINNED_SOURCE_ERA_FILE_SHA256.items())
    )
    if source_pin is None:
        blockers.append("stage12573_file_pin_mismatch")
    if not era_pins_valid:
        blockers.append("source_era_file_pin_set_mismatch")
    if set(source) != STAGE12573_FIELDS:
        blockers.append("stage12573_schema_not_exact")
    if _forbidden_reasons(evidence_rows):
        blockers.append("protected_or_preimage_content_detected")
    if (
        source.get("stage") != "stage12573_source_native_lineage_resolution_ledger"
        or source.get("record_type") != "stage12573_source_native_lineage_resolution_ledger_v1"
    ):
        blockers.append("stage12573_identity_mismatch")
    if (
        source.get("summary_record_sha256") != PINNED_STAGE12573_SUMMARY_RECORD_SHA256
        or stable_hash(_body(source, "summary_record_sha256")) != PINNED_STAGE12573_SUMMARY_RECORD_SHA256
    ):
        blockers.append("stage12573_summary_digest_mismatch")
    if source.get("decision") != "verified_deny_only" or source.get("blocking_reasons") != []:
        blockers.append("stage12573_not_accepted")
    if source.get("mapping_row_set_sha256") != PINNED_STAGE12573_MAPPING_ROW_SET_SHA256:
        blockers.append("stage12573_mapping_set_pin_mismatch")
    if any(source.get(field) is not False for field in DENY_FIELDS):
        blockers.append("stage12573_deny_boundary_violated")

    rows_value = source.get("mapping_rows")
    rows = rows_value if isinstance(rows_value, list) else []
    unresolved: dict[str, Mapping[str, Any]] = {}
    all_row_hashes: list[str] = []
    all_roots: list[str] = []
    for row in rows:
        if not isinstance(row, Mapping) or set(row) != STAGE12573_ROW_FIELDS:
            blockers.append("stage12573_row_schema_not_exact")
            continue
        root = row.get("opaque_root_identity_sha256")
        row_hash = row.get("ledger_row_sha256")
        if not _digest(root) or not _digest(row_hash):
            blockers.append("stage12573_row_digest_invalid")
            continue
        if stable_hash(_body(row, "ledger_row_sha256")) != row_hash:
            blockers.append("stage12573_ledger_row_digest_mismatch")
        if any(row.get(field) is not False for field in DENY_FIELDS):
            blockers.append("stage12573_row_deny_boundary_violated")
        all_roots.append(root)
        all_row_hashes.append(row_hash)
        if row.get("resolution_status") == "unresolved_historical_binding":
            if row.get("source_native_lineage_evidence_sha256") is not None:
                blockers.append("stage12573_unresolved_row_shape_invalid")
            if root in unresolved:
                blockers.append("stage12573_duplicate_unresolved_root")
            unresolved[root] = row
    if (
        len(rows) != 25 or len(all_roots) != 25 or len(set(all_roots)) != 25
        or all_roots != sorted(all_roots)
    ):
        blockers.append("stage12573_roots_missing_extra_duplicate_or_unsorted")
    if stable_hash(sorted(all_row_hashes)) != PINNED_STAGE12573_MAPPING_ROW_SET_SHA256:
        blockers.append("stage12573_mapping_row_digest_mutation")
    unresolved_roots = sorted(unresolved)
    if len(unresolved_roots) != 8 or stable_hash(unresolved_roots) != UNRESOLVED_ROOT_SET_SHA256:
        blockers.append("unresolved_root_set_missing_extra_duplicate_or_unknown")
    if (
        source.get("mapping_row_count") != 25
        or source.get("source_native_lineage_verified_count") != 17
        or source.get("unresolved_historical_binding_count") != 8
        or source.get("independently_authorized_count") != 0
    ):
        blockers.append("stage12573_partition_or_authority_mismatch")

    artifact_set = _source_era_set_sha256(PINNED_SOURCE_ERA_FILE_SHA256)
    evidence_by_root: dict[str, Mapping[str, Any]] = {}
    for evidence in evidence_rows:
        if not isinstance(evidence, Mapping) or set(evidence) != EVIDENCE_FIELDS:
            blockers.append("source_era_evidence_schema_not_exact")
            continue
        root = evidence.get("opaque_root_identity_sha256")
        if root not in unresolved:
            blockers.append("unknown_or_cross_partition_evidence_root")
            continue
        if root in evidence_by_root:
            blockers.append("duplicate_source_era_evidence_root")
            continue
        if evidence.get("stage12573_ledger_row_sha256") != unresolved[root]["ledger_row_sha256"]:
            blockers.append("cross_root_stage12573_join")
        if evidence.get("source_era_artifact_set_sha256") != artifact_set:
            blockers.append("source_era_artifact_join_mismatch")
        if not all(evidence.get(slot) is None or _digest(evidence.get(slot)) for slot in ALL_PROOF_SLOTS):
            blockers.append("source_era_proof_slot_digest_invalid")
        if evidence.get("constructor_commitment_join_sha256") is not None:
            required_inputs = SOURCE_NATIVE_PROOF_SLOTS[:-1]
            if not all(_digest(evidence.get(slot)) for slot in required_inputs):
                blockers.append("constructor_commitment_join_inputs_missing")
            elif evidence["constructor_commitment_join_sha256"] != _constructor_join(evidence):
                blockers.append("cross_root_or_source_constructor_join")
        if evidence.get("evidence_row_sha256") != stable_hash(_body(evidence, "evidence_row_sha256")):
            blockers.append("source_era_evidence_row_digest_mismatch")
        evidence_by_root[root] = evidence

    candidate_rows: list[dict[str, Any]] = []
    for root in unresolved_roots:
        ledger_hash = unresolved[root]["ledger_row_sha256"]
        checkout_observation = evidence_by_root.get(root, {}).get(DIAGNOSTIC_PROOF_SLOT)
        proof_values = {slot: None for slot in SOURCE_NATIVE_PROOF_SLOTS}
        proof_values[DIAGNOSTIC_PROOF_SLOT] = checkout_observation
        proof_values[AUTHORITY_PROOF_SLOT] = None
        missing = [*SOURCE_NATIVE_PROOF_SLOTS, AUTHORITY_PROOF_SLOT]
        if checkout_observation is None:
            missing.insert(len(SOURCE_NATIVE_PROOF_SLOTS), DIAGNOSTIC_PROOF_SLOT)
        row_body = {
            "opaque_root_identity_sha256": root,
            "stage12573_ledger_row_sha256": ledger_hash,
            "source_era_artifact_set_sha256": artifact_set,
            **proof_values,
            "lineage_status": "unresolved_historical_binding",
            "missing_proof_slots": missing,
            "current_checkout_diagnostic_only": True,
            **ZERO,
        }
        candidate_rows.append({**row_body, "acquisition_row_sha256": stable_hash(row_body)})

    blockers = sorted(set(blockers))
    acquisition_rows = [] if blockers else candidate_rows
    verified_count = 0
    body = {
        "stage": STAGE,
        "record_type": "stage12574_guarded_historical_lineage_acquisition_preflight_v1",
        "decision": "blocked" if blockers else "verified_deny_only",
        "source_stage": "stage12573_source_native_lineage_resolution_ledger",
        "source_file_sha256": source_pin,
        "source_summary_record_sha256": (
            PINNED_STAGE12573_SUMMARY_RECORD_SHA256 if source_pin else None
        ),
        "source_era_file_sha256": (
            PINNED_SOURCE_ERA_FILE_SHA256 if era_pins_valid else {}
        ),
        "source_era_artifact_set_sha256": artifact_set if era_pins_valid else None,
        "unresolved_root_set_sha256": UNRESOLVED_ROOT_SET_SHA256 if not blockers else None,
        "acquisition_row_count": len(acquisition_rows),
        "source_native_lineage_verified_count": verified_count,
        "unresolved_historical_binding_count": len(acquisition_rows),
        "independently_authorized_count": 0,
        "acquisition_rows": acquisition_rows,
        "acquisition_row_set_sha256": (
            stable_hash(sorted(row["acquisition_row_sha256"] for row in acquisition_rows))
            if not blockers else None
        ),
        "protected_content_emitted": False,
        "runtime_source_era_records_read": False,
        "current_checkout_can_promote": False,
        "blocking_reasons": blockers,
        "non_authorizing_conditions": [
            "source_era_artifact_copresence_is_not_a_record_binding",
            "caller_supplied_proof_cannot_promote_or_survive_as_authority",
            "current_checkout_similarity_and_later_copies_are_diagnostic_only",
            "independent_source_authority_absent",
        ],
        **ZERO,
    }
    return {**body, "summary_record_sha256": stable_hash(body)}


def build() -> dict[str, Any]:
    # Source-era files are intentionally digest-pinned without parsing protected records.
    return build_preflight(
        read_json(SOURCE),
        source_file_sha256=file_sha256(SOURCE),
        source_era_file_sha256={key: file_sha256(path) for key, path in SOURCE_ERA_FILES.items()},
    )


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> int:
    result = build()
    write_json(OUT / "historical_lineage_acquisition_preflight.json", result)
    write_json(OUT / "summary.json", result)
    write_json(SUMMARY, result)
    print(json.dumps({key: result[key] for key in (
        "acquisition_row_count", "source_native_lineage_verified_count",
        "unresolved_historical_binding_count", "independently_authorized_count",
    )}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
