#!/usr/bin/env python3
"""Replay frozen Stage12693 and privately persist unassigned retention rows."""

from __future__ import annotations

import argparse
import collections
import copy
import ctypes
import errno
import hashlib
import importlib.util
import json
import os
import secrets
import stat
import sys
from pathlib import Path
from typing import Any, Iterable, Mapping


ROOT = Path(__file__).resolve().parents[1]
STAGE12693_PATH = ROOT / "scripts/build_stage12693_source_backed_historical_old_language_retention.py"
STAGE12693_SHA256 = "47d878b684888ccabbc672d0de7aaed04e56ea56be29eac01b0809408edae2fd"
ACCEPTED_SUMMARY = ROOT / (
    "runs/local/artifacts/stage12693_source_backed_historical_old_language_retention/"
    "capacity_summaries/stage12693_capacity_summary_576bf6e1c84403b83706c55e.json"
)
ACCEPTED_SUMMARY_SHA256 = "20ce10fef4a9ab7f874ffca8745d330f634965afef4bd3ab5c3a774bc35ca5eb"
ACCEPTED_STAGE12693_BINDING_SHA256 = (
    "576bf6e1c84403b83706c55e79efe9a4327931eb8a57de862a7d874b2ade0e43"
)
DEFAULT_OUTPUT_ROOT = ROOT / (
    "runs/local/artifacts/stage12699_private_historical_retention_materialization/"
    "private_materializations"
)
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
FORBIDDEN_TARGETS = {
    "", "answer:", "placeholder", "<answer>", "<missing>", "<placeholder>",
    "todo", "tbd", "n/a", "none", "null",
}


class Stage12699Error(RuntimeError):
    pass


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _stable(value: Any) -> str:
    return _sha(json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=True,
    ).encode("ascii"))


def _target_is_placeholder(target: str) -> bool:
    normalized = " ".join(target.strip().lower().split())
    return (
        normalized in FORBIDDEN_TARGETS
        or "<placeholder>" in normalized
        or "[placeholder]" in normalized
        or normalized.startswith("answer: placeholder")
        or normalized.startswith("answer: todo")
        or normalized.startswith("answer: tbd")
        or normalized.startswith("answer: n/a")
        or normalized.startswith("answer: <")
    )


def _source_identity(row: Mapping[str, Any], proof: Mapping[str, Any]) -> str:
    try:
        provenance = row["source_provenance"]
        identity = _stable([
            "stage12693_target_independent_row_selection_v1",
            provenance["repository_key_sha256"],
            provenance["sampling_child_commit_git_oid"],
            provenance["historical_parent_commit_git_oid"],
            provenance["repository_relative_path"],
            proof["base_comparison_objective_family"],
            provenance["span_start_byte"],
            provenance["span_end_byte"],
            provenance["git_blob_oid"],
            provenance["parent_tree_oid"],
        ])
    except (KeyError, TypeError) as exc:
        raise Stage12699Error("source_pair_schema_mismatch") from exc
    return identity


def _validate_source_pair(
    row: Mapping[str, Any], proof: Mapping[str, Any], *, s93: Any | None = None,
) -> None:
    try:
        target = row["target"]["decoder_text"]
        input_text = row["input_text"]
        provenance = row["source_provenance"]
        closed = (
            row["split"] == ""
            and row.get("visibility_class", "") in {"", "private_unassigned"}
            and row["authority"] == AUTHORITY
            and not any(row["authority"].values())
            and proof["training_admitted"] is False
            and proof["strict_eval_admitted"] is False
            and proof["sealed_eval_admitted"] is False
        )
        exact = (
            isinstance(target, str)
            and not _target_is_placeholder(target)
            and proof["row_id"] == row["row_id"]
            and proof["selection_key_sha256"] == _source_identity(row, proof)
            and proof["encoder_input_sha256"] == _sha(input_text.encode("utf-8"))
            and proof["target_sha256"] == _sha(target.encode("utf-8"))
            and provenance["target_sha256"] == proof["target_sha256"]
            and proof["historical_age_bucket"] == provenance["historical_age_bucket"]
            and proof["repository_key_sha256"] == provenance["repository_key_sha256"]
            and proof["content_component_sha256"] == provenance["content_component_sha256"]
            and proof["historical_parent_commit_git_oid"]
            == provenance["historical_parent_commit_git_oid"]
            and proof["source_window_sha256"] == provenance["source_window_sha256"]
            and proof["source_file_sha256"] == provenance["source_file_sha256"]
            and proof["git_blob_oid"] == provenance["git_blob_oid"]
            and proof["row_sha256"] == _stable(row)
        )
    except (KeyError, TypeError, AttributeError) as exc:
        raise Stage12699Error("source_pair_schema_mismatch") from exc
    if not closed:
        raise Stage12699Error("embedded_source_authority_or_split_not_closed")
    if not exact:
        raise Stage12699Error("source_pair_evidence_mismatch")
    if s93 is None:
        s93 = _load_stage12693()
    try:
        s93.validate_historical_row_proof(dict(row), dict(proof))
    except Exception as exc:
        raise Stage12699Error("source_pair_stage12693_proof_mismatch") from exc


