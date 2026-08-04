#!/usr/bin/env python3
"""Build and privately publish the eight-source combined knowledge release."""

from __future__ import annotations

import argparse
import collections
import ctypes
from dataclasses import dataclass
import errno
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import secrets
import stat
import types
import sys
from typing import Any, Iterable, Mapping, Sequence

ROOT = Path(__file__).resolve().parents[1]
CORE_SHA256 = "554f1d24c70ce9bb9c91b575ae1cc66354062926282e6fe70baa1e9e51f2627a"
CORE_PATH = ROOT / "scripts/build_stage12694_global_knowledge_release_split_core.py"
STAGE = "stage12700_combined_knowledge_release"
SCHEMA_VERSION = 1
SOURCE_STAGES = (12687, 12688, 12689, 12690, 12691, 12692, 12698, 12699)
STRICT_SOURCE_STAGES = SOURCE_STAGES[:6]
PINNED_INDEPENDENT_STRICT_AUDIT_SHA256: str | None = None
EXPECTED_STRICT_ROWS = 9568
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
PUBLIC_FILES = {
    12687: ("foundational_train_eval_manifest.jsonl", "train_eval_source_provenance_ledger.jsonl", "train_eval_source_catalog.jsonl"),
    12688: ("multilingual_train_eval_manifest.jsonl", "train_eval_source_provenance_ledger.jsonl", "train_eval_source_catalog.jsonl"),
    12689: ("maintenance_history_train_eval_manifest.jsonl", "train_eval_source_provenance_ledger.jsonl", "train_eval_source_catalog.jsonl"),
    12690: ("symbol_test_train_eval_manifest.jsonl", "train_eval_source_provenance_ledger.jsonl", "train_eval_source_catalog.jsonl"),
    12691: ("api_doc_train_eval_manifest.jsonl", "train_eval_source_provenance_ledger.jsonl", "train_eval_source_catalog.jsonl"),
    12692: ("train_eval_rows.jsonl", "train_eval_proofs.jsonl", "train_eval_source_catalog.jsonl"),
}
PUBLIC_SUMMARY_SHA256 = {
    12687: "4bc5c1918bee56666ec2eb275f3e72a403e7a3afcce35aad2f9fbc2b7ae3a18d",
    12688: "c34c780bd84d167034c7ed392a62f3a618642dec15de6a927dc6fa797f1b7f52",
    12689: "3f97ad79e9bbacf117e500f8be24103c96cf122b1eb4f882af19fe4d3dec2816",
    12690: "5bf05f076e2133086ae189d8bea6f5a8202ebad252a8612f5515787f4ab9d167",
    12691: "3d4eb38f3157563cc5c5fba2a122a5e6ad54d7a151ce761ac89dd0c697dc329e",
    12692: "1209f6f4bfbc3fd3338a0478be419b0f9f714228aef740dd18af3fef63b24199",
}
OBJECTIVES = frozenset({
    "python_parser_source_span_infilling",
    "multilingual_exact_source_span_infilling",
    "exact_pinned_immediate_directory_entry_name_completion",
    "maintenance_commit_message_span_completion",
    "small_diff_exact_child_hunk_completion",
    "python_symbol_reference_prediction",
    "python_test_file_association",
    "python_api_keyword_name_completion",
    "python_sphinx_doc_code_test_relationship",
    "declarative_test_build_scalar_completion",
    "declarative_test_build_target_resolution",
    "repository_structure_classification",
    "test_layout_classification",
    "documentation_layout_classification",
    "parsed_declaration_classification",
    "compact_observed_verifier_summary",
    "historical_multilingual_exact_source_span_infilling",
    "historical_exact_pinned_immediate_directory_entry_name_completion",
})
_SAFE_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,127}")

PUBLIC_ROOTS = {
    12687: ROOT / "runs/local/artifacts/stage12687_source_backed_python_foundational_corpus",
    12688: ROOT / "runs/local/artifacts/stage12688_source_backed_multilingual_knowledge_corpus",
    12689: ROOT / "runs/local/artifacts/stage12689_source_backed_maintenance_history_corpus",
    12690: ROOT / "runs/local/artifacts/stage12690_source_backed_symbol_api_test_links",
    12691: ROOT / "runs/local/artifacts/stage12691_source_backed_python_api_doc_links",
    12692: ROOT / "runs/local/artifacts/stage12692_source_backed_declarative_test_build_conventions",
}

class Stage12700Error(RuntimeError):
    pass


@dataclass(frozen=True)
class ReviewedStage12701Binding:
    root: str
    generation_id: str
    manifest_sha256: str
    complete_sha256: str
    review_contract: str
    independent_review_sha256: str


@dataclass(frozen=True)
class CoreSourceBinding:
    path: str
    sha256: str
    device: int
    inode: int
    size: int

    def as_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "sha256": self.sha256,
            "device": self.device,
            "inode": self.inode,
            "size": self.size,
        }


# Updated only after Stage12701 production, parent audit, and independent review.
REVIEWED_STAGE12701_BINDING: ReviewedStage12701Binding | None = None


