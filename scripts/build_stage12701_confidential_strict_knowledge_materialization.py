#!/usr/bin/env python3
"""Replay and transactionally publish the confidential Stage 1 strict corpus."""

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
import sys
import types
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12701_confidential_strict_knowledge_materialization"
SCHEMA_VERSION = 1
EXPECTED_STRICT_ROWS = 9_568
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
RESIDUAL_TRUST_CONTRACT = {
    "contract": "descriptor_pinned_sources_plus_last_precommit_path_inode_revalidation_v1",
    "atomicity_scope": "same-filesystem renameat2(RENAME_NOREPLACE) of a fully fsynced temporary generation",
    "universal_atomicity_claimed": False,
    "hostile_same_uid_concurrent_writers_excluded": True,
    "residual_assumption": "No hostile same-UID writer mutates an already-open source inode or replaces a validated source path after the last pre-rename inode check.",
}
_SAFE_COMPONENT = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,127}")
_ANSWER_PREFIX = re.compile(r"^answer\s*:\s*(?P<answer>.*)$", re.IGNORECASE | re.DOTALL)
_FILL_MARKER = re.compile(
    r"^(?:todo|tbd)(?:[\s:_-]+(?:fill|filled|replace|complete|completion|answer|value|text|here|me|pending|later).*)?$",
    re.IGNORECASE | re.DOTALL,
)
_SENTINEL = re.compile(
    r"^(?:<|\[|\{|__)?(?:placeholder|missing|answer|todo|tbd|fill[_-]?me|to[_-]?be[_-]?filled|n/?a)(?:[_-](?:token|value|text|answer|sentinel|[0-9]+))?(?:>|\]|\}|__)?$",
    re.IGNORECASE,
)
_PLACEHOLDER_IDENTIFIER = re.compile(
    r"^[A-Za-z0-9_]*PLACEHOLDER[A-Za-z0-9_]*$", re.IGNORECASE
)


class Stage12701Error(RuntimeError):
    pass


@dataclass(frozen=True)
class SourceSpec:
    stage: int
    module_name: str
    builder_sha256: str
    summary_sha256: str
    max_repos: int
    max_rows: int
    strict_rows: int
    proof_authentication: str

    @property
    def builder_path(self) -> Path:
        return ROOT / "scripts" / f"{self.module_name}.py"

    @property
    def summary_path(self) -> Path:
        artifact_root = self.module_name.removeprefix("build_")
        return ROOT / "runs/local/artifacts" / artifact_root / "summary.json"


SOURCES = (
    SourceSpec(12687, "build_stage12687_source_backed_python_foundational_corpus", "6c1e7ce23346eff0628307469267648f174a7c15a102aecf55eb56581215e062", "4bc5c1918bee56666ec2eb275f3e72a403e7a3afcce35aad2f9fbc2b7ae3a18d", 601, 20_000, 2_000, "deterministically_replayed_not_originally_committed"),
    SourceSpec(12688, "build_stage12688_source_backed_multilingual_knowledge_corpus", "66bb3fd3c47305f3598f3eb91c9398839614d2ec68b3c3bc36f2fa8e238f490e", "c34c780bd84d167034c7ed392a62f3a618642dec15de6a927dc6fa797f1b7f52", 800, 60_000, 6_000, "deterministically_replayed_not_originally_committed"),
    SourceSpec(12689, "build_stage12689_source_backed_maintenance_history_corpus", "d778b16ccece74b35b63c441d472864a2633f0be0477f2b194f38265b7cea302", "3f97ad79e9bbacf117e500f8be24103c96cf122b1eb4f882af19fe4d3dec2816", 601, 500, 50, "deterministically_replayed_not_originally_committed"),
    SourceSpec(12690, "build_stage12690_source_backed_symbol_api_test_links", "64f0214712bccc739c1ea3c53b2b8d815cd963a8633a5326c19ab523bb5e0549", "5bf05f076e2133086ae189d8bea6f5a8202ebad252a8612f5515787f4ab9d167", 601, 13_000, 1_300, "deterministically_replayed_not_originally_committed"),
    SourceSpec(12691, "build_stage12691_source_backed_python_api_doc_links", "184b611189f78bd4e671f3a2cb50ae3b76722f29555ba53a7175e4bd5b48adef", "3d4eb38f3157563cc5c5fba2a122a5e6ad54d7a151ce761ac89dd0c697dc329e", 601, 300, 30, "accepted_commitment_authenticates_rows_proofs_and_catalog"),
    SourceSpec(12692, "build_stage12692_source_backed_declarative_test_build_conventions", "cf8ce98ad96bdac5cfdfcd65c564f3f49b6a03fa8b6c0e6d1a27a74ec057ba10", "1209f6f4bfbc3fd3338a0478be419b0f9f714228aef740dd18af3fef63b24199", 601, 1_880, 188, "deterministically_replayed_not_originally_committed"),
)