def _candidate_body_sha256(candidate: Mapping[str, Any]) -> str:
    value = copy.deepcopy(dict(candidate))
    value.get("proof", {}).pop("candidate_body_sha256", None)
    return _stable(value)


def _expected_candidate_id(
    source_row: Mapping[str, Any], source_proof: Mapping[str, Any],
) -> str:
    return "stage12699_" + _stable([
        "stage12699_target_independent_retention_row_v1",
        _source_identity(source_row, source_proof),
        _sha(source_row["input_text"].encode("utf-8")),
        source_row["source_provenance"]["source_window_sha256"],
        _sha(source_row["source_provenance"]["repository_relative_path"].encode("utf-8")),
    ])


def _validate_candidate(
    candidate: Mapping[str, Any], *, s93: Any,
    accepted_binding_sha256: str,
) -> None:
    try:
        source_row = candidate["proof"]["stage12693_source_row"]
        source_proof = candidate["proof"]["stage12693_source_proof"]
        _validate_source_pair(source_row, source_proof, s93=s93)
        exact = (
            candidate["proof"]["proof_contract"]
            == "stage12699_frozen_stage12693_adapter_v1"
            and candidate["proof"]["accepted_stage12693_binding_sha256"]
            == accepted_binding_sha256
            and candidate["proof"]["accepted_stage12693_artifact_sha256"]
            == ACCEPTED_SUMMARY_SHA256
            and candidate["row_id"] == _expected_candidate_id(source_row, source_proof)
            and candidate["input_text"] == source_row["input_text"]
            and candidate["target"] == source_row["target"]
            and candidate["language_family"] == source_row["language_family"]
            and candidate["objective_family"] == source_row["objective_family"]
            and candidate["loss_mask"] == source_row["loss_mask"]
            and candidate["source_provenance"] == source_row["source_provenance"]
            and candidate["split"] == ""
            and candidate["visibility_class"] == "private_unassigned"
            and candidate["authority"] == AUTHORITY
            and not any(candidate["authority"].values())
        )
    except (KeyError, TypeError, AttributeError) as exc:
        raise Stage12699Error("candidate_semantic_schema_mismatch") from exc
    if not exact:
        raise Stage12699Error("candidate_semantic_mismatch")


def _load_stage12693():
    raw = STAGE12693_PATH.read_bytes()
    if _sha(raw) != STAGE12693_SHA256:
        raise Stage12699Error("stage12693_builder_digest_mismatch")
    spec = importlib.util.spec_from_file_location("stage12693_for_stage12699", STAGE12693_PATH)
    if spec is None or spec.loader is None:
        raise Stage12699Error("stage12693_import_unavailable")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    try:
        exec(compile(raw, os.fspath(STAGE12693_PATH), "exec", dont_inherit=True), module.__dict__)
    except BaseException:
        sys.modules.pop(spec.name, None)
        raise
    return module


