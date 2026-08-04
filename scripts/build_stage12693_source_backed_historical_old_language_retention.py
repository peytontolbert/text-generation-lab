#!/usr/bin/env python3
"""Descriptor-pinned historical Git plumbing for the bounded Stage12693 core.

This module verifies immutable Git objects and identifies historical source blobs
absent from pinned current HEAD. It constructs bounded in-memory rows and split plans, but does not scan the
production corpus, publish artifacts, or authorize training.
"""

from __future__ import annotations

import argparse
import collections
import contextvars
import copy
import datetime as dt
import functools
import hashlib
import heapq
import importlib.util
import json
import os
import re
import selectors
import stat
import time
import subprocess
import sys
import unicodedata
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from typing import Any, Iterable


_S88_PATH = Path(__file__).with_name(
    "build_stage12688_source_backed_multilingual_knowledge_corpus.py"
)
_S88_RAW = _S88_PATH.read_bytes()
if hashlib.sha256(_S88_RAW).hexdigest() != "66bb3fd3c47305f3598f3eb91c9398839614d2ec68b3c3bc36f2fa8e238f490e":
    raise RuntimeError("stage12688_helper_digest_mismatch")
_S88_SPEC = importlib.util.spec_from_file_location("stage12688_for_stage12693", _S88_PATH)
if _S88_SPEC is None or _S88_SPEC.loader is None:
    raise RuntimeError("stage12688_helper_import_unavailable")
S88 = importlib.util.module_from_spec(_S88_SPEC)
sys.modules[_S88_SPEC.name] = S88
try:
    exec(compile(_S88_RAW, os.fspath(_S88_PATH), "exec", dont_inherit=True), S88.__dict__)
except BaseException:
    sys.modules.pop(_S88_SPEC.name, None)
    raise


STAGE = "stage12693_source_backed_historical_old_language_retention"
AGE_REFERENCE = dt.datetime(2026, 8, 3, tzinfo=dt.timezone.utc)
REQUIRED_LANGUAGES = tuple(S88.REQUIRED_RETENTION_LANGUAGES)
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

OID_RE = re.compile(r"(?:[0-9a-f]{40}|[0-9a-f]{64})\Z")
COMMITTER_RE = re.compile(br"committer .+ ([0-9]+) ([+-])([0-9]{2})([0-9]{2})\Z")
MAX_COMMIT_OBJECT_BYTES = 4 * 1024 * 1024
MAX_TREE_OBJECT_BYTES = 16 * 1024 * 1024
MAX_BLOB_OBJECT_BYTES = 32 * 1024 * 1024
MAX_GIT_STDOUT_BYTES = MAX_BLOB_OBJECT_BYTES
MAX_TREE_DEPTH = 64
MAX_TREE_ENTRIES_PER_TREE = 100_000
MAX_TREE_ENTRIES_TOTAL = 500_000
MAX_TREE_OBJECTS = 250_000
MAX_HISTORY_COMMITS = 100_000
MAX_REVISION_MATERIALS = 2_000
MAX_TOTAL_BLOB_BYTES_READ = 512 * 1024 * 1024
MAX_CUMULATIVE_OBJECT_READS = 1_000_000
MAX_CUMULATIVE_TREE_WORK = 1_000_000
MAX_ELIGIBLE_SPANS_CONSIDERED = 500_000
MAX_COMPARABLE_EXAMPLES = 500_000
MAX_RETAINED_HEAD_EVIDENCE = 2_000_000
DEFAULT_REPOSITORY_BLOB_PAYLOAD_BYTES = 48 * 1024 * 1024
DEFAULT_REPOSITORY_RAW_OBJECT_BYTES = 64 * 1024 * 1024
DEFAULT_REPOSITORY_TREE_VISITS = 250_000
DEFAULT_REPOSITORY_ELIGIBLE_SPANS = 50_000
MAX_SOURCE_CATALOG_BYTES = 32 * 1024 * 1024
MAX_SOURCE_CATALOG_RECORDS = 10_000
MAX_REPOSITORY_CACHE_OBJECTS = 500_000
MAX_REPOSITORY_CACHE_BYTES = 512 * 1024 * 1024
MAX_REPOSITORY_BLOB_PAYLOAD_CACHE_BYTES = 256 * 1024 * 1024
MAX_REPOSITORY_TREE_OBJECT_CACHE_BYTES = 128 * 1024 * 1024
MAX_REPOSITORY_COMMIT_OBJECT_CACHE_BYTES = 128 * 1024 * 1024
MAX_REPOSITORY_CACHE_HEAD_EVIDENCE = 2_000_000
DEFAULT_SCAN_MAX_LOCAL_DIRECTORIES = 2_000
DEFAULT_SCAN_MAX_REPOSITORIES = 800
DEFAULT_SCAN_MAX_MATERIALS = 800
DEFAULT_SCAN_MAX_MATERIALS_PER_REPOSITORY = 1
DEFAULT_SCAN_MAX_COMMITS_PER_REPOSITORY = 512
DEFAULT_SCAN_MAX_SECONDARY_PARENTS_PER_REPOSITORY = 32
DEFAULT_SCAN_MAX_ROWS_PER_REPOSITORY = S88.MAX_ROWS_PER_REPO
DEFAULT_SCAN_REQUESTED_ROWS = 10_000
_WORKSPACE_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_STAGE12688_SUMMARY = (
    _WORKSPACE_ROOT
    / "runs/local/artifacts/stage12688_source_backed_multilingual_knowledge_corpus/summary.json"
)
DEFAULT_SCAN_SOURCE_ROOT = S88.DEFAULT_SOURCE_ROOT
AUTHORITATIVE_STAGE12688_CATALOG = (
    _WORKSPACE_ROOT
    / "runs/local/artifacts/stage12688_source_backed_multilingual_knowledge_corpus"
    / "private/23cac72b1c420605413d0f77/train_eval_source_catalog.jsonl"
)
AUTHORITATIVE_STAGE12688_CATALOG_SHA256 = (
    "efdc8a4c3051e1621242fad34d82e0b2d5586c2373d438bcca2e12c5a51b98bb"
)
STAGE12693_SUMMARY_OUTPUT_ROOT = (
    _WORKSPACE_ROOT / "runs/local/artifacts" / STAGE / "capacity_summaries"
)


class Stage12693Error(RuntimeError):
    pass


@dataclass(frozen=True)
class Stage12693WorkLimits:
    total_blob_bytes_read: int = MAX_TOTAL_BLOB_BYTES_READ
    object_reads: int = MAX_CUMULATIVE_OBJECT_READS
    tree_work: int = MAX_CUMULATIVE_TREE_WORK
    eligible_spans_considered: int = MAX_ELIGIBLE_SPANS_CONSIDERED
    comparable_examples: int = MAX_COMPARABLE_EXAMPLES
    retained_head_evidence: int = MAX_RETAINED_HEAD_EVIDENCE

    def __post_init__(self) -> None:
        if min(
            self.total_blob_bytes_read,
            self.object_reads,
            self.tree_work,
            self.eligible_spans_considered,
            self.comparable_examples,
            self.retained_head_evidence,
        ) <= 0:
            raise Stage12693Error("invalid_cumulative_work_limit")


@dataclass
class Stage12693WorkBudget:
    limits: Stage12693WorkLimits
    total_blob_bytes_read: int = 0
    object_reads: int = 0
    tree_work: int = 0
    eligible_spans_considered: int = 0
    comparable_examples: int = 0
    retained_head_evidence: int = 0
    repository_caches: dict[tuple[Any, ...], Any] = field(default_factory=dict)

    def consume(self, field: str, amount: int) -> None:
        if amount < 0:
            raise Stage12693Error("negative_cumulative_work")
        next_value = getattr(self, field) + amount
        if next_value > getattr(self.limits, field):
            raise Stage12693Error(f"cumulative_{field}_limit_exceeded")
        setattr(self, field, next_value)


_ACTIVE_WORK_BUDGET: contextvars.ContextVar[Stage12693WorkBudget | None] = (
    contextvars.ContextVar("stage12693_work_budget", default=None)
)


@contextmanager
def cumulative_work_scope(
    limits: Stage12693WorkLimits | None = None,
):
    existing = _ACTIVE_WORK_BUDGET.get()
    if existing is not None:
        if limits is not None and limits != existing.limits:
            raise Stage12693Error("nested_cumulative_work_limit_mismatch")
        yield existing
        return
    budget = Stage12693WorkBudget(limits or Stage12693WorkLimits())
    token = _ACTIVE_WORK_BUDGET.set(budget)
    try:
        yield budget
    finally:
        _ACTIVE_WORK_BUDGET.reset(token)


def _consume_work(field: str, amount: int = 1) -> None:
    budget = _ACTIVE_WORK_BUDGET.get()
    if budget is not None:
        budget.consume(field, amount)


@dataclass(frozen=True)
class RepositoryWorkLimits:
    blob_payload_bytes: int = DEFAULT_REPOSITORY_BLOB_PAYLOAD_BYTES
    raw_object_bytes: int = DEFAULT_REPOSITORY_RAW_OBJECT_BYTES
    tree_visits: int = DEFAULT_REPOSITORY_TREE_VISITS
    commits: int = DEFAULT_SCAN_MAX_COMMITS_PER_REPOSITORY
    eligible_spans_considered: int = DEFAULT_REPOSITORY_ELIGIBLE_SPANS

    def __post_init__(self) -> None:
        if min(
            self.blob_payload_bytes,
            self.raw_object_bytes,
            self.tree_visits,
            self.commits,
            self.eligible_spans_considered,
        ) <= 0:
            raise Stage12693Error("invalid_repository_work_limit")


@dataclass
class RepositoryWorkBudget:
    limits: RepositoryWorkLimits
    blob_payload_bytes: int = 0
    raw_object_bytes: int = 0
    tree_visits: int = 0
    commits: int = 0
    eligible_spans_considered: int = 0

    def consume(self, field: str, amount: int = 1) -> None:
        next_value = getattr(self, field) + amount
        if amount < 0 or next_value > getattr(self.limits, field):
            raise Stage12693Error(f"repository_{field}_quota_exceeded")
        setattr(self, field, next_value)


_ACTIVE_REPOSITORY_WORK_BUDGET: contextvars.ContextVar[
    RepositoryWorkBudget | None
] = contextvars.ContextVar("stage12693_repository_work_budget", default=None)


@contextmanager
def repository_work_scope(limits: RepositoryWorkLimits):
    if _ACTIVE_REPOSITORY_WORK_BUDGET.get() is not None:
        raise Stage12693Error("nested_repository_work_scope")
    budget = RepositoryWorkBudget(limits)
    token = _ACTIVE_REPOSITORY_WORK_BUDGET.set(budget)
    try:
        yield budget
    finally:
        _ACTIVE_REPOSITORY_WORK_BUDGET.reset(token)


def _consume_repository_work(field: str, amount: int = 1) -> None:
    budget = _ACTIVE_REPOSITORY_WORK_BUDGET.get()
    if budget is not None:
        budget.consume(field, amount)


def cumulative_bounded(function):
    @functools.wraps(function)
    def wrapped(*args, work_limits: Stage12693WorkLimits | None = None, **kwargs):
        with cumulative_work_scope(work_limits):
            return function(*args, **kwargs)
    return wrapped


@dataclass(frozen=True)
class CommitObject:
    oid: str
    tree_oid: str
    parent_oids: tuple[str, ...]
    committer_epoch: int
    committer_timezone: str


@dataclass(frozen=True)
class HistoryEdge:
    child_oid: str
    child_tree_oid: str
    parent_oid: str
    parent_tree_oid: str
    parent_committer_epoch: int
    parent_committer_timezone: str
    age_bucket: str | None


@dataclass(frozen=True)
class GitTreeEntry:
    mode: str
    object_type: str
    oid: str
    path: str


@dataclass(frozen=True)
class CurrentHeadExclusionInventory:
    pinned_head_oid: str
    head_tree_oid: str
    blob_oids: frozenset[str]
    tree_oids: frozenset[str]
    file_sha256s: frozenset[str]
    inventory_sha256: str


@dataclass(frozen=True)
class HistoricalBlobCandidate:
    pinned_head_oid: str
    child_commit_oid: str
    parent_commit_oid: str
    parent_tree_oid: str
    parent_committer_epoch: int
    parent_committer_timezone: str
    age_bucket: str
    path: str
    blob_oid: str
    file_sha256: str
    language_family: str
    file_role: str
    data: bytes


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _git_object_oid(object_type: str, data: bytes, width: int) -> str:
    framed = f"{object_type} {len(data)}\0".encode("ascii") + data
    if width == 40:
        return hashlib.sha1(framed).hexdigest()
    if width == 64:
        return hashlib.sha256(framed).hexdigest()
    raise Stage12693Error("unsupported_object_format")


def verify_object_oid(oid: str, object_type: str, data: bytes) -> bool:
    return bool(OID_RE.fullmatch(oid)) and _git_object_oid(object_type, data, len(oid)) == oid


@dataclass
class RepositoryEvidenceCache:
    identity: tuple[Any, ...]
    pinned_head_oid: str = ""
    object_metadata: dict[tuple[str, str], int] = field(default_factory=dict)
    raw_objects: dict[tuple[str, str], bytes] = field(default_factory=dict)
    raw_object_bytes: int = 0
    raw_object_bytes_by_type: collections.Counter[str] = field(
        default_factory=collections.Counter
    )
    parsed_commits: dict[str, CommitObject] = field(default_factory=dict)
    parsed_trees: dict[str, tuple[GitTreeEntry, ...]] = field(default_factory=dict)
    validated_tree_oids: set[str] = field(default_factory=set)
    head_inventories: dict[str, CurrentHeadExclusionInventory] = field(
        default_factory=dict
    )
    head_examples: dict[tuple[str, str], CurrentHeadExampleExclusion] = field(
        default_factory=dict
    )
    head_evidence_items: int = 0
    counters: collections.Counter[str] = field(
        default_factory=collections.Counter
    )

    def bind_head(self, oid: str) -> None:
        if self.pinned_head_oid and self.pinned_head_oid != oid:
            raise Stage12693Error("repository_cache_head_mismatch")
        self.pinned_head_oid = oid

    def retain_raw(
        self, key: tuple[str, str], data: bytes,
    ) -> None:
        if key in self.raw_objects:
            raise Stage12693Error("duplicate_repository_raw_cache_insert")
        if len(self.raw_objects) >= MAX_REPOSITORY_CACHE_OBJECTS:
            raise Stage12693Error("repository_object_cache_entry_limit_exceeded")
        if self.raw_object_bytes + len(data) > MAX_REPOSITORY_CACHE_BYTES:
            raise Stage12693Error("repository_object_cache_byte_limit_exceeded")
        object_type = key[1]
        type_limits = {
            "blob": MAX_REPOSITORY_BLOB_PAYLOAD_CACHE_BYTES,
            "tree": MAX_REPOSITORY_TREE_OBJECT_CACHE_BYTES,
            "commit": MAX_REPOSITORY_COMMIT_OBJECT_CACHE_BYTES,
        }
        if (
            object_type not in type_limits
            or self.raw_object_bytes_by_type[object_type] + len(data)
            > type_limits[object_type]
        ):
            raise Stage12693Error(
                f"repository_{object_type}_cache_byte_limit_exceeded"
            )
        self.raw_objects[key] = data
        self.raw_object_bytes += len(data)
        self.raw_object_bytes_by_type[object_type] += len(data)

    def retain_head_evidence(self, item_count: int) -> None:
        if (
            item_count < 0
            or self.head_evidence_items + item_count
            > MAX_REPOSITORY_CACHE_HEAD_EVIDENCE
        ):
            raise Stage12693Error(
                "repository_head_evidence_cache_limit_exceeded"
            )
        self.head_evidence_items += item_count


def _descriptor_identity(fd: int) -> tuple[int, int]:
    metadata = os.fstat(fd)
    return metadata.st_dev, metadata.st_ino


