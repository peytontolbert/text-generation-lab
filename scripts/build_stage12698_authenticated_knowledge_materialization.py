#!/usr/bin/env python3
"""Materialize authenticated Stage12695 knowledge candidates in memory only."""

from __future__ import annotations

import argparse
import ctypes
import errno
import hashlib
import importlib.util
import json
import os
import re
import secrets
import stat
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REPOSITORY_ROOT = Path("/arxiv/repositories")
DEPENDENCIES = {
    "stage12695": (
        "build_stage12695_source_backed_repository_metadata_and_observed_verifier_summaries.py",
        "06931a91ec84645e3e690fa4b667e57b2f5513be3066e4e55de22155b2ecde7b",
    ),
    "stage12696": (
        "build_stage12696_authenticated_git_declaration_evidence_packages.py",
        "cc25577df07ff777de2e456f0bf11d864f99f3b498c3612436510a94332505c5",
    ),
    "stage12697": (
        "build_stage12697_authenticated_observed_verifier_join_packages.py",
        "dc5a910db209620304e4026523a5a60b257b5bcf177a1364b2c3d1c9da51de68",
    ),
}
AUTHORITY = {
    "implementation_ready": False,
    "level_3_materialized": False,
    "model_execution_authorized": False,
    "replay_trustworthy": False,
    "sealed_eval_admitted": False,
    "strict_eval_admitted": False,
    "training_admitted": False,
    "training_allowed": False,
    "training_run_allowed": False,
}
PRODUCTION_SOURCE_COUNTS = {
    "authenticated_git_heads": 479,
    "authenticated_declaration_rows": 1692,
    "authenticated_verifier_joins": 3,
}
EXPECTED_SOURCE_COUNTS = dict(PRODUCTION_SOURCE_COUNTS)
EXPECTED_RETAINED_METADATA_COUNTS = {
    "repository_structure": 476,
    "test_layout_convention": 476,
    "documentation_layout_convention": 476,
    "parsed_declaration_class": 172,
}
EXPECTED_RETAINED_CANDIDATE_ROWS = 1_603
EXPECTED_DUPLICATE_QUARANTINE_ROWS = 1_529
CANDIDATE_AUTHORITY_FIELDS = frozenset({
    "implementation_ready", "stage12595_allowed", "replay_trustworthy",
    "level_3_materialized", "training_admitted", "strict_eval_admitted",
    "sealed_eval_admitted",
})
EXPECTED_METADATA_FIELDS = frozenset({
    "repository_structure", "test_layout_convention",
    "documentation_layout_convention", "parsed_declaration_class",
})
_FORBIDDEN_TARGETS = frozenset({
    "", "placeholder", "<placeholder>", "__placeholder__", "<missing>",
    "missing", "<answer>", "todo", "tbd", "n/a", "...", "stub",
    "unresolved", "notimplemented", "pass", "not_implemented", "not implemented",
    "raise notimplementederror", "raise notimplementederror()",
})
_ANSWER_PREFIX = re.compile(r"^answer\s*:\s*(.*)$", re.IGNORECASE | re.DOTALL)


class Stage12698Error(RuntimeError):
    pass


RESIDUAL_PUBLICATION_TRUST_CONTRACT = {
    "hostile_same_process_code_excluded": True,
    "hostile_same_uid_concurrent_writers_excluded": True,
    "universal_atomicity_claimed": False,
}
RESERVED_AUTHORITY_FIELDS = frozenset(AUTHORITY) | frozenset({
    "stage12595_allowed", "training_eligible_rows", "publication_performed",
})
PRIVATE_RESULT_FIELDS = frozenset({
    "stage", "record_type", "candidates", "candidate_count",
    "raw_candidate_count", "duplicate_quarantine_count", "objective_counts",
    "metadata_classification_counts", "source_counts", "deduplication",
    "repository_mapping", "stage12696_package_manifest_sha256",
    "stage12697_capacity_commitment_sha256", "candidate_commitment_sha256",
    "model_example_commitment_sha256", "publication_performed",
    "training_eligible_rows", "authority",
})


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _stable(value: Any) -> str:
    return _sha(json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=True,
    ).encode("utf-8"))