def _load_accepted_summary(path: Path = ACCEPTED_SUMMARY) -> dict[str, Any]:
    raw = path.read_bytes()
    if path.resolve(strict=True) != ACCEPTED_SUMMARY or _sha(raw) != ACCEPTED_SUMMARY_SHA256:
        raise Stage12699Error("accepted_stage12693_summary_mismatch")
    value = json.loads(raw)
    binding = value.get("summary_artifact_binding", {})
    if (
        binding.get("builder_sha256") != STAGE12693_SHA256
        or binding.get("binding_sha256") != ACCEPTED_STAGE12693_BINDING_SHA256
        or binding.get("aggregate_only") is not True
        or value.get("counts", {}).get("deduplicated_candidates") != 1114
        or any(value.get("authority", {}).values())
    ):
        raise Stage12699Error("accepted_stage12693_contract_mismatch")
    return value


def _replay_kwargs(s93: Any, accepted: Mapping[str, Any]) -> dict[str, Any]:
    bounds = accepted["bounds"]
    work = bounds["work_limits"]
    repository = bounds["repository_work_limits"]
    return {
        "max_local_directories": bounds["max_local_directories"],
        "max_repositories": bounds["max_repositories"],
        "max_materials": bounds["max_materials"],
        "max_materials_per_repository": bounds["max_materials_per_repository"],
        "max_commits_per_repository": bounds["max_commits_per_repository"],
        "max_secondary_parents_per_repository": bounds["max_secondary_parents_per_repository"],
        "max_rows_per_repository": bounds["max_rows_per_repository"],
        "requested_rows": bounds["requested_rows"],
        "work_limits": s93.Stage12693WorkLimits(**work),
        "repository_work_limits": s93.RepositoryWorkLimits(**repository),
    }


def replay_frozen_stage12693(repository_root: Path) -> tuple[dict[str, Any], tuple[Any, Any]]:
    accepted = _load_accepted_summary()
    s93 = _load_stage12693()
    captured: list[tuple[Any, Any]] = []
    original = s93.globally_deduplicate_historical_rows

    def capture(revisions: Iterable[Any], repository_cap: int = 64):
        result = original(revisions, repository_cap=repository_cap)
        captured.append(copy.deepcopy(result))
        return result

    s93.globally_deduplicate_historical_rows = capture
    try:
        replay = s93.run_capacity_scan(
            repository_root,
            s93.AUTHORITATIVE_STAGE12688_CATALOG,
            **_replay_kwargs(s93, accepted),
        )
    finally:
        s93.globally_deduplicate_historical_rows = original
    expected_body = dict(accepted)
    expected_body.pop("summary_artifact_binding")
    if replay != expected_body:
        raise Stage12699Error("stage12693_exact_replay_summary_mismatch")
    if len(captured) != 1:
        raise Stage12699Error("stage12693_replay_capture_count_mismatch")
    rows, proofs = captured[0]
    if len(rows) != 1114 or len(rows) != len(proofs):
        raise Stage12699Error("stage12693_replay_row_count_mismatch")
    return accepted, (rows, proofs)