def _repository_cache_for_descriptors(
    repo_fd: int,
    git_fd: int,
    root_fd: int | None,
) -> RepositoryEvidenceCache:
    budget = _ACTIVE_WORK_BUDGET.get()
    root_identity = _descriptor_identity(
        repo_fd if root_fd is None else root_fd
    )
    identity = (
        id(budget),
        root_identity,
        _descriptor_identity(repo_fd),
        _descriptor_identity(git_fd),
    )
    if budget is None:
        return RepositoryEvidenceCache(identity)
    cache = budget.repository_caches.get(identity)
    if cache is None:
        cache = RepositoryEvidenceCache(identity)
        budget.repository_caches[identity] = cache
        cache.counters["repository_cache_created"] += 1
    else:
        cache.counters["repository_cache_reused"] += 1
    return cache


class PinnedRepository:
    """Pinned work-tree and Git-directory descriptors for read-only commands."""

    def __init__(
        self,
        path: Path,
        repo_fd: int,
        git_fd: int,
        cache: RepositoryEvidenceCache,
    ) -> None:
        self.path = path
        self.repo_fd = repo_fd
        self.git_fd = git_fd
        self.cache = cache
        self.head_oid = ""
        self.cache.counters["repository_pin_count"] += 1

    def close(self) -> None:
        for attribute in ("git_fd", "repo_fd"):
            fd = getattr(self, attribute, -1)
            if fd >= 0:
                os.close(fd)
                setattr(self, attribute, -1)

    def __enter__(self) -> "PinnedRepository":
        return self

    def __exit__(self, _type: object, _value: object, _traceback: object) -> None:
        self.close()

    def git(
        self, *args: str, timeout: int = 60, max_stdout_bytes: int = 256
    ) -> bytes:
        allowed_shape = (
            args == ("rev-parse", "--verify", "HEAD^{commit}")
            or (
                len(args) == 3 and args[0] == "cat-file"
                and args[1] in {"-t", "-s", "blob", "commit", "tree"}
                and bool(OID_RE.fullmatch(args[2]))
            )
        )
        if (
            self.repo_fd < 0 or self.git_fd < 0 or not allowed_shape
            or not 0 < max_stdout_bytes <= MAX_GIT_STDOUT_BYTES
        ):
            raise Stage12693Error("disallowed_or_closed_git_command")
        env = {
            "GIT_CONFIG_GLOBAL": "/dev/null",
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_OPTIONAL_LOCKS": "0",
            "HOME": "/nonexistent",
            "LC_ALL": "C",
            "PATH": os.defpath,
        }
        command = [
            "git", "--no-replace-objects",
            f"--git-dir=/proc/self/fd/{self.git_fd}",
            f"--work-tree=/proc/self/fd/{self.repo_fd}",
            *args,
        ]
        try:
            process = subprocess.Popen(
                command, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                env=env, pass_fds=(self.repo_fd, self.git_fd),
            )
            assert process.stdout is not None
            os.set_blocking(process.stdout.fileno(), False)
            deadline = time.monotonic() + timeout
            chunks: list[bytes] = []
            total = 0
            with selectors.DefaultSelector() as selector:
                selector.register(process.stdout, selectors.EVENT_READ)
                while True:
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        raise Stage12693Error("read_only_git_timeout")
                    events = selector.select(remaining)
                    if not events:
                        raise Stage12693Error("read_only_git_timeout")
                    chunk = os.read(
                        process.stdout.fileno(),
                        min(64 * 1024, max_stdout_bytes - total + 1),
                    )
                    if not chunk:
                        break
                    chunks.append(chunk)
                    total += len(chunk)
                    if total > max_stdout_bytes:
                        raise Stage12693Error("git_stdout_limit_exceeded")
            returncode = process.wait(timeout=max(0.001, deadline - time.monotonic()))
            output = b"".join(chunks)
        except (OSError, subprocess.TimeoutExpired, Stage12693Error) as exc:
            if "process" in locals() and process.poll() is None:
                process.kill()
                process.wait()
            if isinstance(exc, Stage12693Error):
                raise
            if isinstance(exc, subprocess.TimeoutExpired):
                raise Stage12693Error("read_only_git_timeout") from exc
            raise Stage12693Error(f"read_only_git_failed:{args[0]}") from exc
        if returncode != 0:
            raise Stage12693Error(f"read_only_git_failed:{args[0]}")
        return output


def _open_directory(name: str | Path, *, dir_fd: int | None = None) -> int:
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
    try:
        fd = os.open(name, flags, dir_fd=dir_fd)
    except OSError as exc:
        raise Stage12693Error("repository_directory_pin_failed") from exc
    if not stat.S_ISDIR(os.fstat(fd).st_mode):
        os.close(fd)
        raise Stage12693Error("repository_component_not_directory")
    return fd


@cumulative_bounded
def pin_repository(path: Path) -> PinnedRepository:
    if not path.is_absolute():
        raise Stage12693Error("repository_path_must_be_absolute")
    repo_fd = _open_directory(path)
    try:
        git_fd = _open_directory(".git", dir_fd=repo_fd)
    except Exception:
        os.close(repo_fd)
        raise
    pinned = PinnedRepository(
        path,
        repo_fd,
        git_fd,
        _repository_cache_for_descriptors(repo_fd, git_fd, None),
    )
    try:
        head_oid = pinned.git("rev-parse", "--verify", "HEAD^{commit}").decode("ascii").strip().lower()
        if not OID_RE.fullmatch(head_oid):
            raise Stage12693Error("invalid_head_oid")
        read_verified_object(pinned, head_oid, "commit")
        pinned.cache.bind_head(head_oid)
        pinned.head_oid = head_oid
        return pinned
    except Exception:
        pinned.close()
        raise


def _canonical_repository_entry_name(name: str) -> bool:
    return bool(
        name
        and name not in {".", ".."}
        and "/" not in name
        and "\\" not in name
        and "\x00" not in name
    )


@cumulative_bounded
def pin_repository_at(
    source_root_fd: int,
    name: str,
    display_root: Path,
) -> PinnedRepository:
    if source_root_fd < 0 or not _canonical_repository_entry_name(name):
        raise Stage12693Error("invalid_repository_entry_name")
    repo_fd = _open_directory(name, dir_fd=source_root_fd)
    try:
        git_fd = _open_directory(".git", dir_fd=repo_fd)
    except Exception:
        os.close(repo_fd)
        raise
    pinned = PinnedRepository(
        display_root / name,
        repo_fd,
        git_fd,
        _repository_cache_for_descriptors(
            repo_fd, git_fd, source_root_fd,
        ),
    )
    try:
        head_oid = pinned.git(
            "rev-parse", "--verify", "HEAD^{commit}",
        ).decode("ascii").strip().lower()
        if not OID_RE.fullmatch(head_oid):
            raise Stage12693Error("invalid_head_oid")
        read_verified_object(pinned, head_oid, "commit")
        pinned.cache.bind_head(head_oid)
        pinned.head_oid = head_oid
        return pinned
    except Exception:
        pinned.close()
        raise


@cumulative_bounded
def verified_object_size(
    repo: PinnedRepository,
    oid: str,
    object_type: str,
    *,
    enforce_payload_limit: bool = True,
) -> int:
    if object_type not in {"blob", "commit", "tree"} or not OID_RE.fullmatch(oid):
        raise Stage12693Error("invalid_object_request")
    limits = {
        "blob": MAX_BLOB_OBJECT_BYTES,
        "commit": MAX_COMMIT_OBJECT_BYTES,
        "tree": MAX_TREE_OBJECT_BYTES,
    }
    key = (oid, object_type)
    cached = repo.cache.object_metadata.get(key)
    if cached is not None:
        repo.cache.counters["object_metadata_cache_hits"] += 1
        if enforce_payload_limit and cached > limits[object_type]:
            raise Stage12693Error(f"{object_type}_size_limit_exceeded")
        return cached
    _consume_work("object_reads")
    repo.cache.counters["object_metadata_reads"] += 1
    try:
        actual_type = repo.git(
            "cat-file", "-t", oid, max_stdout_bytes=16,
        ).decode("ascii").strip()
        raw_size = repo.git(
            "cat-file", "-s", oid, max_stdout_bytes=32,
        ).decode("ascii").strip()
    except UnicodeDecodeError as exc:
        raise Stage12693Error("invalid_object_metadata_response") from exc
    if (
        actual_type != object_type
        or not re.fullmatch(r"(?:0|[1-9][0-9]*)", raw_size)
    ):
        raise Stage12693Error("object_metadata_mismatch")
    size = int(raw_size)
    if enforce_payload_limit and size > limits[object_type]:
        raise Stage12693Error(f"{object_type}_size_limit_exceeded")
    if len(repo.cache.object_metadata) >= MAX_REPOSITORY_CACHE_OBJECTS:
        raise Stage12693Error("repository_metadata_cache_limit_exceeded")
    repo.cache.object_metadata[key] = size
    return size


@cumulative_bounded
def read_verified_object(repo: PinnedRepository, oid: str, object_type: str) -> bytes:
    key = (oid, object_type)
    cached = repo.cache.raw_objects.get(key)
    if cached is not None:
        repo.cache.counters["raw_object_cache_hits"] += 1
        repo.cache.counters[f"{object_type}_cache_hits"] += 1
        return cached
    size = verified_object_size(repo, oid, object_type)
    _consume_repository_work("raw_object_bytes", size)
    if object_type == "blob":
        _consume_work("total_blob_bytes_read", size)
        _consume_repository_work("blob_payload_bytes", size)
    data = repo.git(
        "cat-file", object_type, oid, timeout=120,
        max_stdout_bytes=max(1, size),
    )
    if len(data) != size or not verify_object_oid(oid, object_type, data):
        raise Stage12693Error(f"{object_type}_identity_mismatch")
    repo.cache.retain_raw(key, data)
    repo.cache.counters["raw_object_reads"] += 1
    repo.cache.counters["raw_object_bytes_read"] += len(data)
    repo.cache.counters[f"{object_type}_bytes_read"] += len(data)
    repo.cache.counters[f"verified_{object_type}_objects"] += 1
    return data


def parse_raw_commit(data: bytes, oid: str = "") -> CommitObject:
    if b"\x00" in data or b"\n\n" not in data:
        raise Stage12693Error("malformed_commit_object")
    raw_headers, _message = data.split(b"\n\n", 1)
    lines = raw_headers.split(b"\n")
    if not lines or any(not line for line in lines):
        raise Stage12693Error("malformed_commit_headers")
    logical: list[tuple[bytes, bytes]] = []
    critical = {b"tree", b"parent", b"committer"}
    for line in lines:
        if line.startswith(b" "):
            if not logical:
                raise Stage12693Error("invalid_commit_header_continuation")
            key, value = logical[-1]
            if key in critical:
                raise Stage12693Error("critical_commit_header_continuation")
            logical[-1] = (key, value + b"\n" + line[1:])
            continue
        if b" " not in line:
            raise Stage12693Error("malformed_commit_header")
        key, value = line.split(b" ", 1)
        if (
            not key
            or not value
            or re.fullmatch(br"[A-Za-z][A-Za-z0-9-]*", key) is None
        ):
            raise Stage12693Error("malformed_commit_header")
        logical.append((key, value))
    trees = [value for key, value in logical if key == b"tree"]
    parents = [value for key, value in logical if key == b"parent"]
    committers = [
        b"committer " + value
        for key, value in logical
        if key == b"committer"
    ]
    if len(trees) != 1 or len(committers) != 1:
        raise Stage12693Error("invalid_commit_identity_headers")
    try:
        tree_oid = trees[0].decode("ascii")
        parent_oids = tuple(parent.decode("ascii") for parent in parents)
    except UnicodeDecodeError as exc:
        raise Stage12693Error("non_ascii_commit_reference") from exc
    if (
        not OID_RE.fullmatch(tree_oid)
        or any(not OID_RE.fullmatch(parent) for parent in parent_oids)
    ):
        raise Stage12693Error("invalid_commit_reference")
    match = COMMITTER_RE.fullmatch(committers[0])
    if match is None:
        raise Stage12693Error("invalid_committer_timestamp")
    epoch = int(match.group(1))
    hours, minutes = int(match.group(3)), int(match.group(4))
    if hours > 14 or minutes > 59 or (hours == 14 and minutes != 0):
        raise Stage12693Error("invalid_committer_timezone")
    timezone = (match.group(2) + match.group(3) + match.group(4)).decode("ascii")
    return CommitObject(oid, tree_oid, parent_oids, epoch, timezone)


@cumulative_bounded
def read_commit(repo: PinnedRepository, oid: str) -> CommitObject:
    cached = repo.cache.parsed_commits.get(oid)
    if cached is not None:
        repo.cache.counters["parsed_commit_cache_hits"] += 1
        return cached
    _consume_repository_work("commits")
    parsed = parse_raw_commit(
        read_verified_object(repo, oid, "commit"), oid,
    )
    if len(repo.cache.parsed_commits) >= MAX_HISTORY_COMMITS:
        raise Stage12693Error("parsed_commit_cache_limit_exceeded")
    repo.cache.parsed_commits[oid] = parsed
    repo.cache.counters["parsed_commits"] += 1
    if len(parsed.parent_oids) > 1:
        repo.cache.counters["merge_commits"] += 1
    return parsed


def age_bucket(epoch: int, reference: dt.datetime = AGE_REFERENCE) -> str | None:
    if reference.tzinfo is None or reference.utcoffset() is None:
        raise Stage12693Error("naive_age_reference")
    try:
        recorded = dt.datetime.fromtimestamp(epoch, tz=dt.timezone.utc)
        ref = reference.astimezone(dt.timezone.utc)
        two_years = ref.replace(year=ref.year - 2)
        five_years = ref.replace(year=ref.year - 5)
        ten_years = ref.replace(year=ref.year - 10)
    except (OverflowError, OSError, ValueError) as exc:
        raise Stage12693Error("invalid_committer_epoch") from exc
    if recorded > two_years:
        return None
    if recorded > five_years:
        return "historical_2_to_5_years"
    if recorded > ten_years:
        return "historical_5_to_10_years"
    return "historical_10_plus_years"


@cumulative_bounded
def enumerate_single_parent_edges(repo: PinnedRepository) -> tuple[HistoryEdge, ...]:
    commits: dict[str, CommitObject] = {}
    states: dict[str, int] = {}
    stack: list[tuple[str, bool]] = [(repo.head_oid, False)]
    while stack:
        oid, exiting = stack.pop()
        state = states.get(oid, 0)
        if exiting:
            if state != 1:
                raise Stage12693Error("invalid_history_traversal_state")
            states[oid] = 2
            continue
        if state == 2:
            continue
        if state == 1:
            raise Stage12693Error("cyclic_commit_graph")
        if len(commits) >= MAX_HISTORY_COMMITS:
            raise Stage12693Error("history_commit_limit_exceeded")
        commit = read_commit(repo, oid)
        read_verified_object(repo, commit.tree_oid, "tree")
        commits[oid] = commit
        states[oid] = 1
        stack.append((oid, True))
        for parent_oid in reversed(sorted(commit.parent_oids)):
            parent_state = states.get(parent_oid, 0)
            if parent_state == 1:
                raise Stage12693Error("cyclic_commit_graph")
            if parent_state == 0:
                stack.append((parent_oid, False))
    edges: list[HistoryEdge] = []
    for child_oid in sorted(commits):
        child = commits[child_oid]
        if len(child.parent_oids) != 1:
            continue
        parent = commits.get(child.parent_oids[0])
        if parent is None:
            raise Stage12693Error("missing_verified_parent_commit")
        edges.append(HistoryEdge(
            child.oid, child.tree_oid, parent.oid, parent.tree_oid,
            parent.committer_epoch, parent.committer_timezone, age_bucket(parent.committer_epoch),
        ))
    return tuple(edges)


