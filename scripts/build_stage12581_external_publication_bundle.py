#!/usr/bin/env python3
"""Build a fixed, local-only external-publication request for Stage12580."""
from __future__ import annotations

import hashlib
import json
import os
import stat
import subprocess
from pathlib import Path, PurePosixPath
from typing import Any, Callable, Mapping, NamedTuple, Sequence

ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12581_external_publication_bundle"
OUT = ROOT / "runs/local/artifacts" / STAGE
SUMMARY = ROOT / "runs/summaries" / f"{STAGE}.json"
VERSION = "1"

BUNDLE_DOMAIN = "agentkernel.stage12581.ordered-external-publication-bundle"
LEAF_DOMAIN = "agentkernel.stage12581.external-publication-bundle-leaf"
ROOT_DOMAIN = "agentkernel.stage12581.external-publication-bundle-root"


class FileSpec(NamedTuple):
    ordinal: int
    role: str
    path: str
    sha256: str
    size_bytes: int
    media_type: str = "application/json"


FILE_SPECS = (
    FileSpec(
        0,
        "stage12579_required_acquisition_request_dependency",
        "runs/local/artifacts/stage12579_bounded_source_native_replacement_acquisition/acquisition_requests.json",
        "5e74ea058e780dd4b945a894d4c2dce232345148fd6f676657631e7c170ae072",
        14633,
    ),
    FileSpec(
        1,
        "stage12580_unpublished_local_identity_preimage_zero_credit",
        "runs/local/artifacts/stage12580_identity_stratum_preoutcome_commitment/identity_stratum_commitment.json",
        "be01d87200542b7914119f87262113d5e742a9249e254b831734bb573cad7d64",
        11907,
    ),
    FileSpec(
        2,
        "stage12580_ordered_sanitized_identity_manifest",
        "runs/local/artifacts/stage12580_identity_stratum_preoutcome_commitment/ordered_identity_stratum_manifest.json",
        "1008b35f3eda71cd63a7403434037231e4d90bbc9dc047b032b03f537335c015",
        4181,
    ),
)
EXPECTED_PATHS = tuple(spec.path for spec in FILE_SPECS)
MAX_FILE_BYTES = 32 * 1024
MAX_BUNDLE_BYTES = 64 * 1024
ALLOWED_MEDIA_TYPES = frozenset({"application/json"})
ALLOWED_SUFFIXES = frozenset({".json"})
RUNTIME_WEIGHT_SUFFIXES = frozenset({
    ".bin", ".ckpt", ".gguf", ".h5", ".onnx", ".pt", ".pth", ".safetensors",
})
PRIVATE_OR_RAW_COMPONENTS = frozenset({
    "private", "raw", "raw_data", "secrets", "restricted", "checkpoints", "weights",
})
OUTCOME_KEYS = frozenset({
    "accuracy", "correct", "correctness", "eval_result", "evaluation_result", "gold",
    "gold_label", "loss", "metric", "metrics", "model_score", "outcome", "prediction",
    "reward", "score", "scores", "target_label", "test_outcome", "test_result",
    "verifier_outcome", "verifier_result",
})
PRIVATE_OR_RAW_KEYS = frozenset({
    "private_data", "private_rows", "raw_data", "raw_dataset", "raw_rows", "secret",
    "secrets", "runtime_weights", "model_weights", "checkpoint_weights",
})
FORBIDDEN_CONTENT_KEYS = OUTCOME_KEYS | PRIVATE_OR_RAW_KEYS

FALSE_GATES = (
    "publication_authority", "publication_allowed", "external_publication_authorized",
    "external_publication_performed", "external_timestamp_present", "acquisition_allowed",
    "acquisition_execution_allowed", "authority", "authority_granted", "preoutcome_authority",
    "requested_commit_authoritative", "execution_authorized", "training", "training_authority",
    "training_allowed", "eval", "eval_authority", "eval_allowed", "evaluation_authority",
    "evaluation_allowed", "admission", "admission_authority", "admission_allowed",
    "clearance", "clearance_authority", "clearance_granted",
)
STATUS_BLOCKERS = (
    "acquisition_blocked",
    "external_timestamp_absent",
    "publication_not_yet_performed",
)


class DuplicateKeyError(ValueError):
    pass


def stable_hash(value: Any) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("ascii")
    return hashlib.sha256(raw).hexdigest()


def canonical_json_bytes(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True, ensure_ascii=True) + "\n").encode("ascii")


def _object_without_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise DuplicateKeyError(key)
        result[key] = value
    return result


