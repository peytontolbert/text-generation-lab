#!/usr/bin/env python3
"""Nonpublishing Stage12697 reviewed-local observed-verifier join packages."""
from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import re
import shlex
import stat
import sys
from collections import Counter
from pathlib import Path, PurePosixPath
from typing import Any, Mapping, Sequence

ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = "configs/software_maintainer/stage12697_pinned_observation_sources_v1.json"
REVIEWED_CONFIG_SHA256 = "3bdde180a6d774491127232830858a0c0fd84072476704a322606f22a38d8aae"
MAX_FILE_BYTES = 16 * 1024 * 1024
SOURCE_STREAM_CAPTURE_LIMIT = 20_000
MAX_SHALLOW_FILE_BYTES = 4096
MAX_SNAPSHOT_TREE_DEPTH = 128
MAX_SNAPSHOT_TREE_PLACEMENTS = 100_000
MAX_SNAPSHOT_ENTRIES = 500_000
MAX_SNAPSHOT_BLOBS = 500_000
MAX_SNAPSHOT_BLOB_BYTES = 512 * 1024 * 1024
AUTHORITY = {key: False for key in (
    "implementation_ready", "stage12595_allowed", "replay_trustworthy",
    "level_3_materialized", "training_admitted", "strict_eval_admitted",
    "sealed_eval_admitted",
)}
PY_SUMMARY = re.compile(
    r"(\d+ (?:passed|failed|errors?|skipped|xfailed|xpassed)"
    r"(?:, \d+ (?:passed|failed|errors?|skipped|xfailed|xpassed))*)"
    r" in \d+(?:\.\d+)?s\Z"
)
PY_COUNT = re.compile(r"(\d+) (passed|failed|errors?|skipped|xfailed|xpassed)")
PY_COLLECTION = re.compile(r"(\d+) tests? collected in \d+(?:\.\d+)?s\Z")
CT_SUMMARY = re.compile(r"(\d+)% tests passed, (\d+) tests failed out of (\d+)\Z")
CT_RESULT = re.compile(
    r"^\s*(\d+)/(\d+) Test #(\d+): (\S+)\s+\.*\s*"
    r"(Passed|(?:\*\*\*)?Failed)\s+\d+(?:\.\d+)? sec\s*$"
)
CT_TIME = re.compile(r"Total Test time \(real\) =\s+\d+(?:\.\d+)? sec\Z")
PY_PROGRESS = re.compile(r"\.+\s+\[100%\]\Z")
CT_CHANGING = re.compile(r"Internal ctest changing into directory: (?P<path>/[^\x00\r\n]+)\Z")
CT_PROJECT = re.compile(r"Test project (?P<path>/[^\x00\r\n]+)\Z")
CT_START = re.compile(r"Start (?P<test_id>\d+): (?P<name>\S+)\Z")
ENVIRONMENT_TEXT = re.compile(
    r"(errors? while running|error collecting|importerror|modulenotfounderror|"
    r"internalerror|traceback \(most recent call last\)|exception|fatal|no tests ran|"
    r"interrupted|usage: pytest|could not (?:find|load|open)|setup failed)",
    re.IGNORECASE,
)
FAILURE_TEXT = re.compile(r"\b(?:failed|failure|errors?)\b", re.IGNORECASE)


class Stage12697Error(ValueError):
    pass


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _stable(value: Any) -> str:
    return _sha(json.dumps(value, sort_keys=True, separators=(",", ":"),
                           ensure_ascii=True).encode("ascii"))


def _parts(selector: str) -> tuple[str, ...]:
    if (
        not isinstance(selector, str) or not selector or "\x00" in selector
        or "\\" in selector or selector.endswith("/") or "//" in selector
    ):
        raise Stage12697Error("path_selector_invalid")
    path = PurePosixPath(selector)
    if (
        path.is_absolute() or str(path) != selector or not path.parts
        or any(part in {"", ".", ".."} for part in path.parts)
    ):
        raise Stage12697Error("path_selector_noncanonical")
    return path.parts


def _read_fd(fd: int) -> bytes:
    chunks: list[bytes] = []
    total = 0
    while True:
        chunk = os.read(fd, min(1024 * 1024, MAX_FILE_BYTES - total + 1))
        if not chunk:
            return b"".join(chunks)
        total += len(chunk)
        if total > MAX_FILE_BYTES:
            raise Stage12697Error("source_file_too_large")
        chunks.append(chunk)


def _read_pinned(root: Path, selector: str, expected: str) -> bytes:
    parts = _parts(selector)
    opened: list[int] = []
    try:
        parent = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC)
        opened.append(parent)
        for part in parts[:-1]:
            parent = os.open(
                part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC,
                dir_fd=parent,
            )
            opened.append(parent)
        fd = os.open(parts[-1], os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC, dir_fd=parent)
        opened.append(fd)
        before = os.fstat(fd)
        if not stat.S_ISREG(before.st_mode):
            raise Stage12697Error("source_not_regular_file")
        data = _read_fd(fd)
        after = os.fstat(fd)
        current = os.stat(parts[-1], dir_fd=parent, follow_symlinks=False)
        identity = lambda value: (value.st_dev, value.st_ino, value.st_mode, value.st_size)
        if identity(before) != identity(after) or identity(after) != identity(current):
            raise Stage12697Error("source_identity_changed_during_read")
        if not re.fullmatch(r"[0-9a-f]{64}", expected) or _sha(data) != expected:
            raise Stage12697Error("source_digest_mismatch")
        return data
    except OSError as error:
        raise Stage12697Error("source_descriptor_open_failed") from error
    finally:
        for fd in reversed(opened):
            os.close(fd)


def _json_object(raw: bytes, reason: str) -> dict[str, Any]:
    try:
        value = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise Stage12697Error(reason) from error
    if not isinstance(value, dict):
        raise Stage12697Error(reason)
    return value


