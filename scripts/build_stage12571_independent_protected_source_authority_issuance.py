#!/usr/bin/env python3
"""Build the fail-closed protected-source authority issuance worklist."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12571_independent_protected_source_authority_issuance"
OUT = ROOT / "runs/local/artifacts" / STAGE
SUMMARY = ROOT / "runs/summaries" / f"{STAGE}.json"
SOURCES = {
    "stage12565_commitment": ROOT / "runs/local/artifacts/stage12565_paired_pre_outcome_candidate_commitment_v2/paired_candidate_commitment_v2.json",
    "stage12568_adapter": ROOT / "runs/local/artifacts/stage12568_open_swe_source_lineage_adapter/source_lineage_reference_adapter.json",
    "stage12569_precondition": ROOT / "runs/local/artifacts/stage12569_acyclic_attestation/protected_candidate_precondition.json",
    "stage12570_candidates": ROOT / "runs/local/artifacts/stage12570_protected_universe_authority_candidates/protected_universe_authority_candidates.json",
    "stage8663_registry": ROOT / "runs/local/artifacts/stage8663_source_inventory_lineage_registry/source_lineage_registry.json",
}
PINNED_SOURCE_FILE_SHA256 = {
    "stage12565_commitment": "f90d9a972f4e2029c97344f8ed17fa9d2f1ce8f143651901f7d21a4d3bd53e1a",
    "stage12568_adapter": "a83a025e54283e82018c3762554c14d5ed5c74767201f0d8f3a84a59f70b519b",
    "stage12569_precondition": "4ec46724e9739ffcf94bda36f5dfe28206b00c1f9af5db7cc25777ee5cb9f303",
    "stage12570_candidates": "9dcc17dca0d0b90bbeaf2e190012c96c04946365a59ee072dceb8e977da844fe",
    "stage8663_registry": "98b50df0083fea7be08ccf513b361e78669a2d1be03db7948a2f0a3a90bab807",
}
CANONICAL_PROTECTED_ROOT_HASH_SET_SHA256 = "e85fc0827bfcd9e5819fbc862f060afe35617d00b2c67b77a7effbc811541deb"
CANONICAL_STAGE8663_OBJECT_SHA256 = "7b7fdabf1000f1debbf82806543a711916abf05a4e689b87d4f7dfbb51079074"
AUTHORITY_FIELDS = (
    "authorization_allowed", "admission_allowed", "training_allowed",
    "replay_allowed", "gpu_allowed", "execution_authorized", "root_credit",
    "repair_credit", "level3_credit", "strict_eval_eligible",
)
ZERO = {field: False for field in AUTHORITY_FIELDS}
DIGEST_RE = re.compile(r"^[0-9a-f]{64}\Z")
COMMIT_RE = re.compile(r"^[0-9a-f]{40}\Z")
SOURCE_ID_RE = re.compile(r"^src_[0-9a-f]{16}\Z")
REPO_RE = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+\Z")
IMMUTABLE_URI_RE = re.compile(r"^(?:https?|urn):\S*(?:sha256|digest|commit|snapshot)\S*$", re.I)

# No issuer is trusted by this preflight. Authority must arrive from an
# upstream stage that predates this stage and can privately recompute the
# source-native bridge from the Stage12105 root preimage.
TRUSTED_ISSUER_ANCHORS: dict[str, dict[str, str]] = {}
ISSUANCE_FIELDS = {
    "record_type", "opaque_stage12105_root_identity_sha256", "issued_source_id",
    "source_id_assignment_attestation_sha256", "identity_kind", "canonical_repo",
    "non_git_identity", "immutable_revision", "registry_extension_record",
    "independent_evidence_chain", "issuer_id", "issuer_anchor_sha256",
}
EXTENSION_FIELDS = {
    "source_id", "path", "kind", "content_hash_prefix", "lineage_hash",
    "canonical_repo", "immutable_revision", "issuer_id",
}
CHAIN_ROLES = {
    "issuer_authority_attestation", "same_source_binding_manifest",
    "immutable_source_snapshot",
}
PROOF_SLOTS = (
    "preexisting_independent_upstream_identity",
    "pretrusted_independent_issuer_anchor",
    "independent_issuer_assigned_source_id",
    "issuer_signed_canonical_identity",
    "deterministic_source_native_bridge_from_stage12105_root_preimage",
    "immutable_canonical_repo_or_non_git_identity",
    "immutable_full_revision",
    "same_source_binding_manifest",
    "immutable_source_snapshot_digest",
    "registry_extension_record",
)


def stable_hash(value: Any) -> str:
    return hashlib.sha256(json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    ).encode()).hexdigest()


def file_sha256(path: Path) -> str | None:
    if not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected object: {path}")
    return value


def _is_digest(value: Any) -> bool:
    return DIGEST_RE.fullmatch(str(value or "")) is not None


def _immutable_uri(value: Any) -> bool:
    return IMMUTABLE_URI_RE.fullmatch(str(value or "")) is not None


def _forbidden_derived_source_ids(root_hash: str) -> set[str]:
    encodings = (root_hash, stable_hash(root_hash), stable_hash([root_hash]))
    return {f"src_{value[:16]}" for value in encodings}


def validate_issuance(
    record: Mapping[str, Any],
    root_hashes: set[str],
    existing_source_ids: set[str],
    trust_anchors: Mapping[str, Mapping[str, str]],
) -> list[str]:
    blockers: list[str] = []
    if set(record) != ISSUANCE_FIELDS:
        blockers.append("issuance_schema_not_exact")
    root_hash = str(record.get("opaque_stage12105_root_identity_sha256") or "")
    if root_hash not in root_hashes:
        blockers.append("unknown_protected_root")
    source_id = str(record.get("issued_source_id") or "")
    if SOURCE_ID_RE.fullmatch(source_id) is None:
        blockers.append("issued_source_id_invalid")
    if source_id in existing_source_ids:
        blockers.append("issued_source_id_already_registered")
    if source_id in _forbidden_derived_source_ids(root_hash):
        blockers.append("deterministic_root_derived_source_id_forbidden")
    if not _is_digest(record.get("source_id_assignment_attestation_sha256")):
        blockers.append("independent_source_id_assignment_attestation_missing")

    issuer_id = str(record.get("issuer_id") or "")
    if issuer_id in {STAGE, "stage12571"}:
        blockers.append("stage12571_self_issuance_forbidden")
    anchor = trust_anchors.get(issuer_id)
    if not anchor:
        blockers.append("issuer_not_pretrusted")
    elif (
        record.get("issuer_anchor_sha256") != anchor.get("anchor_sha256")
        or not _immutable_uri(anchor.get("immutable_uri"))
        or anchor.get("authority_scope") != "protected_source_registry_extension"
    ):
        blockers.append("issuer_anchor_not_exact_or_immutable")

    kind = record.get("identity_kind")
    repo = record.get("canonical_repo")
    non_git = record.get("non_git_identity")
    revision = record.get("immutable_revision")
    if kind == "git":
        if REPO_RE.fullmatch(str(repo or "")) is None or non_git is not None:
            blockers.append("canonical_git_identity_invalid")
        if COMMIT_RE.fullmatch(str(revision or "")) is None:
            blockers.append("immutable_git_revision_invalid")
    elif kind == "non_git":
        if repo is not None or not _is_digest(non_git) or not _is_digest(revision):
            blockers.append("immutable_non_git_identity_invalid")
    else:
        blockers.append("identity_kind_invalid")

    extension = record.get("registry_extension_record")
    if not isinstance(extension, dict) or set(extension) != EXTENSION_FIELDS:
        blockers.append("registry_extension_schema_not_exact")
    elif (
        extension.get("source_id") != source_id
        or extension.get("canonical_repo") != repo
        or extension.get("immutable_revision") != revision
        or extension.get("issuer_id") != issuer_id
        or extension.get("kind") not in {"file", "directory"}
        or not _immutable_uri(extension.get("path"))
        or not _is_digest(extension.get("content_hash_prefix"))
        or not _is_digest(extension.get("lineage_hash"))
    ):
        blockers.append("registry_extension_identity_or_lineage_invalid")

    chain = record.get("independent_evidence_chain")
    if not isinstance(chain, list) or len(chain) != len(CHAIN_ROLES):
        blockers.append("independent_evidence_chain_incomplete")
    else:
        roles: set[str] = set()
        uris: set[str] = set()
        hashes: set[str] = set()
        for item in chain:
            if not isinstance(item, dict) or set(item) != {"role", "immutable_uri", "sha256"}:
                blockers.append("independent_evidence_item_schema_invalid")
                continue
            roles.add(str(item.get("role") or ""))
            uris.add(str(item.get("immutable_uri") or ""))
            hashes.add(str(item.get("sha256") or ""))
            if not _immutable_uri(item.get("immutable_uri")) or not _is_digest(item.get("sha256")):
                blockers.append("independent_evidence_item_not_immutable")
        if roles != CHAIN_ROLES:
            blockers.append("independent_evidence_roles_incomplete")
        if len(uris) != len(CHAIN_ROLES) or len(hashes) != len(CHAIN_ROLES):
            blockers.append("artifact_copresence_or_self_hash_chain_forbidden")
        candidate_hashes = {
            stable_hash(record), stable_hash(extension) if isinstance(extension, dict) else "",
            root_hash,
        }
        if hashes & candidate_hashes:
            blockers.append("self_hash_not_authority")
    blockers.extend([
        "copied_root_field_not_source_native_bridge",
        "independent_upstream_identity_not_materialized",
        "repo_revision_equality_not_authority",
        "source_native_root_preimage_bridge_not_materialized",
    ])
    return sorted(set(blockers))


def _work_item(stage12570_row: Mapping[str, Any]) -> dict[str, Any]:
    adapter = stage12570_row.get("authority_adapter_record")
    observed = adapter if isinstance(adapter, dict) else {}
    missing = list(PROOF_SLOTS)
    return {
        "record_type": "stage12571_independent_authority_issuance_work_item_v1",
        "opaque_stage12105_root_identity_sha256": stage12570_row.get(
            "opaque_stage12105_root_identity_sha256"
        ),
        "stage12570_mapping_status": stage12570_row.get("mapping_status"),
        "observer_candidate_issuer": observed.get("issuer"),
        "observer_candidate_record_sha256": (
            stable_hash(observed) if observed else None
        ),
        "missing_proof_slots": missing,
        "acceptable_evidence_policy": (
            "pretrusted independent issuer plus three distinct immutable external "
            "artifacts binding issuer authority, same source, and source snapshot"
        ),
        "forbidden_authority_shortcuts": [
            "artifact_copresence", "copied_root_field", "cross_file_observer_join",
            "current_mutable_checkout", "deterministic_source_id",
            "label_derived_repo_or_commit", "repo_revision_equality", "self_hash",
        ],
        "issuance_status": "awaiting_independent_evidence",
        **ZERO,
    }


def build_registry_extension_candidate(
    stage12570: Mapping[str, Any],
    registry: Mapping[str, Any],
    issuance_records: Sequence[Mapping[str, Any]],
    *,
    source_file_sha256: Mapping[str, str | None] | None = None,
) -> dict[str, Any]:
    anchors = TRUSTED_ISSUER_ANCHORS
    predecessor_rows = stage12570.get("mapping_rows")
    rows = predecessor_rows if isinstance(predecessor_rows, list) else []
    root_hashes = {
        str(row.get("opaque_stage12105_root_identity_sha256") or "")
        for row in rows if isinstance(row, dict)
    }
    existing_records = registry.get("records")
    registry_rows = existing_records if isinstance(existing_records, list) else []
    existing_ids = {
        str(row.get("source_id")) for row in registry_rows if isinstance(row, dict)
    }
    blockers: list[str] = []
    if stable_hash(registry) != CANONICAL_STAGE8663_OBJECT_SHA256:
        blockers.append("stage8663_registry_mutation_detected")
    if len(rows) != 25 or len(root_hashes) != 25:
        blockers.append("canonical_protected_root_count_changed")
    root_digest = stable_hash(sorted(root_hashes))
    if root_digest != CANONICAL_PROTECTED_ROOT_HASH_SET_SHA256:
        blockers.append("canonical_protected_root_hash_set_changed")
    if stage12570.get("canonical_protected_root_hash_set_sha256") != root_digest:
        blockers.append("stage12570_root_digest_mismatch")
    pins = dict(source_file_sha256 or {})
    if pins and pins != PINNED_SOURCE_FILE_SHA256:
        blockers.append("pinned_source_file_hash_mismatch")

    by_root: dict[str, list[Mapping[str, Any]]] = {}
    unknown_count = 0
    for record in issuance_records:
        root_hash = str(record.get("opaque_stage12105_root_identity_sha256") or "")
        if root_hash not in root_hashes:
            unknown_count += 1
        else:
            by_root.setdefault(root_hash, []).append(record)

    mapping_rows: list[dict[str, Any]] = []
    invalid_count = 0
    duplicate_count = 0
    resolved_count = 0
    for predecessor in sorted(rows, key=lambda row: row["opaque_stage12105_root_identity_sha256"]):
        root_hash = predecessor["opaque_stage12105_root_identity_sha256"]
        supplied = by_root.get(root_hash, [])
        duplicate_count += max(0, len(supplied) - 1)
        validations = [
            validate_issuance(record, root_hashes, existing_ids, anchors)
            for record in supplied
        ]
        invalid_count += sum(bool(value) for value in validations)
        # This stage has neither root preimages nor an upstream bridge verifier.
        valid = False
        resolved_count += int(valid)
        body = {
            "opaque_stage12105_root_identity_sha256": root_hash,
            "mapping_status": "resolved" if valid else "unresolved",
            "accepted_issuance_record_sha256": stable_hash(supplied[0]) if valid else None,
            "proposed_registry_extension": supplied[0]["registry_extension_record"] if valid else None,
            "issuance_record_count": len(supplied),
            "blocking_reasons": [] if valid else sorted(set(
                [reason for reasons in validations for reason in reasons]
                + (["independent_authority_issuance_missing"] if not supplied else [])
                + (["duplicate_issuance_records_for_root"] if len(supplied) > 1 else [])
                + (["source_native_root_preimage_bridge_not_materialized"] if supplied else [])
            )),
            "issuance_work_item": None if valid else _work_item(predecessor),
            **ZERO,
        }
        mapping_rows.append({**body, "mapping_row_sha256": stable_hash(body)})

    if unknown_count:
        blockers.append("unknown_issuance_record_root")
    if duplicate_count:
        blockers.append("duplicate_issuance_records")
    if invalid_count:
        blockers.append("invalid_independent_issuance_records")
    if resolved_count != 25:
        blockers.append("protected_universe_not_fully_resolved")
    if not anchors:
        blockers.append("independent_issuer_trust_registry_empty")
    unresolved_count = len(mapping_rows) - resolved_count
    worklist = [row["issuance_work_item"] for row in mapping_rows if row["issuance_work_item"]]
    body = {
        "stage": STAGE,
        "record_type": "stage12571_independent_protected_source_authority_issuance_v1",
        "decision": "issuance_worklist_emitted_no_false_resolution" if not resolved_count else "independent_issuance_records_validated",
        "hash_only_protected_identity": True,
        "protected_content_emitted": False,
        "base_registry_mutated": False,
        "registry_extension_policy": "append_only_after_independent_authority_never_self_bootstrapping",
        "source_native_bridge_policy": (
            "upstream authority must privately recompute the deterministic Stage12105 "
            "root identity from its root preimage and bind it to immutable source identity"
        ),
        "canonical_protected_root_count": len(root_hashes),
        "canonical_protected_root_hash_set_sha256": root_digest,
        "mapping_row_count": len(mapping_rows),
        "resolved_count": resolved_count,
        "unresolved_count": unresolved_count,
        "issuance_worklist_count": len(worklist),
        "issuance_record_input_count": len(issuance_records),
        "known_issuance_record_count": len(issuance_records) - unknown_count,
        "unknown_issuance_record_count": unknown_count,
        "invalid_issuance_record_count": invalid_count,
        "duplicate_issuance_record_count": duplicate_count,
        "issuance_record_count_reconciliation_valid": (
            len(issuance_records) == sum(len(value) for value in by_root.values()) + unknown_count
        ),
        "trusted_issuer_anchor_count": len(anchors),
        "mapping_status_count_integrity_valid": len(mapping_rows) == resolved_count + unresolved_count,
        "mapping_row_set_sha256": stable_hash(sorted(row["mapping_row_sha256"] for row in mapping_rows)),
        "issuance_worklist_set_sha256": stable_hash(sorted(stable_hash(row) for row in worklist)),
        "unknown_issuance_record_set_sha256": stable_hash(sorted(
            stable_hash(record) for record in issuance_records
            if str(record.get("opaque_stage12105_root_identity_sha256") or "") not in root_hashes
        )),
        "mapping_rows": mapping_rows,
        "issuance_worklist": worklist,
        "source_file_sha256": dict(sorted(pins.items())),
        "blocking_reasons": sorted(set(blockers)),
        **ZERO,
    }
    return {**body, "summary_record_sha256": stable_hash(body)}


def build() -> dict[str, Any]:
    source_hashes = {name: file_sha256(path) for name, path in SOURCES.items()}
    return build_registry_extension_candidate(
        read_json(SOURCES["stage12570_candidates"]),
        read_json(SOURCES["stage8663_registry"]),
        [],
        source_file_sha256=source_hashes,
    )


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> int:
    result = build()
    write_json(OUT / "independent_protected_source_authority_issuance.json", result)
    write_json(OUT / "issuance_worklist.json", {
        "stage": STAGE,
        "canonical_protected_root_hash_set_sha256": result["canonical_protected_root_hash_set_sha256"],
        "issuance_worklist_count": result["issuance_worklist_count"],
        "issuance_worklist_set_sha256": result["issuance_worklist_set_sha256"],
        "issuance_worklist": result["issuance_worklist"],
        **ZERO,
    })
    write_json(OUT / "summary.json", result)
    write_json(SUMMARY, result)
    print(json.dumps({key: result[key] for key in (
        "decision", "canonical_protected_root_count", "resolved_count",
        "unresolved_count", "issuance_worklist_count", "unknown_issuance_record_count",
        "authorization_allowed", "training_allowed", "replay_allowed", "gpu_allowed",
        "blocking_reasons",
    )}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