def adapt_private_rows(
    rows: Iterable[Mapping[str, Any]], proofs: Iterable[Mapping[str, Any]],
    accepted: Mapping[str, Any],
) -> dict[str, Any]:
    accepted_binding = accepted.get("summary_artifact_binding", {}).get("binding_sha256")
    if accepted_binding != ACCEPTED_STAGE12693_BINDING_SHA256:
        raise Stage12699Error("accepted_stage12693_binding_mismatch")
    s93 = _load_stage12693()
    pairs = list(zip(rows, proofs, strict=True))
    groups: dict[str, list[tuple[Mapping[str, Any], Mapping[str, Any]]]] = {}
    for row, proof in pairs:
        target = row.get("target", {}).get("decoder_text")
        if not isinstance(target, str) or _target_is_placeholder(target):
            raise Stage12699Error("placeholder_or_empty_target")
        _validate_source_pair(row, proof, s93=s93)
        identity = _expected_candidate_id(row, proof)
        groups.setdefault(identity, []).append((row, proof))

    candidates: list[dict[str, Any]] = []
    quarantines: collections.Counter[str] = collections.Counter()
    for identity in sorted(groups):
        group = groups[identity]
        targets = {
            _sha(row["target"]["decoder_text"].encode("utf-8"))
            for row, _proof in group
        }
        if len(targets) != 1:
            quarantines["conflicting_target_for_encoder_identity"] += len(group)
            continue
        row, proof = min(
            group,
            key=lambda pair: _stable([pair[0], pair[1]]),
        )
        if len(group) > 1:
            quarantines["duplicate_target_independent_identity"] += len(group) - 1
        candidate = {
            "row_id": identity,
            "split": "",
            "visibility_class": "private_unassigned",
            "language_family": row["language_family"],
            "objective_family": row["objective_family"],
            "input_text": row["input_text"],
            "target": copy.deepcopy(row["target"]),
            "loss_mask": copy.deepcopy(row["loss_mask"]),
            "source_provenance": copy.deepcopy(row["source_provenance"]),
            "proof": {
                "proof_contract": "stage12699_frozen_stage12693_adapter_v1",
                "target_independent_row_identity_sha256": identity.removeprefix("stage12699_"),
                "accepted_stage12693_binding_sha256": accepted["summary_artifact_binding"]["binding_sha256"],
                "accepted_stage12693_artifact_sha256": ACCEPTED_SUMMARY_SHA256,
                "stage12693_source_row": copy.deepcopy(row),
                "stage12693_source_proof": copy.deepcopy(proof),
            },
            "authority": dict(AUTHORITY),
        }
        candidate["proof"]["candidate_body_sha256"] = _candidate_body_sha256(candidate)
        candidates.append(candidate)

    language_counts = dict(sorted(collections.Counter(
        row["language_family"] for row in candidates
    ).items()))
    age_counts = dict(sorted(collections.Counter(
        row["source_provenance"]["historical_age_bucket"] for row in candidates
    ).items()))
    catalog = sorted({
        (
            row["source_provenance"]["repository_key_sha256"],
            row["source_provenance"]["content_component_sha256"],
            row["source_provenance"]["pinned_head_commit_git_oid"],
        )
        for row in candidates
    })
    quarantine_records = [
        {
            "row_id": identity,
            "reason": (
                "conflicting_target_for_encoder_identity"
                if len({_sha(row["target"]["decoder_text"].encode("utf-8")) for row, _proof in group}) != 1
                else "duplicate_target_independent_identity"
            ),
            "source_row_ids": sorted(row["row_id"] for row, _proof in group),
            "source_evidence_commitments": sorted(
                proof["immutable_evidence_binding_sha256"] for _row, proof in group
            ),
        }
        for identity, group in sorted(groups.items())
        if len(group) > 1
    ]
    source_catalog = [
        {
            "repository_key_sha256": repository,
            "content_component_sha256": component,
            "pinned_head_commit_git_oid": head,
            "visibility_class": "private_unassigned",
        }
        for repository, component, head in catalog
    ]
    result = {
        "stage": 12699,
        "record_type": "stage12699_private_historical_retention_materialization_v1",
        "candidates": candidates,
        "candidate_count": len(candidates),
        "replayed_stage12693_candidate_count": len(pairs),
        "language_counts": language_counts,
        "age_bucket_counts": age_counts,
        "quarantines": dict(sorted(quarantines.items())),
        "quarantine_records": quarantine_records,
        "source_catalog": source_catalog,
        "accepted_stage12693_binding_sha256": accepted["summary_artifact_binding"]["binding_sha256"],
        "accepted_stage12693_artifact_sha256": ACCEPTED_SUMMARY_SHA256,
        "candidate_commitment_sha256": _stable(candidates),
        "source_catalog_commitment_sha256": _stable(source_catalog),
        "publication_performed": False,
        "training_eligible_rows": 0,
        "authority": dict(AUTHORITY),
    }
    if len(pairs) != accepted["counts"]["deduplicated_candidates"]:
        raise Stage12699Error("accepted_capacity_count_mismatch")
    if dict(sorted(collections.Counter(
        row["language_family"] for row, _proof in pairs
    ).items())) != accepted["language_capacity"]:
        raise Stage12699Error("accepted_capacity_language_mismatch")
    if dict(sorted(collections.Counter(
        proof["historical_age_bucket"] for _row, proof in pairs
    ).items())) != accepted["age_bucket_capacity"]:
        raise Stage12699Error("accepted_capacity_age_mismatch")
    return result