def _load_dependency_from_bytes(
    name: str, path: Path, raw: bytes, expected: str,
) -> Any:
    if _sha(raw) != expected:
        raise Stage12698Error(f"dependency_digest_mismatch:{name}")
    spec = importlib.util.spec_from_file_location(f"{name}_for_stage12698", path)
    if spec is None or spec.loader is None:
        raise Stage12698Error(f"dependency_import_unavailable:{name}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    try:
        code = compile(raw, os.fspath(path), "exec", dont_inherit=True)
        exec(code, module.__dict__)
    except BaseException:
        sys.modules.pop(spec.name, None)
        raise
    return module


def _load_dependencies() -> tuple[Any, Any, Any]:
    loaded = []
    for name, (filename, expected) in DEPENDENCIES.items():
        path = Path(__file__).with_name(filename)
        raw = path.read_bytes()
        loaded.append(_load_dependency_from_bytes(name, path, raw, expected))
    return tuple(loaded)


def _raw_record(record: Mapping[str, Any]) -> bytes:
    return json.dumps(
        record, sort_keys=True, separators=(",", ":"), ensure_ascii=True,
    ).encode("utf-8")


def _expected_repository_identities(
    memberships: Mapping[str, Any],
) -> tuple[dict[tuple[str, str], str], set[str]]:
    identities: dict[tuple[str, str], str] = {}
    keys: set[str] = set()
    lanes = (
        (memberships["stage12688_catalog"].records, "head_commit_git_oid", "git_tree_oid"),
        (memberships["stage12692_catalog"].records, "revision", "tree_oid"),
    )
    for records, revision_field, tree_field in lanes:
        for record in records:
            key = record.get("repository_key_sha256")
            revision = record.get(revision_field)
            tree = record.get(tree_field)
            if not all(isinstance(value, str) and value for value in (key, revision, tree)):
                raise Stage12698Error("accepted_repository_identity_missing")
            identity = (revision, tree)
            prior = identities.get(identity)
            if prior is not None and prior != key:
                raise Stage12698Error("conflicting_repository_identity")
            identities[identity] = key
            keys.add(key)
    return identities, keys


def resolve_repository_paths(
    stage12696: Any,
    memberships: Mapping[str, Any],
    repository_root: Path,
    *,
    max_entries: int = 2_000,
) -> tuple[dict[str, str], dict[str, int]]:
    identities, expected_keys = _expected_repository_identities(memberships)
    paths: dict[str, str] = {}
    counters: Counter[str] = Counter()
    with stage12696._pinned_root_handle(repository_root) as root_handle:
        names = sorted(os.listdir(root_handle.fd))
        if len(names) > max_entries:
            raise Stage12698Error("repository_directory_entry_limit_exceeded")
        for name in names:
            counters["local_entries_examined"] += 1
            try:
                stage12696._canonical_relative_path(name)
                with stage12696.pin_repository_at_fd(
                    root_handle.path, root_handle.fd, name,
                ) as pinned:
                    commit = pinned._stage12696_head_commit
                    key = identities.get((pinned.head_oid, commit.tree_oid))
                    if key is None:
                        counters["catalog_unmatched_local_entries"] += 1
                        continue
                    if key in paths:
                        counters["duplicate_local_catalog_identity"] += 1
                        continue
                    paths[key] = name
                    counters["catalog_identities_resolved"] += 1
            except (stage12696.Stage12696Error, stage12696.S93.Stage12693Error, OSError):
                counters["local_entries_quarantined"] += 1
        root_handle.revalidate()
    missing = expected_keys - set(paths)
    if missing:
        raise Stage12698Error(
            f"accepted_repository_identities_unresolved:{len(missing)}"
        )
    if set(paths) != expected_keys:
        raise Stage12698Error("repository_identity_mapping_mismatch")
    return paths, dict(sorted(counters.items()))


def _materialize_verifier_candidate(
    stage12695: Any,
    stage12697: Any,
    bundle: Mapping[str, Any],
    package: Mapping[str, Any],
) -> dict[str, Any]:
    stage12697.validate_materialization_input(bundle, package)
    records = bundle["records"]
    raws = bundle["raw_records"]
    return stage12695.build_observed_verifier_candidate(
        records["stage12537"],
        records["result"],
        records["report"],
        records["commit"],
        records["smoke"],
        records["join"],
        raw_stage12537_bytes=raws["stage12537"],
        raw_result_bytes=raws["result"],
        raw_report_bytes=raws["report"],
        raw_commit_bytes=raws["commit"],
        raw_smoke_bytes=raws["smoke"],
        raw_join_bytes=raws["join"],
    )


def _bind_verifier_repository_snapshot(
    candidate: Mapping[str, Any],
    bundle: Mapping[str, Any],
    package: Mapping[str, Any],
    seen_identities: set[tuple[str, str, str]],
) -> dict[str, Any]:
    package_unsigned = dict(package)
    package_sha256 = package_unsigned.pop("package_sha256", None)
    if (
        not isinstance(package_sha256, str)
        or _stable(package_unsigned) != package_sha256
    ):
        raise Stage12698Error("verifier_package_commitment_mismatch")
    if bundle.get("package_sha256") != package_sha256:
        raise Stage12698Error("verifier_package_bundle_mismatch")

    records = bundle.get("records")
    result = records.get("result") if isinstance(records, Mapping) else None
    snapshot = package.get("snapshot")
    if not isinstance(result, Mapping) or not isinstance(snapshot, Mapping):
        raise Stage12698Error("verifier_repository_snapshot_missing")
    repository_identity = package.get("repository_identity_sha256")
    revision = snapshot.get("revision")
    root_tree_oid = snapshot.get("root_tree_oid")
    snapshot_commitment = snapshot.get("snapshot_commitment_sha256")
    if (
        not isinstance(repository_identity, str)
        or len(repository_identity) != 64
        or any(
            character not in "0123456789abcdef"
            for character in repository_identity
        )
        or snapshot.get("repository_identity_sha256") != repository_identity
        or result.get("commit_sha") != revision
        or package.get("queue_id") != result.get("queue_id")
        or not isinstance(root_tree_oid, str)
        or len(root_tree_oid) not in {40, 64}
        or any(
            character not in "0123456789abcdef"
            for character in root_tree_oid
        )
    ):
        raise Stage12698Error("verifier_repository_snapshot_identity_mismatch")
    repo_family = result.get("repo_family")
    if (
        not isinstance(repo_family, str)
        or _sha(repo_family.encode()) != repository_identity
    ):
        raise Stage12698Error("verifier_repository_identity_mismatch")
    snapshot_unsigned = dict(snapshot)
    snapshot_unsigned.pop("snapshot_commitment_sha256", None)
    expected_snapshot_commitment = _stable([
        "stage12697_descriptor_pinned_shallow_head_snapshot_v1",
        snapshot_unsigned,
    ])
    if snapshot_commitment != expected_snapshot_commitment:
        raise Stage12698Error("verifier_snapshot_commitment_mismatch")

    copied = dict(candidate)
    proof = dict(copied.get("proof", {}))
    if proof.get("immutable_commit_git_oid") != revision:
        raise Stage12698Error("verifier_candidate_commit_snapshot_mismatch")
    identity = (repository_identity, revision, snapshot_commitment)
    if identity in seen_identities:
        raise Stage12698Error(
            "verifier_repository_snapshot_identity_not_unique"
        )
    seen_identities.add(identity)
    component = _stable([
        "stage12697_direct_repository_snapshot_component_v1",
        repository_identity,
        revision,
        root_tree_oid,
        snapshot_commitment,
    ])
    proof.update({
        "repository_key_sha256": repository_identity,
        "repository_identity_sha256": repository_identity,
        "content_component_sha256": component,
        "accepted_revision": revision,
        "revision": revision,
        "root_tree_oid": root_tree_oid,
        "snapshot_commitment_sha256": snapshot_commitment,
        "stage12697_package_sha256": package_sha256,
        "proof_contract":
            "stage12697_direct_authenticated_repository_snapshot_v1",
    })
    copied["proof"] = proof
    return copied


def _target_strings(value: Any):
    if isinstance(value, str):
        yield value
    elif isinstance(value, Mapping):
        for key in sorted(value):
            yield from _target_strings(value[key])
    elif isinstance(value, (list, tuple)):
        for item in value:
            yield from _target_strings(item)


def _is_semantic_placeholder_target(
    value: str, *, field_name: str | None, objective: str | None,
) -> bool:
    normalized = " ".join(value.strip().split()).casefold()
    answer = _ANSWER_PREFIX.fullmatch(normalized)
    if answer is not None:
        normalized = answer.group(1).strip()
    if (
        normalized == "pass"
        and objective == "compact_observed_verifier_summary"
        and field_name == "outcome"
    ):
        return False
    return normalized in _FORBIDDEN_TARGETS


def _target_contains_semantic_placeholder(
    value: Any, *, field_name: str | None = None, objective: str | None = None,
) -> bool:
    if isinstance(value, str):
        return _is_semantic_placeholder_target(
            value, field_name=field_name, objective=objective,
        )
    if isinstance(value, Mapping):
        return any(
            _target_contains_semantic_placeholder(
                child, field_name=str(key), objective=objective,
            )
            for key, child in value.items()
        )
    if isinstance(value, (list, tuple)):
        return any(
            _target_contains_semantic_placeholder(
                child, field_name=field_name, objective=objective,
            )
            for child in value
        )
    return False


def _validate_materialized_supply(
    retained: list[dict[str, Any]],
    dedup: Mapping[str, int],
    source_counts: Mapping[str, int],
) -> dict[str, int]:
    if dict(source_counts) != EXPECTED_SOURCE_COUNTS:
        raise Stage12698Error("authenticated_source_count_mismatch")
    expected_raw = (
        EXPECTED_SOURCE_COUNTS["authenticated_git_heads"] * 3
        + EXPECTED_SOURCE_COUNTS["authenticated_declaration_rows"]
        + EXPECTED_SOURCE_COUNTS["authenticated_verifier_joins"]
    )
    if dict(source_counts) == PRODUCTION_SOURCE_COUNTS:
        expected_metadata_counts = EXPECTED_RETAINED_METADATA_COUNTS
        expected_retained = EXPECTED_RETAINED_CANDIDATE_ROWS
        expected_duplicates = EXPECTED_DUPLICATE_QUARANTINE_ROWS
    else:
        expected_metadata_counts = {
            "repository_structure": EXPECTED_SOURCE_COUNTS["authenticated_git_heads"],
            "test_layout_convention": EXPECTED_SOURCE_COUNTS["authenticated_git_heads"],
            "documentation_layout_convention": EXPECTED_SOURCE_COUNTS["authenticated_git_heads"],
            "parsed_declaration_class": EXPECTED_SOURCE_COUNTS["authenticated_declaration_rows"],
        }
        expected_retained = expected_raw
        expected_duplicates = 0
    if (
        dedup.get("raw_candidate_rows") != expected_raw
        or dedup.get("unique_candidate_rows") != expected_retained
        or dedup.get("duplicate_or_conflicting_rows_quarantined", 0)
        != expected_duplicates
        or dedup.get("conflicting_encoder_inputs", 0) != 0
        or len(retained) != expected_retained
    ):
        raise Stage12698Error("candidate_supply_reconciliation_failed")
    metadata_fields: Counter[str] = Counter()
    verifier_rows = 0
    for row in retained:
        target = row.get("target")
        if not isinstance(target, Mapping) or not target:
            raise Stage12698Error("candidate_target_empty_or_invalid")
        strings = list(_target_strings(target))
        objective = row.get("objective_family")
        if not strings or _target_contains_semantic_placeholder(
            target, objective=objective,
        ):
            raise Stage12698Error("placeholder_or_empty_candidate_target")
        if objective == "exact_repository_metadata_classification":
            field = target.get("classification_field")
            if isinstance(field, str):
                metadata_fields[field] += 1
        elif objective == "compact_observed_verifier_summary":
            verifier_rows += 1
    if set(metadata_fields) != EXPECTED_METADATA_FIELDS:
        raise Stage12698Error("required_metadata_subobjective_missing")
    if dict(metadata_fields) != expected_metadata_counts:
        raise Stage12698Error("metadata_subobjective_count_mismatch")
    if verifier_rows != EXPECTED_SOURCE_COUNTS["authenticated_verifier_joins"]:
        raise Stage12698Error("authenticated_verifier_retention_mismatch")
    return dict(sorted(metadata_fields.items()))


def materialize_authenticated_candidates(
    repository_root: Path = DEFAULT_REPOSITORY_ROOT,
) -> dict[str, Any]:
    stage12695, stage12696, stage12697 = _load_dependencies()
    verifier = stage12697.build_packages(ROOT)

    memberships = stage12696.load_accepted_artifact_memberships(ROOT)
    try:
        repository_paths, mapping = resolve_repository_paths(
            stage12696, memberships, repository_root,
        )
        inventory = stage12696.build_package_inventory(
            **memberships,
            repository_root=repository_root,
            repository_paths=repository_paths,
        )

        candidates: list[dict[str, Any]] = []
        catalog_records = memberships["stage12688_catalog"].records
        if len(catalog_records) != len(inventory.git_heads):
            raise Stage12698Error("git_evidence_reconciliation_failed")
        for record, evidence in zip(catalog_records, inventory.git_heads):
            if record["repository_key_sha256"] != evidence.repository_key_sha256:
                raise Stage12698Error("git_evidence_order_mismatch")

            candidates.extend(stage12695.build_git_metadata_candidates(
                record,
                canonical_tree_objects=evidence.component_objects,
                canonical_tree_entries=evidence.component_tree_entry_identities,
                canonical_root_commit_oids=evidence.root_commit_oids,
                raw_source_record_bytes=_raw_record(record),
            ))

        declaration_records = {
            row["row_id"]: row
            for row in memberships["stage12692_rows"].records
        }
        if len(declaration_records) != len(inventory.declarations):
            raise Stage12698Error("declaration_evidence_reconciliation_failed")
        for evidence in inventory.declarations:
            row = declaration_records.get(evidence.row_id)
            if row is None:
                raise Stage12698Error("declaration_row_missing")
            candidates.append(
                stage12695.build_parsed_declaration_metadata_candidate(
                    row,
                    canonical_source_bytes=evidence.source_bytes,
                    raw_source_record_bytes=_raw_record(row),
                )
            )
    finally:
        stage12696.close_accepted_artifact_memberships(memberships)

    packages = {row["package_sha256"]: row for row in verifier["packages"]}
    if len(packages) != len(verifier["materialization_inputs"]):
        raise Stage12698Error("verifier_materialization_reconciliation_failed")
    verifier_identities: set[tuple[str, str, str]] = set()
    for bundle in verifier["materialization_inputs"]:
        package = packages.get(bundle["package_sha256"])
        if package is None:
            raise Stage12698Error("verifier_package_missing")
        candidate = _materialize_verifier_candidate(
            stage12695, stage12697, bundle, package,
        )
        candidates.append(
            _bind_verifier_repository_snapshot(
                candidate, bundle, package, verifier_identities,
            )
        )

    retained, dedup = stage12695.deduplicate_candidates(candidates)
    for row in retained:
        authority = row.get("authority")
        if not isinstance(authority, Mapping) or any(authority.values()):
            raise Stage12698Error("candidate_authority_not_closed")

    objective_counts = dict(sorted(Counter(
        row["objective_family"] for row in retained
    ).items()))
    source_counts = {
        "authenticated_git_heads": inventory.capacity["authenticated_git_heads"],
        "authenticated_declaration_rows":
            inventory.capacity["authenticated_declaration_rows"],
        "authenticated_verifier_joins": len(verifier["materialization_inputs"]),
    }
    metadata_classification_counts = _validate_materialized_supply(
        retained, dedup, source_counts,
    )
    summary = {
        "stage": 12698,
        "record_type": "stage12698_authenticated_in_memory_materialization_v1",
        "candidates": retained,
        "candidate_count": len(retained),
        "raw_candidate_count": dedup["raw_candidate_rows"],
        "duplicate_quarantine_count":
            dedup["duplicate_or_conflicting_rows_quarantined"],
        "objective_counts": objective_counts,
        "metadata_classification_counts": metadata_classification_counts,
        "source_counts": source_counts,
        "deduplication": dedup,
        "repository_mapping": mapping,
        "stage12696_package_manifest_sha256":
            inventory.package_manifest_sha256,
        "stage12697_capacity_commitment_sha256":
            verifier["capacity_commitment_sha256"],
        "candidate_commitment_sha256": _stable(retained),
        "model_example_commitment_sha256": _stable([
            row["proof"]["dedup_model_example_sha256"] for row in retained
        ]),
        "publication_performed": False,
        "training_eligible_rows": 0,
        "authority": dict(AUTHORITY),
    }
    return summary


def public_summary(result: Mapping[str, Any]) -> dict[str, Any]:
    return {
        key: value for key, value in result.items()
        if key != "candidates"
    }


def _write_all(fd: int, payload: bytes) -> None:
    offset = 0
    while offset < len(payload):
        written = os.write(fd, payload[offset:])
        if written <= 0:
            raise Stage12698Error("private_materialization_short_write")
        offset += written


def _rename_noreplace(directory_fd: int, source: str, destination: str) -> None:
    libc = ctypes.CDLL(None, use_errno=True)
    renameat2 = getattr(libc, "renameat2", None)
    if renameat2 is None:
        raise Stage12698Error("rename_noreplace_unavailable")
    renameat2.argtypes = [
        ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p,
        ctypes.c_uint,
    ]
    renameat2.restype = ctypes.c_int
    result = renameat2(
        directory_fd, source.encode("ascii"), directory_fd,
        destination.encode("ascii"), 1,
    )
    if result != 0:
        error_number = ctypes.get_errno()
        reason = (
            "private_destination_exists" if error_number == errno.EEXIST
            else "private_noreplace_rename_failed"
        )
        raise Stage12698Error(reason)


def _revalidate_generation(
    root_fd: int, generation: str, generation_fd: int,
    identity: tuple[int, int],
) -> None:
    current = os.fstat(generation_fd)
    fresh_fd = os.open(
        generation, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
        dir_fd=root_fd,
    )
    try:
        fresh = os.fstat(fresh_fd)
    finally:
        os.close(fresh_fd)
    if (
        not stat.S_ISDIR(current.st_mode) or not stat.S_ISDIR(fresh.st_mode)
        or (current.st_dev, current.st_ino) != identity
        or (fresh.st_dev, fresh.st_ino) != identity
    ):
        raise Stage12698Error("private_generation_identity_changed")


def _hash_open_fd(fd: int, size: int) -> str:
    digest = hashlib.sha256()
    offset = 0
    while offset < size:
        chunk = os.pread(fd, min(1 << 20, size - offset), offset)
        if not chunk:
            raise Stage12698Error("published_file_short_read")
        digest.update(chunk)
        offset += len(chunk)
    return digest.hexdigest()


def _revalidate_published_file(
    directory_fd: int, name: str, source_fd: int,
    identity: tuple[int, int], size: int, expected_sha256: str, reason: str,
) -> None:
    current = os.fstat(source_fd)
    fresh_fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW, dir_fd=directory_fd)
    try:
        fresh = os.fstat(fresh_fd)
        fresh_sha256 = _hash_open_fd(fresh_fd, size)
    finally:
        os.close(fresh_fd)
    if (
        not stat.S_ISREG(current.st_mode) or not stat.S_ISREG(fresh.st_mode)
        or current.st_nlink != 1 or fresh.st_nlink != 1
        or current.st_size != size or fresh.st_size != size
        or (current.st_dev, current.st_ino) != identity
        or (fresh.st_dev, fresh.st_ino) != identity
        or _hash_open_fd(source_fd, size) != expected_sha256
        or fresh_sha256 != expected_sha256
    ):
        raise Stage12698Error(reason)