def _jsonl(raw: bytes) -> list[dict[str, Any]]:
    rows = []
    for number, line in enumerate(raw.splitlines(keepends=True), 1):
        if not line.strip() or not line.endswith(b"\n"):
            raise Stage12697Error(f"jsonl_member_noncanonical:{number}")
        row = _json_object(line, "jsonl_member_invalid")
        row["__stage12697_member_sha256"] = _sha(line)
        row["__stage12697_line_number"] = number
        row["__stage12697_raw_bytes"] = bytes(line)
        rows.append(row)
    return rows



def _clean_source_record(record: Mapping[str, Any]) -> dict[str, Any]:
    return {
        key: value for key, value in record.items()
        if not key.startswith("__stage12697_")
    }


def _source_raw_bytes(record: Mapping[str, Any]) -> bytes:
    raw = record.get("__stage12697_raw_bytes")
    if not isinstance(raw, bytes) or json.loads(raw) != _clean_source_record(record):
        raise Stage12697Error("materialization_raw_record_binding_mismatch")
    return raw


def _load_manifest(root: Path) -> tuple[dict[str, Any], dict[str, bytes]]:
    raw_manifest = _read_pinned(root, CONFIG_PATH, REVIEWED_CONFIG_SHA256)
    manifest = _json_object(raw_manifest, "config_manifest_invalid")
    if manifest.get("schema_version") != 1 or manifest.get("stage") != 12697:
        raise Stage12697Error("config_manifest_schema_invalid")
    boundary = manifest.get("claim_boundary")
    if (
        not isinstance(boundary, Mapping)
        or boundary.get("external_cryptographic_authentication") is not False
        or not isinstance(boundary.get("residual_trust"), list)
    ):
        raise Stage12697Error("config_trust_boundary_invalid")
    sources = manifest.get("sources")
    if not isinstance(sources, Mapping) or not sources:
        raise Stage12697Error("config_sources_invalid")
    raw_sources: dict[str, bytes] = {}
    seen_paths = set()
    for name in sorted(sources):
        entry = sources[name]
        if not isinstance(entry, Mapping) or set(entry) != {"path", "sha256"}:
            raise Stage12697Error("config_source_entry_invalid")
        path, digest = entry["path"], entry["sha256"]
        if path in seen_paths:
            raise Stage12697Error("config_source_path_duplicate")
        seen_paths.add(path)
        raw_sources[name] = _read_pinned(root, path, digest)
    interface = manifest.get("stage12696_interface")
    if not isinstance(interface, Mapping) or set(interface) != {"path", "sha256"}:
        raise Stage12697Error("stage12696_interface_config_invalid")
    dependencies = manifest.get("implementation_dependencies")
    expected_dependencies = {
        "stage12687", "stage12688", "stage12690", "stage12692", "stage12693",
    }
    if not isinstance(dependencies, Mapping) or set(dependencies) != expected_dependencies:
        raise Stage12697Error("implementation_dependency_config_invalid")
    for name in sorted(dependencies):
        entry = dependencies[name]
        if not isinstance(entry, Mapping) or set(entry) != {"path", "sha256"}:
            raise Stage12697Error("implementation_dependency_config_invalid")
        _read_pinned(root, entry["path"], entry["sha256"])
    return manifest, raw_sources


def _load_stage12696(root: Path, manifest: Mapping[str, Any]):
    interface = manifest["stage12696_interface"]
    raw = _read_pinned(root, interface["path"], interface["sha256"])
    path = root / interface["path"]
    spec = importlib.util.spec_from_file_location("stage12696_for_stage12697", path)
    if spec is None or spec.loader is None:
        raise Stage12697Error("stage12696_interface_import_unavailable")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    try:
        code = compile(raw, os.fspath(path), "exec", dont_inherit=True)
        exec(code, module.__dict__)
    except BaseException as error:
        sys.modules.pop(spec.name, None)
        raise Stage12697Error("stage12696_interface_import_failed") from error
    return module


def _command(argv: Any, text: Any) -> tuple[list[str], str]:
    if not isinstance(argv, list) or not argv or not all(isinstance(item, str) and item for item in argv):
        raise Stage12697Error("command_argv_invalid")
    if not isinstance(text, str) or not text or "\x00" in text:
        raise Stage12697Error("command_text_invalid")
    try:
        parsed = shlex.split(text, posix=True)
    except ValueError as error:
        raise Stage12697Error("command_text_shlex_invalid") from error
    if parsed != argv:
        raise Stage12697Error("command_argv_text_mismatch")
    return list(argv), shlex.join(argv)


def _strict_stderr(stderr: str) -> None:
    if not isinstance(stderr, str):
        raise Stage12697Error("stderr_invalid")
    if stderr:
        raise Stage12697Error("stderr_not_explicitly_benign")


def _strict_pytest(stdout: str) -> dict[str, Any]:
    lines = [line.strip() for line in stdout.splitlines() if line.strip()]
    if ENVIRONMENT_TEXT.search(stdout):
        raise Stage12697Error("pytest_environment_setup_text")
    if len(lines) != 2 or not PY_PROGRESS.fullmatch(lines[0]):
        raise Stage12697Error("pytest_output_grammar_invalid")
    summaries = [PY_SUMMARY.fullmatch(line) for line in lines if PY_SUMMARY.fullmatch(line)]
    if len(summaries) != 1 or not PY_SUMMARY.fullmatch(lines[-1]):
        raise Stage12697Error("pytest_terminal_summary_count_or_position_invalid")
    counts = {key: 0 for key in ("passed", "failed", "errors", "skipped", "xfailed", "xpassed")}
    seen = set()
    match = summaries[0]
    assert match
    for value, name in PY_COUNT.findall(match.group(1)):
        name = "errors" if name == "error" else name
        if name in seen:
            raise Stage12697Error("pytest_duplicate_summary_class")
        seen.add(name)
        counts[name] = int(value)
    if counts["passed"] <= 0 or any(counts[key] for key in counts if key != "passed"):
        raise Stage12697Error("pytest_not_strict_pass")
    return {"verifier_family": "pytest", "counts": counts}


