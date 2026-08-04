#!/usr/bin/env python3
"""Materialize one pinned Biome fail-to-pass replay as raw-private evidence only."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shlex
import shutil
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12584_biome_causal_replay"
OUT = ROOT / "runs/local/artifacts" / STAGE
SUMMARY = ROOT / "runs/summaries" / f"{STAGE}.json"
SOURCE_REPO = Path("/arxiv/repositories/biome")
BEFORE = "c1dfb4394ec06ba3aed5ff791681f984a33e3b08"
AFTER = "5f837df033afc34d43b398aeddc06c1d4fa491d9"
BEFORE_TREE = "2595adfff6f13b187067d470fea25d2b6705931b"
AFTER_TREE = "0b23ac186ab41bbade13390d0220e6444e73d41e"

TEST_PATHS = (
    "crates/biome_migrate/tests/specs/migrations/ruleMover/renamedRuleLastInGroup.json",
    "crates/biome_migrate/tests/specs/migrations/ruleMover/renamedRuleLastInGroup.json.snap",
)
PRODUCTION_PATHS = ("crates/biome_migrate/src/analyzers/rule_mover.rs",)
EXCLUDED_PATHS = (".changeset/fix-migrate-trailing-comma.md",)
EXPECTED_COMMIT_PATHS = tuple(sorted((*TEST_PATHS, *PRODUCTION_PATHS, *EXCLUDED_PATHS)))

TEST_PATCH_SHA256 = "51c59d6e8d1d6851e7e2c5c7e67e15430d9983e2473879bc4993f405d241ecc8"
PRODUCTION_PATCH_SHA256 = "3a8cc1bb9c0512b3a8e59b2372f3b1c0ae1f610c4c994d30173b7507b4164090"
SELECTED_DIFF_SHA256 = "ff1f3f5cf3a8f087afe5b1d6aa57dd2af164d654d80120eec4d37d4b941fce13"
EXCLUDED_DIFF_SHA256 = "541d585c768519bf861eb5dede9f41424607afe065d9ac5ba9f158fc20151fc3"
FULL_DIFF_SHA256 = "5dfeaf9ade01dc8a863a7a1caee746365e2a91dd29de2cbdb51e0cd20cb0852f"
SELECTED_DIFF_CHECK_SHA256 = "1b4049b63070c43b32c9f13ee251dcdbd3cb7dc7a50d10fd122ee90f52585ef6"
SELECTED_TEST_SHA256 = {
    TEST_PATHS[0]: "fc4aec487856f6cb1e06b4549fa4d3151b94d1d9aad133f46ac2bef87db2b23e",
    TEST_PATHS[1]: "01275b4ce64e27651b8dddabad48c155a2b3cca2dc1b1db9afe04af0a3cc5bb3",
}
CARGO_LOCK_SHA256 = "5e4c548d996a40f8ee3d15f874175c3b145f2ef54f29519edb86fd4f85baf909"

AI_PREFIX = Path("/home/peyton/miniconda3/envs/ai")
CARGO = Path("/home/peyton/.cargo/bin/cargo")
VERIFIER = ("cargo", "test", "-p", "biome_migrate")
EXPECTED_BEFORE = {"exit_code": 101, "passed": 32, "failed": 1}
EXPECTED_AFTER = {"exit_code": 0, "passed": 33, "failed": 0}
EXPECTED_TEST_BINARY = "tests/spec_tests.rs"
EXPECTED_TEST_NAME = "specs::migrations::rule_mover::renamed_rule_last_in_group_json"
EXPECTED_TEST_STATUS = {"before": "failed", "after": "ok"}
GENERATED_ROOT_FILES = ("raw_private_evidence.jsonl", "raw_private_candidate.jsonl")
GENERATED_PARTITION_FILES = ("test_setup.patch", "production_repair.patch")
TIMEOUT_SECONDS = 1800

ADMISSION_COUNTERS = {
    "admitted_file_count": 0,
    "training_admitted_record_count": 0,
    "strict_eval_admitted_record_count": 0,
    "source_heldout_admitted_record_count": 0,
}
FORBIDDEN_OUTPUT_KEYS = {"model_input", "candidate_actions", "admitted_episodes", "admitted_training_projections"}


class GateError(RuntimeError):
    pass


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def stable_hash(value: Any) -> str:
    return sha256_bytes(json.dumps(value, sort_keys=True, separators=(",", ":")).encode())


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def clear_generated_outputs(out: Path) -> None:
    out.mkdir(parents=True, exist_ok=True)
    for name in GENERATED_ROOT_FILES:
        path = out / name
        if path.is_symlink() or path.is_file():
            path.unlink()
        elif path.exists():
            raise GateError("generated_root_path_not_file:" + name)

    partitions = out / "partitions"
    if partitions.is_symlink():
        partitions.unlink()
        return
    if not partitions.exists():
        return
    if not partitions.is_dir():
        raise GateError("generated_partitions_not_directory")
    allowed = set(GENERATED_PARTITION_FILES)
    for child in partitions.iterdir():
        if child.name not in allowed:
            raise GateError("unexpected_generated_partition_entry:" + child.name)
        if child.is_symlink() or child.is_file():
            child.unlink()
        else:
            raise GateError("generated_partition_entry_not_file:" + child.name)
    partitions.rmdir()


def run(
    argv: list[str],
    *,
    cwd: Path | None = None,
    env: dict[str, str] | None = None,
    timeout: int = TIMEOUT_SECONDS,
) -> dict[str, Any]:
    started = time.monotonic()
    try:
        proc = subprocess.run(
            argv,
            cwd=cwd,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
            timeout=timeout,
        )
        code, stdout, stderr, timed_out = proc.returncode, proc.stdout, proc.stderr, False
    except subprocess.TimeoutExpired as exc:
        code = 124
        stdout, stderr, timed_out = exc.stdout or b"", exc.stderr or b"", True
    return {
        "argv": argv,
        "command": shlex.join(argv),
        "cwd": str(cwd) if cwd else None,
        "return_code": code,
        "timed_out": timed_out,
        "stdout": stdout.decode("utf-8", "replace")[-24000:],
        "stderr": stderr.decode("utf-8", "replace")[-24000:],
        "stdout_sha256": sha256_bytes(stdout),
        "stderr_sha256": sha256_bytes(stderr),
        "duration_seconds": round(time.monotonic() - started, 3),
    }


def require_ok(observation: dict[str, Any], blocker: str) -> None:
    if observation["return_code"] != 0 or observation["timed_out"]:
        raise GateError(blocker)


def git(repo: Path, *args: str, timeout: int = TIMEOUT_SECONDS) -> dict[str, Any]:
    return run(["git", "-C", str(repo), *args], timeout=timeout)


def git_stdout(repo: Path, *args: str) -> str:
    observation = git(repo, *args)
    require_ok(observation, "git_failed:" + " ".join(args))
    return observation["stdout"].strip()


def git_bytes(repo: Path, *args: str) -> bytes:
    proc = subprocess.run(
        ["git", "-C", str(repo), *args],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if proc.returncode:
        raise GateError("git_bytes_failed:" + " ".join(args))
    return proc.stdout


def diff_bytes(paths: tuple[str, ...] = ()) -> bytes:
    args = ["diff", "--binary", BEFORE, AFTER]
    if paths:
        args.extend(["--", *paths])
    result = git_bytes(SOURCE_REPO, *args)
    if not result:
        raise GateError("empty_pinned_diff:" + ",".join(paths))
    return result


def changed_paths(repo: Path) -> list[str]:
    tracked = git_stdout(repo, "diff", "--name-only", "HEAD").splitlines()
    untracked = git_stdout(repo, "ls-files", "--others", "--exclude-standard").splitlines()
    return sorted({path for path in (*tracked, *untracked) if path})


def worktree_state(repo: Path) -> dict[str, Any]:
    head = git_stdout(repo, "rev-parse", "HEAD")
    tree = git_stdout(repo, "rev-parse", "HEAD^{tree}")
    status = git_stdout(repo, "status", "--porcelain=v1", "--untracked-files=all")
    working_diff = git_bytes(repo, "diff", "--binary", "HEAD")
    paths = changed_paths(repo)
    body = {
        "head": head,
        "head_tree": tree,
        "status_porcelain": status,
        "changed_paths": paths,
        "clean": not status,
        "working_diff_sha256": sha256_bytes(working_diff),
        "working_diff_bytes": len(working_diff),
    }
    return {**body, "identity_sha256": stable_hash(body)}


def source_state() -> dict[str, Any]:
    state = worktree_state(SOURCE_REPO)
    state["repository"] = str(SOURCE_REPO)
    return state


def exact_diff(repo: Path, expected: bytes, expected_paths: tuple[str, ...], blocker: str) -> None:
    actual = git_bytes(repo, "diff", "--binary", "HEAD", "--", *expected_paths)
    if actual != expected:
        raise GateError(blocker)
    if changed_paths(repo) != sorted(expected_paths):
        raise GateError(blocker + "_path_residue")


def apply_indexed_patch(repo: Path, patch_path: Path, label: str) -> dict[str, Any]:
    check = git(repo, "apply", "--check", "--index", str(patch_path))
    require_ok(check, label + "_apply_check_failed")
    applied = git(repo, "apply", "--index", str(patch_path))
    require_ok(applied, label + "_apply_failed")
    output = (applied["stdout"] + applied["stderr"]).lower()
    if "offset" in output or "fuzz" in output:
        raise GateError(label + "_apply_not_exact")
    return {
        "check_stdout_sha256": check["stdout_sha256"],
        "check_stderr_sha256": check["stderr_sha256"],
        "apply_stdout_sha256": applied["stdout_sha256"],
        "apply_stderr_sha256": applied["stderr_sha256"],
        "zero_fuzz": True,
    }


def ai_environment(target_dir: Path) -> dict[str, str]:
    env = os.environ.copy()
    env.update(
        {
            "CONDA_PREFIX": str(AI_PREFIX),
            "CONDA_DEFAULT_ENV": "ai",
            "PATH": os.pathsep.join((str(AI_PREFIX / "bin"), str(CARGO.parent), env.get("PATH", ""))),
            "CUDA_VISIBLE_DEVICES": "",
            "CARGO_NET_OFFLINE": "true",
            "CARGO_TARGET_DIR": str(target_dir),
            "RUST_BACKTRACE": "0",
            "RUST_TEST_THREADS": "1",
        }
    )
    return env


def file_sha256(path: Path) -> str:
    if not path.is_file():
        raise GateError("required_file_missing:" + str(path))
    return sha256_bytes(path.read_bytes())


def selected_test_hashes(repo: Path) -> dict[str, str]:
    hashes = {path: file_sha256(repo / path) for path in TEST_PATHS}
    if hashes != SELECTED_TEST_SHA256:
        raise GateError("selected_test_hash_mismatch")
    return hashes


def verifier_identity(repo: Path, target_dir: Path) -> dict[str, Any]:
    env = ai_environment(target_dir)
    normalized = {
        "logical_command": " ".join(VERIFIER),
        "argv": [str(CARGO), *VERIFIER[1:]],
        "cwd": "<disposable_biome_worktree>",
        "conda_environment": "ai",
        "conda_prefix": str(AI_PREFIX),
        "cargo_executable": str(CARGO),
        "cargo_executable_sha256": file_sha256(CARGO),
        "cpu_only": True,
        "environment": {
            "CONDA_DEFAULT_ENV": env["CONDA_DEFAULT_ENV"],
            "CONDA_PREFIX": env["CONDA_PREFIX"],
            "CUDA_VISIBLE_DEVICES": env["CUDA_VISIBLE_DEVICES"],
            "CARGO_NET_OFFLINE": env["CARGO_NET_OFFLINE"],
            "CARGO_TARGET_DIR": "<disposable_target_dir>",
            "RUST_BACKTRACE": env["RUST_BACKTRACE"],
            "RUST_TEST_THREADS": env["RUST_TEST_THREADS"],
        },
        "selected_test_content_sha256": selected_test_hashes(repo),
    }
    return {"normalized": normalized, "identity_sha256": stable_hash(normalized)}


RESULT_RE = re.compile(
    r"test result: (ok|FAILED)\.\s+(\d+) passed;\s+(\d+) failed;[^\r\n]*",
    re.IGNORECASE,
)
RUNNING_SUITE_RE = re.compile(r"(?m)^running (\d+) tests?\s*$")
TEST_CASE_RE = re.compile(r"(?m)^test (\S+) \.\.\. (ok|FAILED|ignored)\s*$", re.IGNORECASE)
TEST_BINARY_RE = re.compile(
    r"(?m)^\s*Running (?:unittests )?(\S+\.rs) \(([^)\r\n]+)\)\s*$"
)
TEMP_ROOT_RE = re.compile(r"/data/tmp/stage12584_biome_causal_replay-[^/\s\"']+")
FINISHED_DURATION_RE = re.compile(r"finished in (?:\d+m\s+)?\d+(?:\.\d+)?s", re.IGNORECASE)
PANIC_THREAD_RE = re.compile(r"\(\d+\) panicked")


def normalize_volatile_text(value: str) -> str:
    value = TEMP_ROOT_RE.sub("<disposable>", value)
    value = FINISHED_DURATION_RE.sub("finished in <duration>", value)
    return PANIC_THREAD_RE.sub("(<thread-id>) panicked", value)


def parse_test_results(output: str) -> list[dict[str, Any]]:
    suite_headers = list(RUNNING_SUITE_RE.finditer(output))
    results = []
    previous_result_end = 0
    for index, match in enumerate(RESULT_RE.finditer(output)):
        candidates = [
            header
            for header in suite_headers
            if previous_result_end <= header.start() < match.start()
        ]
        if not candidates:
            raise GateError("cargo_test_suite_header_missing")
        header = candidates[-1]
        suite_output = output[header.start() : match.end()]
        test_cases = [
            {
                "name": test.group(1),
                "status": test.group(2).lower(),
                "test_line_sha256": sha256_bytes(test.group(0).encode("utf-8")),
            }
            for test in TEST_CASE_RE.finditer(suite_output)
        ]
        canonical_suite = {
            "suite_index": index,
            "declared_test_count": int(header.group(1)),
            "status": match.group(1).lower(),
            "passed": int(match.group(2)),
            "failed": int(match.group(3)),
            "test_cases": test_cases,
            "normalized_suite_output_sha256": sha256_bytes(
                normalize_volatile_text(suite_output).encode("utf-8")
            ),
        }
        results.append(
            {
                **canonical_suite,
                "result_line_sha256": sha256_bytes(match.group(0).encode("utf-8")),
                "canonical_result_sha256": stable_hash(canonical_suite),
            }
        )
        previous_result_end = match.end()
    if not results:
        raise GateError("cargo_test_results_missing")
    return results


def parse_test_binary_headers(stderr: str) -> list[dict[str, Any]]:
    headers = []
    for index, match in enumerate(TEST_BINARY_RE.finditer(stderr)):
        raw_header = match.group(0).strip()
        headers.append(
            {
                "binary_index": index,
                "source_path": match.group(1),
                "executable": match.group(2),
                "raw_header_sha256": sha256_bytes(raw_header.encode("utf-8")),
                "canonical_header_sha256": sha256_bytes(
                    normalize_volatile_text(raw_header).encode("utf-8")
                ),
            }
        )
    if not headers:
        raise GateError("cargo_test_binary_headers_missing")
    return headers


def canonical_observation(observation: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema": "stage12584_canonical_observation_v1",
        "return_code": observation["return_code"],
        "timed_out": observation["timed_out"],
        "logical_command": observation["logical_command"],
        "verifier_identity_sha256": observation["verifier_identity_sha256"],
        "suite_results": [
            {
                key: result[key]
                for key in (
                    "suite_index",
                    "declared_test_count",
                    "status",
                    "passed",
                    "failed",
                    "test_cases",
                    "normalized_suite_output_sha256",
                    "canonical_result_sha256",
                )
            }
            for result in observation["suite_results"]
        ],
        "test_binary_headers": [
            {
                "binary_index": header["binary_index"],
                "source_path": header["source_path"],
                "canonical_header_sha256": header["canonical_header_sha256"],
            }
            for header in observation["test_binary_headers"]
        ],
        "intended_suite_binding": observation["intended_suite_binding"],
    }


def run_verifier(repo: Path, target_dir: Path, identity: dict[str, Any]) -> dict[str, Any]:
    observation = run(
        [str(CARGO), *VERIFIER[1:]],
        cwd=repo,
        env=ai_environment(target_dir),
    )
    suite_results = parse_test_results(observation["stdout"])
    binary_headers = parse_test_binary_headers(observation["stderr"])
    return {
        **observation,
        "suite_results": suite_results,
        "suite_results_sha256": stable_hash(suite_results),
        "test_binary_headers": binary_headers,
        "test_binary_headers_sha256": stable_hash(binary_headers),
        "logical_command": " ".join(VERIFIER),
        "verifier_identity_sha256": identity["identity_sha256"],
    }


def validate_observation(observation: dict[str, Any], expected: dict[str, int], label: str) -> None:
    if observation["timed_out"] or observation["return_code"] != expected["exit_code"]:
        raise GateError(
            f"{label}_exit_mismatch:"
            f"{{'actual': {observation['return_code']}, 'expected': {expected['exit_code']}}}"
        )
    binary_matches = [
        header
        for header in observation["test_binary_headers"]
        if header["source_path"] == EXPECTED_TEST_BINARY
    ]
    if len(binary_matches) != 1:
        raise GateError(f"{label}_intended_test_binary_match_count:{len(binary_matches)}")

    expected_tuple = (expected["passed"], expected["failed"])
    tuple_matches = [
        result
        for result in observation["suite_results"]
        if (result["passed"], result["failed"]) == expected_tuple
    ]
    if not tuple_matches:
        raise GateError(f"{label}_expected_suite_tuple_absent:{expected_tuple}")
    if len(tuple_matches) != 1:
        raise GateError(f"{label}_expected_suite_tuple_ambiguous:{expected_tuple}")

    named_suite_matches = []
    for result in observation["suite_results"]:
        named = [case for case in result["test_cases"] if case["name"] == EXPECTED_TEST_NAME]
        if named:
            named_suite_matches.append((result, named))
    if len(named_suite_matches) != 1 or len(named_suite_matches[0][1]) != 1:
        raise GateError(f"{label}_named_test_evidence_match_count:{len(named_suite_matches)}")
    intended_suite, named_tests = named_suite_matches[0]
    named_test = named_tests[0]
    if intended_suite["suite_index"] != tuple_matches[0]["suite_index"]:
        raise GateError(f"{label}_expected_tuple_not_in_intended_suite")
    if intended_suite["declared_test_count"] != 33:
        raise GateError(f"{label}_intended_suite_declared_count_mismatch")
    expected_status = EXPECTED_TEST_STATUS[label]
    if named_test["status"] != expected_status:
        raise GateError(
            f"{label}_named_test_status_mismatch:{named_test['status']}:{expected_status}"
        )

    observation["expected_suite_tuple"] = list(expected_tuple)
    observation["expected_suite_match_index"] = intended_suite["suite_index"]
    observation["expected_suite_match_count"] = 1
    observation["intended_suite_binding"] = {
        "package": "biome_migrate",
        "test_binary_source_path": EXPECTED_TEST_BINARY,
        "test_binary_canonical_header_sha256": binary_matches[0]["canonical_header_sha256"],
        "suite_index": intended_suite["suite_index"],
        "declared_test_count": intended_suite["declared_test_count"],
        "suite_canonical_result_sha256": intended_suite["canonical_result_sha256"],
        "named_test": named_test,
    }
    canonical = canonical_observation(observation)
    observation["canonical_identity"] = canonical
    observation["canonical_identity_sha256"] = stable_hash(canonical)


def validate_pinned_source() -> dict[str, Any]:
    if not SOURCE_REPO.is_dir():
        raise GateError("source_repository_missing")
    if git_stdout(SOURCE_REPO, "rev-parse", f"{BEFORE}^{{commit}}") != BEFORE:
        raise GateError("before_commit_identity_mismatch")
    if git_stdout(SOURCE_REPO, "rev-parse", f"{AFTER}^{{commit}}") != AFTER:
        raise GateError("after_commit_identity_mismatch")
    if git_stdout(SOURCE_REPO, "rev-parse", f"{BEFORE}^{{tree}}") != BEFORE_TREE:
        raise GateError("before_tree_identity_mismatch")
    if git_stdout(SOURCE_REPO, "rev-parse", f"{AFTER}^{{tree}}") != AFTER_TREE:
        raise GateError("after_tree_identity_mismatch")
    if git_stdout(SOURCE_REPO, "rev-parse", f"{AFTER}^") != BEFORE:
        raise GateError("after_parent_is_not_before")
    paths = tuple(sorted(git_stdout(SOURCE_REPO, "diff", "--name-only", BEFORE, AFTER).splitlines()))
    if paths != EXPECTED_COMMIT_PATHS:
        raise GateError("commit_changed_path_set_mismatch")

    test_patch = diff_bytes(TEST_PATHS)
    production_patch = diff_bytes(PRODUCTION_PATHS)
    selected_diff = diff_bytes((*PRODUCTION_PATHS, *TEST_PATHS))
    excluded_diff = diff_bytes(EXCLUDED_PATHS)
    full_diff = diff_bytes()
    actual_hashes = {
        "test_patch_sha256": sha256_bytes(test_patch),
        "production_patch_sha256": sha256_bytes(production_patch),
        "selected_diff_sha256": sha256_bytes(selected_diff),
        "excluded_diff_sha256": sha256_bytes(excluded_diff),
        "full_diff_sha256": sha256_bytes(full_diff),
    }
    expected_hashes = {
        "test_patch_sha256": TEST_PATCH_SHA256,
        "production_patch_sha256": PRODUCTION_PATCH_SHA256,
        "selected_diff_sha256": SELECTED_DIFF_SHA256,
        "excluded_diff_sha256": EXCLUDED_DIFF_SHA256,
        "full_diff_sha256": FULL_DIFF_SHA256,
    }
    if actual_hashes != expected_hashes:
        raise GateError("pinned_diff_hash_mismatch")
    return {
        "commit_changed_paths": list(paths),
        "test_only_paths": list(TEST_PATHS),
        "production_only_paths": list(PRODUCTION_PATHS),
        "excluded_paths": list(EXCLUDED_PATHS),
        "path_overlap": [],
        "diff_hashes": actual_hashes,
        "test_patch": test_patch,
        "production_patch": production_patch,
        "selected_diff": selected_diff,
    }


def assert_no_forbidden_keys(value: Any, path: str = "$") -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            if str(key) in FORBIDDEN_OUTPUT_KEYS:
                raise GateError("forbidden_output_key:" + path + "." + str(key))
            assert_no_forbidden_keys(child, path + "." + str(key))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            assert_no_forbidden_keys(child, f"{path}[{index}]")


def canonical_evidence_identity(evidence: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema": "stage12584_canonical_evidence_identity_v1",
        "source": {
            key: evidence["source"][key]
            for key in ("repository", "before_commit", "after_commit", "before_tree", "after_tree")
        },
        "patch_split": evidence["patch_split"],
        "selected_test_content_sha256": evidence["selected_test_content_sha256"],
        "verifier_identity_sha256": evidence["verifier"]["identity_sha256"],
        "before_observation_identity_sha256": evidence["observations"]["before"][
            "canonical_identity_sha256"
        ],
        "after_observation_identity_sha256": evidence["observations"]["after"][
            "canonical_identity_sha256"
        ],
        "final_worktree_state_sha256": evidence["worktree_states"]["final"]["identity_sha256"],
        "final_diff_sha256": evidence["mutation_audit"]["final_diff_sha256"],
    }


def replay(out: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    source_before = source_state()
    disposable: Path | None = None
    diagnostics: dict[str, Any] = {"stage": STAGE, "status": "REJECTED", "gates_passed": []}
    try:
        pinned = validate_pinned_source()
        diagnostics["gates_passed"].append("source_commits_trees_paths_and_diff_hashes")
        partitions = out / "partitions"
        partitions.mkdir(parents=True, exist_ok=True)
        test_patch_path = partitions / "test_setup.patch"
        production_patch_path = partitions / "production_repair.patch"
        test_patch_path.write_bytes(pinned.pop("test_patch"))
        production_patch_path.write_bytes(pinned.pop("production_patch"))
        selected_diff = pinned.pop("selected_diff")

        disposable = Path(tempfile.mkdtemp(prefix=STAGE + "-", dir="/data/tmp"))
        repo, target_dir = disposable / "biome", disposable / "target"
        clone = run(
            ["git", "clone", "--shared", "--no-checkout", str(SOURCE_REPO), str(repo)],
            timeout=300,
        )
        require_ok(clone, "disposable_clone_failed")
        require_ok(git(repo, "checkout", "--detach", BEFORE), "baseline_checkout_failed")
        baseline = worktree_state(repo)
        if baseline["head"] != BEFORE or baseline["head_tree"] != BEFORE_TREE or not baseline["clean"]:
            raise GateError("baseline_identity_or_cleanliness_mismatch")
        if file_sha256(repo / "Cargo.lock") != CARGO_LOCK_SHA256:
            raise GateError("baseline_cargo_lock_hash_mismatch")
        diagnostics["gates_passed"].append("clean_disposable_before_baseline")

        test_application = apply_indexed_patch(repo, test_patch_path, "test_setup")
        test_setup_state = worktree_state(repo)
        test_patch_bytes = test_patch_path.read_bytes()
        exact_diff(repo, test_patch_bytes, TEST_PATHS, "test_setup_not_exact")
        tests = selected_test_hashes(repo)
        identity_before = verifier_identity(repo, target_dir)
        state_pre_before_verify = worktree_state(repo)
        before_observation = run_verifier(repo, target_dir, identity_before)
        validate_observation(before_observation, EXPECTED_BEFORE, "before")
        state_post_before_verify = worktree_state(repo)
        if state_post_before_verify["identity_sha256"] != state_pre_before_verify["identity_sha256"]:
            raise GateError("before_verifier_mutated_worktree")
        if file_sha256(repo / "Cargo.lock") != CARGO_LOCK_SHA256:
            raise GateError("before_verifier_mutated_cargo_lock")
        diagnostics["gates_passed"].append("test_only_before_32_passed_1_failed_exit_101")

        production_application = apply_indexed_patch(repo, production_patch_path, "production_repair")
        exact_diff(
            repo,
            selected_diff,
            (*PRODUCTION_PATHS, *TEST_PATHS),
            "selected_after_diff_not_exact",
        )
        identity_after = verifier_identity(repo, target_dir)
        if identity_after["identity_sha256"] != identity_before["identity_sha256"]:
            raise GateError("verifier_identity_changed")
        state_pre_after_verify = worktree_state(repo)
        after_observation = run_verifier(repo, target_dir, identity_after)
        validate_observation(after_observation, EXPECTED_AFTER, "after")
        state_post_after_verify = worktree_state(repo)
        if state_post_after_verify["identity_sha256"] != state_pre_after_verify["identity_sha256"]:
            raise GateError("after_verifier_mutated_worktree")
        if file_sha256(repo / "Cargo.lock") != CARGO_LOCK_SHA256:
            raise GateError("after_verifier_mutated_cargo_lock")
        if state_post_after_verify["working_diff_sha256"] != SELECTED_DIFF_SHA256:
            raise GateError("final_worktree_diff_hash_mismatch")
        final_diff_check = git(repo, "diff", "--check", "HEAD")
        final_diff_check_hash = sha256_bytes(
            (final_diff_check["stdout"] + final_diff_check["stderr"]).encode("utf-8")
        )
        if (
            final_diff_check["timed_out"]
            or final_diff_check["return_code"] != 2
            or final_diff_check_hash != SELECTED_DIFF_CHECK_SHA256
        ):
            raise GateError("final_pinned_diff_check_signature_mismatch")
        diagnostics["gates_passed"].append("identical_verifier_after_33_passed_exit_0")
        diagnostics["gates_passed"].append("final_worktree_exact_no_mutation_or_residue")

        source_after = source_state()
        if source_after["identity_sha256"] != source_before["identity_sha256"]:
            raise GateError("source_repository_mutated")
        diagnostics["gates_passed"].append("source_repository_unchanged")

        evidence = {
            "record_type": "stage12584_raw_private_causal_replay_evidence_v1",
            "stage": STAGE,
            "artifact_scope": "raw_private_non_trainer",
            "trainer_visible": False,
            "training_allowed": False,
            "strict_eval": False,
            "source_heldout": False,
            "source": {
                "repository": str(SOURCE_REPO),
                "before_commit": BEFORE,
                "after_commit": AFTER,
                "before_tree": BEFORE_TREE,
                "after_tree": AFTER_TREE,
                "after_parent_is_before": True,
                "source_state_before": source_before,
                "source_state_after": source_after,
                "source_unchanged": True,
            },
            "patch_split": pinned,
            "patch_application": {
                "test_setup": test_application,
                "production_repair": production_application,
            },
            "selected_test_content_sha256": tests,
            "verifier": {
                "identity_sha256": identity_before["identity_sha256"],
                "normalized_identity": identity_before["normalized"],
                "identical_before_after": True,
                "expected_before": EXPECTED_BEFORE,
                "expected_after": EXPECTED_AFTER,
            },
            "observations": {"before": before_observation, "after": after_observation},
            "worktree_states": {
                "baseline": baseline,
                "after_test_setup": test_setup_state,
                "pre_before_verifier": state_pre_before_verify,
                "post_before_verifier": state_post_before_verify,
                "pre_after_verifier": state_pre_after_verify,
                "final": state_post_after_verify,
            },
            "mutation_audit": {
                "source_repository_unchanged": True,
                "before_verifier_worktree_unchanged": True,
                "after_verifier_worktree_unchanged": True,
                "cargo_lock_unchanged": True,
                "final_changed_paths_exact": True,
                "final_changed_paths": state_post_after_verify["changed_paths"],
                "final_diff_sha256": state_post_after_verify["working_diff_sha256"],
                "pinned_diff_check": {
                    "return_code": final_diff_check["return_code"],
                    "output_sha256": final_diff_check_hash,
                    "expected_snapshot_whitespace_diagnostics": True,
                },
            },
            "admission": {
                "admission_allowed": False,
                "admitted_files": [],
                "counters": ADMISSION_COUNTERS,
                "reason": "raw_private_evidence_candidate_only",
            },
        }
        evidence["canonical_identity"] = canonical_evidence_identity(evidence)
        evidence["evidence_sha256"] = stable_hash(evidence["canonical_identity"])
        candidate = {
            "record_type": "stage12584_raw_private_evidence_candidate_v1",
            "stage": STAGE,
            "artifact_scope": "raw_private_non_trainer",
            "trainer_visible": False,
            "training_allowed": False,
            "strict_eval": False,
            "source_heldout": False,
            "candidate_status": "raw_private_evidence_only_not_admitted",
            "evidence_sha256": evidence["evidence_sha256"],
            "source_identity_sha256": stable_hash(evidence["source"]),
            "verifier_identity_sha256": identity_before["identity_sha256"],
            "before_observation_sha256": before_observation["canonical_identity_sha256"],
            "after_observation_sha256": after_observation["canonical_identity_sha256"],
            "final_worktree_state_sha256": state_post_after_verify["identity_sha256"],
            "admission_allowed": False,
            "admitted_files": [],
            "admission_counters": ADMISSION_COUNTERS,
        }
        candidate["candidate_identity_sha256"] = stable_hash(candidate)
        assert_no_forbidden_keys(evidence)
        assert_no_forbidden_keys(candidate)
        diagnostics.update({"status": "RAW_PRIVATE_MATERIALIZED", "exact_blocker": None})
        return evidence, {"candidate": candidate, "diagnostics": diagnostics}
    except Exception as exc:
        diagnostics["exact_blocker"] = str(exc)
        raise GateError(str(exc)) from exc
    finally:
        if disposable is not None:
            shutil.rmtree(disposable, ignore_errors=True)


def summary_record(status: str, blocker: str | None) -> dict[str, Any]:
    return {
        "stage": STAGE,
        "status": status,
        "training_allowed": False,
        "strict_eval": False,
        "source_heldout": False,
        "support_scope": "raw-private-evidence-candidate-only",
        "admitted_files": [],
        "counters": ADMISSION_COUNTERS,
        "model_input_emitted": False,
        "candidate_actions_emitted": False,
        "exact_blocker": blocker,
        "claim_boundary": (
            "Fresh local CPU replay evidence is raw-private candidate material only. "
            "No file or record is admitted to training, strict evaluation, or source-heldout evaluation."
        ),
    }


def execute(out: Path = OUT, summary: Path = SUMMARY) -> dict[str, Any]:
    out.mkdir(parents=True, exist_ok=True)
    try:
        clear_generated_outputs(out)
        evidence, materialized = replay(out)
        write_jsonl(out / "raw_private_evidence.jsonl", [evidence])
        write_jsonl(out / "raw_private_candidate.jsonl", [materialized["candidate"]])
        write_json(out / "replay_diagnostics.json", materialized["diagnostics"])
        result = summary_record("RAW_PRIVATE_REPLAY_MATERIALIZED", None)
    except Exception as exc:
        blocker = str(exc)
        try:
            clear_generated_outputs(out)
        except Exception as cleanup_exc:
            blocker += ";reject_cleanup_failed:" + str(cleanup_exc)
        result = summary_record("REJECTED", blocker)
        write_json(
            out / "replay_diagnostics.json",
            {"stage": STAGE, "status": "REJECTED", "exact_blocker": blocker},
        )
    assert_no_forbidden_keys(result)
    write_json(out / "summary.json", result)
    write_json(summary, result)
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, default=OUT)
    parser.add_argument("--summary", type=Path, default=SUMMARY)
    args = parser.parse_args()
    result = execute(args.output_dir, args.summary)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["status"] == "RAW_PRIVATE_REPLAY_MATERIALIZED" else 2


if __name__ == "__main__":
    raise SystemExit(main())
