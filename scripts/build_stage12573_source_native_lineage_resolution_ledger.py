#!/usr/bin/env python3
"""Build the deny-only source-native lineage resolution ledger from Stage12572 v5."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12573_source_native_lineage_resolution_ledger"
OUT = ROOT / "runs/local/artifacts" / STAGE
SUMMARY = ROOT / "runs/summaries" / f"{STAGE}.json"
SOURCE = (
    ROOT
    / "runs/local/artifacts/stage12572_source_native_protected_root_preimage_reconstruction_census"
    / "source_native_preimage_reconstruction_census.json"
)
PINNED_STAGE12572_FILE_SHA256 = (
    "1440ac769b188808ff7f29c138503e86ccbce1796e2a72dab115a1e99498541c"
)
PINNED_STAGE12572_SUMMARY_RECORD_SHA256 = (
    "31c0539a69d3c8a937bb36ab22827ca62441f51739bbe6407cc16e71f1986d10"
)
CANONICAL_ROOT_SET_SHA256 = (
    "e85fc0827bfcd9e5819fbc862f060afe35617d00b2c67b77a7effbc811541deb"
)
VERIFIED_ROOT_SET_SHA256 = (
    "d7866db7e54ccb58a4146275c25e31dd68100496823747e8d0870f64d99b5b65"
)
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
STAGE12572_FIELDS = {
    "stage", "record_type", "decision", "canonical_protected_root_count",
    "canonical_protected_root_hash_set_sha256",
    "immutable_source_bridge_root_set_sha256",
    "committed_root_identity_verified_count", "immutable_source_bridge_count",
    "immutable_source_bridge_kind_counts", "historical_binding_missing_count",
    "independently_authorized_count", "invalid_observer_record_count",
    "census_rows", "census_row_set_sha256", "source_file_sha256",
    "evidence_file_sha256", "protected_content_emitted",
    "runtime_plaintext_preimages_read", "outcomes_gold_target_or_verifier_read",
    "blocking_reasons", "non_authorizing_conditions", "summary_record_sha256",
    *AUTHORITY_FIELDS,
}
STAGE12572_ROW_FIELDS = {
    "opaque_stage12105_root_identity_sha256",
    "committed_root_identity_verified", "immutable_source_bridge",
    "proof_status", "bridge_kind", "source_join_sha256", "census_row_sha256",
    *AUTHORITY_FIELDS,
}
FORBIDDEN_KEYS = {
    "stage12105_root_key", "gold", "gold_label", "gold_patch", "outcome",
    "reward", "target", "target_label", "target_text", "verifier_output",
    "verifier_outcome", "verifier_result", "protected_content",
}
EXPECTED_KIND_COUNTS = {
    "full_revision_prior_root": 5,
    "stage11576_deterministic_constructor": 11,
    "stage11811_fixed_git_snapshot": 1,
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


def protected_content_reasons(value: Any, location: str = "$") -> list[str]:
    reasons: list[str] = []
    if isinstance(value, Mapping):
        for key, child in value.items():
            normalized = str(key).lower()
            if normalized in FORBIDDEN_KEYS:
                reasons.append(f"protected_or_forbidden_field:{location}.{normalized}")
            reasons.extend(protected_content_reasons(child, f"{location}.{normalized}"))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            reasons.extend(protected_content_reasons(child, f"{location}[{index}]"))
    return sorted(set(reasons))


def _digest(value: Any) -> bool:
    return isinstance(value, str) and DIGEST_RE.fullmatch(value) is not None


def _validated_pin(value: Any, expected: str) -> str | None:
    return expected if _digest(value) and value == expected else None


def _stage12572_body(source: Mapping[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in source.items() if key != "summary_record_sha256"}


def build_ledger(
    source: Mapping[str, Any], *, source_file_sha256: str | None
) -> dict[str, Any]:
    blockers: list[str] = []
    validated_source_file_pin = _validated_pin(
        source_file_sha256, PINNED_STAGE12572_FILE_SHA256
    )
    validated_source_summary_pin = _validated_pin(
        source.get("summary_record_sha256"),
        PINNED_STAGE12572_SUMMARY_RECORD_SHA256,
    )
    protected_reasons = protected_content_reasons(source)
    if protected_reasons:
        blockers.append("protected_content_detected")
    if validated_source_file_pin is None:
        blockers.append("stage12572_file_pin_mismatch")
    if set(source) != STAGE12572_FIELDS:
        blockers.append("stage12572_schema_not_exact")
    if (
        source.get("stage")
        != "stage12572_source_native_protected_root_preimage_reconstruction_census"
        or source.get("record_type")
        != "stage12572_source_native_committed_root_identity_census_v5"
    ):
        blockers.append("stage12572_v5_identity_mismatch")
    if (
        validated_source_summary_pin is None
        or stable_hash(_stage12572_body(source))
        != PINNED_STAGE12572_SUMMARY_RECORD_SHA256
    ):
        blockers.append("stage12572_summary_digest_mismatch")
    if source.get("decision") != "verified" or source.get("blocking_reasons") != []:
        blockers.append("stage12572_blocked_or_unaccepted")
    if source.get("non_authorizing_conditions") != [
        "independent_source_authority_absent"
    ]:
        blockers.append("stage12572_non_authorizing_condition_mismatch")
    if (
        source.get("protected_content_emitted") is not False
        or source.get("runtime_plaintext_preimages_read") is not False
        or source.get("outcomes_gold_target_or_verifier_read") is not False
    ):
        blockers.append("stage12572_protected_content_boundary_violated")
    if any(source.get(field) is not False for field in AUTHORITY_FIELDS):
        blockers.append("stage12572_deny_boundary_violated")

    rows_value = source.get("census_rows")
    rows = rows_value if isinstance(rows_value, list) else []
    roots: list[str] = []
    verified_roots: list[str] = []
    verified = 0
    unresolved = 0
    candidate_rows: list[dict[str, Any]] = []
    census_hashes: list[str] = []
    for row in rows:
        if not isinstance(row, Mapping) or set(row) != STAGE12572_ROW_FIELDS:
            blockers.append("stage12572_row_schema_not_exact")
            continue
        row_body = {key: value for key, value in row.items() if key != "census_row_sha256"}
        root = row.get("opaque_stage12105_root_identity_sha256")
        census_hash = row.get("census_row_sha256")
        source_join = row.get("source_join_sha256")
        if not _digest(root) or not _digest(census_hash):
            blockers.append("stage12572_row_digest_invalid")
            continue
        if stable_hash(row_body) != census_hash:
            blockers.append("stage12572_census_row_digest_mismatch")
        if row.get("committed_root_identity_verified") is not True:
            blockers.append("stage12572_committed_root_not_verified")
        if any(row.get(field) is not False for field in AUTHORITY_FIELDS):
            blockers.append("stage12572_row_deny_boundary_violated")
        roots.append(root)
        census_hashes.append(census_hash)

        bridge = row.get("immutable_source_bridge")
        if bridge is True:
            if (
                row.get("proof_status") != "immutable_source_bridge_verified_unauthed"
                or row.get("bridge_kind") not in EXPECTED_KIND_COUNTS
                or not _digest(source_join)
            ):
                blockers.append("stage12572_verified_bridge_shape_invalid")
                continue
            status = "source_native_lineage_verified"
            lineage_hash = source_join
            verified += 1
            verified_roots.append(root)
        elif bridge is False:
            if (
                row.get("proof_status")
                != "preimage_commitment_historical_binding_missing"
                or row.get("bridge_kind") is not None
                or source_join is not None
            ):
                blockers.append("stage12572_unresolved_bridge_shape_invalid")
                continue
            status = "unresolved_historical_binding"
            lineage_hash = None
            unresolved += 1
        else:
            blockers.append("stage12572_bridge_boolean_invalid")
            continue
        ledger_body = {
            "opaque_root_identity_sha256": root,
            "stage12572_census_row_sha256": census_hash,
            "resolution_basis_sha256": census_hash,
            "source_native_lineage_evidence_sha256": lineage_hash,
            "resolution_status": status,
            **ZERO,
        }
        candidate_rows.append({**ledger_body, "ledger_row_sha256": stable_hash(ledger_body)})

    roots_sorted = sorted(roots)
    verified_roots_sorted = sorted(verified_roots)
    if len(rows) != 25 or len(roots) != 25 or len(set(roots)) != 25 or roots != roots_sorted:
        blockers.append("stage12572_roots_missing_extra_duplicate_or_unsorted")
    if stable_hash(roots_sorted) != CANONICAL_ROOT_SET_SHA256:
        blockers.append("canonical_root_set_digest_mismatch")
    if stable_hash(verified_roots_sorted) != VERIFIED_ROOT_SET_SHA256:
        blockers.append("verified_root_set_digest_or_bridge_split_mismatch")
    if (
        source.get("canonical_protected_root_count") != 25
        or source.get("canonical_protected_root_hash_set_sha256") != CANONICAL_ROOT_SET_SHA256
        or source.get("committed_root_identity_verified_count") != 25
        or source.get("immutable_source_bridge_count") != 17
        or source.get("historical_binding_missing_count") != 8
        or source.get("independently_authorized_count") != 0
        or source.get("invalid_observer_record_count") != 0
        or source.get("immutable_source_bridge_root_set_sha256") != VERIFIED_ROOT_SET_SHA256
        or source.get("immutable_source_bridge_kind_counts") != EXPECTED_KIND_COUNTS
        or source.get("census_row_set_sha256") != stable_hash(sorted(census_hashes))
    ):
        blockers.append("stage12572_count_digest_or_partition_mismatch")
    if len(candidate_rows) != 25 or verified != 17 or unresolved != 8:
        blockers.append("stage12573_expected_partition_not_reproduced")

    blockers = sorted(set(blockers))
    ledger_rows = [] if blockers else candidate_rows
    body = {
        "stage": STAGE,
        "record_type": "stage12573_source_native_lineage_resolution_ledger_v1",
        "decision": "blocked" if blockers else "verified_deny_only",
        "source_stage": "stage12572_source_native_protected_root_preimage_reconstruction_census",
        "source_record_type": "stage12572_source_native_committed_root_identity_census_v5",
        "source_file_sha256": validated_source_file_pin,
        "source_summary_record_sha256": validated_source_summary_pin,
        "canonical_root_count": 25 if not blockers else 0,
        "canonical_root_set_sha256": CANONICAL_ROOT_SET_SHA256 if not blockers else None,
        "mapping_row_count": len(ledger_rows),
        "source_native_lineage_verified_count": 17 if not blockers else 0,
        "unresolved_historical_binding_count": 8 if not blockers else 0,
        "independently_authorized_count": 0,
        "mapping_rows": ledger_rows,
        "mapping_row_set_sha256": (
            stable_hash(sorted(row["ledger_row_sha256"] for row in ledger_rows))
            if not blockers else None
        ),
        "protected_content_emitted": False,
        "blocking_reasons": blockers,
        "non_authorizing_conditions": [
            "stage12572_independent_source_authority_absent"
        ],
        **ZERO,
    }
    return {**body, "summary_record_sha256": stable_hash(body)}


def build() -> dict[str, Any]:
    return build_ledger(read_json(SOURCE), source_file_sha256=file_sha256(SOURCE))


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> int:
    result = build()
    write_json(OUT / "source_native_lineage_resolution_ledger.json", result)
    write_json(OUT / "summary.json", result)
    write_json(SUMMARY, result)
    print(json.dumps({key: result[key] for key in (
        "mapping_row_count", "source_native_lineage_verified_count",
        "unresolved_historical_binding_count", "independently_authorized_count",
    )}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