def _read_pinned_core_source(
    path: Path = CORE_PATH, expected_sha256: str = CORE_SHA256,
) -> tuple[bytes, CoreSourceBinding]:
    if not path.is_absolute() or str(path) != os.path.normpath(str(path)):
        raise Stage12700Error("split_core_path_not_canonical_absolute")
    parent_fd = os.open("/", os.O_RDONLY | os.O_DIRECTORY)
    source_fd = -1
    try:
        for part in path.parent.parts[1:]:
            if not _SAFE_NAME.fullmatch(part) or part in {".", ".."}:
                raise Stage12700Error("split_core_parent_component_invalid")
            child = os.open(
                part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
                dir_fd=parent_fd,
            )
            os.close(parent_fd)
            parent_fd = child
        source_fd = os.open(
            path.name, os.O_RDONLY | os.O_NOFOLLOW, dir_fd=parent_fd,
        )
        before = os.fstat(source_fd)
        linked = os.stat(path.name, dir_fd=parent_fd, follow_symlinks=False)
        if (
            not stat.S_ISREG(before.st_mode)
            or before.st_nlink != 1
            or before.st_size > 4 << 20
            or (before.st_dev, before.st_ino) != (linked.st_dev, linked.st_ino)
        ):
            raise Stage12700Error("split_core_source_identity_invalid")
        payload = bytearray()
        while len(payload) < before.st_size:
            block = os.read(source_fd, before.st_size - len(payload))
            if not block:
                raise Stage12700Error("split_core_source_short_read")
            payload.extend(block)
        after = os.fstat(source_fd)
        linked_after = os.stat(
            path.name, dir_fd=parent_fd, follow_symlinks=False,
        )
        identity = (before.st_dev, before.st_ino, before.st_size)
        if (
            identity != (after.st_dev, after.st_ino, after.st_size)
            or identity != (
                linked_after.st_dev, linked_after.st_ino, linked_after.st_size,
            )
        ):
            raise Stage12700Error("split_core_source_changed_during_read")
        digest = hashlib.sha256(payload).hexdigest()
        if digest != expected_sha256:
            raise Stage12700Error("split_core_source_digest_mismatch")
        return bytes(payload), CoreSourceBinding(
            str(path), digest, before.st_dev, before.st_ino, before.st_size,
        )
    finally:
        if source_fd >= 0:
            os.close(source_fd)
        os.close(parent_fd)


def _load_core() -> tuple[types.ModuleType, CoreSourceBinding]:
    payload, binding = _read_pinned_core_source()
    module_name = "stage12694_for_stage12700_" + binding.sha256[:16]
    module = types.ModuleType(module_name)
    module.__file__ = binding.path
    sys.modules[module_name] = module
    code = compile(payload, binding.path, "exec", dont_inherit=True)
    exec(code, module.__dict__)
    return module, binding


CORE, CORE_SOURCE_BINDING = _load_core()


def _revalidate_core_source_identity() -> None:
    _payload_bytes, current = _read_pinned_core_source()
    if current != CORE_SOURCE_BINDING:
        raise Stage12700Error("split_core_source_identity_changed_before_commit")


def stable(value: Any) -> str:
    return CORE.stable(value)


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _canonical_target(target: Any) -> str:
    if isinstance(target, Mapping) and isinstance(target.get("decoder_text"), str):
        return target["decoder_text"]
    if not isinstance(target, Mapping) or not target:
        raise Stage12700Error("private_candidate_target_invalid")
    return json.dumps(target, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _open_absolute_directory(path: Path) -> int:
    if not path.is_absolute() or str(path) != os.path.normpath(str(path)):
        raise Stage12700Error("directory_not_canonical_absolute")
    fd = os.open("/", os.O_RDONLY | os.O_DIRECTORY)
    try:
        for part in path.parts[1:]:
            if not part or part in {".", ".."} or not _SAFE_NAME.fullmatch(part):
                raise Stage12700Error("unsafe_directory_component")
            child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
            os.close(fd)
            fd = child
        return fd
    except BaseException:
        os.close(fd)
        raise


def _open_child_directory(parent_fd: int, name: str) -> int:
    if not _SAFE_NAME.fullmatch(name) or name in {".", ".."}:
        raise Stage12700Error("unsafe_generation_name")
    fd = os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=parent_fd)
    info = os.fstat(fd)
    linked = os.stat(name, dir_fd=parent_fd, follow_symlinks=False)
    if not stat.S_ISDIR(info.st_mode) or (info.st_dev, info.st_ino) != (linked.st_dev, linked.st_ino):
        os.close(fd)
        raise Stage12700Error("generation_identity_mismatch")
    return fd


def _read_file(directory_fd: int, name: str, *, maximum: int, expected_sha256: str | None = None) -> bytes:
    if not _SAFE_NAME.fullmatch(name):
        raise Stage12700Error("unsafe_artifact_name")
    fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW, dir_fd=directory_fd)
    try:
        before = os.fstat(fd)
        linked = os.stat(name, dir_fd=directory_fd, follow_symlinks=False)
        if (
            not stat.S_ISREG(before.st_mode) or before.st_nlink != 1
            or (before.st_dev, before.st_ino) != (linked.st_dev, linked.st_ino)
            or before.st_size > maximum
        ):
            raise Stage12700Error("artifact_identity_or_size_invalid")
        chunks: list[bytes] = []
        remaining = before.st_size
        while remaining:
            block = os.read(fd, min(1 << 20, remaining))
            if not block:
                raise Stage12700Error("artifact_short_read")
            chunks.append(block)
            remaining -= len(block)
        after = os.fstat(fd)
        if (before.st_dev, before.st_ino, before.st_size) != (after.st_dev, after.st_ino, after.st_size):
            raise Stage12700Error("artifact_changed_during_read")
        payload = b"".join(chunks)
        if expected_sha256 is not None and sha(payload) != expected_sha256:
            raise Stage12700Error("artifact_digest_mismatch")
        return payload
    finally:
        os.close(fd)


def _json_object(payload: bytes) -> dict[str, Any]:
    try:
        value = json.loads(payload)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise Stage12700Error("invalid_json_artifact") from error
    if not isinstance(value, dict):
        raise Stage12700Error("json_artifact_not_object")
    return value


def _jsonl(payload: bytes, expected_rows: int) -> tuple[dict[str, Any], ...]:
    rows = []
    for raw in payload.splitlines():
        if not raw:
            raise Stage12700Error("blank_jsonl_record")
        value = _json_object(raw)
        rows.append(value)
    if len(rows) != expected_rows:
        raise Stage12700Error("jsonl_row_count_mismatch")
    return tuple(rows)