def _strict_ctest(stdout: str) -> dict[str, Any]:
    lines = [line.strip() for line in stdout.splitlines() if line.strip()]
    if len(lines) != 6:
        raise Stage12697Error("ctest_output_grammar_invalid")
    changing = CT_CHANGING.fullmatch(lines[0])
    project = CT_PROJECT.fullmatch(lines[1])
    start = CT_START.fullmatch(lines[2])
    result = CT_RESULT.fullmatch(lines[3])
    summary = CT_SUMMARY.fullmatch(lines[4])
    if not all((changing, project, start, result, summary)) or not CT_TIME.fullmatch(lines[5]):
        raise Stage12697Error("ctest_output_grammar_invalid")
    assert changing and project and start and result and summary
    parsed_results = [result.groups()]
    percent, failed, total = map(int, summary.groups())
    ordinals = [int(item[0]) for item in parsed_results]
    ids = [int(item[2]) for item in parsed_results]
    names = [item[3] for item in parsed_results]
    statuses = [item[4] for item in parsed_results]
    if (
        total <= 0 or failed != 0 or percent != 100 or len(parsed_results) != total
        or ordinals != list(range(1, total + 1)) or len(set(ids)) != total
        or len(set(names)) != total or any(int(item[1]) != total for item in parsed_results)
        or any(status != "Passed" for status in statuses)
        or int(start.group("test_id")) != ids[0] or start.group("name") != names[0]
    ):
        raise Stage12697Error("ctest_not_strict_pass_or_identity_invalid")
    return {
        "verifier_family": "ctest",
        "counts": {"passed": total, "failed": 0, "errors": 0,
                   "skipped": 0, "xfailed": 0, "xpassed": 0},
        "test_names": names,
        "ctest_directory": changing.group("path"),
        "ctest_project": project.group("path"),
    }


def parse_strict_run(argv: Sequence[str], stdout: str, stderr: str) -> dict[str, Any]:
    if not isinstance(stdout, str):
        raise Stage12697Error("stdout_invalid")
    _strict_stderr(stderr)
    if len(stdout) >= SOURCE_STREAM_CAPTURE_LIMIT or len(stderr) >= SOURCE_STREAM_CAPTURE_LIMIT:
        raise Stage12697Error("source_stream_may_be_truncated")
    if argv[:3] == ["python", "-m", "pytest"]:
        if "--collect-only" in argv:
            raise Stage12697Error("pytest_collection_only_is_not_run")
        return _strict_pytest(stdout)
    if argv and argv[0] == "ctest":
        return _strict_ctest(stdout)
    raise Stage12697Error("verifier_family_unsupported")


def parse_pytest_collection(argv: Sequence[str], stdout: str, stderr: str) -> list[str]:
    _strict_stderr(stderr)
    _allowlist_pytest_collection_argv(argv)
    lines = [line.strip() for line in stdout.splitlines() if line.strip()]
    indexes = [index for index, line in enumerate(lines) if PY_COLLECTION.fullmatch(line)]
    if len(indexes) != 1 or indexes[0] != len(lines) - 1 or ENVIRONMENT_TEXT.search(stdout):
        raise Stage12697Error("pytest_collection_terminal_invalid")
    match = PY_COLLECTION.fullmatch(lines[-1])
    assert match
    nodes = lines[:-1]
    if int(match.group(1)) != len(nodes) or not nodes or len(set(nodes)) != len(nodes):
        raise Stage12697Error("pytest_collection_count_or_identity_invalid")
    for node in nodes:
        path, separator, test = node.partition("::")
        _parts(path)
        if not separator or not test or "::" in test or any(char.isspace() for char in test):
            raise Stage12697Error("pytest_collection_node_invalid")
    return nodes


def _allowlist_run_argv(argv: Sequence[str]) -> tuple[str, str, str | None]:
    if len(argv) == 5 and list(argv[:4]) == ["python", "-m", "pytest", "-q"]:
        selector = argv[4]
        _parts(selector)
        if not selector.endswith(".py"):
            raise Stage12697Error("pytest_run_path_not_python")
        return "pytest", selector, None
    if (
        len(argv) == 6 and argv[0] == "ctest" and argv[1] == "--test-dir"
        and argv[3] == "--output-on-failure" and argv[4] == "-R"
    ):
        _parts(argv[2])
        if not re.fullmatch(r"\^[A-Za-z0-9_.+\-]+\$", argv[5]):
            raise Stage12697Error("ctest_regex_not_exact_allowlisted")
        return "ctest", argv[2], argv[5]
    raise Stage12697Error("verifier_argv_not_allowlisted")


def _allowlist_pytest_collection_argv(argv: Sequence[str]) -> str:
    if len(argv) != 6 or list(argv[:5]) != [
        "python", "-m", "pytest", "--collect-only", "-q",
    ]:
        raise Stage12697Error("pytest_collection_argv_not_allowlisted")
    selector = argv[5]
    _parts(selector)
    if not selector.endswith(".py"):
        raise Stage12697Error("pytest_collection_path_not_python")
    return selector


def _open_absolute_directory(path: str) -> int:
    value = Path(path)
    if (
        not value.is_absolute() or value != Path(os.path.abspath(value))
        or any(part in {"", ".", ".."} for part in value.parts[1:])
    ):
        raise Stage12697Error("checkout_root_noncanonical")
    opened = []
    try:
        fd = os.open("/", os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC)
        opened.append(fd)
        for part in value.parts[1:]:
            fd = os.open(
                part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC,
                dir_fd=fd,
            )
            opened.append(fd)
        result = os.dup(fd)
    except OSError as error:
        raise Stage12697Error("checkout_root_descriptor_open_failed") from error
    finally:
        for fd in reversed(opened):
            os.close(fd)
    return result