def _canonical_tree_name(raw_name: bytes) -> str:
    try:
        name = raw_name.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise Stage12693Error("non_utf8_tree_name") from exc
    if (
        not name or name in {".", ".."} or "/" in name or "\\" in name
        or any(unicodedata.category(char).startswith("C") for char in name)
    ):
        raise Stage12693Error("noncanonical_tree_name")
    return name


def parse_raw_tree(data: bytes, oid_width: int) -> tuple[GitTreeEntry, ...]:
    if len(data) > MAX_TREE_OBJECT_BYTES:
        raise Stage12693Error("tree_size_limit_exceeded")
    raw_oid_bytes = {40: 20, 64: 32}.get(oid_width)
    if raw_oid_bytes is None:
        raise Stage12693Error("unsupported_object_format")
    entries: list[GitTreeEntry] = []
    cursor = 0
    previous_sort_key: bytes | None = None
    while cursor < len(data):
        if len(entries) >= MAX_TREE_ENTRIES_PER_TREE:
            raise Stage12693Error("tree_entry_limit_exceeded")
        space = data.find(b" ", cursor)
        nul = data.find(b"\0", space + 1)
        if space < 0 or nul < 0:
            raise Stage12693Error("malformed_tree_object")
        try:
            mode = data[cursor:space].decode("ascii")
        except UnicodeDecodeError as exc:
            raise Stage12693Error("malformed_tree_mode") from exc
        raw_name = data[space + 1:nul]
        name = _canonical_tree_name(raw_name)
        oid_end = nul + 1 + raw_oid_bytes
        if oid_end > len(data):
            raise Stage12693Error("truncated_tree_oid")
        object_oid = data[nul + 1:oid_end].hex()
        if mode == "40000":
            object_type = "tree"
        elif mode == "160000":
            object_type = "commit"
        elif mode in {"100644", "100755", "120000"}:
            object_type = "blob"
        else:
            raise Stage12693Error("unsupported_tree_mode")
        sort_key = raw_name + (b"/" if object_type == "tree" else b"\0")
        if previous_sort_key is not None and sort_key <= previous_sort_key:
            raise Stage12693Error("noncanonical_git_tree_order")
        previous_sort_key = sort_key
        _consume_work("tree_work")
        entries.append(GitTreeEntry(mode, object_type, object_oid, name))
        cursor = oid_end
    return tuple(entries)


def _parsed_tree_entries(
    repo: PinnedRepository,
    tree_oid: str,
) -> tuple[GitTreeEntry, ...]:
    cached = repo.cache.parsed_trees.get(tree_oid)
    if cached is not None:
        repo.cache.counters["parsed_tree_cache_hits"] += 1
        return cached
    _consume_work("tree_work")
    entries = parse_raw_tree(
        read_verified_object(repo, tree_oid, "tree"),
        len(tree_oid),
    )
    if len(repo.cache.parsed_trees) >= MAX_TREE_OBJECTS:
        raise Stage12693Error("parsed_tree_cache_limit_exceeded")
    repo.cache.parsed_trees[tree_oid] = entries
    repo.cache.counters["parsed_trees"] += 1
    return entries


@cumulative_bounded
def list_tree_immediate(repo: PinnedRepository, tree_oid: str) -> tuple[GitTreeEntry, ...]:
    entries = _parsed_tree_entries(repo, tree_oid)
    if tree_oid in repo.cache.validated_tree_oids:
        repo.cache.counters["validated_tree_cache_hits"] += 1
        return entries
    for entry in entries:
        if entry.object_type in {"blob", "tree"}:
            read_verified_object(repo, entry.oid, entry.object_type)
    repo.cache.validated_tree_oids.add(tree_oid)
    repo.cache.counters["validated_trees"] += 1
    return entries


@cumulative_bounded
def list_tree_recursive(repo: PinnedRepository, tree_oid: str) -> tuple[GitTreeEntry, ...]:
    collected: list[GitTreeEntry] = []
    active: set[str] = set()
    tree_visits = 0

    def walk(current_oid: str, prefix: str, depth: int) -> None:
        nonlocal tree_visits
        if depth > MAX_TREE_DEPTH:
            raise Stage12693Error("tree_depth_limit_exceeded")
        if current_oid in active:
            raise Stage12693Error("cyclic_tree_graph")
        tree_visits += 1
        if tree_visits > MAX_TREE_OBJECTS:
            raise Stage12693Error("tree_object_limit_exceeded")
        active.add(current_oid)
        try:
            for entry in list_tree_immediate(repo, current_oid):
                if len(collected) >= MAX_TREE_ENTRIES_TOTAL:
                    raise Stage12693Error("total_tree_entry_limit_exceeded")
                path = entry.path if not prefix else f"{prefix}/{entry.path}"
                full = GitTreeEntry(entry.mode, entry.object_type, entry.oid, path)
                collected.append(full)
                if entry.object_type == "tree":
                    walk(entry.oid, path, depth + 1)
        finally:
            active.remove(current_oid)

    walk(tree_oid, "", 0)
    return tuple(collected)


@cumulative_bounded
def _typed_metadata_tree_entries(
    repo: PinnedRepository, tree_oid: str,
) -> tuple[GitTreeEntry, ...]:
    _consume_work("tree_work")
    _consume_repository_work("tree_visits")
    entries = _parsed_tree_entries(repo, tree_oid)
    for entry in entries:
        _consume_work("tree_work")
        _consume_repository_work("tree_visits")
        verified_object_size(
            repo,
            entry.oid,
            entry.object_type,
            enforce_payload_limit=entry.object_type != "blob",
        )
    return entries


@cumulative_bounded
def list_tree_metadata_recursive(
    repo: PinnedRepository, tree_oid: str,
) -> tuple[GitTreeEntry, ...]:
    collected: list[GitTreeEntry] = []
    active: set[str] = set()
    tree_visits = 0

    def walk(current_oid: str, prefix: str, depth: int) -> None:
        nonlocal tree_visits
        if depth > MAX_TREE_DEPTH:
            raise Stage12693Error("tree_depth_limit_exceeded")
        if current_oid in active:
            raise Stage12693Error("cyclic_tree_graph")
        tree_visits += 1
        if tree_visits > MAX_TREE_OBJECTS:
            raise Stage12693Error("tree_object_limit_exceeded")
        active.add(current_oid)
        try:
            for entry in _typed_metadata_tree_entries(repo, current_oid):
                if len(collected) >= MAX_TREE_ENTRIES_TOTAL:
                    raise Stage12693Error("total_tree_entry_limit_exceeded")
                path = entry.path if not prefix else f"{prefix}/{entry.path}"
                full = GitTreeEntry(
                    entry.mode, entry.object_type, entry.oid, path,
                )
                collected.append(full)
                if entry.object_type == "tree":
                    walk(entry.oid, path, depth + 1)
        finally:
            active.remove(current_oid)

    walk(tree_oid, "", 0)
    return tuple(collected)


@cumulative_bounded
def changed_supported_parent_tree_entries(
    repo: PinnedRepository,
    child_tree_oid: str,
    parent_tree_oid: str,
) -> tuple[GitTreeEntry, ...]:
    changed: list[GitTreeEntry] = []
    active: set[tuple[str, str]] = set()

    def walk(child_oid: str | None, parent_oid: str, prefix: str, depth: int) -> None:
        if depth > MAX_TREE_DEPTH:
            raise Stage12693Error("tree_depth_limit_exceeded")
        _consume_work("tree_work")
        _consume_repository_work("tree_visits")
        if child_oid == parent_oid:
            return
        identity = (child_oid or "", parent_oid)
        if identity in active:
            raise Stage12693Error("cyclic_tree_graph")
        active.add(identity)
        try:
            child_entries = (
                {
                    entry.path: entry
                    for entry in _typed_metadata_tree_entries(repo, child_oid)
                }
                if child_oid is not None else {}
            )
            parent_entries = {
                entry.path: entry
                for entry in _typed_metadata_tree_entries(repo, parent_oid)
            }
            for name in sorted(
                parent_entries, key=lambda value: value.encode("utf-8")
            ):
                parent_entry = parent_entries[name]
                child_entry = child_entries.get(name)
                path = name if not prefix else f"{prefix}/{name}"
                if (
                    child_entry is not None
                    and child_entry.mode == parent_entry.mode
                    and child_entry.object_type == parent_entry.object_type
                    and child_entry.oid == parent_entry.oid
                ):
                    continue
                if parent_entry.object_type == "tree":
                    paired_child_oid = (
                        child_entry.oid
                        if child_entry is not None
                        and child_entry.object_type == "tree"
                        else None
                    )
                    walk(paired_child_oid, parent_entry.oid, path, depth + 1)
                    continue
                if (
                    parent_entry.object_type == "blob"
                    and parent_entry.mode in {"100644", "100755"}
                    and classify_required_language(path) is not None
                ):
                    size = verified_object_size(
                        repo, parent_entry.oid, "blob",
                        enforce_payload_limit=False,
                    )
                    if S88.MIN_FILE_BYTES <= size <= S88.MAX_FILE_BYTES:
                        changed.append(GitTreeEntry(
                            parent_entry.mode,
                            parent_entry.object_type,
                            parent_entry.oid,
                            path,
                        ))
        finally:
            active.remove(identity)

    walk(child_tree_oid, parent_tree_oid, "", 0)
    return tuple(changed)


@cumulative_bounded
def build_current_head_exclusion_inventory(repo: PinnedRepository) -> CurrentHeadExclusionInventory:
    cached = repo.cache.head_inventories.get(repo.head_oid)
    if cached is not None:
        repo.cache.counters["head_inventory_cache_hits"] += 1
        return cached
    head = read_commit(repo, repo.head_oid)
    recursive = list_tree_metadata_recursive(repo, head.tree_oid)
    blob_oids: set[str] = set()
    tree_oids: set[str] = set()
    file_sha256s: set[str] = set()

    _consume_work("retained_head_evidence")
    tree_oids.add(head.tree_oid)
    for entry in recursive:
        destination = (
            blob_oids if entry.object_type == "blob"
            else tree_oids if entry.object_type == "tree"
            else None
        )
        if destination is not None and entry.oid not in destination:
            _consume_work("retained_head_evidence")
            destination.add(entry.oid)
    comparable_entries = tuple(
        entry for entry in recursive
        if entry.object_type == "blob"
        and entry.mode in {"100644", "100755"}
        and classify_required_language(entry.path) is not None
        and S88.MIN_FILE_BYTES
        <= verified_object_size(
            repo, entry.oid, "blob", enforce_payload_limit=False,
        )
        <= S88.MAX_FILE_BYTES
    )
    for entry in comparable_entries:
        digest = _sha256(read_verified_object(repo, entry.oid, "blob"))
        if digest not in file_sha256s:
            _consume_work("retained_head_evidence")
            file_sha256s.add(digest)
    inventory_sha256 = S88.stable([
        "stage12693_comparable_current_head_exclusion_v2",
        repo.head_oid, head.tree_oid,
        sorted(blob_oids), sorted(tree_oids), sorted(file_sha256s),
    ])
    inventory = CurrentHeadExclusionInventory(
        repo.head_oid, head.tree_oid, frozenset(blob_oids), frozenset(tree_oids),
        frozenset(file_sha256s), inventory_sha256,
    )
    repo.cache.retain_head_evidence(
        len(blob_oids) + len(tree_oids) + len(file_sha256s)
    )
    repo.cache.head_inventories[repo.head_oid] = inventory
    repo.cache.counters["head_inventory_builds"] += 1
    return inventory


@cumulative_bounded
def validate_current_head_exclusion_inventory(
    repo: PinnedRepository, inventory: CurrentHeadExclusionInventory
) -> None:
    expected = build_current_head_exclusion_inventory(repo)
    if inventory != expected:
        raise Stage12693Error("forged_or_stale_head_exclusion_inventory")


def classify_required_language(path: str) -> S88.FileKind | None:
    kind = S88.classify_path(path)
    return kind if kind is not None and kind.language_family in REQUIRED_LANGUAGES else None


def historical_content_rejection_reason(data: bytes) -> str | None:
    return S88.content_rejection_reason(data)


@cumulative_bounded
def select_historical_blobs_absent_from_current_head(
    repo: PinnedRepository,
    edge: HistoryEdge,
    inventory: CurrentHeadExclusionInventory,
) -> tuple[HistoricalBlobCandidate, ...]:
    validate_current_head_exclusion_inventory(repo, inventory)
    child = read_commit(repo, edge.child_oid)
    if (
        len(child.parent_oids) != 1 or child.parent_oids[0] != edge.parent_oid
        or child.tree_oid != edge.child_tree_oid
    ):
        raise Stage12693Error("history_edge_identity_mismatch")
    parent = read_commit(repo, edge.parent_oid)
    if (
        parent.tree_oid != edge.parent_tree_oid
        or parent.committer_epoch != edge.parent_committer_epoch
        or parent.committer_timezone != edge.parent_committer_timezone
        or age_bucket(parent.committer_epoch) != edge.age_bucket
    ):
        raise Stage12693Error("parent_history_identity_mismatch")
    if edge.age_bucket is None:
        return ()
    candidates: list[HistoricalBlobCandidate] = []
    for entry in changed_supported_parent_tree_entries(
        repo, child.tree_oid, parent.tree_oid,
    ):
        if (
            entry.object_type != "blob" or entry.mode not in {"100644", "100755"}
            or entry.oid in inventory.blob_oids
        ):
            continue
        kind = classify_required_language(entry.path)
        if kind is None:
            continue
        size = verified_object_size(
            repo, entry.oid, "blob", enforce_payload_limit=False,
        )
        if not S88.MIN_FILE_BYTES <= size <= S88.MAX_FILE_BYTES:
            continue
        data = read_verified_object(repo, entry.oid, "blob")
        digest = _sha256(data)
        if digest in inventory.file_sha256s or historical_content_rejection_reason(data) is not None:
            continue
        candidates.append(HistoricalBlobCandidate(
            repo.head_oid, edge.child_oid, edge.parent_oid, edge.parent_tree_oid,
            edge.parent_committer_epoch, edge.parent_committer_timezone, edge.age_bucket,
            entry.path, entry.oid, digest, kind.language_family, kind.file_role, data,
        ))
    return tuple(sorted(
        candidates,
        key=lambda item: S88.stable([
            "stage12693_target_independent_blob_selection_v1", repo.head_oid,
            edge.parent_oid, item.path, item.blob_oid, item.file_sha256,
        ]),
    ))


HISTORICAL_OBJECTIVES = {
    "multilingual_exact_source_span_infilling":
        "historical_multilingual_exact_source_span_infilling",
    "exact_pinned_immediate_directory_entry_name_completion":
        "historical_exact_pinned_immediate_directory_entry_name_completion",
}
DEFAULT_REPOSITORY_ROW_CAP = S88.MAX_ROWS_PER_REPO


@dataclass
class HistoricalRevisionMaterial:
    repository_key_sha256: str
    pinned_head_oid: str
    edge: HistoryEdge
    lineage_commit_oids: frozenset[str]
    tree_oids: frozenset[str]
    blob_oids: frozenset[str]
    component_key: str = ""
    verified_row_source_bindings: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True)
class CurrentHeadExampleExclusion:
    base_inventory: CurrentHeadExclusionInventory
    encoder_input_sha256s: frozenset[str]
    model_example_sha256s: frozenset[str]
    semantic_example_sha256s: frozenset[str]
    source_window_sha256s: frozenset[str]
    commitment_sha256: str


@dataclass(frozen=True)
class HistoricalRevisionRows:
    material: HistoricalRevisionMaterial
    rows: tuple[dict[str, Any], ...]
    proofs: tuple[dict[str, Any], ...]


@dataclass(frozen=True)
class RetentionPlanningGates:
    required_languages: tuple[str, ...] = ()
    required_age_buckets: tuple[str, ...] = ()
    min_rows_per_language_per_split: int = 0
    min_rows_per_age_bucket_per_split: int = 0


