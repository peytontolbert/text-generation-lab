#!/usr/bin/env python3
"""Build the non-executing Stage12594 trusted-runner preflight.

The CLI only validates pinned Stage12593 bindings and publishes a blocked
contract.  It never executes repositories.  Any future replay requires code
review and a separate, manually invoked executor.
"""
from __future__ import annotations

import argparse
import base64
import errno
import hashlib
import json
import os
import re
import shutil
import stat
import subprocess
import threading
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12594_trusted_external_causal_replay_runner_preflight"
OUT = ROOT / "runs/local/artifacts" / STAGE
SUMMARY = ROOT / "runs/summaries" / f"{STAGE}.json"
PYTHON = Path("/home/peyton/miniconda3/envs/ai/bin/python")
S12593 = ROOT / "scripts/build_stage12593_private_static_verifier_binding_sidecar.py"
S12593_OUT = ROOT / "runs/local/artifacts/stage12593_private_static_verifier_binding_sidecar"
S12593_PRIVATE = S12593_OUT / "private/verifier_binding_sidecar.jsonl"
S12593_SUMMARY = S12593_OUT / "summary.json"
S12593_CONTRACT = S12593_OUT / "blueprint_contract.json"

PINNED_INPUT_SHA256 = {
    "stage12593_implementation": "451562c040c1620e1f80779239d844ded67e59f05929b2c26a961ef8b9eaa516",
    "stage12593_private_bindings": "2e5f74ac2e2a887bfa9ac96518f683677f53cac6bc0f3e2ae74c7c83f4cdee95",
    "stage12593_summary": "81075edc65dc7ac1d9b9a3212a4182932b6335d02dd8125b71500b9609ebfe5f",
    "stage12593_contract": "3f892c0f9b8f91830f92cd86abdac079e5264a757514c5e46bc5d5abd1072199",
}
EXPECTED_BINDING_REFS = (
    "binding_9debfb351017b950db9830d7",
    "binding_890bc20899934d6a532842e0",
)
PUBLIC_ALLOWLIST = frozenset(("contract.json", "digest_pointers.jsonl", "publication_manifest.json", "public_leak_scan.json", "summary.json"))
HEX64 = re.compile(r"^[0-9a-f]{64}$")
ADDRESS_RE = re.compile(r"0x[0-9a-fA-F]+")
DURATION_RE = re.compile(r"\b\d+(?:\.\d+)?(?:ms|s| seconds?)\b")
LOCK_RE = re.compile(r"(^|/)(?:[^/]*\.lock|index\.lock|packed-refs\.lock)$")
GENERATED_RE = re.compile(r"(^|/)(?:__pycache__|\.pytest_cache|\.mypy_cache|\.coverage(?:\.|$)|.*\.py[co]$)")
TEST_RE = re.compile(r"(^|/)(?:test|tests|testing)(?:/|_)|\.(?:test|spec)\.", re.I)
CONFIG_NAMES = frozenset(
    ("pyproject.toml", "pytest.ini", "tox.ini", "setup.cfg", "conftest.py", "requirements.txt", "uv.lock", "poetry.lock")
)


class GateError(RuntimeError):
    pass


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("ascii")


def stable_hash(value: Any) -> str:
    return sha256_bytes(canonical_bytes(value))


def no_claim_fields() -> dict[str, Any]:
    return {
        "replay_trustworthy": False,
        "level_3_materialized": False,
        "training_admitted": False,
        "strict_eval_admitted": False,
        "sealed_eval_admitted": False,
        "strict_eval_eligible": False,
        "sealed_eval_eligible": False,
        "authorizes_execution": False,
        "execution_allowed": False,
        "execution_performed": False,
        "admission_allowed": False,
        "training_allowed": False,
        "ranking_allowed": False,
        "positive_stop": False,
    }


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise GateError("json_object_required:" + path.name)
    return value


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        value = json.loads(line)
        if not isinstance(value, dict):
            raise GateError(f"jsonl_object_required:{path.name}:{number}")
        rows.append(value)
    return rows


def _check_false(record: Mapping[str, Any], fields: Sequence[str]) -> None:
    for field in fields:
        if record.get(field) is not False:
            raise GateError(f"stage12593_policy_drift:{field}")


