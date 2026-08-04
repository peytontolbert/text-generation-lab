#!/usr/bin/env python3
"""Build a deny-only protected-root quarantine proposal from Stages 12573/12574."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12575_provenance_only_protected_root_quarantine_proposal"
OUT = ROOT / "runs/local/artifacts" / STAGE
SUMMARY = ROOT / "runs/summaries" / f"{STAGE}.json"
SOURCE12573 = (
    ROOT / "runs/local/artifacts/stage12573_source_native_lineage_resolution_ledger"
    / "source_native_lineage_resolution_ledger.json"
)
SOURCE12574 = (
    ROOT / "runs/local/artifacts/stage12574_guarded_eight_root_historical_lineage_acquisition_preflight"
    / "historical_lineage_acquisition_preflight.json"
)
PINNED_STAGE12573_FILE_SHA256 = "3c0a1d68edfaeb3c1b9c3bab97efd0d9692a855c2f8b9c72cf3aed8e346a61ec"
PINNED_STAGE12573_SUMMARY_RECORD_SHA256 = "e982c826bc81a00276add3faa3bbd87f328578ee7268e8ea6a5d8a7e01cf0964"
PINNED_STAGE12573_MAPPING_ROW_SET_SHA256 = "eee6d15d577d82f6c4072a1b3bf221afd36420c0358de8ff354c52a84d38ba60"
PINNED_STAGE12574_FILE_SHA256 = "bc8b2e3d9cfb1b7563e46a3ab7020c2b9104d85a9a221132cf0609a11b59f25d"
PINNED_STAGE12574_SUMMARY_RECORD_SHA256 = "eee5a6c09bff3a387281499a754cd033ecfcbfb25c7a88b13b955fcdc1a5db9c"
PINNED_STAGE12574_ACQUISITION_ROW_SET_SHA256 = "551ccd89e594cc64c539dd4e672e479f5bd5477923cf9b95836dc9af39afff2c"
CANONICAL_ROOT_SET_SHA256 = "e85fc0827bfcd9e5819fbc862f060afe35617d00b2c67b77a7effbc811541deb"
RETAINED_ROOT_SET_SHA256 = "d7866db7e54ccb58a4146275c25e31dd68100496823747e8d0870f64d99b5b65"
QUARANTINED_ROOT_SET_SHA256 = "954c086b4fcacac79f5cc45353419e2717f99f16292ab843701c3c85dbe5d019"
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
PROVENANCE_PREDICATE_FIELDS = (
    "resolution_status", "source_native_lineage_evidence_sha256",
    "lineage_status", "missing_proof_slots",
)
OUTCOME_CONDITIONED_KEYS = {
    "prediction", "predictions", "model_prediction", "model_predictions",
    "label", "labels", "gold", "gold_label", "gold_patch", "score", "scores",
    "outcome", "outcomes", "reward", "rewards", "success", "passed",
    "accuracy", "metric", "metrics", "verifier_output", "verifier_result",
}
PROTECTED_KEYS = {
    "stage12105_root_key", "root_id", "repo", "canonical_repo", "path",
    "blob", "content", "protected_content", "commit", "revision", "target",
    "target_label", "target_text",
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
SOURCE_NATIVE_PROOF_SLOTS = (
    "original_lineage_record_pin_sha256", "canonical_repo_sha256",
    "immutable_revision_sha256", "tree_binding_sha256", "path_binding_sha256",
    "blob_binding_sha256", "content_binding_sha256",
    "constructor_commitment_join_sha256",
)
STAGE12574_FIELDS = {
    "stage", "record_type", "decision", "source_stage", "source_file_sha256",
    "source_summary_record_sha256", "source_era_file_sha256",
    "source_era_artifact_set_sha256", "unresolved_root_set_sha256",
    "acquisition_row_count", "source_native_lineage_verified_count",
    "unresolved_historical_binding_count", "independently_authorized_count",
    "acquisition_rows", "acquisition_row_set_sha256", "protected_content_emitted",
    "runtime_source_era_records_read", "current_checkout_can_promote",
    "blocking_reasons", "non_authorizing_conditions", "summary_record_sha256",
    *DENY_FIELDS,
}
STAGE12574_ROW_FIELDS = {
    "opaque_root_identity_sha256", "stage12573_ledger_row_sha256",
    "source_era_artifact_set_sha256", *SOURCE_NATIVE_PROOF_SLOTS,
    "current_checkout_observation_sha256", "independent_authority_status_sha256",
    "lineage_status", "missing_proof_slots", "current_checkout_diagnostic_only",
    "acquisition_row_sha256", *DENY_FIELDS,
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
            if normalized in OUTCOME_CONDITIONED_KEYS:
                reasons.append(f"outcome_conditioned_field:{location}.{normalized}")
            if normalized in PROTECTED_KEYS:
                reasons.append(f"protected_content_field:{location}.{normalized}")
            reasons.extend(_forbidden_reasons(child, f"{location}.{normalized}"))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            reasons.extend(_forbidden_reasons(child, f"{location}[{index}]"))
    return sorted(set(reasons))


def _validate_source12573(source: Mapping[str, Any], blockers: list[str]) -> dict[str, Mapping[str, Any]]:
    if set(source) != STAGE12573_FIELDS:
        blockers.append("stage12573_schema_not_exact")
    if source.get("stage") != "stage12573_source_native_lineage_resolution_ledger" or source.get("record_type") != "stage12573_source_native_lineage_resolution_ledger_v1":
        blockers.append("stage12573_identity_mismatch")
    if source.get("summary_record_sha256") != PINNED_STAGE12573_SUMMARY_RECORD_SHA256 or stable_hash(_body(source, "summary_record_sha256")) != PINNED_STAGE12573_SUMMARY_RECORD_SHA256:
        blockers.append("stage12573_summary_digest_mismatch")
    if source.get("decision") != "verified_deny_only" or source.get("blocking_reasons") != []:
        blockers.append("stage12573_not_accepted")
    if source.get("canonical_root_set_sha256") != CANONICAL_ROOT_SET_SHA256 or source.get("mapping_row_set_sha256") != PINNED_STAGE12573_MAPPING_ROW_SET_SHA256:
        blockers.append("stage12573_root_or_mapping_set_pin_mismatch")
    if any(source.get(field) is not False for field in DENY_FIELDS):
        blockers.append("stage12573_deny_boundary_violated")

    rows_value = source.get("mapping_rows")
    rows = rows_value if isinstance(rows_value, list) else []
    by_root: dict[str, Mapping[str, Any]] = {}
    row_hashes: list[str] = []
    for row in rows:
        if not isinstance(row, Mapping) or set(row) != STAGE12573_ROW_FIELDS:
            blockers.append("stage12573_row_schema_not_exact")
            continue
        root, row_hash = row.get("opaque_root_identity_sha256"), row.get("ledger_row_sha256")
        if not _digest(root) or not _digest(row_hash):
            blockers.append("stage12573_row_digest_invalid")
            continue
        if root in by_root:
            blockers.append("duplicate_stage12573_root")
        if stable_hash(_body(row, "ledger_row_sha256")) != row_hash:
            blockers.append("stage12573_row_digest_mismatch")
        if any(row.get(field) is not False for field in DENY_FIELDS):
            blockers.append("stage12573_row_deny_boundary_violated")
        by_root[root] = row
        row_hashes.append(row_hash)
    roots = list(by_root)
    if len(rows) != 25 or len(by_root) != 25 or roots != sorted(roots) or stable_hash(sorted(roots)) != CANONICAL_ROOT_SET_SHA256:
        blockers.append("stage12573_roots_missing_extra_duplicate_unknown_or_unsorted")
    if stable_hash(sorted(row_hashes)) != PINNED_STAGE12573_MAPPING_ROW_SET_SHA256:
        blockers.append("stage12573_mapping_row_set_digest_mutation")
    return by_root


def _validate_source12574(source: Mapping[str, Any], blockers: list[str]) -> dict[str, Mapping[str, Any]]:
    if set(source) != STAGE12574_FIELDS:
        blockers.append("stage12574_schema_not_exact")
    if source.get("stage") != "stage12574_guarded_eight_root_historical_lineage_acquisition_preflight" or source.get("record_type") != "stage12574_guarded_historical_lineage_acquisition_preflight_v1":
        blockers.append("stage12574_identity_mismatch")
    if source.get("summary_record_sha256") != PINNED_STAGE12574_SUMMARY_RECORD_SHA256 or stable_hash(_body(source, "summary_record_sha256")) != PINNED_STAGE12574_SUMMARY_RECORD_SHA256:
        blockers.append("stage12574_summary_digest_mismatch")
    if source.get("decision") != "verified_deny_only" or source.get("blocking_reasons") != []:
        blockers.append("stage12574_not_accepted")
    if source.get("unresolved_root_set_sha256") != QUARANTINED_ROOT_SET_SHA256 or source.get("acquisition_row_set_sha256") != PINNED_STAGE12574_ACQUISITION_ROW_SET_SHA256:
        blockers.append("stage12574_partition_or_row_set_pin_mismatch")
    if source.get("runtime_source_era_records_read") is not False or source.get("current_checkout_can_promote") is not False or any(source.get(field) is not False for field in DENY_FIELDS):
        blockers.append("stage12574_deny_boundary_violated")

    rows_value = source.get("acquisition_rows")
    rows = rows_value if isinstance(rows_value, list) else []
    by_root: dict[str, Mapping[str, Any]] = {}
    row_hashes: list[str] = []
    for row in rows:
        if not isinstance(row, Mapping) or set(row) != STAGE12574_ROW_FIELDS:
            blockers.append("stage12574_row_schema_not_exact")
            continue
        root, row_hash = row.get("opaque_root_identity_sha256"), row.get("acquisition_row_sha256")
        if not _digest(root) or not _digest(row_hash):
            blockers.append("stage12574_row_digest_invalid")
            continue
        if root in by_root:
            blockers.append("duplicate_stage12574_root")
        if stable_hash(_body(row, "acquisition_row_sha256")) != row_hash:
            blockers.append("stage12574_row_digest_mismatch")
        if any(row.get(field) is not False for field in DENY_FIELDS):
            blockers.append("stage12574_row_deny_boundary_violated")
        by_root[root] = row
        row_hashes.append(row_hash)
    roots = list(by_root)
    if len(rows) != 8 or len(by_root) != 8 or roots != sorted(roots) or stable_hash(sorted(roots)) != QUARANTINED_ROOT_SET_SHA256:
        blockers.append("stage12574_roots_missing_extra_duplicate_unknown_or_unsorted")
    if stable_hash(sorted(row_hashes)) != PINNED_STAGE12574_ACQUISITION_ROW_SET_SHA256:
        blockers.append("stage12574_acquisition_row_set_digest_mutation")
    return by_root


def build_proposal(
    source12573: Mapping[str, Any], source12574: Mapping[str, Any], *,
    source12573_file_sha256: str | None, source12574_file_sha256: str | None,
) -> dict[str, Any]:
    blockers: list[str] = []
    pin73 = PINNED_STAGE12573_FILE_SHA256 if source12573_file_sha256 == PINNED_STAGE12573_FILE_SHA256 else None
    pin74 = PINNED_STAGE12574_FILE_SHA256 if source12574_file_sha256 == PINNED_STAGE12574_FILE_SHA256 else None
    if pin73 is None:
        blockers.append("stage12573_file_pin_mismatch")
    if pin74 is None:
        blockers.append("stage12574_file_pin_mismatch")
    forbidden = _forbidden_reasons([source12573, source12574])
    if any(reason.startswith("outcome_conditioned_field:") for reason in forbidden):
        blockers.append("outcome_conditioned_field_detected")
    if any(reason.startswith("protected_content_field:") for reason in forbidden):
        blockers.append("protected_content_detected")

    rows73 = _validate_source12573(source12573, blockers)
    rows74 = _validate_source12574(source12574, blockers)
    candidate_rows: list[dict[str, Any]] = []
    retained_roots: list[str] = []
    quarantined_roots: list[str] = []
    for root in sorted(rows73):
        row73 = rows73[root]
        complete = (
            row73.get("resolution_status") == "source_native_lineage_verified"
            and _digest(row73.get("source_native_lineage_evidence_sha256"))
        )
        row74 = rows74.get(root)
        if complete:
            if row74 is not None:
                blockers.append("stage12574_cross_partition_root")
            disposition = "retained_verified_lineage"
            retained_roots.append(root)
        else:
            incomplete74 = (
                row73.get("resolution_status") == "unresolved_historical_binding"
                and row73.get("source_native_lineage_evidence_sha256") is None
                and row74 is not None
                and row74.get("stage12573_ledger_row_sha256") == row73.get("ledger_row_sha256")
                and row74.get("lineage_status") == "unresolved_historical_binding"
                and all(row74.get(slot) is None for slot in SOURCE_NATIVE_PROOF_SLOTS)
                and row74.get("independent_authority_status_sha256") is None
                and all(slot in row74.get("missing_proof_slots", []) for slot in SOURCE_NATIVE_PROOF_SLOTS)
            )
            if not incomplete74:
                blockers.append("source_era_provenance_partition_or_completeness_mismatch")
            disposition = "quarantined_unrecoverable_historical_provenance"
            quarantined_roots.append(root)
        row_body = {
            "opaque_root_identity_sha256": root,
            "stage12573_ledger_row_sha256": row73.get("ledger_row_sha256"),
            "stage12574_acquisition_row_sha256": row74.get("acquisition_row_sha256") if row74 else None,
            "source_era_provenance_complete": complete,
            "proposed_disposition": disposition,
            "quarantine_predicate_id": "source_era_provenance_completeness_v1",
            "proposal_only": True,
            "quarantine_applied": False,
            **ZERO,
        }
        candidate_rows.append({**row_body, "proposal_row_sha256": stable_hash(row_body)})

    if set(rows74) != set(quarantined_roots):
        blockers.append("stage12574_unknown_or_cross_partition_roots")
    if len(retained_roots) != 17 or stable_hash(sorted(retained_roots)) != RETAINED_ROOT_SET_SHA256:
        blockers.append("retained_partition_mutation")
    if len(quarantined_roots) != 8 or stable_hash(sorted(quarantined_roots)) != QUARANTINED_ROOT_SET_SHA256:
        blockers.append("quarantined_partition_mutation")
    if (
        source12573.get("mapping_row_count") != 25
        or source12573.get("source_native_lineage_verified_count") != 17
        or source12573.get("unresolved_historical_binding_count") != 8
        or source12574.get("acquisition_row_count") != 8
        or source12574.get("source_native_lineage_verified_count") != 0
        or source12574.get("unresolved_historical_binding_count") != 8
    ):
        blockers.append("pinned_partition_counts_mutated")

    blockers = sorted(set(blockers))
    ledger = [] if blockers else candidate_rows
    body = {
        "stage": STAGE,
        "record_type": "stage12575_provenance_only_protected_root_quarantine_proposal_v1",
        "decision": "blocked" if blockers else "proposal_verified_deny_only",
        "artifact_kind": "proposal_control_only",
        "authorization_effect": "none",
        "source_stages": [
            "stage12573_source_native_lineage_resolution_ledger",
            "stage12574_guarded_eight_root_historical_lineage_acquisition_preflight",
        ],
        "source_file_sha256": {"stage12573": pin73, "stage12574": pin74},
        "source_summary_record_sha256": {
            "stage12573": PINNED_STAGE12573_SUMMARY_RECORD_SHA256 if pin73 else None,
            "stage12574": PINNED_STAGE12574_SUMMARY_RECORD_SHA256 if pin74 else None,
        },
        "canonical_root_count": 25 if not blockers else 0,
        "canonical_root_set_sha256": CANONICAL_ROOT_SET_SHA256 if not blockers else None,
        "proposal_row_count": len(ledger),
        "retained_verified_lineage_count": 17 if not blockers else 0,
        "quarantined_unrecoverable_historical_provenance_count": 8 if not blockers else 0,
        "retained_root_set_sha256": RETAINED_ROOT_SET_SHA256 if not blockers else None,
        "quarantined_root_set_sha256": QUARANTINED_ROOT_SET_SHA256 if not blockers else None,
        "proposal_rows": ledger,
        "proposal_row_set_sha256": stable_hash(sorted(row["proposal_row_sha256"] for row in ledger)) if not blockers else None,
        "quarantine_predicate_id": "source_era_provenance_completeness_v1",
        "quarantine_predicate_fields": list(PROVENANCE_PREDICATE_FIELDS),
        "quarantine_predicate_outcome_independent": True,
        "quarantine_applied": False,
        "original_25_root_metrics_status": "legacy_metrics_reference_missing_non_comparable",
        "legacy_metrics_reference": None,
        "legacy_metrics_file_sha256": None,
        "legacy_metrics_reference_present": False,
        "legacy_metrics_claim_preserved": False,
        "retained_17_root_eval_claim_allowed": False,
        "required_replacement_root_count": 8,
        "replacement_sealed_roots_required_before_17_root_eval_claim": True,
        "replacement_manifest_requirement": {
            "status": "required_not_supplied",
            "reference": None,
            "file_sha256": None,
            "required_root_count": 8,
            "must_be_pre_outcome_sealed": True,
            "must_be_disjoint_from_legacy_25_roots": True,
            "identity_placeholders_allowed": False,
            "root_identities_emitted": False,
        },
        "protected_content_emitted": False,
        "blocking_reasons": blockers,
        "non_authorizing_blockers": ["legacy_metrics_reference_missing"],
        "non_authorizing_conditions": [
            "proposal_does_not_apply_quarantine_or_authorize_use",
            "legacy_metrics_reference_missing_so_no_preservation_claim_is_made",
            "replacement_sealed_roots_required_before_any_17_root_eval_claim",
            "independent_source_authority_absent",
        ],
        **ZERO,
    }
    return {**body, "summary_record_sha256": stable_hash(body)}


def build() -> dict[str, Any]:
    return build_proposal(
        read_json(SOURCE12573), read_json(SOURCE12574),
        source12573_file_sha256=file_sha256(SOURCE12573),
        source12574_file_sha256=file_sha256(SOURCE12574),
    )


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> int:
    result = build()
    write_json(OUT / "provenance_only_protected_root_quarantine_proposal.json", result)
    write_json(OUT / "summary.json", result)
    write_json(SUMMARY, result)
    print(json.dumps({key: result[key] for key in (
        "proposal_row_count", "retained_verified_lineage_count",
        "quarantined_unrecoverable_historical_provenance_count",
        "authorization_allowed",
    )}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