def _sha(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _stable(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return _sha(payload.encode("ascii"))


def _json_bytes(value: Any) -> bytes:
    return (json.dumps(value, sort_keys=True, indent=2, ensure_ascii=True) + "\n").encode("ascii")


def _jsonl_bytes(values: list[dict[str, Any]]) -> bytes:
    return b"".join(
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("ascii") + b"\n"
        for value in values
    )


def _read_frozen_json(path: Path, expected_sha256: str) -> dict[str, Any]:
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    except OSError as error:
        raise Stage12701Error("accepted_summary_open_failed") from error
    try:
        before = os.fstat(fd)
        linked = os.stat(path, follow_symlinks=False)
        if (
            not stat.S_ISREG(before.st_mode)
            or before.st_nlink != 1
            or before.st_size > 1 << 20
            or (before.st_dev, before.st_ino) != (linked.st_dev, linked.st_ino)
        ):
            raise Stage12701Error("accepted_summary_identity_invalid")
        payload = b""
        while len(payload) < before.st_size:
            chunk = os.read(fd, before.st_size - len(payload))
            if not chunk:
                raise Stage12701Error("accepted_summary_short_read")
            payload += chunk
        after = os.fstat(fd)
        if (before.st_dev, before.st_ino, before.st_size) != (after.st_dev, after.st_ino, after.st_size):
            raise Stage12701Error("accepted_summary_changed_during_read")
    finally:
        os.close(fd)
    if _sha(payload) != expected_sha256:
        raise Stage12701Error("accepted_summary_digest_mismatch")
    try:
        value = json.loads(payload)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise Stage12701Error("accepted_summary_invalid_json") from error
    if not isinstance(value, dict):
        raise Stage12701Error("accepted_summary_not_object")
    return value


@dataclass(frozen=True)
class PinnedSource:
    spec: SourceSpec
    payload: bytes
    device: int
    inode: int
    size: int

    def manifest_identity(self) -> dict[str, Any]:
        return {
            "path": os.fspath(self.spec.builder_path),
            "device": self.device,
            "inode": self.inode,
            "size": self.size,
            "sha256": self.spec.builder_sha256,
        }


_MISSING_MODULE = object()
_PRIVATE_STAGE12688_DEPENDENCY = "stage12687_for_stage12688"
_PRIVATE_STAGE12689_DEPENDENCY = "stage12687_history_dependency"


class _PinnedDependencyLoader:
    def __init__(self, source: PinnedSource):
        self.source = source

    def create_module(self, spec: Any) -> None:
        return None

    def exec_module(self, module: Any) -> None:
        module.__file__ = os.fspath(self.source.spec.builder_path)
        module.__package__ = ""
        module.__loader__ = self
        code = compile(
            self.source.payload,
            os.fspath(self.source.spec.builder_path),
            "exec",
            dont_inherit=True,
        )
        exec(code, module.__dict__)
        module.__stage12701_pinned_source_sha256__ = (
            self.source.spec.builder_sha256
        )


@dataclass
class FrozenClosure:
    modules: dict[int, Any]
    sources: dict[int, PinnedSource]
    saved_modules: dict[str, Any]

    def source_manifest(self) -> dict[str, dict[str, Any]]:
        return {
            source.spec.module_name: source.manifest_identity()
            for _, source in sorted(self.sources.items())
        }

    def close(self) -> None:
        for name, previous in self.saved_modules.items():
            if previous is _MISSING_MODULE:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = previous


def _read_pinned_source(spec: SourceSpec) -> PinnedSource:
    flags = os.O_RDONLY | os.O_NOFOLLOW | getattr(os, "O_CLOEXEC", 0)
    try:
        fd = os.open(spec.builder_path, flags)
    except OSError as error:
        raise Stage12701Error(f"stage{spec.stage}_builder_open_failed") from error
    try:
        before = os.fstat(fd)
        linked = os.stat(spec.builder_path, follow_symlinks=False)
        if (
            not stat.S_ISREG(before.st_mode)
            or before.st_nlink != 1
            or before.st_size <= 0
            or before.st_size > 8 << 20
            or (before.st_dev, before.st_ino) != (linked.st_dev, linked.st_ino)
        ):
            raise Stage12701Error(f"stage{spec.stage}_builder_identity_invalid")
        chunks: list[bytes] = []
        remaining = before.st_size
        while remaining:
            chunk = os.read(fd, min(1 << 20, remaining))
            if not chunk:
                raise Stage12701Error(f"stage{spec.stage}_builder_short_read")
            chunks.append(chunk)
            remaining -= len(chunk)
        after = os.fstat(fd)
        if (before.st_dev, before.st_ino, before.st_size) != (
            after.st_dev,
            after.st_ino,
            after.st_size,
        ):
            raise Stage12701Error(f"stage{spec.stage}_builder_changed_during_read")
        payload = b"".join(chunks)
    finally:
        os.close(fd)
    if _sha(payload) != spec.builder_sha256:
        raise Stage12701Error(f"stage{spec.stage}_builder_digest_mismatch")
    return PinnedSource(spec, payload, before.st_dev, before.st_ino, before.st_size)


def _exec_pinned_module(source: PinnedSource) -> Any:
    name = source.spec.module_name
    module = types.ModuleType(name)
    module.__file__ = os.fspath(source.spec.builder_path)
    module.__package__ = ""
    module.__loader__ = None
    module.__spec__ = importlib.util.spec_from_loader(
        name, loader=None, origin=module.__file__
    )
    sys.modules[name] = module
    try:
        code = compile(
            source.payload,
            module.__file__,
            "exec",
            dont_inherit=True,
        )
        exec(code, module.__dict__)
    except BaseException:
        sys.modules.pop(name, None)
        raise
    return module


def _verify_frozen_closure(closure: FrozenClosure) -> None:
    modules = closure.modules
    for spec in SOURCES:
        if sys.modules.get(spec.module_name) is not modules.get(spec.stage):
            raise Stage12701Error(f"stage{spec.stage}_sys_modules_substitution")
    expected_edges = (
        (12688, "trusted", 12687),
        (12689, "S87", 12687),
        (12690, "stage12687", 12687),
        (12691, "stage12690", 12690),
        (12692, "stage12687", 12687),
        (12692, "stage12688", 12688),
        (12692, "stage12690", 12690),
    )
    for owner, attribute, dependency in expected_edges:
        if getattr(modules[owner], attribute, None) is not modules[dependency]:
            raise Stage12701Error(
                f"stage{owner}_transitive_dependency_substitution:{attribute}"
            )


def _load_frozen_closure() -> FrozenClosure:
    sources = {spec.stage: _read_pinned_source(spec) for spec in SOURCES}
    managed_names = [spec.module_name for spec in SOURCES]
    managed_names.append(_PRIVATE_STAGE12688_DEPENDENCY)
    managed_names.append(_PRIVATE_STAGE12689_DEPENDENCY)
    saved = {name: sys.modules.get(name, _MISSING_MODULE) for name in managed_names}
    for name in managed_names:
        sys.modules.pop(name, None)
    modules: dict[int, Any] = {}
    original_read_bytes = Path.read_bytes
    original_spec_from_file_location = importlib.util.spec_from_file_location
    pinned_by_path = {
        os.path.normpath(os.fspath(source.spec.builder_path)): source.payload
        for source in sources.values()
    }

    def pinned_read_bytes(candidate: Path) -> bytes:
        normalized = os.path.normpath(os.fspath(candidate))
        if normalized in pinned_by_path:
            return bytes(pinned_by_path[normalized])
        return original_read_bytes(candidate)

    def pinned_spec_from_file_location(
        name: str, location: Any, *args: Any, **kwargs: Any
    ):
        normalized = os.path.normpath(os.fspath(location))
        stage12687 = sources[12687]
        expected = os.path.normpath(os.fspath(stage12687.spec.builder_path))
        if name == _PRIVATE_STAGE12689_DEPENDENCY and normalized == expected:
            return importlib.util.spec_from_loader(
                name,
                _PinnedDependencyLoader(stage12687),
                origin=os.fspath(stage12687.spec.builder_path),
            )
        return original_spec_from_file_location(name, location, *args, **kwargs)

    Path.read_bytes = pinned_read_bytes
    importlib.util.spec_from_file_location = pinned_spec_from_file_location
    closure = FrozenClosure(modules, sources, saved)
    try:
        for spec in SOURCES:
            module = _exec_pinned_module(sources[spec.stage])
            modules[spec.stage] = module
            if spec.stage == 12688:
                nested = sys.modules.pop(_PRIVATE_STAGE12688_DEPENDENCY, None)
                if nested is None:
                    raise Stage12701Error("stage12688_pinned_dependency_not_executed")
                module.trusted = modules[12687]
            if spec.stage == 12689:
                nested = sys.modules.pop(_PRIVATE_STAGE12689_DEPENDENCY, None)
                if nested is None or getattr(
                    nested, "__stage12701_pinned_source_sha256__", None
                ) != sources[12687].spec.builder_sha256:
                    raise Stage12701Error(
                        "stage12689_pinned_dependency_not_executed"
                    )
                canonical = modules[12687]
                for attribute, value in list(vars(module).items()):
                    if (
                        hasattr(nested, attribute)
                        and value is getattr(nested, attribute)
                    ):
                        setattr(module, attribute, getattr(canonical, attribute))
                module.S87 = canonical
        _verify_frozen_closure(closure)
        return closure
    except BaseException:
        closure.close()
        raise
    finally:
        importlib.util.spec_from_file_location = original_spec_from_file_location
        Path.read_bytes = original_read_bytes

def _prepare_stage(module: Any, spec: SourceSpec, repository_root: Path):
    if spec.stage == 12692:
        if module.DEFAULT_MAX_REPOS != spec.max_repos or module.DEFAULT_MAX_ROWS != spec.max_rows:
            raise Stage12701Error("stage12692_replay_limits_mismatch")
        scan = module.scan_repository_supply(
            repository_root,
            max_repos=spec.max_repos,
            per_repo_cap=module.DEFAULT_PER_REPO_CAP,
        )
        return module.prepare_full_release(scan, spec.max_rows)
    if module.MAX_REPOS != spec.max_repos or module.MAX_ROWS != spec.max_rows:
        raise Stage12701Error(f"stage{spec.stage}_replay_limits_mismatch")
    return module.prepare_release(
        repository_root,
        max_repos=spec.max_repos,
        max_rows=spec.max_rows,
    )


def _placeholder_target(text: str) -> bool:
    candidate = text.strip()
    if not candidate:
        return True
    answer_match = _ANSWER_PREFIX.fullmatch(candidate)
    if answer_match is not None:
        candidate = answer_match.group("answer").strip()
        if not candidate:
            return True
    return bool(
        _SENTINEL.fullmatch(candidate)
        or _FILL_MARKER.fullmatch(candidate)
        or _PLACEHOLDER_IDENTIFIER.fullmatch(candidate)
    )


def _target_text(row: Mapping[str, Any]) -> str:
    target = row.get("target")
    if not isinstance(target, Mapping) or not isinstance(target.get("decoder_text"), str):
        raise Stage12701Error("strict_target_schema_invalid")
    text = target["decoder_text"]
    if _placeholder_target(text):
        raise Stage12701Error("strict_target_placeholder_or_empty")
    return text


def _module_stable(module: Any, value: Any) -> str:
    function = getattr(module, "stable", None)
    if function is None:
        function = getattr(getattr(module, "stage12688", None), "stable", None)
    if function is None:
        raise Stage12701Error("source_stable_function_missing")
    return function(value)


def _canonical_snapshot(value: Any, label: str) -> tuple[Any, bytes]:
    try:
        payload = json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        ).encode("ascii")
        snapshot = json.loads(payload)
    except (TypeError, ValueError, UnicodeError, json.JSONDecodeError) as error:
        raise Stage12701Error(f"{label}_not_canonical_json") from error
    return snapshot, payload


def _required_text(value: Mapping[str, Any], field: str, label: str) -> str:
    result = value.get(field)
    if not isinstance(result, str) or not result:
        raise Stage12701Error(f"{label}_{field}_invalid")
    return result


def _catalog_identity(entry: Mapping[str, Any]) -> tuple[str, str, str, str]:
    repository = _required_text(entry, "repository_key_sha256", "catalog")
    component = _required_text(entry, "content_component_sha256", "catalog")
    revision = _required_text(entry, "revision", "catalog")
    split = _required_text(entry, "split", "catalog")
    if not re.fullmatch(r"[0-9a-f]{64}", repository):
        raise Stage12701Error("catalog_repository_key_sha256_invalid")
    if not re.fullmatch(r"[0-9a-f]{64}", component):
        raise Stage12701Error("catalog_content_component_sha256_invalid")
    if not re.fullmatch(r"[0-9a-f]{40}", revision):
        raise Stage12701Error("catalog_revision_invalid")
    if split not in {"train", "eval", "strict_eval"}:
        raise Stage12701Error("catalog_split_invalid")
    return repository, component, revision, split


def _snapshot_contract(
    rows: list[dict[str, Any]],
    proofs: list[dict[str, Any]],
    catalog: list[dict[str, Any]],
    summary: dict[str, Any],
    payloads: Mapping[str, bytes],
    strict_rows: list[dict[str, Any]],
    strict_proofs: list[dict[str, Any]],
    strict_catalog: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "full_rows_sha256": _stable(rows),
        "full_proofs_sha256": _stable(proofs),
        "full_catalog_sha256": _stable(catalog),
        "summary_sha256": _stable(summary),
        "public_payload_sha256s": {
            name: _sha(payload) for name, payload in sorted(payloads.items())
        },
        "strict_rows_sha256": _stable(strict_rows),
        "strict_proofs_sha256": _stable(strict_proofs),
        "strict_catalog_sha256": _stable(strict_catalog),
    }


def _validated_payloads(stage: Mapping[str, Any]) -> dict[str, bytes]:
    contract = stage.get("validated_snapshot_contract")
    commitment = stage.get("validated_snapshot_commitment_sha256")
    if not isinstance(contract, Mapping) or _stable(contract) != commitment:
        raise Stage12701Error("validated_snapshot_commitment_mismatch")
    rows, _ = _canonical_snapshot(stage.get("rows"), "publication_rows")
    proofs, _ = _canonical_snapshot(stage.get("proofs"), "publication_proofs")
    catalog, _ = _canonical_snapshot(stage.get("catalog"), "publication_catalog")
    if not isinstance(rows, list) or _stable(rows) != contract.get("strict_rows_sha256"):
        raise Stage12701Error("validated_rows_mutated_before_publication")
    if not isinstance(proofs, list) or _stable(proofs) != contract.get("strict_proofs_sha256"):
        raise Stage12701Error("validated_proofs_mutated_before_publication")
    if not isinstance(catalog, list) or _stable(catalog) != contract.get("strict_catalog_sha256"):
        raise Stage12701Error("validated_catalog_mutated_before_publication")
    if len(rows) != stage.get("strict_row_count") or len(proofs) != len(rows):
        raise Stage12701Error("validated_snapshot_count_mismatch")
    return {
        "strict_rows.jsonl": _jsonl_bytes(rows),
        "strict_proofs.jsonl": _jsonl_bytes(proofs),
        "strict_catalog.jsonl": _jsonl_bytes(catalog),
    }


def _validate_prepared(module: Any, spec: SourceSpec, prepared: Any, accepted: dict[str, Any]) -> dict[str, Any]:
    for field in ("rows", "proofs", "catalog", "public_payloads", "summary"):
        if not hasattr(prepared, field):
            raise Stage12701Error(f"stage{spec.stage}_prepared_field_missing:{field}")

    # Snapshot every caller-owned collection before evaluating any relationship.
    rows, _ = _canonical_snapshot(prepared.rows, "prepared_rows")
    proofs, _ = _canonical_snapshot(prepared.proofs, "prepared_proofs")
    catalog, _ = _canonical_snapshot(prepared.catalog, "prepared_catalog")
    summary, _ = _canonical_snapshot(prepared.summary, "prepared_summary")
    accepted_snapshot, _ = _canonical_snapshot(accepted, "accepted_summary")
    if not isinstance(rows, list) or not isinstance(proofs, list) or not isinstance(catalog, list):
        raise Stage12701Error("prepared_collections_not_lists")
    if not isinstance(summary, dict) or not isinstance(accepted_snapshot, dict):
        raise Stage12701Error("prepared_or_accepted_summary_not_object")
    if not isinstance(prepared.public_payloads, Mapping):
        raise Stage12701Error("prepared_public_payloads_not_mapping")
    payloads: dict[str, bytes] = {}
    for name, payload in prepared.public_payloads.items():
        if not isinstance(name, str) or not isinstance(payload, (bytes, bytearray, memoryview)):
            raise Stage12701Error("prepared_public_payload_invalid")
        payloads[name] = bytes(memoryview(payload))

    if summary != accepted_snapshot:
        raise Stage12701Error(f"stage{spec.stage}_public_replay_mismatch")
    if len(rows) != spec.max_rows or len(proofs) != spec.max_rows:
        raise Stage12701Error(f"stage{spec.stage}_full_row_or_proof_count_mismatch")

    catalog_identity_counts: collections.Counter[tuple[str, str, str, str]] = collections.Counter()
    catalog_entry_sha256s: set[str] = set()
    repository_identities: dict[str, tuple[str, str, str, str]] = {}
    for entry in catalog:
        if not isinstance(entry, dict):
            raise Stage12701Error("catalog_entry_not_object")
        identity = _catalog_identity(entry)
        entry_sha256 = _stable(entry)
        if entry_sha256 in catalog_entry_sha256s:
            raise Stage12701Error("catalog_entry_duplicate")
        prior = repository_identities.setdefault(identity[0], identity)
        if prior != identity:
            raise Stage12701Error("catalog_repository_identity_conflict")
        catalog_identity_counts[identity] += 1
        catalog_entry_sha256s.add(entry_sha256)
    if any(
        count > 1 and identity[3] == "strict_eval"
        for identity, count in catalog_identity_counts.items()
    ):
        raise Stage12701Error("strict_catalog_identity_ambiguous")
    catalog_identities = set(catalog_identity_counts)

    row_by_id: dict[str, dict[str, Any]] = {}
    for row in rows:
        if not isinstance(row, dict):
            raise Stage12701Error("row_not_object")
        row_id = _required_text(row, "row_id", "row")
        if row_id in row_by_id:
            raise Stage12701Error("row_identity_duplicate")
        _required_text(row, "split", "row")
        _required_text(row, "objective_family", "row")
        provenance = row.get("source_provenance")
        if not isinstance(provenance, Mapping):
            raise Stage12701Error("row_source_provenance_invalid")
        for field in ("repository_key_sha256", "content_component_sha256", "revision"):
            _required_text(provenance, field, "row_provenance")
        _target_text(row)
        authority = row.get("authority")
        if not isinstance(authority, Mapping) or any(authority.values()):
            raise Stage12701Error("row_authority_open")
        row_by_id[row_id] = row

    proof_by_id: dict[str, dict[str, Any]] = {}
    for proof in proofs:
        if not isinstance(proof, dict):
            raise Stage12701Error("proof_not_object")
        row_id = _required_text(proof, "row_id", "proof")
        if row_id in proof_by_id:
            raise Stage12701Error("proof_identity_duplicate")
        row = row_by_id.get(row_id)
        if row is None:
            raise Stage12701Error("proof_without_matching_row")
        provenance = row["source_provenance"]
        if _required_text(proof, "split", "proof") != row["split"]:
            raise Stage12701Error("row_proof_split_mismatch")
        proof_objective = proof.get("objective_family")
        if proof_objective is None:
            if spec.stage != 12687:
                raise Stage12701Error("proof_objective_family_missing")
        elif proof_objective != row["objective_family"]:
            raise Stage12701Error("row_proof_objective_mismatch")
        for field in ("repository_key_sha256", "content_component_sha256"):
            if _required_text(proof, field, "proof") != provenance[field]:
                raise Stage12701Error(f"row_proof_{field}_mismatch")
        proof_revision = proof.get("revision")
        if proof_revision is None:
            if spec.stage not in {12689, 12690, 12691}:
                raise Stage12701Error("proof_revision_missing")
        elif proof_revision != provenance["revision"]:
            raise Stage12701Error("row_proof_revision_mismatch")
        identity = (
            provenance["repository_key_sha256"],
            provenance["content_component_sha256"],
            provenance["revision"],
            row["split"],
        )
        if identity not in catalog_identities:
            raise Stage12701Error("proof_exact_catalog_identity_missing")
        if _required_text(proof, "row_sha256", "proof") != _module_stable(module, row):
            raise Stage12701Error("proof_row_digest_mismatch")
        for authority_key in ("training_admitted", "strict_eval_admitted", "sealed_eval_admitted"):
            if proof.get(authority_key, False):
                raise Stage12701Error("proof_authority_open")
        proof_by_id[row_id] = proof
    if set(row_by_id) != set(proof_by_id):
        raise Stage12701Error("full_row_proof_bijection_failed")

    row_catalog_identities = {
        (
            row["source_provenance"]["repository_key_sha256"],
            row["source_provenance"]["content_component_sha256"],
            row["source_provenance"]["revision"],
            row["split"],
        )
        for row in rows
    }
    projected_catalog_identities = {
        identity for identity in row_catalog_identities
        if identity[3] == "strict_eval" and identity in catalog_identities
    }

    excluded_source_universe = sorted(set(catalog_identities) - projected_catalog_identities)
    excluded_by_split = {
        split: sorted(identity for identity in excluded_source_universe if identity[3] == split)
        for split in ("train", "eval", "strict_eval")
    }
    catalog_accounting = {
        "contract": "published strict identities are exact row-bound identities; every other full-source identity is source-universe-unselected and excluded_v4",
        "row_bound_identity_count": len(row_catalog_identities),
        "component_member_without_direct_row_count": len(
            projected_catalog_identities - row_catalog_identities
        ),
        "component_member_without_direct_row_identities_sha256": _stable(
            sorted(projected_catalog_identities - row_catalog_identities)
        ),
        "excluded_source_universe_contract": "source-universe-unselected",
        "excluded_source_universe_identity_count": len(excluded_source_universe),
        "excluded_source_universe_identities_sha256": _stable(excluded_source_universe),
        "excluded_source_universe_by_split": {
            split: {
                "identity_count": len(identities),
                "identities_sha256": _stable(identities),
            }
            for split, identities in excluded_by_split.items()
        },
    }

    strict_rows = [row for row in rows if row["split"] == "strict_eval"]
    strict_proofs = [proof for proof in proofs if proof["split"] == "strict_eval"]
    full_strict_catalog = [entry for entry in catalog if entry["split"] == "strict_eval"]
    strict_catalog = [
        entry for entry in catalog if _catalog_identity(entry) in projected_catalog_identities
    ]
    if len(strict_rows) != spec.strict_rows or len(strict_proofs) != spec.strict_rows:
        raise Stage12701Error(f"stage{spec.stage}_reserved_strict_count_mismatch")
    if accepted_snapshot.get("reserved_unmaterialized_strict_row_count") != spec.strict_rows:
        raise Stage12701Error(f"stage{spec.stage}_accepted_strict_count_mismatch")
    if not full_strict_catalog or not strict_catalog:
        raise Stage12701Error(f"stage{spec.stage}_strict_catalog_missing")
    strict_row_ids = {row["row_id"] for row in strict_rows}
    strict_proof_ids = {proof["row_id"] for proof in strict_proofs}
    if strict_row_ids != strict_proof_ids or len(strict_row_ids) != len(strict_rows):
        raise Stage12701Error("strict_row_proof_bijection_failed")

    if spec.stage == 12691:
        commitment = _module_stable(module, {
            "contract": "stage12691_strict_eval_v2",
            "row_sha256s": sorted(_module_stable(module, row) for row in strict_rows),
            "proof_sha256s": sorted(_module_stable(module, proof) for proof in strict_proofs),
            "catalog_sha256s": sorted(
                _module_stable(module, entry) for entry in full_strict_catalog
            ),
        })
    else:
        commitment = _module_stable(module, sorted(proof["row_sha256"] for proof in strict_proofs))
    if commitment != accepted_snapshot.get("strict_eval_commitment_sha256"):
        raise Stage12701Error(f"stage{spec.stage}_strict_commitment_mismatch")

    expected_artifacts = accepted_snapshot.get("artifact_contract") or accepted_snapshot.get("artifact_sha256s")
    if not isinstance(expected_artifacts, Mapping) or set(expected_artifacts) != set(payloads):
        raise Stage12701Error(f"stage{spec.stage}_public_payload_set_mismatch")
    for name, payload in payloads.items():
        expected = expected_artifacts[name]
        expected_hash = expected.get("sha256") if isinstance(expected, Mapping) else expected
        if _sha(payload) != expected_hash:
            raise Stage12701Error(f"stage{spec.stage}_public_payload_hash_mismatch")

    snapshot_contract = _snapshot_contract(
        rows,
        proofs,
        catalog,
        summary,
        payloads,
        strict_rows,
        strict_proofs,
        strict_catalog,
    )
    result = {
        "stage": spec.stage,
        "accepted_generation_id": accepted_snapshot.get("generation_id"),
        "accepted_summary_sha256": spec.summary_sha256,
        "builder_sha256": spec.builder_sha256,
        "replay_limits": {"max_repositories": spec.max_repos, "max_rows": spec.max_rows},
        "strict_row_count": len(strict_rows),
        "accepted_strict_commitment_sha256": commitment,
        "proof_authentication": spec.proof_authentication,
        "catalog_accounting": catalog_accounting,
        "rows": strict_rows,
        "proofs": strict_proofs,
        "catalog": strict_catalog,
        "validated_snapshot_contract": snapshot_contract,
        "validated_snapshot_commitment_sha256": _stable(snapshot_contract),
    }
    _validated_payloads(result)
    return result

def _replay_stage(
    spec: SourceSpec,
    repository_root: Path,
    closure: FrozenClosure,
) -> dict[str, Any]:
    _verify_frozen_closure(closure)
    accepted = _read_frozen_json(spec.summary_path, spec.summary_sha256)
    module = closure.modules[spec.stage]
    prepared = _prepare_stage(module, spec, repository_root)
    result = _validate_prepared(module, spec, prepared, accepted)
    result["transitive_source_closure"] = closure.source_manifest()
    result["transitive_source_closure_sha256"] = _stable(
        result["transitive_source_closure"]
    )
    return result


def _open_absolute_directory(path: Path) -> int:
    if not path.is_absolute() or str(path) != os.path.normpath(str(path)):
        raise Stage12701Error("path_not_canonical_absolute")
    fd = os.open("/", os.O_RDONLY | os.O_DIRECTORY)
    try:
        for part in path.parts[1:]:
            if not _SAFE_COMPONENT.fullmatch(part) or part in {".", ".."}:
                raise Stage12701Error("unsafe_path_component")
            child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
            os.close(fd)
            fd = child
        return fd
    except BaseException:
        os.close(fd)
        raise


def _open_or_create_confidential_root(path: Path) -> tuple[int, int, str, os.stat_result]:
    if path == Path("/") or not path.is_absolute() or str(path) != os.path.normpath(str(path)):
        raise Stage12701Error("confidential_root_not_canonical_absolute")
    parent = path.parent
    name = path.name
    if not _SAFE_COMPONENT.fullmatch(name):
        raise Stage12701Error("confidential_root_name_invalid")
    parent_fd = _open_absolute_directory(parent)
    try:
        try:
            os.mkdir(name, 0o700, dir_fd=parent_fd)
        except FileExistsError:
            pass
        root_fd = os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=parent_fd)
        opened = os.fstat(root_fd)
        linked = os.stat(name, dir_fd=parent_fd, follow_symlinks=False)
        if not stat.S_ISDIR(opened.st_mode) or (opened.st_dev, opened.st_ino) != (linked.st_dev, linked.st_ino):
            os.close(root_fd)
            raise Stage12701Error("confidential_root_identity_invalid")
        os.fchmod(root_fd, 0o700)
        os.fsync(root_fd)
        os.fsync(parent_fd)
        return parent_fd, root_fd, name, opened
    except BaseException:
        os.close(parent_fd)
        raise