def _resolve_selector(checkout: str, selector: str, *, directory: bool) -> None:
    parts = _parts(selector)
    opened: list[int] = []
    try:
        parent = _open_absolute_directory(checkout)
        opened.append(parent)
        for index, part in enumerate(parts):
            leaf = index == len(parts) - 1
            flags = os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC
            if not leaf or directory:
                flags |= os.O_DIRECTORY
            fd = os.open(part, flags, dir_fd=parent)
            opened.append(fd)
            info = os.fstat(fd)
            if leaf:
                expected = stat.S_ISDIR(info.st_mode) if directory else stat.S_ISREG(info.st_mode)
                if not expected:
                    raise Stage12697Error("checkout_selector_wrong_type")
            parent = fd
    except OSError as error:
        raise Stage12697Error("checkout_selector_resolution_failed") from error
    finally:
        for fd in reversed(opened):
            os.close(fd)


def _field_agreement(records: Sequence[Mapping[str, Any]]) -> None:
    exits = []
    timeouts = []
    for record in records:
        for key in ("process_exit_code", "session_exit_code", "exit_code"):
            if key in record:
                value = record[key]
                if isinstance(value, bool) or not isinstance(value, int):
                    raise Stage12697Error("exit_field_invalid")
                exits.append(value)
        if "timeout" in record:
            if not isinstance(record["timeout"], bool):
                raise Stage12697Error("timeout_field_invalid")
            timeouts.append(record["timeout"])
    if not exits or len(set(exits)) != 1 or exits[0] != 0:
        raise Stage12697Error("exit_fields_disagree_or_nonzero")
    if any(timeouts):
        raise Stage12697Error("timeout_fields_disagree_or_true")


def _closed(record: Mapping[str, Any]) -> None:
    for key in (
        "admissible_for_training", "training_allowed", "strict_eval_eligible",
        "source_heldout_admissible", "level3_admitted", "patch_trace_admitted",
        "repair_claim_admitted", "fail_to_pass_claim_admitted",
    ):
        if record.get(key) not in (None, False):
            raise Stage12697Error("source_authority_open")


def _read_shallow_boundary(repo: Any, expected_head: str) -> str:
    opened = []
    try:
        fd = os.open(
            "shallow", os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC,
            dir_fd=repo.git_fd,
        )
        opened.append(fd)
        before = os.fstat(fd)
        if (
            not stat.S_ISREG(before.st_mode) or before.st_nlink != 1
            or before.st_size > MAX_SHALLOW_FILE_BYTES
        ):
            raise Stage12697Error("shallow_boundary_not_bounded_regular_file")
        data = os.read(fd, MAX_SHALLOW_FILE_BYTES + 1)
        after = os.fstat(fd)
        current = os.stat("shallow", dir_fd=repo.git_fd, follow_symlinks=False)
        identity = lambda value: (value.st_dev, value.st_ino, value.st_mode, value.st_size)
        if identity(before) != identity(after) or identity(after) != identity(current):
            raise Stage12697Error("shallow_boundary_identity_changed")
    except OSError as error:
        raise Stage12697Error("shallow_boundary_descriptor_open_failed") from error
    finally:
        for fd in reversed(opened):
            os.close(fd)
    if len(data) > MAX_SHALLOW_FILE_BYTES or not data.endswith(b"\n") or b"\r" in data:
        raise Stage12697Error("shallow_boundary_noncanonical")
    try:
        lines = data.decode("ascii").splitlines()
    except UnicodeDecodeError as error:
        raise Stage12697Error("shallow_boundary_non_ascii") from error
    if lines != [expected_head]:
        raise Stage12697Error("shallow_boundary_not_exact_expected_head")
    return _sha(data)


def _head_only_snapshot(stage12696: Any, result: Mapping[str, Any], checkout: str) -> dict[str, Any]:
    revision = result.get("commit_sha")
    repo = result.get("repo_family")
    queue = result.get("queue_id")
    if not isinstance(revision, str) or not re.fullmatch(r"[0-9a-f]{40}", revision):
        raise Stage12697Error("snapshot_revision_invalid")
    checkout_path = Path(checkout)
    repository_root = checkout_path.parent
    repository_relative_path = checkout_path.name
    _parts(repository_relative_path)
    try:
        with stage12696.pin_repository_at_root(
            repository_root, repository_relative_path,
        ) as pinned:
            if pinned.head_oid != revision:
                raise Stage12697Error("snapshot_head_oid_mismatch")
            shallow_sha256 = _read_shallow_boundary(pinned, revision)
            commit_raw = stage12696.S93.read_verified_object(
                pinned, revision, "commit",
            )
            commit = stage12696.S93.parse_raw_commit(commit_raw, revision)
            tree_inventory = []
            blob_inventory = []
            gitlink_inventory = []
            pending = [(commit.tree_oid, "", 0)]
            placements = set()
            total_entries = 0
            total_blob_bytes = 0
            while pending:
                tree_oid, prefix, depth = pending.pop()
                if depth > MAX_SNAPSHOT_TREE_DEPTH:
                    raise Stage12697Error("snapshot_tree_depth_limit_exceeded")
                placement = (tree_oid, prefix)
                if placement in placements:
                    continue
                placements.add(placement)
                if len(placements) > MAX_SNAPSHOT_TREE_PLACEMENTS:
                    raise Stage12697Error("snapshot_tree_placement_limit_exceeded")
                tree_raw = stage12696.S93.read_verified_object(
                    pinned, tree_oid, "tree",
                )
                entries = stage12696.S93.parse_raw_tree(tree_raw, len(revision))
                tree_inventory.append([tree_oid, prefix, len(tree_raw), len(entries)])
                total_entries += len(entries)
                if total_entries > MAX_SNAPSHOT_ENTRIES:
                    raise Stage12697Error("snapshot_tree_entry_limit_exceeded")
                for entry in entries:
                    path = entry.path if not prefix else f"{prefix}/{entry.path}"
                    _parts(path)
                    if entry.object_type == "tree":
                        if entry.mode != "40000":
                            raise Stage12697Error("snapshot_tree_mode_mismatch")
                        pending.append((entry.oid, path, depth + 1))
                    elif entry.object_type == "blob":
                        if entry.mode not in {"100644", "100755", "120000"}:
                            raise Stage12697Error("snapshot_blob_mode_invalid")
                        blob_raw = stage12696.S93.read_verified_object(
                            pinned, entry.oid, "blob",
                        )
                        total_blob_bytes += len(blob_raw)
                        if len(blob_inventory) >= MAX_SNAPSHOT_BLOBS:
                            raise Stage12697Error("snapshot_blob_count_limit_exceeded")
                        if total_blob_bytes > MAX_SNAPSHOT_BLOB_BYTES:
                            raise Stage12697Error("snapshot_blob_byte_limit_exceeded")
                        blob_inventory.append([
                            entry.oid, path, entry.mode, len(blob_raw),
                        ])
                    elif entry.object_type == "commit":
                        if entry.mode != "160000" or not re.fullmatch(
                            r"(?:[0-9a-f]{40}|[0-9a-f]{64})", entry.oid,
                        ):
                            raise Stage12697Error("snapshot_gitlink_invalid")
                        gitlink_inventory.append([
                            entry.oid, path, entry.mode, None,
                        ])
                    else:
                        raise Stage12697Error("snapshot_entry_type_invalid")
    except Exception as error:
        if isinstance(error, Stage12697Error):
            raise
        raise Stage12697Error(
            "stage12696_head_snapshot_unavailable:" + str(error)
        ) from error
    evidence = {
        "snapshot_contract": "descriptor_pinned_exact_shallow_head_only_v1",
        "repository_identity_sha256": _sha(repo.encode()),
        "queue_id_sha256": _sha(queue.encode()),
        "revision": revision,
        "root_tree_oid": commit.tree_oid,
        "declared_parent_oids": list(commit.parent_oids),
        "parents_traversed": False,
        "shallow_boundary_sha256": shallow_sha256,
        "tree_inventory": sorted(tree_inventory),
        "blob_inventory": sorted(blob_inventory),
        "gitlink_inventory": sorted(gitlink_inventory),
        "tree_placements": len(tree_inventory),
        "blob_count": len(blob_inventory),
        "gitlink_count": len(gitlink_inventory),
        "total_entries": total_entries,
        "total_blob_bytes": total_blob_bytes,
    }
    evidence["snapshot_commitment_sha256"] = _stable([
        "stage12697_descriptor_pinned_shallow_head_snapshot_v1", evidence,
    ])
    return evidence


