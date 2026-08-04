#!/usr/bin/env python3
"""Nonpublishing authenticated Git/declaration evidence package core.

The module derives all labels from descriptor-pinned raw Git objects and reruns
the exact Stage12692 parser adapters.  It only returns immutable in-memory
inventories; it has no publication or training-authority path.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import selectors
import secrets
import signal
import stat
import subprocess
import sys
import threading
import time
import types
from collections import Counter
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from typing import Any, Iterable, Mapping, Sequence


MAX_BATCH_BLOB_OBJECTS = 500_000
MAX_BATCH_REQUEST_BYTES = 64 * 1024 * 1024
MAX_BATCH_RESPONSE_BYTES = 64 * 1024 * 1024


DEPENDENCY_SHA256 = {
    "build_stage12687_source_backed_python_foundational_corpus":
        "6c1e7ce23346eff0628307469267648f174a7c15a102aecf55eb56581215e062",
    "build_stage12688_source_backed_multilingual_knowledge_corpus":
        "66bb3fd3c47305f3598f3eb91c9398839614d2ec68b3c3bc36f2fa8e238f490e",
    "build_stage12690_source_backed_symbol_api_test_links":
        "64f0214712bccc739c1ea3c53b2b8d815cd963a8633a5326c19ab523bb5e0549",
    "stage12692_for_stage12696":
        "cf8ce98ad96bdac5cfdfcd65c564f3f49b6a03fa8b6c0e6d1a27a74ec057ba10",
    "stage12693_for_stage12696":
        "47d878b684888ccabbc672d0de7aaed04e56ea56be29eac01b0809408edae2fd",
}


def _load(name: str, filename: str):
    path = Path(__file__).with_name(filename)
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != DEPENDENCY_SHA256[name]:
        raise RuntimeError(f"{name}_digest_mismatch")
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"{name}_import_unavailable")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    try:
        code = compile(raw, os.fspath(path), "exec", dont_inherit=True)
        exec(code, module.__dict__)
    except BaseException:
        sys.modules.pop(name, None)
        raise
    return module


_S87 = _load(
    "build_stage12687_source_backed_python_foundational_corpus",
    "build_stage12687_source_backed_python_foundational_corpus.py",
)
_S88 = _load(
    "build_stage12688_source_backed_multilingual_knowledge_corpus",
    "build_stage12688_source_backed_multilingual_knowledge_corpus.py",
)
_S90 = _load(
    "build_stage12690_source_backed_symbol_api_test_links",
    "build_stage12690_source_backed_symbol_api_test_links.py",
)
S92 = _load("stage12692_for_stage12696", "build_stage12692_source_backed_declarative_test_build_conventions.py")
S93 = _load("stage12693_for_stage12696", "build_stage12693_source_backed_historical_old_language_retention.py")

STAGE = "stage12696_authenticated_git_declaration_evidence_packages"
AUTHORITY = {
    "implementation_ready": False,
    "level_3_materialized": False,
    "model_execution_authorized": False,
    "publication_allowed": False,
    "sealed_eval_admitted": False,
    "strict_eval_admitted": False,
    "training_admitted": False,
    "training_allowed": False,
    "training_run_allowed": False,
}
ACCEPTED_STAGE12688_GENERATION = "23cac72b1c420605413d0f77"
ACCEPTED_STAGE12692_GENERATION = "0251bea687f8f0fa4baff39661d3cf2e0f7c9e5e33521fb3587089c202f812be"
ACCEPTED_ARTIFACT_SHA256S = {
    "stage12688_catalog": "efdc8a4c3051e1621242fad34d82e0b2d5586c2373d438bcca2e12c5a51b98bb",
    "stage12692_rows": "477d5dc664726de10d5e2ce1c22f2f5a6cefd42f0ede01eb632ecf1760266894",
    "stage12692_catalog": "8d80bc4735865b0c6007691ab9a185484fc273f17a41e1dcb1f23907aafb0187",
    "stage12692_ledger": "6d5cb0972ae240f02fd77f01a85e6ebfee73995b7bf5bc6f5a14d7bd56c64459",
}
ACCEPTED_ARTIFACT_RELATIVE_PATHS = {
    "stage12688_catalog": f"runs/local/artifacts/stage12688_source_backed_multilingual_knowledge_corpus/private/{ACCEPTED_STAGE12688_GENERATION}/train_eval_source_catalog.jsonl",
    "stage12692_rows": f"runs/local/artifacts/stage12692_source_backed_declarative_test_build_conventions/private/{ACCEPTED_STAGE12692_GENERATION}/train_eval_rows.jsonl",
    "stage12692_catalog": f"runs/local/artifacts/stage12692_source_backed_declarative_test_build_conventions/private/{ACCEPTED_STAGE12692_GENERATION}/train_eval_source_catalog.jsonl",
    "stage12692_ledger": f"runs/local/artifacts/stage12692_source_backed_declarative_test_build_conventions/private/{ACCEPTED_STAGE12692_GENERATION}/train_eval_proofs.jsonl",
}
SUPPORTED_ADAPTERS = {
    "stdlib_json_plus_byte_spans",
    "stdlib_configparser_strict",
    "stdlib_tomllib_pyproject",
    "stdlib_tomllib_cargo",
    "raw_makefile_literal_rules",
}


class Stage12696Error(RuntimeError):
    pass


_MEMBERSHIP_SEAL = object()
_ISSUED_GENERATION_TOKENS: dict[object, tuple[Any, Any]] = {}


def _canonical(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _stable(value: Any) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


@dataclass(frozen=True)
class PackageLimits:
    jsonl_bytes: int = 512 * 1024 * 1024
    jsonl_lines: int = 100_000
    repositories: int = 600
    commits: int = 250_000
    trees: int = 500_000
    # Inventory-wide bound; measured accepted inventory is 2,027,908 entries.
    tree_entries: int = 2_100_000
    object_reads: int = 4_000_000
    blob_bytes: int = 2 * 1024 * 1024 * 1024
    declaration_rows: int = 10_000
    object_read_seconds: float = 60.0
    repository_seconds: float = 30 * 60.0
    inventory_seconds: float = 6 * 60 * 60.0

    def __post_init__(self) -> None:
        if any(
            isinstance(value, bool) or not isinstance(value, (int, float))
            or value <= 0 or not value < float("inf")
            for value in vars(self).values()
        ):
            raise Stage12696Error("invalid_package_limit")


@dataclass
class WorkBudget:
    limits: PackageLimits
    commits: int = 0
    trees: int = 0
    tree_entries: int = 0
    object_reads: int = 0
    blob_bytes: int = 0
    declaration_rows: int = 0
    inventory_deadline: float = field(init=False)
    repository_deadline: float | None = field(init=False, default=None)

    _RESOURCE_FIELDS = frozenset({
        "commits", "trees", "tree_entries", "object_reads",
        "blob_bytes", "declaration_rows",
    })

    def __post_init__(self) -> None:
        self.inventory_deadline = time.monotonic() + self.limits.inventory_seconds

    def charge(self, field: str, amount: int = 1) -> None:
        if amount < 0 or field not in self._RESOURCE_FIELDS:
            raise Stage12696Error("invalid_work_charge")
        value = getattr(self, field) + amount
        if value > getattr(self.limits, field):
            raise Stage12696Error(f"resource_limit_exceeded:{field}")
        setattr(self, field, value)

    def begin_repository(self) -> None:
        now = time.monotonic()
        if now >= self.inventory_deadline:
            raise Stage12696Error("inventory_deadline_exceeded")
        self.repository_deadline = min(
            self.inventory_deadline, now + self.limits.repository_seconds,
        )

    def end_repository(self) -> None:
        self.repository_deadline = None

    def operation_deadline(self) -> float:
        now = time.monotonic()
        if now >= self.inventory_deadline:
            raise Stage12696Error("inventory_deadline_exceeded")
        if self.repository_deadline is None:
            raise Stage12696Error("repository_deadline_not_started")
        if now >= self.repository_deadline:
            raise Stage12696Error("repository_deadline_exceeded")
        deadline = min(
            now + self.limits.object_read_seconds,
            self.repository_deadline,
            self.inventory_deadline,
        )
        if deadline <= now:
            raise Stage12696Error("batch_object_reader_timeout")
        return deadline


@dataclass(frozen=True)
class AuthenticatedJsonl:
    records: tuple[dict[str, Any], ...]
    file_sha256: str
    line_sha256s: tuple[str, ...]
    membership_commitment_sha256: str
    root_path: Path
    relative_path: str
    device: int
    inode: int
    _seal: object = field(repr=False, compare=False)
    _accepted_role: str | None = field(repr=False, compare=False)
    _generation_token: object | None = field(repr=False, compare=False)


@dataclass
class _PinnedGenerationRoot:
    path: Path
    fd: int
    guard_fd: int
    device: int
    inode: int
    offset_cookie: int
    closed: bool = False
    _challenge_floor: int = 2
    _lock: Any = field(default_factory=threading.RLock, repr=False)

    def revalidate(self) -> None:
        with self._lock:
            if self.closed or self.fd < 0 or self.guard_fd < 0:
                raise Stage12696Error("accepted_generation_root_closed")
            try:
                pinned = os.fstat(self.fd)
                guard = os.fstat(self.guard_fd)
                saved_fd = os.lseek(self.fd, 0, os.SEEK_CUR)
                saved_guard = os.lseek(self.guard_fd, 0, os.SEEK_CUR)
            except OSError as exc:
                raise Stage12696Error("accepted_generation_root_fd_invalid_or_reused") from exc
            if (
                not stat.S_ISDIR(pinned.st_mode)
                or (pinned.st_dev, pinned.st_ino) != (self.device, self.inode)
                or (guard.st_dev, guard.st_ino) != (self.device, self.inode)
                or saved_fd != saved_guard
            ):
                raise Stage12696Error("accepted_generation_root_fd_invalid_or_reused")

            monotonic_floor = time.monotonic_ns() & ((1 << 40) - 1)
            first = max(
                self._challenge_floor + secrets.randbelow(1 << 20) + 2,
                monotonic_floor + 2,
            )
            second = first + secrets.randbelow(1 << 20) + 2
            self._challenge_floor = second
            challenge_failed = False
            restore_failed = False
            try:
                os.lseek(self.fd, first, os.SEEK_SET)
                challenge_failed |= os.lseek(self.guard_fd, 0, os.SEEK_CUR) != first
                os.lseek(self.guard_fd, second, os.SEEK_SET)
                challenge_failed |= os.lseek(self.fd, 0, os.SEEK_CUR) != second
            except OSError:
                challenge_failed = True
            finally:
                try:
                    os.lseek(self.fd, saved_fd, os.SEEK_SET)
                    os.lseek(self.guard_fd, saved_guard, os.SEEK_SET)
                    restore_failed = (
                        os.lseek(self.fd, 0, os.SEEK_CUR) != saved_fd
                        or os.lseek(self.guard_fd, 0, os.SEEK_CUR) != saved_guard
                    )
                except OSError:
                    restore_failed = True
            if challenge_failed or restore_failed:
                raise Stage12696Error("accepted_generation_root_fd_invalid_or_reused")

            pathname_fd = _open_absolute_directory(self.path)
            try:
                pathname = os.fstat(pathname_fd)
            finally:
                os.close(pathname_fd)
            if (pathname.st_dev, pathname.st_ino) != (self.device, self.inode):
                raise Stage12696Error("accepted_generation_root_path_replaced")

    def close(self) -> None:
        with self._lock:
            if self.closed:
                return
            self.closed = True
            descriptors = (self.fd, self.guard_fd)
            self.fd = self.guard_fd = -1
            for descriptor in descriptors:
                if descriptor >= 0:
                    try:
                        os.close(descriptor)
                    except OSError:
                        pass


@dataclass(frozen=True)
class GitHeadEvidence:
    repository_key_sha256: str
    revision: str
    commit_oids: tuple[str, ...]
    root_commit_oids: tuple[str, ...]
    root_tree_oid: str
    commit_objects_inspected: int
    tree_count: int
    blob_count: int
    submodule_count: int
    total_object_count: int
    component_objects: tuple[tuple[str, str, int | None], ...]
    tree_entry_identities: tuple[tuple[str, str, str, str, str], ...]
    component_tree_entry_identities: tuple[tuple[str, str, str, str, str], ...]
    gitlink_identities: tuple[tuple[str, str, str, str, str], ...]
    object_inventory_sha256: str
    catalog_line_sha256: str
    evidence_commitment_sha256: str


@dataclass(frozen=True)
class DeclarationEvidence:
    row_id: str
    repository_key_sha256: str
    revision: str
    source_path: str
    source_blob_oid: str
    source_file_sha256: str
    source_size: int
    source_bytes: bytes = field(repr=False)
    parser_adapter: str
    reproduced_row_sha256: str
    row_membership_sha256: str
    proof_membership_sha256: str
    evidence_commitment_sha256: str


@dataclass(frozen=True)
class PackageInventory:
    git_heads: tuple[GitHeadEvidence, ...]
    declarations: tuple[DeclarationEvidence, ...]
    source_membership_commitments: tuple[str, ...]
    package_manifest_sha256: str
    capacity: dict[str, int]
    authority: dict[str, bool]


def _canonical_relative_path(path: str) -> tuple[str, ...]:
    if (
        not isinstance(path, str) or not path or path.startswith("/")
        or path.endswith("/") or "//" in path or "\\" in path or "\x00" in path
    ):
        raise Stage12696Error("noncanonical_relative_path")
    parts = tuple(path.split("/"))
    if any(part in {"", ".", ".."} for part in parts):
        raise Stage12696Error("noncanonical_relative_path")
    return parts


def _open_absolute_directory(path: Path) -> int:
    if (
        not path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts[1:])
        or path != Path(os.path.abspath(path))
    ):
        raise Stage12696Error("root_must_be_absolute")
    parts = path.parts[1:]
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
    try:
        fd = os.open("/", flags)
        for part in parts:
            next_fd = os.open(part, flags, dir_fd=fd)
            os.close(fd)
            fd = next_fd
        return fd
    except OSError as exc:
        if "fd" in locals():
            os.close(fd)
        raise Stage12696Error("descriptor_root_pin_failed") from exc



def _pin_root_handle(path: Path) -> _PinnedGenerationRoot:
    fd = _open_absolute_directory(path)
    guard_fd = os.dup(fd)
    info = os.fstat(fd)
    try:
        offset_cookie = os.lseek(fd, 1, os.SEEK_SET)
        if os.lseek(guard_fd, 0, os.SEEK_CUR) != offset_cookie:
            raise Stage12696Error("pinned_root_guard_not_shared")
        return _PinnedGenerationRoot(
            path, fd, guard_fd, info.st_dev, info.st_ino, offset_cookie,
        )
    except Exception:
        os.close(guard_fd)
        os.close(fd)
        raise




@contextmanager
def _pinned_root_handle(path: Path):
    handle = _pin_root_handle(path)
    try:
        yield handle
    finally:
        handle.close()


def _open_at_root_fd(root_fd: int, relative_path: str, *, directory: bool) -> int:
    parts = _canonical_relative_path(relative_path)
    try:
        fd = os.dup(root_fd)
        root_info = os.fstat(fd)
        if not stat.S_ISDIR(root_info.st_mode):
            raise Stage12696Error("descriptor_root_fd_not_directory")
        for part in parts[:-1]:
            next_fd = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
            os.close(fd)
            fd = next_fd
        flags = os.O_RDONLY | os.O_NOFOLLOW
        if directory:
            flags |= os.O_DIRECTORY
        result = os.open(parts[-1], flags, dir_fd=fd)
    except OSError as exc:
        raise Stage12696Error("descriptor_relative_open_failed") from exc
    finally:
        if "fd" in locals() and fd >= 0:
            os.close(fd)
    info = os.fstat(result)
    expected = stat.S_ISDIR(info.st_mode) if directory else stat.S_ISREG(info.st_mode)
    if not expected or (not directory and info.st_nlink != 1):
        os.close(result)
        raise Stage12696Error(
            "descriptor_leaf_hard_link_rejected" if not directory and info.st_nlink != 1
            else "descriptor_target_type_mismatch"
        )
    return result


def _open_at_root(root: Path, relative_path: str, *, directory: bool) -> int:
    root_fd = _open_absolute_directory(root)
    try:
        return _open_at_root_fd(root_fd, relative_path, directory=directory)
    finally:
        os.close(root_fd)


def _kill_process_group(process: subprocess.Popen[bytes]) -> None:
    try:
        os.killpg(process.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired as exc:
        raise Stage12696Error("git_process_group_cleanup_failed") from exc


def _git_no_lazy_fetch(
    repo: Any, *args: str, timeout: int = 60, max_stdout_bytes: int = 256,
) -> bytes:
    allowed = (
        args == ("rev-parse", "--verify", "HEAD^{commit}")
        or (
            len(args) == 3 and args[0] == "cat-file"
            and args[1] in {"-t", "-s", "blob", "commit", "tree"}
            and bool(S93.OID_RE.fullmatch(args[2]))
        )
    )
    if (
        repo.repo_fd < 0 or repo.git_fd < 0 or not allowed
        or not 0 < max_stdout_bytes <= S93.MAX_GIT_STDOUT_BYTES
    ):
        raise Stage12696Error("disallowed_or_closed_git_command")
    environment = {
        "GIT_CONFIG_GLOBAL": "/dev/null",
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_NO_LAZY_FETCH": "1",
        "GIT_OPTIONAL_LOCKS": "0",
        "HOME": "/nonexistent",
        "LC_ALL": "C",
        "PATH": os.defpath,
    }
    command = [
        "git", "--no-replace-objects",
        f"--git-dir=/proc/self/fd/{repo.git_fd}",
        f"--work-tree=/proc/self/fd/{repo.repo_fd}",
        *args,
    ]
    process: subprocess.Popen[bytes] | None = None
    try:
        process = subprocess.Popen(
            command,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            env=environment,
            pass_fds=(repo.repo_fd, repo.git_fd),
            start_new_session=True,
        )
        output, _stderr = process.communicate(timeout=timeout)
    except (OSError, subprocess.TimeoutExpired) as exc:
        if process is not None:
            _kill_process_group(process)
        raise Stage12696Error("read_only_git_failed") from exc
    if process.returncode != 0 or len(output) > max_stdout_bytes:
        _kill_process_group(process)
        raise Stage12696Error("read_only_git_failed")
    return output


class _BatchObjectReader:
    """One descriptor-pinned, bounded git cat-file process per repository."""

    def __init__(self, repo: Any, budget: WorkBudget) -> None:
        self.repo = repo
        self.budget = budget
        self.process: subprocess.Popen[bytes] | None = None
        self.buffer = bytearray()
        self.request_bytes = 0
        self.response_bytes = 0
        self.object_count = 0

    def __enter__(self) -> "_BatchObjectReader":
        command = [
            "git", "--no-replace-objects",
            f"--git-dir=/proc/self/fd/{self.repo.git_fd}",
            f"--work-tree=/proc/self/fd/{self.repo.repo_fd}",
            "cat-file", "--batch",
        ]
        environment = {
            "GIT_CONFIG_GLOBAL": "/dev/null", "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_NO_LAZY_FETCH": "1", "GIT_OPTIONAL_LOCKS": "0",
            "HOME": "/nonexistent", "LC_ALL": "C", "PATH": os.defpath,
        }
        try:
            self.process = subprocess.Popen(
                command, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL, env=environment,
                pass_fds=(self.repo.repo_fd, self.repo.git_fd),
                start_new_session=True,
            )
            assert self.process.stdin is not None and self.process.stdout is not None
            os.set_blocking(self.process.stdin.fileno(), False)
            os.set_blocking(self.process.stdout.fileno(), False)
        except (OSError, AssertionError) as exc:
            if self.process is not None:
                _kill_process_group(self.process)
            raise Stage12696Error("batch_object_reader_start_failed") from exc
        return self

    def _wait(self, fileobj: Any, event: int, deadline: float) -> None:
        selector = selectors.DefaultSelector()
        try:
            selector.register(fileobj, event)
            remaining = deadline - time.monotonic()
            if remaining <= 0 or not selector.select(remaining):
                raise Stage12696Error("batch_object_reader_timeout")
        finally:
            selector.close()

    def _write(self, payload: bytes, deadline: float) -> None:
        if self.request_bytes + len(payload) > MAX_BATCH_REQUEST_BYTES:
            raise Stage12696Error("batch_object_request_bytes_exceeded")
        assert self.process is not None and self.process.stdin is not None
        offset = 0
        while offset < len(payload):
            self._wait(self.process.stdin, selectors.EVENT_WRITE, deadline)
            try:
                written = os.write(self.process.stdin.fileno(), payload[offset:])
            except (BrokenPipeError, OSError) as exc:
                raise Stage12696Error("batch_object_reader_write_failed") from exc
            if written <= 0:
                raise Stage12696Error("batch_object_reader_write_failed")
            offset += written
        self.request_bytes += len(payload)

    def _fill(self, deadline: float) -> None:
        assert self.process is not None and self.process.stdout is not None
        self._wait(self.process.stdout, selectors.EVENT_READ, deadline)
        try:
            chunk = os.read(self.process.stdout.fileno(), 65536)
        except OSError as exc:
            raise Stage12696Error("batch_object_reader_read_failed") from exc
        if not chunk:
            raise Stage12696Error("batch_object_reader_unexpected_eof")
        self.buffer.extend(chunk)
        self.response_bytes += len(chunk)
        if self.response_bytes > MAX_BATCH_RESPONSE_BYTES:
            raise Stage12696Error("batch_object_response_bytes_exceeded")

    def _line(self, deadline: float) -> bytes:
        while b"\n" not in self.buffer:
            if len(self.buffer) > 128:
                raise Stage12696Error("batch_object_header_too_large")
            self._fill(deadline)
        line, _, remainder = self.buffer.partition(b"\n")
        self.buffer = bytearray(remainder)
        if len(line) > 128:
            raise Stage12696Error("batch_object_header_too_large")
        return bytes(line)

    def _exact(self, size: int, deadline: float) -> bytes:
        while len(self.buffer) < size:
            self._fill(deadline)
        result = bytes(self.buffer[:size])
        del self.buffer[:size]
        return result

    def read(self, oid: str, kind: str) -> bytes:
        if (
            self.process is None or self.process.poll() is not None
            or kind not in {"blob", "commit", "tree"}
            or not S93.OID_RE.fullmatch(oid)
            or self.object_count >= MAX_BATCH_BLOB_OBJECTS
        ):
            raise Stage12696Error("invalid_or_closed_batch_object_request")
        request = (oid + "\n").encode("ascii")
        deadline = self.budget.operation_deadline()
        self._write(request, deadline)
        try:
            header = self._line(deadline).decode("ascii", errors="strict").split(" ")
        except UnicodeDecodeError as exc:
            raise Stage12696Error("batch_object_header_invalid") from exc
        if (
            len(header) != 3 or header[0] != oid or header[1] != kind
            or not header[2].isdigit()
        ):
            raise Stage12696Error("batch_object_identity_mismatch")
        size = int(header[2])
        if size > MAX_BATCH_RESPONSE_BYTES:
            raise Stage12696Error("batch_object_size_exceeded")
        framed = self._exact(size + 1, deadline)
        if not framed.endswith(b"\n"):
            raise Stage12696Error("batch_object_framing_invalid")
        data = framed[:-1]
        if not S93.verify_object_oid(oid, kind, data):
            raise Stage12696Error("batch_object_digest_mismatch")
        self.object_count += 1
        return data

    def __exit__(self, exc_type: Any, exc: Any, traceback: Any) -> None:
        process = self.process
        self.process = None
        if process is None:
            return
        try:
            if process.stdin is not None and not process.stdin.closed:
                process.stdin.close()
            returncode = process.wait(timeout=5)
            if returncode != 0 and exc_type is None:
                raise Stage12696Error("batch_object_reader_exit_failed")
        except (OSError, subprocess.TimeoutExpired):
            _kill_process_group(process)
            if exc_type is None:
                raise Stage12696Error("batch_object_reader_exit_failed")
        finally:
            if process.stdout is not None and not process.stdout.closed:
                process.stdout.close()


def _revalidate_repository_path(
    root_fd: int, relative_path: str, pinned: Any,
) -> None:
    pathname_fd = _open_at_root_fd(root_fd, relative_path, directory=True)
    try:
        pathname = os.fstat(pathname_fd)
        descriptor = os.fstat(pinned.repo_fd)
    except OSError as exc:
        raise Stage12696Error("repository_path_revalidation_failed") from exc
    finally:
        os.close(pathname_fd)
    if (
        not stat.S_ISDIR(descriptor.st_mode)
        or (pathname.st_dev, pathname.st_ino)
        != (descriptor.st_dev, descriptor.st_ino)
    ):
        raise Stage12696Error("repository_path_replaced")


@contextmanager
def pin_repository_at_fd(root: Path, root_fd: int, relative_path: str):
    repo_fd = _open_at_root_fd(root_fd, relative_path, directory=True)
    try:
        try:
            git_fd = os.open(".git", os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=repo_fd)
        except OSError as exc:
            raise Stage12696Error("git_directory_pin_failed") from exc
        cache = S93._repository_cache_for_descriptors(repo_fd, git_fd, root_fd)
        pinned = S93.PinnedRepository(root / relative_path, repo_fd, git_fd, cache)
        pinned.git = types.MethodType(_git_no_lazy_fetch, pinned)
        repo_fd = -1
        try:
            head = pinned.git("rev-parse", "--verify", "HEAD^{commit}").decode("ascii").strip().lower()
            if not S93.OID_RE.fullmatch(head):
                raise Stage12696Error("invalid_head_oid")
            head_object = S93.read_verified_object(pinned, head, "commit")
            pinned._stage12696_head_object = head_object
            pinned._stage12696_head_commit = S93.parse_raw_commit(head_object, head)
            pinned.cache.bind_head(head)
            pinned.head_oid = head
            yield pinned
        finally:
            try:
                _revalidate_repository_path(root_fd, relative_path, pinned)
            finally:
                pinned.close()
    finally:
        if repo_fd >= 0:
            os.close(repo_fd)


@contextmanager
def pin_repository_at_root(root: Path, relative_path: str):
    root_fd = _open_absolute_directory(root)
    try:
        with pin_repository_at_fd(root, root_fd, relative_path) as pinned:
            yield pinned
    finally:
        os.close(root_fd)


def _authenticate_jsonl(
    root: Path, relative_path: str, expected_sha256: str, limits: PackageLimits,
    *, accepted_role: str | None = None, generation_token: object | None = None,
    root_fd: int | None = None,
) -> AuthenticatedJsonl:
    if len(expected_sha256) != 64 or not S93.OID_RE.fullmatch(expected_sha256):
        raise Stage12696Error("invalid_jsonl_authentication_request")
    fd = (
        _open_at_root_fd(root_fd, relative_path, directory=False)
        if root_fd is not None else _open_at_root(root, relative_path, directory=False)
    )
    try:
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or info.st_size > limits.jsonl_bytes:
            raise Stage12696Error("jsonl_not_bounded_regular_file")
        data = bytearray()
        while len(data) <= limits.jsonl_bytes:
            chunk = os.read(fd, min(1024 * 1024, limits.jsonl_bytes - len(data) + 1))
            if not chunk:
                break
            data.extend(chunk)
        if len(data) > limits.jsonl_bytes:
            raise Stage12696Error("resource_limit_exceeded:jsonl_bytes")
    finally:
        os.close(fd)
    raw = bytes(data)
    if _sha(raw) != expected_sha256:
        raise Stage12696Error("jsonl_file_commitment_mismatch")
    lines = raw.splitlines()
    if len(lines) > limits.jsonl_lines or any(not line for line in lines):
        raise Stage12696Error("invalid_or_unbounded_jsonl")
    records: list[dict[str, Any]] = []
    line_hashes: list[str] = []
    for line in lines:
        try:
            record = json.loads(line)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise Stage12696Error("invalid_jsonl_record") from exc
        if not isinstance(record, dict) or _canonical(record) != line:
            raise Stage12696Error("noncanonical_jsonl_record")
        records.append(record)
        line_hashes.append(_sha(line))
    commitment = _stable(["stage12696_jsonl_membership_v1", expected_sha256, line_hashes])
    return AuthenticatedJsonl(
        tuple(records), expected_sha256, tuple(line_hashes), commitment,
        root, relative_path, info.st_dev, info.st_ino, _MEMBERSHIP_SEAL,
        accepted_role, generation_token,
    )


def authenticate_jsonl(
    root: Path, relative_path: str, expected_sha256: str, limits: PackageLimits,
) -> AuthenticatedJsonl:
    """Authenticate one file without granting accepted-generation authority."""
    return _authenticate_jsonl(root, relative_path, expected_sha256, limits)


def _reauthenticate_membership(
    value: AuthenticatedJsonl, limits: PackageLimits,
    root_handle: _PinnedGenerationRoot | None = None,
) -> AuthenticatedJsonl:
    if not isinstance(value, AuthenticatedJsonl) or value._seal is not _MEMBERSHIP_SEAL:
        raise Stage12696Error("unauthenticated_membership")
    fresh = _authenticate_jsonl(
        value.root_path, value.relative_path, value.file_sha256, limits,
        accepted_role=value._accepted_role, generation_token=value._generation_token,
        root_fd=root_handle.fd if root_handle is not None else None,
    )
    if (
        fresh.device != value.device or fresh.inode != value.inode
        or fresh.records != value.records or fresh.line_sha256s != value.line_sha256s
        or fresh.membership_commitment_sha256 != value.membership_commitment_sha256
    ):
        raise Stage12696Error("authenticated_membership_replaced")
    return fresh


def _generation_contract(
    root: Path, memberships: Mapping[str, AuthenticatedJsonl],
) -> tuple[Any, ...]:
    return (
        str(root),
        tuple(
            (
                role, value.relative_path, value.file_sha256, value.device,
                value.inode, value.membership_commitment_sha256,
            )
            for role, value in sorted(memberships.items())
        ),
    )


def _require_accepted_generation(
    memberships: Mapping[str, AuthenticatedJsonl],
) -> _PinnedGenerationRoot:
    expected_roles = set(ACCEPTED_ARTIFACT_SHA256S)
    if set(memberships) != expected_roles or set(ACCEPTED_ARTIFACT_RELATIVE_PATHS) != expected_roles:
        raise Stage12696Error("accepted_artifact_role_set_mismatch")
    if any(not isinstance(value, AuthenticatedJsonl) for value in memberships.values()):
        raise Stage12696Error("accepted_artifact_membership_type_mismatch")
    tokens = {value._generation_token for value in memberships.values()}
    if len(tokens) != 1 or None in tokens:
        raise Stage12696Error("accepted_generation_token_missing_or_mixed")
    token = next(iter(tokens))
    issued = _ISSUED_GENERATION_TOKENS.get(token)
    if issued is None:
        raise Stage12696Error("accepted_generation_token_not_issued")
    root_handle, issued_contract = issued
    root_handle.revalidate()
    roots = {value.root_path for value in memberships.values()}
    if len(roots) != 1:
        raise Stage12696Error("accepted_generation_root_mismatch")
    for role, value in memberships.items():
        if (
            value._seal is not _MEMBERSHIP_SEAL or value._accepted_role != role
            or value.relative_path != ACCEPTED_ARTIFACT_RELATIVE_PATHS[role]
            or value.file_sha256 != ACCEPTED_ARTIFACT_SHA256S[role]
        ):
            raise Stage12696Error("accepted_artifact_role_path_or_digest_mismatch")
    if _generation_contract(next(iter(roots)), memberships) != issued_contract:
        raise Stage12696Error("accepted_generation_contract_mismatch")
    return root_handle


def _read(repo: Any, oid: str, kind: str, budget: WorkBudget) -> bytes:
    budget.charge("object_reads")
    cached_head = getattr(repo, "_stage12696_head_object", None)
    if cached_head is not None and oid == repo.head_oid and kind == "commit":
        data = cached_head
    else:
        reader = getattr(repo, "_stage12696_object_reader", None)
        data = (
            reader.read(oid, kind) if reader is not None
            else S93.read_verified_object(repo, oid, kind)
        )
    if kind == "blob":
        budget.charge("blob_bytes", len(data))
    return data


def _tree(repo: Any, oid: str, budget: WorkBudget) -> tuple[Any, ...]:
    budget.charge("trees")
    entries = S93.parse_raw_tree(_read(repo, oid, "tree", budget), len(oid))
    budget.charge("tree_entries", len(entries))
    return entries


def _parse_batch_blob_sizes(
    ordered: Sequence[str], stdout: bytes,
) -> dict[str, int]:
    try:
        lines = stdout.decode("ascii", errors="strict").splitlines()
    except UnicodeDecodeError as exc:
        raise Stage12696Error("batch_blob_metadata_mismatch") from exc
    if len(lines) != len(ordered):
        raise Stage12696Error("batch_blob_metadata_count_mismatch")
    sizes: dict[str, int] = {}
    for expected_oid, line in zip(ordered, lines, strict=True):
        parts = line.split(" ")
        if (
            len(parts) != 3 or parts[0] != expected_oid or parts[1] != "blob"
            or not parts[2] or (
                parts[2] != "0" and (
                    parts[2].startswith("0") or not parts[2].isdigit()
                )
            )
        ):
            raise Stage12696Error("batch_blob_metadata_mismatch")
        sizes[expected_oid] = int(parts[2])
    return sizes


def _batch_blob_sizes(
    repo: Any, blob_oids: Iterable[str], budget: WorkBudget,
) -> dict[str, int]:
    ordered = tuple(sorted(set(blob_oids)))
    if not ordered:
        return {}
    if (
        len(ordered) > min(
            budget.limits.tree_entries, MAX_BATCH_BLOB_OBJECTS,
        )
        or any(not S93.OID_RE.fullmatch(oid) for oid in ordered)
    ):
        raise Stage12696Error("invalid_batch_blob_inventory")
    request = ("\n".join(ordered) + "\n").encode("ascii")
    max_output_bytes = min(len(ordered) * 128, MAX_BATCH_RESPONSE_BYTES)
    if len(request) > MAX_BATCH_REQUEST_BYTES:
        raise Stage12696Error("batch_blob_request_bytes_exceeded")
    budget.charge("object_reads", len(ordered))
    command = [
        "git", "--no-replace-objects",
        f"--git-dir=/proc/self/fd/{repo.git_fd}",
        f"--work-tree=/proc/self/fd/{repo.repo_fd}",
        "cat-file",
        "--batch-check=%(objectname) %(objecttype) %(objectsize)",
    ]
    environment = {
        "GIT_CONFIG_GLOBAL": "/dev/null",
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_NO_LAZY_FETCH": "1",
        "GIT_OPTIONAL_LOCKS": "0",
        "HOME": "/nonexistent",
        "LC_ALL": "C",
        "PATH": os.defpath,
    }
    process: subprocess.Popen[bytes] | None = None
    selector = selectors.DefaultSelector()
    try:
        process = subprocess.Popen(
            command,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            env=environment,
            pass_fds=(repo.repo_fd, repo.git_fd),
            start_new_session=True,
        )
        assert process.stdin is not None and process.stdout is not None
        os.set_blocking(process.stdin.fileno(), False)
        os.set_blocking(process.stdout.fileno(), False)
        selector.register(process.stdin, selectors.EVENT_WRITE, "stdin")
        selector.register(process.stdout, selectors.EVENT_READ, "stdout")
        request_offset = 0
        output = bytearray()
        deadline = budget.operation_deadline()
        while selector.get_map():
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise Stage12696Error("batch_blob_metadata_timeout")
            events = selector.select(remaining)
            if not events:
                raise Stage12696Error("batch_blob_metadata_timeout")
            for key, _mask in events:
                if key.data == "stdin":
                    try:
                        written = os.write(
                            process.stdin.fileno(),
                            request[request_offset:request_offset + 65536],
                        )
                    except BrokenPipeError:
                        written = 0
                    request_offset += written
                    if written == 0 or request_offset == len(request):
                        selector.unregister(process.stdin)
                        process.stdin.close()
                else:
                    chunk = os.read(
                        process.stdout.fileno(),
                        min(65536, max_output_bytes - len(output) + 1),
                    )
                    if not chunk:
                        selector.unregister(process.stdout)
                        process.stdout.close()
                    else:
                        output.extend(chunk)
                        if len(output) > max_output_bytes:
                            raise Stage12696Error(
                                "batch_blob_response_bytes_exceeded"
                            )
        returncode = process.wait(
            timeout=max(0.001, deadline - time.monotonic()),
        )
        if returncode != 0:
            raise Stage12696Error("batch_blob_metadata_failed")
        return _parse_batch_blob_sizes(ordered, bytes(output))
    except (OSError, subprocess.TimeoutExpired) as exc:
        if process is not None:
            _kill_process_group(process)
        raise Stage12696Error("batch_blob_metadata_failed") from exc
    except BaseException:
        if process is not None:
            _kill_process_group(process)
        raise
    finally:
        selector.close()


def _derive_git_head_evidence(
    catalog_record: Mapping[str, Any], catalog_line_sha256: str,
    repo: Any, budget: WorkBudget,
    lineage_commit_oids: Sequence[str] = (),
) -> GitHeadEvidence:
    required = {"repository_key_sha256", "revision"}
    if not required <= catalog_record.keys() or not S93.OID_RE.fullmatch(catalog_line_sha256):
        raise Stage12696Error("catalog_identity_missing")
    repo_key = catalog_record["repository_key_sha256"]
    revision = catalog_record["revision"]
    if not isinstance(repo_key, str) or len(repo_key) != 64 or not isinstance(revision, str) or not S93.OID_RE.fullmatch(revision):
        raise Stage12696Error("invalid_catalog_identity")
    try:
        if repo.head_oid != revision:
            raise Stage12696Error("pinned_revision_mismatch")
        targets = tuple(sorted(set(lineage_commit_oids)))
        if any(not isinstance(oid, str) or not S93.OID_RE.fullmatch(oid) for oid in targets):
            raise Stage12696Error("invalid_lineage_commit_target")
        budget.charge("commits")
        head_commit = S93.parse_raw_commit(
            _read(repo, revision, "commit", budget), revision,
        )
        inspected: dict[str, Any] = {revision: head_commit}
        roots = tuple(catalog_record.get("root_commit_git_oids", ()))
        if (
            not roots or roots != tuple(sorted(set(roots)))
            or any(not isinstance(oid, str) or not S93.OID_RE.fullmatch(oid) for oid in roots)
        ):
            raise Stage12696Error("invalid_catalog_root_inventory")
        for oid in roots:
            if oid not in inspected:
                try:
                    budget.charge("commits")
                    inspected[oid] = S93.parse_raw_commit(
                        _read(repo, oid, "commit", budget), oid,
                    )
                except (S93.Stage12693Error, Stage12696Error) as exc:
                    raise Stage12696Error(
                        "catalog_git_derivation_mismatch"
                    ) from exc
            if inspected[oid].parent_oids:
                raise Stage12696Error("catalog_root_has_parent")

        available_targets = set()
        target_commits: dict[str, Any] = {}
        for oid in targets:
            if oid in inspected:
                available_targets.add(oid)
                continue
            try:
                budget.charge("commits")
                target_commits[oid] = S93.parse_raw_commit(
                    _read(repo, oid, "commit", budget), oid,
                )
            except (S93.Stage12693Error, Stage12696Error):
                continue
            inspected[oid] = target_commits[oid]
            available_targets.add(oid)

        matched_targets = {revision} & available_targets
        unresolved = available_targets - matched_targets
        pending = list(sorted(head_commit.parent_oids, reverse=True))
        seen = {revision}
        while pending and unresolved:
            oid = pending.pop()
            if oid in seen:
                continue
            seen.add(oid)
            commit = inspected.get(oid) or target_commits.get(oid)
            if commit is None:
                budget.charge("commits")
                commit = S93.parse_raw_commit(
                    _read(repo, oid, "commit", budget), oid,
                )
            inspected[oid] = commit
            if oid in unresolved:
                matched_targets.add(oid)
                unresolved.remove(oid)
            pending.extend(sorted(commit.parent_oids, reverse=True))

        root_tree = head_commit.tree_oid
        authenticated_commits = tuple(sorted({revision, *matched_targets}))
        objects: set[tuple[str, str, int | None]] = {
            ("commit", oid, None) for oid in authenticated_commits
        }
        component_objects: list[tuple[str, str, int | None]] = []
        tree_entry_evidence: list[tuple[str, str, str, str, str]] = []
        component_tree_entry_evidence: list[tuple[str, str, str, str, str]] = []
        gitlinks: list[tuple[str, str, str, str, str]] = []
        blob_placements: list[str] = []
        visited_tree_placements: set[tuple[str, str]] = set()
        stack = [(root_tree, "")]
        while stack:
            current, prefix = stack.pop()
            placement = (current, prefix)
            if placement in visited_tree_placements:
                continue
            entries = _tree(repo, current, budget)
            visited_tree_placements.add(placement)
            objects.add(("tree", current, len(entries)))
            for entry in entries:
                full_path = entry.path if not prefix else f"{prefix}/{entry.path}"
                evidence = (current, entry.mode, entry.object_type, entry.oid, full_path)
                tree_entry_evidence.append(evidence)
                component_tree_entry_evidence.append(evidence)
                if entry.mode == "160000":
                    gitlinks.append(evidence)
                    component_objects.append(("commit", entry.oid, None))
                elif entry.object_type == "tree":
                    stack.append((entry.oid, full_path))
                elif entry.object_type == "blob":
                    objects.add(("blob", entry.oid, None))
                    blob_placements.append(entry.oid)
                else:
                    raise Stage12696Error("unexpected_tree_entry_type")
        blob_sizes = _batch_blob_sizes(repo, blob_placements, budget)
        component_objects.extend(
            ("blob", oid, blob_sizes[oid]) for oid in blob_placements
        )
        component_objects.sort()
    except S93.Stage12693Error as exc:
        raise Stage12696Error(f"git_evidence_failure:{exc}") from exc
    ordered = [sorted(objects), sorted(tree_entry_evidence), sorted(gitlinks)]
    if (
        catalog_record.get("head_commit_git_oid", revision) != revision
        or catalog_record.get("git_tree_oid", root_tree) != root_tree
        or tuple(sorted(catalog_record.get("root_commit_git_oids", roots))) != roots
    ):
        raise Stage12696Error("catalog_git_derivation_mismatch")
    component_type_counts = dict(sorted(Counter(
        object_type for object_type, _oid, _size in component_objects
    ).items()))
    if catalog_record.get("all_tree_object_count") != len(component_objects):
        raise Stage12696Error("catalog_component_object_count_mismatch")
    if catalog_record.get("all_tree_object_identity_inventory_sha256") != (
        S92.stage12688.stable(component_objects)
    ):
        raise Stage12696Error("catalog_component_object_inventory_mismatch")
    if catalog_record.get("tree_object_type_counts") != component_type_counts:
        raise Stage12696Error("catalog_component_object_type_counts_mismatch")
    derived = {
        "repository_key_sha256": repo_key,
        "revision": revision,
        "commit_oids": authenticated_commits,
        "root_commit_oids": roots,
        "root_tree_oid": root_tree,
        "commit_objects_inspected": len(inspected),
        "tree_count": sum(kind == "tree" for kind, _, _ in objects),
        "blob_count": sum(kind == "blob" for kind, _, _ in objects),
        "submodule_count": len(gitlinks),
        "total_object_count": len(objects) + len(gitlinks),
        "component_objects": tuple(component_objects),
        "tree_entry_identities": tuple(sorted(tree_entry_evidence)),
        "component_tree_entry_identities": tuple(sorted(component_tree_entry_evidence)),
        "gitlink_identities": tuple(sorted(gitlinks)),
        "object_inventory_sha256": _stable(ordered),
        "catalog_line_sha256": catalog_line_sha256,
    }
    return GitHeadEvidence(**derived, evidence_commitment_sha256=_stable(["stage12696_git_head_evidence_v1", derived]))


def derive_git_head_evidence(
    catalog_record: Mapping[str, Any], catalog_line_sha256: str,
    repository_root: Path, repository_relative_path: str, budget: WorkBudget,
    lineage_commit_oids: Sequence[str] = (),
) -> GitHeadEvidence:
    budget.begin_repository()
    try:
        with pin_repository_at_root(repository_root, repository_relative_path) as repo:
            with _BatchObjectReader(repo, budget) as reader:
                repo._stage12696_object_reader = reader
                return _derive_git_head_evidence(
                    catalog_record, catalog_line_sha256, repo, budget,
                    lineage_commit_oids,
                )
    finally:
        budget.end_repository()


def _find_blob(repo: Any, commit_oid: str, path: str, budget: WorkBudget) -> tuple[str, bytes]:
    if not S92.stage12688.canonical_git_path(path):
        raise Stage12696Error("noncanonical_declaration_path")
    commit = S93.parse_raw_commit(_read(repo, commit_oid, "commit", budget), commit_oid)
    tree_oid = commit.tree_oid
    parts = PurePosixPath(path).parts
    for index, part in enumerate(parts):
        entries = _tree(repo, tree_oid, budget)
        matches = [entry for entry in entries if entry.path == part]
        if len(matches) != 1:
            raise Stage12696Error("declaration_path_not_found")
        entry = matches[0]
        leaf = index == len(parts) - 1
        if leaf:
            if entry.object_type != "blob" or entry.mode not in {"100644", "100755"}:
                raise Stage12696Error("declaration_leaf_not_regular_blob")
            return entry.oid, _read(repo, entry.oid, "blob", budget)
        if entry.object_type != "tree":
            raise Stage12696Error("declaration_parent_not_tree")
        tree_oid = entry.oid
    raise Stage12696Error("empty_declaration_path")


def _adapter_rows(source: bytes, row: Mapping[str, Any]) -> list[dict[str, Any]]:
    provenance = row.get("source_provenance")
    if not isinstance(provenance, dict):
        raise Stage12696Error("declaration_provenance_missing")
    path = provenance.get("source_path")
    adapter = provenance.get("parser_adapter")
    if not isinstance(path, str) or not isinstance(adapter, dict) or adapter.get("version") != "1" or adapter.get("name") not in SUPPORTED_ADAPTERS:
        raise Stage12696Error("unsupported_parser_adapter")
    function = S92._adapter_for_path(path)
    expected_name = {
        S92.extract_package_json_rows: "stdlib_json_plus_byte_spans",
        S92.extract_tox_ini_rows: "stdlib_configparser_strict",
        S92.extract_pyproject_toml_rows: "stdlib_tomllib_pyproject",
        S92.extract_cargo_toml_rows: "stdlib_tomllib_cargo",
        S92.extract_makefile_rows: "raw_makefile_literal_rules",
    }[function]
    if adapter["name"] != expected_name:
        raise Stage12696Error("parser_adapter_path_mismatch")
    kwargs = {
        "repository_key_sha256": provenance["repository_key_sha256"],
        "revision": provenance["revision"],
    }
    if function is S92.extract_package_json_rows:
        rows = function(source, package_blob_oid=provenance["source_git_blob_oid"], package_path=path, **kwargs)
    else:
        rows = function(source, source_blob_oid=provenance["source_git_blob_oid"], source_path=path, **kwargs)
    for candidate in rows:
        candidate_provenance = candidate["source_provenance"]
        candidate_provenance.update({
            "source_path": candidate_provenance.get("source_path", candidate_provenance.get("package_path")),
            "source_git_blob_oid": candidate_provenance.get("source_git_blob_oid", candidate_provenance.get("package_git_blob_oid")),
            "source_file_sha256": candidate_provenance.get("source_file_sha256", candidate_provenance.get("package_file_sha256")),
        })
    return rows


def _authenticate_declaration_row(
    row: Mapping[str, Any], proof: Mapping[str, Any], row_membership_sha256: str,
    proof_membership_sha256: str, repo: Any, budget: WorkBudget,
    blob_cache: dict[tuple[str, str], tuple[str, bytes]] | None = None,
    parser_cache: dict[tuple[str, str, str, str], tuple[dict[str, Any], ...]] | None = None,
) -> DeclarationEvidence:
    budget.charge("declaration_rows")
    if not S93.OID_RE.fullmatch(row_membership_sha256) or not S93.OID_RE.fullmatch(proof_membership_sha256):
        raise Stage12696Error("declaration_membership_missing")
    if proof.get("row_sha256") != S92.stage12688.stable(dict(row)) or proof.get("row_id") != row.get("row_id"):
        raise Stage12696Error("row_proof_commitment_mismatch")
    provenance = row.get("source_provenance")
    if not isinstance(provenance, dict):
        raise Stage12696Error("declaration_provenance_missing")
    for field in ("repository_key_sha256", "revision", "source_path", "source_git_blob_oid", "source_file_sha256"):
        if not isinstance(provenance.get(field), str):
            raise Stage12696Error("declaration_identity_missing")
    try:
        if repo.head_oid != provenance["revision"]:
            raise Stage12696Error("pinned_revision_mismatch")
        blob_key = (provenance["revision"], provenance["source_path"])
        cached_blob = blob_cache.get(blob_key) if blob_cache is not None else None
        if cached_blob is None:
            oid, source = _find_blob(
                repo, provenance["revision"], provenance["source_path"], budget,
            )
            if blob_cache is not None:
                blob_cache[blob_key] = (oid, bytes(source))
        else:
            oid, source = cached_blob
    except S93.Stage12693Error as exc:
        raise Stage12696Error(f"declaration_git_failure:{exc}") from exc
    if oid != provenance["source_git_blob_oid"] or _sha(source) != provenance["source_file_sha256"]:
        raise Stage12696Error("declaration_blob_identity_mismatch")
    adapter = provenance.get("parser_adapter")
    adapter_name = adapter.get("name") if isinstance(adapter, dict) else ""
    parser_key = (
        provenance["revision"], provenance["source_path"], oid, adapter_name,
    )
    cached_rows = parser_cache.get(parser_key) if parser_cache is not None else None
    if cached_rows is None:
        try:
            reproduced = _adapter_rows(source, row)
        except (S92.PackageJsonError, S92.Stage12692BuildError, KeyError, TypeError, ValueError) as exc:
            raise Stage12696Error("declaration_parser_replay_failed") from exc
        if len(reproduced) > budget.limits.declaration_rows:
            raise Stage12696Error("resource_limit_exceeded:declaration_rows")
        if parser_cache is not None:
            parser_cache[parser_key] = tuple(
                json.loads(json.dumps(candidate)) for candidate in reproduced
            )
    else:
        reproduced = [json.loads(json.dumps(candidate)) for candidate in cached_rows]
    exact = [candidate for candidate in reproduced if candidate.get("row_id") == row.get("row_id")]
    supplied_parser_projection = json.loads(json.dumps({key: value for key, value in row.items() if key != "split"}))
    supplied_provenance = supplied_parser_projection.get("source_provenance", {})
    # Stage12692 adds these catalog-derived fields after adapter extraction.
    # They are bound separately by the authenticated catalog/package inventory.
    supplied_provenance.pop("content_component_sha256", None)
    supplied_provenance.pop("tree_oid", None)
    if len(exact) != 1 or exact[0] != supplied_parser_projection:
        raise Stage12696Error("declaration_row_not_reproduced")
    for field in ("repository_key_sha256", "revision", "source_path", "source_file_sha256"):
        if proof.get(field) != provenance[field]:
            raise Stage12696Error("declaration_proof_identity_mismatch")
    adapter_name = provenance["parser_adapter"]["name"]
    derived = {
        "row_id": row["row_id"], "repository_key_sha256": provenance["repository_key_sha256"],
        "revision": provenance["revision"], "source_path": provenance["source_path"],
        "source_blob_oid": oid, "source_file_sha256": _sha(source),
        "source_size": len(source),
        "parser_adapter": adapter_name, "reproduced_row_sha256": S92.stage12688.stable(exact[0]),
        "row_membership_sha256": row_membership_sha256,
        "proof_membership_sha256": proof_membership_sha256,
    }
    return DeclarationEvidence(**derived, source_bytes=bytes(source), evidence_commitment_sha256=_stable(["stage12696_declaration_evidence_v1", derived]))


def authenticate_declaration_row(
    row: Mapping[str, Any], proof: Mapping[str, Any], row_membership_sha256: str,
    proof_membership_sha256: str, repository_root: Path,
    repository_relative_path: str, budget: WorkBudget,
) -> DeclarationEvidence:
    budget.begin_repository()
    try:
        with pin_repository_at_root(repository_root, repository_relative_path) as repo:
            with _BatchObjectReader(repo, budget) as reader:
                repo._stage12696_object_reader = reader
                return _authenticate_declaration_row(
                    row, proof, row_membership_sha256, proof_membership_sha256,
                    repo, budget,
                )
    finally:
        budget.end_repository()


def build_package_inventory(
    *, stage12688_catalog: AuthenticatedJsonl, stage12692_rows: AuthenticatedJsonl,
    stage12692_catalog: AuthenticatedJsonl, stage12692_ledger: AuthenticatedJsonl,
    repository_root: Path, repository_paths: Mapping[str, str],
    lineage_commit_oids: Sequence[str] = (),
    limits: PackageLimits | None = None,
) -> PackageInventory:
    limits = limits or PackageLimits()
    budget = WorkBudget(limits)
    memberships = {
        "stage12688_catalog": stage12688_catalog,
        "stage12692_rows": stage12692_rows,
        "stage12692_catalog": stage12692_catalog,
        "stage12692_ledger": stage12692_ledger,
    }
    root_handle = _require_accepted_generation(memberships)
    stage12688_catalog = _reauthenticate_membership(stage12688_catalog, limits, root_handle)
    stage12692_rows = _reauthenticate_membership(stage12692_rows, limits, root_handle)
    stage12692_catalog = _reauthenticate_membership(stage12692_catalog, limits, root_handle)
    stage12692_ledger = _reauthenticate_membership(stage12692_ledger, limits, root_handle)
    metadata_keys = {item.get("repository_key_sha256") for item in stage12688_catalog.records}
    declaration_keys = {item.get("repository_key_sha256") for item in stage12692_catalog.records}
    unique_repository_keys = metadata_keys | declaration_keys
    if None in unique_repository_keys or len(unique_repository_keys) > limits.repositories:
        raise Stage12696Error("resource_limit_exceeded:repositories")
    if set(repository_paths) != unique_repository_keys:
        raise Stage12696Error("repository_path_identity_set_mismatch")
    for relative_path in repository_paths.values():
        _canonical_relative_path(relative_path)
    proofs_by_id = {
        proof.get("row_id"): (proof, line_hash)
        for proof, line_hash in zip(
            stage12692_ledger.records, stage12692_ledger.line_sha256s,
        )
    }
    if len(proofs_by_id) != len(stage12692_ledger.records):
        raise Stage12696Error("duplicate_proof_row_id")
    catalogs_by_identity = {
        (item.get("repository_key_sha256"), item.get("revision")): item
        for item in stage12692_catalog.records
    }
    if len(catalogs_by_identity) != len(stage12692_catalog.records):
        raise Stage12696Error("duplicate_declaration_catalog_identity")

    metadata_work: dict[str, list[tuple[int, Mapping[str, Any], str]]] = {}
    for index, (record, line_hash) in enumerate(zip(
        stage12688_catalog.records, stage12688_catalog.line_sha256s,
    )):
        metadata_work.setdefault(record.get("repository_key_sha256"), []).append(
            (index, record, line_hash)
        )
    declaration_work: dict[
        str, list[tuple[int, Mapping[str, Any], str, Mapping[str, Any], str]]
    ] = {}
    for index, (row, row_hash) in enumerate(zip(
        stage12692_rows.records, stage12692_rows.line_sha256s,
    )):
        provenance = row.get("source_provenance", {})
        identity = (
            provenance.get("repository_key_sha256"), provenance.get("revision"),
        )
        catalog_record = catalogs_by_identity.get(identity)
        if catalog_record is None or identity[0] not in unique_repository_keys:
            raise Stage12696Error("declaration_catalog_or_repository_missing")
        if (
            provenance.get("tree_oid") != catalog_record.get("tree_oid")
            or provenance.get("content_component_sha256")
            != catalog_record.get("content_component_sha256")
        ):
            raise Stage12696Error("declaration_catalog_identity_mismatch")
        pair = proofs_by_id.get(row.get("row_id"))
        if pair is None:
            raise Stage12696Error("declaration_proof_missing")
        declaration_work.setdefault(identity[0], []).append(
            (index, row, row_hash, pair[0], pair[1])
        )

    git_heads_by_index: dict[int, GitHeadEvidence] = {}
    declarations_by_index: dict[int, DeclarationEvidence] = {}
    with _pinned_root_handle(repository_root) as repository_root_handle:
        for key in sorted(unique_repository_keys):
            budget.begin_repository()
            with pin_repository_at_fd(
                repository_root_handle.path, repository_root_handle.fd,
                repository_paths[key],
            ) as repo:
                with _BatchObjectReader(repo, budget) as reader:
                    repo._stage12696_object_reader = reader
                    blob_cache: dict[tuple[str, str], tuple[str, bytes]] = {}
                    parser_cache: dict[
                        tuple[str, str, str, str], tuple[dict[str, Any], ...]
                    ] = {}
                    for index, record, line_hash in metadata_work.get(key, ()):
                        revision = record.get("revision")
                        try:
                            evidence = _derive_git_head_evidence(
                                record, line_hash, repo, budget,
                                lineage_commit_oids,
                            )
                        except Stage12696Error as exc:
                            raise Stage12696Error(
                                f"git_head_evidence_failed:{key}:{revision}:{exc}"
                            ) from exc
                        git_heads_by_index[index] = evidence
                    for index, row, row_hash, proof, proof_hash in (
                        declaration_work.get(key, ())
                    ):
                        declarations_by_index[index] = _authenticate_declaration_row(
                            row, proof, row_hash, proof_hash, repo, budget,
                            blob_cache, parser_cache,
                        )
            budget.end_repository()
            repository_root_handle.revalidate()
        repository_root_handle.revalidate()

    if len(git_heads_by_index) != len(stage12688_catalog.records):
        raise Stage12696Error("git_head_inventory_reconciliation_failed")
    if len(declarations_by_index) != len(stage12692_rows.records):
        raise Stage12696Error("declaration_inventory_reconciliation_failed")
    git_heads = [git_heads_by_index[index] for index in range(len(git_heads_by_index))]
    declarations = [
        declarations_by_index[index] for index in range(len(declarations_by_index))
    ]
    for membership in (
        stage12688_catalog, stage12692_rows,
        stage12692_catalog, stage12692_ledger,
    ):
        _reauthenticate_membership(membership, limits, root_handle)
    root_handle.revalidate()
    commitments = (
        stage12688_catalog.membership_commitment_sha256,
        stage12692_rows.membership_commitment_sha256,
        stage12692_catalog.membership_commitment_sha256,
        stage12692_ledger.membership_commitment_sha256,
    )
    head_commitments = sorted(item.evidence_commitment_sha256 for item in git_heads)
    declaration_commitments = sorted(item.evidence_commitment_sha256 for item in declarations)
    capacity = {
        "authenticated_git_heads": len(git_heads),
        "authenticated_declaration_rows": len(declarations),
        "unique_declaration_blobs": len({(item.revision, item.source_blob_oid) for item in declarations}),
        "authenticated_unique_repositories": len(unique_repository_keys),
        "training_eligible_rows": 0,
    }
    manifest = _stable(["stage12696_package_manifest_v1", commitments, head_commitments, declaration_commitments, capacity, AUTHORITY])
    root_handle.revalidate()
    return PackageInventory(tuple(git_heads), tuple(declarations), commitments, manifest, capacity, dict(AUTHORITY))


def load_accepted_artifact_memberships(
    workspace_root: Path, limits: PackageLimits | None = None,
) -> dict[str, AuthenticatedJsonl]:
    """Load four accepted artifacts; caller owns and must close the returned bundle."""
    limits = limits or PackageLimits()
    if not workspace_root.is_absolute():
        raise Stage12696Error("workspace_root_must_be_absolute")
    if set(ACCEPTED_ARTIFACT_RELATIVE_PATHS) != set(ACCEPTED_ARTIFACT_SHA256S):
        raise Stage12696Error("accepted_artifact_role_set_mismatch")
    token = object()
    root_fd = _open_absolute_directory(workspace_root)
    root_info = os.fstat(root_fd)
    guard_fd = os.dup(root_fd)
    try:
        offset_cookie = os.lseek(root_fd, 1, os.SEEK_SET)
        if os.lseek(guard_fd, 0, os.SEEK_CUR) != offset_cookie:
            raise Stage12696Error("accepted_generation_root_guard_not_shared")
    except Exception:
        os.close(guard_fd)
        os.close(root_fd)
        raise
    root_handle = _PinnedGenerationRoot(
        workspace_root, root_fd, guard_fd, root_info.st_dev, root_info.st_ino,
        offset_cookie,
    )
    try:
        result = {
            role: _authenticate_jsonl(
                workspace_root, path, ACCEPTED_ARTIFACT_SHA256S[role], limits,
                accepted_role=role, generation_token=token, root_fd=root_handle.fd,
            )
            for role, path in ACCEPTED_ARTIFACT_RELATIVE_PATHS.items()
        }
        root_handle.revalidate()
        _ISSUED_GENERATION_TOKENS[token] = (
            root_handle, _generation_contract(workspace_root, result),
        )
        return result
    except Exception:
        root_handle.close()
        raise


def close_accepted_artifact_memberships(
    memberships: Mapping[str, AuthenticatedJsonl],
) -> None:
    """Idempotently close the loader-owned generation root descriptor."""
    if set(memberships) != set(ACCEPTED_ARTIFACT_SHA256S):
        raise Stage12696Error("accepted_artifact_role_set_mismatch")
    tokens = {
        value._generation_token for value in memberships.values()
        if isinstance(value, AuthenticatedJsonl) and value._generation_token is not None
    }
    if len(tokens) != 1:
        raise Stage12696Error("accepted_generation_token_missing_or_mixed")
    issued = _ISSUED_GENERATION_TOKENS.get(next(iter(tokens)))
    if issued is None:
        raise Stage12696Error("accepted_generation_token_not_issued")
    issued[0].close()


__all__ = [
    "ACCEPTED_ARTIFACT_RELATIVE_PATHS", "ACCEPTED_ARTIFACT_SHA256S", "ACCEPTED_STAGE12688_GENERATION", "ACCEPTED_STAGE12692_GENERATION", "AUTHORITY",
    "AuthenticatedJsonl", "DeclarationEvidence", "GitHeadEvidence", "PackageInventory",
    "PackageLimits", "Stage12696Error", "WorkBudget", "authenticate_declaration_row",
    "authenticate_jsonl", "build_package_inventory", "close_accepted_artifact_memberships", "derive_git_head_evidence",
    "load_accepted_artifact_memberships",
]