def _write_file(directory_fd: int, name: str, payload: bytes) -> dict[str, Any]:
    if not _SAFE_COMPONENT.fullmatch(name):
        raise Stage12701Error("publication_filename_invalid")
    fd = os.open(name, os.O_RDWR | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=directory_fd)
    try:
        view = memoryview(payload)
        while view:
            written = os.write(fd, view)
            if written <= 0:
                raise Stage12701Error("publication_short_write")
            view = view[written:]
        os.fsync(fd)
        opened = os.fstat(fd)
        linked = os.stat(name, dir_fd=directory_fd, follow_symlinks=False)
        if not stat.S_ISREG(opened.st_mode) or opened.st_nlink != 1 or (opened.st_dev, opened.st_ino) != (linked.st_dev, linked.st_ino):
            raise Stage12701Error("publication_file_identity_invalid")
        os.lseek(fd, 0, os.SEEK_SET)
        digest = hashlib.sha256()
        remaining = opened.st_size
        while remaining:
            block = os.read(fd, min(1 << 20, remaining))
            if not block:
                raise Stage12701Error("publication_file_short_read")
            digest.update(block)
            remaining -= len(block)
        if digest.hexdigest() != _sha(payload):
            raise Stage12701Error("publication_file_digest_mismatch")
        os.fchmod(fd, 0o400)
        os.fsync(fd)
        return {"bytes": len(payload), "sha256": digest.hexdigest()}
    finally:
        os.close(fd)