def _validate_join(
    candidate: Mapping[str, Any], result: Mapping[str, Any], smoke: Mapping[str, Any],
    report: Mapping[str, Any], report_path: str, commit_record: Mapping[str, Any],
    commit_path: str, collection: Mapping[str, Any] | None, collection_path: str | None,
    stage12696,
) -> dict[str, Any]:
    for record in (candidate, result, smoke):
        _closed(record)
    required_true = (
        "actual_verifier_command_output_observation_provenance",
        "hydratable_verifier_observation_candidate",
        "stage12534_constraint_preflight_passed", "source_lineage_checked",
    )
    if any(candidate.get(key) is not True for key in required_true):
        raise Stage12697Error("stage12537_guardrail_invalid")
    if candidate.get("controlled_fixture_like") is not False or candidate.get("generic_selected_test_collapsed") is not False:
        raise Stage12697Error("stage12537_guardrail_invalid")
    queue, repo, checkout = result.get("queue_id"), result.get("repo_family"), result.get("checkout_path")
    if not all(isinstance(value, str) and value for value in (queue, repo, checkout)):
        raise Stage12697Error("join_identity_missing")
    for record in (smoke, report, commit_record):
        if record.get("queue_id") != queue or record.get("repo_family") != repo:
            raise Stage12697Error("queue_repository_join_mismatch")
    if smoke.get("checkout_path") != checkout or report.get("cwd") != checkout or commit_record.get("cwd") != checkout:
        raise Stage12697Error("checkout_join_mismatch")
    if smoke.get("commit_sha") != result.get("commit_sha"):
        raise Stage12697Error("commit_join_mismatch")

    commit_argv, _ = _command(commit_record.get("command"), commit_record.get("command_text"))
    attempts = [item for item in smoke.get("commands_attempted", []) if isinstance(item, Mapping)
                and item.get("command") == ["git", "rev-parse", "HEAD"]]
    if len(attempts) == 1:
        _command(attempts[0].get("command"), attempts[0].get("command_text"))
    if (
        commit_argv != ["git", "rev-parse", "HEAD"] or len(attempts) != 1
        or attempts[0].get("log_path") != commit_path
        or commit_record.get("stdout_tail") != result.get("commit_sha") + "\n"
        or commit_record.get("stderr_tail") != ""
    ):
        raise Stage12697Error("commit_record_membership_invalid")

    argv, command_text = _command(report.get("command"), report.get("command_text"))
    _command(argv, result.get("command_attempted"))
    verifier_family, allowlisted_selector, allowlisted_pattern = _allowlist_run_argv(argv)
    if report.get("log_path") != report_path or result.get("command_log") != report_path:
        raise Stage12697Error("report_membership_invalid")
    if report.get("hydration_detected") is not False or result.get("selected_test_execution_succeeded") is not True:
        raise Stage12697Error("execution_observation_ineligible")
    parsed = parse_strict_run(argv, report.get("stdout_tail"), report.get("stderr_tail"))

    agreement_records = [candidate, result, smoke, report, commit_record, attempts[0]]
    selected = result.get("selected_test_ids")
    if not isinstance(selected, list) or not selected or not all(isinstance(item, str) and item for item in selected):
        raise Stage12697Error("selected_scope_invalid")
    if verifier_family == "ctest":
        if collection is not None:
            raise Stage12697Error("ctest_scope_command_invalid")
        test_dir = allowlisted_selector
        _resolve_selector(checkout, test_dir, directory=True)
        pattern = allowlisted_pattern
        if len(selected) != 1 or pattern != "^" + selected[0] + "$" or parsed.get("test_names") != selected:
            raise Stage12697Error("ctest_selected_scope_mismatch")
        expected_ctest_directory = checkout + "/" + test_dir
        if (
            parsed.get("ctest_directory") != expected_ctest_directory
            or parsed.get("ctest_project") != expected_ctest_directory
        ):
            raise Stage12697Error("ctest_report_directory_mismatch")
    else:
        files = [allowlisted_selector]
        if collection is None or collection_path is None:
            raise Stage12697Error("pytest_collection_evidence_missing")
        _resolve_selector(checkout, files[0], directory=False)
        collection_argv, _ = _command(collection.get("command"), collection.get("command_text"))
        collection_selector = _allowlist_pytest_collection_argv(collection_argv)
        if collection.get("log_path") != collection_path or collection.get("cwd") != checkout:
            raise Stage12697Error("pytest_collection_membership_mismatch")
        collected = parse_pytest_collection(
            collection_argv, collection.get("stdout_tail"), collection.get("stderr_tail")
        )
        if collection_selector != files[0] or selected != collected:
            raise Stage12697Error("pytest_selected_nodes_collection_mismatch")
        for node in selected:
            if node.partition("::")[0] != files[0]:
                raise Stage12697Error("pytest_selected_path_mismatch")
        agreement_records.append(collection)
    if sum(parsed["counts"].values()) != len(selected):
        raise Stage12697Error("selected_scope_outcome_count_mismatch")
    _field_agreement(agreement_records)

    stdout, stderr = report["stdout_tail"], report["stderr_tail"]
    if (
        candidate.get("verifier_exit_status_class") != "exit_zero"
        or candidate.get("target_semantic_value") != "PASS_CURRENT_STATE"
        or candidate.get("verifier_status") != "PASS_CURRENT_STATE"
        or candidate.get("verifier_stdout_hash") != _sha(stdout.encode())
        or candidate.get("verifier_stderr_hash") != _sha(stderr.encode())
    ):
        raise Stage12697Error("stage12537_observation_mismatch")

    snapshot = _head_only_snapshot(stage12696, result, checkout)
    target = dict(parsed)
    target.pop("test_names", None)
    target.update({"scope": "selected_tests_only", "process_exit_code": 0})
    package = {
        "record_type": "stage12697_reviewed_local_observed_verifier_join_package_v2",
        "candidate_ref_hash": candidate.get("candidate_ref_hash"),
        "queue_id": queue,
        "repository_identity_sha256": _sha(repo.encode()),
        "snapshot": snapshot,
        "reviewed_config_sha256": REVIEWED_CONFIG_SHA256,
        "stage12696_interface_sha256": stage12696.__stage12697_reviewed_sha256,
        "stage12687_implementation_sha256": stage12696.__stage12697_stage12687_sha256,
        "stage12688_implementation_sha256": stage12696.__stage12697_stage12688_sha256,
        "stage12690_implementation_sha256": stage12696.__stage12697_stage12690_sha256,
        "stage12692_implementation_sha256": stage12696.__stage12697_stage12692_sha256,
        "stage12693_implementation_sha256": stage12696.__stage12697_stage12693_sha256,
        "evidence": {
            "command": argv, "command_text": command_text,
            "selected_test_ids": list(selected), "scope": "selected_tests_only",
            "stdout": stdout, "stderr": stderr, "timeout": False,
        },
        "target": target,
        "source_membership": {
            "stage12537_member_sha256": candidate["__stage12697_member_sha256"],
            "stage12125_member_sha256": result["__stage12697_member_sha256"],
            "stage12123_member_sha256": smoke["__stage12697_member_sha256"],
            "report_sha256": report["__stage12697_file_sha256"],
            "commit_record_sha256": commit_record["__stage12697_file_sha256"],
        },
        "authentication_claim": "reviewed_local_digest_and_raw_git_recomputation_only",
        "external_cryptographic_authentication": False,
        "authority": dict(AUTHORITY),
    }
    if collection is not None:
        package["source_membership"]["collection_report_sha256"] = collection["__stage12697_file_sha256"]
    package["package_sha256"] = _stable(package)
    return package



