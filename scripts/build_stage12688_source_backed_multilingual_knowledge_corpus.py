#!/usr/bin/env python3
"""Build byte-exact multilingual knowledge rows from pinned Git snapshots."""

from __future__ import annotations

import argparse
import collections
import copy
import ctypes
import errno
import hashlib
import heapq
import math
import importlib.util
import json
import os
import re
import stat
import sys
import unicodedata
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any, Iterable, Mapping

trusted_path = Path(__file__).with_name("build_stage12687_source_backed_python_foundational_corpus.py")
trusted_raw = trusted_path.read_bytes()
if hashlib.sha256(trusted_raw).hexdigest() != "6c1e7ce23346eff0628307469267648f174a7c15a102aecf55eb56581215e062":
    raise RuntimeError("stage12687_helper_digest_mismatch")
trusted_spec = importlib.util.spec_from_file_location("stage12687_for_stage12688", trusted_path)
if trusted_spec is None or trusted_spec.loader is None:
    raise RuntimeError("stage12687_helper_import_unavailable")
trusted = importlib.util.module_from_spec(trusted_spec)
sys.modules[trusted_spec.name] = trusted
try:
    exec(compile(trusted_raw, os.fspath(trusted_path), "exec", dont_inherit=True), trusted.__dict__)
except BaseException:
    sys.modules.pop(trusted_spec.name, None)
    raise


ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12688_source_backed_multilingual_knowledge_corpus"
DEFAULT_SOURCE_ROOT = Path("/arxiv/repositories")
DEFAULT_OUT = ROOT / "runs/local/artifacts" / STAGE
DEFAULT_SUMMARY = ROOT / "runs/summaries" / f"{STAGE}.json"
ACQUISITION_DATE = "2026-08-02"

MAX_REPOS = 800
MAX_FILES_PER_REPO = 240
MAX_ROWS = 60_000
MAX_ROWS_PER_FILE = 3
MAX_ROWS_PER_REPO = 240
MIN_FILE_BYTES = 24
MAX_FILE_BYTES = 200_000
MIN_TARGET_BYTES = 4
MAX_TARGET_BYTES = 640
CONTEXT_BYTES_EACH_SIDE = 900
MAX_INPUT_CHARS = 2_400
MASK = "<MASKED_EXACT_SPAN>"
DIRECTORY_ENTRY_MASK = "<MASKED_DIRECTORY_ENTRY_NAME>"