@dataclass(frozen=True)
class HistoricalSplitPlan:
    train_rows: tuple[dict[str, Any], ...]
    eval_rows: tuple[dict[str, Any], ...]
    train_proofs: tuple[dict[str, Any], ...]
    eval_proofs: tuple[dict[str, Any], ...]
    strict_planned_count: int
    strict_commitment_sha256: str
    component_splits: tuple[tuple[str, str], ...]
    language_counts_by_split: dict[str, dict[str, int]]
    age_bucket_counts_by_split: dict[str, dict[str, int]]
    authority: dict[str, bool]


def _stage12688_mode(entry: GitTreeEntry) -> str:
    return "040000" if entry.mode == "40000" else entry.mode


def _tree_oid_by_directory(
    repo: PinnedRepository, root_tree_oid: str
) -> dict[str, str]:
    result = {".": root_tree_oid}
    for entry in list_tree_metadata_recursive(repo, root_tree_oid):
        if entry.object_type == "tree":
            result[entry.path] = entry.oid
    return result


def _stage12688_directory_inventories(
    repo: PinnedRepository,
    root_tree_oid: str,
    blobs: Iterable[S88.Blob],
) -> dict[str, Any]:
    tree_oids = _tree_oid_by_directory(repo, root_tree_oid)
    inventories: dict[str, Any] = {}
    for parent_path in sorted({str(PurePosixPath(blob.path).parent) for blob in blobs}):
        tree_oid = tree_oids.get(parent_path)
        if tree_oid is None:
            raise Stage12693Error("historical_parent_directory_tree_missing")
        converted = []
        for entry in _parsed_tree_entries(repo, tree_oid):
            size = (
                verified_object_size(
                    repo, entry.oid, "blob", enforce_payload_limit=False,
                )
                if entry.object_type == "blob" else None
            )
            converted.append(S88.TreeEntry(
                _stage12688_mode(entry), entry.object_type, entry.oid, size, entry.path,
            ))
        inventories[parent_path] = S88.DirectoryInventory(
            parent_path,
            tree_oid,
            tuple(sorted(converted, key=lambda entry: entry.path.encode("utf-8"))),
        )
    return inventories


def _stage12688_snapshot(
    repo: PinnedRepository,
    repository_key: str,
    revision: str,
    tree_oid: str,
    blobs: list[S88.Blob],
    component_key: str,
) -> Any:
    snapshot = S88.RepoSnapshot(
        local_path=repo.path,
        repo_key=repository_key,
        origin_url="",
        revision=revision,
        tree_oid=tree_oid,
        blobs=blobs,
        component_objects=(),
        lineage_keys=(),
    )
    snapshot.component_key = component_key
    snapshot.directory_inventories = _stage12688_directory_inventories(
        repo, tree_oid, blobs,
    )
    return snapshot


def _construct_comparable_pairs(
    repo: PinnedRepository,
    repository_key: str,
    revision: str,
    tree_oid: str,
    files: Iterable[HistoricalBlobCandidate],
    component_key: str,
    *,
    all_source_spans: bool = False,
) -> tuple[tuple[dict[str, Any], dict[str, Any]], ...]:
    candidates = tuple(files)
    blobs = [
        S88.Blob(candidate.blob_oid, len(candidate.data), candidate.path)
        for candidate in candidates
    ]
    snapshot = _stage12688_snapshot(
        repo, repository_key, revision, tree_oid, blobs, component_key,
    )
    pairs: list[tuple[dict[str, Any], dict[str, Any]]] = []
    for candidate, blob in zip(candidates, blobs):
        kind = S88.classify_path(blob.path)
        if kind is None:
            raise Stage12693Error("historical_classification_lost")
        _consume_work("comparable_examples")
        directory_pair = S88.build_directory_entry_row(
            snapshot, blob, candidate.file_sha256,
        )
        if directory_pair is not None:
            pairs.append(directory_pair)
        spans = (
            _all_stage12688_candidate_spans(candidate.data)
            if all_source_spans
            else _bounded_stage12688_candidate_spans(
                candidate.data, repository_key, blob.path,
            )
        )
        for span in spans:
            _consume_work("comparable_examples")
            pair = S88.build_span_row(
                snapshot, blob, kind, candidate.data, span, candidate.file_sha256,
            )
            if pair is not None:
                pairs.append(pair)
    return tuple(pairs)


def _iter_binary_lines_keepends(data: bytes) -> Iterable[tuple[int, bytes]]:
    cursor = 0
    while cursor < len(data):
        end = cursor
        while end < len(data) and data[end] not in {
            0x0A, 0x0B, 0x0C, 0x0D, 0x1C, 0x1D, 0x1E, 0x85,
        }:
            end += 1
        if end < len(data):
            if data[end] == 0x0D and end + 1 < len(data) and data[end + 1] == 0x0A:
                end += 2
            else:
                end += 1
        yield cursor, data[cursor:end]
        cursor = end


def _eligible_line_spans(data: bytes) -> Iterable[tuple[int, int]]:
    for start, line in _iter_binary_lines_keepends(data):
        end = start + len(line)
        stripped = line.strip()
        if not (
            S88.MIN_TARGET_BYTES <= len(line) <= S88.MAX_TARGET_BYTES
            and stripped
        ):
            continue
        try:
            target = line.decode("utf-8")
        except UnicodeDecodeError:
            continue
        if (
            S88.MASK in target
            or S88.DIRECTORY_ENTRY_MASK in target
            or S88.rejected_target_marker(target)
        ):
            continue
        _consume_work("eligible_spans_considered")
        _consume_repository_work("eligible_spans_considered")
        yield start, end


def _all_stage12688_candidate_spans(data: bytes) -> tuple[tuple[int, int], ...]:
    return tuple(_eligible_line_spans(data))


def _bounded_stage12688_candidate_spans(
    data: bytes, repository_key: str, path: str,
) -> tuple[tuple[int, int], ...]:
    return tuple(heapq.nsmallest(
        S88.MAX_ROWS_PER_FILE,
        _eligible_line_spans(data),
        key=lambda span: (
            S88.stable([repository_key, path, span[0], span[1]]),
            span,
        ),
    ))


def _current_head_source_candidates(
    repo: PinnedRepository,
    repository_key: str,
) -> tuple[HistoricalBlobCandidate, ...]:
    head = read_commit(repo, repo.head_oid)
    candidates: list[HistoricalBlobCandidate] = []
    for entry in list_tree_metadata_recursive(repo, head.tree_oid):
        if entry.object_type != "blob" or entry.mode not in {"100644", "100755"}:
            continue
        kind = classify_required_language(entry.path)
        if kind is None:
            continue
        size = verified_object_size(
            repo, entry.oid, "blob", enforce_payload_limit=False,
        )
        if not S88.MIN_FILE_BYTES <= size <= S88.MAX_FILE_BYTES:
            continue
        data = read_verified_object(repo, entry.oid, "blob")
        if historical_content_rejection_reason(data) is not None:
            continue
        candidates.append(HistoricalBlobCandidate(
            repo.head_oid, repo.head_oid, repo.head_oid, head.tree_oid,
            head.committer_epoch, head.committer_timezone,
            age_bucket(head.committer_epoch) or "current_head",
            entry.path, entry.oid, _sha256(data),
            kind.language_family, kind.file_role, data,
        ))
    return tuple(sorted(candidates, key=lambda item: (
        item.path.encode("utf-8"), item.blob_oid,
    )))


@cumulative_bounded
def build_current_head_example_exclusion(
    repo: PinnedRepository,
    repository_key: str,
) -> CurrentHeadExampleExclusion:
    cache_key = (repo.head_oid, repository_key)
    cached = repo.cache.head_examples.get(cache_key)
    if cached is not None:
        repo.cache.counters["head_example_cache_hits"] += 1
        return cached
    base = build_current_head_exclusion_inventory(repo)
    head = read_commit(repo, repo.head_oid)
    head_candidates = _current_head_source_candidates(repo, repository_key)
    pairs = _construct_comparable_pairs(
        repo, repository_key, repo.head_oid, head.tree_oid,
        head_candidates, "", all_source_spans=True,
    )
    retained: dict[str, set[str]] = {
        "encoder_input_sha256": set(),
        "model_example_sha256": set(),
        "semantic_example_sha256": set(),
        "source_window_sha256": set(),
    }
    for _row, proof in pairs:
        for field, values in retained.items():
            value = proof[field]
            if value not in values:
                _consume_work("retained_head_evidence")
                values.add(value)
    encoder = frozenset(retained["encoder_input_sha256"])
    model = frozenset(retained["model_example_sha256"])
    semantic = frozenset(retained["semantic_example_sha256"])
    windows = frozenset(retained["source_window_sha256"])
    commitment = S88.stable([
        "stage12693_current_head_example_exclusion_v1",
        base.inventory_sha256,
        sorted(encoder), sorted(model), sorted(semantic), sorted(windows),
    ])
    exclusion = CurrentHeadExampleExclusion(
        base, encoder, model, semantic, windows, commitment,
    )
    repo.cache.retain_head_evidence(
        len(encoder) + len(model) + len(semantic) + len(windows)
    )
    repo.cache.head_examples[cache_key] = exclusion
    repo.cache.counters["head_example_builds"] += 1
    return exclusion


@cumulative_bounded
def validate_current_head_example_exclusion(
    repo: PinnedRepository,
    repository_key: str,
    exclusion: CurrentHeadExampleExclusion,
) -> None:
    expected = build_current_head_example_exclusion(repo, repository_key)
    if exclusion != expected:
        raise Stage12693Error("forged_or_stale_head_example_exclusion")


@cumulative_bounded
def construct_revision_material(
    repo: PinnedRepository,
    repository_key: str,
    edge: HistoryEdge,
) -> HistoricalRevisionMaterial:
    edges = enumerate_single_parent_edges(repo)
    exact = next((candidate for candidate in edges if candidate == edge), None)
    if exact is None:
        raise Stage12693Error("unverified_history_edge")
    lineage = {repo.head_oid}
    for candidate in edges:
        lineage.update((candidate.child_oid, candidate.parent_oid))
    entries = list_tree_metadata_recursive(repo, edge.parent_tree_oid)
    material = HistoricalRevisionMaterial(
        repository_key_sha256=repository_key,
        pinned_head_oid=repo.head_oid,
        edge=edge,
        lineage_commit_oids=frozenset(lineage),
        tree_oids=frozenset({
            edge.parent_tree_oid,
            *(entry.oid for entry in entries if entry.object_type == "tree"),
        }),
        blob_oids=frozenset(
            entry.oid for entry in entries if entry.object_type == "blob"
        ),
    )
    _register_verified_material(material)
    return material


def assign_historical_components(
    materials: list[HistoricalRevisionMaterial],
) -> dict[str, tuple[HistoricalRevisionMaterial, ...]]:
    if not materials:
        return {}
    if len(materials) > MAX_REVISION_MATERIALS:
        raise Stage12693Error("historical_revision_material_limit_exceeded")
    union = S88.UnionFind(str(index) for index in range(len(materials)))
    for left_index, left in enumerate(materials):
        for right_index in range(left_index + 1, len(materials)):
            right = materials[right_index]
            if (
                left.pinned_head_oid == right.pinned_head_oid
                or bool(left.lineage_commit_oids.intersection(right.lineage_commit_oids))
            ):
                union.union(str(left_index), str(right_index))
    grouped: dict[str, list[HistoricalRevisionMaterial]] = collections.defaultdict(list)
    for index, material in enumerate(materials):
        grouped[union.find(str(index))].append(material)
    result: dict[str, tuple[HistoricalRevisionMaterial, ...]] = {}
    for members in grouped.values():
        ordered = tuple(sorted(
            members,
            key=lambda item: (
                item.repository_key_sha256, item.edge.parent_oid, item.edge.child_oid,
            ),
        ))
        digest = S88.stable([
            "stage12693_verified_commit_lineage_component_v2",
            sorted({
                value
                for member in ordered
                for value in (
                    member.pinned_head_oid,
                    *member.lineage_commit_oids,
                )
            }),
        ])
        for material in ordered:
            if material.verified_row_source_bindings:
                raise Stage12693Error("cannot_reassign_material_after_row_binding")
            material.component_key = digest
            if id(material) in _VERIFIED_MATERIALS:
                _register_verified_material(material)
        result[digest] = ordered
    return dict(sorted(result.items()))


def immutable_material_binding(material: HistoricalRevisionMaterial) -> str:
    return S88.stable([
        "stage12693_verified_historical_material_v1",
        material.repository_key_sha256,
        material.pinned_head_oid,
        material.edge.child_oid,
        material.edge.child_tree_oid,
        material.edge.parent_oid,
        material.edge.parent_tree_oid,
        material.edge.parent_committer_epoch,
        material.edge.parent_committer_timezone,
        material.edge.age_bucket,
        sorted(material.lineage_commit_oids),
        sorted(material.tree_oids),
        sorted(material.blob_oids),
        material.component_key,
    ])


_VERIFIED_MATERIALS: dict[
    int,
    tuple[HistoricalRevisionMaterial, str, tuple[tuple[str, str], ...]],
] = {}


def _register_verified_material(material: HistoricalRevisionMaterial) -> None:
    bindings = tuple(material.verified_row_source_bindings)
    if len({row_id for row_id, _digest in bindings}) != len(bindings):
        raise Stage12693Error("duplicate_verified_row_source_binding")
    _VERIFIED_MATERIALS[id(material)] = (
        material,
        immutable_material_binding(material),
        bindings,
    )


def _require_verified_material(material: HistoricalRevisionMaterial) -> None:
    registered = _VERIFIED_MATERIALS.get(id(material))
    if (
        registered is None
        or registered[0] is not material
        or registered[1] != immutable_material_binding(material)
        or registered[2] != tuple(material.verified_row_source_bindings)
    ):
        raise Stage12693Error("untrusted_or_forged_historical_material")


_BINDING_PROVENANCE_FIELDS = (
    "source_stage",
    "repository_key_sha256",
    "content_component_sha256",
    "pinned_head_commit_git_oid",
    "sampling_child_commit_git_oid",
    "historical_parent_commit_git_oid",
    "historical_parent_tree_git_oid",
    "historical_parent_commit_object_sha256",
    "source_recorded_committer_epoch",
    "source_recorded_committer_timezone",
    "age_reference_timestamp",
    "historical_age_bucket",
    "repository_relative_path",
    "git_blob_oid",
    "source_file_sha256",
    "source_window_sha256",
    "span_start_byte",
    "span_end_byte",
    "parent_directory",
    "parent_tree_oid",
    "target_object_mode",
    "target_object_type",
    "target_object_oid",
    "immediate_directory_inventory_sha256",
    "target_sha256",
    "file_role",
    "reinsertion_contract",
    "current_head_exclusion_inventory_sha256",
    "current_head_example_exclusion_sha256",
    "exact_reconstruction_verified",
)


def immutable_row_evidence_binding(
    row: dict[str, Any], proof: dict[str, Any]
) -> str:
    provenance = row["source_provenance"]
    return S88.stable([
        "stage12693_immutable_row_evidence_v1",
        proof["material_binding_sha256"],
        proof["selection_key_sha256"],
        row["row_id"],
        row["language_family"],
        row["objective_family"],
        proof["base_comparison_objective_family"],
        proof["encoder_input_sha256"],
        proof["model_example_sha256"],
        proof["semantic_example_sha256"],
        proof["source_window_sha256"],
        proof["source_file_sha256"],
        proof["git_blob_oid"],
        proof["repository_relative_path_sha256"],
        proof["target_sha256"],
        [(field, provenance[field]) for field in _BINDING_PROVENANCE_FIELDS],
    ])