def _build_materialization_input(
    package: Mapping[str, Any], candidate: Mapping[str, Any],
    result: Mapping[str, Any], report: Mapping[str, Any],
    commit_record: Mapping[str, Any], smoke: Mapping[str, Any],
) -> dict[str, Any]:
    records = {
        "stage12537": _clean_source_record(candidate),
        "result": _clean_source_record(result),
        "report": _clean_source_record(report),
        "commit": _clean_source_record(commit_record),
        "smoke": _clean_source_record(smoke),
    }
    raw_records = {
        "stage12537": _source_raw_bytes(candidate),
        "result": _source_raw_bytes(result),
        "report": _source_raw_bytes(report),
        "commit": _source_raw_bytes(commit_record),
        "smoke": _source_raw_bytes(smoke),
    }
    memberships = package["source_membership"]
    expected_hashes = {
        "stage12537": memberships["stage12537_member_sha256"],
        "result": memberships["stage12125_member_sha256"],
        "report": memberships["report_sha256"],
        "commit": memberships["commit_record_sha256"],
        "smoke": memberships["stage12123_member_sha256"],
    }
    raw_hashes = {key: _sha(value) for key, value in raw_records.items()}
    if raw_hashes != expected_hashes:
        raise Stage12697Error("materialization_source_membership_mismatch")
    join = {
        "queue_id": records["result"]["queue_id"],
        "repo_family": records["result"]["repo_family"],
        "checkout_path": records["result"]["checkout_path"],
        "commit_sha": records["result"]["commit_sha"],
        "command": list(package["evidence"]["command"]),
        "selected_test_ids": list(package["evidence"]["selected_test_ids"]),
        "report_sha256": raw_hashes["report"],
        "result_sha256": raw_hashes["result"],
        "stage12537_record_sha256": raw_hashes["stage12537"],
        "smoke_record_sha256": raw_hashes["smoke"],
        "commit_record_sha256": raw_hashes["commit"],
        "candidate_ref_hash": records["stage12537"]["candidate_ref_hash"],
        "process_exit_code": records["report"]["exit_code"],
        "session_exit_code": records["result"]["exit_code"],
        "timeout": False,
    }
    raw_join = (json.dumps(
        join, sort_keys=True, separators=(",", ":"), ensure_ascii=True,
    ) + "\n").encode("utf-8")
    records["join"] = join
    raw_records["join"] = raw_join
    raw_hashes["join"] = _sha(raw_join)
    commitment = _stable({
        "contract": "stage12697_stage12695_materialization_input_v1",
        "package_sha256": package["package_sha256"],
        "raw_record_sha256s": raw_hashes,
        "authority": AUTHORITY,
    })
    bundle = {
        "package_sha256": package["package_sha256"],
        "records": records,
        "raw_records": raw_records,
        "raw_record_sha256s": raw_hashes,
        "materialization_input_commitment_sha256": commitment,
        "authority": dict(AUTHORITY),
    }
    validate_materialization_input(bundle, package)
    return bundle