REQUIRED_RETENTION_LANGUAGES = (
    "python",
    "javascript_typescript",
    "go",
    "rust",
    "java",
    "c_cpp",
    "shell",
    "markdown",
    "restructuredtext",
    "json",
    "toml",
    "yaml",
)
MIN_STRICT_ROWS_PER_REQUIRED_LANGUAGE = 100
MIN_STRICT_REPOSITORIES_PER_REQUIRED_LANGUAGE = 10
FORK_GROUPING_CONTRACT_VERSION = "practical_exact_lineage_rare_object_v1"
MIN_SHARED_SEEDING_OBJECTS = 8
MIN_SHARED_SEEDING_BYTES = 32 * 1024
MIN_SHARED_SUPPORTED_PLACEMENTS = 2
MIN_WEIGHTED_SMALLER_OBJECT_CONTAINMENT = 0.80
MIN_PLACEMENT_CONTAINMENT = 0.70
MIN_WEIGHTED_JACCARD = 0.50
HIGH_CONFIDENCE_OBJECT_CONTAINMENT = 0.95
ALLOCATION_SEARCH_STATE_BUDGET = 500_000
ALLOCATION_SEARCH_MEMORY_BUDGET = 500_000
ALLOCATION_SEARCH_WORK_BUDGET = 2_000_000
RETENTION_OBJECTIVE_FAMILIES = (
    "multilingual_exact_source_span_infilling",
    "exact_pinned_immediate_directory_entry_name_completion",
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

EXCLUDED_PARTS = trusted.EXCLUDED_PARTS | frozenset({
    ".cache", ".idea", ".mypy_cache", ".next", ".pytest_cache", ".ruff_cache",
    ".vscode", "coverage", "fixtures", "migrations", "snapshots", "target",
})
GENERATED_BASENAMES = frozenset({
    "cargo.lock", "composer.lock", "package-lock.json", "pnpm-lock.yaml",
    "poetry.lock", "yarn.lock",
})
GENERATED_PATH_MARKERS = (
    ".generated.", ".min.js", ".min.css", "_pb2.py", "_pb2_grpc.py",
    ".designer.cs", ".g.cs", "/gen/", "/generated/",
)
PLACEHOLDER_RE = re.compile(
    r"(?:\bTODO\b|\bFIXME\b|\bTBD\b|Answer:\s*$|"
    r"raise\s+NotImplementedError|^\s*(?:pass|\.\.\.)\s*(?:#.*)?$)",
    re.IGNORECASE | re.MULTILINE,
)
UNRESOLVED_SENTINEL_RE = re.compile(
    r"(?<![A-Za-z0-9_])(?:PLACEHOLDER|(?:[A-Z][A-Z0-9]*_)+PLACEHOLDER)(?![A-Za-z0-9_])"
)


def rejected_target_marker(value: str) -> bool:
    return bool(PLACEHOLDER_RE.search(value) or UNRESOLVED_SENTINEL_RE.search(value))


BUILD_BASENAMES: dict[str, str] = {
    "build.gradle": "gradle",
    "build.gradle.kts": "gradle_kotlin",
    "build.xml": "xml",
    "build.zig": "zig",
    "cargo.toml": "toml",
    "cmakelists.txt": "cmake",
    "dockerfile": "dockerfile",
    "gemfile": "ruby",
    "go.mod": "go_module",
    "go.sum": "go_module",
    "justfile": "just",
    "makefile": "make",
    "meson.build": "meson",
    "package.json": "json",
    "pom.xml": "xml",
    "pyproject.toml": "toml",
    "requirements.txt": "requirements",
    "setup.cfg": "ini",
    "setup.py": "python",
    "tox.ini": "ini",
    "workspace": "bazel",
}
BUILD_SUFFIXES: dict[str, str] = {
    ".bzl": "bazel", ".gradle": "gradle", ".mk": "make",
}
LANGUAGE_SUFFIXES: dict[str, str] = {
    ".bash": "shell",
    ".c": "c_cpp",
    ".cc": "c_cpp",
    ".cfg": "ini",
    ".cmake": "cmake",
    ".cpp": "c_cpp",
    ".cxx": "c_cpp",
    ".go": "go",
    ".h": "c_cpp",
    ".hh": "c_cpp",
    ".hpp": "c_cpp",
    ".htm": "html",
    ".html": "html",
    ".ini": "ini",
    ".java": "java",
    ".js": "javascript_typescript",
    ".json": "json",
    ".jsx": "javascript_typescript",
    ".ksh": "shell",
    ".md": "markdown",
    ".mjs": "javascript_typescript",
    ".py": "python",
    ".rst": "restructuredtext",
    ".rs": "rust",
    ".sh": "shell",
    ".toml": "toml",
    ".ts": "javascript_typescript",
    ".tsx": "javascript_typescript",
    ".xhtml": "html",
    ".xml": "xml",
    ".yaml": "yaml",
    ".yml": "yaml",
    ".zsh": "shell",
}
DOC_NAMES = frozenset({"authors", "changelog", "changes", "contributing", "history", "readme"})


class Stage12688Error(RuntimeError):
    pass


Blob = trusted.Blob
UnionFind = trusted.UnionFind
sha256_bytes = trusted.sha256_bytes
stable = trusted.stable
verify_blob_oid = trusted.verify_blob_oid
secure_atomic_write = trusted.secure_atomic_write
open_directory_nofollow = trusted.open_directory_nofollow
file_sha256 = trusted.file_sha256


@dataclass(frozen=True)
class FileKind:
    language_family: str
    file_role: str


@dataclass(frozen=True)
class TreeEntry:
    mode: str
    object_type: str
    oid: str
    size: int | None
    path: str


@dataclass(frozen=True)
class DirectoryInventory:
    parent_path: str
    tree_oid: str
    entries: tuple[TreeEntry, ...]


@dataclass
class RepoSnapshot:
    local_path: Path
    repo_key: str
    origin_url: str
    revision: str
    tree_oid: str
    blobs: list[Blob]
    component_objects: tuple[tuple[str, str, int | None], ...]
    lineage_keys: tuple[str, ...]
    tree_entries: tuple[TreeEntry, ...] = ()
    supported_placements: tuple[tuple[tuple[str, str, int | None], str, str], ...] = ()
    directory_inventories: dict[str, DirectoryInventory] | None = None
    estimated_row_capacity: int = 0
    license_path: str = ""
    license_oid: str = ""
    license_id: str = "unknown"
    license_sha256: str = ""
    component_key: str = ""
    split: str = ""


def git(repo: Path, *args: str, timeout: int = 60) -> bytes:
    try:
        return trusted.git(repo, *args, timeout=timeout)
    except trusted.Stage12687Error as exc:
        raise Stage12688Error(str(exc)) from exc


def parse_ls_tree(data: bytes) -> list[TreeEntry]:
    entries: list[TreeEntry] = []
    for record in data.split(b"\0"):
        if not record:
            continue
        try:
            header, raw_path = record.split(b"\t", 1)
            mode, object_type, oid, raw_size = header.decode("ascii").split()
            path = raw_path.decode("utf-8")
            size = None if raw_size == "-" else int(raw_size)
        except (UnicodeDecodeError, ValueError) as exc:
            raise Stage12688Error("malformed_ls_tree_record") from exc
        if object_type not in {"blob", "commit", "tree"}:
            raise Stage12688Error(f"unsupported_ls_tree_object_type:{object_type}")
        if not re.fullmatch(r"[0-7]{6}", mode) or not trusted.REVISION_RE.fullmatch(oid):
            raise Stage12688Error("malformed_ls_tree_identity")
        if object_type == "blob" and size is None:
            raise Stage12688Error("blob_size_missing")
        if object_type in {"commit", "tree"} and size is not None:
            raise Stage12688Error("nonblob_object_size_present")
        entries.append(TreeEntry(mode, object_type, oid, size, path))
    return entries


def cat_blobs(repo: Path, blobs: list[Blob]) -> dict[str, bytes]:
    try:
        return trusted.cat_blobs(repo, blobs)
    except trusted.Stage12687Error as exc:
        raise Stage12688Error(str(exc)) from exc


def sanitize_origin(raw: str) -> str:
    return trusted.sanitize_origin(raw)


def read_untrusted_origin_metadata(repo: Path) -> str:
    try:
        raw = git(repo, "config", "--get", "remote.origin.url").decode("utf-8")
    except (Stage12688Error, UnicodeDecodeError):
        return ""
    return sanitize_origin(raw)


def canonical_git_path(path: str) -> bool:
    return bool(path) and not (
        path.startswith("/") or path.endswith("/") or "//" in path or "\\" in path
        or any(unicodedata.category(character) == "Cc" for character in path)
    ) and all(part not in {"", ".", ".."} for part in path.split("/"))


def classify_path(path: str) -> FileKind | None:
    if not canonical_git_path(path):
        return None
    pure = PurePosixPath(path)
    lower_parts = tuple(part.lower() for part in pure.parts)
    if set(lower_parts).intersection(EXCLUDED_PARTS):
        return None
    lower = path.lower()
    name = lower_parts[-1]
    if name in GENERATED_BASENAMES or any(marker in f"/{lower}" for marker in GENERATED_PATH_MARKERS):
        return None
    if name in BUILD_BASENAMES:
        return FileKind(BUILD_BASENAMES[name], "build")
    if name.startswith("dockerfile") or name.startswith("makefile"):
        return FileKind("dockerfile" if name.startswith("dockerfile") else "make", "build")
    suffix = pure.suffix.lower()
    if suffix in BUILD_SUFFIXES:
        return FileKind(BUILD_SUFFIXES[suffix], "build")
    language = LANGUAGE_SUFFIXES.get(suffix)
    if language is None:
        return None
    stem = pure.stem.lower()
    if any(part in {"test", "tests", "spec", "specs", "testing"} for part in lower_parts) or re.search(
        r"(?:^|[_.-])(?:test|tests|spec)(?:[_.-]|$)", name
    ):
        role = "test"
    elif language in {"markdown", "restructuredtext"} or stem in DOC_NAMES or "docs" in lower_parts:
        role = "documentation"
    elif language in {"json", "toml", "yaml", "ini", "xml"}:
        role = "config"
    else:
        role = "code"
    return FileKind(language, role)


def content_rejection_reason(data: bytes) -> str | None:
    if not (MIN_FILE_BYTES <= len(data) <= MAX_FILE_BYTES):
        return "size"
    if b"\x00" in data:
        return "binary"
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        return "malformed_utf8"
    controls = sum(ord(char) < 32 and char not in "\n\r\t\f" for char in text)
    if controls > max(1, len(text) // 200):
        return "binary_controls"
    if trusted.contains_high_confidence_secret(data):
        return "secret"
    if trusted.generated_content(data):
        return "generated"
    if UNRESOLVED_SENTINEL_RE.search(text):
        return "unresolved_sentinel"
    if not text.strip() or PLACEHOLDER_RE.fullmatch(text.strip()):
        return "stub_placeholder"
    return None


def normalized_without_whitespace(value: str) -> str:
    return "".join(value.split())


def candidate_spans(data: bytes, repo_key: str, path: str) -> list[tuple[int, int]]:
    spans: list[tuple[int, int]] = []
    cursor = 0
    for line in data.splitlines(keepends=True):
        start, end = cursor, cursor + len(line)
        cursor = end
        stripped = line.strip()
        if not (MIN_TARGET_BYTES <= len(line) <= MAX_TARGET_BYTES) or not stripped:
            continue
        try:
            target = line.decode("utf-8")
        except UnicodeDecodeError:
            continue
        if MASK in target or DIRECTORY_ENTRY_MASK in target or rejected_target_marker(target):
            continue
        spans.append((start, end))
    return heapq.nsmallest(
        MAX_ROWS_PER_FILE, spans,
        key=lambda span: (stable([repo_key, path, span[0], span[1]]), span),
    )


def _utf8_boundary(data: bytes, offset: int, *, forward: bool) -> int:
    offset = max(0, min(offset, len(data)))
    if forward:
        while offset < len(data) and data[offset] & 0xC0 == 0x80:
            offset += 1
    else:
        while offset > 0 and offset < len(data) and data[offset] & 0xC0 == 0x80:
            offset -= 1
    return offset


def build_span_row(
    snapshot: RepoSnapshot,
    blob: Blob,
    kind: FileKind,
    data: bytes,
    span: tuple[int, int],
    source_file_sha256: str | None = None,
) -> tuple[dict[str, Any], dict[str, Any]] | None:
    start, end = span
    left = _utf8_boundary(data, start - CONTEXT_BYTES_EACH_SIDE, forward=True)
    right = _utf8_boundary(data, end + CONTEXT_BYTES_EACH_SIDE, forward=True)
    try:
        before = data[left:start].decode("utf-8")
        target = data[start:end].decode("utf-8")
        after = data[end:right].decode("utf-8")
    except UnicodeDecodeError:
        return None
    input_text = (
        f"repository_relative_path: {blob.path}\n"
        f"file_role: {kind.file_role}\n"
        f"language_family: {kind.language_family}\n"
        f"<VERIFIED_SOURCE>\n{before}{MASK}{after}</VERIFIED_SOURCE>"
    )
    normalized_target = normalized_without_whitespace(target)
    if (
        not normalized_target
        or len(input_text) > MAX_INPUT_CHARS
        or input_text.count(MASK) != 1
        or normalized_target in normalized_without_whitespace(input_text)
        or rejected_target_marker(target)
    ):
        return None
    reconstructed_window = before + target + after
    expected = (
        f"repository_relative_path: {blob.path}\n"
        f"file_role: {kind.file_role}\n"
        f"language_family: {kind.language_family}\n"
        f"<VERIFIED_SOURCE>\n{reconstructed_window}</VERIFIED_SOURCE>"
    )
    if input_text.replace(MASK, target, 1) != expected:
        raise Stage12688Error("source_window_reconstruction_failure")
    if data[:start] + target.encode("utf-8") + data[end:] != data:
        raise Stage12688Error("source_blob_reinsertion_failure")
    return _make_row_and_proof(
        snapshot=snapshot,
        blob=blob,
        kind=kind,
        input_text=input_text,
        target=target,
        objective="multilingual_exact_source_span_infilling",
        source_file_sha256=source_file_sha256 or sha256_bytes(data),
        source_window_sha256=sha256_bytes(reconstructed_window.encode("utf-8")),
        span_start=start,
        span_end=end,
        reinsertion_contract="verified_git_blob_byte_exact_span_v1",
    )


def tree_object_identity(entry: TreeEntry) -> tuple[str, str, int | None]:
    return (entry.object_type, entry.oid, entry.size)


def render_tree_entry(entry: TreeEntry) -> str:
    size = "-" if entry.size is None else str(entry.size)
    return f"{entry.mode} {entry.object_type} {entry.oid} {size}\t{entry.path}"


def canonical_entry_name(name: str) -> bool:
    return (
        bool(name)
        and name not in {".", ".."}
        and "/" not in name
        and "\\" not in name
        and not any(ord(char) < 32 or 127 <= ord(char) <= 159 for char in name)
        and DIRECTORY_ENTRY_MASK not in name
        and not rejected_target_marker(name)
    )


def discover_directory_inventories(
    repo: Path,
    revision: str,
    root_tree_oid: str,
    selected: Iterable[Blob],
) -> dict[str, DirectoryInventory]:
    inventories: dict[str, DirectoryInventory] = {}
    parent_paths = sorted({str(PurePosixPath(blob.path).parent) for blob in selected})
    for parent_path in parent_paths:
        if parent_path != "." and (
            not canonical_git_path(parent_path) or rejected_target_marker(parent_path)
        ):
            raise Stage12688Error("noncanonical_parent_directory")
        object_spec = revision + "^{tree}" if parent_path == "." else f"{revision}:{parent_path}"
        try:
            tree_oid = git(repo, "rev-parse", "--verify", object_spec).decode("ascii").strip().lower()
        except UnicodeDecodeError as exc:
            raise Stage12688Error("invalid_parent_tree_oid") from exc
        if not trusted.REVISION_RE.fullmatch(tree_oid):
            raise Stage12688Error("invalid_parent_tree_oid")
        if parent_path == "." and tree_oid != root_tree_oid:
            raise Stage12688Error("root_tree_oid_mismatch")
        immediate = parse_ls_tree(git(repo, "ls-tree", "-l", "-z", object_spec))
        if any(not canonical_entry_name(entry.path) for entry in immediate):
            raise Stage12688Error("noncanonical_immediate_directory_entry")
        if len({entry.path for entry in immediate}) != len(immediate):
            raise Stage12688Error("duplicate_immediate_directory_entry")
        entries = tuple(sorted(immediate, key=lambda entry: entry.path.encode("utf-8")))
        inventories[parent_path] = DirectoryInventory(parent_path, tree_oid, entries)
    return inventories


def repository_content_identity(
    revision: str, tree_oid: str, entries: Iterable[TreeEntry]
) -> str:
    inventory = sorted(
        (entry.mode, entry.object_type, entry.oid, entry.size, entry.path)
        for entry in entries
    )
    return stable(["revision_tree_object_inventory_v1", revision, tree_oid, inventory])


def build_directory_entry_row(
    snapshot: RepoSnapshot,
    target_blob: Blob,
    source_file_sha256: str = "",
) -> tuple[dict[str, Any], dict[str, Any]] | None:
    parent_path = str(PurePosixPath(target_blob.path).parent)
    inventory = (snapshot.directory_inventories or {}).get(parent_path)
    if inventory is None:
        return None
    entries = inventory.entries
    if (
        inventory.parent_path != parent_path
        or not trusted.REVISION_RE.fullmatch(inventory.tree_oid)
        or any(not canonical_entry_name(entry.path) for entry in entries)
    ):
        raise Stage12688Error("noncanonical_immediate_directory_inventory")
    target_name = PurePosixPath(target_blob.path).name
    if not canonical_entry_name(target_name):
        raise Stage12688Error("noncanonical_target_entry_name")
    target_indexes = [
        index for index, entry in enumerate(entries)
        if entry.path == target_name
        and entry.object_type == "blob"
        and entry.oid == target_blob.oid
    ]
    if len(target_indexes) != 1 or len(entries) < 3:
        return None
    target_index = target_indexes[0]
    target_entry = entries[target_index]
    names = tuple(entry.path for entry in entries)
    visible = list(names)
    visible[target_index] = DIRECTORY_ENTRY_MASK
    input_text = (
        f"parent_directory: {parent_path}\n"
        "<PINNED_IMMEDIATE_DIRECTORY_ENTRY_NAMES>\n"
        + "\n".join(visible)
        + "\n</PINNED_IMMEDIATE_DIRECTORY_ENTRY_NAMES>"
    )
    normalized_target = normalized_without_whitespace(target_name)
    if (
        len(input_text) > MAX_INPUT_CHARS
        or input_text.count(DIRECTORY_ENTRY_MASK) != 1
        or not normalized_target
        or normalized_target in normalized_without_whitespace(input_text)
    ):
        return None
    reconstructed = visible.copy()
    reconstructed[target_index] = target_name
    if tuple(reconstructed) != names:
        raise Stage12688Error("immediate_directory_entry_name_reconstruction_failure")
    kind = classify_path(target_blob.path)
    if kind is None:
        raise Stage12688Error("classified_directory_target_lost")
    return _make_row_and_proof(
        snapshot=snapshot,
        blob=target_blob,
        kind=kind,
        input_text=input_text,
        target=target_name,
        objective="exact_pinned_immediate_directory_entry_name_completion",
        source_file_sha256=source_file_sha256,
        source_window_sha256=stable(visible),
        span_start=None,
        span_end=None,
        reinsertion_contract="pinned_immediate_directory_ordered_entry_name_completion_v1",
        parent_tree_oid=inventory.tree_oid,
        target_object_mode=target_entry.mode,
        target_object_type=target_entry.object_type,
        target_object_oid=target_entry.oid,
        immediate_directory_inventory_sha256=stable([
            (entry.mode, entry.object_type, entry.oid, entry.size, entry.path)
            for entry in entries
        ]),
    )


def _make_row_and_proof(
    *,
    snapshot: RepoSnapshot,
    blob: Blob,
    kind: FileKind,
    input_text: str,
    target: str,
    objective: str,
    source_file_sha256: str,
    source_window_sha256: str,
    span_start: int | None,
    span_end: int | None,
    reinsertion_contract: str,
    parent_tree_oid: str = "",
    target_object_mode: str = "",
    target_object_type: str = "",
    target_object_oid: str = "",
    immediate_directory_inventory_sha256: str = "",
) -> tuple[dict[str, Any], dict[str, Any]]:
    if rejected_target_marker(target):
        raise Stage12688Error("rejected_marker_in_final_target")
    target_sha = sha256_bytes(target.encode("utf-8"))
    row_id = "stage12688_" + stable([
        snapshot.repo_key, objective, blob.path, span_start, span_end, target_sha,
    ])[:24]
    provenance = {
        "source_stage": STAGE,
        "origin_url": snapshot.origin_url,
        "origin_url_trust": "untrusted_mutable_metadata_not_used_for_identity_or_split",
        "origin_url_sha256": (
            sha256_bytes(snapshot.origin_url.encode("utf-8")) if snapshot.origin_url else ""
        ),
        "revision": snapshot.revision,
        "repository_key_sha256": snapshot.repo_key,
        "content_component_sha256": snapshot.component_key,
        "repository_relative_path": blob.path,
        "git_tree_oid": snapshot.tree_oid,
        "git_blob_oid": blob.oid,
        "source_file_sha256": source_file_sha256,
        "source_window_sha256": source_window_sha256,
        "parent_directory": str(PurePosixPath(blob.path).parent) if parent_tree_oid else "",
        "parent_tree_oid": parent_tree_oid,
        "target_object_mode": target_object_mode,
        "target_object_type": target_object_type,
        "target_object_oid": target_object_oid,
        "immediate_directory_inventory_sha256": immediate_directory_inventory_sha256,
        "target_sha256": target_sha,
        "span_start_byte": span_start,
        "span_end_byte": span_end,
        "file_role": kind.file_role,
        "reinsertion_contract": reinsertion_contract,
        "acquisition_date": ACQUISITION_DATE,
    }
    row = {
        "row_id": row_id,
        "split": snapshot.split,
        "language_family": kind.language_family,
        "objective_family": objective,
        "input_text": input_text,
        "target": {"decoder_text": target},
        "loss_mask": {"decoder_ce": True},
        "source_provenance": provenance,
        "authority": dict(AUTHORITY),
    }
    proof = {
        "row_id": row_id,
        "row_sha256": stable(row),
        "encoder_input_sha256": sha256_bytes(input_text.encode("utf-8")),
        "model_example_sha256": stable([input_text, target]),
        "semantic_example_sha256": stable([
            objective, normalized_without_whitespace(input_text), normalized_without_whitespace(target),
        ]),
        "split": snapshot.split,
        "objective_family": objective,
        "language_family": kind.language_family,
        "file_role": kind.file_role,
        "repository_key_sha256": snapshot.repo_key,
        "content_component_sha256": snapshot.component_key,
        "revision": snapshot.revision,
        "git_tree_oid": snapshot.tree_oid,
        "git_blob_oid": blob.oid,
        "repository_relative_path_sha256": sha256_bytes(blob.path.encode("utf-8")),
        "source_file_sha256": source_file_sha256,
        "source_window_sha256": source_window_sha256,
        "parent_directory": str(PurePosixPath(blob.path).parent) if parent_tree_oid else "",
        "parent_tree_oid": parent_tree_oid,
        "target_object_mode": target_object_mode,
        "target_object_type": target_object_type,
        "target_object_oid": target_object_oid,
        "immediate_directory_inventory_sha256": immediate_directory_inventory_sha256,
        "target_sha256": target_sha,
        "span_start_byte": span_start,
        "span_end_byte": span_end,
        "byte_exact_source_span_reinsertion_verified": objective == "multilingual_exact_source_span_infilling",
        "exact_pinned_immediate_directory_entry_name_completion_verified": (
            objective == "exact_pinned_immediate_directory_entry_name_completion"
        ),
        "input_target_whitespace_normalized_overlap": False,
        "training_admitted": False,
        "strict_eval_admitted": False,
        "sealed_eval_admitted": False,
    }
    return row, proof


def discover_repositories(source_root: Path, max_repos: int) -> tuple[list[RepoSnapshot], collections.Counter[str]]:
    counters: collections.Counter[str] = collections.Counter()
    snapshots: list[RepoSnapshot] = []
    try:
        repositories = sorted((path for path in source_root.iterdir() if path.is_dir()), key=lambda path: path.name)
    except OSError as exc:
        raise Stage12688Error(f"source_root_unreadable:{source_root}") from exc
    for repo in repositories:
        if len(snapshots) >= max_repos:
            break
        counters["repository_directories_seen"] += 1
        if not (repo / ".git").exists():
            counters["without_git"] += 1
            continue
        try:
            revision = git(repo, "rev-parse", "--verify", "HEAD").decode("ascii").strip().lower()
            origin = read_untrusted_origin_metadata(repo)
            entries = parse_ls_tree(git(repo, "ls-tree", "-r", "-l", "-z", revision))
            tree_oid = git(repo, "rev-parse", revision + "^{tree}").decode("ascii").strip().lower()
            roots = git(repo, "rev-list", "--max-parents=0", revision).decode("ascii").splitlines()
            is_shallow = git(repo, "rev-parse", "--is-shallow-repository").decode("ascii").strip()
        except (Stage12688Error, UnicodeDecodeError):
            counters["git_metadata_failure"] += 1
            continue
        if is_shallow == "true":
            counters["shallow_repository_rejected"] += 1
            continue
        if is_shallow != "false":
            counters["shallow_status_invalid"] += 1
            continue
        if not trusted.REVISION_RE.fullmatch(revision) or not trusted.REVISION_RE.fullmatch(tree_oid):
            counters["unpinned_content_identity"] += 1
            continue
        if any(not canonical_git_path(blob.path) for blob in entries):
            counters["noncanonical_tree_path_rejected"] += 1
            continue
        all_candidates = [
            entry for entry in entries
            if entry.object_type == "blob"
            and entry.size is not None
            and MIN_FILE_BYTES <= entry.size <= MAX_FILE_BYTES
            and classify_path(entry.path) is not None
        ]
        all_candidates.sort(key=lambda entry: (stable([revision, tree_oid, entry.path]), entry.path))
        selected = all_candidates[:MAX_FILES_PER_REPO]
        if not selected:
            counters["without_supported_files"] += 1
            continue
        root_entries = {blob.path.lower(): blob for blob in entries if "/" not in blob.path}
        license_blob = next(
            (root_entries[name.lower()] for name in trusted.LICENSE_NAMES if name.lower() in root_entries),
            None,
        )
        license_path = license_oid = license_sha256 = ""
        license_id = "unknown"
        if (
            license_blob is not None
            and license_blob.object_type == "blob"
            and license_blob.size is not None
            and license_blob.size <= 256_000
        ):
            try:
                license_data = cat_blobs(repo, [license_blob])[license_blob.path]
            except (Stage12688Error, KeyError):
                counters["optional_license_metadata_read_failure"] += 1
            else:
                license_path = license_blob.path
                license_oid = license_blob.oid
                license_sha256 = sha256_bytes(license_data)
                license_id = trusted.detect_license(license_data.decode("utf-8", errors="ignore"))
        lineage_keys = tuple(sorted({
            f"head:{revision}",
            *(f"root:{oid}" for oid in roots if trusted.REVISION_RE.fullmatch(oid)),
            f"tree:{tree_oid}",
        }))
        repo_key = repository_content_identity(revision, tree_oid, entries)
        supported_placements = tuple(sorted(
            (tree_object_identity(entry), entry.path, kind.file_role)
            for entry in all_candidates
            for kind in [classify_path(entry.path)]
            if kind is not None and kind.file_role in {"code", "test", "build"}
        ))
        try:
            directory_inventories = discover_directory_inventories(
                repo, revision, tree_oid, selected
            )
        except Stage12688Error:
            counters["directory_inventory_verification_failure"] += 1
            continue
        layout_candidate_count = sum(
            len(directory_inventories.get(str(PurePosixPath(blob.path).parent), DirectoryInventory("", "", ())).entries) >= 3
            for blob in selected
        )
        snapshot = RepoSnapshot(
            local_path=repo,
            repo_key=repo_key,
            origin_url=origin,
            revision=revision,
            tree_oid=tree_oid,
            blobs=selected,
            component_objects=tuple(sorted(tree_object_identity(entry) for entry in entries)),
            lineage_keys=lineage_keys,
            tree_entries=tuple(sorted(entries, key=lambda blob: blob.path)),
            license_path=license_path,
            license_oid=license_oid,
            license_id=license_id,
            license_sha256=license_sha256,
            supported_placements=supported_placements,
            directory_inventories=directory_inventories,
            estimated_row_capacity=min(
                MAX_ROWS_PER_REPO, len(selected) * MAX_ROWS_PER_FILE + layout_candidate_count
            ),
        )
        snapshots.append(snapshot)
        counters["repositories_accepted"] += 1
        counters["supported_blobs_selected"] += len(selected)
    return snapshots, counters


def _object_weight(identity: tuple[str, str, int | None]) -> int:
    object_type, _oid, size = identity
    return int(size) if object_type == "blob" and size is not None and size > 0 else 0


def exact_component_capacity_assignment(
    components: list[dict[str, Any]],
    requested_caps: Mapping[str, int],
    *,
    state_budget: int | None = None,
    memory_budget: int | None = None,
    work_budget: int | None = None,
) -> dict[str, Any]:
    splits = ("train", "eval", "strict_eval")
    ordered = tuple(sorted(components, key=lambda item: (-item["capacity"], item["digest"])))
    capacities = tuple(int(item["capacity"]) for item in ordered)
    if any(capacity <= 0 for capacity in capacities):
        raise ValueError("component_capacity_must_be_positive")
    initial = tuple(int(requested_caps[split]) for split in splits)
    if any(deficit < 0 for deficit in initial):
        raise ValueError("requested_split_cap_must_be_nonnegative")
    state_limit = ALLOCATION_SEARCH_STATE_BUDGET if state_budget is None else state_budget
    memory_limit = ALLOCATION_SEARCH_MEMORY_BUDGET if memory_budget is None else memory_budget
    work_limit = ALLOCATION_SEARCH_WORK_BUDGET if work_budget is None else work_budget
    if min(state_limit, memory_limit, work_limit) <= 0:
        raise ValueError("allocation_search_budgets_must_be_positive")

    suffix_capacity = [0] * (len(capacities) + 1)
    for index in range(len(capacities) - 1, -1, -1):
        suffix_capacity[index] = suffix_capacity[index + 1] + capacities[index]

    def outcome(status: str, assignment: dict[str, str] | None = None) -> dict[str, Any]:
        return {
            "status": status,
            "assignment": assignment,
            "explored_states": explored_states,
            "memoized_dead_states": len(dead_states),
            "work_items": work_items,
            "state_budget": state_limit,
            "memory_budget": memory_limit,
            "work_budget": work_limit,
        }

    # Each frame is [index, deficits, deterministic branches, next branch, parent choice].
    stack: list[list[Any]] = [[
        0,
        initial,
        tuple(sorted(range(3), key=lambda position: (-initial[position], position))),
        0,
        None,
    ]]
    dead_states: set[tuple[int, tuple[int, int, int]]] = set()
    explored_states = 1
    work_items = 0

    while stack:
        if work_items >= work_limit:
            return outcome("search_budget_exhausted")
        work_items += 1
        frame = stack[-1]
        index = int(frame[0])
        deficits = frame[1]

        if not any(deficits):
            choices = [int(item[4]) for item in stack[1:]]
            choices.extend([0] * (len(ordered) - index))
            assignment = {
                item["digest"]: splits[position]
                for item, position in zip(ordered, choices)
            }
            return outcome("feasible", assignment)

        remaining = suffix_capacity[index]
        terminal = index == len(ordered)
        impossible = sum(deficits) > remaining or any(
            deficit > remaining for deficit in deficits
        )
        if terminal or impossible or int(frame[3]) >= len(frame[2]):
            state = (index, deficits)
            stack.pop()
            if state not in dead_states:
                if len(dead_states) + len(stack) >= memory_limit:
                    return outcome("search_budget_exhausted")
                dead_states.add(state)
            continue

        position = int(frame[2][int(frame[3])])
        frame[3] = int(frame[3]) + 1
        next_deficits = list(deficits)
        next_deficits[position] = max(0, next_deficits[position] - capacities[index])
        child_deficits = tuple(next_deficits)
        child_state = (index + 1, child_deficits)
        if child_state in dead_states:
            continue
        if explored_states >= state_limit or len(dead_states) + len(stack) >= memory_limit:
            return outcome("search_budget_exhausted")
        child_branches = tuple(
            sorted(range(3), key=lambda candidate: (-child_deficits[candidate], candidate))
        )
        stack.append([index + 1, child_deficits, child_branches, 0, position])
        explored_states += 1

    return outcome("proven_infeasible")


def assign_components(
    snapshots: list[RepoSnapshot], requested_rows: int | None = None
) -> dict[str, Any]:
    ordered = sorted(
        snapshots, key=lambda snapshot: (snapshot.repo_key, str(snapshot.local_path))
    )
    node_for = {id(snapshot): f"node:{index:06d}:{snapshot.repo_key}" for index, snapshot in enumerate(ordered)}
    snapshot_for = {node_for[id(snapshot)]: snapshot for snapshot in ordered}
    union = UnionFind(snapshot_for)
    hard_owners: dict[str, str] = {}
    hard_union_count = 0
    for snapshot in ordered:
        node = node_for[id(snapshot)]
        for key in snapshot.lineage_keys:
            owner = hard_owners.setdefault(key, node)
            if union.find(node) != union.find(owner):
                union.union(node, owner)
                hard_union_count += 1

    repository_count = len(ordered)
    common_df_threshold = max(8, math.ceil(repository_count * 0.02))
    object_df: collections.Counter[tuple[str, str, int | None]] = collections.Counter()
    for snapshot in ordered:
        object_df.update(set(snapshot.component_objects))
    seeding_objects = {
        identity for identity, frequency in object_df.items()
        if _object_weight(identity) > 0 and frequency <= common_df_threshold
    }
    postings: dict[tuple[str, str, int | None], list[str]] = collections.defaultdict(list)
    for snapshot in ordered:
        node = node_for[id(snapshot)]
        for identity in sorted(set(snapshot.component_objects).intersection(seeding_objects)):
            postings[identity].append(node)
    candidate_pairs: set[tuple[str, str]] = set()
    for nodes in postings.values():
        bounded = sorted(nodes)
        for left_index, left in enumerate(bounded):
            for right in bounded[left_index + 1:]:
                candidate_pairs.add((left, right))

    fork_union_count = 0
    compared_pair_count = 0
    for left_node, right_node in sorted(candidate_pairs):
        if union.find(left_node) == union.find(right_node):
            continue
        compared_pair_count += 1
        left = snapshot_for[left_node]
        right = snapshot_for[right_node]
        left_objects = set(left.component_objects)
        right_objects = set(right.component_objects)
        shared_seed = left_objects.intersection(right_objects).intersection(seeding_objects)
        shared_seed_bytes = sum(_object_weight(identity) for identity in shared_seed)
        left_placements = set(left.supported_placements)
        right_placements = set(right.supported_placements)
        shared_placements = left_placements.intersection(right_placements)
        left_weight = sum(_object_weight(identity) for identity in left_objects)
        right_weight = sum(_object_weight(identity) for identity in right_objects)
        shared_weight = sum(
            _object_weight(identity) for identity in left_objects.intersection(right_objects)
        )
        smaller_weight = min(left_weight, right_weight)
        object_containment = shared_weight / smaller_weight if smaller_weight else 0.0
        placement_denominator = min(len(left_placements), len(right_placements))
        placement_containment = (
            len(shared_placements) / placement_denominator if placement_denominator else 0.0
        )
        union_weight = left_weight + right_weight - shared_weight
        weighted_jaccard = shared_weight / union_weight if union_weight else 0.0
        qualifies = (
            len(shared_seed) >= MIN_SHARED_SEEDING_OBJECTS
            and shared_seed_bytes >= MIN_SHARED_SEEDING_BYTES
            and len(shared_placements) >= MIN_SHARED_SUPPORTED_PLACEMENTS
            and object_containment >= MIN_WEIGHTED_SMALLER_OBJECT_CONTAINMENT
            and placement_containment >= MIN_PLACEMENT_CONTAINMENT
            and (
                weighted_jaccard >= MIN_WEIGHTED_JACCARD
                or object_containment >= HIGH_CONFIDENCE_OBJECT_CONTAINMENT
            )
        )
        if qualifies:
            union.union(left_node, right_node)
            fork_union_count += 1

    members: dict[str, list[str]] = collections.defaultdict(list)
    for node in snapshot_for:
        members[union.find(node)].append(node)
    components: list[dict[str, Any]] = []
    for nodes in members.values():
        component_snapshots = [snapshot_for[node] for node in sorted(nodes)]
        digest = stable([
            FORK_GROUPING_CONTRACT_VERSION,
            sorted(snapshot.repo_key for snapshot in component_snapshots),
        ])
        capacity = sum(
            snapshot.estimated_row_capacity
            or min(MAX_ROWS_PER_REPO, max(1, len(snapshot.blobs) * (MAX_ROWS_PER_FILE + 1)))
            for snapshot in component_snapshots
        )
        components.append({"digest": digest, "capacity": capacity, "snapshots": component_snapshots})

    total_capacity = sum(component["capacity"] for component in components)
    fractions = {"train": 0.8, "eval": 0.1, "strict_eval": 0.1}
    targets = {split: total_capacity * fraction for split, fraction in fractions.items()}
    assigned: collections.Counter[str] = collections.Counter()
    priorities = {"train": 0, "eval": 1, "strict_eval": 2}

    def assign_proportionally() -> None:
        assigned.clear()
        for component in sorted(
            components, key=lambda item: (-item["capacity"], item["digest"])
        ):
            split = min(
                fractions,
                key=lambda name: (
                    assigned[name] / targets[name] if targets[name] else float("inf"),
                    priorities[name],
                ),
            )
            assigned[split] += component["capacity"]
            for snapshot in component["snapshots"]:
                snapshot.component_key = component["digest"]
                snapshot.split = split

    for component in components:
        for snapshot in component["snapshots"]:
            snapshot.component_key = component["digest"]

    requested_caps = None
    estimated_feasible = True
    allocation_method = "deterministic_proportional_no_requested_caps"
    allocation_search_states = 0
    allocation_search_memoized_states = 0
    allocation_search_work_items = 0
    allocation_search_status = "not_requested"
    allocation_search_exhaustive_infeasible = False
    allocation_search_budget_exhausted = False
    if requested_rows is None:
        assign_proportionally()
    else:
        requested_caps = {
            "train": requested_rows * 8 // 10,
            "eval": requested_rows // 10,
            "strict_eval": requested_rows - requested_rows * 8 // 10 - requested_rows // 10,
        }
        search_result = exact_component_capacity_assignment(
            components, requested_caps
        )
        allocation_search_status = search_result["status"]
        allocation_search_states = search_result["explored_states"]
        allocation_search_memoized_states = search_result["memoized_dead_states"]
        allocation_search_work_items = search_result["work_items"]
        exact_assignment = search_result["assignment"]
        if allocation_search_status == "search_budget_exhausted":
            allocation_method = "deterministic_iterative_bounded_search_budget_exhausted"
            allocation_search_budget_exhausted = True
            estimated_feasible = False
            assign_proportionally()
        elif allocation_search_status == "proven_infeasible":
            allocation_method = "deterministic_exact_memoized_exhaustive_infeasible"
            allocation_search_exhaustive_infeasible = True
            estimated_feasible = False
            assign_proportionally()
        else:
            if allocation_search_status != "feasible" or exact_assignment is None:
                raise AssertionError("invalid_exact_allocation_search_outcome")
            allocation_method = "deterministic_iterative_bounded_exact"
            assigned.clear()
            for component in components:
                split = exact_assignment[component["digest"]]
                assigned[split] += component["capacity"]
                for snapshot in component["snapshots"]:
                    snapshot.split = split
            estimated_feasible = all(
                assigned[split] >= cap for split, cap in requested_caps.items()
            )
            if not estimated_feasible:
                raise AssertionError("exact_component_assignment_failed_requested_caps")
    return {
        "contract_version": FORK_GROUPING_CONTRACT_VERSION,
        "thresholds": {
            "minimum_shared_seeding_objects": MIN_SHARED_SEEDING_OBJECTS,
            "minimum_shared_seeding_bytes": MIN_SHARED_SEEDING_BYTES,
            "minimum_shared_supported_code_test_build_placements": MIN_SHARED_SUPPORTED_PLACEMENTS,
            "minimum_weighted_smaller_side_object_containment": MIN_WEIGHTED_SMALLER_OBJECT_CONTAINMENT,
            "minimum_placement_containment": MIN_PLACEMENT_CONTAINMENT,
            "minimum_weighted_jaccard": MIN_WEIGHTED_JACCARD,
            "alternative_high_confidence_object_containment": HIGH_CONFIDENCE_OBJECT_CONTAINMENT,
            "common_df_rule": "df > max(8, ceil(repository_count * 0.02)) is non-seeding",
        },
        "repository_count": repository_count,
        "object_df_common_threshold": common_df_threshold,
        "all_object_inventory_occurrences": sum(len(snapshot.component_objects) for snapshot in ordered),
        "distinct_object_count": len(object_df),
        "nonseeding_empty_or_submodule_object_count": sum(
            _object_weight(identity) == 0 for identity in object_df
        ),
        "nonseeding_common_object_count": sum(
            frequency > common_df_threshold for frequency in object_df.values()
        ),
        "seeding_object_count": len(seeding_objects),
        "maximum_seeding_posting_size": max((len(nodes) for nodes in postings.values()), default=0),
        "candidate_pair_count": len(candidate_pairs),
        "compared_pair_count": compared_pair_count,
        "hard_union_count": hard_union_count,
        "fork_union_count": fork_union_count,
        "component_count": len(components),
        "component_digest_computation_count": len(components),
        "estimated_total_row_capacity": total_capacity,
        "estimated_split_row_capacities": dict(sorted(assigned.items())),
        "estimated_split_capacity_fractions": {
            split: (assigned[split] / total_capacity if total_capacity else 0.0)
            for split in ("train", "eval", "strict_eval")
        },
        "requested_split_row_caps": requested_caps,
        "estimated_split_cap_feasible": estimated_feasible,
        "allocation_method": allocation_method,
        "allocation_search_status": allocation_search_status,
        "allocation_search_states": allocation_search_states,
        "allocation_search_memoized_states": allocation_search_memoized_states,
        "allocation_search_work_items": allocation_search_work_items,
        "allocation_search_state_budget": ALLOCATION_SEARCH_STATE_BUDGET,
        "allocation_search_memory_budget": ALLOCATION_SEARCH_MEMORY_BUDGET,
        "allocation_search_work_budget": ALLOCATION_SEARCH_WORK_BUDGET,
        "allocation_search_exhaustive_infeasible": allocation_search_exhaustive_infeasible,
        "allocation_search_budget_exhausted": allocation_search_budget_exhausted,
        "whole_component_assignment": True,
        "residual": (
            "rare-object candidate generation may miss re-rooted near-duplicates without at least "
            "eight shared noncommon objects; exact lineage and stated containment gates are the practical contract"
        ),
    }


def _validate_and_add(
    row: dict[str, Any],
    proof: dict[str, Any],
    *,
    rows: list[dict[str, Any]],
    proofs: list[dict[str, Any]],
    seen: dict[str, set[str]],
    digest_splits: dict[str, str],
    input_splits: dict[str, str],
    quarantined_file_digests: set[str],
    quarantined_file_instances: set[str],
    quarantined_objective_families: set[str],
    counters: collections.Counter[str],
) -> bool:
    target = row["target"]["decoder_text"]
    if normalized_without_whitespace(target) in normalized_without_whitespace(row["input_text"]):
        raise Stage12688Error("target_leakage_after_whitespace_normalization")
    digest = proof["source_file_sha256"]
    if digest and (prior_split := digest_splits.get(digest)) not in {None, row["split"]}:
        if prior_split != "strict_eval" and row["split"] != "strict_eval":
            quarantined_file_digests.add(digest)
            quarantined_objective_families.add(row["objective_family"])
            file_instance = stable([
                digest, row["split"], proof["repository_key_sha256"],
                proof["repository_relative_path_sha256"],
            ])
            if file_instance not in quarantined_file_instances:
                quarantined_file_instances.add(file_instance)
                counters["public_cross_split_source_file_digest_files_quarantined"] += 1
            counters["public_cross_split_source_file_digest_candidate_rows_rejected"] += 1
        return False
    input_digest = proof["encoder_input_sha256"]
    if input_digest != sha256_bytes(row["input_text"].encode("utf-8")):
        raise Stage12688Error("encoder_input_hash_mismatch")
    keys = {
        "row": proof["row_sha256"],
        "input": input_digest,
        "model": proof["model_example_sha256"],
        "semantic": proof["semantic_example_sha256"],
        "window": proof["source_window_sha256"],
    }
    duplicate_kinds = [name for name, value in keys.items() if value in seen[name]]
    if row["row_id"] in seen["id"] or duplicate_kinds:
        counters["duplicate_row_or_example_rejected"] += 1
        if row["row_id"] in seen["id"]:
            counters["global_row_id_duplicate_rejected"] += 1
        for name in duplicate_kinds:
            counters[f"global_{name}_duplicate_rejected"] += 1
        prior_input_split = input_splits.get(input_digest)
        if (
            "input" in duplicate_kinds
            and prior_input_split not in {None, "strict_eval"}
            and row["split"] != "strict_eval"
        ):
            counters["public_duplicate_encoder_input_rows_quarantined"] += 1
        return False
    seen["id"].add(row["row_id"])
    for name, value in keys.items():
        seen[name].add(value)
    if digest:
        digest_splits[digest] = row["split"]
    input_splits[input_digest] = row["split"]
    rows.append(row)
    proofs.append(proof)
    return True


def write_json_atomic(path: Path, value: Any) -> None:
    secure_atomic_write(
        path,
        (json.dumps(value, indent=2, sort_keys=True, ensure_ascii=True) + "\n").encode("ascii"),
        mode=0o644,
    )


def write_jsonl_atomic(path: Path, rows: Iterable[Mapping[str, Any]]) -> None:
    payload = b"".join(
        json.dumps(row, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("ascii") + b"\n"
        for row in rows
    )
    secure_atomic_write(path, payload, mode=0o600)


@dataclass(frozen=True)
class ArtifactIdentity:
    device: int
    inode: int
    size: int
    sha256: str


@dataclass(frozen=True)
class PreparedRelease:
    rows: list[dict[str, Any]]
    proofs: list[dict[str, Any]]
    catalog: list[dict[str, Any]]
    public_payloads: dict[str, bytes]
    summary: dict[str, Any]


def sha256_open_fd(fd: int) -> str:
    digest = hashlib.sha256()
    os.lseek(fd, 0, os.SEEK_SET)
    while True:
        chunk = os.read(fd, 1024 * 1024)
        if not chunk:
            break
        digest.update(chunk)
    os.lseek(fd, 0, os.SEEK_SET)
    return digest.hexdigest()


def write_file_at(
    directory_fd: int, name: str, data: bytes, *, mode: int
) -> ArtifactIdentity:
    if not name or "/" in name or "\\" in name or name in {".", ".."}:
        raise Stage12688Error("unsafe_publication_filename")
    flags = os.O_RDWR | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
    fd = os.open(name, flags, mode, dir_fd=directory_fd)
    try:
        opened = os.fstat(fd)
        if not stat.S_ISREG(opened.st_mode):
            raise Stage12688Error("publication_leaf_not_regular")
        view = memoryview(data)
        while view:
            written = os.write(fd, view)
            if written <= 0:
                raise Stage12688Error("publication_short_write")
            view = view[written:]
        os.fchmod(fd, mode)
        os.fsync(fd)
        finalized = os.fstat(fd)
        digest = sha256_open_fd(fd)
        if finalized.st_size != len(data):
            raise Stage12688Error("publication_size_mismatch")
        return ArtifactIdentity(
            device=finalized.st_dev, inode=finalized.st_ino,
            size=finalized.st_size, sha256=digest,
        )
    finally:
        os.close(fd)


def secure_atomic_write_at(parent_fd: int, name: str, data: bytes, *, mode: int) -> None:
    temporary = f".{name}.tmp.{os.getpid()}.{sha256_bytes(data)[:12]}"
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
    fd = os.open(temporary, flags, mode, dir_fd=parent_fd)
    try:
        view = memoryview(data)
        while view:
            written = os.write(fd, view)
            view = view[written:]
        os.fchmod(fd, mode)
        os.fsync(fd)
    finally:
        os.close(fd)
    os.replace(temporary, name, src_dir_fd=parent_fd, dst_dir_fd=parent_fd)
    os.fsync(parent_fd)


def revalidate_directory_identity(path: Path, fd: int, expected: tuple[int, int]) -> None:
    held = os.fstat(fd)
    try:
        live = os.stat(path, follow_symlinks=False)
    except OSError as exc:
        raise Stage12688Error("private_root_identity_unavailable") from exc
    if (held.st_dev, held.st_ino) != expected or (live.st_dev, live.st_ino) != expected:
        raise Stage12688Error("private_root_identity_changed")
    if not stat.S_ISDIR(live.st_mode):
        raise Stage12688Error("private_root_not_directory")


def rename_noreplace(parent_fd: int, source_name: str, destination_name: str) -> None:
    renameat2 = getattr(ctypes.CDLL(None, use_errno=True), "renameat2", None)
    if renameat2 is None:
        raise Stage12688Error("renameat2_noreplace_unavailable")
    renameat2.argtypes = [
        ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint,
    ]
    renameat2.restype = ctypes.c_int
    if renameat2(
        parent_fd, source_name.encode("utf-8"),
        parent_fd, destination_name.encode("utf-8"),
        1,
    ) != 0:
        error_number = ctypes.get_errno()
        raise OSError(error_number, os.strerror(error_number), destination_name)


def verify_generation_entry(
    private_fd: int,
    entry_name: str,
    expected: os.stat_result,
    required_artifacts: Mapping[str, ArtifactIdentity],
    *,
    phase: str,
) -> None:
    flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0)
    try:
        entry_stat = os.stat(entry_name, dir_fd=private_fd, follow_symlinks=False)
        entry_fd = os.open(entry_name, flags, dir_fd=private_fd)
    except OSError as exc:
        raise Stage12688Error(f"{phase}_generation_entry_unavailable") from exc
    try:
        opened = os.fstat(entry_fd)
        identity = (expected.st_dev, expected.st_ino)
        if (
            not stat.S_ISDIR(entry_stat.st_mode)
            or (entry_stat.st_dev, entry_stat.st_ino) != identity
            or (opened.st_dev, opened.st_ino) != identity
        ):
            raise Stage12688Error(f"{phase}_generation_inode_mismatch")
        artifact_flags = (
            os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0)
        )
        for name, expected_artifact in required_artifacts.items():
            artifact_fd: int | None = None
            try:
                named_before = os.stat(name, dir_fd=entry_fd, follow_symlinks=False)
                artifact_fd = os.open(name, artifact_flags, dir_fd=entry_fd)
                artifact = os.fstat(artifact_fd)
                digest = sha256_open_fd(artifact_fd)
                named_after = os.stat(name, dir_fd=entry_fd, follow_symlinks=False)
            except OSError as exc:
                raise Stage12688Error(
                    f"{phase}_generation_required_artifact_missing:{name}"
                ) from exc
            finally:
                if artifact_fd is not None:
                    os.close(artifact_fd)
            expected_file_identity = (expected_artifact.device, expected_artifact.inode)
            if (
                not stat.S_ISREG(named_before.st_mode)
                or not stat.S_ISREG(artifact.st_mode)
                or not stat.S_ISREG(named_after.st_mode)
                or (named_before.st_dev, named_before.st_ino) != expected_file_identity
                or (artifact.st_dev, artifact.st_ino) != expected_file_identity
                or (named_after.st_dev, named_after.st_ino) != expected_file_identity
                or artifact.st_size != expected_artifact.size
                or named_after.st_size != expected_artifact.size
                or digest != expected_artifact.sha256
            ):
                raise Stage12688Error(
                    f"{phase}_generation_artifact_identity_mismatch:{name}"
                )
    finally:
        os.close(entry_fd)


def publish_generation(
    private_root: Path,
    generation_id: str,
    artifact_payloads: Mapping[str, bytes],
    summary: Mapping[str, Any],
) -> Path:
    private_root.mkdir(parents=True, exist_ok=True, mode=0o700)
    if private_root.is_symlink() or private_root.resolve() != private_root.absolute():
        raise Stage12688Error(f"symlinked_private_root:{private_root}")
    os.chmod(private_root, 0o700)
    private_fd = open_directory_nofollow(private_root)
    private_stat = os.fstat(private_fd)
    expected_private = (private_stat.st_dev, private_stat.st_ino)
    pending_name = f".pending-{generation_id}-{os.getpid()}"
    generation_name = generation_id
    summary_payload = (
        json.dumps(summary, indent=2, sort_keys=True, ensure_ascii=True) + "\n"
    ).encode("ascii")
    pending_fd: int | None = None
    try:
        try:
            os.stat(generation_name, dir_fd=private_fd, follow_symlinks=False)
        except FileNotFoundError:
            pass
        else:
            raise Stage12688Error(f"immutable_generation_exists:{generation_id}")
        os.mkdir(pending_name, 0o700, dir_fd=private_fd)
        pending_flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0)
        pending_fd = os.open(pending_name, pending_flags, dir_fd=private_fd)
        pending_identity = os.fstat(pending_fd)
        if not stat.S_ISDIR(pending_identity.st_mode):
            raise Stage12688Error("pending_generation_not_directory")
        expected_artifacts = {
            name: write_file_at(pending_fd, name, payload, mode=0o400)
            for name, payload in artifact_payloads.items()
        }
        expected_artifacts["summary.json"] = write_file_at(
            pending_fd, "summary.json", summary_payload, mode=0o400
        )
        os.fchmod(pending_fd, 0o500)
        os.fsync(pending_fd)
        revalidate_directory_identity(private_root, private_fd, expected_private)
        verify_generation_entry(
            private_fd, pending_name, pending_identity, expected_artifacts, phase="pending"
        )
        rename_noreplace(private_fd, pending_name, generation_name)
        verify_generation_entry(
            private_fd, generation_name, pending_identity, expected_artifacts, phase="published"
        )
        os.fsync(private_fd)
        revalidate_directory_identity(private_root, private_fd, expected_private)
    finally:
        if pending_fd is not None:
            os.close(pending_fd)
        os.close(private_fd)
    return private_root / generation_name