def trusted_row_source_binding(
    row: dict[str, Any], proof: dict[str, Any],
) -> str:
    provenance = row["source_provenance"]
    return S88.stable([
        "stage12693_verified_row_source_material_v1",
        row["row_id"],
        row["language_family"],
        row["objective_family"],
        row["input_text"],
        row["target"]["decoder_text"],
        proof["selection_key_sha256"],
        proof["encoder_input_sha256"],
        proof["model_example_sha256"],
        proof["semantic_example_sha256"],
        proof["base_comparison_objective_family"],
        proof["repository_relative_path_sha256"],
        [(field, provenance[field]) for field in _BINDING_PROVENANCE_FIELDS],
    ])


def historical_planning_identity(
    row: dict[str, Any], proof: dict[str, Any],
) -> str:
    return S88.stable([
        "stage12693_historical_planning_identity_v1",
        row["row_id"],
        proof["immutable_evidence_binding_sha256"],
    ])


def validate_historical_row_proof(
    row: dict[str, Any],
    proof: dict[str, Any],
    material: HistoricalRevisionMaterial | None = None,
) -> None:
    try:
        provenance = row["source_provenance"]
        target = row["target"]["decoder_text"]
        input_text = row["input_text"]
        base_objective = proof["base_comparison_objective_family"]
        expected_objective = HISTORICAL_OBJECTIVES[base_objective]
        kind = classify_required_language(provenance["repository_relative_path"])
        expected_age = age_bucket(provenance["source_recorded_committer_epoch"])
        expected_selection_key = S88.stable([
            "stage12693_target_independent_row_selection_v1",
            provenance["repository_key_sha256"],
            provenance["sampling_child_commit_git_oid"],
            provenance["historical_parent_commit_git_oid"],
            provenance["repository_relative_path"],
            base_objective,
            provenance["span_start_byte"],
            provenance["span_end_byte"],
            provenance["git_blob_oid"],
            provenance["parent_tree_oid"],
        ])
        expected_row_id = "stage12693_" + S88.stable([
            expected_selection_key,
            _sha256(target.encode("utf-8")),
        ])[:24]
        exact_fields = (
            proof["row_id"] == row["row_id"],
            row["row_id"] == expected_row_id,
            proof["selection_key_sha256"] == expected_selection_key,
            proof["row_sha256"] == S88.stable(row),
            proof["encoder_input_sha256"] == _sha256(input_text.encode("utf-8")),
            proof["model_example_sha256"] == S88.stable([input_text, target]),
            proof["semantic_example_sha256"] == S88.stable([
                base_objective,
                S88.normalized_without_whitespace(input_text),
                S88.normalized_without_whitespace(target),
            ]),
            proof["target_sha256"] == _sha256(target.encode("utf-8")),
            provenance["target_sha256"] == proof["target_sha256"],
            row["objective_family"] == expected_objective,
            proof["objective_family"] == expected_objective,
            kind is not None,
            row["language_family"] == kind.language_family if kind else False,
            proof["language_family"] == row["language_family"],
            provenance["file_role"] == kind.file_role if kind else False,
            proof["historical_age_bucket"] == expected_age,
            provenance["historical_age_bucket"] == expected_age,
            proof["repository_key_sha256"] == provenance["repository_key_sha256"],
            proof["content_component_sha256"] == provenance["content_component_sha256"],
            proof["historical_parent_commit_git_oid"]
                == provenance["historical_parent_commit_git_oid"],
            proof["git_blob_oid"] == provenance["git_blob_oid"],
            proof["source_file_sha256"] == provenance["source_file_sha256"],
            proof["source_window_sha256"] == provenance["source_window_sha256"],
            proof["repository_relative_path_sha256"] == _sha256(
                provenance["repository_relative_path"].encode("utf-8")
            ),
            bool(provenance["repository_key_sha256"]),
            bool(provenance["content_component_sha256"]),
            bool(OID_RE.fullmatch(provenance["pinned_head_commit_git_oid"])),
            bool(OID_RE.fullmatch(provenance["sampling_child_commit_git_oid"])),
            bool(OID_RE.fullmatch(provenance["historical_parent_commit_git_oid"])),
            bool(OID_RE.fullmatch(provenance["historical_parent_tree_git_oid"])),
            bool(re.fullmatch(
                r"[0-9a-f]{64}",
                provenance["historical_parent_commit_object_sha256"],
            )),
            provenance["source_stage"] == STAGE,
            provenance["age_reference_timestamp"] == "2026-08-03T00:00:00Z",
            provenance["exact_reconstruction_verified"] is True,
            not any(row["authority"].values()),
            proof["training_admitted"] is False,
            proof["strict_eval_admitted"] is False,
            proof["sealed_eval_admitted"] is False,
        )
    except (KeyError, TypeError, AttributeError, ValueError) as exc:
        raise Stage12693Error("historical_row_proof_schema_mismatch") from exc
    if not all(exact_fields):
        raise Stage12693Error("historical_row_proof_field_mismatch")
    if material is not None:
        _require_verified_material(material)
        trusted_bindings = dict(material.verified_row_source_bindings)
        if len(trusted_bindings) != len(material.verified_row_source_bindings):
            raise Stage12693Error("duplicate_verified_row_source_binding")
        material_fields = (
            proof["material_binding_sha256"] == immutable_material_binding(material),
            provenance["repository_key_sha256"] == material.repository_key_sha256,
            provenance["content_component_sha256"] == material.component_key,
            provenance["pinned_head_commit_git_oid"] == material.pinned_head_oid,
            provenance["sampling_child_commit_git_oid"] == material.edge.child_oid,
            provenance["historical_parent_commit_git_oid"] == material.edge.parent_oid,
            provenance["historical_parent_tree_git_oid"] == material.edge.parent_tree_oid,
            provenance["source_recorded_committer_epoch"]
                == material.edge.parent_committer_epoch,
            provenance["source_recorded_committer_timezone"]
                == material.edge.parent_committer_timezone,
            provenance["historical_age_bucket"] == material.edge.age_bucket,
            provenance["git_blob_oid"] in material.blob_oids,
            (
                not provenance["parent_tree_oid"]
                or provenance["parent_tree_oid"] in material.tree_oids
            ),
            (
                (
                    not provenance["target_object_oid"]
                    and not provenance["target_object_type"]
                )
                or (
                    provenance["target_object_type"] == "blob"
                    and provenance["target_object_oid"] in material.blob_oids
                )
                or (
                    provenance["target_object_type"] == "tree"
                    and provenance["target_object_oid"] in material.tree_oids
                )
            ),
            row["row_id"] in trusted_bindings,
            trusted_bindings.get(row["row_id"]) == trusted_row_source_binding(
                row, proof,
            ),
        )
        if not all(material_fields):
            raise Stage12693Error("historical_row_material_binding_mismatch")
    if (
        proof.get("immutable_evidence_binding_sha256")
        != immutable_row_evidence_binding(row, proof)
    ):
        raise Stage12693Error("historical_row_immutable_evidence_binding_mismatch")


def _historicalize_pair(
    repo: PinnedRepository,
    pair: tuple[dict[str, Any], dict[str, Any]],
    material: HistoricalRevisionMaterial,
    exclusion: CurrentHeadExampleExclusion,
) -> tuple[dict[str, Any], dict[str, Any]]:
    base_row, base_proof = pair
    base_objective = base_row["objective_family"]
    historical_objective = HISTORICAL_OBJECTIVES[base_objective]
    target = base_row["target"]["decoder_text"]
    input_text = base_row["input_text"]
    source = base_row["source_provenance"]
    target_sha256 = _sha256(target.encode("utf-8"))
    selection_key = S88.stable([
        "stage12693_target_independent_row_selection_v1",
        material.repository_key_sha256,
        material.edge.child_oid,
        material.edge.parent_oid,
        source["repository_relative_path"],
        base_objective,
        source["span_start_byte"],
        source["span_end_byte"],
        source["git_blob_oid"],
        source["parent_tree_oid"],
    ])
    row_id = "stage12693_" + S88.stable([
        selection_key, target_sha256,
    ])[:24]
    parent_commit_data = read_verified_object(
        repo, material.edge.parent_oid, "commit"
    )
    provenance = {
        "source_stage": STAGE,
        "repository_key_sha256": material.repository_key_sha256,
        "content_component_sha256": material.component_key,
        "pinned_head_commit_git_oid": material.pinned_head_oid,
        "sampling_child_commit_git_oid": material.edge.child_oid,
        "historical_parent_commit_git_oid": material.edge.parent_oid,
        "historical_parent_tree_git_oid": material.edge.parent_tree_oid,
        "historical_parent_commit_object_sha256": _sha256(parent_commit_data),
        "source_recorded_committer_epoch": material.edge.parent_committer_epoch,
        "source_recorded_committer_timezone": material.edge.parent_committer_timezone,
        "age_reference_timestamp": "2026-08-03T00:00:00Z",
        "historical_age_bucket": material.edge.age_bucket,
        "repository_relative_path": source["repository_relative_path"],
        "git_blob_oid": source["git_blob_oid"],
        "source_file_sha256": source["source_file_sha256"],
        "source_window_sha256": source["source_window_sha256"],
        "span_start_byte": source["span_start_byte"],
        "span_end_byte": source["span_end_byte"],
        "parent_directory": source["parent_directory"],
        "parent_tree_oid": source["parent_tree_oid"],
        "target_object_mode": source["target_object_mode"],
        "target_object_type": source["target_object_type"],
        "target_object_oid": source["target_object_oid"],
        "immediate_directory_inventory_sha256":
            source["immediate_directory_inventory_sha256"],
        "target_sha256": target_sha256,
        "file_role": source["file_role"],
        "reinsertion_contract": source["reinsertion_contract"],
        "current_head_exclusion_inventory_sha256":
            exclusion.base_inventory.inventory_sha256,
        "current_head_example_exclusion_sha256": exclusion.commitment_sha256,
        "exact_reconstruction_verified": True,
    }
    row = {
        "row_id": row_id,
        "split": "",
        "language_family": base_row["language_family"],
        "objective_family": historical_objective,
        "input_text": input_text,
        "target": {"decoder_text": target},
        "loss_mask": {"decoder_ce": True},
        "source_provenance": provenance,
        "authority": dict(AUTHORITY),
    }
    proof = {
        "row_id": row_id,
        "row_sha256": S88.stable(row),
        "selection_key_sha256": selection_key,
        "encoder_input_sha256": base_proof["encoder_input_sha256"],
        "model_example_sha256": base_proof["model_example_sha256"],
        "semantic_example_sha256": base_proof["semantic_example_sha256"],
        "source_window_sha256": base_proof["source_window_sha256"],
        "source_file_sha256": base_proof["source_file_sha256"],
        "git_blob_oid": base_proof["git_blob_oid"],
        "repository_relative_path_sha256":
            base_proof["repository_relative_path_sha256"],
        "repository_key_sha256": material.repository_key_sha256,
        "content_component_sha256": material.component_key,
        "historical_parent_commit_git_oid": material.edge.parent_oid,
        "historical_age_bucket": material.edge.age_bucket,
        "language_family": base_row["language_family"],
        "objective_family": historical_objective,
        "base_comparison_objective_family": base_objective,
        "target_sha256": target_sha256,
        "training_admitted": False,
        "strict_eval_admitted": False,
        "sealed_eval_admitted": False,
        "material_binding_sha256": immutable_material_binding(material),
    }
    proof["immutable_evidence_binding_sha256"] = immutable_row_evidence_binding(
        row, proof,
    )
    validate_historical_row_proof(row, proof)
    return row, proof


@cumulative_bounded
def construct_historical_revision_rows(
    repo: PinnedRepository,
    material: HistoricalRevisionMaterial,
    exclusion: CurrentHeadExampleExclusion,
) -> HistoricalRevisionRows:
    _require_verified_material(material)
    if not material.component_key:
        raise Stage12693Error("historical_component_unassigned")
    if material.pinned_head_oid != repo.head_oid:
        raise Stage12693Error("historical_material_head_mismatch")
    validate_current_head_example_exclusion(
        repo, material.repository_key_sha256, exclusion,
    )
    if material.edge.parent_tree_oid in exclusion.base_inventory.tree_oids:
        return HistoricalRevisionRows(material, (), ())
    candidates = select_historical_blobs_absent_from_current_head(
        repo, material.edge, exclusion.base_inventory,
    )
    tree_oids = _tree_oid_by_directory(repo, material.edge.parent_tree_oid)
    filtered = tuple(
        candidate for candidate in candidates
        if tree_oids.get(str(PurePosixPath(candidate.path).parent))
        not in exclusion.base_inventory.tree_oids
    )
    pairs = _construct_comparable_pairs(
        repo,
        material.repository_key_sha256,
        material.edge.parent_oid,
        material.edge.parent_tree_oid,
        filtered,
        material.component_key,
    )
    rows: list[dict[str, Any]] = []
    proofs: list[dict[str, Any]] = []
    for pair in pairs:
        row, proof = _historicalize_pair(repo, pair, material, exclusion)
        if (
            proof["encoder_input_sha256"] in exclusion.encoder_input_sha256s
            or proof["model_example_sha256"] in exclusion.model_example_sha256s
            or proof["semantic_example_sha256"] in exclusion.semantic_example_sha256s
            or proof["source_window_sha256"] in exclusion.source_window_sha256s
        ):
            continue
        rows.append(row)
        proofs.append(proof)
    material.verified_row_source_bindings = tuple(sorted(
        (row["row_id"], trusted_row_source_binding(row, proof))
        for row, proof in zip(rows, proofs, strict=True)
    ))
    _register_verified_material(material)
    for row, proof in zip(rows, proofs, strict=True):
        validate_historical_row_proof(row, proof, material)
    return HistoricalRevisionRows(material, tuple(rows), tuple(proofs))


def globally_deduplicate_historical_rows(
    revisions: Iterable[HistoricalRevisionRows],
    repository_cap: int = DEFAULT_REPOSITORY_ROW_CAP,
) -> tuple[tuple[dict[str, Any], ...], tuple[dict[str, Any], ...]]:
    if repository_cap <= 0:
        raise Stage12693Error("invalid_repository_row_cap")
    revision_list = tuple(revisions)
    if any(len(revision.rows) != len(revision.proofs) for revision in revision_list):
        raise Stage12693Error("historical_revision_row_proof_count_mismatch")
    for revision in revision_list:
        for row, proof in zip(revision.rows, revision.proofs, strict=True):
            validate_historical_row_proof(row, proof, revision.material)
    candidates = sorted(
        (
            (row, proof)
            for revision in revision_list
            for row, proof in zip(revision.rows, revision.proofs, strict=True)
        ),
        key=lambda pair: (
            pair[1]["selection_key_sha256"],
            pair[1]["repository_key_sha256"],
            pair[0]["row_id"],
        ),
    )
    seen = {name: set() for name in (
        "row_id", "encoder", "model", "semantic", "window",
    )}
    repository_counts: collections.Counter[str] = collections.Counter()
    rows: list[dict[str, Any]] = []
    proofs: list[dict[str, Any]] = []
    for row, proof in candidates:
        repository_key = proof["repository_key_sha256"]
        values = {
            "row_id": row["row_id"],
            "encoder": proof["encoder_input_sha256"],
            "model": proof["model_example_sha256"],
            "semantic": proof["semantic_example_sha256"],
            "window": proof["source_window_sha256"],
        }
        if repository_counts[repository_key] >= repository_cap:
            continue
        if any(value in seen[name] for name, value in values.items()):
            continue
        for name, value in values.items():
            seen[name].add(value)
        repository_counts[repository_key] += 1
        rows.append(copy.deepcopy(row))
        proofs.append(copy.deepcopy(proof))
    return tuple(rows), tuple(proofs)


def historical_component_capacities(
    proofs: Iterable[dict[str, Any]],
) -> tuple[tuple[str, int], ...]:
    capacities: collections.Counter[str] = collections.Counter()
    for proof in proofs:
        component = proof.get("content_component_sha256", "")
        if not component:
            raise Stage12693Error("missing_historical_component_identity")
        capacities[component] += 1
    return tuple(sorted(capacities.items()))