def _rename_noreplace(directory_fd: int, source: str, destination: str) -> None:
    libc = ctypes.CDLL(None, use_errno=True)
    renameat2 = getattr(libc, "renameat2", None)
    if renameat2 is None:
        raise Stage12701Error("renameat2_unavailable")
    renameat2.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint]
    renameat2.restype = ctypes.c_int
    if renameat2(directory_fd, os.fsencode(source), directory_fd, os.fsencode(destination), 1) != 0:
        code = ctypes.get_errno()
        reason = "publication_generation_collision" if code == errno.EEXIST else "publication_rename_failed"
        raise Stage12701Error(reason) from OSError(code, os.strerror(code))


def _close_suppress(fd: int) -> None:
    if fd < 0:
        return
    try:
        os.close(fd)
    except BaseException:
        # Descriptor cleanup is postcommit housekeeping and cannot revoke a rename.
        pass


def _revalidate_transitive_source_paths(replayed: list[dict[str, Any]]) -> None:
    expected_names = {spec.module_name for spec in SOURCES}
    manifests = [stage.get("transitive_source_closure") for stage in replayed]
    if not manifests or not all(isinstance(value, Mapping) for value in manifests):
        raise Stage12701Error("transitive_source_closure_missing")
    first = manifests[0]
    if set(first) != expected_names or any(value != first for value in manifests[1:]):
        raise Stage12701Error("transitive_source_closure_inconsistent")
    if any(stage.get("transitive_source_closure_sha256") != _stable(first) for stage in replayed):
        raise Stage12701Error("transitive_source_closure_commitment_mismatch")
    seen_paths: set[str] = set()
    for name, identity in sorted(first.items()):
        if not isinstance(identity, Mapping):
            raise Stage12701Error("transitive_source_identity_invalid")
        path_text = identity.get("path")
        if (
            not isinstance(path_text, str)
            or not os.path.isabs(path_text)
            or path_text != os.path.normpath(path_text)
            or path_text in seen_paths
        ):
            raise Stage12701Error("transitive_source_path_invalid")
        seen_paths.add(path_text)
        try:
            fd = os.open(path_text, os.O_RDONLY | os.O_NOFOLLOW | getattr(os, "O_CLOEXEC", 0))
        except OSError as error:
            raise Stage12701Error("transitive_source_path_revalidation_open_failed") from error
        try:
            opened = os.fstat(fd)
            linked = os.stat(path_text, follow_symlinks=False)
            expected = (identity.get("device"), identity.get("inode"), identity.get("size"))
            actual = (opened.st_dev, opened.st_ino, opened.st_size)
            if (
                not stat.S_ISREG(opened.st_mode)
                or opened.st_nlink != 1
                or actual != expected
                or (opened.st_dev, opened.st_ino) != (linked.st_dev, linked.st_ino)
            ):
                raise Stage12701Error("transitive_source_path_inode_changed")
        finally:
            os.close(fd)