def cached_blob_sha256(cache: dict[str, str], oid: str, data: bytes) -> str:
    digest = cache.get(oid)
    if digest is None:
        digest = sha256_bytes(data)
        cache[oid] = digest
    return digest


def finalized_cross_split_overlap(proofs: list[dict[str, Any]], field: str) -> dict[str, Any]:
    owners: dict[str, set[str]] = collections.defaultdict(set)
    for proof in proofs:
        value = proof.get(field)
        if value:
            owners[str(value)].add(proof["split"])
    overlapping = sorted(value for value, splits in owners.items() if len(splits) > 1)
    return {
        "field": field,
        "overlap_count": len(overlapping),
        "overlap_value_commitment_sha256": stable(overlapping),
        "computed_from_finalized_rows": True,
    }



@dataclass(frozen=True)
class InventoryCandidate:
    snapshot: RepoSnapshot
    row: dict[str, Any]
    proof: dict[str, Any]
    sort_key: tuple[Any, ...]


def _inventory_sort_key(
    snapshot: RepoSnapshot, row: Mapping[str, Any], proof: Mapping[str, Any]
) -> tuple[Any, ...]:
    return (
        snapshot.component_key,
        snapshot.repo_key,
        str(row["source_provenance"]["repository_relative_path"]),
        str(row["objective_family"]),
        -1 if proof["span_start_byte"] is None else int(proof["span_start_byte"]),
        -1 if proof["span_end_byte"] is None else int(proof["span_end_byte"]),
        str(proof["target_sha256"]),
        str(row["row_id"]),
    )