def public_summary(result: Mapping[str, Any]) -> dict[str, Any]:
    return {
        key: value for key, value in result.items()
        if key not in {"candidates", "source_catalog", "quarantine_records"}
    }


def _write_all(fd: int, payload: bytes) -> None:
    offset = 0
    while offset < len(payload):
        written = os.write(fd, payload[offset:])
        if written <= 0:
            raise Stage12699Error("private_short_write")
        offset += written


def _rename_noreplace(directory_fd: int, source: str, destination: str) -> None:
    libc = ctypes.CDLL(None, use_errno=True)
    renameat2 = getattr(libc, "renameat2", None)
    if renameat2 is None:
        raise Stage12699Error("rename_noreplace_unavailable")
    renameat2.argtypes = [
        ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p,
        ctypes.c_uint,
    ]
    renameat2.restype = ctypes.c_int
    result = renameat2(directory_fd, source.encode("ascii"), directory_fd, destination.encode("ascii"), 1)
    if result != 0:
        reason = "private_destination_exists" if ctypes.get_errno() == errno.EEXIST else "private_noreplace_rename_failed"
        raise Stage12699Error(reason)


def _same_inode(fd: int, directory_fd: int, name: str, *, directory: bool = False) -> bool:
    flags = os.O_RDONLY | os.O_NOFOLLOW | (os.O_DIRECTORY if directory else 0)
    fresh_fd = os.open(name, flags, dir_fd=directory_fd)
    try:
        before, fresh = os.fstat(fd), os.fstat(fresh_fd)
        expected_type = stat.S_ISDIR if directory else stat.S_ISREG
        link_count_ok = True if directory else before.st_nlink == fresh.st_nlink == 1
        return (
            expected_type(before.st_mode) and expected_type(fresh.st_mode)
            and link_count_ok
            and (before.st_dev, before.st_ino) == (fresh.st_dev, fresh.st_ino)
        )
    finally:
        os.close(fresh_fd)


def _open_absolute_directory(path: Path) -> int:
    if (
        not path.is_absolute()
        or path != Path(os.path.abspath(path))
        or any(part in {"", ".", ".."} for part in path.parts[1:])
    ):
        raise Stage12699Error("private_output_root_not_canonical")
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
    fd = os.open("/", flags)
    try:
        for part in path.parts[1:]:
            next_fd = os.open(part, flags, dir_fd=fd)
            os.close(fd)
            fd = next_fd
        return fd
    except OSError as exc:
        os.close(fd)
        raise Stage12699Error("private_output_root_pin_failed") from exc


def _revalidate_root(root_fd: int, path: Path, identity: tuple[int, int]) -> None:
    current = os.fstat(root_fd)
    fresh_fd = _open_absolute_directory(path)
    try:
        fresh = os.fstat(fresh_fd)
    finally:
        os.close(fresh_fd)
    if (
        not stat.S_ISDIR(current.st_mode)
        or (current.st_dev, current.st_ino) != identity
        or (fresh.st_dev, fresh.st_ino) != identity
    ):
        raise Stage12699Error("private_output_root_identity_changed")