def _publish(output_root: Path, replayed: list[dict[str, Any]]) -> dict[str, Any]:
    total = sum(stage["strict_row_count"] for stage in replayed)
    if total != EXPECTED_STRICT_ROWS or [stage["stage"] for stage in replayed] != [spec.stage for spec in SOURCES]:
        raise Stage12701Error("combined_strict_supply_mismatch")
    manifest_stages = [
        {key: value for key, value in stage.items() if key not in {"rows", "proofs", "catalog"}}
        for stage in replayed
    ]
    payloads: dict[str, bytes] = {}
    for stage in replayed:
        prefix = f"stage{stage['stage']}"
        # This fresh canonical snapshot is the final check before serialization.
        stage_payloads = _validated_payloads(stage)
        for suffix, payload in stage_payloads.items():
            payloads[f"{prefix}_{suffix}"] = payload
    artifact_contract = {
        name: {"bytes": len(payload), "sha256": _sha(payload)}
        for name, payload in sorted(payloads.items())
    }
    generation_id = _stable([STAGE, SCHEMA_VERSION, manifest_stages, artifact_contract])
    manifest = {
        "stage": STAGE,
        "schema_version": SCHEMA_VERSION,
        "generation_id": generation_id,
        "visibility_class": "confidential_strict_eval_only",
        "strict_row_count": total,
        "source_stages": manifest_stages,
        "artifact_contract": artifact_contract,
        "proof_authentication_caveat": "Stages12687-12690 and 12692 replay proofs/catalogs deterministically but their accepted releases committed only strict row hashes.",
        "model_selection_access": False,
        "plaintext_mirror_materialized": False,
        "training_eligible_rows": 0,
        "authority": dict(AUTHORITY),
        "publication_residual_trust_contract": dict(RESIDUAL_TRUST_CONTRACT),
    }
    payloads["manifest.json"] = _json_bytes(manifest)
    parent_fd, root_fd, root_name, root_identity = _open_or_create_confidential_root(output_root)
    temporary = f".pending-{secrets.token_hex(12)}"
    generation_fd = -1
    try:
        os.mkdir(temporary, 0o700, dir_fd=root_fd)
        generation_fd = os.open(temporary, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=root_fd)
        for name, payload in sorted(payloads.items()):
            _write_file(generation_fd, name, payload)
        complete = _json_bytes({
            "generation_id": generation_id,
            "manifest_sha256": _sha(payloads["manifest.json"]),
            "artifact_count": len(payloads),
        })
        _write_file(generation_fd, "COMPLETE", complete)
        os.fchmod(generation_fd, 0o500)
        os.fsync(generation_fd)
        linked_temp = os.stat(temporary, dir_fd=root_fd, follow_symlinks=False)
        opened_temp = os.fstat(generation_fd)
        if (opened_temp.st_dev, opened_temp.st_ino) != (linked_temp.st_dev, linked_temp.st_ino):
            raise Stage12701Error("temporary_generation_replaced")
        linked_root = os.stat(root_name, dir_fd=parent_fd, follow_symlinks=False)
        current_root = os.fstat(root_fd)
        if (
            (current_root.st_dev, current_root.st_ino) != (root_identity.st_dev, root_identity.st_ino)
            or (current_root.st_dev, current_root.st_ino) != (linked_root.st_dev, linked_root.st_ino)
        ):
            raise Stage12701Error("confidential_root_replaced")
        os.fsync(root_fd)
        os.fsync(parent_fd)
        # This source-path inode check is deliberately the last precommit operation.
        _revalidate_transitive_source_paths(replayed)
        # Atomic no-replace rename is the final fallible operation and commit point.
        _rename_noreplace(root_fd, temporary, generation_id)
        return manifest
    finally:
        _close_suppress(generation_fd)
        _close_suppress(root_fd)
        _close_suppress(parent_fd)