def materialize_candidate_inventory(
    snapshots: list[RepoSnapshot],
    counters: collections.Counter[str],
) -> tuple[list[InventoryCandidate], set[str], set[str], set[str]]:
    candidates: list[InventoryCandidate] = []
    source_file_digest_cache: dict[str, str] = {}
    for snapshot in sorted(snapshots, key=lambda item: (item.component_key, item.repo_key)):
        try:
            contents = cat_blobs(snapshot.local_path, snapshot.blobs)
        except Stage12688Error:
            counters["verified_blob_read_failure"] += 1
            continue
        for blob in snapshot.blobs:
            data = contents.get(blob.path)
            reason = "missing" if data is None else content_rejection_reason(data)
            if reason is not None:
                counters[f"content_rejected_{reason}"] += 1
                continue
            assert data is not None
            source_file_digest = cached_blob_sha256(
                source_file_digest_cache, blob.oid, data
            )
            kind = classify_path(blob.path)
            if kind is None:
                raise Stage12688Error("selected_path_lost_classification")
            built_candidates: list[tuple[dict[str, Any], dict[str, Any]]] = []
            tree_built = build_directory_entry_row(snapshot, blob, source_file_digest)
            if tree_built is not None:
                built_candidates.append(tree_built)
            built_candidates.extend(
                built
                for span in candidate_spans(data, snapshot.repo_key, blob.path)
                for built in [
                    build_span_row(snapshot, blob, kind, data, span, source_file_digest)
                ]
                if built is not None
            )
            for row, proof in built_candidates:
                candidates.append(InventoryCandidate(
                    snapshot=snapshot,
                    row=row,
                    proof=proof,
                    sort_key=_inventory_sort_key(snapshot, row, proof),
                ))
    candidates.sort(key=lambda candidate: candidate.sort_key)
    counters["candidate_inventory_rows_before_global_gates"] += len(candidates)

    digest_components: dict[str, set[str]] = collections.defaultdict(set)
    for candidate in candidates:
        digest = str(candidate.proof["source_file_sha256"])
        if digest:
            digest_components[digest].add(candidate.snapshot.component_key)
    quarantined_digests = {
        digest for digest, components in digest_components.items() if len(components) > 1
    }
    if quarantined_digests:
        counters["cross_component_source_file_digests_quarantined"] += len(quarantined_digests)
    quarantined_file_instances: set[str] = set()
    quarantined_objective_families: set[str] = set()
    filtered: list[InventoryCandidate] = []
    for candidate in candidates:
        if candidate.proof["source_file_sha256"] in quarantined_digests:
            counters["cross_component_source_file_candidate_rows_quarantined"] += 1
            quarantined_file_instances.add(stable([
                candidate.proof["source_file_sha256"],
                candidate.snapshot.component_key,
                candidate.snapshot.repo_key,
                candidate.proof["repository_relative_path_sha256"],
            ]))
            quarantined_objective_families.add(str(candidate.row["objective_family"]))
            continue
        filtered.append(candidate)

    seen = {name: set() for name in ("id", "row", "input", "model", "semantic", "window")}
    deduplicated: list[InventoryCandidate] = []
    for candidate in filtered:
        keys = {
            "id": candidate.row["row_id"],
            "row": candidate.proof["row_sha256"],
            "input": candidate.proof["encoder_input_sha256"],
            "model": candidate.proof["model_example_sha256"],
            "semantic": candidate.proof["semantic_example_sha256"],
            "window": candidate.proof["source_window_sha256"],
        }
        duplicate_kinds = [name for name, value in keys.items() if value in seen[name]]
        if duplicate_kinds:
            counters["duplicate_row_or_example_rejected"] += 1
            for name in duplicate_kinds:
                counters[f"global_{name}_duplicate_rejected"] += 1
            continue
        for name, value in keys.items():
            seen[name].add(value)
        deduplicated.append(candidate)

    repo_counts: collections.Counter[str] = collections.Counter()
    capped: list[InventoryCandidate] = []
    for candidate in deduplicated:
        repo_key = candidate.snapshot.repo_key
        if repo_counts[repo_key] >= MAX_ROWS_PER_REPO:
            counters["per_repository_candidate_rows_capped"] += 1
            continue
        repo_counts[repo_key] += 1
        capped.append(candidate)
    counters["candidate_inventory_rows_after_global_gates"] += len(capped)
    return (
        capped, quarantined_digests, quarantined_file_instances,
        quarantined_objective_families,
    )