def _validate_private_result(result: Mapping[str, Any]) -> None:
    forbidden_top_level = frozenset(AUTHORITY) | frozenset({"stage12595_allowed"})
    if forbidden_top_level & set(result):
        raise Stage12698Error("reserved_top_level_authority_field")
    if (
        result.get("publication_performed") is not False
        or result.get("training_eligible_rows") != 0
        or result.get("authority") != AUTHORITY
    ):
        raise Stage12698Error("private_result_authority_not_closed")
    candidates = result.get("candidates")
    if not isinstance(candidates, list) or any(
        not isinstance(row, Mapping)
        or not isinstance(row.get("authority"), Mapping)
        or not CANDIDATE_AUTHORITY_FIELDS <= set(row["authority"])
        or any(row["authority"].values())
        for row in candidates
    ):
        raise Stage12698Error("private_candidate_authority_not_closed")
    if set(result) != PRIVATE_RESULT_FIELDS:
        raise Stage12698Error("private_result_schema_invalid")
    dedup = result.get("deduplication")
    source_counts = result.get("source_counts")
    if not isinstance(dedup, Mapping) or not isinstance(source_counts, Mapping):
        raise Stage12698Error("private_supply_contract_missing")
    metadata_counts = _validate_materialized_supply(candidates, dedup, source_counts)
    objective_counts = dict(sorted(Counter(
        row["objective_family"] for row in candidates
    ).items()))
    model_commitments = [
        row.get("proof", {}).get("dedup_model_example_sha256")
        for row in candidates
    ]
    if (
        result.get("candidate_count") != len(candidates)
        or result.get("raw_candidate_count") != dedup["raw_candidate_rows"]
        or result.get("duplicate_quarantine_count")
        != dedup["duplicate_or_conflicting_rows_quarantined"]
        or result.get("objective_counts") != objective_counts
        or result.get("metadata_classification_counts") != metadata_counts
        or result.get("candidate_commitment_sha256") != _stable(candidates)
        or any(not isinstance(value, str) for value in model_commitments)
        or len(set(model_commitments)) != len(model_commitments)
        or result.get("model_example_commitment_sha256")
        != _stable(model_commitments)
    ):
        raise Stage12698Error("private_result_supply_or_commitment_invalid")


