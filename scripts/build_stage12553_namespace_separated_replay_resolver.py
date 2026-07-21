#!/usr/bin/env python3
"""Resolve replay candidates without crossing trajectory and task namespaces.

This is a contract-only stage.  It checks identity, protection, and patch
applicability, but grants no replay, training, root, or repair credit.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import tempfile
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import urlparse


ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12553_namespace_separated_replay_resolver"
OUT = ROOT / "runs/local/artifacts" / STAGE
SUMMARY = ROOT / "runs/summaries" / f"{STAGE}.json"
DEFAULT_BINDINGS = ROOT / "runs/local/artifacts/stage12550_source_native_replay_eligibility_prefilter/recovery_worklist.jsonl"
DEFAULT_TASK_RECORDS = ROOT / "runs/local/artifacts/stage12551_open_swe_upstream_identity_and_checkout_resolver/resolved_checkout_candidates.jsonl"
DEFAULT_ADJUDICATIONS = ROOT / "runs/local/artifacts/stage12552_protected_task_universe_validator/coverage_adjudications.jsonl"

SHA256_RE = re.compile(r"^[0-9a-f]{64}$", re.I)
COMMIT_RE = re.compile(r"^[0-9a-f]{40}$", re.I)
SAFE_REPO_PART_RE = re.compile(r"^[A-Za-z0-9_.-]+$")
SAFE_LOCAL_CONFIG_KEYS = {
    "core.repositoryformatversion", "core.filemode", "core.bare",
    "core.logallrefupdates", "core.ignorecase", "core.precomposeunicode",
    "remote.origin.url", "remote.origin.fetch",
}
ZERO_FLAGS = {
    "training_allowed": False,
    "gpu_allowed": False,
    "admission_allowed": False,
    "replay_allowed": False,
    "root_credit": False,
    "repair_credit": False,
    "strict_eval_eligible": False,
}


def stable_hash(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(payload.encode()).hexdigest()


def canonical_repo(value: Any) -> str | None:
    text = str(value or "").strip().replace("\\", "/")
    if text.startswith("git@github.com:"):
        text = text.split(":", 1)[1]
    elif "://" in text:
        parsed = urlparse(text)
        if parsed.hostname not in {"github.com", "www.github.com"}:
            return None
        text = parsed.path
    text = text.strip("/")
    if text.lower().endswith(".git"):
        text = text[:-4]
    parts = text.split("/")
    if len(parts) == 1 and "__" in text:
        parts = text.split("__", 1)
    if len(parts) != 2 or not all(SAFE_REPO_PART_RE.fullmatch(part) for part in parts):
        return None
    return f"{parts[0].lower()}/{parts[1].lower()}"


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            if not line.strip():
                continue
            value = json.loads(line)
            if not isinstance(value, dict):
                raise ValueError(f"{path}:{line_number}: expected object")
            rows.append(value)
    return rows


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")


def _nested(row: dict[str, Any], name: str) -> dict[str, Any]:
    value = row.get(name)
    return value if isinstance(value, dict) else {}


def _explicit_task_key(row: dict[str, Any]) -> tuple[str, str] | None:
    """Read only explicit task keys, never a trajectory-native instance_id."""
    identity = _nested(row, "source_native_identity")
    namespace = row.get("task_namespace", identity.get("task_namespace"))
    instance = row.get("task_instance_id", identity.get("task_instance_id"))
    if not isinstance(namespace, str) or not namespace.strip():
        return None
    if not isinstance(instance, str) or not instance.strip():
        return None
    return namespace, instance


def _field(row: dict[str, Any], name: str, *aliases: str) -> Any:
    identity = _nested(row, "source_native_identity")
    for key in (name, *aliases):
        if key in row:
            return row[key]
        if key in identity:
            return identity[key]
    return None


def trajectory_key(row: dict[str, Any]) -> tuple[Any, ...] | None:
    values = (
        _field(row, "trajectory_namespace"),
        _field(row, "trajectory_snapshot_sha256", "dataset_snapshot_sha256"),
        _field(row, "trajectory_shard_id", "shard_id"),
        _field(row, "trajectory_shard_sha256", "shard_sha256", "dataset_file_sha256"),
        _field(row, "trajectory_ordinal", "row_index_zero_based", "source_row_index_zero_based"),
        _field(row, "source_row_sha256"),
        _field(row, "trajectory_sha256"),
        _field(row, "model_patch_sha256"),
    )
    digest_indexes = {1, 3, 5, 6, 7}
    if not all(isinstance(values[index], str) and SHA256_RE.fullmatch(values[index]) for index in digest_indexes):
        return None
    if not isinstance(values[0], str) or not values[0].strip():
        return None
    if not isinstance(values[2], str) or not values[2].strip():
        return None
    if not isinstance(values[4], int) or isinstance(values[4], bool) or values[4] < 0:
        return None
    return tuple(value.lower() if index in digest_indexes else value for index, value in enumerate(values))


def binding_errors(binding: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    identity = _nested(binding, "source_native_identity")
    namespace = binding.get("task_namespace", identity.get("task_namespace"))
    instance = binding.get("task_instance_id", identity.get("task_instance_id"))
    if not isinstance(namespace, str) or not namespace.strip():
        errors.append("explicit_task_namespace_missing_from_trajectory_binding")
    if not isinstance(instance, str) or not instance.strip():
        errors.append("explicit_task_instance_id_missing_from_trajectory_binding")
    checks = {
        "trajectory_namespace_missing": _field(binding, "trajectory_namespace"),
        "trajectory_snapshot_digest_missing": _field(binding, "trajectory_snapshot_sha256", "dataset_snapshot_sha256"),
        "trajectory_shard_identity_missing": _field(binding, "trajectory_shard_id", "shard_id"),
        "trajectory_shard_digest_missing": _field(binding, "trajectory_shard_sha256", "shard_sha256", "dataset_file_sha256"),
        "source_row_digest_missing": _field(binding, "source_row_sha256"),
        "trajectory_digest_missing": _field(binding, "trajectory_sha256"),
        "model_patch_digest_missing": _field(binding, "model_patch_sha256"),
        "task_snapshot_digest_missing": _field(binding, "task_snapshot_sha256"),
        "protected_inventory_digest_missing": _field(binding, "protected_inventory_sha256"),
        "protected_policy_digest_missing": _field(binding, "protected_policy_sha256"),
        "canonical_repo_lineage_id_missing": _field(binding, "canonical_repo_lineage_id"),
    }
    for reason, value in checks.items():
        if reason.endswith("identity_missing"):
            valid = isinstance(value, str) and bool(value.strip())
        elif reason == "trajectory_namespace_missing":
            valid = isinstance(value, str) and bool(value.strip())
        else:
            valid = isinstance(value, str) and bool(SHA256_RE.fullmatch(value))
        if not valid:
            errors.append(reason)
    ordinal = _field(binding, "trajectory_ordinal", "row_index_zero_based", "source_row_index_zero_based")
    if not isinstance(ordinal, int) or isinstance(ordinal, bool) or ordinal < 0:
        errors.append("trajectory_ordinal_missing_or_invalid")
    if canonical_repo(binding.get("canonical_repo")) is None:
        errors.append("canonical_repo_lineage_missing_from_trajectory_binding")
    for name, reason in (
        ("authoritative_base_commit", "pinned_authoritative_base_commit_missing"),
        ("authoritative_base_tree", "pinned_authoritative_base_tree_missing"),
        ("expected_post_tree", "pinned_expected_post_tree_missing"),
    ):
        if not COMMIT_RE.fullmatch(str(_field(binding, name) or "")):
            errors.append(reason)
    return sorted(errors)


def _repo_lineage(row: dict[str, Any]) -> tuple[str | None, list[str]]:
    errors: list[str] = []
    primary = canonical_repo(row.get("canonical_repo") or row.get("repo"))
    lineage = row.get("repo_lineage")
    values: list[Any] = []
    if isinstance(lineage, dict):
        values = [value for key, value in lineage.items() if "repo" in key or "remote" in key]
    elif isinstance(lineage, list):
        values = lineage
    canonical_values = [canonical_repo(value) for value in values]
    if any(value is None for value in canonical_values):
        errors.append("invalid_canonical_repo_lineage")
    if primary is None:
        errors.append("canonical_repo_lineage_missing")
    elif any(value != primary for value in canonical_values):
        errors.append("internally_conflicting_canonical_repo_lineage")
    return primary, errors


def _authoritative_task_errors(row: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if row.get("authoritative") is not True:
        errors.append("task_record_not_authoritative")
    if _explicit_task_key(row) is None:
        errors.append("authoritative_task_key_missing")
    if not SHA256_RE.fullmatch(str(row.get("task_snapshot_sha256") or "")):
        errors.append("authoritative_task_snapshot_digest_missing")
    if not COMMIT_RE.fullmatch(str(row.get("base_commit") or "")):
        errors.append("authoritative_base_commit_missing")
    if not COMMIT_RE.fullmatch(str(row.get("base_tree") or "")):
        errors.append("authoritative_base_tree_missing")
    if not isinstance(row.get("trusted_ref"), str) or not str(row["trusted_ref"]).startswith("refs/tags/"):
        errors.append("trusted_immutable_ref_missing_or_invalid")
    if not COMMIT_RE.fullmatch(str(row.get("trusted_ref_tip") or "")):
        errors.append("trusted_ref_tip_missing")
    if row.get("trusted_ref_immutable") is not True:
        errors.append("trusted_ref_not_declared_immutable")
    if not isinstance(row.get("repository_identity_authority"), str) or not row["repository_identity_authority"].strip():
        errors.append("trusted_repository_identity_authority_missing")
    if not SHA256_RE.fullmatch(str(row.get("repository_identity_sha256") or "")):
        errors.append("trusted_repository_identity_digest_missing")
    if not SHA256_RE.fullmatch(str(row.get("canonical_repo_lineage_id") or "")):
        errors.append("canonical_repo_lineage_id_missing")
    _, lineage_errors = _repo_lineage(row)
    errors.extend(lineage_errors)
    return sorted(set(errors))


def _protected_errors(row: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if row.get("validated") is not True:
        errors.append("protected_adjudication_not_validated")
    if _explicit_task_key(row) is None:
        errors.append("protected_adjudication_task_key_missing")
    if row.get("protected_status") != "CLEAR":
        errors.append("protected_status_not_clear")
    if not SHA256_RE.fullmatch(str(row.get("task_snapshot_sha256") or "")):
        errors.append("protected_task_snapshot_digest_missing")
    for name in (
        "protected_inventory_sha256", "protected_policy_sha256",
        "trajectory_key_sha256", "task_key_sha256", "model_patch_sha256",
        "canonical_repo_lineage_id", "resolution_certificate_sha256",
    ):
        if not SHA256_RE.fullmatch(str(row.get(name) or "")):
            errors.append(f"protected_{name}_missing")
    for name in ("base_commit", "base_tree", "expected_post_tree"):
        if not COMMIT_RE.fullmatch(str(row.get(name) or "")):
            errors.append(f"protected_{name}_missing")
    _, lineage_errors = _repo_lineage(row)
    errors.extend(lineage_errors)
    return sorted(set(errors))


def _patch_errors(row: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    patch = row.get("model_patch")
    if not isinstance(patch, str) or not patch.strip():
        errors.append("trajectory_model_patch_missing")
    elif hashlib.sha256(patch.encode()).hexdigest() != str(_field(row, "model_patch_sha256") or "").lower():
        errors.append("trajectory_model_patch_digest_mismatch")
    if trajectory_key(row) is None:
        errors.append("exact_trajectory_patch_binding_incomplete")
    repo, lineage_errors = _repo_lineage(row)
    errors.extend(lineage_errors)
    if repo is None:
        errors.append("trajectory_patch_repo_lineage_missing")
    if not SHA256_RE.fullmatch(str(row.get("canonical_repo_lineage_id") or "")):
        errors.append("trajectory_patch_repo_lineage_id_missing")
    if not COMMIT_RE.fullmatch(str(row.get("expected_post_tree") or "")):
        errors.append("trajectory_patch_expected_post_tree_missing")
    return sorted(set(errors))


def _run_git(repo: Path, args: list[str], *, env: dict[str, str] | None = None, patch: str | None = None) -> subprocess.CompletedProcess[str]:
    clean_env = os.environ.copy()
    for name in ("GIT_ALTERNATE_OBJECT_DIRECTORIES", "GIT_OBJECT_DIRECTORY", "GIT_REPLACE_REF_BASE", "GIT_SHALLOW_FILE"):
        clean_env.pop(name, None)
    clean_env.update({
        "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_SYSTEM": os.devnull,
        "GIT_CONFIG_GLOBAL": os.devnull, "GIT_OPTIONAL_LOCKS": "0",
        "GIT_TERMINAL_PROMPT": "0", "GIT_NO_REPLACE_OBJECTS": "1",
    })
    if env:
        clean_env.update(env)
    return subprocess.run(
        ["git", "-C", str(repo), *args], input=patch, text=True,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False, timeout=20, env=clean_env,
    )


def _git_repository_state_errors(repo: Path) -> list[str]:
    errors: list[str] = []
    git_dir_result = _run_git(repo, ["rev-parse", "--absolute-git-dir"])
    common_dir_result = _run_git(repo, ["rev-parse", "--git-common-dir"])
    if git_dir_result.returncode or common_dir_result.returncode:
        return ["authoritative_checkout_not_git_repository"]
    git_dir = Path(git_dir_result.stdout.strip())
    common_dir = Path(common_dir_result.stdout.strip())
    if not common_dir.is_absolute():
        common_dir = (repo / common_dir).resolve()
    shallow = _run_git(repo, ["rev-parse", "--is-shallow-repository"])
    if shallow.returncode or shallow.stdout.strip() != "false" or (git_dir / "shallow").exists() or (common_dir / "shallow").exists():
        errors.append("shallow_repository_forbidden")
    replacements = _run_git(repo, ["for-each-ref", "--format=%(refname)", "refs/replace"])
    if replacements.returncode or replacements.stdout.strip():
        errors.append("replace_refs_forbidden")
    if (common_dir / "info" / "grafts").exists() or (git_dir / "info" / "grafts").exists():
        errors.append("grafts_forbidden")
    if (common_dir / "objects" / "info" / "alternates").exists() or (git_dir / "objects" / "info" / "alternates").exists():
        errors.append("object_alternates_forbidden")
    config = _run_git(repo, ["config", "--local", "--name-only", "--list"])
    if config.returncode:
        errors.append("local_git_config_unreadable")
    else:
        keys = {line.strip().lower() for line in config.stdout.splitlines() if line.strip()}
        if any("promisor" in key or "partialclone" in key for key in keys):
            errors.append("promisor_or_partial_clone_forbidden")
        if keys - SAFE_LOCAL_CONFIG_KEYS:
            errors.append("uncontrolled_local_git_config_forbidden")
    return sorted(set(errors))


def expected_lineage_id(task: dict[str, Any], canonical: str) -> str:
    return stable_hash({
        "canonical_repo": canonical,
        "repository_identity_authority": task.get("repository_identity_authority"),
        "repository_identity_sha256": task.get("repository_identity_sha256"),
        "trusted_ref": task.get("trusted_ref"),
        "trusted_ref_tip": str(task.get("trusted_ref_tip") or "").lower(),
    })


def resolution_certificate_payload(
    binding: dict[str, Any], task: dict[str, Any], trace_key: tuple[Any, ...],
    task_key: tuple[str, str], lineage_id: str,
) -> dict[str, Any]:
    return {
        "protected_inventory_sha256": str(_field(binding, "protected_inventory_sha256") or "").lower(),
        "protected_policy_sha256": str(_field(binding, "protected_policy_sha256") or "").lower(),
        "trajectory_key_sha256": stable_hash(trace_key),
        "task_key_sha256": stable_hash(task_key),
        "model_patch_sha256": str(_field(binding, "model_patch_sha256") or "").lower(),
        "base_commit": str(task.get("base_commit") or "").lower(),
        "base_tree": str(task.get("base_tree") or "").lower(),
        "expected_post_tree": str(_field(binding, "expected_post_tree") or "").lower(),
        "canonical_repo_lineage_id": lineage_id,
    }


def check_model_patch(task: dict[str, Any], patch_record: dict[str, Any]) -> tuple[str, list[str], dict[str, str]]:
    checkout = _nested(task, "checkout")
    repo_value = task.get("repo_root") or task.get("mirror_path") or checkout.get("mirror_path") or checkout.get("repo_root")
    if not isinstance(repo_value, str) or not Path(repo_value).is_dir():
        return "unresolved", ["authoritative_checkout_missing"], {}
    repo = Path(repo_value)
    commit = str(task.get("base_commit") or "").lower()
    state_errors = _git_repository_state_errors(repo)
    if state_errors:
        return "blocked", state_errors, {}
    if _run_git(repo, ["cat-file", "-e", f"{commit}^{{commit}}"]).returncode:
        return "blocked", ["authoritative_base_commit_object_missing"], {}
    trusted_ref = str(task.get("trusted_ref") or "")
    tip = _run_git(repo, ["rev-parse", "--verify", f"{trusted_ref}^{{commit}}"])
    if tip.returncode or tip.stdout.strip().lower() != str(task.get("trusted_ref_tip") or "").lower():
        return "blocked", ["trusted_ref_tip_mismatch_or_missing"], {}
    if _run_git(repo, ["merge-base", "--is-ancestor", commit, tip.stdout.strip()]).returncode:
        return "blocked", ["authoritative_base_not_reachable_from_trusted_ref"], {}
    tree = _run_git(repo, ["rev-parse", f"{commit}^{{tree}}"])
    if tree.returncode:
        return "blocked", ["authoritative_base_tree_unreadable"], {}
    pre_tree = tree.stdout.strip().lower()
    if pre_tree != str(task.get("base_tree") or "").lower():
        return "blocked", ["authoritative_base_tree_mismatch"], {"pre_tree": pre_tree}
    with tempfile.TemporaryDirectory(prefix="stage12553-index-") as temp:
        env = {"GIT_INDEX_FILE": str(Path(temp) / "index")}
        if _run_git(repo, ["read-tree", commit], env=env).returncode:
            return "blocked", ["authoritative_base_tree_unreadable"], {}
        result = _run_git(
            repo, ["apply", "--cached", "--whitespace=nowarn", "-"],
            env=env, patch=patch_record["model_patch"],
        )
        post = _run_git(repo, ["write-tree"], env=env) if result.returncode == 0 else None
    if result.returncode:
        return "blocked", ["trajectory_model_patch_not_applicable_at_authoritative_base"], {"pre_tree": pre_tree}
    if post is None or post.returncode or not COMMIT_RE.fullmatch(post.stdout.strip()):
        return "blocked", ["post_index_tree_unavailable"], {"pre_tree": pre_tree}
    post_tree = post.stdout.strip().lower()
    if post_tree != str(patch_record.get("expected_post_tree") or "").lower():
        return "blocked", ["resulting_tree_binding_mismatch"], {"pre_tree": pre_tree, "post_tree": post_tree}
    return "resolved_replay_candidate", [], {"pre_tree": pre_tree, "post_tree": post_tree}

def _base_result(binding: dict[str, Any], status: str, reasons: Iterable[str]) -> dict[str, Any]:
    return {
        "record_type": "stage12553_namespace_separated_replay_resolution_v1",
        "candidate_id": binding.get("candidate_id"),
        "task_namespace": (_explicit_task_key(binding) or (None, None))[0],
        "task_instance_id": (_explicit_task_key(binding) or (None, None))[1],
        "resolution_status": status,
        "blocking_reasons": sorted(set(reasons)),
        "trajectory_instance_id_fallback_used": False,
        "trajectory_dataset_path_join_used": False,
        "task_patch_equality_join_used": False,
        "reference_or_gold_patch_applied": False,
        "contract_only": True,
        **ZERO_FLAGS,
    }


def resolve_replay_candidates(
    trajectory_bindings: list[dict[str, Any]],
    authoritative_task_records: list[dict[str, Any]],
    protected_adjudications: list[dict[str, Any]],
    trajectory_patch_records: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Resolve four independent namespaces using only explicit exact keys."""
    tasks: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    protected: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    patches: dict[tuple[Any, ...], list[dict[str, Any]]] = defaultdict(list)
    for row in authoritative_task_records:
        key = _explicit_task_key(row)
        if key is not None:
            tasks[key].append(row)
    for row in protected_adjudications:
        key = _explicit_task_key(row)
        if key is not None:
            protected[key].append(row)
    for row in trajectory_patch_records:
        key = trajectory_key(row)
        if key is not None:
            patches[key].append(row)

    output: list[dict[str, Any]] = []
    for binding in trajectory_bindings:
        errors = binding_errors(binding)
        if errors:
            output.append(_base_result(binding, "blocked", errors))
            continue
        task_key = _explicit_task_key(binding)
        trace_key = trajectory_key(binding)
        assert task_key is not None and trace_key is not None
        task_matches = tasks.get(task_key, [])
        protected_matches = protected.get(task_key, [])
        patch_matches = patches.get(trace_key, [])
        missing = []
        if not task_matches:
            missing.append("authoritative_task_record_missing_for_explicit_task_key")
        if not protected_matches:
            missing.append("validated_protected_adjudication_missing_for_explicit_task_key")
        if not patch_matches:
            missing.append("trajectory_model_patch_record_missing_for_exact_trajectory_key")
        if missing:
            output.append(_base_result(binding, "unresolved", missing))
            continue
        if len(task_matches) != 1 or len(protected_matches) != 1 or len(patch_matches) != 1:
            reasons = []
            if len(task_matches) != 1:
                reasons.append("authoritative_task_record_ambiguous")
            if len(protected_matches) != 1:
                reasons.append("protected_adjudication_ambiguous")
            if len(patch_matches) != 1:
                reasons.append("trajectory_model_patch_record_ambiguous")
            output.append(_base_result(binding, "blocked", reasons))
            continue

        task, adjudication, patch_record = task_matches[0], protected_matches[0], patch_matches[0]
        errors = _authoritative_task_errors(task) + _protected_errors(adjudication) + _patch_errors(patch_record)
        pinned_task_snapshot = str(_field(binding, "task_snapshot_sha256") or "").lower()
        for row, reason in (
            (task, "authoritative_task_snapshot_binding_mismatch"),
            (adjudication, "protected_task_snapshot_binding_mismatch"),
        ):
            if str(row.get("task_snapshot_sha256") or "").lower() != pinned_task_snapshot:
                errors.append(reason)
        repos = [_repo_lineage(row)[0] for row in (binding, task, adjudication, patch_record)]
        if None in repos or len(set(repos)) != 1:
            errors.append("canonical_repo_lineage_mismatch_across_namespaces")
        canonical = repos[0] if repos and repos[0] is not None else ""
        lineage_id = expected_lineage_id(task, canonical)
        explicit_lineages = [
            str(_field(binding, "canonical_repo_lineage_id") or "").lower(),
            str(task.get("canonical_repo_lineage_id") or "").lower(),
            str(adjudication.get("canonical_repo_lineage_id") or "").lower(),
            str(patch_record.get("canonical_repo_lineage_id") or "").lower(),
        ]
        if any(value != lineage_id for value in explicit_lineages):
            errors.append("canonical_repo_lineage_id_mismatch")
        if str(_field(binding, "authoritative_base_commit") or "").lower() != str(task.get("base_commit") or "").lower():
            errors.append("authoritative_base_commit_binding_mismatch")
        if str(_field(binding, "authoritative_base_tree") or "").lower() != str(task.get("base_tree") or "").lower():
            errors.append("authoritative_base_tree_binding_mismatch")
        if str(patch_record.get("expected_post_tree") or "").lower() != str(_field(binding, "expected_post_tree") or "").lower():
            errors.append("trajectory_patch_resulting_tree_binding_mismatch")
        certificate = resolution_certificate_payload(binding, task, trace_key, task_key, lineage_id)
        certificate_digest = stable_hash(certificate)
        protected_expected = {**certificate, "resolution_certificate_sha256": certificate_digest}
        for name, expected in protected_expected.items():
            if str(adjudication.get(name) or "").lower() != str(expected).lower():
                errors.append(f"protected_certificate_{name}_mismatch")
        if errors:
            output.append(_base_result(binding, "blocked", errors))
            continue
        status, applicability_errors, trees = check_model_patch(task, patch_record)
        if status == "resolved_replay_candidate" and trees.get("post_tree") != certificate["expected_post_tree"]:
            status = "blocked"
            applicability_errors.append("protected_resulting_tree_binding_mismatch")
        result = _base_result(binding, status, applicability_errors)
        if status == "resolved_replay_candidate":
            result.update({
                "canonical_repo": canonical,
                "canonical_repo_lineage_id": lineage_id,
                "authoritative_base_commit": str(task["base_commit"]).lower(),
                "pre_tree_id": trees["pre_tree"],
                "post_index_tree_id": trees["post_tree"],
                "trajectory_key_sha256": stable_hash(trace_key),
                "task_key_sha256": stable_hash(task_key),
                "resolution_certificate_sha256": certificate_digest,
                "model_patch_applicability_verified": True,
                "protected_status": "CLEAR",
            })
        output.append(result)
    return output