def assign_actual_candidate_capacities(
    snapshots: list[RepoSnapshot],
    candidates: list[InventoryCandidate],
    grouping_contract: dict[str, Any],
    split_caps: Mapping[str, int],
) -> None:
    capacities: collections.Counter[str] = collections.Counter(
        candidate.snapshot.component_key for candidate in candidates
    )
    component_snapshots: dict[str, list[RepoSnapshot]] = collections.defaultdict(list)
    for snapshot in snapshots:
        component_snapshots[snapshot.component_key].append(snapshot)
        snapshot.split = "train"
    components = [
        {
            "digest": digest,
            "capacity": capacities[digest],
            "snapshots": sorted(
                members, key=lambda snapshot: (snapshot.repo_key, str(snapshot.local_path))
            ),
        }
        for digest, members in sorted(component_snapshots.items())
        if capacities[digest] > 0
    ]
    search_result = exact_component_capacity_assignment(components, split_caps)
    status = search_result["status"]
    grouping_contract.update({
        "capacity_basis": "single_pinned_snapshot_candidate_inventory_after_global_gates_v1",
        "estimated_total_row_capacity": sum(capacities.values()),
        "requested_split_row_caps": dict(split_caps),
        "allocation_method": "deterministic_iterative_bounded_exact_actual_candidate_capacity",
        "allocation_search_status": status,
        "allocation_search_states": search_result["explored_states"],
        "allocation_search_memoized_states": search_result["memoized_dead_states"],
        "allocation_search_work_items": search_result["work_items"],
        "allocation_search_exhaustive_infeasible": status == "proven_infeasible",
        "allocation_search_budget_exhausted": status == "search_budget_exhausted",
        "estimated_split_cap_feasible": status == "feasible",
    })
    if status == "search_budget_exhausted":
        raise Stage12688Error("component_split_allocation_search_budget_exhausted")
    if status == "proven_infeasible":
        raise Stage12688Error("actual_component_split_capacity_infeasible")
    assignment = search_result["assignment"]
    if status != "feasible" or assignment is None:
        raise AssertionError("invalid_exact_allocation_search_outcome")
    assigned: collections.Counter[str] = collections.Counter()
    for component in components:
        split = assignment[component["digest"]]
        assigned[split] += component["capacity"]
        for snapshot in component["snapshots"]:
            snapshot.split = split
    grouping_contract["estimated_split_row_capacities"] = dict(sorted(assigned.items()))
    grouping_contract["estimated_split_capacity_fractions"] = {
        split: assigned[split] / sum(capacities.values())
        for split in ("train", "eval", "strict_eval")
    }


