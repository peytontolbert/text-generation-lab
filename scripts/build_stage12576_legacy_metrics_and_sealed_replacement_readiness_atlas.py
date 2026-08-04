#!/usr/bin/env python3
"""Build the fail-closed legacy-metrics and sealed-replacement readiness atlas."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12576_legacy_metrics_and_sealed_replacement_readiness_atlas"
OUT = ROOT / "runs/local/artifacts" / STAGE
SUMMARY = ROOT / "runs/summaries" / f"{STAGE}.json"
SOURCE12574 = (
    ROOT / "runs/local/artifacts/stage12574_guarded_eight_root_historical_lineage_acquisition_preflight"
    / "historical_lineage_acquisition_preflight.json"
)
SOURCE12575 = (
    ROOT / "runs/local/artifacts/stage12575_provenance_only_protected_root_quarantine_proposal"
    / "provenance_only_protected_root_quarantine_proposal.json"
)
SOURCE12564 = ROOT / "runs/local/artifacts/stage12564_authoritative_protected_lineage_preflight/authoritative_protected_lineage_preflight.json"
SOURCE12568 = ROOT / "runs/local/artifacts/stage12568_open_swe_source_lineage_adapter/source_lineage_reference_adapter.json"
SOURCE12568_ROWS = ROOT / "runs/local/artifacts/stage12568_open_swe_source_lineage_adapter/trajectory_source_bindings.jsonl"
PINNED_STAGE12564_FILE_SHA256 = "c9e95cbab0eac344e8be5e595067114ef380730fb17baa627c1868451d99aede"
PINNED_STAGE12568_FILE_SHA256 = "a83a025e54283e82018c3762554c14d5ed5c74767201f0d8f3a84a59f70b519b"
PINNED_STAGE12568_ROWS_SHA256 = "dab856c947426dcc128acd7bb0c1731f98a6bd9d6ab5cd6eb7be8d8271150b0a"
PINNED_STAGE12574_FILE_SHA256 = "bc8b2e3d9cfb1b7563e46a3ab7020c2b9104d85a9a221132cf0609a11b59f25d"
PINNED_STAGE12574_SUMMARY_RECORD_SHA256 = "eee5a6c09bff3a387281499a754cd033ecfcbfb25c7a88b13b955fcdc1a5db9c"
PINNED_STAGE12575_FILE_SHA256 = "da7d5618703822b75207a4759550e79e69b0c0ec27ed5dffbb09986130da931e"
PINNED_STAGE12575_SUMMARY_RECORD_SHA256 = "e152e1999271afd56e4b1e0e0ad32f633043d5763812bb8b82e2e1f62c77426c"
CANONICAL_ROOT_SET_SHA256 = "e85fc0827bfcd9e5819fbc862f060afe35617d00b2c67b77a7effbc811541deb"
QUARANTINED_ROOT_SET_SHA256 = "954c086b4fcacac79f5cc45353419e2717f99f16292ab843701c3c85dbe5d019"
PINNED_LANGUAGE_STRATA = frozenset({"rust", "web_js_ts_html"})
PINNED_TASK_STRATA = frozenset({
    "transition_candidate_selection", "transition_continue_or_stop",
    "transition_next_action", "transition_verifier_transition",
})

SPINE_SOURCES = {
    "stage12547_authoritative_independent_root_ledger": (
        ROOT / "runs/summaries/stage12547_authoritative_independent_root_ledger.json",
        "c05f0fc4023805c49b98d18caf83d97046f4f3457c3faf777eae29dd50258cb9",
    ),
    "stage12560_protected_namespace_deny_sidecars": (
        ROOT / "runs/summaries/stage12560_protected_namespace_deny_sidecars.json",
        "8204b779017ea66ff1f96169f40ac962da1e379d6fa7175cc81ef395d95dcf2e",
    ),
    "stage12562_pre_outcome_candidate_commitment": (
        ROOT / "runs/summaries/stage12562_pre_outcome_candidate_commitment.json",
        "facde05a42d8be6f38d388933ab296148e7c9b135e4954c50290cbe285e6830a",
    ),
    "stage12565_paired_pre_outcome_candidate_commitment_v2": (
        ROOT / "runs/summaries/stage12565_paired_pre_outcome_candidate_commitment_v2.json",
        "f90d9a972f4e2029c97344f8ed17fa9d2f1ce8f143651901f7d21a4d3bd53e1a",
    ),
}

DIGEST_RE = re.compile(r"^[0-9a-f]{64}\Z")
DENY_FIELDS = (
    "authorization_allowed", "admission_allowed", "training_allowed",
    "evaluation_allowed", "strict_eval_eligible", "replay_allowed", "gpu_allowed",
    "execution_authorized", "root_credit", "repair_credit", "level3_credit",
    "protected_clearance", "use_clearance", "replacement_admitted",
    "replacement_applied",
)
ZERO = {field: False for field in DENY_FIELDS}
LEGACY_RECORD_TYPE = "legacy_25_root_metrics_reference_v1"
REPLACEMENT_RECORD_TYPE = "prospective_sealed_replacement_candidate_v1"
LEGACY_FIELDS = {
    "record_type", "canonical_root_count", "canonical_root_set_sha256",
    "metrics_artifact_reference", "metrics_file_sha256", "metric_payload_sha256",
    "source_revision_sha256", "metrics_record_sha256",
}
REPLACEMENT_FIELDS = {
    "record_type", "candidate_identity_sha256", "source_native_lineage_record_sha256",
    "canonical_repo_sha256", "repo_family_sha256", "immutable_revision_sha256",
    "tree_sha256", "blob_sha256", "split_name",
    "split_disjoint_from_legacy_25_roots", "root_disjoint_from_legacy_25_roots",
    "repo_family_disjoint_from_legacy_25_roots", "language_stratum", "task_stratum",
    "split_disjointness_evidence_sha256", "root_disjointness_evidence_sha256",
    "repo_family_disjointness_evidence_sha256", "stratum_binding_evidence_sha256",
    "pre_execution_seal_sha256", "pre_execution_seal_ready", "selection_basis",
    "outcome_fields_read", "candidate_record_sha256",
}
STAGE12574_FIELDS = {
    "stage", "record_type", "decision", "source_stage", "source_file_sha256",
    "source_summary_record_sha256", "source_era_file_sha256", "source_era_artifact_set_sha256",
    "unresolved_root_set_sha256", "acquisition_row_count", "source_native_lineage_verified_count",
    "unresolved_historical_binding_count", "independently_authorized_count", "acquisition_rows",
    "acquisition_row_set_sha256", "protected_content_emitted", "runtime_source_era_records_read",
    "current_checkout_can_promote", "blocking_reasons", "non_authorizing_conditions",
    "summary_record_sha256", "authorization_allowed", "admission_allowed", "training_allowed",
    "replay_allowed", "gpu_allowed", "execution_authorized", "root_credit", "repair_credit",
    "level3_credit", "strict_eval_eligible", "protected_universe_resolved", "protected_clearance",
    "use_clearance",
}
STAGE12575_FIELDS = {
    "stage", "record_type", "decision", "artifact_kind", "authorization_effect", "source_stages",
    "source_file_sha256", "source_summary_record_sha256", "canonical_root_count",
    "canonical_root_set_sha256", "proposal_row_count", "retained_verified_lineage_count",
    "quarantined_unrecoverable_historical_provenance_count", "retained_root_set_sha256",
    "quarantined_root_set_sha256", "proposal_rows", "proposal_row_set_sha256",
    "quarantine_predicate_id", "quarantine_predicate_fields", "quarantine_predicate_outcome_independent",
    "quarantine_applied", "original_25_root_metrics_status", "legacy_metrics_reference",
    "legacy_metrics_file_sha256", "legacy_metrics_reference_present", "legacy_metrics_claim_preserved",
    "retained_17_root_eval_claim_allowed", "required_replacement_root_count",
    "replacement_sealed_roots_required_before_17_root_eval_claim", "replacement_manifest_requirement",
    "protected_content_emitted", "blocking_reasons", "non_authorizing_blockers",
    "non_authorizing_conditions", "summary_record_sha256", "authorization_allowed", "admission_allowed",
    "training_allowed", "replay_allowed", "gpu_allowed", "execution_authorized", "root_credit",
    "repair_credit", "level3_credit", "strict_eval_eligible", "protected_universe_resolved",
    "protected_clearance", "use_clearance",
}
FORBIDDEN_OUTCOME_KEYS = {
    "prediction", "predictions", "model_prediction", "model_predictions", "score",
    "scores", "outcome", "outcomes", "reward", "rewards", "success", "passed",
    "accuracy", "verifier_output", "verifier_result", "gold", "gold_patch",
    "test_output", "patch_effect",
}
PROTECTED_CONTENT_KEYS = {
    "content", "protected_content", "target", "target_text", "target_label",
    "patch", "gold_patch", "prompt", "raw_prompt", "path", "instance_id",
    "canonical_repo", "repo", "base_commit", "task_key",
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


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    if any(not isinstance(row, dict) for row in rows):
        raise ValueError(f"expected object rows: {path}")
    return rows


def _allowlisted_local_reference(reference: Any, allowlist: Mapping[str, Path]) -> Path | None:
    if not isinstance(reference, str) or reference.startswith(("immutable://", "http://", "https://")):
        return None
    candidate = (ROOT / reference).resolve()
    return candidate if candidate in {path.resolve() for path in allowlist.values()} and candidate.is_file() else None


def _digest(value: Any) -> bool:
    return isinstance(value, str) and DIGEST_RE.fullmatch(value) is not None


def _body(value: Mapping[str, Any], digest_field: str) -> dict[str, Any]:
    return {key: child for key, child in value.items() if key != digest_field}


def _walk_typed_records(value: Any, record_type: str) -> list[Mapping[str, Any]]:
    found: list[Mapping[str, Any]] = []
    if isinstance(value, Mapping):
        if value.get("record_type") == record_type:
            found.append(value)
        for child in value.values():
            found.extend(_walk_typed_records(child, record_type))
    elif isinstance(value, list):
        for child in value:
            found.extend(_walk_typed_records(child, record_type))
    return found


def _forbidden_candidate_reasons(value: Any, location: str = "$") -> list[str]:
    reasons: list[str] = []
    if isinstance(value, Mapping):
        for key, child in value.items():
            normalized = str(key).lower()
            if normalized in FORBIDDEN_OUTCOME_KEYS:
                reasons.append(f"outcome_conditioned_field:{location}.{normalized}")
            if normalized in PROTECTED_CONTENT_KEYS:
                reasons.append(f"protected_content_field:{location}.{normalized}")
            reasons.extend(_forbidden_candidate_reasons(child, f"{location}.{normalized}"))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            reasons.extend(_forbidden_candidate_reasons(child, f"{location}[{index}]"))
    return sorted(set(reasons))


def _validate_stage12574(source: Mapping[str, Any], digest: str | None, blockers: list[str]) -> None:
    if digest != PINNED_STAGE12574_FILE_SHA256:
        blockers.append("stage12574_file_pin_mismatch")
    if set(source) != STAGE12574_FIELDS:
        blockers.append("stage12574_schema_not_exact")
    if (
        source.get("stage") != "stage12574_guarded_eight_root_historical_lineage_acquisition_preflight"
        or source.get("record_type") != "stage12574_guarded_historical_lineage_acquisition_preflight_v1"
        or source.get("summary_record_sha256") != PINNED_STAGE12574_SUMMARY_RECORD_SHA256
        or stable_hash(_body(source, "summary_record_sha256")) != PINNED_STAGE12574_SUMMARY_RECORD_SHA256
    ):
        blockers.append("stage12574_identity_or_summary_pin_mismatch")
    if (
        source.get("decision") != "verified_deny_only"
        or source.get("unresolved_root_set_sha256") != QUARANTINED_ROOT_SET_SHA256
        or source.get("acquisition_row_count") != 8
        or source.get("source_native_lineage_verified_count") != 0
        or source.get("unresolved_historical_binding_count") != 8
    ):
        blockers.append("stage12574_partition_compatibility_mismatch")
    if any(source.get(field) is not False for field in DENY_FIELDS if field in source):
        blockers.append("stage12574_deny_boundary_violated")


def _validate_stage12575(source: Mapping[str, Any], digest: str | None, blockers: list[str]) -> None:
    if digest != PINNED_STAGE12575_FILE_SHA256:
        blockers.append("stage12575_corrected_file_pin_mismatch")
    if set(source) != STAGE12575_FIELDS:
        blockers.append("stage12575_corrected_schema_not_exact")
    forbidden = _forbidden_candidate_reasons(source)
    if any(reason.startswith("outcome_conditioned_field:") for reason in forbidden):
        blockers.append("stage12575_outcome_conditioned_field_detected")
    if any(reason.startswith("protected_content_field:") for reason in forbidden):
        blockers.append("stage12575_protected_content_detected")
    if (
        source.get("stage") != "stage12575_provenance_only_protected_root_quarantine_proposal"
        or source.get("record_type") != "stage12575_provenance_only_protected_root_quarantine_proposal_v1"
        or source.get("summary_record_sha256") != PINNED_STAGE12575_SUMMARY_RECORD_SHA256
        or stable_hash(_body(source, "summary_record_sha256")) != PINNED_STAGE12575_SUMMARY_RECORD_SHA256
    ):
        blockers.append("stage12575_corrected_identity_or_summary_pin_mismatch")
    if (
        source.get("decision") != "proposal_verified_deny_only"
        or source.get("canonical_root_count") != 25
        or source.get("canonical_root_set_sha256") != CANONICAL_ROOT_SET_SHA256
        or source.get("proposal_row_count") != 25
        or source.get("retained_verified_lineage_count") != 17
        or source.get("quarantined_unrecoverable_historical_provenance_count") != 8
        or source.get("quarantined_root_set_sha256") != QUARANTINED_ROOT_SET_SHA256
        or source.get("quarantine_applied") is not False
    ):
        blockers.append("stage12575_corrected_partition_compatibility_mismatch")
    if (
        source.get("original_25_root_metrics_status") != "legacy_metrics_reference_missing_non_comparable"
        or source.get("legacy_metrics_reference") is not None
        or source.get("replacement_manifest_requirement", {}).get("required_root_count") != 8
    ):
        blockers.append("stage12575_legacy_or_replacement_contract_mismatch")
    if any(source.get(field) is not False for field in DENY_FIELDS if field in source):
        blockers.append("stage12575_deny_boundary_violated")


def _validate_legacy(record: Mapping[str, Any], blockers: list[str]) -> bool:
    if set(record) != LEGACY_FIELDS:
        blockers.append("legacy_metrics_record_schema_not_exact")
        return False
    if stable_hash(_body(record, "metrics_record_sha256")) != record.get("metrics_record_sha256"):
        blockers.append("legacy_metrics_record_digest_mismatch")
        return False
    artifact = _allowlisted_local_reference(record.get("metrics_artifact_reference"), {})
    if artifact is None:
        blockers.append("legacy_metrics_reference_not_allowlisted_openable_local_artifact")
        return False
    # No legacy metric artifact is currently allowlisted. A future allowlist must
    # additionally parse exact semantic names/values, manifest identity, and bytes.
    blockers.append("legacy_metrics_semantic_validator_not_configured")
    return False

def _validate_candidate(record: Mapping[str, Any], blockers: list[str]) -> bool:
    forbidden = _forbidden_candidate_reasons(record)
    if any(reason.startswith("outcome_conditioned_field:") for reason in forbidden):
        blockers.append("replacement_candidate_outcome_conditioned_selection_detected")
    if any(reason.startswith("protected_content_field:") for reason in forbidden):
        blockers.append("replacement_candidate_protected_content_detected")
    if set(record) != REPLACEMENT_FIELDS:
        blockers.append("replacement_candidate_schema_not_exact")
        return False
    if stable_hash(_body(record, "candidate_record_sha256")) != record.get("candidate_record_sha256"):
        blockers.append("replacement_candidate_record_digest_mismatch")
        return False
    if record.get("language_stratum") not in PINNED_LANGUAGE_STRATA or record.get("task_stratum") not in PINNED_TASK_STRATA:
        blockers.append("replacement_candidate_required_strata_not_pinned")
    blockers.append("replacement_candidate_unopened_caller_record_rejected")
    blockers.append("replacement_candidate_source_native_git_verifier_not_invoked")
    blockers.append("replacement_candidate_full_universe_overlap_not_verified")
    blockers.append("replacement_candidate_pre_outcome_source_artifact_missing")
    return False

def _known_source_evaluations() -> list[dict[str, Any]]:
    stage64 = read_json(SOURCE12564)
    stage68 = read_json(SOURCE12568)
    rows68 = read_jsonl(SOURCE12568_ROWS)
    reasons64 = set(stage64.get("blocking_reasons") or [])
    if file_sha256(SOURCE12564) != PINNED_STAGE12564_FILE_SHA256:
        reasons64.add("source_file_pin_mismatch")
    reasons64.update({
        "no_source_native_tree_blob_evidence_per_candidate",
        "no_pre_execution_replacement_eval_seal_artifact",
        "full_protected_train_reserved_universe_overlap_not_resolved",
    })
    reasons68 = {
        "records_are_train_sources_not_replacement_eval_candidates",
        "no_source_native_tree_blob_evidence_per_candidate",
        "no_pre_execution_replacement_eval_seal_artifact",
        "outcome_blindness_not_proven_by_pre_outcome_source_artifact",
        "full_protected_train_reserved_universe_overlap_not_resolved",
    }
    if file_sha256(SOURCE12568) != PINNED_STAGE12568_FILE_SHA256 or file_sha256(SOURCE12568_ROWS) != PINNED_STAGE12568_ROWS_SHA256:
        reasons68.add("source_file_pin_mismatch")
    return [
        {"source_stage": "stage12564_authoritative_protected_lineage_preflight", "candidate_record_count": int(stage64.get("candidate_count") or 0), "eligible_candidate_count": 0, "reason_codes": sorted(reasons64)},
        {"source_stage": "stage12568_open_swe_source_lineage_adapter", "candidate_record_count": len(rows68), "eligible_candidate_count": 0, "reason_codes": sorted(reasons68)},
    ]


def build_atlas(
    source12574: Mapping[str, Any], source12575: Mapping[str, Any],
    spine_records: Sequence[Mapping[str, Any]], *,
    source12574_file_sha256: str | None, source12575_file_sha256: str | None,
    spine_file_sha256: Mapping[str, str | None],
) -> dict[str, Any]:
    fatal: list[str] = []
    _validate_stage12574(source12574, source12574_file_sha256, fatal)
    _validate_stage12575(source12575, source12575_file_sha256, fatal)

    expected_spine_names = set(SPINE_SOURCES)
    if set(spine_file_sha256) != expected_spine_names:
        fatal.append("structured_summary_spine_source_set_mismatch")
    for name, (_, expected_digest) in SPINE_SOURCES.items():
        if spine_file_sha256.get(name) != expected_digest:
            fatal.append(f"structured_summary_spine_pin_mismatch:{name}")

    legacy_records: list[Mapping[str, Any]] = []
    candidate_records: list[Mapping[str, Any]] = []
    for source in spine_records:
        legacy_records.extend(_walk_typed_records(source, LEGACY_RECORD_TYPE))
        candidate_records.extend(_walk_typed_records(source, REPLACEMENT_RECORD_TYPE))

    valid_legacy = [record for record in legacy_records if _validate_legacy(record, fatal)]
    if len(legacy_records) > 1:
        fatal.append("canonical_legacy_25_root_metrics_ambiguous")
    if len(valid_legacy) > 1:
        fatal.append("duplicate_canonical_legacy_25_root_metrics_records")

    valid_candidates = [record for record in candidate_records if _validate_candidate(record, fatal)]
    identities = [record.get("candidate_identity_sha256") for record in valid_candidates]
    repos = [record.get("canonical_repo_sha256") for record in valid_candidates]
    families = [record.get("repo_family_sha256") for record in valid_candidates]
    seals = [record.get("pre_execution_seal_sha256") for record in valid_candidates]
    if len(candidate_records) > 8:
        fatal.append("replacement_candidate_count_exceeds_eight")
    if len(identities) != len(set(identities)):
        fatal.append("duplicate_replacement_candidate_identity")
    if len(repos) != len(set(repos)):
        fatal.append("replacement_candidate_repo_overlap")
    if len(families) != len(set(families)):
        fatal.append("replacement_candidate_repo_family_overlap")
    if len(seals) != len(set(seals)):
        fatal.append("duplicate_replacement_candidate_seal")

    fatal = sorted(set(fatal))
    metrics_missing = len(valid_legacy) == 0
    candidates_missing = len(valid_candidates) == 0
    blockers = list(fatal)
    if metrics_missing:
        blockers.append("canonical_legacy_25_root_metrics_record_missing")
    if candidates_missing:
        blockers.append("prospective_sealed_replacement_candidate_records_missing")
    blockers = sorted(set(blockers))

    emit_allowed = not fatal
    legacy = valid_legacy[0] if emit_allowed and len(valid_legacy) == 1 else None
    rows: list[dict[str, Any]] = []
    if emit_allowed:
        for record in sorted(valid_candidates, key=lambda row: row["candidate_identity_sha256"]):
            row_body = {
                **{key: record[key] for key in sorted(REPLACEMENT_FIELDS)},
                "prospective_only": True,
                "seal_readiness_verified": True,
                **ZERO,
            }
            rows.append({**row_body, "atlas_row_sha256": stable_hash(row_body)})

    remaining_gaps: list[str] = []
    if legacy is None:
        remaining_gaps.append("unique_canonical_25_root_metrics_reference_with_file_payload_and_revision_pins")
    if len(rows) < 8:
        remaining_gaps.extend([
            f"{8 - len(rows)}_additional_prospective_replacement_candidates",
            "source_native_lineage_with_immutable_revision_tree_and_blob_evidence",
            "legacy_25_root_split_root_and_repo_family_disjointness",
            "language_and_task_stratum_bindings",
            "pre_execution_seal_readiness_attestations",
        ])

    body = {
        "stage": STAGE,
        "record_type": "stage12576_legacy_metrics_and_sealed_replacement_readiness_atlas_v1",
        "decision": "blocked_readiness_atlas" if blockers else "readiness_atlas_complete_deny_only",
        "source_stages": [
            "stage12574_guarded_eight_root_historical_lineage_acquisition_preflight",
            "stage12575_provenance_only_protected_root_quarantine_proposal",
        ],
        "source_file_sha256": {
            "stage12574": PINNED_STAGE12574_FILE_SHA256 if source12574_file_sha256 == PINNED_STAGE12574_FILE_SHA256 else None,
            "stage12575_corrected": PINNED_STAGE12575_FILE_SHA256 if source12575_file_sha256 == PINNED_STAGE12575_FILE_SHA256 else None,
        },
        "source_summary_record_sha256": {
            "stage12574": PINNED_STAGE12574_SUMMARY_RECORD_SHA256,
            "stage12575_corrected": PINNED_STAGE12575_SUMMARY_RECORD_SHA256,
        },
        "structured_summary_spine_file_sha256": {
            name: spine_file_sha256.get(name) if spine_file_sha256.get(name) == expected[1] else None
            for name, expected in sorted(SPINE_SOURCES.items())
        },
        "canonical_root_count": 25 if not fatal else 0,
        "canonical_root_set_sha256": CANONICAL_ROOT_SET_SHA256 if not fatal else None,
        "legacy_metrics_status": (
            "canonical_reference_pinned" if legacy is not None
            else "missing_no_values_invented"
        ),
        "legacy_metrics_reference": legacy.get("metrics_artifact_reference") if legacy else None,
        "legacy_metrics_file_sha256": legacy.get("metrics_file_sha256") if legacy else None,
        "legacy_metric_payload_sha256": legacy.get("metric_payload_sha256") if legacy else None,
        "legacy_metrics_source_revision_sha256": legacy.get("source_revision_sha256") if legacy else None,
        "legacy_metrics_record_sha256": legacy.get("metrics_record_sha256") if legacy else None,
        "legacy_metrics_candidate_record_count": len(legacy_records),
        "legacy_metrics_claim_preserved": False,
        "required_replacement_root_count": 8,
        "prospective_replacement_candidate_count": len(rows),
        "prospective_replacement_candidates": rows,
        "prospective_replacement_candidate_set_sha256": (
            stable_hash(sorted(row["atlas_row_sha256"] for row in rows)) if rows else None
        ),
        "replacement_source_record_count": len(candidate_records),
        "selection_outcome_or_score_conditioned": None,
        "outcome_blindness_verified": False,
        "outcome_blindness_source_artifact_reference": None,
        "replacement_manifest_sealed": len(rows) == 8 and not blockers,
        "replacement_admission_performed": False,
        "replacement_application_performed": False,
        "training_or_evaluation_performed": False,
        "protected_content_emitted": False,
        "fatal_validation_blockers": fatal,
        "blocking_reasons": blockers,
        "remaining_gaps": sorted(set(remaining_gaps)),
        "required_language_strata": sorted(PINNED_LANGUAGE_STRATA),
        "required_task_strata": sorted(PINNED_TASK_STRATA),
        "explicit_candidate_source_evaluations": _known_source_evaluations(),
        "reviewed_ineligible_spine_evidence": [
            {
                "source_stage": "stage12565_paired_pre_outcome_candidate_commitment_v2",
                "reason_codes": [
                    "policy_split_is_train_not_prospective_replacement_eval",
                    "source_native_tree_and_blob_lineage_not_attested",
                    "legacy_root_and_repo_family_disjointness_not_attested",
                    "language_and_task_strata_not_attested",
                    "replacement_pre_execution_seal_readiness_not_attested",
                ],
            }
        ],
        **ZERO,
    }
    return {**body, "summary_record_sha256": stable_hash(body)}


def build() -> dict[str, Any]:
    spine_records = [read_json(path) for path, _ in SPINE_SOURCES.values()]
    return build_atlas(
        read_json(SOURCE12574), read_json(SOURCE12575), spine_records,
        source12574_file_sha256=file_sha256(SOURCE12574),
        source12575_file_sha256=file_sha256(SOURCE12575),
        spine_file_sha256={name: file_sha256(path) for name, (path, _) in SPINE_SOURCES.items()},
    )


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> int:
    result = build()
    write_json(OUT / "legacy_metrics_and_sealed_replacement_readiness_atlas.json", result)
    write_json(OUT / "summary.json", result)
    write_json(SUMMARY, result)
    print(json.dumps({key: result[key] for key in (
        "decision", "legacy_metrics_status", "prospective_replacement_candidate_count",
        "replacement_manifest_sealed", "training_allowed", "evaluation_allowed",
    )}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