resolve_candidates = resolve_replay_candidates


def build_summary(rows: list[dict[str, Any]], input_counts: dict[str, int]) -> dict[str, Any]:
    statuses = Counter(row["resolution_status"] for row in rows)
    reasons = Counter(reason for row in rows for reason in row["blocking_reasons"])
    return {
        "stage": STAGE,
        "record_type": "stage12553_namespace_separated_replay_resolver_summary_v1",
        **input_counts,
        "output_row_count": len(rows),
        "resolved_replay_candidate_count": statuses["resolved_replay_candidate"],
        "blocked_count": statuses["blocked"],
        "unresolved_count": statuses["unresolved"],
        "reason_counts": dict(sorted(reasons.items())),
        "all_inputs_namespace_separated": True,
        "trajectory_instance_id_fallback_used": False,
        "trajectory_dataset_path_join_used": False,
        "task_patch_equality_join_used": False,
        "reference_or_gold_patch_applied": False,
        "default_disposition": "blocked" if statuses["resolved_replay_candidate"] == 0 else "mixed",
        "contract_only": True,
        **ZERO_FLAGS,
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--trajectory-bindings", type=Path, default=DEFAULT_BINDINGS)
    parser.add_argument("--authoritative-task-records", type=Path, default=DEFAULT_TASK_RECORDS)
    parser.add_argument("--protected-adjudications", type=Path, default=DEFAULT_ADJUDICATIONS)
    parser.add_argument("--trajectory-patches", type=Path)
    parser.add_argument("--output-dir", type=Path, default=OUT)
    parser.add_argument("--summary", type=Path, default=SUMMARY)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    bindings = read_jsonl(args.trajectory_bindings)
    tasks = read_jsonl(args.authoritative_task_records)
    adjudications = read_jsonl(args.protected_adjudications)
    patches = read_jsonl(args.trajectory_patches) if args.trajectory_patches else []
    rows = resolve_replay_candidates(bindings, tasks, adjudications, patches)
    resolved = [row for row in rows if row["resolution_status"] == "resolved_replay_candidate"]
    blocked = [row for row in rows if row["resolution_status"] == "blocked"]
    unresolved = [row for row in rows if row["resolution_status"] == "unresolved"]
    write_jsonl(args.output_dir / "resolved_replay_candidates.jsonl", resolved)
    write_jsonl(args.output_dir / "blocked_candidates.jsonl", blocked)
    write_jsonl(args.output_dir / "unresolved_candidates.jsonl", unresolved)
    write_jsonl(args.output_dir / "all_resolutions.jsonl", rows)
    summary = build_summary(rows, {
        "trajectory_binding_count": len(bindings),
        "authoritative_task_record_count": len(tasks),
        "protected_adjudication_count": len(adjudications),
        "trajectory_patch_record_count": len(patches),
    })
    write_json(args.output_dir / "summary.json", summary)
    write_json(args.summary, summary)
    print(json.dumps(summary, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