def finalize_inventory_candidate(
    candidate: InventoryCandidate,
) -> tuple[dict[str, Any], dict[str, Any]]:
    row = copy.deepcopy(candidate.row)
    proof = copy.deepcopy(candidate.proof)
    split = candidate.snapshot.split
    row["split"] = split
    row["source_provenance"]["content_component_sha256"] = candidate.snapshot.component_key
    proof["split"] = split
    proof["content_component_sha256"] = candidate.snapshot.component_key
    proof["row_sha256"] = stable(row)
    return row, proof


def prepare_release(
    source_root: Path,
    *,
    max_repos: int,
    max_rows: int,
) -> PreparedRelease:
    if max_rows < 10 or max_rows % 10 != 0:
        raise Stage12688Error("invalid_max_rows_exact_80_10_10_required")
    if not source_root.is_dir():
        raise Stage12688Error(f"source_root_missing:{source_root}")
    snapshots, counters = discover_repositories(source_root, max_repos)
    if not snapshots:
        raise Stage12688Error("no_eligible_repositories")
    grouping_contract = assign_components(snapshots)
    split_caps = {
        "train": max_rows * 8 // 10,
        "eval": max_rows // 10,
        "strict_eval": max_rows - max_rows * 8 // 10 - max_rows // 10,
    }
    (
        inventory,
        quarantined_file_digests,
        quarantined_file_instances,
        quarantined_objective_families,
    ) = materialize_candidate_inventory(snapshots, counters)
    assign_actual_candidate_capacities(
        snapshots, inventory, grouping_contract, split_caps
    )

    rows: list[dict[str, Any]] = []
    proofs: list[dict[str, Any]] = []
    split_counts: collections.Counter[str] = collections.Counter()
    objective_counts: collections.Counter[str] = collections.Counter()
    language_counts: collections.Counter[str] = collections.Counter()
    role_counts: collections.Counter[str] = collections.Counter()
    seen = {name: set() for name in ("id", "row", "input", "model", "semantic", "window")}
    digest_splits: dict[str, str] = {}
    input_splits: dict[str, str] = {}

    for candidate in inventory:
        split = candidate.snapshot.split
        if split_counts[split] >= split_caps[split]:
            continue
        row, proof = finalize_inventory_candidate(candidate)
        if not _validate_and_add(
            row, proof, rows=rows, proofs=proofs, seen=seen,
            digest_splits=digest_splits,
            input_splits=input_splits,
            quarantined_file_digests=quarantined_file_digests,
            quarantined_file_instances=quarantined_file_instances,
            quarantined_objective_families=quarantined_objective_families,
            counters=counters,
        ):
            raise Stage12688Error("post_allocation_candidate_inventory_changed")
        split_counts[split] += 1
        objective_counts[row["objective_family"]] += 1
        language_counts[row["language_family"]] += 1
        role_counts[row["source_provenance"]["file_role"]] += 1
        counters["rows_materialized"] += 1

    if any(
        split_counts[split] != split_caps[split]
        for split in ("train", "eval", "strict_eval")
    ):
        raise Stage12688Error("requested_split_caps_unfilled_after_actual_capacity_assignment")

    catalog = [{
        "repository_key_sha256": snapshot.repo_key,
        "origin_url": snapshot.origin_url,
        "origin_url_trust": "untrusted_mutable_metadata_not_used_for_identity_or_split",
        "origin_url_sha256": (
            sha256_bytes(snapshot.origin_url.encode("utf-8")) if snapshot.origin_url else ""
        ),
        "revision": snapshot.revision,
        "git_tree_oid": snapshot.tree_oid,
        "content_component_sha256": snapshot.component_key,
        "split": snapshot.split,
        "selected_supported_blob_count": len(snapshot.blobs),
        "all_tree_object_count": len(snapshot.component_objects),
        "all_tree_object_identity_inventory_sha256": stable(snapshot.component_objects),
        "supported_code_test_build_placement_count": len(snapshot.supported_placements),
        "supported_code_test_build_placement_inventory_sha256": stable(snapshot.supported_placements),
        "verified_immediate_directory_inventory_count": len(snapshot.directory_inventories or {}),
        "verified_immediate_directory_entry_count": sum(
            len(inventory.entries) for inventory in (snapshot.directory_inventories or {}).values()
        ),
        "tree_object_type_counts": dict(sorted(collections.Counter(
            entry.object_type for entry in snapshot.tree_entries
        ).items())),
        "license_file": snapshot.license_path,
        "license_git_blob_oid": snapshot.license_oid,
        "license_id_if_detected": snapshot.license_id,
        "license_file_sha256": snapshot.license_sha256,
        "head_commit_git_oid": snapshot.revision,
        "root_commit_git_oids": sorted(key[5:] for key in snapshot.lineage_keys if key.startswith("root:")),
        "hard_grouping_key_sha256s": [
            sha256_bytes(key.encode("utf-8")) for key in snapshot.lineage_keys
        ],
        "tree_git_oids": sorted(key[5:] for key in snapshot.lineage_keys if key.startswith("tree:")),
    } for snapshot in snapshots]
    train_eval = [row for row in rows if row["split"] != "strict_eval"]
    train_eval_proofs = [proof for proof in proofs if proof["split"] != "strict_eval"]
    train_eval_catalog = [entry for entry in catalog if entry["split"] != "strict_eval"]
    strict_proofs = [proof for proof in proofs if proof["split"] == "strict_eval"]
    strict_reserved_count = len(strict_proofs)
    strict_commitment = stable(sorted(proof["row_sha256"] for proof in strict_proofs))
    if any(
        rejected_target_marker(row["target"]["decoder_text"]) for row in rows
    ):
        raise Stage12688Error("rejected_marker_in_finalized_target")

    public_objective_counts = collections.Counter(
        row["objective_family"] for row in train_eval
    )
    public_language_counts = collections.Counter(row["language_family"] for row in train_eval)
    public_role_counts = collections.Counter(
        row["source_provenance"]["file_role"] for row in train_eval
    )
    public_repo_counts = collections.Counter(
        proof["repository_key_sha256"] for proof in train_eval_proofs
    )
    overlap_fields = {
        "repository": "repository_key_sha256",
        "component": "content_component_sha256",
        "file_digest": "source_file_sha256",
        "source_window": "source_window_sha256",
        "encoder_input": "encoder_input_sha256",
        "model_example": "model_example_sha256",
        "semantic_example": "semantic_example_sha256",
    }
    internal_overlap_metrics = {
        name: finalized_cross_split_overlap(proofs, field)
        for name, field in overlap_fields.items()
    }
    if any(metric["overlap_count"] for metric in internal_overlap_metrics.values()):
        raise Stage12688Error("finalized_cross_split_overlap_detected")
    public_overlap_metrics = {
        name: finalized_cross_split_overlap(train_eval_proofs, field)
        for name, field in overlap_fields.items()
    }
    public_cross_split_file_quarantine = {
        "policy": "global_cross_component_source_file_quarantine_before_split_allocation_v1",
        "quarantined_distinct_source_file_digest_count": len(quarantined_file_digests),
        "quarantined_source_file_digest_commitment_sha256": stable(
            sorted(quarantined_file_digests)
        ),
        "quarantined_file_instance_count": len(quarantined_file_instances),
        "quarantined_file_instance_commitment_sha256": stable(
            sorted(quarantined_file_instances)
        ),
        "quarantined_objective_families": sorted(quarantined_objective_families),
        "candidate_row_rejection_count": counters["cross_component_source_file_candidate_rows_quarantined"],
        "accepted_train_eval_source_file_ownership_commitment_sha256": stable(sorted(
            (digest, split) for digest, split in digest_splits.items()
            if split != "strict_eval"
        )),
        "finalized_train_eval_file_digest_overlap_zero": (
            public_overlap_metrics["file_digest"]["overlap_count"] == 0
        ),
        "exact_public_split_caps_refilled": (
            split_counts["train"] == split_caps["train"]
            and split_counts["eval"] == split_caps["eval"]
        ),
    }
    public_grouping_contract = {
        "contract_version": grouping_contract["contract_version"],
        "thresholds": grouping_contract["thresholds"],
        "whole_component_assignment": grouping_contract["whole_component_assignment"],
        "estimated_split_cap_feasible": grouping_contract["estimated_split_cap_feasible"],
        "allocation_method": grouping_contract["allocation_method"],
        "residual": grouping_contract["residual"],
    }
    artifact_values = {
        "multilingual_train_eval_manifest.jsonl": train_eval,
        "train_eval_source_provenance_ledger.jsonl": train_eval_proofs,
        "train_eval_source_catalog.jsonl": train_eval_catalog,
    }
    artifact_payloads = {
        name: b"".join(
            json.dumps(row, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("ascii") + b"\n"
            for row in values
        )
        for name, values in artifact_values.items()
    }
    artifact_schema_version = 4
    artifact_identity_inputs = sorted(
        (name, len(artifact_values[name]), sha256_bytes(payload))
        for name, payload in artifact_payloads.items()
    )
    generation_id = stable([
        "stage12688_generation_v4_public_artifacts_and_strict_commitment",
        artifact_schema_version,
        artifact_identity_inputs,
        strict_reserved_count,
        strict_commitment,
    ])[:24]
    artifact_contract = {
        name: {
            "relative_path": f"private/{generation_id}/{name}",
            "rows": len(artifact_values[name]),
            "sha256": sha256_bytes(payload),
        }
        for name, payload in artifact_payloads.items()
    }
    summary = {
        "stage": STAGE,
        "generation_id": generation_id,
        "generation_relative_path": f"private/{generation_id}",
        "artifact_schema_version": artifact_schema_version,
        "authoritative_summary_relative_path": f"private/{generation_id}/summary.json",
        "generation_and_authoritative_summary_transactional": True,
        "external_summary_mirrors_are_nonauthoritative": True,
        "decision": "SOURCE_BACKED_MULTILINGUAL_FOUNDATIONAL_CORPUS_MATERIALIZED_REVIEW_REQUIRED",
        "objective_families": dict(sorted(public_objective_counts.items())),
        "language_families": dict(sorted(public_language_counts.items())),
        "file_roles": dict(sorted(public_role_counts.items())),
        "repository_snapshots": len(train_eval_catalog),
        "content_components": len({
            entry["content_component_sha256"] for entry in train_eval_catalog
        }),
        "all_tree_object_inventory_audit": {
            "retained": True,
            "included_object_types": ["blob", "commit"],
            "identity_fields": ["object_type", "git_object_oid", "blob_size_or_null"],
            "placement_inventory_retained": True,
            "single_shared_object_never_hard_unions": True,
        },
        "practical_fork_grouping_contract": public_grouping_contract,
        "repositories_contributing_rows": len(public_repo_counts),
        "maximum_rows_from_one_repository": max(public_repo_counts.values(), default=0),
        "materialized_model_row_count": len(train_eval),
        "reserved_unmaterialized_strict_row_count": strict_reserved_count,
        "strict_eval_commitment_sha256": strict_commitment,
        "public_split_counts": {
            "train": split_counts["train"],
            "eval": split_counts["eval"],
        },
        "byte_exact_source_span_reinsertion_verified_rows": sum(
            proof["byte_exact_source_span_reinsertion_verified"]
            for proof in train_eval_proofs
        ),
        "exact_pinned_immediate_directory_entry_name_completion_verified_rows": sum(
            proof["exact_pinned_immediate_directory_entry_name_completion_verified"]
            for proof in train_eval_proofs
        ),
        "input_target_whitespace_normalized_overlap_rows": 0,
        "stub_or_placeholder_target_rows": sum(
            bool(PLACEHOLDER_RE.search(row["target"]["decoder_text"]))
            for row in train_eval
        ),
        "unresolved_sentinel_target_rows": sum(
            bool(UNRESOLVED_SENTINEL_RE.search(row["target"]["decoder_text"]))
            for row in train_eval
        ),
        "distinct_row_ids": len({row["row_id"] for row in train_eval}),
        "distinct_row_hashes": len({proof["row_sha256"] for proof in train_eval_proofs}),
        "distinct_encoder_input_hashes": len({
            proof["encoder_input_sha256"] for proof in train_eval_proofs
        }),
        "encoder_input_hashes_equal_materialized_rows": (
            len({proof["encoder_input_sha256"] for proof in train_eval_proofs})
            == len(train_eval)
        ),
        "public_duplicate_encoder_input_rows_quarantined": (
            counters["public_duplicate_encoder_input_rows_quarantined"]
            + counters["global_input_duplicate_rejected"]
        ),
        "distinct_model_example_hashes": len({
            proof["model_example_sha256"] for proof in train_eval_proofs
        }),
        "distinct_semantic_example_hashes": len({
            proof["semantic_example_sha256"] for proof in train_eval_proofs
        }),
        "public_split_overlap_metrics": public_overlap_metrics,
        "public_cross_split_source_file_quarantine": public_cross_split_file_quarantine,
        "train_eval_repository_overlap": public_overlap_metrics["repository"]["overlap_count"],
        "train_eval_component_overlap": public_overlap_metrics["component"]["overlap_count"],
        "train_eval_file_digest_overlap": public_overlap_metrics["file_digest"]["overlap_count"],
        "train_eval_source_window_overlap": public_overlap_metrics["source_window"]["overlap_count"],
        "source_catalog_rows": len(train_eval_catalog),
        "artifact_contract": artifact_contract,
        "near_duplicate_rerooted_residual": {
            "status": "UNRESOLVED_REVIEW_REQUIRED",
            "all_tree_object_and_placement_inventory_retained": True,
            "practical_fork_grouping_contract_version": FORK_GROUPING_CONTRACT_VERSION,
            "immutable_root_head_tree_hard_grouping": True,
            "mutable_remote_metadata_hard_grouping": False,
            "single_shared_object_hard_grouping": False,
            "semantic_example_deduplication": True,
            "residual_assumption": "near-duplicate re-rooted repositories without shared exact tree objects or immutable lineage identifiers may remain",
        },
        "mutable_remote_metadata_contract": {
            "origin_url_recorded_as_untrusted_metadata": True,
            "origin_url_sha256_recorded_as_untrusted_metadata_hash": True,
            "excluded_from_repository_key": True,
            "excluded_from_lineage_keys_and_component_union": True,
            "excluded_from_component_digest": True,
            "excluded_from_capacity_and_split_assignment": True,
        },
        "training_eligible_rows": 0,
        "unresolved_knowledge_lanes": [
            "semantic_api_and_symbol_reference_prediction",
            "proof_backed_doc_code_test_relationships",
            "proof_backed_test_file_association",
            "issue_linked_maintenance_vocabulary",
            "parent_child_small_diff_reconstruction",
            "machine_report_backed_compact_verifier_summaries",
        ],
        "release_blockers": [
            "independent_semantic_security_and_leakage_review_required",
            "tokenizer_bound_context_and_target_audit_required",
            "language_and_role_balance_admission_contract_required",
            "near_duplicate_rerooted_repository_review_required",
            "historical_version_retention_coverage_absent",
            "retention_eligibility_not_established",
        ],
        "authority": dict(AUTHORITY),
    }
    return PreparedRelease(
        rows=rows,
        proofs=proofs,
        catalog=catalog,
        public_payloads=artifact_payloads,
        summary=summary,
    )


def build(
    source_root: Path,
    output_dir: Path,
    summary_path: Path,
    *,
    max_repos: int,
    max_rows: int,
) -> dict[str, Any]:
    prepared = prepare_release(source_root, max_repos=max_repos, max_rows=max_rows)
    summary = prepared.summary
    private_root = output_dir / "private"
    publish_generation(
        private_root, summary["generation_id"], prepared.public_payloads, summary
    )
    mirror = output_dir / "summary.json"
    write_json_atomic(mirror, summary)
    if summary_path.absolute() != mirror.absolute():
        write_json_atomic(summary_path, summary)
    return summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-root", type=Path, default=DEFAULT_SOURCE_ROOT)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--summary-path", type=Path, default=DEFAULT_SUMMARY)
    parser.add_argument("--max-repos", type=int, default=MAX_REPOS)
    parser.add_argument("--max-rows", type=int, default=MAX_ROWS)
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    if args.max_repos <= 0 or args.max_rows < 10 or args.max_rows % 10 != 0:
        raise SystemExit(
            "max-repos must be positive and max-rows must be at least 10 and divisible by 10"
        )
    print(json.dumps(build(
        args.source_root.resolve(),
        args.output_dir.resolve(),
        args.summary_path.resolve(),
        max_repos=args.max_repos,
        max_rows=args.max_rows,
    ), indent=2, sort_keys=True))