def materialize_and_persist(repository_root: Path, confidential_output_root: Path) -> dict[str, Any]:
    """Sole production API: replay all sources, then publish one private generation."""
    repository_root = Path(repository_root)
    confidential_output_root = Path(confidential_output_root)
    if not repository_root.is_absolute() or str(repository_root) != os.path.normpath(str(repository_root)):
        raise Stage12701Error("repository_root_not_canonical_absolute")
    repository_fd = _open_absolute_directory(repository_root)
    repository_identity = os.fstat(repository_fd)
    os.close(repository_fd)
    closure = _load_frozen_closure()
    published = False
    try:
        replayed = [
            _replay_stage(spec, repository_root, closure) for spec in SOURCES
        ]
        repository_fd = _open_absolute_directory(repository_root)
        try:
            after = os.fstat(repository_fd)
            if (after.st_dev, after.st_ino) != (repository_identity.st_dev, repository_identity.st_ino):
                raise Stage12701Error("repository_root_replaced_during_replay")
        finally:
            os.close(repository_fd)
        result = _publish(confidential_output_root, replayed)
        published = True
        return result
    finally:
        try:
            closure.close()
        except BaseException:
            if not published:
                raise


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repository-root", type=Path, required=True)
    parser.add_argument("--confidential-output-root", type=Path, required=True)
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    print(json.dumps(materialize_and_persist(args.repository_root, args.confidential_output_root), indent=2, sort_keys=True))