def materialize_and_persist(
    repository_root: Path, output_root: Path,
) -> dict[str, Any]:
    accepted, (rows, proofs) = replay_frozen_stage12693(repository_root)
    result = adapt_private_rows(rows, proofs, accepted)
    accepted_binding = accepted["summary_artifact_binding"]["binding_sha256"]
    if (
        result.get("accepted_stage12693_binding_sha256") != accepted_binding
        or result.get("accepted_stage12693_artifact_sha256")
        != ACCEPTED_SUMMARY_SHA256
    ):
        raise Stage12699Error("result_stage12693_binding_mismatch")
    s93 = _load_stage12693()
    if result.get("authority") != AUTHORITY or any(result["authority"].values()):
        raise Stage12699Error("result_authority_not_closed")
    candidates = result.get("candidates")
    if (
        not isinstance(candidates, list)
        or result.get("candidate_commitment_sha256") != _stable(candidates)
    ):
        raise Stage12699Error("candidate_commitment_mismatch")
    quarantine_counts = result.get("quarantines")
    if (
        result.get("candidate_count") != len(candidates)
        or result.get("replayed_stage12693_candidate_count") != len(rows)
        or not isinstance(quarantine_counts, dict)
        or any(
            not isinstance(value, int) or isinstance(value, bool) or value < 0
            for value in quarantine_counts.values()
        )
        or len(candidates) + sum(quarantine_counts.values()) != len(rows)
    ):
        raise Stage12699Error("materialization_row_accounting_mismatch")
    if any(
        row.get("proof", {}).get("candidate_body_sha256")
        != _candidate_body_sha256(row)
        for row in candidates
    ):
        raise Stage12699Error("candidate_body_commitment_mismatch")
    replay_pair_commitments = collections.Counter(
        _stable(["stage12699_exact_stage12693_source_pair_v1", row, proof])
        for row, proof in zip(rows, proofs, strict=True)
    )
    embedded_pair_commitments: collections.Counter[str] = collections.Counter()
    for candidate in candidates:
        _validate_candidate(
            candidate, s93=s93,
            accepted_binding_sha256=accepted_binding,
        )
        embedded_pair_commitments[_stable([
            "stage12699_exact_stage12693_source_pair_v1",
            candidate["proof"]["stage12693_source_row"],
            candidate["proof"]["stage12693_source_proof"],
        ])] += 1
    if any(
        count > replay_pair_commitments[commitment]
        for commitment, count in embedded_pair_commitments.items()
    ):
        raise Stage12699Error("materialization_not_derived_from_exact_replay")
    source_catalog = result.get("source_catalog")
    expected_catalog = [
        {
            "repository_key_sha256": repository,
            "content_component_sha256": component,
            "pinned_head_commit_git_oid": head,
            "visibility_class": "private_unassigned",
        }
        for repository, component, head in sorted({
            (
                row["source_provenance"]["repository_key_sha256"],
                row["source_provenance"]["content_component_sha256"],
                row["source_provenance"]["pinned_head_commit_git_oid"],
            )
            for row in candidates
        })
    ]
    if (
        not isinstance(source_catalog, list)
        or source_catalog != expected_catalog
        or result.get("source_catalog_commitment_sha256") != _stable(source_catalog)
        or any(
            row.get("visibility_class") != "private_unassigned"
            for row in source_catalog
        )
    ):
        raise Stage12699Error("source_catalog_commitment_or_visibility_mismatch")
    if any(
        row.get("split") != ""
        or row.get("visibility_class") != "private_unassigned"
        or row.get("authority") != AUTHORITY
        for row in candidates
    ):
        raise Stage12699Error("candidate_visibility_or_authority_invalid")
    if output_root.resolve(strict=True) != output_root:
        raise Stage12699Error("private_output_root_not_canonical")

    generation_commitment = _stable({
        "candidate_commitment_sha256": result["candidate_commitment_sha256"],
        "source_catalog_commitment_sha256":
            result["source_catalog_commitment_sha256"],
        "accepted_stage12693_binding_sha256":
            result["accepted_stage12693_binding_sha256"],
    })
    generation = (
        f"stage12699_{generation_commitment[:24]}_{secrets.token_hex(8)}"
    )
    bundle = {
        "record_type": "stage12699_private_historical_retention_bundle_v1",
        "generation_commitment_sha256": generation_commitment,
        "summary": public_summary(result),
        "candidates": candidates,
        "source_catalog": source_catalog,
        "quarantine_records": result["quarantine_records"],
        "authority": dict(AUTHORITY),
    }
    payload = json.dumps(
        bundle, sort_keys=True, separators=(",", ":"), ensure_ascii=True,
    ).encode("ascii") + b"\n"
    complete_payload = json.dumps({
        "generation_commitment_sha256": generation_commitment,
        "private_materialization_sha256": _sha(payload),
    }, sort_keys=True, separators=(",", ":")).encode("ascii") + b"\n"
    publication = {
        "generation": generation,
        "generation_commitment_sha256": generation_commitment,
        "private_materialization_sha256": _sha(payload),
        "private_materialization_performed": True,
        "publication_performed": False,
        "training_eligible_rows": 0,
        "authority": dict(AUTHORITY),
    }
    output = public_summary(result)
    output["private_artifact"] = publication

    root_fd = generation_fd = artifact_fd = complete_fd = -1
    try:
        root_fd = _open_absolute_directory(output_root)
        root_info = os.fstat(root_fd)
        root_identity = (root_info.st_dev, root_info.st_ino)
        _revalidate_root(root_fd, output_root, root_identity)
        try:
            os.mkdir(generation, 0o700, dir_fd=root_fd)
        except FileExistsError as exc:
            raise Stage12699Error("private_generation_collision") from exc
        created = os.stat(generation, dir_fd=root_fd, follow_symlinks=False)
        generation_fd = os.open(
            generation, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
            dir_fd=root_fd,
        )
        opened = os.fstat(generation_fd)
        if (
            not stat.S_ISDIR(created.st_mode)
            or (created.st_dev, created.st_ino) != (opened.st_dev, opened.st_ino)
        ):
            raise Stage12699Error("generation_replaced_before_open")
        if not _same_inode(
            generation_fd, root_fd, generation, directory=True,
        ):
            raise Stage12699Error("generation_identity_changed")

        artifact_temporary = ".materialization.tmp." + secrets.token_hex(16)
        try:
            artifact_fd = os.open(
                artifact_temporary,
                os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                0o600,
                dir_fd=generation_fd,
            )
        except FileExistsError as exc:
            raise Stage12699Error("private_temporary_collision") from exc
        _write_all(artifact_fd, payload)
        os.fsync(artifact_fd)
        if os.fstat(artifact_fd).st_size != len(payload):
            raise Stage12699Error("private_artifact_size_mismatch")
        if not _same_inode(
            artifact_fd, generation_fd, artifact_temporary,
        ):
            raise Stage12699Error("private_artifact_identity_changed")
        _rename_noreplace(
            generation_fd, artifact_temporary, "private_materialization.json",
        )
        if not _same_inode(
            artifact_fd, generation_fd, "private_materialization.json",
        ):
            raise Stage12699Error("private_artifact_identity_changed")

        complete_temporary = ".complete.tmp." + secrets.token_hex(16)
        try:
            complete_fd = os.open(
                complete_temporary,
                os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                0o600,
                dir_fd=generation_fd,
            )
        except FileExistsError as exc:
            raise Stage12699Error("private_temporary_collision") from exc
        _write_all(complete_fd, complete_payload)
        os.fsync(complete_fd)
        if os.fstat(complete_fd).st_size != len(complete_payload):
            raise Stage12699Error("private_complete_size_mismatch")
        if not _same_inode(
            complete_fd, generation_fd, complete_temporary,
        ):
            raise Stage12699Error("private_complete_identity_changed")

        if not _same_inode(
            artifact_fd, generation_fd, "private_materialization.json",
        ):
            raise Stage12699Error("private_artifact_identity_changed")
        if not _same_inode(
            generation_fd, root_fd, generation, directory=True,
        ):
            raise Stage12699Error("generation_identity_changed")
        _revalidate_root(root_fd, output_root, root_identity)
        os.fsync(generation_fd)
        os.fsync(root_fd)

        # Final commit point. No error-propagating operation follows.
        _rename_noreplace(generation_fd, complete_temporary, "COMPLETE")
        return output
    finally:
        for descriptor in (complete_fd, artifact_fd, generation_fd, root_fd):
            if descriptor >= 0:
                try:
                    os.close(descriptor)
                except BaseException:
                    pass


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--materialize", action="store_true")
    parser.add_argument("--repository-root", type=Path, required=True)
    parser.add_argument("--private-output-root", type=Path, required=True)
    args = parser.parse_args(argv)
    if not args.materialize:
        parser.error("explicit --materialize is required")
    output = materialize_and_persist(
        args.repository_root, args.private_output_root,
    )
    print(json.dumps(output, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