def load_public_stage(root: Path, stage: int, *, expected_summary_sha256: str) -> CORE.StageArtifacts:
    if stage not in PUBLIC_FILES:
        raise Stage12700Error("unsupported_public_stage")
    root_fd = _open_absolute_directory(root)
    try:
        summary_payload = _read_file(root_fd, "summary.json", maximum=1 << 20, expected_sha256=expected_summary_sha256)
        summary = _json_object(summary_payload)
        if summary.get("artifact_schema_version") != CORE.STAGE_SCHEMAS[stage]:
            raise Stage12700Error("public_schema_mismatch")
        generation = summary.get("generation_relative_path")
        if not isinstance(generation, str) or generation.split("/") != ["private", summary.get("generation_id")]:
            raise Stage12700Error("public_generation_binding_invalid")
        private_fd = _open_child_directory(root_fd, "private")
        try:
            generation_fd = _open_child_directory(private_fd, summary["generation_id"])
            try:
                records = []
                contract = summary.get("artifact_contract")
                if not isinstance(contract, Mapping):
                    raise Stage12700Error("public_artifact_contract_missing")
                for filename in PUBLIC_FILES[stage]:
                    binding = contract.get(filename)
                    if (
                        not isinstance(binding, Mapping)
                        or binding.get("relative_path") != f"{generation}/{filename}"
                        or not isinstance(binding.get("rows"), int)
                        or not isinstance(binding.get("sha256"), str)
                    ):
                        raise Stage12700Error("public_artifact_binding_invalid")
                    payload = _read_file(
                        generation_fd, filename, maximum=512 << 20,
                        expected_sha256=binding["sha256"],
                    )
                    records.append(_jsonl(payload, binding["rows"]))
            finally:
                os.close(generation_fd)
        finally:
            os.close(private_fd)
    finally:


        os.close(root_fd)
    rows, ledger, catalog = records
    return CORE.StageArtifacts(
        stage, CORE.STAGE_SCHEMAS[stage], rows, ledger, catalog,
        catalog_commitment_sha256=CORE._records_commitment(catalog),
        ledger_commitment_sha256=CORE._records_commitment(ledger),
    )
def _candidate_body_sha256(candidate: Mapping[str, Any]) -> str:
    value = json.loads(json.dumps(candidate))
    proof = value.get("proof")
    if isinstance(proof, dict):
        proof.pop("candidate_body_sha256", None)
    return stable(value)


def _validate_private_bundle(stage: int, bundle: Mapping[str, Any]) -> None:
    expected_type = {
        12698: "stage12698_private_materialization_bundle_v1",
        12699: "stage12699_private_historical_retention_bundle_v1",
    }[stage]
    summary = bundle.get("summary")
    candidates = bundle.get("candidates")
    if (
        bundle.get("record_type") != expected_type
        or not isinstance(summary, Mapping)
        or not isinstance(candidates, list)
        or summary.get("candidate_count") != len(candidates)
        or summary.get("candidate_commitment_sha256") != stable(candidates)
        or summary.get("authority") != AUTHORITY
        or summary.get("training_eligible_rows") != 0
    ):
        raise Stage12700Error("private_bundle_contract_invalid")
    if stage == 12698:
        expected_generation = stable({
            "candidate_commitment_sha256": summary["candidate_commitment_sha256"],
            "stage12696_package_manifest_sha256": summary.get(
                "stage12696_package_manifest_sha256"
            ),
            "stage12697_capacity_commitment_sha256": summary.get(
                "stage12697_capacity_commitment_sha256"
            ),
        })
    else:
        catalog = bundle.get("source_catalog")
        accepted = summary.get("accepted_stage12693_binding_sha256")
        if (
            not isinstance(catalog, list)
            or summary.get("source_catalog_commitment_sha256") != stable(catalog)
            or not isinstance(accepted, str)
            or any(
                candidate.get("proof", {}).get("accepted_stage12693_binding_sha256")
                != accepted
                or candidate.get("proof", {}).get("candidate_body_sha256")
                != _candidate_body_sha256(candidate)
                for candidate in candidates
            )
        ):
            raise Stage12700Error("stage12699_evidence_contract_invalid")
        expected_generation = stable({
            "candidate_commitment_sha256": summary["candidate_commitment_sha256"],
            "source_catalog_commitment_sha256": summary[
                "source_catalog_commitment_sha256"
            ],
            "accepted_stage12693_binding_sha256": accepted,
        })
    if bundle.get("generation_commitment_sha256") != expected_generation:
        raise Stage12700Error("private_generation_commitment_invalid")