def _validate_retention_gates(
    planned: dict[str, list[tuple[dict[str, Any], dict[str, Any]]]],
    gates: RetentionPlanningGates,
) -> None:
    if (
        gates.min_rows_per_language_per_split < 0
        or gates.min_rows_per_age_bucket_per_split < 0
    ):
        raise Stage12693Error("invalid_retention_gate")
    for split in ("train", "eval", "strict_eval"):
        language_counts = collections.Counter(
            row["language_family"] for row, _proof in planned[split]
        )
        age_counts = collections.Counter(
            proof["historical_age_bucket"] for _row, proof in planned[split]
        )
        if any(
            language_counts[language] < gates.min_rows_per_language_per_split
            for language in gates.required_languages
        ):
            raise Stage12693Error("retention_language_gate_unfilled")
        if any(
            age_counts[bucket] < gates.min_rows_per_age_bucket_per_split
            for bucket in gates.required_age_buckets
        ):
            raise Stage12693Error("retention_age_gate_unfilled")


def plan_historical_component_splits(
    rows: tuple[dict[str, Any], ...],
    proofs: tuple[dict[str, Any], ...],
    requested_rows: int,
    gates: RetentionPlanningGates = RetentionPlanningGates(),
    repository_cap: int = DEFAULT_REPOSITORY_ROW_CAP,
    *,
    trusted_materials: Iterable[
        tuple[str, HistoricalRevisionMaterial]
    ] | None = None,
) -> HistoricalSplitPlan:
    if (
        requested_rows < 10 or requested_rows % 10 != 0
        or len(rows) != len(proofs)
    ):
        raise Stage12693Error("invalid_exact_80_10_10_plan_request")
    if repository_cap <= 0:
        raise Stage12693Error("invalid_repository_row_cap")
    if trusted_materials is None:
        raise Stage12693Error("missing_trusted_historical_material")
    trusted_by_identity: dict[str, HistoricalRevisionMaterial] = {}
    for entry in trusted_materials:
        if not isinstance(entry, tuple) or len(entry) != 2:
            raise Stage12693Error("malformed_trusted_material_entry")
        identity, material = entry
        if identity in trusted_by_identity:
            raise Stage12693Error("duplicate_trusted_material_entry")
        _require_verified_material(material)
        trusted_by_identity[identity] = material
    expected_identities = tuple(
        historical_planning_identity(row, proof)
        for row, proof in zip(rows, proofs, strict=True)
    )
    if len(set(expected_identities)) != len(expected_identities):
        raise Stage12693Error("duplicate_historical_planning_identity")
    expected_identity_set = set(expected_identities)
    if expected_identity_set - trusted_by_identity.keys():
        raise Stage12693Error("missing_trusted_historical_material")
    if trusted_by_identity.keys() - expected_identity_set:
        raise Stage12693Error("unused_trusted_historical_material")

    by_component: dict[str, list[tuple[dict[str, Any], dict[str, Any]]]] = (
        collections.defaultdict(list)
    )
    repository_counts: collections.Counter[str] = collections.Counter()
    seen = {
        name: set()
        for name in ("row", "encoder", "model", "semantic", "window")
    }
    for row, proof in zip(rows, proofs):
        identity = historical_planning_identity(row, proof)
        material = trusted_by_identity[identity]
        validate_historical_row_proof(row, proof, material)
        component = proof["content_component_sha256"]
        repository_key = proof["repository_key_sha256"]
        identities = {
            "row": row["row_id"],
            "encoder": proof["encoder_input_sha256"],
            "model": proof["model_example_sha256"],
            "semantic": proof["semantic_example_sha256"],
            "window": proof["source_window_sha256"],
        }
        if not component or row["source_provenance"]["content_component_sha256"] != component:
            raise Stage12693Error("row_component_identity_mismatch")
        if repository_counts[repository_key] >= repository_cap:
            raise Stage12693Error("historical_repository_cap_exceeded")
        if any(value in seen[name] for name, value in identities.items()):
            raise Stage12693Error("historical_global_dedup_required")
        for name, value in identities.items():
            seen[name].add(value)
        repository_counts[repository_key] += 1
        by_component[component].append((row, proof))
    components = [
        {"digest": digest, "capacity": capacity}
        for digest, capacity in historical_component_capacities(proofs)
    ]
    caps = {
        "train": requested_rows * 8 // 10,
        "eval": requested_rows // 10,
        "strict_eval": requested_rows // 10,
    }
    allocation = S88.exact_component_capacity_assignment(components, caps)
    if allocation["status"] == "search_budget_exhausted":
        raise Stage12693Error("historical_component_allocation_search_budget_exhausted")
    if allocation["status"] != "feasible" or allocation["assignment"] is None:
        raise Stage12693Error("historical_component_capacity_infeasible")
    assignment = allocation["assignment"]
    planned: dict[str, list[tuple[dict[str, Any], dict[str, Any]]]] = {
        split: [] for split in caps
    }
    for component, split in sorted(assignment.items()):
        ordered = sorted(
            by_component[component],
            key=lambda pair: pair[1]["selection_key_sha256"],
        )
        remaining = caps[split] - len(planned[split])
        if remaining > 0:
            planned[split].extend(ordered[:remaining])
    if any(len(planned[split]) != caps[split] for split in caps):
        raise Stage12693Error("historical_component_split_caps_unfilled")
    _validate_retention_gates(planned, gates)
    finalized: dict[str, list[tuple[dict[str, Any], dict[str, Any]]]] = {
        split: [] for split in caps
    }
    for split, pairs in planned.items():
        for source_row, source_proof in pairs:
            row = copy.deepcopy(source_row)
            proof = copy.deepcopy(source_proof)
            row["split"] = split
            proof["split"] = split
            proof["row_sha256"] = S88.stable(row)
            finalized[split].append((row, proof))
    strict_commitment = S88.stable([
        "stage12693_private_strict_plan_v1",
        sorted(S88.stable([row, proof]) for row, proof in finalized["strict_eval"]),
    ])
    language_counts = {
        split: dict(sorted(collections.Counter(
            row["language_family"] for row, _proof in finalized[split]
        ).items()))
        for split in ("train", "eval")
    }
    age_counts = {
        split: dict(sorted(collections.Counter(
            proof["historical_age_bucket"] for _row, proof in finalized[split]
        ).items()))
        for split in ("train", "eval")
    }
    return HistoricalSplitPlan(
        train_rows=tuple(row for row, _proof in finalized["train"]),
        eval_rows=tuple(row for row, _proof in finalized["eval"]),
        train_proofs=tuple(proof for _row, proof in finalized["train"]),
        eval_proofs=tuple(proof for _row, proof in finalized["eval"]),
        strict_planned_count=len(finalized["strict_eval"]),
        strict_commitment_sha256=strict_commitment,
        component_splits=tuple(sorted(
            (component, split) for component, split in assignment.items()
            if split != "strict_eval"
        )),
        language_counts_by_split=language_counts,
        age_bucket_counts_by_split=age_counts,
        authority=dict(AUTHORITY),
    )


def _read_canonical_regular_file(path: Path, max_bytes: int) -> bytes:
    if not path.is_absolute() or max_bytes <= 0:
        raise Stage12693Error("invalid_bounded_input_path")
    try:
        resolved = path.resolve(strict=True)
    except OSError as exc:
        raise Stage12693Error("bounded_input_unavailable") from exc
    if resolved != path:
        raise Stage12693Error("bounded_input_path_not_canonical")
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    except OSError as exc:
        raise Stage12693Error("bounded_input_open_failed") from exc
    try:
        metadata = os.fstat(fd)
        if not stat.S_ISREG(metadata.st_mode):
            raise Stage12693Error("bounded_input_not_regular")
        if metadata.st_size > max_bytes:
            raise Stage12693Error("bounded_input_size_limit_exceeded")
        chunks: list[bytes] = []
        retained = 0
        while True:
            chunk = os.read(fd, min(1024 * 1024, max_bytes + 1 - retained))
            if not chunk:
                break
            retained += len(chunk)
            if retained > max_bytes:
                raise Stage12693Error("bounded_input_size_limit_exceeded")
            chunks.append(chunk)
        return b"".join(chunks)
    finally:
        os.close(fd)


def resolve_default_source_catalog(summary_path: Path) -> Path:
    try:
        summary = json.loads(
            _read_canonical_regular_file(
                summary_path, MAX_SOURCE_CATALOG_BYTES,
            ).decode("utf-8")
        )
        relative = summary["artifact_contract"][
            "train_eval_source_catalog.jsonl"
        ]["relative_path"]
    except (
        KeyError, TypeError, ValueError, UnicodeDecodeError,
    ) as exc:
        raise Stage12693Error("invalid_stage12688_summary") from exc
    relative_path = PurePosixPath(relative)
    if (
        relative_path.is_absolute()
        or not relative_path.parts
        or any(part in {"", ".", ".."} for part in relative_path.parts)
    ):
        raise Stage12693Error("invalid_stage12688_catalog_relative_path")
    catalog = summary_path.parent.joinpath(*relative_path.parts)
    try:
        resolved = catalog.resolve(strict=True)
    except OSError as exc:
        raise Stage12693Error("stage12688_catalog_unavailable") from exc
    if resolved != catalog:
        raise Stage12693Error("stage12688_catalog_path_not_canonical")
    return catalog


def load_accepted_source_catalog(
    catalog_path: Path,
    *,
    expected_path: Path = AUTHORITATIVE_STAGE12688_CATALOG,
    expected_sha256: str = AUTHORITATIVE_STAGE12688_CATALOG_SHA256,
) -> tuple[dict[tuple[str, str], str], dict[str, int]]:
    if (
        catalog_path != expected_path
        or not re.fullmatch(r"[0-9a-f]{64}", expected_sha256)
    ):
        raise Stage12693Error("unauthorized_source_catalog_path")
    raw = _read_canonical_regular_file(
        catalog_path, MAX_SOURCE_CATALOG_BYTES,
    )
    if _sha256(raw) != expected_sha256:
        raise Stage12693Error("authoritative_source_catalog_sha256_mismatch")
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise Stage12693Error("source_catalog_not_utf8") from exc
    lines = text.splitlines()
    if len(lines) > MAX_SOURCE_CATALOG_RECORDS:
        raise Stage12693Error("source_catalog_record_limit_exceeded")
    accepted: dict[tuple[str, str], str] = {}
    duplicate_records = 0
    for line in lines:
        if not line:
            raise Stage12693Error("blank_source_catalog_record")
        try:
            record = json.loads(line)
            head_oid = record["head_commit_git_oid"]
            tree_oid = record["git_tree_oid"]
            repository_key = record["repository_key_sha256"]
            split = record["split"]
        except (KeyError, TypeError, ValueError) as exc:
            raise Stage12693Error("malformed_source_catalog_record") from exc
        if (
            not isinstance(record, dict)
            or not isinstance(head_oid, str)
            or not isinstance(tree_oid, str)
            or not isinstance(repository_key, str)
            or not OID_RE.fullmatch(head_oid)
            or not OID_RE.fullmatch(tree_oid)
            or not re.fullmatch(r"[0-9a-f]{64}", repository_key)
            or split not in {"train", "eval"}
        ):
            raise Stage12693Error("invalid_source_catalog_identity")
        identity = (head_oid, tree_oid)
        prior = accepted.get(identity)
        if prior is not None:
            duplicate_records += 1
            if prior != repository_key:
                raise Stage12693Error("conflicting_source_catalog_identity")
            continue
        accepted[identity] = repository_key
    if not accepted:
        raise Stage12693Error("empty_source_catalog")
    return accepted, {
        "records_loaded": len(lines),
        "unique_repository_identities": len(accepted),
        "duplicate_records_quarantined": duplicate_records,
    }


def _scan_error_reason(exc: BaseException) -> str:
    reason = str(exc).split(":", 1)[0]
    return reason if re.fullmatch(r"[a-z0-9_]+", reason) else "controlled_scan_error"


def _component_capacity_summary(
    proofs: tuple[dict[str, Any], ...],
) -> dict[str, Any]:
    capacities = tuple(
        capacity for _component, capacity
        in historical_component_capacities(proofs)
    )
    histogram = collections.Counter(capacities)
    return {
        "component_count": len(capacities),
        "total_candidate_capacity": sum(capacities),
        "minimum_component_capacity": min(capacities, default=0),
        "maximum_component_capacity": max(capacities, default=0),
        "capacity_histogram": {
            str(capacity): count
            for capacity, count in sorted(histogram.items())
        },
    }


def _split_feasibility_summary(
    proofs: tuple[dict[str, Any], ...],
    requested_rows: int,
) -> dict[str, Any]:
    requested_caps = {
        "train": requested_rows * 8 // 10,
        "eval": requested_rows // 10,
        "strict_eval": requested_rows // 10,
    }
    components = [
        {"digest": component, "capacity": capacity}
        for component, capacity in historical_component_capacities(proofs)
    ]
    allocation = S88.exact_component_capacity_assignment(
        components, requested_caps,
    )
    return {
        "requested_rows": requested_rows,
        "requested_split_capacities": requested_caps,
        "status": allocation["status"],
        "feasible": allocation["status"] == "feasible",
        "explored_states": allocation["explored_states"],
        "memoized_dead_states": allocation["memoized_dead_states"],
        "work_items": allocation["work_items"],
        "state_budget": allocation["state_budget"],
        "memory_budget": allocation["memory_budget"],
        "work_budget": allocation["work_budget"],
    }


def _qualified_split_feasibility(
    feasibility: dict[str, Any], complete: bool,
) -> dict[str, Any]:
    result = dict(feasibility)
    observed_status = result.pop("status")
    observed_feasible = result.pop("feasible")
    result.update({
        "observed_capacity_status": (
            f"complete_observed_{observed_status}"
            if complete else f"partial_observed_{observed_status}"
        ),
        "observed_sample_feasible": observed_feasible,
        "complete_corpus_status": (
            observed_status if complete else "unknown_incomplete_scan"
        ),
    })
    return result


def _aggregate_repository_cache_counters(
    work_budget: Stage12693WorkBudget,
) -> dict[str, int]:
    aggregate: collections.Counter[str] = collections.Counter()
    caches = {id(cache): cache for cache in work_budget.repository_caches.values()}
    for cache in caches.values():
        aggregate.update(cache.counters)
    aggregate["repository_cache_count"] = len(caches)
    aggregate["repository_cached_raw_objects"] = sum(
        len(cache.raw_objects) for cache in caches.values()
    )
    aggregate["repository_cached_raw_bytes"] = sum(
        cache.raw_object_bytes for cache in caches.values()
    )
    return dict(sorted(aggregate.items()))


def _enumerate_bounded_repository_names(
    source_root_fd: int,
    max_local_directories: int,
) -> tuple[tuple[str, ...], bool, int]:
    names: list[str] = []
    entries_seen = 0
    exceeded = False
    with os.scandir(source_root_fd) as entries:
        for entry in entries:
            entries_seen += 1
            if entries_seen > max_local_directories:
                exceeded = True
                break
            if (
                _canonical_repository_entry_name(entry.name)
                and entry.is_dir(follow_symlinks=False)
            ):
                names.append(entry.name)
    if exceeded:
        return (), True, entries_seen
    return tuple(sorted(names, key=lambda value: value.encode("utf-8"))), False, entries_seen


STREAMING_AGE_BUCKETS = (
    "historical_2_to_5_years",
    "historical_5_to_10_years",
    "historical_10_plus_years",
)