def _forbidden_key_paths(value: Any, prefix: str = "$") -> list[str]:
    found: list[str] = []
    if isinstance(value, Mapping):
        for key, child in value.items():
            path = f"{prefix}.{key}"
            if str(key).lower() in FORBIDDEN_CONTENT_KEYS:
                found.append(path)
            found.extend(_forbidden_key_paths(child, path))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            found.extend(_forbidden_key_paths(child, f"{prefix}[{index}]"))
    return found


def _path_policy_reasons(path_text: str) -> list[str]:
    reasons: list[str] = []
    path = PurePosixPath(path_text)
    if path.is_absolute() or ".." in path.parts or str(path) != path_text:
        reasons.append("noncanonical_or_escaping_path")
    lowered = {part.lower() for part in path.parts}
    if lowered & PRIVATE_OR_RAW_COMPONENTS:
        reasons.append("private_or_raw_path_rejected")
    if path.suffix.lower() in RUNTIME_WEIGHT_SUFFIXES:
        reasons.append("runtime_weight_type_rejected")
    if path.suffix.lower() not in ALLOWED_SUFFIXES:
        reasons.append("file_type_not_allowlisted")
    return reasons


def _git_check_ignore_argv(relative_path: str) -> list[str]:
    return ["git", "check-ignore", "--quiet", "--no-index", "--", relative_path]