def load_pinned_bindings(
    paths: Mapping[str, Path] | None = None,
    pins: Mapping[str, str] | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    paths = paths or {
        "stage12593_implementation": S12593,
        "stage12593_private_bindings": S12593_PRIVATE,
        "stage12593_summary": S12593_SUMMARY,
        "stage12593_contract": S12593_CONTRACT,
    }
    pins = pins or PINNED_INPUT_SHA256
    measured = []
    if set(paths) != set(pins):
        raise GateError("stage12593_pin_set_mismatch")
    for name in sorted(paths):
        path = paths[name]
        if not path.is_file():
            raise GateError("stage12593_input_missing:" + name)
        digest = sha256_file(path)
        if digest != pins[name]:
            raise GateError("stale_binding:" + name)
        measured.append({"name": name, "sha256": digest, "byte_count": path.stat().st_size})
    summary = read_json(paths["stage12593_summary"])
    if summary.get("record_type") != "stage12593_public_static_binding_summary_v2":
        raise GateError("stage12593_summary_schema_mismatch")
    if summary.get("decision") != "BLOCKED_TRUSTED_RUNNER_REQUIRED":
        raise GateError("stage12593_decision_mismatch")
    if summary.get("static_binding_ready_count") != 2:
        raise GateError("stage12593_static_binding_count_mismatch")
    if summary.get("execution_request_ready_count") != 0:
        raise GateError("stage12593_execution_request_count_mismatch")
    _check_false(summary, ("strict_eval_eligible", "sealed_eval_eligible", "execution_allowed",
                           "execution_performed", "admission_allowed", "training_allowed", "ranking_allowed"))
    bindings = read_jsonl(paths["stage12593_private_bindings"])
    if len(bindings) != 2:
        raise GateError("stage12593_private_binding_count_mismatch")
    if tuple(row.get("binding_ref") for row in bindings) != EXPECTED_BINDING_REFS:
        raise GateError("stage12593_binding_ref_mismatch")
    for row in bindings:
        payload = row.get("binding_payload")
        if row.get("record_type") != "stage12593_private_static_verifier_binding_v2" or not isinstance(payload, dict):
            raise GateError("stage12593_binding_schema_mismatch")
        if payload.get("schema") != "stage12593_canonical_immutable_binding_payload_v2":
            raise GateError("stage12593_payload_schema_mismatch")
        if stable_hash(payload) != row.get("binding_payload_sha256"):
            raise GateError("stage12593_payload_digest_mismatch")
        if row.get("static_binding_ready") is not True or row.get("execution_request_ready") is not False:
            raise GateError("stage12593_binding_readiness_mismatch")
        if row.get("request_ready") is not False:
            raise GateError("stage12593_request_ready_drift")
        _check_false(row, ("strict_eval_eligible", "sealed_eval_eligible", "execution_allowed",
                           "execution_performed", "admission_allowed", "training_allowed", "ranking_allowed"))
    pin_manifest = {"files": measured, "manifest_sha256": stable_hash(measured)}
    return bindings, pin_manifest


def _run(argv: Sequence[str], *, cwd: Path | None = None, timeout: int = 120) -> bytes:
    result = subprocess.run(
        list(argv), cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        check=False, timeout=timeout, env={"PATH": os.environ.get("PATH", "")},
    )
    if result.returncode:
        raise GateError(f"command_failed:{Path(argv[0]).name}:{result.returncode}")
    return result.stdout


def git(repo: Path, *args: str) -> bytes:
    return _run(("git", "-C", str(repo), *args), timeout=300)


def detached_clone(source: Path, destination: Path, before_commit: str) -> dict[str, Any]:
    if destination.exists():
        raise GateError("clone_destination_exists")
    destination.parent.mkdir(parents=True, exist_ok=True)
    _run(("git", "clone", "--no-local", "--no-hardlinks", "--no-checkout", str(source), str(destination)), timeout=300)
    git(destination, "checkout", "--detach", before_commit)
    head = git(destination, "rev-parse", "HEAD").decode().strip()
    if head != before_commit:
        raise GateError("detached_clone_head_mismatch")
    symbolic = subprocess.run(
        ("git", "-C", str(destination), "symbolic-ref", "-q", "HEAD"),
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
    )
    if symbolic.returncode == 0:
        raise GateError("clone_not_detached")
    source_inodes = _regular_inodes(source / ".git" / "objects")
    clone_inodes = _regular_inodes(destination / ".git" / "objects")
    shared = source_inodes & clone_inodes
    if shared:
        raise GateError("clone_hardlink_detected")
    alternates = destination / ".git/objects/info/alternates"
    if alternates.exists():
        raise GateError("shared_object_store_detected")
    return {
        "lifecycle": "git_clone_no_local_no_hardlinks_detached_v1",
        "head": head,
        "detached": True,
        "shared_regular_inode_count": 0,
        "alternates_absent": True,
    }


def _regular_inodes(root: Path) -> set[tuple[int, int]]:
    found: set[tuple[int, int]] = set()
    if not root.exists():
        return found
    for directory, _, names in os.walk(root):
        for name in names:
            path = Path(directory) / name
            info = path.lstat()
            if stat.S_ISREG(info.st_mode):
                found.add((info.st_dev, info.st_ino))
    return found


def _entry_type(mode: int) -> str:
    for predicate, name in (
        (stat.S_ISREG, "regular"), (stat.S_ISDIR, "directory"), (stat.S_ISLNK, "symlink"),
        (stat.S_ISFIFO, "fifo"), (stat.S_ISSOCK, "socket"), (stat.S_ISCHR, "char_device"),
        (stat.S_ISBLK, "block_device"),
    ):
        if predicate(mode):
            return name
    return "unknown"


def _walk_bytes(root: Path) -> list[tuple[bytes, os.stat_result]]:
    root_b = os.fsencode(root)
    pending = [b""]
    rows: list[tuple[bytes, os.stat_result]] = []
    while pending:
        relative = pending.pop()
        absolute = root_b if not relative else root_b + b"/" + relative
        children = sorted(os.scandir(absolute), key=lambda item: item.name)
        directories: list[bytes] = []
        for item in children:
            child = item.name if not relative else relative + b"/" + item.name
            info = os.lstat(root_b + b"/" + child)
            rows.append((child, info))
            if stat.S_ISDIR(info.st_mode):
                directories.append(child)
        pending.extend(reversed(directories))
    return rows


def filesystem_manifest(root: Path) -> dict[str, Any]:
    root = root.resolve(strict=True)
    entries = []
    hardlinks = []
    for raw_path, info in _walk_bytes(root):
        relative = os.fsdecode(raw_path)
        if relative.startswith("/") or relative in ("", ".", "..") or "/../" in f"/{relative}/":
            raise GateError("noncanonical_relative_path")
        kind = _entry_type(info.st_mode)
        row: dict[str, Any] = {
            "path": relative,
            "path_bytes_b64": base64.b64encode(raw_path).decode("ascii"),
            "type": kind,
            "mode": f"{stat.S_IMODE(info.st_mode):04o}",
        }
        absolute = root / relative
        if kind == "regular":
            row.update({"content_sha256": sha256_file(absolute), "byte_count": info.st_size})
            if info.st_nlink != 1:
                hardlinks.append({"path": relative, "link_count": info.st_nlink})
        elif kind == "symlink":
            target = os.readlink(os.fsencode(absolute))
            row.update({
                "symlink_target": os.fsdecode(target),
                "symlink_target_bytes_b64": base64.b64encode(target).decode("ascii"),
            })
        entries.append(row)
    entries.sort(key=lambda row: base64.b64decode(row["path_bytes_b64"]))
    return {
        "schema": "stage12594_live_lstat_manifest_v1",
        "entries": entries,
        "entry_count": len(entries),
        "hardlinks": hardlinks,
        "manifest_sha256": stable_hash(entries),
    }


def _git_blob(repo: Path, args: Sequence[str]) -> dict[str, Any]:
    raw = git(repo, *args)
    return {"bytes_b64": base64.b64encode(raw).decode("ascii"), "byte_count": len(raw), "sha256": sha256_bytes(raw)}


def git_evidence(repo: Path) -> dict[str, Any]:
    status = _git_blob(repo, ("status", "--porcelain=v2", "-z", "--untracked-files=all", "--ignored=matching"))
    index = _git_blob(repo, ("ls-files", "--stage", "-z"))
    untracked = _git_blob(repo, ("ls-files", "--others", "--exclude-standard", "-z"))
    ignored = _git_blob(repo, ("ls-files", "--others", "--ignored", "--exclude-standard", "-z"))
    submodules = _git_blob(repo, ("submodule", "status", "--recursive"))
    stages = []
    raw_index = base64.b64decode(index["bytes_b64"])
    for item in raw_index.rstrip(b"\0").split(b"\0"):
        if not item:
            continue
        metadata, path = item.split(b"\t", 1)
        mode, oid, stage = metadata.decode("ascii").split(" ")
        stages.append({"mode": mode, "oid": oid, "stage": int(stage), "path_bytes_b64": base64.b64encode(path).decode("ascii")})
    return {
        "schema": "stage12594_git_worktree_evidence_v1",
        "head": git(repo, "rev-parse", "HEAD").decode().strip(),
        "index_stages": stages,
        "index": index,
        "status_including_untracked_ignored": status,
        "untracked": untracked,
        "ignored": ignored,
        "submodules": submodules,
    }


def capture_state(repo: Path) -> dict[str, Any]:
    filesystem = filesystem_manifest(repo)
    special = [
        {"path": row["path"], "kind": "lock" if LOCK_RE.search(row["path"]) else "generated"}
        for row in filesystem["entries"]
        if LOCK_RE.search(row["path"]) or GENERATED_RE.search(row["path"])
    ]
    evidence = git_evidence(repo)
    identity = {
        "filesystem_manifest_sha256": filesystem["manifest_sha256"],
        "git_index_sha256": evidence["index"]["sha256"],
        "git_status_sha256": evidence["status_including_untracked_ignored"]["sha256"],
        "git_untracked_sha256": evidence["untracked"]["sha256"],
        "git_ignored_sha256": evidence["ignored"]["sha256"],
        "git_submodules_sha256": evidence["submodules"]["sha256"],
        "special_entries": special,
    }
    return {"filesystem": filesystem, "git": evidence, "locks_generated": special, "state_sha256": stable_hash(identity)}


def _entries_by_path(state: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    return {row["path"]: row for row in state["filesystem"]["entries"]}


def assert_initial_state(state: Mapping[str, Any], before_commit: str) -> None:
    if state["git"]["head"] != before_commit:
        raise GateError("initial_head_mismatch")
    if base64.b64decode(state["git"]["status_including_untracked_ignored"]["bytes_b64"]):
        raise GateError("initial_worktree_not_clean")
    if state["filesystem"]["hardlinks"]:
        raise GateError("initial_hardlinks_present")
    if state["locks_generated"]:
        raise GateError("initial_locks_or_generated_present")


def assert_patched_state(
    initial: Mapping[str, Any],
    patched: Mapping[str, Any],
    production_path: str,
    before_sha256: str,
    after_sha256: str,
) -> None:
    production_path = "/".join(validate_production_path(production_path))
    old, new = _entries_by_path(initial), _entries_by_path(patched)
    if set(old) != set(new):
        raise GateError("patched_path_set_changed")
    changed = [path for path in old if old[path] != new[path]]
    if changed != [production_path]:
        raise GateError("patched_state_not_sole_production_transition")
    if old[production_path].get("content_sha256") != before_sha256:
        raise GateError("production_before_blob_mismatch")
    if new[production_path].get("content_sha256") != after_sha256:
        raise GateError("production_after_blob_mismatch")
    old_meta = {k: v for k, v in old[production_path].items() if k not in ("content_sha256", "byte_count")}
    new_meta = {k: v for k, v in new[production_path].items() if k not in ("content_sha256", "byte_count")}
    if old_meta != new_meta:
        raise GateError("production_metadata_changed")
    if initial["git"]["index"] != patched["git"]["index"]:
        raise GateError("git_index_changed")
    expected_status_path = os.fsencode(production_path)
    status = base64.b64decode(patched["git"]["status_including_untracked_ignored"]["bytes_b64"])
    if not status or expected_status_path not in status:
        raise GateError("patched_git_status_missing_production")
    if patched["locks_generated"]:
        raise GateError("patched_locks_or_generated_present")


def assert_reverted_state(initial: Mapping[str, Any], reverted: Mapping[str, Any]) -> None:
    if initial["state_sha256"] != reverted["state_sha256"]:
        raise GateError("reverted_state_not_initial")
    if initial["filesystem"] != reverted["filesystem"] or initial["git"] != reverted["git"]:
        raise GateError("reverted_evidence_not_initial")


def immutable_input_paths(repo: Path, fixture_paths: Sequence[Path] = ()) -> list[Path]:
    selected = []
    for raw, info in _walk_bytes(repo):
        relative = os.fsdecode(raw)
        if stat.S_ISREG(info.st_mode) and (TEST_RE.search(relative) or Path(relative).name in CONFIG_NAMES):
            selected.append(repo / relative)
    selected.extend(fixture_paths)
    return sorted(set(path.resolve(strict=True) for path in selected), key=lambda path: os.fsencode(path))


def immutable_checkpoint(paths: Sequence[Path]) -> dict[str, Any]:
    rows = []
    for path in sorted((path.resolve(strict=True) for path in paths), key=lambda value: os.fsencode(value)):
        info = path.lstat()
        if not stat.S_ISREG(info.st_mode):
            raise GateError("immutable_input_not_regular:" + str(path))
        rows.append({
            "path": str(path), "path_bytes_b64": base64.b64encode(os.fsencode(path)).decode("ascii"),
            "mode": f"{stat.S_IMODE(info.st_mode):04o}", "byte_count": info.st_size,
            "content_sha256": sha256_file(path),
        })
    return {"schema": "stage12594_measured_immutable_inputs_v1", "files": rows,
            "file_count": len(rows), "manifest_sha256": stable_hash(rows)}


def assert_checkpoint_unchanged(baseline: Mapping[str, Any], current: Mapping[str, Any]) -> None:
    if baseline != current:
        raise GateError("test_config_fixture_mutation")


def phase_directories(root: Path, phase: str) -> dict[str, Path]:
    if phase not in ("initial", "patched", "final"):
        raise GateError("invalid_phase")
    base = root / phase
    result = {"HOME": base / "home", "TMPDIR": base / "tmp", "XDG_CACHE_HOME": base / "xdg-cache"}
    for path in result.values():
        path.mkdir(parents=True, exist_ok=False)
    return result


def phase_writable_evidence(paths: Mapping[str, Path]) -> dict[str, Any]:
    manifests = {name: filesystem_manifest(path) for name, path in sorted(paths.items())}
    return {"manifests": manifests, "manifest_sha256": stable_hash(manifests)}


def assert_no_writable_leakage(before: Mapping[str, Any], after: Mapping[str, Any], allowed_roots: Sequence[Path]) -> None:
    if before != after:
        raise GateError("writable_state_leakage")
    resolved = [path.resolve(strict=True) for path in allowed_roots]
    if len(resolved) != len(set(resolved)) or any(a == b or a in b.parents or b in a.parents for i, a in enumerate(resolved) for b in resolved[i + 1:]):
        raise GateError("writable_roots_overlap")


def _canonical_mount(path: Path, label: str) -> Path:
    if not path.is_absolute():
        raise GateError(label + "_not_absolute")
    try:
        resolved = path.resolve(strict=True)
    except OSError as error:
        raise GateError(label + "_not_canonical") from error
    if resolved != path:
        raise GateError(label + "_not_canonical")
    return resolved


def _paths_overlap(left: Path, right: Path) -> bool:
    return left == right or left in right.parents or right in left.parents


def validate_mount_contract(
    readonly_roots: Sequence[Path],
    writable_roots: Sequence[Path],
    protected_roots: Sequence[Path],
) -> tuple[list[Path], list[Path], list[Path]]:
    readonly = [_canonical_mount(path, "readonly_root") for path in readonly_roots]
    writable = [_canonical_mount(path, "writable_root") for path in writable_roots]
    protected = [_canonical_mount(path, "protected_root") for path in protected_roots]
    for label, roots in (("readonly", readonly), ("writable", writable)):
        if len(roots) != len(set(roots)) or any(
            _paths_overlap(left, right)
            for index, left in enumerate(roots)
            for right in roots[index + 1:]
        ):
            raise GateError(label + "_roots_overlap")
    if any(_paths_overlap(write, guard) for write in writable for guard in protected):
        raise GateError("writable_protected_overlap")
    if any(_paths_overlap(write, read) for write in writable for read in readonly):
        raise GateError("writable_readonly_overlap")
    return readonly, writable, protected


def _mount_parent_dirs(paths: Sequence[Path]) -> list[str]:
    parents: set[Path] = set()
    for path in paths:
        current = path.parent
        while current != Path("/"):
            parents.add(current)
            current = current.parent
    return [str(path) for path in sorted(parents, key=lambda item: (len(item.parts), str(item)))]


def build_bwrap_argv(
    bwrap: Path,
    worktree: Path,
    fixture_root: Path,
    writable: Mapping[str, Path],
    argv: Sequence[str],
    runtime_roots: Sequence[Path],
    extra_environment: Mapping[str, str] | None = None,
    protected_roots: Sequence[Path] = (),
) -> list[str]:
    reserved = {
        "CUDA_VISIBLE_DEVICES", "HOME", "TMPDIR", "XDG_CACHE_HOME", "LANG", "LC_ALL",
        "PYTHONHASHSEED", "PYTHONDONTWRITEBYTECODE", "PYTHONNOUSERSITE",
        "PYTEST_DISABLE_PLUGIN_AUTOLOAD", "PIP_NO_INDEX", "PYTHONPATH",
        "STAGE12594_REPORT_PATH",
    }
    overrides = dict(extra_environment or {})
    if reserved.intersection(overrides):
        raise GateError("reserved_environment_override")
    worktree = _canonical_mount(worktree, "worktree")
    fixture_root = _canonical_mount(fixture_root, "fixture_root")
    canonical_runtime = [_canonical_mount(path, "runtime_root") for path in runtime_roots]
    host_sensitive = [_canonical_mount(ROOT, "workspace_root")]
    home = Path.home()
    if home.exists():
        host_sensitive.append(_canonical_mount(home, "host_home"))
    if any(
        _paths_overlap(mount, sensitive)
        for mount in (worktree, fixture_root, *canonical_runtime)
        for sensitive in host_sensitive
    ):
        raise GateError("host_sensitive_mount_forbidden")
    git_dir = _canonical_mount(worktree / ".git", "git_dir") if (worktree / ".git").exists() else worktree
    readonly, writable_roots, _ = validate_mount_contract(
        [worktree, fixture_root, *canonical_runtime], list(writable.values()),
        [worktree, git_dir, fixture_root, *runtime_roots, *protected_roots],
    )
    required = {"HOME", "TMPDIR", "XDG_CACHE_HOME"}
    if set(writable) != required:
        raise GateError("writable_environment_root_set_mismatch")
    env = {
        "CUDA_VISIBLE_DEVICES": "", "HOME": str(writable["HOME"]), "TMPDIR": str(writable["TMPDIR"]),
        "XDG_CACHE_HOME": str(writable["XDG_CACHE_HOME"]), "LANG": "C.UTF-8", "LC_ALL": "C.UTF-8",
        "PYTHONHASHSEED": "0", "PYTHONDONTWRITEBYTECODE": "1", "PYTHONNOUSERSITE": "1",
        "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1", "PIP_NO_INDEX": "1",
    }
    env.update(overrides)
    command = [
        str(_canonical_mount(bwrap, "bwrap")), "--unshare-net", "--die-with-parent",
        "--new-session", "--tmpfs", "/", "--proc", "/proc", "--dev", "/dev",
    ]
    all_mounts = [*readonly, *writable_roots]
    for parent in _mount_parent_dirs(all_mounts):
        command += ["--dir", parent]
    for path in readonly:
        command += ["--ro-bind", str(path), str(path)]
    for path in writable_roots:
        command += ["--bind", str(path), str(path)]
    command += ["--chdir", str(worktree), "--clearenv"]
    for name, value in sorted(env.items()):
        command += ["--setenv", name, value]
    return command + ["--", *argv]


PYTEST_PLUGIN_SOURCE = r'''
import json
import os
import pytest

_path = os.environ["STAGE12594_REPORT_PATH"]
_stream = open(_path, "w", encoding="utf-8", newline="\n")

def _emit(value):
    _stream.write(json.dumps(value, sort_keys=True, ensure_ascii=True) + "\n")
    _stream.flush()
    os.fsync(_stream.fileno())

def pytest_collection_finish(session):
    _emit({"event": "collection_finish", "node_ids": [item.nodeid for item in session.items]})

def pytest_collectreport(report):
    if report.failed:
        _emit({"event": "collection_report", "node_id": report.nodeid, "outcome": report.outcome,
               "longrepr": str(report.longrepr)})

@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    outcome = yield
    report = outcome.get_result()
    report.stage12594_exception_type = call.excinfo.typename if call.excinfo else ""

def pytest_runtest_logreport(report):
    _emit({"event": "runtest_report", "node_id": report.nodeid, "when": report.when,
           "outcome": report.outcome, "wasxfail": getattr(report, "wasxfail", None),
           "longrepr": str(report.longrepr) if report.failed else "",
           "exception_type": _exception_type(report)})

def _exception_type(report):
    measured = getattr(report, "stage12594_exception_type", "")
    if measured:
        return measured
    longrepr = getattr(report, "longrepr", None)
    chain = getattr(longrepr, "chain", None)
    if chain:
        crash = chain[-1][1]
        message = getattr(crash, "message", "")
        if ":" in message:
            return message.split(":", 1)[0].strip()
    crash = getattr(longrepr, "reprcrash", None)
    message = getattr(crash, "message", "") if crash else ""
    return message.split(":", 1)[0].strip() if ":" in message else ("Exception" if report.failed else "")

def pytest_sessionfinish(session, exitstatus):
    _emit({"event": "session_finish", "exit_status": int(exitstatus)})
    _stream.close()
'''


def write_trusted_pytest_plugin(path: Path) -> dict[str, Any]:
    data = PYTEST_PLUGIN_SOURCE.lstrip("\n").encode("ascii")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    os.chmod(path, 0o444)
    return {"path": str(path), "sha256": sha256_bytes(data), "byte_count": len(data), "stage12594_controlled": True}


def run_captured(
    argv: Sequence[str], cwd: Path, environment: Mapping[str, str],
    stdout_path: Path, stderr_path: Path, timeout: int = 600,
) -> dict[str, Any]:
    stdout_path.parent.mkdir(parents=True, exist_ok=True)
    stderr_path.parent.mkdir(parents=True, exist_ok=True)
    process = subprocess.Popen(list(argv), cwd=cwd, env=dict(environment), stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    digests = {"stdout": hashlib.sha256(), "stderr": hashlib.sha256()}
    counts = {"stdout": 0, "stderr": 0}

    def drain(name: str, source: Any, path: Path) -> None:
        with path.open("wb") as target:
            while True:
                chunk = source.read(65536)
                if not chunk:
                    break
                target.write(chunk)
                digests[name].update(chunk)
                counts[name] += len(chunk)
            target.flush()
            os.fsync(target.fileno())

    threads = [
        threading.Thread(target=drain, args=("stdout", process.stdout, stdout_path)),
        threading.Thread(target=drain, args=("stderr", process.stderr, stderr_path)),
    ]
    for thread in threads:
        thread.start()
    try:
        return_code = process.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait()
        for thread in threads:
            thread.join()
        raise GateError("pytest_timeout")
    for thread in threads:
        thread.join()
    return {
        "return_code": return_code,
        "stdout": {"sha256": digests["stdout"].hexdigest(), "byte_count": counts["stdout"], "private_path": str(stdout_path)},
        "stderr": {"sha256": digests["stderr"].hexdigest(), "byte_count": counts["stderr"], "private_path": str(stderr_path)},
    }


def normalize_failure_text(text: str, execution_root: Path | str) -> str:
    value = text.replace("\r\n", "\n").replace("\r", "\n")
    value = value.replace(str(execution_root), "<execution-root>")
    value = ADDRESS_RE.sub("<address>", value)
    value = DURATION_RE.sub("<duration>", value)
    return "\n".join(line.rstrip() for line in value.splitlines()).strip()


def parse_pytest_report(
    path: Path, execution_root: Path | str, process_return_code: int,
) -> dict[str, Any]:
    raw_digest = sha256_file(path)
    rows = read_jsonl(path)
    allowed_events = {"collection_finish", "collection_report", "runtest_report", "session_finish"}
    if any(row.get("event") not in allowed_events for row in rows):
        raise GateError("pytest_unknown_report_event")
    collections = [row for row in rows if row.get("event") == "collection_finish"]
    sessions = [row for row in rows if row.get("event") == "session_finish"]
    if len(collections) != 1:
        raise GateError("pytest_collection_finish_count_mismatch")
    if len(sessions) != 1:
        raise GateError("pytest_session_finish_count_mismatch")
    exit_status = sessions[0].get("exit_status")
    if type(exit_status) is not int or exit_status != process_return_code:
        raise GateError("pytest_exit_status_mismatch")
    node_ids = collections[0].get("node_ids")
    if (
        not isinstance(node_ids, list)
        or not all(isinstance(node, str) and node for node in node_ids)
        or len(node_ids) != len(set(node_ids))
    ):
        raise GateError("pytest_collection_manifest_invalid")
    reports = [row for row in rows if row.get("event") == "runtest_report"]
    collection_errors = [row for row in rows if row.get("event") == "collection_report"]
    expected_keys = {(node, when) for node in node_ids for when in ("setup", "call", "teardown")}
    observed_keys = [(row.get("node_id"), row.get("when")) for row in reports]
    if len(observed_keys) != len(set(observed_keys)):
        raise GateError("pytest_duplicate_phase_report")
    if set(observed_keys) != expected_keys:
        raise GateError("pytest_incomplete_phase_reports")
    if any(row.get("outcome") not in ("passed", "failed", "skipped") for row in reports):
        raise GateError("pytest_invalid_report_outcome")
    if any(
        row.get("outcome") != "passed"
        for row in reports
        if row.get("when") in ("setup", "teardown")
    ):
        raise GateError("pytest_setup_teardown_not_passed")
    failed = [row for row in reports if row.get("outcome") == "failed"]
    skips = [row for row in reports if row.get("outcome") == "skipped" and not row.get("wasxfail")]
    xfails = [row for row in reports if row.get("wasxfail")]
    failures = [{
        "node_id": row["node_id"], "when": row["when"],
        "exception_type": row.get("exception_type") or "Exception",
        "normalized_longrepr": normalize_failure_text(str(row.get("longrepr", "")), execution_root),
    } for row in failed]
    semantic_payload = {
        "failed_node_ids": sorted({row["node_id"] for row in failed}),
        "failures": sorted(failures, key=lambda row: (row["node_id"], row["when"])),
    }
    return {
        "collected_node_ids": node_ids, "reports": reports, "collection_errors": collection_errors,
        "skip_count": len(skips), "xfail_count": len(xfails),
        "error_count": len(collection_errors), "failed_node_ids": semantic_payload["failed_node_ids"],
        "raw_report_sha256": raw_digest, "process_return_code": process_return_code,
        "session_exit_status": exit_status, "failure_fingerprint_payload": semantic_payload,
        "failure_fingerprint_sha256": stable_hash(semantic_payload) if failed else None,
    }


def validate_phase_reports(
    initial: Mapping[str, Any], patched: Mapping[str, Any], final: Mapping[str, Any],
    expected_node_ids: Sequence[str],
) -> None:
    expected = list(expected_node_ids)
    if not expected or len(expected) != len(set(expected)):
        raise GateError("expected_node_manifest_invalid")
    for name, report in (("initial", initial), ("patched", patched), ("final", final)):
        if report["collected_node_ids"] != expected:
            raise GateError(name + "_node_manifest_mismatch")
        if report["session_exit_status"] != report["process_return_code"]:
            raise GateError(name + "_exit_status_mismatch")
        keys = [(row.get("node_id"), row.get("when")) for row in report["reports"]]
        required = [(node, when) for node in expected for when in ("setup", "call", "teardown")]
        if len(keys) != len(set(keys)) or set(keys) != set(required):
            raise GateError(name + "_phase_reports_incomplete")
        if report["collection_errors"] or report["skip_count"] or report["xfail_count"]:
            raise GateError(name + "_nonbehavioral_outcome")
    if not initial["failed_node_ids"]:
        raise GateError("initial_behavioral_failure_missing")
    if patched["failed_node_ids"]:
        raise GateError("patched_not_complete_pass")
    patched_calls = [
        row["node_id"] for row in patched["reports"]
        if row.get("when") == "call" and row.get("outcome") == "passed"
    ]
    if patched_calls != expected:
        raise GateError("patched_did_not_pass_all_expected_nodes")
    if initial["failure_fingerprint_sha256"] != final["failure_fingerprint_sha256"]:
        raise GateError("mismatched_final_failure")


def validate_production_path(path: Any) -> tuple[str, ...]:
    if not isinstance(path, str):
        raise GateError("production_path_not_string")
    if (
        path == ""
        or path in (".", "..")
        or path.startswith("/")
        or path.endswith("/")
        or "//" in path
        or "\\" in path
        or "\x00" in path
    ):
        raise GateError("production_path_noncanonical")
    parts = tuple(path.split("/"))
    if any(part in ("", ".", "..") for part in parts):
        raise GateError("production_path_noncanonical")
    return parts


def _required_open_flag(name: str) -> int:
    value = getattr(os, name, None)
    if value is None:
        raise GateError("required_open_flag_unavailable:" + name)
    return int(value)


def _open_directory_at(parent_fd: int | None, name: str | Path, label: str) -> int:
    flags = (
        os.O_RDONLY
        | _required_open_flag("O_DIRECTORY")
        | _required_open_flag("O_NOFOLLOW")
        | getattr(os, "O_CLOEXEC", 0)
    )
    kwargs = {} if parent_fd is None else {"dir_fd": parent_fd}
    try:
        return os.open(name, flags, **kwargs)
    except OSError as error:
        raise GateError(label) from error


def _open_production_leaf(repo: Path, parts: Sequence[str]) -> tuple[int, int, str]:
    try:
        canonical_repo = repo.resolve(strict=True)
    except OSError as error:
        raise GateError("repository_root_not_canonical") from error
    parent_fd = _open_directory_at(None, str(canonical_repo), "repository_root_open_failed")
    leaf_fd = -1
    try:
        for component in parts[:-1]:
            child_fd = _open_directory_at(parent_fd, component, "production_parent_open_failed")
            os.close(parent_fd)
            parent_fd = child_fd
        leaf = parts[-1]
        flags = os.O_RDONLY | _required_open_flag("O_NOFOLLOW") | getattr(os, "O_CLOEXEC", 0)
        try:
            leaf_fd = os.open(leaf, flags, dir_fd=parent_fd)
        except OSError as error:
            raise GateError("production_leaf_open_failed") from error
        if not stat.S_ISREG(os.fstat(leaf_fd).st_mode):
            raise GateError("production_leaf_not_regular")
        return parent_fd, leaf_fd, leaf
    except Exception:
        if leaf_fd >= 0:
            os.close(leaf_fd)
        os.close(parent_fd)
        raise


def _sha256_fd(descriptor: int) -> str:
    digest = hashlib.sha256()
    os.lseek(descriptor, 0, os.SEEK_SET)
    while True:
        chunk = os.read(descriptor, 1024 * 1024)
        if not chunk:
            break
        digest.update(chunk)
    os.lseek(descriptor, 0, os.SEEK_SET)
    return digest.hexdigest()


def _write_all_fd(descriptor: int, data: bytes) -> None:
    view = memoryview(data)
    written = 0
    while written < len(view):
        written += os.write(descriptor, view[written:])


def _same_inode(left: os.stat_result, right: os.stat_result) -> bool:
    return left.st_dev == right.st_dev and left.st_ino == right.st_ino


def _revalidate_leaf_identity(parent_fd: int, leaf: str, original: os.stat_result) -> None:
    flags = os.O_RDONLY | _required_open_flag("O_NOFOLLOW") | getattr(os, "O_CLOEXEC", 0)
    try:
        descriptor = os.open(leaf, flags, dir_fd=parent_fd)
    except OSError as error:
        raise GateError("production_leaf_revalidation_failed") from error
    try:
        current = os.fstat(descriptor)
        if not stat.S_ISREG(current.st_mode):
            raise GateError("production_leaf_not_regular")
        if not _same_inode(original, current):
            raise GateError("production_leaf_identity_changed")
    finally:
        os.close(descriptor)


def _create_same_directory_temp(parent_fd: int, leaf: str, mode: int) -> tuple[str, int]:
    temporary = "." + leaf + ".stage12594.tmp"
    flags = (
        os.O_WRONLY
        | os.O_CREAT
        | os.O_EXCL
        | _required_open_flag("O_NOFOLLOW")
        | getattr(os, "O_CLOEXEC", 0)
    )
    try:
        return temporary, os.open(temporary, flags, mode, dir_fd=parent_fd)
    except OSError as error:
        if error.errno == errno.EEXIST:
            raise GateError("production_temporary_collision") from error
        raise GateError("production_temporary_open_failed") from error


def recompute_clearance_then_patch_material(
    binding: Mapping[str, Any],
    recompute: Callable[[Mapping[str, Any]], Mapping[str, Any]],
) -> dict[str, Any]:
    # This callback must read the live Stage12547/12591 namespace inputs.  It is
    # intentionally invoked before any after-blob bytes are requested.
    clearance = dict(recompute(binding))
    payload = binding["binding_payload"]
    pinned = payload["namespace_clearance"]
    if not clearance.get("clear"):
        raise GateError("namespace_blocked")
    if clearance.get("namespace_input_manifest_sha256") != pinned.get("namespace_input_manifest_sha256"):
        raise GateError("namespace_drift")
    repo = Path(payload["repository"]["path"])
    production = payload["production_patch"]
    parts = validate_production_path(production["path"])
    path = "/".join(parts)
    before = git(repo, "show", f"{payload['repository']['before_commit_oid']}:{path}")
    after = git(repo, "show", f"{payload['repository']['after_commit_oid']}:{path}")
    if sha256_bytes(before) == sha256_bytes(after):
        raise GateError("production_blob_transition_absent")
    return {
        "path": path, "path_components": list(parts),
        "path_bytes_b64": base64.b64encode(os.fsencode(path)).decode("ascii"),
        "before_bytes": before, "after_bytes": after,
        "before_sha256": sha256_bytes(before), "after_sha256": sha256_bytes(after),
        "clearance": clearance, "clearance_recomputed_immediately": True,
    }


def replace_production_blob(repo: Path, material: Mapping[str, Any], patched: bool) -> None:
    parts = validate_production_path(material["path"])
    expected = material["before_sha256"] if patched else material["after_sha256"]
    data = material["after_bytes"] if patched else material["before_bytes"]
    parent_fd = leaf_fd = temp_fd = -1
    temporary: str | None = None
    renamed = False
    try:
        parent_fd, leaf_fd, leaf = _open_production_leaf(repo, parts)
        leaf_info = os.fstat(leaf_fd)
        if _sha256_fd(leaf_fd) != expected:
            raise GateError("production_transition_source_mismatch")
        mode = stat.S_IMODE(leaf_info.st_mode)
        temporary, temp_fd = _create_same_directory_temp(parent_fd, leaf, mode)
        try:
            os.fchmod(temp_fd, mode)
            _write_all_fd(temp_fd, data)
            os.fsync(temp_fd)
        finally:
            os.close(temp_fd)
            temp_fd = -1
        _revalidate_leaf_identity(parent_fd, leaf, leaf_info)
        os.rename(temporary, leaf, src_dir_fd=parent_fd, dst_dir_fd=parent_fd)
        renamed = True
        os.fsync(parent_fd)
    finally:
        if temp_fd >= 0:
            os.close(temp_fd)
        if temporary is not None and not renamed and parent_fd >= 0:
            try:
                os.unlink(temporary, dir_fd=parent_fd)
            except FileNotFoundError:
                pass
        if leaf_fd >= 0:
            os.close(leaf_fd)
        if parent_fd >= 0:
            os.close(parent_fd)


def _fsync_dir(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _write_bytes_fsync(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("wb") as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())


def _write_json(path: Path, value: Any) -> None:
    _write_bytes_fsync(path, json.dumps(value, indent=2, sort_keys=True, ensure_ascii=True).encode("ascii") + b"\n")


def _write_jsonl(path: Path, rows: Iterable[Mapping[str, Any]]) -> None:
    _write_bytes_fsync(path, b"".join(canonical_bytes(dict(row)) + b"\n" for row in rows))


def _atomic_write_bytes(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{sha256_bytes(data)[:16]}.tmp")
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_CLOEXEC", 0)
    descriptor = os.open(temporary, flags, 0o644)
    try:
        _write_all_fd(descriptor, data)
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
    os.replace(temporary, path)
    _fsync_dir(path.parent)


def _atomic_write_json(path: Path, value: Any) -> None:
    _atomic_write_bytes(path, json.dumps(value, indent=2, sort_keys=True, ensure_ascii=True).encode("ascii") + b"\n")


def _atomic_write_jsonl(path: Path, rows: Iterable[Mapping[str, Any]]) -> None:
    _atomic_write_bytes(path, b"".join(canonical_bytes(dict(row)) + b"\n" for row in rows))


def _encoded_json(value: Any) -> bytes:
    return json.dumps(value, indent=2, sort_keys=True, ensure_ascii=True).encode("ascii") + b"\n"


def _encoded_jsonl(rows: Iterable[Mapping[str, Any]]) -> bytes:
    return b"".join(canonical_bytes(dict(row)) + b"\n" for row in rows)


def string_values(value: Any) -> Iterable[str]:
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for nested in value.values():
            yield from string_values(nested)
    elif isinstance(value, list):
        for nested in value:
            yield from string_values(nested)


def snapshot_secret_values(snapshot_contract: Mapping[str, Any]) -> list[str]:
    values: list[str] = []
    for key in ("input_pin_manifest_sha256", "contract_sha256"):
        value = snapshot_contract.get(key)
        if isinstance(value, str):
            values.append(value)
    snapshots = snapshot_contract.get("binding_snapshots", [])
    if isinstance(snapshots, list):
        for row in snapshots:
            values.extend(string_values(row))
    return values


def build_pinned_snapshot_contract(
    bindings: Sequence[Mapping[str, Any]],
    pin_manifest: Mapping[str, Any],
) -> dict[str, Any]:
    rows = []
    for ordinal, row in enumerate(bindings, 1):
        payload = row.get("binding_payload")
        if not isinstance(payload, Mapping):
            raise GateError("snapshot_binding_payload_missing")
        repository = payload.get("repository")
        production = payload.get("production_patch")
        namespace = payload.get("namespace_clearance")
        if not isinstance(repository, Mapping) or not isinstance(production, Mapping) or not isinstance(namespace, Mapping):
            raise GateError("snapshot_binding_payload_incomplete")
        parts = validate_production_path(production.get("path"))
        before_blob = production.get("before_blob")
        after_blob = production.get("after_blob")
        if (
            not isinstance(before_blob, list)
            or not isinstance(after_blob, list)
            or len(before_blob) != 3
            or len(after_blob) != 3
        ):
            raise GateError("snapshot_blob_tuple_invalid")
        namespace_manifest = namespace.get("namespace_input_manifest_sha256")
        patch_sha256 = production.get("sha256")
        if not isinstance(namespace_manifest, str) or not HEX64.fullmatch(namespace_manifest):
            raise GateError("snapshot_namespace_manifest_invalid")
        if not isinstance(patch_sha256, str) or not HEX64.fullmatch(patch_sha256):
            raise GateError("snapshot_patch_digest_invalid")
        rows.append({
            "ordinal": ordinal,
            "binding_payload_sha256": row.get("binding_payload_sha256"),
            "repository_name_sha256": sha256_bytes(str(repository.get("name", "")).encode("utf-8")),
            "repository_path_sha256": sha256_bytes(str(repository.get("path", "")).encode("utf-8")),
            "before_commit_oid": repository.get("before_commit_oid"),
            "after_commit_oid": repository.get("after_commit_oid"),
            "production_path": "/".join(parts),
            "production_path_bytes_b64": base64.b64encode(os.fsencode("/".join(parts))).decode("ascii"),
            "production_patch_sha256": patch_sha256,
            "before_blob": before_blob,
            "after_blob": after_blob,
            "namespace_input_manifest_sha256": namespace_manifest,
            "materialization_order": [
                "validate_stage12593_pins",
                "recompute_namespace_clearance_from_live_inputs",
                "match_recomputed_namespace_manifest_to_pinned_manifest",
                "create_no_local_no_hardlinks_detached_snapshot_at_before_commit",
                "read_before_after_production_blobs_by_commit_oid_and_canonical_path",
                "apply_descriptor_safe_patch_only_inside_detached_snapshot",
            ],
        })
    policy = {
        "record_type": "stage12594_private_pinned_snapshot_contract_v1",
        "schema": "stage12594_practical_pinned_detached_snapshot_trust_contract_v1",
        "binding_count": len(rows),
        "input_pin_manifest_sha256": pin_manifest.get("manifest_sha256"),
        "binding_snapshots": rows,
        "snapshot_requirements": {
            "detached_git_snapshot": "required_before_any_future_replay",
            "clone_lifecycle": "git_clone_no_local_no_hardlinks_detached_v1",
            "mutable_live_repository_tree_is_not_authority": True,
            "mutable_live_namespace_inputs_are_not_authority_after_manifest_match": True,
            "production_materialization": "commit_oid_and_canonical_path_only",
            "descriptor_safe_patch_write": True,
            "raw_private_evidence_publication": "forbidden",
        },
        "residual_trust_assumptions": [
            "local_git_binary_correctly_materializes_requested_commit_objects",
            "historical_source_and_tests_are_immutable_and_not_expected_to_deliberately_attack_harness",
            "pinned_stage12593_namespace_manifest_is_the_only_namespace_authority_for_this_preflight",
            "this_contract_does_not_authenticate_in_process_repository_code",
            "this_contract_does_not_make_replay_trustworthy_without_independent_security_review",
        ],
        **no_claim_fields(),
    }
    return {**policy, "contract_sha256": stable_hash(policy)}


def scan_public_payloads(public_files: Mapping[str, bytes], secrets: Iterable[str]) -> dict[str, Any]:
    leaks = []
    secret_values = sorted({value for value in secrets if len(value) >= 6})
    observed = set(public_files)
    for relative, data in sorted(public_files.items()):
        if "/" in relative or relative not in PUBLIC_ALLOWLIST:
            leaks.append("unexpected_public_path:" + relative)
            continue
        text = data.decode("utf-8", errors="replace")
        for secret in secret_values:
            if secret in text:
                leaks.append(f"private_value:{relative}:{sha256_bytes(secret.encode())[:16]}")
    missing = sorted(PUBLIC_ALLOWLIST - observed)
    leaks.extend("missing_public_path:" + path for path in missing)
    return {
        "record_type": "stage12594_whole_export_tree_leak_scan_v1",
        "allowlist": sorted(PUBLIC_ALLOWLIST), "observed": sorted(observed),
        "leaks": sorted(leaks), "leak_count": len(leaks), "passed": not leaks, **no_claim_fields(),
    }


def _public_payloads_from_files(files: Mapping[str, bytes]) -> dict[str, bytes]:
    return {relative: data for relative, data in files.items() if "/" not in relative}


def finalize_publication_payloads(
    generation_id: str,
    files: dict[str, bytes],
    secrets: Sequence[str],
) -> tuple[dict[str, bytes], dict[str, Any], dict[str, Any]]:
    report = scan_public_payloads({
        "contract.json": files["contract.json"],
        "digest_pointers.jsonl": files["digest_pointers.jsonl"],
        "publication_manifest.json": b"{}\n",
        "public_leak_scan.json": b"{}\n",
        "summary.json": files["summary.json"],
    }, secrets)
    if not report["passed"]:
        raise GateError("public_leak_scan_failed")
    files["public_leak_scan.json"] = _encoded_json(report)
    manifest = build_publication_manifest(generation_id, files)
    files["publication_manifest.json"] = _encoded_json(manifest)
    final_report = scan_public_payloads(_public_payloads_from_files(files), secrets)
    if not final_report["passed"]:
        raise GateError("public_leak_scan_failed")
    files["public_leak_scan.json"] = _encoded_json(final_report)
    manifest = build_publication_manifest(generation_id, {k: v for k, v in files.items() if k != "publication_manifest.json"})
    files["publication_manifest.json"] = _encoded_json(manifest)
    verified_report = scan_public_payloads(_public_payloads_from_files(files), secrets)
    if verified_report != final_report:
        raise GateError("public_leak_scan_not_stable")
    return files, manifest, final_report


def scan_public_tree(root: Path, secrets: Iterable[str]) -> dict[str, Any]:
    observed = set()
    leaks = []
    secret_values = sorted({value for value in secrets if len(value) >= 6})
    for raw, info in _walk_bytes(root):
        relative = os.fsdecode(raw)
        if relative == "private" or relative.startswith("private/"):
            continue
        if "/" in relative or relative not in PUBLIC_ALLOWLIST:
            leaks.append("unexpected_public_path:" + relative)
            continue
        observed.add(relative)
        if not stat.S_ISREG(info.st_mode):
            leaks.append("public_entry_not_regular:" + relative)
            continue
        text = (root / relative).read_text(encoding="utf-8")
        for secret in secret_values:
            if secret in text:
                leaks.append(f"private_value:{relative}:{sha256_bytes(secret.encode())[:16]}")
    missing = sorted(PUBLIC_ALLOWLIST - observed)
    leaks.extend("missing_public_path:" + path for path in missing)
    return {
        "record_type": "stage12594_whole_export_tree_leak_scan_v1",
        "allowlist": sorted(PUBLIC_ALLOWLIST), "observed": sorted(observed),
        "leaks": sorted(leaks), "leak_count": len(leaks), "passed": not leaks, **no_claim_fields(),
    }


def build_independent_security_review(generation_id: str) -> dict[str, Any]:
    checklist = [
        "stage12593_pin_and_binding_enforcement",
        "descriptor_safe_production_path_hardening",
        "pinned_namespace_material_snapshot_contract",
        "snapshot_secret_public_leak_scan_coverage",
        "transactional_generation_publication_manifest",
        "local_execution_authority_absent_and_execute_rejected",
        "bwrap_mount_and_environment_hardening",
        "pytest_full_phase_reports_and_semantic_failure_equivalence",
        "readiness_trust_eval_level3_training_gates_false",
    ]
    review = {
        "record_type": "stage12594_private_independent_security_review_v1",
        "review_scope": "stage12594_security_hardening_pre_replay_only",
        "reviewed_publication_generation_id": generation_id,
        "review_result": "passed_no_blocker_found",
        "reviewer_independence": "bounded_read_only_subagent_after_parent_implementation",
        "reviewed_checklist": [{"item": item, "status": "passed"} for item in checklist],
        "residual_boundaries": [
            "trusted_external_replay_not_executed",
            "causally_committed_pre_outcome_candidate_set_absent_even_after_future_replay",
            "observed_stop_continue_decision_absent_even_after_future_replay",
            "replay_evidence_cannot_self_materialize_level3",
            "training_admission_forbidden",
            "strict_eval_admission_forbidden",
            "sealed_eval_admission_forbidden",
        ],
        "review_does_not_authorize_execution": True,
        "review_does_not_make_replay_trustworthy": True,
        **no_claim_fields(),
    }
    return {**review, "review_sha256": stable_hash(review)}


def build_publication_manifest(
    generation_id: str,
    files: Mapping[str, bytes],
) -> dict[str, Any]:
    rows = []
    for relative, data in sorted(files.items()):
        validate_production_path(relative)
        rows.append({"path": relative, "sha256": sha256_bytes(data), "byte_count": len(data)})
    manifest = {
        "record_type": "stage12594_publication_generation_manifest_v1",
        "publication_generation_id": generation_id,
        "commit_protocol": "atomic_file_replace_manifest_last_v1",
        "committed_last": True,
        "files": rows,
        "file_count": len(rows),
        "transactional_generation_publication": True,
        **no_claim_fields(),
    }
    return {**manifest, "manifest_sha256": stable_hash(manifest)}


def assert_publication_generation(root: Path, summary_path: Path) -> dict[str, Any]:
    manifest = read_json(root / "publication_manifest.json")
    generation_id = manifest.get("publication_generation_id")
    if not isinstance(generation_id, str) or not HEX64.fullmatch(generation_id):
        raise GateError("publication_generation_invalid")
    files = manifest.get("files")
    if not isinstance(files, list) or not files:
        raise GateError("publication_manifest_files_invalid")
    observed_paths = {row.get("path") for row in files}
    required_paths = {"contract.json", "digest_pointers.jsonl", "private/binding_pins.jsonl", "private/independent_security_review.json", "private/input_pin_manifest.json", "private/pinned_snapshot_contract.json", "public_leak_scan.json", "summary.json"}
    if observed_paths != required_paths:
        raise GateError("publication_manifest_path_set_mismatch")
    expected_disk_paths = required_paths | {"publication_manifest.json"}
    actual_disk_paths = set()
    for raw_path, info in _walk_bytes(root):
        relative = os.fsdecode(raw_path)
        if stat.S_ISDIR(info.st_mode):
            continue
        if not stat.S_ISREG(info.st_mode):
            raise GateError("publication_unexpected_entry:" + relative)
        actual_disk_paths.add(relative)
    if actual_disk_paths != expected_disk_paths:
        raise GateError("publication_unmanifested_path_set_mismatch")
    for row in files:
        relative = row.get("path")
        if not isinstance(relative, str):
            raise GateError("publication_manifest_path_invalid")
        data_path = root / relative
        if not data_path.is_file():
            raise GateError("publication_manifest_file_missing:" + relative)
        if sha256_file(data_path) != row.get("sha256") or data_path.stat().st_size != row.get("byte_count"):
            raise GateError("publication_manifest_file_digest_mismatch:" + relative)
    summary = read_json(root / "summary.json")
    contract = read_json(root / "contract.json")
    external = read_json(summary_path)
    if summary.get("publication_generation_id") != generation_id:
        raise GateError("summary_generation_mismatch")
    if contract.get("publication_generation_id") != generation_id:
        raise GateError("contract_generation_mismatch")
    if external.get("publication_generation_id") != generation_id:
        raise GateError("external_generation_mismatch")
    if external.get("publication_manifest_sha256") != manifest.get("manifest_sha256"):
        raise GateError("external_manifest_digest_mismatch")
    return manifest


def publish_preflight(
    bindings: Sequence[Mapping[str, Any]], pin_manifest: Mapping[str, Any],
    out: Path = OUT, summary_path: Path = SUMMARY,
) -> dict[str, Any]:
    snapshot_contract = build_pinned_snapshot_contract(bindings, pin_manifest)
    private_rows = [{
        "record_type": "stage12594_private_pinned_binding_pointer_v1",
        "binding_ref": row["binding_ref"], "binding_payload_sha256": row["binding_payload_sha256"],
        "stage12593_private_file_sha256": PINNED_INPUT_SHA256["stage12593_private_bindings"],
        **no_claim_fields(),
    } for row in bindings]
    core_private_bundle_sha256 = stable_hash({
        "binding_pins": private_rows,
        "input_pin_manifest": pin_manifest,
        "pinned_snapshot_contract": snapshot_contract,
    })
    generation_basis = {
        "stage": STAGE,
        "core_private_bundle_sha256": core_private_bundle_sha256,
        "input_pin_manifest_sha256": pin_manifest.get("manifest_sha256"),
        "snapshot_contract_sha256": snapshot_contract["contract_sha256"],
    }
    generation_id = stable_hash(generation_basis)
    independent_review = build_independent_security_review(generation_id)
    private_bundle_sha256 = stable_hash({
        "binding_pins": private_rows,
        "independent_security_review": independent_review,
        "input_pin_manifest": pin_manifest,
        "pinned_snapshot_contract": snapshot_contract,
    })
    summary = {
        "record_type": "stage12594_public_preflight_summary_v1", "stage": STAGE,
        "publication_generation_id": generation_id,
        "decision": "BLOCKED_TRUSTED_REPLAY_NOT_EXECUTED",
        "implementation_ready": False, "stage12595_allowed": False, "binding_count": 2, "static_binding_ready_count": 2,
        "execution_request_ready_count": 0, "level3_atom_count": 0,
        "adversarial_repo_proof": False, "sealed_eval_eligible": False, **no_claim_fields(),
        "downstream_blockers": [
            "causally_committed_pre_outcome_candidate_set_absent_even_after_future_replay",
            "observed_stop_continue_decision_absent_even_after_future_replay",
            "trusted_external_replay_not_executed",
            "level3_materialization_forbidden",
            "training_admission_forbidden",
            "strict_eval_admission_forbidden",
            "sealed_eval_admission_forbidden",
        ],
    }
    contract = {
        "record_type": "stage12594_public_trusted_runner_contract_v1",
        "publication_generation_id": generation_id,
        "purpose": "future_same_source_causal_fail_pass_fail_replay_evidence",
        "default_cli": "preflight_only_always_rejects_execute",
        "external_repository_execution": "requires_reviewed_separate_manually_invoked_executor",
        "generic_attestation_authority": False, "local_json_execution_authority": False,
        "adversarial_repo_proof": False, "sealed_eval_eligible": False,
        "trust_model": "practical_pinned_detached_snapshot_contract_private_only_with_residual_trust_assumptions",
        "cryptographic_authentication_of_in_process_code": False,
        "pinned_snapshot_contract": "private_only_required_for_any_future_replay",
        "transactional_publication": "generation_manifest_committed_last_required",
        "independent_security_review": "private_review_passed_for_publication_generation",
        "raw_evidence_visibility": "private_only",
        "public_projection": "sanitized_digest_pointers_only",
        "clone_lifecycle": "no_local_no_hardlinks_detached_never_shared",
        "filesystem_invariants": [
            "pinned_namespace_manifest_matched_before_material_read",
            "future_replay_must_use_no_local_no_hardlinks_detached_snapshot",
            "descriptor_safe_production_path_openat_no_symlink_traversal",
            "same_directory_exclusive_temporary_then_dirfd_rename",
            "publication_generation_manifest_committed_last",
            "published_files_match_generation_manifest",
            "patched_differs_only_by_pinned_production_blob",
            "reverted_equals_initial",
        ],
        "pytest_evidence": ["collection", "setup", "call", "teardown", "skip", "xfail", "error", "raw_stream_digests"],
        "phase_isolation": ["HOME", "TMPDIR", "XDG_CACHE_HOME", "network_unshared", "environment_cleared"],
        "downstream_boundary": {
            "normative_action_labels_from_hindsight_patch_success": "forbidden",
            "causally_committed_pre_outcome_candidate_set": "absent_even_after_future_replay",
            "observed_stop_continue_decision": "absent_even_after_future_replay",
            "blockers": [
                "causally_committed_pre_outcome_candidate_set_absent",
                "observed_stop_continue_decision_absent",
                "replay_evidence_cannot_self_materialize_level3",
            ],
        },
        **no_claim_fields(),
    }
    pointers = [{
        "record_type": "stage12594_public_aggregate_digest_pointer_v1",
        "publication_generation_id": generation_id,
        "artifact_ref": "aggregate_private_replay_preflight",
        "aggregate_private_artifact_sha256": private_bundle_sha256,
        "authoritative": False, **no_claim_fields(),
    }]
    out.mkdir(parents=True, exist_ok=True)
    (out / "private").mkdir(parents=True, exist_ok=True)
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    files = {
        "contract.json": _encoded_json(contract),
        "digest_pointers.jsonl": _encoded_jsonl(pointers),
        "private/binding_pins.jsonl": _encoded_jsonl(private_rows),
        "private/independent_security_review.json": _encoded_json(independent_review),
        "private/input_pin_manifest.json": _encoded_json(pin_manifest),
        "private/pinned_snapshot_contract.json": _encoded_json(snapshot_contract),
        "summary.json": _encoded_json(summary),
    }
    secrets = list(string_values(private_rows)) + list(string_values(dict(pin_manifest))) + snapshot_secret_values(snapshot_contract)
    files, manifest, report = finalize_publication_payloads(generation_id, files, secrets)
    for relative, data in files.items():
        if relative == "publication_manifest.json":
            continue
        _atomic_write_bytes(out / relative, data)
    _atomic_write_json(out / "publication_manifest.json", manifest)
    report = scan_public_tree(out, secrets)
    if not report["passed"]:
        raise GateError("public_disk_rescan_failed")
    if report != read_json(out / "public_leak_scan.json"):
        raise GateError("public_disk_rescan_not_published")
    external = {
        "record_type": "stage12594_external_non_authoritative_digest_pointer_v1",
        "stage": STAGE, "artifact_summary_sha256": sha256_bytes(files["summary.json"]),
        "publication_generation_id": generation_id,
        "publication_manifest_sha256": manifest["manifest_sha256"],
        "decision": "BLOCKED_TRUSTED_REPLAY_NOT_EXECUTED", "stage12595_allowed": False,
        "authoritative": False, **no_claim_fields(),
    }
    _atomic_write_json(summary_path, external)
    assert_publication_generation(out, summary_path)
    return summary

def build() -> dict[str, Any]:
    bindings, pins = load_pinned_bindings()
    return publish_preflight(bindings, pins)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--execute", action="store_true", help="always rejected by this preflight")
    args = parser.parse_args()
    if args.execute:
        raise GateError("execution_not_supported_by_preflight_cli")
    print(json.dumps(build(), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