def _iter_bounded_history_edges(
    repo: PinnedRepository,
    *,
    max_commits: int,
    max_secondary_parents: int,
    report: collections.Counter[str],
) -> Iterable[HistoryEdge]:
    if max_commits < 2 or max_secondary_parents < 0:
        raise Stage12693Error("invalid_streaming_history_bounds")
    commits: dict[str, CommitObject] = {}
    expanded: set[str] = set()
    frontier: collections.deque[str] = collections.deque([repo.head_oid])
    secondary_queued = 0

    def load(oid: str) -> CommitObject | None:
        cached = commits.get(oid)
        if cached is not None:
            return cached
        if len(commits) >= max_commits:
            report["commit_bound_reached"] = 1
            return None
        commit = read_commit(repo, oid)
        read_verified_object(repo, commit.tree_oid, "tree")
        commits[oid] = commit
        report["bounded_commits_verified"] += 1
        if len(commit.parent_oids) > 1:
            report["bounded_merges_verified"] += 1
        return commit

    while frontier:
        child_oid = frontier.popleft()
        if child_oid in expanded:
            continue
        child = load(child_oid)
        if child is None:
            break
        expanded.add(child_oid)
        if not child.parent_oids:
            continue
        first_parent_oid = child.parent_oids[0]
        first_parent = load(first_parent_oid)
        if first_parent is None:
            break
        if first_parent_oid not in expanded:
            frontier.appendleft(first_parent_oid)
        for secondary_oid in sorted(child.parent_oids[1:]):
            if secondary_queued >= max_secondary_parents:
                report["secondary_parent_bound_reached"] = 1
                break
            if secondary_oid not in expanded and secondary_oid not in frontier:
                frontier.append(secondary_oid)
                secondary_queued += 1
                report["secondary_parents_queued"] += 1
        if len(child.parent_oids) != 1:
            continue
        report["single_parent_edges_verified"] += 1
        yield HistoryEdge(
            child.oid,
            child.tree_oid,
            first_parent.oid,
            first_parent.tree_oid,
            first_parent.committer_epoch,
            first_parent.committer_timezone,
            age_bucket(first_parent.committer_epoch),
        )


def _edge_has_supported_changed_blob(
    repo: PinnedRepository,
    edge: HistoryEdge,
) -> bool:
    return bool(changed_supported_parent_tree_entries(
        repo, edge.child_tree_oid, edge.parent_tree_oid,
    ))


@cumulative_bounded
def construct_streaming_revision_material(
    repo: PinnedRepository,
    repository_key: str,
    edge: HistoryEdge,
) -> HistoricalRevisionMaterial:
    child = read_commit(repo, edge.child_oid)
    parent = read_commit(repo, edge.parent_oid)
    if (
        len(child.parent_oids) != 1
        or child.parent_oids[0] != parent.oid
        or child.tree_oid != edge.child_tree_oid
        or parent.tree_oid != edge.parent_tree_oid
        or parent.committer_epoch != edge.parent_committer_epoch
        or parent.committer_timezone != edge.parent_committer_timezone
        or age_bucket(parent.committer_epoch) != edge.age_bucket
    ):
        raise Stage12693Error("unverified_streaming_history_edge")
    entries = list_tree_metadata_recursive(repo, parent.tree_oid)
    material = HistoricalRevisionMaterial(
        repository_key_sha256=repository_key,
        pinned_head_oid=repo.head_oid,
        edge=edge,
        lineage_commit_oids=frozenset({
            repo.head_oid, child.oid, parent.oid,
        }),
        tree_oids=frozenset({
            parent.tree_oid,
            *(entry.oid for entry in entries if entry.object_type == "tree"),
        }),
        blob_oids=frozenset(
            entry.oid for entry in entries if entry.object_type == "blob"
        ),
        component_key=S88.stable([
            "stage12693_bounded_repository_component_v1", repo.head_oid,
        ]),
    )
    _register_verified_material(material)
    return material


def _release_repository_cache(
    work_budget: Stage12693WorkBudget,
    cache: RepositoryEvidenceCache,
    aggregate: collections.Counter[str],
    released: set[tuple[Any, ...]],
) -> None:
    identity = cache.identity
    if identity in released:
        return
    aggregate.update(cache.counters)
    aggregate["repository_cache_count"] += 1
    aggregate["repository_cached_raw_objects"] += len(cache.raw_objects)
    aggregate["repository_cached_raw_bytes"] += cache.raw_object_bytes
    for object_type, byte_count in cache.raw_object_bytes_by_type.items():
        aggregate[f"repository_cached_{object_type}_bytes"] += byte_count
        aggregate[f"repository_cache_peak_{object_type}_bytes"] = max(
            aggregate[f"repository_cache_peak_{object_type}_bytes"],
            byte_count,
        )
    aggregate["repository_cache_peak_raw_bytes"] = max(
        aggregate["repository_cache_peak_raw_bytes"], cache.raw_object_bytes,
    )
    for key, candidate in tuple(work_budget.repository_caches.items()):
        if candidate is cache:
            del work_budget.repository_caches[key]
    cache.object_metadata.clear()
    cache.raw_objects.clear()
    cache.parsed_commits.clear()
    cache.parsed_trees.clear()
    cache.validated_tree_oids.clear()
    cache.head_inventories.clear()
    cache.head_examples.clear()
    cache.raw_object_bytes = 0
    cache.raw_object_bytes_by_type.clear()
    cache.head_evidence_items = 0
    released.add(identity)


def run_capacity_scan(
    source_root: Path,
    catalog_path: Path,
    *,
    max_local_directories: int,
    max_repositories: int,
    max_materials: int,
    max_materials_per_repository: int,
    requested_rows: int,
    work_limits: Stage12693WorkLimits,
    max_commits_per_repository: int = DEFAULT_SCAN_MAX_COMMITS_PER_REPOSITORY,
    max_secondary_parents_per_repository: int = (
        DEFAULT_SCAN_MAX_SECONDARY_PARENTS_PER_REPOSITORY
    ),
    max_rows_per_repository: int = DEFAULT_SCAN_MAX_ROWS_PER_REPOSITORY,
    repository_work_limits: RepositoryWorkLimits = RepositoryWorkLimits(),
    expected_catalog_path: Path = AUTHORITATIVE_STAGE12688_CATALOG,
    expected_catalog_sha256: str = AUTHORITATIVE_STAGE12688_CATALOG_SHA256,
) -> dict[str, Any]:
    if (
        min(
            max_local_directories,
            max_repositories,
            max_materials,
            max_materials_per_repository,
            max_commits_per_repository,
            max_rows_per_repository,
        ) <= 0
        or max_commits_per_repository < 2
        or max_secondary_parents_per_repository < 0
        or requested_rows < 10
        or requested_rows % 10
    ):
        raise Stage12693Error("invalid_capacity_scan_bounds")
    if not source_root.is_absolute():
        raise Stage12693Error("source_root_must_be_absolute")
    try:
        resolved_root = source_root.resolve(strict=True)
    except OSError as exc:
        raise Stage12693Error("source_root_unavailable") from exc
    if resolved_root != source_root:
        raise Stage12693Error("source_root_not_canonical")

    catalog, catalog_report = load_accepted_source_catalog(
        catalog_path,
        expected_path=expected_catalog_path,
        expected_sha256=expected_catalog_sha256,
    )
    errors: collections.Counter[str] = collections.Counter()
    quarantines: collections.Counter[str] = collections.Counter()
    quarantines["duplicate_source_catalog_records"] = (
        catalog_report["duplicate_records_quarantined"]
    )
    source_root_fd = _open_directory(source_root)
    catalog_matches: set[tuple[str, str]] = set()
    local_catalog_unmatched = 0
    local_catalog_duplicates = 0
    repositories_attempted: set[str] = set()
    lifecycle: dict[str, str] = {}
    material_states: collections.Counter[str] = collections.Counter()
    traversal_states: collections.Counter[str] = collections.Counter()
    materials_constructed = 0
    eligible_materials_seen = 0
    revisions: list[HistoricalRevisionRows] = []
    raw_candidates_after_head_exclusion = 0
    materials_with_candidates = 0
    resource_termination = ""
    repository_bound_reached = False
    material_bound_reached = False
    global_stop = False
    repository_work_consumed: collections.Counter[str] = collections.Counter()

    try:
        names, directory_bound_reached, local_entries_seen = (
            _enumerate_bounded_repository_names(
                source_root_fd, max_local_directories,
            )
        )
        if directory_bound_reached:
            quarantines["source_directory_bound_exceeded"] += 1
        with cumulative_work_scope(work_limits) as work_budget:
            queued: list[
                tuple[str, str, str, RepositoryEvidenceCache]
            ] = []
            cache_counters: collections.Counter[str] = collections.Counter()
            released_caches: set[tuple[Any, ...]] = set()

            if not directory_bound_reached:
                for name in names:
                    if len(queued) >= max_repositories:
                        repository_bound_reached = True
                        break
                    repositories_attempted.add(name)
                    cache: RepositoryEvidenceCache | None = None
                    matched = False
                    try:
                        with pin_repository_at(
                            source_root_fd, name, source_root,
                        ) as pinned:
                            cache = pinned.cache
                            head = read_commit(pinned, pinned.head_oid)
                            catalog_identity = (pinned.head_oid, head.tree_oid)
                            repository_key = catalog.get(catalog_identity)
                            if repository_key is None:
                                local_catalog_unmatched += 1
                                continue
                            if catalog_identity in catalog_matches:
                                local_catalog_duplicates += 1
                                quarantines[
                                    "duplicate_local_catalog_identity"
                                ] += 1
                                continue
                            matched = True
                            catalog_matches.add(catalog_identity)
                            queued.append((
                                name, repository_key, pinned.head_oid, cache,
                            ))
                    except (Stage12693Error, S88.Stage12688Error, OSError) as exc:
                        reason = _scan_error_reason(exc)
                        errors[reason] += 1
                        if reason.startswith("cumulative_"):
                            resource_termination = reason
                            global_stop = True
                    finally:
                        if cache is not None and not matched:
                            _release_repository_cache(
                                work_budget,
                                cache,
                                cache_counters,
                                released_caches,
                            )
                    if global_stop:
                        break

            for queue_index, (
                name,
                repository_key,
                expected_head,
                cache,
            ) in enumerate(queued):
                if global_stop:
                    lifecycle[name] = "not_started_due_global_limit"
                    continue
                processing_started = False
                repository_material_count = 0
                repository_row_count = 0
                repository_report: collections.Counter[str] = (
                    collections.Counter()
                )
                repository_budget: RepositoryWorkBudget | None = None
                try:
                    if materials_constructed >= max_materials:
                        material_bound_reached = True
                        global_stop = True
                        lifecycle[name] = "not_started_due_global_limit"
                        continue
                    with repository_work_scope(
                        repository_work_limits
                    ) as repository_budget, pin_repository_at(
                        source_root_fd, name, source_root,
                    ) as pinned:
                        processing_started = True
                        if (
                            pinned.cache is not cache
                            or pinned.head_oid != expected_head
                        ):
                            raise Stage12693Error(
                                "repository_changed_after_streaming_pin"
                            )
                        preferred_offset = (
                            int(repository_key[:8], 16)
                            % len(STREAMING_AGE_BUCKETS)
                        )
                        preferred_buckets = (
                            STREAMING_AGE_BUCKETS[preferred_offset:]
                            + STREAMING_AGE_BUCKETS[:preferred_offset]
                        )
                        exclusion: CurrentHeadExampleExclusion | None = None
                        edges = _iter_bounded_history_edges(
                            pinned,
                            max_commits=max_commits_per_repository,
                            max_secondary_parents=(
                                max_secondary_parents_per_repository
                            ),
                            report=repository_report,
                        )
                        for edge in edges:
                            if edge.age_bucket is None:
                                continue
                            eligible_materials_seen += 1
                            repository_report["age_eligible_edges"] += 1
                            desired_bucket = preferred_buckets[
                                repository_material_count
                                % len(preferred_buckets)
                            ]
                            if (
                                edge.age_bucket != desired_bucket
                                and repository_report[
                                    "age_stratification_skips"
                                ] < 1
                            ):
                                repository_report[
                                    "age_stratification_skips"
                                ] += 1
                                continue
                            if not _edge_has_supported_changed_blob(
                                pinned, edge,
                            ):
                                repository_report[
                                    "unsupported_or_unchanged_edges"
                                ] += 1
                                continue
                            if materials_constructed >= max_materials:
                                material_bound_reached = True
                                global_stop = True
                                break
                            if exclusion is None:
                                exclusion = (
                                    build_current_head_example_exclusion(
                                        pinned, repository_key,
                                    )
                                )
                            material_states[
                                "construction_attempted"
                            ] += 1
                            material = construct_streaming_revision_material(
                                pinned, repository_key, edge,
                            )
                            materials_constructed += 1
                            repository_material_count += 1
                            material_states[
                                "construction_completed"
                            ] += 1
                            material_states["candidate_attempted"] += 1
                            revision = construct_historical_revision_rows(
                                pinned, material, exclusion,
                            )
                            material_states["candidate_completed"] += 1
                            raw_candidates_after_head_exclusion += len(
                                revision.rows
                            )
                            materials_with_candidates += bool(revision.rows)
                            remaining = (
                                max_rows_per_repository
                                - repository_row_count
                            )
                            if remaining > 0 and revision.rows:
                                retained = HistoricalRevisionRows(
                                    revision.material,
                                    revision.rows[:remaining],
                                    revision.proofs[:remaining],
                                )
                                revisions.append(retained)
                                repository_row_count += len(retained.rows)
                            if (
                                repository_material_count
                                >= max_materials_per_repository
                                or repository_row_count
                                >= max_rows_per_repository
                            ):
                                repository_report[
                                    "repository_capacity_stop"
                                ] = 1
                                break
                        lifecycle[name] = (
                            "partial" if global_stop else "completed"
                        )
                except (Stage12693Error, S88.Stage12688Error, OSError) as exc:
                    reason = _scan_error_reason(exc)
                    errors[reason] += 1
                    if reason.startswith("cumulative_"):
                        resource_termination = reason
                        global_stop = True
                    lifecycle[name] = (
                        "partial" if processing_started else "error"
                    )
                    material_states[
                        "candidate_or_construction_errors"
                    ] += 1
                finally:
                    if repository_budget is not None:
                        for field in (
                            "blob_payload_bytes", "raw_object_bytes",
                            "tree_visits", "commits",
                            "eligible_spans_considered",
                        ):
                            repository_work_consumed[field] += getattr(
                                repository_budget, field,
                            )
                    traversal_states.update(repository_report)
                    _release_repository_cache(
                        work_budget,
                        cache,
                        cache_counters,
                        released_caches,
                    )

                if global_stop:
                    for (
                        queued_name,
                        _queued_key,
                        _queued_head,
                        queued_cache,
                    ) in queued[queue_index + 1:]:
                        lifecycle[queued_name] = (
                            "not_started_due_global_limit"
                        )
                        _release_repository_cache(
                            work_budget,
                            queued_cache,
                            cache_counters,
                            released_caches,
                        )
                    break

            for _name, _key, _head, cache in queued:
                _release_repository_cache(
                    work_budget,
                    cache,
                    cache_counters,
                    released_caches,
                )

            if len(lifecycle) != len(queued) or any(
                lifecycle[name] not in {
                    "completed",
                    "partial",
                    "error",
                    "not_started_due_global_limit",
                }
                for name, _key, _head, _cache in queued
            ):
                raise Stage12693Error(
                    "repository_lifecycle_reconciliation_failed"
                )

            if revisions:
                deduplicated_rows, deduplicated_proofs = (
                    globally_deduplicate_historical_rows(
                        revisions,
                        repository_cap=max_rows_per_repository,
                    )
                )
            else:
                deduplicated_rows, deduplicated_proofs = (), ()

            language_capacity = dict(sorted(collections.Counter(
                row["language_family"] for row in deduplicated_rows
            ).items()))
            age_capacity = dict(sorted(collections.Counter(
                proof["historical_age_bucket"]
                for proof in deduplicated_proofs
            ).items()))
            component_summary = _component_capacity_summary(
                deduplicated_proofs,
            )
            feasibility = _split_feasibility_summary(
                deduplicated_proofs, requested_rows,
            )
            work_report = {
                field: getattr(work_budget, field)
                for field in (
                    "total_blob_bytes_read",
                    "object_reads",
                    "tree_work",
                    "eligible_spans_considered",
                    "comparable_examples",
                    "retained_head_evidence",
                )
            }
            cache_counter_report = dict(sorted(cache_counters.items()))
    finally:
        os.close(source_root_fd)

    unverified_catalog_identities = len(catalog) - len(catalog_matches)
    catalog_selection_complete = not any((
        directory_bound_reached,
        repository_bound_reached,
        resource_termination,
    ))
    if unverified_catalog_identities and catalog_selection_complete:
        quarantines[
            "catalog_identities_not_verified_after_complete_local_scan"
        ] += unverified_catalog_identities
    lifecycle_counts = collections.Counter(lifecycle.values())
    lifecycle_total = sum(lifecycle_counts.values())
    if lifecycle_total != len(catalog_matches):
        raise Stage12693Error(
            "repository_lifecycle_reconciliation_failed"
        )
    complete = not any((
        directory_bound_reached,
        repository_bound_reached,
        material_bound_reached,
        resource_termination,
        unverified_catalog_identities,
        errors,
        traversal_states["commit_bound_reached"],
        traversal_states["secondary_parent_bound_reached"],
    ))
    feasibility = _qualified_split_feasibility(feasibility, complete)
    return {
        "schema_version": "stage12693_read_only_capacity_scan_v2",
        "decision": "READ_ONLY_CAPACITY_SCAN_NO_PUBLICATION",
        "scan_mode": "capacity_only_streaming_bounded_history",
        "bounds": {
            "max_local_directories": max_local_directories,
            "max_repositories": max_repositories,
            "max_materials": max_materials,
            "max_materials_per_repository":
                max_materials_per_repository,
            "max_commits_per_repository": max_commits_per_repository,
            "max_secondary_parents_per_repository":
                max_secondary_parents_per_repository,
            "max_rows_per_repository": max_rows_per_repository,
            "repository_work_limits": {
                field: getattr(repository_work_limits, field)
                for field in (
                    "blob_payload_bytes", "raw_object_bytes",
                    "tree_visits", "commits",
                    "eligible_spans_considered",
                )
            },
            "requested_rows": requested_rows,
            "repository_row_cap": max_rows_per_repository,
            "static_safety_limits": {
                "max_commit_object_bytes": MAX_COMMIT_OBJECT_BYTES,
                "max_tree_object_bytes": MAX_TREE_OBJECT_BYTES,
                "max_blob_object_bytes": MAX_BLOB_OBJECT_BYTES,
                "max_tree_depth": MAX_TREE_DEPTH,
                "max_tree_entries_per_tree": MAX_TREE_ENTRIES_PER_TREE,
                "max_tree_entries_total": MAX_TREE_ENTRIES_TOTAL,
                "max_tree_objects": MAX_TREE_OBJECTS,
                "max_history_commits_per_repository": MAX_HISTORY_COMMITS,
                "max_source_catalog_bytes": MAX_SOURCE_CATALOG_BYTES,
                "max_source_catalog_records": MAX_SOURCE_CATALOG_RECORDS,
                "max_repository_cache_objects":
                    MAX_REPOSITORY_CACHE_OBJECTS,
                "max_repository_cache_bytes":
                    MAX_REPOSITORY_CACHE_BYTES,
                "max_repository_blob_payload_cache_bytes":
                    MAX_REPOSITORY_BLOB_PAYLOAD_CACHE_BYTES,
                "max_repository_tree_object_cache_bytes":
                    MAX_REPOSITORY_TREE_OBJECT_CACHE_BYTES,
                "max_repository_commit_object_cache_bytes":
                    MAX_REPOSITORY_COMMIT_OBJECT_CACHE_BYTES,
                "max_repository_cache_head_evidence":
                    MAX_REPOSITORY_CACHE_HEAD_EVIDENCE,
            },
            "work_limits": {
                field: getattr(work_limits, field)
                for field in (
                    "total_blob_bytes_read",
                    "object_reads",
                    "tree_work",
                    "eligible_spans_considered",
                    "comparable_examples",
                    "retained_head_evidence",
                )
            },
        },
        "completeness": {
            "complete": complete,
            "history_claim": "bounded_traversal_not_complete_history",
            "capacity_interpretation": (
                "exact_for_complete_bounded_scan"
                if complete else "bounded_lower_bound"
            ),
            "source_directory_bound_reached": directory_bound_reached,
            "repository_bound_reached": repository_bound_reached,
            "material_bound_reached": material_bound_reached,
            "history_commit_bound_reached_repositories":
                traversal_states["commit_bound_reached"],
            "secondary_parent_bound_reached_repositories":
                traversal_states["secondary_parent_bound_reached"],
            "resource_termination": resource_termination or None,
            "catalog_identity_selection_complete":
                catalog_selection_complete,
            "catalog_identities_not_verified":
                unverified_catalog_identities,
            "catalog_identity_availability_claim": (
                "all_catalog_identities_verified"
                if not unverified_catalog_identities
                else "not_verified_after_complete_local_scan"
                if catalog_selection_complete
                else "unknown_outside_bounded_scan"
            ),
        },
        "catalog": {
            "records_loaded": catalog_report["records_loaded"],
            "accepted_repository_identities": len(catalog),
            "matched_repository_identities": len(catalog_matches),
            "unverified_repository_identities":
                unverified_catalog_identities,
        },
        "counts": {
            "local_directory_entries_seen": local_entries_seen,
            "repositories_scanned": len(catalog_matches),
            "snapshots_scanned": len(catalog_matches),
            "repositories_attempted": len(repositories_attempted),
            "repositories_catalog_matched": len(catalog_matches),
            "repositories_catalog_unmatched": local_catalog_unmatched,
            "repositories_catalog_duplicate_identity":
                local_catalog_duplicates,
            "repositories_completed": lifecycle_counts["completed"],
            "repositories_partial": lifecycle_counts["partial"],
            "repositories_error": lifecycle_counts["error"],
            "repositories_not_started_due_global_limit":
                lifecycle_counts["not_started_due_global_limit"],
            "repository_lifecycle_total": lifecycle_total,
            "commits_verified": cache_counter_report.get(
                "parsed_commits", 0,
            ),
            "merge_commits_verified": cache_counter_report.get(
                "merge_commits", 0,
            ),
            "eligible_historical_materials_seen":
                eligible_materials_seen,
            "materials_constructed": materials_constructed,
            "materials_with_candidates": materials_with_candidates,
            "raw_candidates_after_head_exclusion":
                raw_candidates_after_head_exclusion,
            "deduplicated_candidates": len(deduplicated_rows),
            "retained_candidate_rows": len(deduplicated_rows),
            "retained_candidate_spans": sum(
                proof["base_comparison_objective_family"]
                == "multilingual_exact_source_span_infilling"
                for proof in deduplicated_proofs
            ),
            "material_states": dict(sorted(material_states.items())),
            "traversal_states": dict(sorted(traversal_states.items())),
        },
        "language_capacity": language_capacity,
        "age_bucket_capacity": age_capacity,
        "component_capacity": component_summary,
        "requested_split_feasibility": feasibility,
        "work_consumed": work_report,
        "repository_work_consumed": dict(sorted(
            repository_work_consumed.items()
        )),
        "verification_counters": cache_counter_report,
        "errors": {
            "total": sum(errors.values()),
            "by_reason": dict(sorted(errors.items())),
        },
        "quarantines": {
            "total": sum(quarantines.values()),
            "by_reason": {
                reason: count
                for reason, count in sorted(quarantines.items())
                if count
            },
        },
        "privacy": {
            "rows_emitted": 0,
            "row_or_repository_identifiers_emitted": False,
            "strict_plaintext_emitted": False,
            "strict_component_identities_emitted": False,
            "aggregate_counts_only": True,
        },
        "authority": dict(AUTHORITY),
    }