def load_private_generation(
    root: Path, generation: str, *, stage: int, expected_bundle_sha256: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    if stage not in {12698, 12699} or not generation.startswith(f"stage{stage}_"):
        raise Stage12700Error("private_generation_stage_mismatch")
    root_fd = _open_absolute_directory(root)
    try:
        generation_fd = _open_child_directory(root_fd, generation)
        try:
            complete = _json_object(_read_file(generation_fd, "COMPLETE", maximum=4096))
            bundle_payload = _read_file(
                generation_fd, "private_materialization.json", maximum=512 << 20,
                expected_sha256=expected_bundle_sha256,
            )
            if complete.get("private_materialization_sha256") != sha(bundle_payload):
                raise Stage12700Error("private_complete_digest_mismatch")
            bundle = _json_object(bundle_payload)
            if (
                complete.get("generation_commitment_sha256") != bundle.get("generation_commitment_sha256")
                or bundle.get("authority") != AUTHORITY
                or any(bundle["authority"].values())
            ):
                raise Stage12700Error("private_generation_commitment_or_authority_invalid")
            _validate_private_bundle(stage, bundle)
            candidates = bundle.get("candidates")
            if not isinstance(candidates, list) or not candidates:
                raise Stage12700Error("private_candidates_missing")
            return bundle, {
                "generation": generation,
                "generation_commitment_sha256": bundle["generation_commitment_sha256"],
                "private_materialization_sha256": sha(bundle_payload),
            }
        finally:
            os.close(generation_fd)
    finally:
        os.close(root_fd)


def _private_objective(stage: int, candidate: Mapping[str, Any]) -> str:
    objective = candidate.get("objective_family")
    if stage == 12698 and objective == "exact_repository_metadata_classification":
        field = candidate.get("target", {}).get("classification_field")
        mapping = {
            "repository_structure": "repository_structure_classification",
            "test_layout_convention": "test_layout_classification",
            "documentation_layout_convention": "documentation_layout_classification",
            "parsed_declaration_class": "parsed_declaration_classification",
        }
        objective = mapping.get(field)
    if not isinstance(objective, str) or objective not in OBJECTIVES:
        raise Stage12700Error("private_objective_invalid")
    return objective


def adapt_private_stage(bundle: Mapping[str, Any], stage: int) -> CORE.StageArtifacts:
    rows: list[dict[str, Any]] = []
    ledger: list[dict[str, Any]] = []
    catalog_by_repo: dict[str, dict[str, Any]] = {}
    for candidate in bundle["candidates"]:
        candidate_authority = candidate.get("authority")
        if (
            not isinstance(candidate, Mapping)
            or not isinstance(candidate_authority, Mapping)
            or any(candidate_authority.values())
        ):
            raise Stage12700Error("private_candidate_authority_invalid")
        proof0 = candidate.get("proof")
        if not isinstance(proof0, Mapping):
            raise Stage12700Error("private_candidate_proof_missing")
        provenance0 = candidate.get("source_provenance", {})
        if not isinstance(provenance0, Mapping):
            raise Stage12700Error("private_candidate_provenance_invalid")
        repo = proof0.get("repository_key_sha256", provenance0.get("repository_key_sha256"))
        component = proof0.get("content_component_sha256", provenance0.get("content_component_sha256"))
        revision = proof0.get("revision", proof0.get("accepted_revision", provenance0.get("revision")))
        if revision is None:
            roots = proof0.get("canonical_root_commit_oids", ())
            revision = roots[0] if isinstance(roots, list) and roots else proof0.get("immutable_commit_git_oid")
        if not isinstance(repo, str) or not isinstance(component, str) or not isinstance(revision, str):
            raise Stage12700Error("private_candidate_lineage_missing")
        input_text = candidate.get("input_text")
        if not isinstance(input_text, str):
            raise Stage12700Error("private_candidate_input_invalid")
        target_text = _canonical_target(candidate.get("target"))
        objective = _private_objective(stage, candidate)
        source_sha = proof0.get(
            "source_file_sha256",
            proof0.get("canonical_tree_entry_inventory_sha256", proof0.get("source_record_sha256")),
        )
        if not isinstance(source_sha, str):
            source_sha = stable(["private_source", stage, proof0])
        row_id = "stage" + str(stage) + "_" + stable([
            "target_independent_row_v1", stage, input_text, repo, component, revision, source_sha,
        ])
        provenance = dict(provenance0)
        provenance.update({
            "repository_key_sha256": repo,
            "content_component_sha256": component,
            "revision": revision,
            "source_file_sha256": source_sha,
        })
        row = {
            "row_id": row_id,
            "split": "train",
            "objective_family": objective,
            "input_text": input_text,
            "target": {"decoder_text": target_text},
            "source_provenance": provenance,
        }
        proof = {
            "row_id": row_id,
            "split": "train",
            "objective_family": objective,
            "repository_key_sha256": repo,
            "content_component_sha256": component,
            "revision": revision,
            "row_sha256": stable(row),
            "model_input_sha256": sha(input_text.encode("utf-8")),
            "target_sha256": sha(target_text.encode("utf-8")),
            "source_file_sha256": source_sha,
            "source_window_sha256": stable(["private_source_window_v1", stage, proof0]),
            "candidate_evidence_sha256": stable(["private_candidate_v1", stage, candidate]),
            "private_source_proof": dict(proof0),
        }
        rows.append(row)
        ledger.append(proof)
        catalog_by_repo.setdefault(repo, {
            "repository_key_sha256": repo,
            "content_component_sha256": component,
            "revision": revision,
            "root_commit_git_oids": [revision],
            "source_file_sha256s": [source_sha],
            "split": "train",
        })
        existing = catalog_by_repo[repo]
        if (existing["content_component_sha256"], existing["revision"]) != (component, revision):
            raise Stage12700Error("private_catalog_lineage_conflict")
        existing["source_file_sha256s"] = sorted(set(existing["source_file_sha256s"] + [source_sha]))
    catalog = tuple(catalog_by_repo[key] for key in sorted(catalog_by_repo))
    return CORE.StageArtifacts(
        stage, 1, tuple(rows), tuple(ledger), catalog,
        catalog_commitment_sha256=CORE._records_commitment(catalog),
        ledger_commitment_sha256=CORE._records_commitment(ledger),
    )


def load_confidential_strict_generation(
    root: Path, generation: str, *, expected_manifest_sha256: str,
) -> tuple[tuple[CORE.StageArtifacts, ...], dict[str, Any]]:
    """Load only Stage12701's descriptor-pinned, committed strict generation."""

    if not re.fullmatch(r"[0-9a-f]{64}", generation):
        raise Stage12700Error("strict_generation_id_invalid")
    root_fd = _open_absolute_directory(root)
    try:
        if os.fstat(root_fd).st_mode & 0o077:
            raise Stage12700Error("strict_root_not_confidential")
        generation_fd = _open_child_directory(root_fd, generation)
        try:
            if os.fstat(generation_fd).st_mode & 0o077:
                raise Stage12700Error("strict_generation_not_confidential")
            complete_payload = _read_file(generation_fd, "COMPLETE", maximum=4096)
            complete = _json_object(complete_payload)
            manifest_payload = _read_file(
                generation_fd, "manifest.json", maximum=1 << 20,
                expected_sha256=expected_manifest_sha256,
            )
            manifest = _json_object(manifest_payload)
            if (
                complete.get("generation_id") != generation
                or complete.get("manifest_sha256") != sha(manifest_payload)
                or manifest.get("generation_id") != generation
                or manifest.get("stage")
                != "stage12701_confidential_strict_knowledge_materialization"
                or manifest.get("schema_version") != 1
                or manifest.get("visibility_class") != "confidential_strict_eval_only"
                or manifest.get("strict_row_count") != EXPECTED_STRICT_ROWS
                or manifest.get("authority") != AUTHORITY
                or any(manifest["authority"].values())
                or manifest.get("training_eligible_rows") != 0
                or manifest.get("plaintext_mirror_materialized") is not False
                or manifest.get("model_selection_access") is not False
            ):
                raise Stage12700Error("strict_manifest_contract_invalid")
            source_entries = manifest.get("source_stages")
            if (
                not isinstance(source_entries, list)
                or [entry.get("stage") for entry in source_entries]
                != list(STRICT_SOURCE_STAGES)
            ):
                raise Stage12700Error("strict_source_stage_set_invalid")
            artifact_contract = manifest.get("artifact_contract")
            expected_names = {
                f"stage{stage}_strict_{kind}.jsonl"
                for stage in STRICT_SOURCE_STAGES
                for kind in ("rows", "proofs", "catalog")
            }
            if (
                not isinstance(artifact_contract, Mapping)
                or set(artifact_contract) != expected_names
                or complete.get("artifact_count") != len(expected_names) + 1
            ):
                raise Stage12700Error("strict_artifact_contract_invalid")
            committed_names = expected_names | {"manifest.json", "COMPLETE"}
            if set(os.listdir(generation_fd)) != committed_names:
                raise Stage12700Error("strict_generation_file_set_invalid")
            if any(
                os.stat(name, dir_fd=generation_fd, follow_symlinks=False).st_mode
                & 0o077
                for name in committed_names
            ):
                raise Stage12700Error("strict_artifact_not_confidential")

            artifacts = []
            for source in source_entries:
                stage = source["stage"]
                count = source.get("strict_row_count")
                snapshot = source.get("validated_snapshot_contract")
                if (
                    not isinstance(count, int) or count <= 0
                    or not isinstance(snapshot, Mapping)
                    or source.get("validated_snapshot_commitment_sha256")
                    != stable(snapshot)
                ):
                    raise Stage12700Error("strict_source_snapshot_invalid")
                loaded = []
                for kind in ("rows", "proofs", "catalog"):
                    name = f"stage{stage}_strict_{kind}.jsonl"
                    binding = artifact_contract[name]
                    if (
                        not isinstance(binding, Mapping)
                        or not isinstance(binding.get("bytes"), int)
                        or not isinstance(binding.get("sha256"), str)
                    ):
                        raise Stage12700Error("strict_artifact_binding_invalid")
                    payload = _read_file(
                        generation_fd, name, maximum=512 << 20,
                        expected_sha256=binding["sha256"],
                    )
                    if len(payload) != binding["bytes"]:
                        raise Stage12700Error("strict_artifact_size_mismatch")
                    expected_rows = (
                        count if kind != "catalog" else len(payload.splitlines())
                    )
                    loaded.append(_jsonl(payload, expected_rows))
                rows, proofs, catalog = loaded
                if (
                    stable(rows) != snapshot.get("strict_rows_sha256")
                    or stable(proofs) != snapshot.get("strict_proofs_sha256")
                    or stable(catalog) != snapshot.get("strict_catalog_sha256")
                    or any(row.get("split") != "strict_eval" for row in rows)
                    or any(proof.get("split") != "strict_eval" for proof in proofs)
                    or any(entry.get("split") != "strict_eval" for entry in catalog)
                ):
                    raise Stage12700Error("strict_snapshot_payload_mismatch")
                artifact = CORE.StageArtifacts(
                    stage, CORE.STAGE_SCHEMAS[stage], rows, proofs, catalog,
                    catalog_commitment_sha256=CORE._records_commitment(catalog),
                    ledger_commitment_sha256=CORE._records_commitment(proofs),
                )
                CORE._validate_input(artifact)
                artifacts.append(artifact)
            if sum(len(item.rows) for item in artifacts) != EXPECTED_STRICT_ROWS:
                raise Stage12700Error("strict_total_row_count_mismatch")
            return tuple(artifacts), {
                "generation_id": generation,
                "manifest_sha256": sha(manifest_payload),
                "complete_sha256": sha(complete_payload),
            }
        finally:
            os.close(generation_fd)
    finally:
        os.close(root_fd)


def combine_authenticated_inputs(
    public: Sequence[CORE.StageArtifacts],
    private: Sequence[CORE.StageArtifacts],
    strict: Sequence[CORE.StageArtifacts],
) -> tuple[tuple[CORE.StageArtifacts, ...], frozenset[str]]:
    public_by_stage = {item.stage: item for item in public}
    private_by_stage = {item.stage: item for item in private}
    strict_by_stage = {item.stage: item for item in strict}
    if (
        set(public_by_stage) != set(STRICT_SOURCE_STAGES)
        or set(strict_by_stage) != set(STRICT_SOURCE_STAGES)
        or set(private_by_stage) != {12698, 12699}
    ):
        raise Stage12700Error("authenticated_source_stage_set_invalid")
    combined = []
    strict_refs: set[str] = set()
    for stage in STRICT_SOURCE_STAGES:
        public_item = public_by_stage[stage]
        strict_item = strict_by_stage[stage]
        if any(row.get("split") == "strict_eval" for row in public_item.rows):
            raise Stage12700Error("public_train_eval_contains_strict_row")
        if any(row.get("split") != "strict_eval" for row in strict_item.rows):
            raise Stage12700Error("confidential_input_contains_non_strict_row")
        rows = tuple(public_item.rows) + tuple(strict_item.rows)
        proofs = tuple(public_item.ledger) + tuple(strict_item.ledger)
        catalog = tuple(public_item.catalog) + tuple(strict_item.catalog)
        combined.append(CORE.StageArtifacts(
            stage, public_item.schema_version, rows, proofs, catalog,
            catalog_commitment_sha256=CORE._records_commitment(catalog),
            ledger_commitment_sha256=CORE._records_commitment(proofs),
        ))
        strict_refs.update(
            f"stage{stage}:{row['row_id']}" for row in strict_item.rows
        )
    combined.extend(private_by_stage[stage] for stage in (12698, 12699))
    return tuple(combined), frozenset(strict_refs)


def build_release(
    inputs: Sequence[CORE.StageArtifacts], *, requested_rows: int,
    source_bindings: Mapping[str, Any],
    authenticated_strict_row_refs: frozenset[str],
    strict_audit: Mapping[str, Any] | None,
) -> dict[str, Any]:
    if requested_rows <= 0 or requested_rows % 10:
        raise Stage12700Error("requested_rows_must_be_positive_multiple_of_ten")
    all_refs = {
        f"stage{item.stage}:{row['row_id']}": row
        for item in inputs for row in item.rows
    }
    actual_strict_refs = frozenset(
        ref for ref, row in all_refs.items() if row.get("split") == "strict_eval"
    )
    if (
        not authenticated_strict_row_refs
        or actual_strict_refs != authenticated_strict_row_refs
        or any(
            int(ref.split(":", 1)[0][5:]) not in STRICT_SOURCE_STAGES
            for ref in actual_strict_refs
        )
    ):
        raise Stage12700Error("strict_rows_not_exactly_authenticated_stage12701_rows")
    plan = CORE.build_locked_global_split_core(
        inputs, requested_rows=requested_rows,
    )
    if any(plan["post_assignment_target_quarantine_split_deficits"].values()):
        raise Stage12700Error("exact_split_geometry_unavailable")
    if any(plan["global_overlap_counts"].values()):
        raise Stage12700Error("cross_split_overlap_nonzero")
    if not plan["source_split_assignments_preserved"]:
        raise Stage12700Error("source_split_assignment_changed")
    lookup = {
        f"stage{item.stage}:{row['row_id']}": (item, row)
        for item in inputs for row in item.rows
    }
    proofs = {
        f"stage{item.stage}:{proof['row_id']}": proof
        for item in inputs for proof in item.ledger
    }
    output_rows = []
    output_proofs = []
    output_catalog = []
    for reference in plan["row_reference_plan"]:
        item, source_row = lookup[reference["row_ref"]]
        source_proof = proofs[reference["row_ref"]]
        row = dict(source_row)
        if source_row["split"] != reference["global_split"]:
            raise Stage12700Error("source_split_assignment_changed")
        row["split"] = source_row["split"]
        row["source_stage"] = item.stage
        row["global_component_id"] = reference["global_component_id"]
        row["release_row_id"] = "stage12700_" + stable([
            "target_independent_release_identity_v1", item.stage,
            source_row["row_id"], reference["global_component_id"],
        ])
        proof = {
            "release_row_id": row["release_row_id"],
            "source_stage": item.stage,
            "source_row_id": source_row["row_id"],
            "global_split": reference["global_split"],
            "global_component_id": reference["global_component_id"],
            "source_row_sha256": stable(source_row),
            "source_proof_sha256": stable(source_proof),
            "release_row_sha256": stable(row),
            "source_proof": source_proof,
        }
        output_rows.append(row)

        provenance = source_row["source_provenance"]
        output_catalog.append({
            "release_row_id": row["release_row_id"],
            "source_stage": item.stage,
            "source_row_id": source_row["row_id"],
            "split": source_row["split"],
            "global_component_id": reference["global_component_id"],
            "repository_key_sha256": provenance["repository_key_sha256"],
            "content_component_sha256": provenance["content_component_sha256"],
            "revision": provenance["revision"],
        })
        output_proofs.append(proof)
    counts = collections.Counter(row["split"] for row in output_rows)
    objectives = collections.Counter(row["objective_family"] for row in output_rows)
    if set(objectives) != OBJECTIVES or any(value <= 0 for value in objectives.values()):
        missing = sorted(OBJECTIVES - set(objectives))
        raise Stage12700Error("required_objective_family_missing:" + ",".join(missing))
    strict_rows = [row for row in output_rows if row["split"] == "strict_eval"]
    audit_ok = (
        PINNED_INDEPENDENT_STRICT_AUDIT_SHA256 is not None
        and isinstance(strict_audit, Mapping)
        and stable(strict_audit) == PINNED_INDEPENDENT_STRICT_AUDIT_SHA256
        and strict_audit.get("decision") == "PASS"
        and strict_audit.get("strict_rows_sha256") == stable(strict_rows)
        and strict_audit.get("reviewer_independent") is True
    )
    result = {
        "stage": STAGE,
        "schema_version": SCHEMA_VERSION,
        "decision": (
            "KNOWLEDGE_DATASET_ADMISSION_ELIGIBLE_EXECUTION_CLOSED"
            if audit_ok else "BLOCKED_INDEPENDENT_STRICT_AUDIT_REQUIRED"
        ),
        "source_stages": list(SOURCE_STAGES),
        "source_bindings": dict(source_bindings),
        "transformation_dag": [
            {"operation": "authenticated_load_and_private_adaptation", "inputs": list(SOURCE_STAGES)},
            {"operation": "target_independent_component_split", "implementation": CORE.STAGE},
            {"operation": "global_quarantine_and_zero_overlap_gate"},
            {"operation": "trainer_row_and_proof_materialization"},
        ],
        "requested_split_counts": plan["requested_split_counts"],
        "materialized_split_counts": {name: counts[name] for name in CORE.SPLITS},
        "objective_counts": dict(sorted(objectives.items())),
        "objective_family_count": len(objectives),
        "global_overlap_counts": plan["global_overlap_counts"],
        "quarantine_ledger": plan["quarantined_rows"],
        "rows": output_rows,
        "proof_ledger": output_proofs,
        "source_catalog": output_catalog,
        "strict_audit": dict(strict_audit) if strict_audit is not None else None,
        "strict_material_present": bool(strict_rows),
        "knowledge_admission_eligible": audit_ok,
        "training_eligible_rows": len(output_rows) if audit_ok else 0,
        "training_execution_authorized": False,
        "authority": dict(AUTHORITY),
    }
    result["release_commitment_sha256"] = stable({
        key: value for key, value in result.items()

        if key not in {"rows", "proof_ledger", "source_catalog", "quarantine_ledger"}
    } | {
        "rows_sha256": stable(output_rows),
        "proof_ledger_sha256": stable(output_proofs),
        "source_catalog_sha256": stable(result["source_catalog"]),
        "quarantine_ledger_sha256": stable(result["quarantine_ledger"]),
    })
    return result
def _rename_noreplace(directory_fd: int, source: str, destination: str) -> None:
    libc = ctypes.CDLL(None, use_errno=True)
    renameat2 = getattr(libc, "renameat2", None)
    if renameat2 is None:
        raise Stage12700Error("renameat2_unavailable")
    renameat2.argtypes = [
        ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p,
        ctypes.c_uint,
    ]
    renameat2.restype = ctypes.c_int
    if renameat2(
        directory_fd, source.encode("ascii"),
        directory_fd, destination.encode("ascii"), 1,
    ) != 0:
        error = ctypes.get_errno()
        if error == errno.EEXIST:
            raise Stage12700Error("publication_destination_collision")
        raise Stage12700Error("publication_rename_failed") from OSError(
            error, os.strerror(error)
        )



def _payload(records: Iterable[Mapping[str, Any]]) -> bytes:
    return b"".join(
        json.dumps(row, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("ascii") + b"\n"
        for row in records
    )


def _write_file(directory_fd: int, name: str, payload: bytes) -> str:
    temporary = "." + name + ".tmp." + secrets.token_hex(12)
    fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=directory_fd)
    try:
        offset = 0
        while offset < len(payload):
            offset += os.write(fd, payload[offset:])
        os.fsync(fd)
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_size != len(payload):
            raise Stage12700Error("published_file_validation_failed")
        _rename_noreplace(directory_fd, temporary, name)
        linked = os.stat(name, dir_fd=directory_fd, follow_symlinks=False)
        if (info.st_dev, info.st_ino) != (linked.st_dev, linked.st_ino):
            raise Stage12700Error("published_file_identity_changed")
        os.fsync(directory_fd)
        return sha(payload)
    finally:
        os.close(fd)


def _validate_release_for_publication(
    result: Mapping[str, Any],
) -> tuple[list[Any], list[Any], list[Any], list[Any]]:
    """Validate an internal release; this function has no persistence authority."""

    if result.get("authority") != AUTHORITY or any(result["authority"].values()):
        raise Stage12700Error("release_authority_not_closed")
    rows = result.get("rows")
    proofs = result.get("proof_ledger")
    catalog = result.get("source_catalog")
    quarantine = result.get("quarantine_ledger")
    if not all(isinstance(value, list) for value in (rows, proofs, catalog, quarantine)):
        raise Stage12700Error("release_payload_shape_invalid")
    row_ids = [row.get("release_row_id") for row in rows]
    proof_ids = [proof.get("release_row_id") for proof in proofs]
    catalog_ids = [entry.get("release_row_id") for entry in catalog]
    if (
        len(set(row_ids)) != len(rows)
        or row_ids != proof_ids
        or row_ids != catalog_ids
        or any(
            row.get("split") != entry.get("split")
            for row, entry in zip(rows, catalog, strict=True)
        )
    ):
        raise Stage12700Error("release_row_proof_catalog_bijection_invalid")
    commitment_view = {
        key: value for key, value in result.items()
        if key not in {
            "rows", "proof_ledger", "source_catalog", "quarantine_ledger",
            "release_commitment_sha256",
        }
    } | {
        "rows_sha256": stable(rows),
        "proof_ledger_sha256": stable(proofs),
        "source_catalog_sha256": stable(catalog),
        "quarantine_ledger_sha256": stable(quarantine),
    }
    if result.get("release_commitment_sha256") != stable(commitment_view):
        raise Stage12700Error("release_commitment_invalid")
    return rows, proofs, catalog, quarantine

def _read_bound_absolute_json(path: Path, expected_sha256: str) -> dict[str, Any]:
    parent_fd = _open_absolute_directory(path.parent)
    try:
        return _json_object(
            _read_file(
                parent_fd, path.name, maximum=1 << 20,
                expected_sha256=expected_sha256,
            )
        )
    finally:
        os.close(parent_fd)


def materialize_and_persist(
    *,
    output_root: Path,
    stage12698_root: Path,
    stage12698_generation: str,
    stage12698_sha256: str,
    stage12699_root: Path,
    stage12699_generation: str,
    stage12699_sha256: str,
    requested_rows: int,
) -> dict[str, Any]:
    """Sole production API: authenticate every source, build, then publish."""

    reviewed = REVIEWED_STAGE12701_BINDING
    if reviewed is None:
        return {
            "stage": STAGE,
            "decision": "BLOCKED_REVIEWED_STAGE12701_BINDING_REQUIRED",
            "publication_performed": False,
            "knowledge_admission_eligible": False,
            "training_eligible_rows": 0,
            "training_execution_authorized": False,
            "authority": dict(AUTHORITY),
        }
    if (
        not isinstance(reviewed, ReviewedStage12701Binding)
        or not os.path.isabs(reviewed.root)
        or reviewed.root != os.path.normpath(reviewed.root)
        or not re.fullmatch(r"[0-9a-f]{64}", reviewed.generation_id)
        or not re.fullmatch(r"[0-9a-f]{64}", reviewed.manifest_sha256)
        or not re.fullmatch(r"[0-9a-f]{64}", reviewed.complete_sha256)
        or reviewed.review_contract
        != "parent_production_and_independent_review_v1"
        or not re.fullmatch(
            r"[0-9a-f]{64}", reviewed.independent_review_sha256,
        )
    ):
        return {
            "stage": STAGE,
            "decision": "BLOCKED_REVIEWED_STAGE12701_BINDING_INVALID",
            "publication_performed": False,
            "knowledge_admission_eligible": False,
            "training_eligible_rows": 0,
            "training_execution_authorized": False,
            "authority": dict(AUTHORITY),
        }

    public = tuple(
        load_public_stage(
            PUBLIC_ROOTS[stage], stage,
            expected_summary_sha256=PUBLIC_SUMMARY_SHA256[stage],
        )
        for stage in sorted(PUBLIC_ROOTS)
    )
    bundle98, binding98 = load_private_generation(
        stage12698_root, stage12698_generation, stage=12698,
        expected_bundle_sha256=stage12698_sha256,
    )
    bundle99, binding99 = load_private_generation(
        stage12699_root, stage12699_generation, stage=12699,
        expected_bundle_sha256=stage12699_sha256,
    )
    strict, binding12701 = load_confidential_strict_generation(
        Path(reviewed.root), reviewed.generation_id,
        expected_manifest_sha256=reviewed.manifest_sha256,
    )
    if binding12701 != {
        "generation_id": reviewed.generation_id,
        "manifest_sha256": reviewed.manifest_sha256,
        "complete_sha256": reviewed.complete_sha256,
    }:
        raise Stage12700Error("reviewed_stage12701_binding_mismatch")
    inputs, strict_refs = combine_authenticated_inputs(
        public,
        (
            adapt_private_stage(bundle98, 12698),
            adapt_private_stage(bundle99, 12699),
        ),
        strict,
    )
    result = build_release(
        inputs,
        requested_rows=requested_rows,
        source_bindings={
            "public_summary_sha256": {
                str(stage): digest
                for stage, digest in sorted(PUBLIC_SUMMARY_SHA256.items())
            },
            "stage12694_split_core": CORE_SOURCE_BINDING.as_dict(),
            "stage12698": binding98,
            "stage12699": binding99,
            "stage12701": binding12701,
            "stage12701_independent_review": {
                "contract": reviewed.review_contract,
                "sha256": reviewed.independent_review_sha256,
            },
            "independent_strict_audit_sha256":
                PINNED_INDEPENDENT_STRICT_AUDIT_SHA256,
        },
        authenticated_strict_row_refs=strict_refs,
        strict_audit=None,
    )
    rows, proofs, catalog, quarantine = _validate_release_for_publication(result)

    def publish_internal_result() -> dict[str, Any]:
        root_fd = _open_absolute_directory(output_root)
        generation = "stage12700_" + result["release_commitment_sha256"][:32]
        temporary = ".pending-" + secrets.token_hex(12)
        generation_fd = -1
        try:
            if os.fstat(root_fd).st_mode & 0o077:
                raise Stage12700Error("output_root_not_confidential")
            os.mkdir(temporary, 0o700, dir_fd=root_fd)
            generation_fd = os.open(
                temporary,
                os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
                dir_fd=root_fd,
            )
            files = {
                "train_eval_rows.jsonl": _payload(
                    row for row in rows if row["split"] != "strict_eval"
                ),
                "strict_eval_rows.jsonl": _payload(
                    row for row in rows if row["split"] == "strict_eval"
                ),
                "proof_ledger.jsonl": _payload(proofs),
                "source_catalog.jsonl": _payload(catalog),
                "quarantine_ledger.jsonl": _payload(quarantine),
            }
            hashes = {
                name: _write_file(generation_fd, name, payload)
                for name, payload in files.items()
            }
            manifest = {
                key: value for key, value in result.items()
                if key not in {
                    "rows", "proof_ledger", "source_catalog", "quarantine_ledger",
                }
            }
            manifest["artifact_sha256"] = hashes
            manifest_payload = json.dumps(
                manifest,
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=True,
            ).encode("ascii") + b"\n"
            manifest_sha = _write_file(
                generation_fd, "release_manifest.json", manifest_payload,
            )
            complete_payload = json.dumps({
                "release_commitment_sha256":
                    result["release_commitment_sha256"],
                "release_manifest_sha256": manifest_sha,
                "artifact_sha256": hashes,
            }, sort_keys=True, separators=(",", ":")).encode("ascii") + b"\n"
            _write_file(generation_fd, "COMPLETE", complete_payload)
            os.fchmod(generation_fd, 0o500)
            os.fsync(generation_fd)
            opened = os.fstat(generation_fd)
            linked = os.stat(
                temporary, dir_fd=root_fd, follow_symlinks=False,
            )
            if (opened.st_dev, opened.st_ino) != (
                linked.st_dev, linked.st_ino,
            ):
                raise Stage12700Error("temporary_generation_replaced")
            os.fsync(root_fd)
            _revalidate_core_source_identity()
            _rename_noreplace(root_fd, temporary, generation)
            return {
                "generation": generation,
                "release_commitment_sha256":
                    result["release_commitment_sha256"],
                "knowledge_admission_eligible":
                    result["knowledge_admission_eligible"],
                "training_execution_authorized": False,
                "authority": dict(AUTHORITY),
            }
        finally:
            if generation_fd >= 0:
                os.close(generation_fd)
            os.close(root_fd)

    return publish_internal_result()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--stage12698-root", type=Path, required=True)
    parser.add_argument("--stage12698-generation", required=True)
    parser.add_argument("--stage12698-sha256", required=True)
    parser.add_argument("--stage12699-root", type=Path, required=True)
    parser.add_argument("--stage12699-generation", required=True)
    parser.add_argument("--stage12699-sha256", required=True)
    parser.add_argument("--requested-rows", type=int, required=True)
    args = parser.parse_args(argv)
    persisted = materialize_and_persist(
        output_root=args.output_root,
        stage12698_root=args.stage12698_root,
        stage12698_generation=args.stage12698_generation,
        stage12698_sha256=args.stage12698_sha256,
        stage12699_root=args.stage12699_root,
        stage12699_generation=args.stage12699_generation,
        stage12699_sha256=args.stage12699_sha256,
        requested_rows=args.requested_rows,
    )
    print(json.dumps(persisted, sort_keys=True))
    return 0


if __name__ == "__main__":
    main()
