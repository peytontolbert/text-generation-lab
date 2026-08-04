#!/usr/bin/env python3
"""Emit deny-only source-authority candidates for the protected root universe."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12570_protected_universe_authority_candidates"
OUT = ROOT / "runs/local/artifacts" / STAGE
SUMMARY = ROOT / "runs/summaries" / f"{STAGE}.json"
SEALED = ROOT / "runs/local/artifacts/stage12105_sealed_transition_candidate_atlas/sealed_transition_candidate_rows.jsonl"
REGISTRY = ROOT / "runs/local/artifacts/stage8663_source_inventory_lineage_registry/source_lineage_registry.json"
PREDECESSOR = ROOT / "runs/local/artifacts/stage12569_acyclic_attestation/protected_candidate_precondition.json"
PINNED_INPUT_FILE_SHA256 = {
    "stage12105_sealed_rows_file_sha256": "dbaf3800b987bb8607c8cd2ddb0ddcbf2011e6be9b2f4c0a41847013b86dddd2",
    "stage8663_registry_file_sha256": "98b50df0083fea7be08ccf513b361e78669a2d1be03db7948a2f0a3a90bab807",
    "stage12569_precondition_file_sha256": "4ec46724e9739ffcf94bda36f5dfe28206b00c1f9af5db7cc25777ee5cb9f303",
}
CANONICAL_PROTECTED_ROOT_HASH_SET_SHA256 = "e85fc0827bfcd9e5819fbc862f060afe35617d00b2c67b77a7effbc811541deb"
AUTHORITY_FIELDS = (
    "authorization_allowed", "admission_allowed", "training_allowed",
    "replay_allowed", "gpu_allowed", "execution_authorized", "root_credit",
    "repair_credit", "level3_credit", "strict_eval_eligible",
)
ZERO = {name: False for name in AUTHORITY_FIELDS}
DIGEST_RE = re.compile(r"^[0-9a-f]{64}\Z")
FULL_COMMIT_RE = re.compile(r"^[0-9a-f]{40}\Z")
SOURCE_ID_RE = re.compile(r"^src_[0-9a-f]{16}\Z")
REGISTRY_REQUIRED_FIELDS = {
    "source_id", "path", "kind", "content_hash_prefix", "lineage_hash",
}
ADAPTER_FIELDS = {
    "record_type", "opaque_stage12105_root_identity_sha256",
    "registered_parent_source_id", "parent_registry_link_status",
    "identity_kind", "canonical_repo", "non_git_identity",
    "observed_repo_family", "immutable_full_revision",
    "pinned_aggregate_source_sha256", "evidence_artifacts",
    "evidence_artifact_set_sha256", "evidence_row_hash_set_sha256",
    "evidence_ref", "issuer", "issuer_provenance_class",
    "same_source_proof_status", "missing_required_fields",
    "independent_issuer_anchor_sha256", "resolution_eligible",
}
CANDIDATE_ROOT_HASHES = frozenset({
    "2ea6309c6a0970ae5de8c3d78d6ce6cd07929f6e0ec587278a31c7f4ad764029",
    "b752e3c36ee91a31e43235db8b525ab289dade267a2ccdae00f9222401e0675d",
    "93e07648e29745bf7e285cdde8f3621e6c17b08b59a91db7f20e898fbf1e50a8",
    "03553beb669f93c7450affeac40ad05471c33b9241a51a0e5e0c37503a121702",
    "e0371b81cecf3bffaa690014c5c42128fd709cab588709d050bf1352a7075943",
    "812d2a52e00a239d89858870f6cae78c60983be83827b11f4dfd417b51d5c652",
    "b64d6e0b337846d863d83c172ead3f74e8a6387babcc7de5f34264464bea3d92",
    "64a107060fc0b8b13215ed928f8212a8e9219174cd66c110bddd342e9cccb649",
    "eb077237ea705fd28d3d02a11a806e36999c9618c9c207c00b673e625b547b44",
    "37b3c128e355b2c00afc9855ca3b081de60850efeb4ed6de1edb35001d5e5490",
    "39e93b6b6f9d041adef79c367984ba1514d715a88ad967b0cd393964fd2eb229",
    "1d0dc43042f95412268ba8a2f324fa04accc8ca113cc1b8507fe54fe1e0767ed",
    "d60b58fbf0b2aac9b02b70c70bb9662720e072aa6a72b26518d02338ccf661a0",
    "266d0386da88856dce68456da657e39f19363dd71b248c6a57b85f2791051002",
    "e57d8f60f423c551bc7bcb3a98fa53d0a7ceda0a69f40b535b96884cc8c3769b",
    "8e84bb1ed0b94483560333bb9055b7ca81af2eefa366dd672311d178f84bdef4",
    "714390a794486b8c4f52bd6afd48697b88c5ea6053ff420bd9910112f769dfef",
})
EVIDENCE_PATHS = {
    "stage11354": ROOT / "runs/local/artifacts/stage11354_web_executed_verifier_support_rows/web_executed_verifier_root_bundles.jsonl",
    "stage11364": ROOT / "runs/local/artifacts/stage11364_web_sourcebot_executed_support_rows/web_sourcebot_executed_support_bundles.jsonl",
    "stage11537_packets": ROOT / "runs/local/artifacts/stage11537_openclaw_extra_web_gold_support_rows/openclaw_extra_web_gold_packets.jsonl",
    "stage11537_rows": ROOT / "runs/local/artifacts/stage11537_openclaw_extra_web_gold_support_rows/openclaw_extra_web_gold_train_support_rows.jsonl",
    "stage11545": ROOT / "runs/local/artifacts/stage11545_openclaw_more_web_gold_train_rows/openclaw_more_web_gold_train_packets.jsonl",
    "stage11576": ROOT / "runs/local/artifacts/stage11576_web_fresh_source_candidate_atlas/web_fresh_source_candidate_roots.jsonl",
    "stage11811": ROOT / "runs/local/artifacts/stage11811_llm_memory_python_support_rows/llm_memory_python_support_rows.jsonl",
}


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


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    values = [json.loads(line) for line in path.read_text(
        encoding="utf-8"
    ).splitlines() if line.strip()]
    if not all(isinstance(value, dict) for value in values):
        raise ValueError(f"expected object rows: {path}")
    return values


def protected_root(row: Mapping[str, Any]) -> str:
    return str(row.get("stage12105_root_key") or row.get(
        "root_lineage_key"
    ) or row.get("root_id") or "")


def root_identity_hash(root: str) -> str:
    return stable_hash(["stage12105", root])


def registry_records(
    registry: Mapping[str, Any],
) -> tuple[dict[str, dict[str, Any]], list[str]]:
    rows = registry.get("records") if isinstance(
        registry.get("records"), list
    ) else []
    records: dict[str, dict[str, Any]] = {}
    blockers: list[str] = []
    for row in rows:
        if not isinstance(row, dict) or not REGISTRY_REQUIRED_FIELDS.issubset(row):
            blockers.append("stage8663_registry_schema_incompatible")
            continue
        source_id = str(row.get("source_id") or "")
        if not SOURCE_ID_RE.fullmatch(source_id) or source_id in records:
            blockers.append("stage8663_registry_source_id_invalid_or_duplicate")
            continue
        if (
            row.get("kind") not in {"file", "directory"}
            or DIGEST_RE.fullmatch(str(row.get("content_hash_prefix") or "")) is None
            or DIGEST_RE.fullmatch(str(row.get("lineage_hash") or "")) is None
        ):
            blockers.append("stage8663_registry_lineage_fields_invalid")
        records[source_id] = dict(row)
    if not rows:
        blockers.append("stage8663_registry_records_missing")
    return records, sorted(set(blockers))


def _artifact_descriptor(path: Path) -> dict[str, Any]:
    return {
        "path": str(path.relative_to(ROOT)),
        "file_sha256": file_sha256(path),
    }


def _adapter(
    *,
    root_hash: str,
    rows: Sequence[Mapping[str, Any]],
    artifacts: Sequence[Path],
    issuer: str,
    proof_status: str,
    git_repo_family: Any = None,
    git_head: Any = None,
    non_git_identity: Any = None,
) -> dict[str, Any]:
    descriptors = sorted(
        (_artifact_descriptor(path) for path in artifacts),
        key=lambda item: item["path"],
    )
    evidence_row_hashes = sorted({stable_hash(row) for row in rows})
    revision = str(git_head or "").lower()
    if FULL_COMMIT_RE.fullmatch(revision) is None:
        revision = None
    identity_kind = "non_git" if non_git_identity else "git"
    missing = [
        "registered_parent_source_id",
        "independent_issuer_anchor_sha256",
        "same_source_proof_independently_anchored",
    ]
    # Repo-family labels are observations, not canonical owner/repo authority.
    canonical_repo = None
    if identity_kind == "git":
        missing.append("canonical_repo")
    if revision is None:
        missing.append("immutable_full_revision")
    aggregate_projection = {
        "evidence_artifacts": descriptors,
        "evidence_row_hash_set_sha256": stable_hash(evidence_row_hashes),
        "observed_repo_family": git_repo_family,
        "immutable_full_revision": revision,
        "non_git_identity": non_git_identity,
    }
    return {
        "record_type": "stage12570_source_authority_candidate_adapter_v2",
        "opaque_stage12105_root_identity_sha256": root_hash,
        "registered_parent_source_id": None,
        "parent_registry_link_status": "no_stage8663_parent_source_id",
        "identity_kind": identity_kind,
        "canonical_repo": canonical_repo,
        "non_git_identity": non_git_identity,
        "observed_repo_family": git_repo_family,
        "immutable_full_revision": revision,
        "pinned_aggregate_source_sha256": stable_hash(aggregate_projection),
        "evidence_artifacts": descriptors,
        "evidence_artifact_set_sha256": stable_hash(descriptors),
        "evidence_row_hash_set_sha256": stable_hash(evidence_row_hashes),
        "evidence_ref": [
            f"{issuer}:file_sha256:{item['file_sha256']}" for item in descriptors
        ],
        "issuer": issuer,
        "issuer_provenance_class": "observer_artifact_producer_unanchored",
        "same_source_proof_status": proof_status,
        "missing_required_fields": sorted(missing),
        "independent_issuer_anchor_sha256": None,
        "resolution_eligible": False,
    }


def observer_adapter_records() -> list[dict[str, Any]]:
    adapters: list[dict[str, Any]] = []

    for stage in ("stage11354", "stage11364"):
        path = EVIDENCE_PATHS[stage]
        for row in read_jsonl(path):
            root = str(row.get("root_lineage_key") or "")
            root_hash = root_identity_hash(root)
            if root_hash not in CANDIDATE_ROOT_HASHES:
                continue
            adapters.append(_adapter(
                root_hash=root_hash, rows=[row], artifacts=[path], issuer=stage,
                proof_status="direct_root_field_observer_join_unanchored",
                git_repo_family=row.get("git_repo_family"),
                git_head=row.get("git_head"),
            ))

    packet_path = EVIDENCE_PATHS["stage11537_packets"]
    train_path = EVIDENCE_PATHS["stage11537_rows"]
    packets = {str(row.get("root_id") or ""): row for row in read_jsonl(packet_path)}
    stage11537_rows: dict[str, list[dict[str, Any]]] = {}
    for row in read_jsonl(train_path):
        root = str(row.get("root_lineage_key") or "")
        root_hash = root_identity_hash(root)
        if root_hash in CANDIDATE_ROOT_HASHES:
            stage11537_rows.setdefault(root_hash, []).append(row)
    for root_hash, rows in stage11537_rows.items():
        bundle = ((rows[0].get("standalone_projection_source") or {}).get("bundle") or {})
        packet = packets.get(str(bundle.get("root_id") or ""))
        joined_rows = [*rows, *([packet] if packet else [])]
        adapters.append(_adapter(
            root_hash=root_hash, rows=joined_rows,
            artifacts=[packet_path, train_path], issuer="stage11537",
            proof_status="cross_file_root_join_unanchored",
            git_repo_family=bundle.get("git_repo_family"),
            git_head=bundle.get("git_head"),
        ))

    for stage in ("stage11545", "stage11576"):
        path = EVIDENCE_PATHS[stage]
        for row in read_jsonl(path):
            root_hash = root_identity_hash(str(row.get("root_id") or ""))
            if root_hash not in CANDIDATE_ROOT_HASHES:
                continue
            adapters.append(_adapter(
                root_hash=root_hash, rows=[row], artifacts=[path], issuer=stage,
                proof_status="direct_root_field_observer_join_unanchored",
                git_repo_family=row.get("git_repo_family"),
                git_head=row.get("git_head"),
            ))

    path = EVIDENCE_PATHS["stage11811"]
    matching_rows: dict[str, list[dict[str, Any]]] = {}
    for row in read_jsonl(path):
        root_hash = root_identity_hash(str(row.get("root_lineage_key") or ""))
        if root_hash in CANDIDATE_ROOT_HASHES:
            matching_rows.setdefault(root_hash, []).append(row)
    for root_hash, rows in matching_rows.items():
        adapters.append(_adapter(
            root_hash=root_hash, rows=rows, artifacts=[path], issuer="stage11811",
            proof_status="direct_root_field_observer_join_unanchored",
            git_repo_family=None, git_head=None,
            non_git_identity=rows[0].get("source_snapshot_id"),
        ))
    return sorted(
        adapters,
        key=lambda row: row["opaque_stage12105_root_identity_sha256"],
    )


def adapter_projection(row: Mapping[str, Any]) -> dict[str, Any]:
    return {key: row.get(key) for key in sorted(ADAPTER_FIELDS)}


def validate_adapter(
    adapter: Mapping[str, Any],
    registry: Mapping[str, Mapping[str, Any]],
) -> list[str]:
    blockers: list[str] = []
    if set(adapter) != ADAPTER_FIELDS:
        blockers.append("authority_adapter_schema_not_exact")
    if DIGEST_RE.fullmatch(str(
        adapter.get("opaque_stage12105_root_identity_sha256") or ""
    )) is None:
        blockers.append("authority_adapter_root_hash_invalid")
    aggregate = {
        "evidence_artifacts": adapter.get("evidence_artifacts"),
        "evidence_row_hash_set_sha256": adapter.get("evidence_row_hash_set_sha256"),
        "observed_repo_family": adapter.get("observed_repo_family"),
        "immutable_full_revision": adapter.get("immutable_full_revision"),
        "non_git_identity": adapter.get("non_git_identity"),
    }
    if adapter.get("pinned_aggregate_source_sha256") != stable_hash(aggregate):
        blockers.append("authority_adapter_aggregate_source_hash_invalid")
    artifacts = adapter.get("evidence_artifacts")
    if (
        not isinstance(artifacts, list)
        or not artifacts
        or adapter.get("evidence_artifact_set_sha256") != stable_hash(artifacts)
        or any(
            not isinstance(item, dict)
            or set(item) != {"path", "file_sha256"}
            or DIGEST_RE.fullmatch(str(item.get("file_sha256") or "")) is None
            for item in artifacts
        )
    ):
        blockers.append("authority_adapter_evidence_artifacts_invalid")
    parent_id = adapter.get("registered_parent_source_id")
    if not (
        parent_id is None
        and adapter.get("parent_registry_link_status")
        == "no_stage8663_parent_source_id"
    ):
        if parent_id not in registry:
            blockers.append("authority_adapter_registered_parent_invalid")
    revision = adapter.get("immutable_full_revision")
    if revision is not None and FULL_COMMIT_RE.fullmatch(str(revision)) is None:
        blockers.append("authority_adapter_full_revision_invalid")
    if (
        adapter.get("canonical_repo") is not None
        or adapter.get("independent_issuer_anchor_sha256") is not None
        or adapter.get("resolution_eligible") is not False
        or not str(adapter.get("same_source_proof_status") or "").endswith(
            "_unanchored"
        )
    ):
        blockers.append("independent_issuer_anchor_unavailable_in_stage12570")
    missing = adapter.get("missing_required_fields")
    if not isinstance(missing, list) or not missing:
        blockers.append("authority_adapter_missing_field_report_absent")
    return sorted(set(blockers))


def build_candidates(
    protected_rows: Sequence[Mapping[str, Any]],
    registry: Mapping[str, Any],
    adapter_records: Sequence[Mapping[str, Any]],
    *,
    source_file_sha256: Mapping[str, str | None] | None = None,
) -> dict[str, Any]:
    root_hashes = sorted({
        root_identity_hash(root)
        for row in protected_rows
        if (root := protected_root(row))
    })
    root_hash_set = set(root_hashes)
    canonical_root_digest = stable_hash(root_hashes)
    registry_by_id, blockers = registry_records(registry)

    by_root: dict[str, list[Mapping[str, Any]]] = {}
    unknown: list[Mapping[str, Any]] = []
    for adapter in adapter_records:
        root_hash = str(
            adapter.get("opaque_stage12105_root_identity_sha256") or ""
        )
        if root_hash not in root_hash_set:
            unknown.append(adapter)
        else:
            by_root.setdefault(root_hash, []).append(adapter)

    mapping_rows: list[dict[str, Any]] = []
    known_adapter_count = 0
    duplicate_adapter_count = 0
    invalid_adapter_count = 0
    for root_hash in root_hashes:
        supplied = by_root.get(root_hash, [])
        known_adapter_count += len(supplied)
        duplicate_adapter_count += max(0, len(supplied) - 1)
        row_blockers: list[str] = []
        projected_adapter = None
        if supplied:
            validations = [
                validate_adapter(item, registry_by_id) for item in supplied
            ]
            invalid_adapter_count += sum(bool(reasons) for reasons in validations)
            row_blockers.extend(
                reason for reasons in validations for reason in reasons
            )
            if len(supplied) > 1:
                row_blockers.append("duplicate_authority_adapter_for_root")
            status = "candidate"
            projected_adapter = adapter_projection(supplied[0])
            row_blockers.extend([
                "independent_issuer_binding_not_anchored",
                "required_authority_fields_missing",
            ])
        else:
            status = "unresolved"
            row_blockers.append("source_authority_candidate_missing")
        body = {
            "opaque_stage12105_root_identity_sha256": root_hash,
            "mapping_status": status,
            "authority_adapter_record": projected_adapter,
            "authority_adapter_record_count": len(supplied),
            "blocking_reasons": sorted(set(row_blockers)),
            **ZERO,
        }
        mapping_rows.append({
            **body, "mapping_row_sha256": stable_hash(body)
        })

    resolved_count = 0
    evidence_candidate_count = sum(
        row["mapping_status"] == "candidate" for row in mapping_rows
    )
    unresolved_count = sum(
        row["mapping_status"] == "unresolved" for row in mapping_rows
    )
    unknown_hashes = sorted(
        stable_hash(adapter_projection(item)) for item in unknown
    )
    pins = dict(source_file_sha256 or {})
    reconciled = (
        len(adapter_records) == known_adapter_count + len(unknown)
    )
    if len(root_hashes) != 25:
        blockers.append("canonical_protected_root_count_changed")
    if canonical_root_digest != CANONICAL_PROTECTED_ROOT_HASH_SET_SHA256:
        blockers.append("canonical_protected_root_hash_set_changed")
    if pins and pins != PINNED_INPUT_FILE_SHA256:
        blockers.append("pinned_input_file_hash_mismatch")
    if unknown:
        blockers.append("unknown_authority_adapter_root_hash")
    if not reconciled:
        blockers.append("authority_adapter_count_reconciliation_failed")
    if duplicate_adapter_count:
        blockers.append("duplicate_authority_adapter_records")
    if invalid_adapter_count:
        blockers.append("invalid_authority_adapter_records")
    blockers.extend([
        "independent_issuer_authority_not_anchored",
        "protected_universe_not_fully_resolved",
    ])

    mapping_rows.sort(
        key=lambda row: row["opaque_stage12105_root_identity_sha256"]
    )
    body = {
        "stage": STAGE,
        "record_type": "stage12570_protected_universe_authority_candidates_v2",
        "authority_adapter_schema": {
            "record_type": "stage12570_source_authority_candidate_adapter_v2",
            "fields": sorted(ADAPTER_FIELDS),
            "stage8663_mutated": False,
            "resolution_requires_independently_anchored_issuer_binding": True,
        },
        "digest_definitions": {
            "canonical_protected_root_hash_set_sha256":
                "sha256(canonical_json(sorted(opaque_stage12105_root_identity_sha256)))",
            "authority_adapter_record_set_sha256":
                "sha256(canonical_json(sorted(sha256(canonical_adapter_projection))))",
            "mapping_row_set_sha256":
                "sha256(canonical_json(sorted(mapping_row_sha256)))",
            "unknown_adapter_record_hash_set_sha256":
                "sha256(canonical_json(sorted(sha256(canonical_adapter_projection))))",
        },
        "hash_only_protected_identity": True,
        "protected_content_emitted": False,
        "canonical_protected_root_count": len(root_hashes),
        "canonical_protected_root_hash_set_sha256": canonical_root_digest,
        "mapping_row_count": len(mapping_rows),
        "evidence_candidate_count": evidence_candidate_count,
        "resolved_count": resolved_count,
        "unresolved_count": unresolved_count,
        "mapping_status_count_integrity_valid": (
            len(mapping_rows)
            == resolved_count + evidence_candidate_count + unresolved_count
        ),
        "authority_adapter_input_record_count": len(adapter_records),
        "known_authority_adapter_record_count": known_adapter_count,
        "unknown_authority_adapter_record_count": len(unknown),
        "duplicate_authority_adapter_record_count": duplicate_adapter_count,
        "invalid_authority_adapter_record_count": invalid_adapter_count,
        "authority_adapter_count_reconciliation_valid": reconciled,
        "unknown_adapter_record_hash_set_sha256": stable_hash(unknown_hashes),
        "authority_adapter_record_set_sha256": stable_hash(sorted(
            stable_hash(adapter_projection(item)) for item in adapter_records
        )),
        "mapping_row_set_sha256": stable_hash(sorted(
            row["mapping_row_sha256"] for row in mapping_rows
        )),
        "mapping_rows": mapping_rows,
        "source_file_sha256": dict(sorted(pins.items())),
        "blocking_reasons": sorted(set(blockers)),
        **ZERO,
    }
    return {**body, "summary_record_sha256": stable_hash(body)}


def build() -> dict[str, Any]:
    registry = read_json(REGISTRY)
    source_hashes = {
        "stage12105_sealed_rows_file_sha256": file_sha256(SEALED),
        "stage8663_registry_file_sha256": file_sha256(REGISTRY),
        "stage12569_precondition_file_sha256": file_sha256(PREDECESSOR),
    }
    return build_candidates(
        read_jsonl(SEALED), registry, observer_adapter_records(),
        source_file_sha256=source_hashes,
    )


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def main() -> int:
    result = build()
    write_json(OUT / "protected_universe_authority_candidates.json", result)
    write_json(OUT / "summary.json", result)
    write_json(SUMMARY, result)
    print(json.dumps({key: result[key] for key in (
        "mapping_row_count", "evidence_candidate_count", "resolved_count",
        "unresolved_count", "canonical_protected_root_hash_set_sha256",
        "unknown_authority_adapter_record_count", "authorization_allowed",
        "training_allowed", "replay_allowed", "gpu_allowed", "blocking_reasons",
    )}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