def _build_bound_summary_payload(
    summary: dict[str, Any],
    catalog_sha256: str,
    config_sha256: str,
) -> tuple[bytes, str]:
    builder = Path(__file__).resolve()
    builder_sha256 = _sha256(_read_canonical_regular_file(
        builder, 8 * 1024 * 1024,
    ))
    body = json.dumps(
        summary, sort_keys=True, separators=(",", ":"),
    ).encode("utf-8")
    body_sha256 = _sha256(body)
    binding_sha256 = _sha256("\0".join((
        "stage12693_capacity_summary_binding_v1",
        builder_sha256,
        catalog_sha256,
        config_sha256,
        body_sha256,
    )).encode("ascii"))
    bound = dict(summary)
    bound["summary_artifact_binding"] = {
        "builder_sha256": builder_sha256,
        "catalog_sha256": catalog_sha256,
        "config_sha256": config_sha256,
        "summary_body_sha256": body_sha256,
        "binding_sha256": binding_sha256,
        "aggregate_only": True,
        "authority": dict(AUTHORITY),
    }
    payload = (
        json.dumps(bound, sort_keys=True, separators=(",", ":")) + "\n"
    ).encode("utf-8")
    return payload, binding_sha256


def _write_persisted_summary(
    output_root: Path, payload: bytes, binding_sha256: str,
) -> Path:
    if not output_root.is_absolute():
        raise Stage12693Error("summary_output_root_must_be_absolute")
    try:
        resolved = output_root.resolve(strict=True)
    except OSError as exc:
        raise Stage12693Error("summary_output_root_unavailable") from exc
    if resolved != output_root or resolved != STAGE12693_SUMMARY_OUTPUT_ROOT:
        raise Stage12693Error("summary_output_root_not_authorized")
    filename = f"stage12693_capacity_summary_{binding_sha256[:24]}.json"
    try:
        parent_fd = os.open(
            output_root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
        )
    except OSError as exc:
        raise Stage12693Error("summary_output_root_open_failed") from exc
    try:
        try:
            fd = os.open(
                filename,
                os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                0o600,
                dir_fd=parent_fd,
            )
        except OSError as exc:
            raise Stage12693Error("summary_output_collision_or_create_failed") from exc
        try:
            offset = 0
            while offset < len(payload):
                offset += os.write(fd, payload[offset:])
            os.fsync(fd)
        finally:
            os.close(fd)
        os.fsync(parent_fd)
    finally:
        os.close(parent_fd)
    return output_root / filename


def parse_capacity_scan_args(
    argv: list[str] | None = None,
) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--capacity-scan", action="store_true")
    parser.add_argument("--source-root", type=Path, default=DEFAULT_SCAN_SOURCE_ROOT)
    parser.add_argument("--source-catalog", type=Path)
    parser.add_argument(
        "--stage12688-summary",
        type=Path,
        default=DEFAULT_STAGE12688_SUMMARY,
    )
    parser.add_argument("--summary-output", type=Path)
    parser.add_argument(
        "--max-repository-blob-payload-bytes", type=int,
        default=DEFAULT_REPOSITORY_BLOB_PAYLOAD_BYTES,
    )
    parser.add_argument(
        "--max-repository-raw-object-bytes", type=int,
        default=DEFAULT_REPOSITORY_RAW_OBJECT_BYTES,
    )
    parser.add_argument(
        "--max-repository-tree-visits", type=int,
        default=DEFAULT_REPOSITORY_TREE_VISITS,
    )
    parser.add_argument(
        "--max-repository-eligible-spans", type=int,
        default=DEFAULT_REPOSITORY_ELIGIBLE_SPANS,
    )
    parser.add_argument(
        "--max-local-directories",
        type=int,
        default=DEFAULT_SCAN_MAX_LOCAL_DIRECTORIES,
    )
    parser.add_argument(
        "--max-repositories",
        type=int,
        default=DEFAULT_SCAN_MAX_REPOSITORIES,
    )
    parser.add_argument(
        "--max-materials",
        type=int,
        default=DEFAULT_SCAN_MAX_MATERIALS,
    )
    parser.add_argument(
        "--max-materials-per-repository",
        type=int,
        default=DEFAULT_SCAN_MAX_MATERIALS_PER_REPOSITORY,
    )
    parser.add_argument(
        "--max-commits-per-repository",
        type=int,
        default=DEFAULT_SCAN_MAX_COMMITS_PER_REPOSITORY,
    )
    parser.add_argument(
        "--max-secondary-parents-per-repository",
        type=int,
        default=DEFAULT_SCAN_MAX_SECONDARY_PARENTS_PER_REPOSITORY,
    )
    parser.add_argument(
        "--max-rows-per-repository",
        type=int,
        default=DEFAULT_SCAN_MAX_ROWS_PER_REPOSITORY,
    )
    parser.add_argument(
        "--requested-rows",
        type=int,
        default=DEFAULT_SCAN_REQUESTED_ROWS,
    )
    parser.add_argument(
        "--max-total-blob-bytes",
        type=int,
        default=MAX_TOTAL_BLOB_BYTES_READ,
    )
    parser.add_argument(
        "--max-object-reads",
        type=int,
        default=MAX_CUMULATIVE_OBJECT_READS,
    )
    parser.add_argument(
        "--max-tree-work",
        type=int,
        default=MAX_CUMULATIVE_TREE_WORK,
    )
    parser.add_argument(
        "--max-eligible-spans-considered",
        type=int,
        default=MAX_ELIGIBLE_SPANS_CONSIDERED,
    )
    parser.add_argument(
        "--max-comparable-examples",
        type=int,
        default=MAX_COMPARABLE_EXAMPLES,
    )
    parser.add_argument(
        "--max-retained-head-evidence",
        type=int,
        default=MAX_RETAINED_HEAD_EVIDENCE,
    )
    args = parser.parse_args(argv)
    if not args.capacity_scan:
        parser.error("explicit --capacity-scan is required")
    return args


def capacity_scan_main(argv: list[str] | None = None) -> int:
    args = parse_capacity_scan_args(argv)
    catalog_path = args.source_catalog
    if catalog_path is None:
        catalog_path = resolve_default_source_catalog(
            args.stage12688_summary,
        )
    summary = run_capacity_scan(
        args.source_root,
        catalog_path,
        max_local_directories=args.max_local_directories,
        max_repositories=args.max_repositories,
        max_materials=args.max_materials,
        max_materials_per_repository=args.max_materials_per_repository,
        max_commits_per_repository=args.max_commits_per_repository,
        max_secondary_parents_per_repository=(
            args.max_secondary_parents_per_repository
        ),
        max_rows_per_repository=args.max_rows_per_repository,
        repository_work_limits=RepositoryWorkLimits(
            blob_payload_bytes=args.max_repository_blob_payload_bytes,
            raw_object_bytes=args.max_repository_raw_object_bytes,
            tree_visits=args.max_repository_tree_visits,
            commits=args.max_commits_per_repository,
            eligible_spans_considered=args.max_repository_eligible_spans,
        ),
        requested_rows=args.requested_rows,
        work_limits=Stage12693WorkLimits(
            total_blob_bytes_read=args.max_total_blob_bytes,
            object_reads=args.max_object_reads,
            tree_work=args.max_tree_work,
            eligible_spans_considered=args.max_eligible_spans_considered,
            comparable_examples=args.max_comparable_examples,
            retained_head_evidence=args.max_retained_head_evidence,
        ),
    )
    config_sha256 = S88.stable({
        key: str(value) if isinstance(value, Path) else value
        for key, value in vars(args).items()
        if key not in {"summary_output", "source_catalog", "stage12688_summary"}
    })
    catalog_sha256 = _sha256(_read_canonical_regular_file(
        catalog_path, MAX_SOURCE_CATALOG_BYTES,
    ))
    payload, binding_sha256 = _build_bound_summary_payload(
        summary, catalog_sha256, config_sha256,
    )
    if args.summary_output is None:
        sys.stdout.buffer.write(payload)
        sys.stdout.buffer.flush()
    else:
        _write_persisted_summary(
            args.summary_output, payload, binding_sha256,
        )
    return 0


def assert_bounded_core_only() -> None:
    if any(AUTHORITY.values()):
        raise Stage12693Error("authority_must_remain_false")


if __name__ == "__main__":
    assert_bounded_core_only()
    raise SystemExit(capacity_scan_main())