def _default_ignore_check(root: Path, relative_path: str) -> bool:
    completed = subprocess.run(
        _git_check_ignore_argv(relative_path),
        cwd=root,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    if completed.returncode not in (0, 1):
        raise RuntimeError("git_check_ignore_failed")
    return completed.returncode == 0


def _read_regular_file_once(root: Path, spec: FileSpec) -> tuple[bytes | None, list[str]]:
    reasons = _path_policy_reasons(spec.path)
    candidate = root / spec.path
    current = root
    try:
        for component in PurePosixPath(spec.path).parts:
            current = current / component
            mode = current.lstat().st_mode
            if stat.S_ISLNK(mode):
                reasons.append("symlink_rejected")
                return None, sorted(set(reasons))
        flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
        fd = os.open(candidate, flags)
    except FileNotFoundError:
        reasons.append("required_file_missing")
        return None, sorted(set(reasons))
    except OSError:
        reasons.append("required_file_unreadable")
        return None, sorted(set(reasons))
    try:
        before = os.fstat(fd)
        if not stat.S_ISREG(before.st_mode):
            reasons.append("non_regular_file_rejected")
            return None, sorted(set(reasons))
        if before.st_size > MAX_FILE_BYTES:
            reasons.append("file_too_large")
            return None, sorted(set(reasons))
        chunks: list[bytes] = []
        remaining = MAX_FILE_BYTES + 1
        while remaining:
            chunk = os.read(fd, min(remaining, 65536))
            if not chunk:
                break
            chunks.append(chunk)
            remaining -= len(chunk)
        raw = b"".join(chunks)
        after = os.fstat(fd)
        if (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns) != (
            after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns
        ):
            reasons.append("file_changed_during_read")
            return None, sorted(set(reasons))
        return raw, sorted(set(reasons))
    finally:
        os.close(fd)


def _validate_file(
    root: Path,
    spec: FileSpec,
    ignore_check: Callable[[Path, str], bool],
) -> tuple[dict[str, Any] | None, Any, list[str]]:
    raw, reasons = _read_regular_file_once(root, spec)
    if raw is None:
        return None, None, reasons
    digest = hashlib.sha256(raw).hexdigest()
    if digest != spec.sha256:
        reasons.append("selected_file_sha256_mismatch")
    if len(raw) != spec.size_bytes:
        reasons.append("selected_file_size_mismatch")
    if len(raw) > MAX_FILE_BYTES:
        reasons.append("file_too_large")
    if spec.media_type not in ALLOWED_MEDIA_TYPES:
        reasons.append("media_type_not_allowlisted")
    try:
        parsed = json.loads(raw.decode("utf-8"), object_pairs_hook=_object_without_duplicate_keys)
    except (UnicodeDecodeError, json.JSONDecodeError, DuplicateKeyError):
        parsed = None
        reasons.append("invalid_or_ambiguous_json")
    if parsed is not None:
        if not isinstance(parsed, Mapping):
            reasons.append("top_level_json_type_rejected")
        if canonical_json_bytes(parsed) != raw:
            reasons.append("noncanonical_json_bytes")
        if _forbidden_key_paths(parsed):
            reasons.append("forbidden_outcome_private_or_raw_field")
    try:
        if ignore_check(root, spec.path):
            reasons.append("git_ignored_file_rejected")
    except Exception:
        reasons.append("git_ignore_status_unavailable")
    entry = {
        "ordinal": spec.ordinal,
        "role": spec.role,
        "path": spec.path,
        "media_type": spec.media_type,
        "size_bytes": len(raw),
        "sha256": digest,
    }
    return entry, parsed, sorted(set(reasons))


def _cross_file_reasons(documents: Sequence[Any]) -> list[str]:
    if len(documents) != 3 or not all(isinstance(item, Mapping) for item in documents):
        return ["required_dependency_set_unavailable"]
    dependency, commitment, manifest = documents
    reasons: list[str] = []
    if dependency.get("request_count") != 8 or dependency.get("network_clone_performed") is not False:
        reasons.append("stage12579_dependency_not_accepted_request_ledger")
    audit = commitment.get("audit_only_stage12579_validation")
    if not isinstance(audit, Mapping) or audit.get("stage12579_file_sha256") != FILE_SPECS[0].sha256:
        reasons.append("stage12579_dependency_link_mismatch")
    if not isinstance(audit, Mapping) or audit.get("stage12579_file_pin_valid") is not True:
        reasons.append("stage12579_dependency_pin_not_valid")
    if commitment.get("local_identity_preimage_constructed") is not True:
        reasons.append("stage12580_unpublished_local_identity_preimage_not_constructed")
    preimage = commitment.get("commitment_preimage")
    if not isinstance(preimage, Mapping) or stable_hash(preimage) != commitment.get("commitment_root_sha256"):
        reasons.append("stage12580_commitment_root_mismatch")
    rows = commitment.get("ordered_manifest")
    expected_manifest_preimage = {
        "domain": manifest.get("domain"),
        "version": manifest.get("version"),
        "rows": rows,
    }
    if manifest.get("rows") != rows or stable_hash(expected_manifest_preimage) != commitment.get("ordered_manifest_sha256"):
        reasons.append("stage12580_ordered_manifest_link_mismatch")
    if manifest.get("ordered_manifest_sha256") != commitment.get("ordered_manifest_sha256"):
        reasons.append("stage12580_ordered_manifest_hash_mismatch")
    for document in (commitment, manifest):
        for key in (
            "externally_published", "trusted_timestamp", "acquisition_execution_allowed",
            "training_allowed", "evaluation_allowed", "admission_allowed", "clearance_granted",
        ):
            if document.get(key) is not False:
                reasons.append(f"nonzero_prior_stage_gate:{key}")
    return sorted(set(reasons))


def _status_fields() -> dict[str, bool]:
    return {
        "publication_not_yet_performed": True,
        "external_timestamp_absent": True,
        "acquisition_blocked": True,
        **{key: False for key in FALSE_GATES},
    }


def _scope_fields() -> dict[str, Any]:
    return {
        "content_only_publication_bundle": True,
        "clean_clone_reproducible": False,
        "implementation_and_tests_included": False,
        "local_bundle_valid_scope": "byte_integrity_and_cross_file_linkage_only",
    }


def _transparency_fields(*, read_only_validation_performed: bool) -> dict[str, Any]:
    return {
        "read_only_git_validation_performed": read_only_validation_performed,
        "read_only_git_validation_argv": [_git_check_ignore_argv(path) for path in EXPECTED_PATHS],
        "write_capable_git_execution_performed": False,
        "publication_git_argv_emitted": False,
        "publication_git_execution_performed": False,
        "embedded_unexecuted_acquisition_argv_present": True,
        "embedded_acquisition_argv_executed": False,
    }


def _blocked(extra_reasons: Sequence[str]) -> dict[str, Any]:
    reasons = sorted(set(extra_reasons) | set(STATUS_BLOCKERS))
    body = {
        "stage": STAGE,
        "record_type": "stage12581_external_publication_request_v1",
        "decision": "external_publication_bundle_rejected",
        "local_bundle_valid": False,
        "ordered_files": [],
        "ordered_bundle_sha256": None,
        "bundle_root_sha256": None,
        "total_size_bytes": 0,
        "file_count": 0,
        "blocking_reasons": reasons,
        **_scope_fields(),
        **_transparency_fields(read_only_validation_performed=False),
        **_status_fields(),
    }
    return {**body, "summary_record_sha256": stable_hash(body)}


def _build_fixed(
    root: Path,
    ignore_check: Callable[[Path, str], bool] = _default_ignore_check,
) -> dict[str, Any]:
    entries: list[dict[str, Any]] = []
    documents: list[Any] = []
    reasons: list[str] = []
    for spec in FILE_SPECS:
        entry, parsed, file_reasons = _validate_file(root, spec, ignore_check)
        if entry is not None:
            entries.append(entry)
        documents.append(parsed)
        reasons.extend(f"{spec.path}:{reason}" for reason in file_reasons)
    if sum(entry["size_bytes"] for entry in entries) > MAX_BUNDLE_BYTES:
        reasons.append("bundle_too_large")
    if len(entries) == len(FILE_SPECS):
        reasons.extend(_cross_file_reasons(documents))
    else:
        reasons.append("required_dependency_set_unavailable")
    if reasons:
        return _blocked(reasons)

    leaf_hashes = [stable_hash({"domain": LEAF_DOMAIN, "version": VERSION, **entry}) for entry in entries]
    bundle_preimage = {"domain": BUNDLE_DOMAIN, "version": VERSION, "files": entries}
    root_preimage = {
        "domain": ROOT_DOMAIN,
        "version": VERSION,
        "ordered_leaf_sha256": leaf_hashes,
    }
    body = {
        "stage": STAGE,
        "record_type": "stage12581_external_publication_request_v1",
        "decision": "content_only_publication_bundle_constructed_unpublished_zero_credit",
        "local_bundle_valid": True,
        "ordered_files": entries,
        "ordered_leaf_sha256": leaf_hashes,
        "ordered_bundle_sha256": stable_hash(bundle_preimage),
        "bundle_root_sha256": stable_hash(root_preimage),
        "hash_construction": {
            "canonical_metadata_encoding": "utf8_json_sort_keys_compact_ascii",
            "file_digest_encoding": "sha256_exact_file_bytes",
            "ordered_bundle_domain": BUNDLE_DOMAIN,
            "leaf_domain": LEAF_DOMAIN,
            "root_domain": ROOT_DOMAIN,
        },
        "total_size_bytes": sum(entry["size_bytes"] for entry in entries),
        "file_count": len(entries),
        "blocking_reasons": list(STATUS_BLOCKERS),
        **_scope_fields(),
        **_transparency_fields(read_only_validation_performed=True),
        **_status_fields(),
    }
    return {**body, "summary_record_sha256": stable_hash(body)}


def build_stage(*, file_paths: Sequence[str] | None = None) -> dict[str, Any]:
    if file_paths is not None:
        paths = [str(path) for path in file_paths]
        reasons = ["caller_file_list_rejected"]
        if tuple(paths) != EXPECTED_PATHS:
            reasons.append("caller_file_list_mismatch")
        for path in paths:
            if path not in EXPECTED_PATHS:
                reasons.append("unrelated_path_rejected")
            reasons.extend(_path_policy_reasons(path))
        return _blocked(reasons)
    return _build_fixed(ROOT)


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(canonical_json_bytes(value))


def bundle_manifest(result: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "stage": STAGE,
        "record_type": "stage12581_external_publication_bundle_manifest_v1",
        "local_bundle_valid": result["local_bundle_valid"],
        "ordered_files": result["ordered_files"],
        "ordered_bundle_sha256": result["ordered_bundle_sha256"],
        "bundle_root_sha256": result["bundle_root_sha256"],
        "total_size_bytes": result["total_size_bytes"],
        "file_count": result["file_count"],
        "blocking_reasons": result["blocking_reasons"],
        "summary_record_sha256": result["summary_record_sha256"],
        **_scope_fields(),
        **_transparency_fields(read_only_validation_performed=result["read_only_git_validation_performed"]),
        **_status_fields(),
    }


def write_artifacts(result: Mapping[str, Any]) -> None:
    write_json(OUT / "external_publication_bundle_manifest.json", bundle_manifest(result))
    write_json(OUT / "external_publication_request.json", result)
    write_json(OUT / "summary.json", result)
    write_json(SUMMARY, result)


def main() -> int:
    result = build_stage()
    write_artifacts(result)
    print(json.dumps({key: result[key] for key in (
        "decision", "local_bundle_valid", "ordered_bundle_sha256", "bundle_root_sha256",
        "publication_not_yet_performed", "external_timestamp_absent", "acquisition_blocked",
        "blocking_reasons",
    )}, sort_keys=True))
    return 0 if result["local_bundle_valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