def validate_materialization_input(
    bundle: Mapping[str, Any], package: Mapping[str, Any],
) -> None:
    roles = {"stage12537", "result", "report", "commit", "smoke", "join"}
    if (
        set(bundle) != {
            "package_sha256", "records", "raw_records",
            "raw_record_sha256s",
            "materialization_input_commitment_sha256", "authority",
        }
        or bundle.get("package_sha256") != package.get("package_sha256")
        or bundle.get("authority") != AUTHORITY
        or set(bundle.get("records", {})) != roles
        or set(bundle.get("raw_records", {})) != roles
        or set(bundle.get("raw_record_sha256s", {})) != roles
    ):
        raise Stage12697Error("materialization_input_shape_invalid")
    records = bundle["records"]
    raws = bundle["raw_records"]
    hashes = bundle["raw_record_sha256s"]
    for role in sorted(roles):
        raw = raws[role]
        if (
            not isinstance(raw, bytes)
            or not isinstance(records[role], Mapping)
            or json.loads(raw) != records[role]
            or _sha(raw) != hashes[role]
        ):
            raise Stage12697Error("materialization_input_raw_binding_invalid")
    memberships = package["source_membership"]
    expected_source_hashes = {
        "stage12537": memberships["stage12537_member_sha256"],
        "result": memberships["stage12125_member_sha256"],
        "report": memberships["report_sha256"],
        "commit": memberships["commit_record_sha256"],
        "smoke": memberships["stage12123_member_sha256"],
    }
    if any(hashes[role] != digest for role, digest in expected_source_hashes.items()):
        raise Stage12697Error("materialization_input_membership_invalid")
    result = records["result"]
    report = records["report"]
    source = records["stage12537"]
    expected_join = {
        "queue_id": result["queue_id"],
        "repo_family": result["repo_family"],
        "checkout_path": result["checkout_path"],
        "commit_sha": result["commit_sha"],
        "command": list(package["evidence"]["command"]),
        "selected_test_ids": list(package["evidence"]["selected_test_ids"]),
        "report_sha256": hashes["report"],
        "result_sha256": hashes["result"],
        "stage12537_record_sha256": hashes["stage12537"],
        "smoke_record_sha256": hashes["smoke"],
        "commit_record_sha256": hashes["commit"],
        "candidate_ref_hash": source["candidate_ref_hash"],
        "process_exit_code": report["exit_code"],
        "session_exit_code": result["exit_code"],
        "timeout": False,
    }
    if records["join"] != expected_join:
        raise Stage12697Error("materialization_input_join_invalid")
    expected_commitment = _stable({
        "contract": "stage12697_stage12695_materialization_input_v1",
        "package_sha256": package["package_sha256"],
        "raw_record_sha256s": dict(hashes),
        "authority": AUTHORITY,
    })
    if bundle["materialization_input_commitment_sha256"] != expected_commitment:
        raise Stage12697Error("materialization_input_commitment_invalid")