def _make_materialize_and_persist():
    def _persist_materialization(
        result: Mapping[str, Any], output_root: Path,
    ) -> dict[str, Any]:
        _validate_private_result(result)
        if "candidates" not in result or not isinstance(result["candidates"], list):
            raise Stage12698Error("private_candidates_missing")
        if result.get("candidate_commitment_sha256") != _stable(result["candidates"]):
            raise Stage12698Error("private_candidate_commitment_mismatch")
        _stage12695, stage12696, _stage12697 = _load_dependencies()
        generation_commitment = _stable({
            "candidate_commitment_sha256": result["candidate_commitment_sha256"],
            "stage12696_package_manifest_sha256":
                result["stage12696_package_manifest_sha256"],
            "stage12697_capacity_commitment_sha256":
                result["stage12697_capacity_commitment_sha256"],
        })
        generation = (
            "stage12698_" + generation_commitment[:24] + "_" + secrets.token_hex(8)
        )
        temporary_generation = ".pending-" + secrets.token_hex(16)
        bundle = {
            "record_type": "stage12698_private_materialization_bundle_v1",
            "generation_commitment_sha256": generation_commitment,
            "summary": public_summary(result),
            "candidates": result["candidates"],
            "authority": dict(AUTHORITY),
            "residual_publication_trust_contract":
                dict(RESIDUAL_PUBLICATION_TRUST_CONTRACT),
        }
        payload = json.dumps(
            bundle, sort_keys=True, separators=(",", ":"), ensure_ascii=True,
        ).encode("ascii") + b"\n"
        payload_sha256 = _sha(payload)
        with stage12696._pinned_root_handle(output_root) as root_handle:
            try:
                os.mkdir(temporary_generation, mode=0o700, dir_fd=root_handle.fd)
            except OSError as error:
                raise Stage12698Error("private_generation_create_failed") from error
            generation_fd = os.open(
                temporary_generation, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
                dir_fd=root_handle.fd,
            )
            generation_info = os.fstat(generation_fd)
            generation_identity = (generation_info.st_dev, generation_info.st_ino)
            try:
                _revalidate_generation(
                    root_handle.fd, temporary_generation, generation_fd, generation_identity,
                )
                temporary = ".private_materialization.tmp." + secrets.token_hex(16)
                flags = os.O_RDWR | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW
                artifact_fd = os.open(temporary, flags, 0o600, dir_fd=generation_fd)
                try:
                    before = os.fstat(artifact_fd)
                    _write_all(artifact_fd, payload)
                    os.fchmod(artifact_fd, 0o400)
                    os.fsync(artifact_fd)
                    after = os.fstat(artifact_fd)
                    if (
                        not stat.S_ISREG(after.st_mode) or after.st_nlink != 1
                        or (before.st_dev, before.st_ino) != (after.st_dev, after.st_ino)
                        or after.st_size != len(payload)
                    ):
                        raise Stage12698Error("private_artifact_identity_changed")
                    _revalidate_generation(
                        root_handle.fd, temporary_generation, generation_fd, generation_identity,
                    )
                    _rename_noreplace(
                        generation_fd, temporary, "private_materialization.json",
                    )
                    _revalidate_published_file(
                        generation_fd, "private_materialization.json", artifact_fd,
                        (after.st_dev, after.st_ino), len(payload), payload_sha256,
                        "private_artifact_identity_changed",
                    )
                    os.fsync(generation_fd)
                    _revalidate_generation(
                        root_handle.fd, temporary_generation, generation_fd, generation_identity,
                    )
                finally:
                    os.close(artifact_fd)
                complete = json.dumps({
                    "generation_commitment_sha256": generation_commitment,
                    "private_materialization_sha256": payload_sha256,
                }, sort_keys=True, separators=(",", ":")).encode("ascii") + b"\n"
                complete_temporary = ".complete.tmp." + secrets.token_hex(16)
                complete_fd = os.open(
                    complete_temporary, flags, 0o600, dir_fd=generation_fd,
                )
                try:
                    before = os.fstat(complete_fd)
                    _write_all(complete_fd, complete)
                    os.fchmod(complete_fd, 0o400)
                    os.fsync(complete_fd)
                    after = os.fstat(complete_fd)
                    if (
                        not stat.S_ISREG(after.st_mode) or after.st_nlink != 1
                        or (before.st_dev, before.st_ino) != (after.st_dev, after.st_ino)
                        or after.st_size != len(complete)
                    ):
                        raise Stage12698Error("private_complete_identity_changed")
                    _revalidate_generation(
                        root_handle.fd, temporary_generation, generation_fd, generation_identity,
                    )
                    _rename_noreplace(generation_fd, complete_temporary, "COMPLETE")
                    _revalidate_published_file(
                        generation_fd, "COMPLETE", complete_fd,
                        (after.st_dev, after.st_ino), len(complete), _sha(complete),
                        "private_complete_identity_changed",
                    )
                finally:
                    os.close(complete_fd)
                os.fsync(generation_fd)
                _revalidate_generation(
                    root_handle.fd, temporary_generation, generation_fd, generation_identity,
                )
                root_handle.revalidate()
                os.fsync(root_handle.fd)
                os.fchmod(generation_fd, 0o500)
                os.fsync(generation_fd)
                _revalidate_generation(
                    root_handle.fd, temporary_generation, generation_fd,
                    generation_identity,
                )
                root_handle.revalidate()
                _rename_noreplace(
                    root_handle.fd, temporary_generation, generation,
                )
                _revalidate_generation(
                    root_handle.fd, generation, generation_fd, generation_identity,
                )
                os.fsync(root_handle.fd)
            finally:
                os.close(generation_fd)
        return {
            "generation": generation,
            "generation_commitment_sha256": generation_commitment,
            "private_materialization_sha256": payload_sha256,
            "private_materialization_performed": True,
            "publication_performed": False,
            "training_eligible_rows": 0,
            "authority": dict(AUTHORITY),
            "residual_publication_trust_contract":
                dict(RESIDUAL_PUBLICATION_TRUST_CONTRACT),
        }


    def materialize_and_persist(
        repository_root: Path, private_output_root: Path,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        result = materialize_authenticated_candidates(repository_root)
        persisted = _persist_materialization(result, private_output_root)
        return public_summary(result), persisted

    return materialize_and_persist


materialize_and_persist = _make_materialize_and_persist()
del _make_materialize_and_persist


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--materialize-in-memory", action="store_true")
    parser.add_argument(
        "--repository-root", type=Path, default=DEFAULT_REPOSITORY_ROOT,
    )
    parser.add_argument("--private-output-root", type=Path)
    args = parser.parse_args(argv)
    if not args.materialize_in_memory:
        parser.error("explicit --materialize-in-memory is required")
    if args.private_output_root is None:
        output = public_summary(
            materialize_authenticated_candidates(args.repository_root)
        )
    else:
        output, persisted = materialize_and_persist(
            args.repository_root, args.private_output_root,
        )
        output["private_artifact"] = persisted
    print(json.dumps(output, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