def build_packages(root: Path = ROOT) -> dict[str, Any]:
    manifest, raw = _load_manifest(root)
    stage12696 = None
    stage12696_blocker = None
    try:
        stage12696 = _load_stage12696(root, manifest)
        stage12696.__stage12697_reviewed_sha256 = manifest["stage12696_interface"]["sha256"]
        stage12696.__stage12697_stage12687_sha256 = manifest["implementation_dependencies"]["stage12687"]["sha256"]
        stage12696.__stage12697_stage12688_sha256 = manifest["implementation_dependencies"]["stage12688"]["sha256"]
        stage12696.__stage12697_stage12690_sha256 = manifest["implementation_dependencies"]["stage12690"]["sha256"]
        stage12696.__stage12697_stage12692_sha256 = manifest["implementation_dependencies"]["stage12692"]["sha256"]
        stage12696.__stage12697_stage12693_sha256 = manifest["implementation_dependencies"]["stage12693"]["sha256"]
    except Stage12697Error as error:
        stage12696_blocker = "stage12696_reviewed_interface_unavailable:" + str(error)
    sources = manifest["sources"]
    rows12537 = _jsonl(raw["stage12537_rows"])
    rows12125 = _jsonl(raw["stage12125_results"])
    rows12123 = _jsonl(raw["stage12123_results"])
    objects_by_path: dict[str, dict[str, Any]] = {}
    for name, payload in raw.items():
        if name in {"stage12537_rows", "stage12125_results", "stage12123_results",
                    "stage12125_capture_implementation"}:
            continue
        record = _json_object(payload, f"source_json_invalid:{name}")
        record["__stage12697_file_sha256"] = sources[name]["sha256"]
        record["__stage12697_raw_bytes"] = bytes(payload)
        objects_by_path[sources[name]["path"]] = record

    reports = [record for path, record in objects_by_path.items()
               if "exact_selected_test_refinement/command_logs/" in path
               and record.get("label") in {"exact_selected_ctest", "pytest_run_refined"}]
    smoke_by_queue = {}
    for row in rows12123:
        smoke_by_queue.setdefault(row.get("queue_id"), []).append(row)
    result_by_report = {}
    for row in rows12125:
        result_by_report.setdefault(row.get("command_log"), []).append(row)

    packages = []
    materialization_inputs = []
    audit = []
    for candidate in rows12537:
        reasons = []
        matched_queue = None
        if candidate.get("source_stage") != "stage12125_exact_selected_test_refinement":
            reasons.append("source_stage_not_stage12125")
        matches = [
            report for report in reports
            if candidate.get("verifier_stdout_hash") == _sha(str(report.get("stdout_tail", "")).encode())
            and candidate.get("verifier_stderr_hash") == _sha(str(report.get("stderr_tail", "")).encode())
        ]
        if not matches:
            reasons.append("no_pinned_stage12125_report_stream_match")
        elif len(matches) != 1:
            reasons.append("ambiguous_pinned_stage12125_report_stream_match")
        if not reasons:
            report = matches[0]
            report_path = report.get("log_path")
            results = result_by_report.get(report_path, [])
            if len(results) != 1:
                reasons.append("result_membership_not_unique")
            else:
                result = results[0]
                matched_queue = result.get("queue_id")
                smokes = smoke_by_queue.get(matched_queue, [])
                if len(smokes) != 1:
                    reasons.append("smoke_membership_not_unique")
                else:
                    smoke = smokes[0]
                    commit_attempts = [
                        item for item in smoke.get("commands_attempted", [])
                        if isinstance(item, Mapping)
                        and item.get("command") == ["git", "rev-parse", "HEAD"]
                    ]
                    if len(commit_attempts) != 1:
                        reasons.append("commit_record_selector_not_unique")
                    else:
                        commit_path = commit_attempts[0].get("log_path")
                        commit_record = objects_by_path.get(commit_path)
                        if commit_record is None:
                            reasons.append("commit_record_not_pinned")
                        else:
                            collection_path = result.get("collect_command_log")
                            collection = objects_by_path.get(collection_path) if collection_path else None
                            try:
                                if stage12696 is None:
                                    raise Stage12697Error(stage12696_blocker)
                                package = _validate_join(
                                    candidate, result, smoke, report, report_path,
                                    commit_record, commit_path, collection, collection_path,
                                    stage12696,
                                )
                            except Stage12697Error as error:
                                reasons.append(str(error))
                            else:
                                packages.append(package)
                                materialization_inputs.append(
                                    _build_materialization_input(
                                        package, candidate, result, report,
                                        commit_record, smoke,
                                    )
                                )
        audit.append({
            "candidate_ref_hash": candidate.get("candidate_ref_hash"),
            "stage12537_member_sha256": candidate["__stage12697_member_sha256"],
            "matched_queue_id": matched_queue,
            "accepted": not reasons,
            "rejection_reasons": sorted(set(reasons)),
        })

    packages.sort(key=lambda row: (row["queue_id"], row["candidate_ref_hash"]))
    materialization_inputs.sort(key=lambda row: row["package_sha256"])
    audit.sort(key=lambda row: row["stage12537_member_sha256"])
    reason_counts = Counter(reason for row in audit for reason in row["rejection_reasons"])
    if len(audit) != len(rows12537) or len({row["stage12537_member_sha256"] for row in audit}) != len(audit):
        raise Stage12697Error("discovery_audit_not_exhaustive")
    if len({row["package_sha256"] for row in packages}) != len(packages):
        raise Stage12697Error("discovered_package_duplicate")
    if (
        len(materialization_inputs) != len(packages)
        or {row["package_sha256"] for row in materialization_inputs}
        != {row["package_sha256"] for row in packages}
        or len({row["materialization_input_commitment_sha256"]
                for row in materialization_inputs}) != len(materialization_inputs)
    ):
        raise Stage12697Error("materialization_input_reconciliation_failed")
    summary = {
        "stage": 12697,
        "record_type": "stage12697_nonpublishing_exhaustive_discovery_summary_v2",
        "reviewed_config_sha256": REVIEWED_CONFIG_SHA256,
        "stage12696_interface_sha256": manifest["stage12696_interface"]["sha256"],
        "stage12687_implementation_sha256": manifest["implementation_dependencies"]["stage12687"]["sha256"],
        "stage12688_implementation_sha256": manifest["implementation_dependencies"]["stage12688"]["sha256"],
        "stage12690_implementation_sha256": manifest["implementation_dependencies"]["stage12690"]["sha256"],
        "stage12692_implementation_sha256": manifest["implementation_dependencies"]["stage12692"]["sha256"],
        "stage12693_implementation_sha256": manifest["implementation_dependencies"]["stage12693"]["sha256"],
        "stage12696_dependency_available": stage12696 is not None,
        "stage12696_dependency_blocker": stage12696_blocker,
        "external_cryptographic_authentication": False,
        "residual_trust": list(manifest["claim_boundary"]["residual_trust"]),
        "stage12537_members_examined": len(rows12537),
        "stage12125_members_examined": len(rows12125),
        "stage12123_members_examined": len(rows12123),
        "discovered_join_package_count": len(packages),
        "rejected_stage12537_candidate_count": sum(not row["accepted"] for row in audit),
        "rejection_reason_counts": dict(sorted(reason_counts.items())),
        "discovery_audit": audit,
        "packages": packages,
        "materialization_inputs": materialization_inputs,
        "publication_performed": False,
        "verifier_execution_performed": False,
        "read_only_git_inspection_performed": True,
        "training_eligible_rows": 0,
        "authority": dict(AUTHORITY),
    }
    summary["capacity_commitment_sha256"] = _stable({
        "reviewed_config_sha256": REVIEWED_CONFIG_SHA256,
        "audit": audit,
        "packages": [row["package_sha256"] for row in packages],
        "authority": AUTHORITY,
    })
    return summary


def main() -> int:
    result = build_packages()
    public = {key: value for key, value in result.items()
              if key not in {"packages", "discovery_audit", "materialization_inputs"}}
    print(json.dumps(public, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
