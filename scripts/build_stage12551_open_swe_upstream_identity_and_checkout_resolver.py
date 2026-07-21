#!/usr/bin/env python3
"""Resolve authoritative Open-SWE task metadata to verified local Git mirrors.

Only explicitly configured metadata adapters and mirror roots are inspected.  A
trajectory, command transcript, or candidate-authored digest is never an input
to identity or commit resolution.
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
STAGE = "stage12551_open_swe_upstream_identity_and_checkout_resolver"
INPUT = ROOT / "runs/local/artifacts/stage12550_source_native_replay_eligibility_prefilter/recovery_worklist.jsonl"
OUT = ROOT / "runs/local/artifacts" / STAGE
RESOLVED_OUT = OUT / "resolved_checkout_candidates.jsonl"
UNRESOLVED_OUT = OUT / "unresolved_worklist.jsonl"
CONFLICT_OUT = OUT / "ambiguous_or_conflicting.jsonl"
OUT_SUMMARY = OUT / "summary.json"
SUMMARY = ROOT / "runs/summaries" / f"{STAGE}.json"

FULL_SHA_RE = re.compile(r"^[0-9a-f]{40}$", re.I)
SHA256_RE = re.compile(r"^[0-9a-f]{64}$", re.I)
SAFE_REPO_PART_RE = re.compile(r"^[A-Za-z0-9_.-]+$")
AUTHORITATIVE_RECORD_TYPES = {
    "open_swe_upstream_task_record_v1",
    "swe_bench_upstream_task_record_v1",
}
AUTHORITATIVE_COMMIT_SOURCES = {"upstream_task_record", "dataset_task_record"}
AUTHORITATIVE_PATCH_SOURCES = {"upstream_task_record", "dataset_task_record"}
ZERO_FLAGS = {
    "training_allowed": False,
    "gpu_allowed": False,
    "admission_allowed": False,
    "root_credit": False,
    "repair_credit": False,
    "replay_allowed": False,
    "strict_eval_eligible": False,
}


def stable_hash(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(payload.encode()).hexdigest()


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
        for number, line in enumerate(handle, 1):
            if not line.strip():
                continue
            value = json.loads(line)
            if not isinstance(value, dict):
                raise ValueError(f"{path}:{number}: expected object")
            rows.append(value)
    return rows


def read_adapter(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    if path.suffix.lower() == ".jsonl":
        return read_jsonl(path)
    value = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(value, dict):
        value = value.get("records")
    if not isinstance(value, list) or not all(isinstance(row, dict) for row in value):
        raise ValueError(f"{path}: expected a JSON list or a records list")
    return value


def write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def canonical_dataset(value: Any) -> str:
    # Dataset identity is exact and lexical: no basename or similarity joins.
    return str(value or "").strip()


def canonical_repo(value: Any) -> str | None:
    """Normalize common upstream aliases to a lower-case owner/repository key."""
    text = str(value or "").strip().replace("\\", "/")
    if not text:
        return None
    if text.startswith("git@") and ":" in text:
        text = text.split(":", 1)[1]
    elif "://" in text:
        parsed = urlparse(text)
        if parsed.hostname not in {"github.com", "www.github.com"}:
            return None
        text = parsed.path
    text = text.strip("/")
    if text.lower().endswith(".git"):
        text = text[:-4]
    parts = [part for part in text.split("/") if part]
    if len(parts) == 1 and "__" in parts[0]:
        parts = parts[0].split("__", 1)
    if len(parts) != 2 or not all(SAFE_REPO_PART_RE.fullmatch(part) for part in parts):
        return None
    return f"{parts[0].lower()}/{parts[1].lower()}"


def recovery_identity(row: dict[str, Any]) -> tuple[str, str]:
    identity = row.get("source_native_identity")
    identity = identity if isinstance(identity, dict) else {}
    return canonical_dataset(identity.get("dataset_file")), str(identity.get("instance_id") or "")


def source_key(row: dict[str, Any]) -> tuple[str, str, str] | None:
    dataset = canonical_dataset(row.get("dataset_file") or row.get("dataset"))
    instance = str(row.get("instance_id") or "")
    repo = canonical_repo(row.get("repo") or row.get("repository") or row.get("repo_url"))
    if not dataset or not instance or repo is None:
        return None
    return dataset, instance, repo


def authoritative_source_record(row: dict[str, Any]) -> bool:
    """Require field-level upstream provenance, not merely plausible metadata."""
    return bool(
        row.get("authoritative") is True
        and row.get("record_type") in AUTHORITATIVE_RECORD_TYPES
        and source_key(row) is not None
        and FULL_SHA_RE.fullmatch(str(row.get("base_commit") or ""))
        and row.get("base_commit_source") in AUTHORITATIVE_COMMIT_SOURCES
        and isinstance(row.get("patch"), str)
        and bool(row["patch"].strip())
        and row.get("patch_source") in AUTHORITATIVE_PATCH_SOURCES
        and SHA256_RE.fullmatch(str(row.get("dataset_file_sha256") or ""))
        and isinstance(row.get("source_row_index_zero_based"), int)
        and row["source_row_index_zero_based"] >= 0
        and bool(str(row.get("trajectory_id") or "").strip())
        and SHA256_RE.fullmatch(str(row.get("source_row_sha256") or ""))
    )


def recovery_binding_errors(recovery: dict[str, Any], source: dict[str, Any]) -> list[str]:
    """Require the authoritative record to identify the exact mined source row."""
    errors: list[str] = []
    recovery_repo = canonical_repo(recovery.get("canonical_repo"))
    source_repo = source_key(source)
    if recovery_repo is None or source_repo is None or recovery_repo != source_repo[2]:
        errors.append("canonical_repo_binding_mismatch")

    recovery_patch = str(recovery.get("model_patch_sha256") or "").lower()
    source_patch = hashlib.sha256(source["patch"].encode()).hexdigest()
    if not SHA256_RE.fullmatch(recovery_patch) or recovery_patch != source_patch:
        errors.append("model_patch_binding_mismatch")

    identity = recovery.get("source_native_identity")
    identity = identity if isinstance(identity, dict) else {}
    recovery_snapshot = str(
        recovery.get("source_dataset_file_sha256")
        or identity.get("dataset_file_sha256")
        or ""
    ).lower()
    source_snapshot = str(source.get("dataset_file_sha256") or "").lower()
    if not SHA256_RE.fullmatch(recovery_snapshot) or recovery_snapshot != source_snapshot:
        errors.append("dataset_snapshot_binding_mismatch")

    recovery_ordinal = recovery.get("source_row_index_zero_based")
    if recovery_ordinal is None:
        recovery_ordinal = identity.get("row_index_zero_based")
    if recovery_ordinal != source.get("source_row_index_zero_based"):
        errors.append("source_row_ordinal_binding_mismatch")
    recovery_trajectory = str(identity.get("trajectory_id") or "")
    if not recovery_trajectory or recovery_trajectory != str(source.get("trajectory_id") or ""):
        errors.append("trajectory_identity_binding_mismatch")
    recovery_row_hash = str(recovery.get("source_row_sha256") or "").lower()
    source_row_hash = str(source.get("source_row_sha256") or "").lower()
    if not SHA256_RE.fullmatch(recovery_row_hash) or recovery_row_hash != source_row_hash:
        errors.append("source_row_hash_binding_mismatch")
    return errors


def _base(recovery: dict[str, Any], reasons: Iterable[str], disposition: str) -> dict[str, Any]:
    dataset, instance = recovery_identity(recovery)
    return {
        "record_type": "stage12551_upstream_identity_checkout_resolution_v1",
        "candidate_id": recovery.get("candidate_id"),
        "source_native_identity": recovery.get("source_native_identity"),
        "canonical_dataset": dataset,
        "instance_id": instance,
        "disposition": disposition,
        "blocking_reasons": sorted(set(reasons)),
        "protected_universe_status": "unresolved_separate_gate",
        **ZERO_FLAGS,
    }


def _run_git(repo: Path, args: list[str], *, env: dict[str, str] | None = None, input_text: str | None = None) -> subprocess.CompletedProcess[str]:
    clean_env = os.environ.copy()
    clean_env.update({
        "GIT_OPTIONAL_LOCKS": "0",
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_TERMINAL_PROMPT": "0",
    })
    if env:
        clean_env.update(env)
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        input=input_text,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
        timeout=20,
        env=clean_env,
    )


def mirror_candidates(repo: str, roots: Iterable[Path]) -> list[Path]:
    """Generate bounded conventional paths; never walk or glob a root."""
    owner, name = repo.split("/", 1)
    candidates: list[Path] = []
    for configured in roots:
        root = configured.expanduser().resolve()
        candidates.extend([
            root,
            root / owner / name,
            root / owner / f"{name}.git",
            root / f"{owner}__{name}",
            root / f"{owner}__{name}.git",
            root / name,
            root / f"{name}.git",
        ])
    output: list[Path] = []
    seen: set[Path] = set()
    for path in candidates:
        if path not in seen and path.is_dir():
            seen.add(path)
            output.append(path)
    return output


def _remote_identity(repo: Path) -> str | None:
    result = _run_git(repo, ["remote", "get-url", "origin"])
    return canonical_repo(result.stdout.strip()) if result.returncode == 0 else None


def _is_git_repo(repo: Path) -> bool:
    bare = _run_git(repo, ["rev-parse", "--is-bare-repository"])
    if bare.returncode:
        return False
    if bare.stdout.strip() == "true":
        git_dir = _run_git(repo, ["rev-parse", "--absolute-git-dir"])
        return git_dir.returncode == 0 and Path(git_dir.stdout.strip()).resolve() == repo.resolve()
    top = _run_git(repo, ["rev-parse", "--show-toplevel"])
    return top.returncode == 0 and Path(top.stdout.strip()).resolve() == repo.resolve()


def _object_exists(repo: Path, commit: str) -> bool:
    return _run_git(repo, ["cat-file", "-e", f"{commit}^{{commit}}"]).returncode == 0


def _tree_digest(repo: Path, commit: str) -> tuple[str, str] | None:
    tree = _run_git(repo, ["rev-parse", f"{commit}^{{tree}}"])
    listing = _run_git(repo, ["ls-tree", "-r", "--full-tree", commit])
    if tree.returncode or listing.returncode or not FULL_SHA_RE.fullmatch(tree.stdout.strip()):
        return None
    return tree.stdout.strip().lower(), hashlib.sha256(listing.stdout.encode()).hexdigest()


def _patch_applies(repo: Path, commit: str, patch: str) -> bool:
    # A temporary index materializes the base tree without touching HEAD or worktree.
    with tempfile.TemporaryDirectory(prefix="stage12551-index-") as temp:
        index = str(Path(temp) / "index")
        env = {"GIT_INDEX_FILE": index}
        if _run_git(repo, ["read-tree", commit], env=env).returncode:
            return False
        result = _run_git(
            repo,
            ["apply", "--cached", "--check", "--whitespace=nowarn", "-"],
            env=env,
            input_text=patch,
        )
        return result.returncode == 0


def verify_mirrors(record: dict[str, Any], roots: Iterable[Path]) -> dict[str, Any]:
    key = source_key(record)
    assert key is not None
    repo_id = key[2]
    commit = str(record["base_commit"]).lower()
    paths = mirror_candidates(repo_id, roots)
    if not paths:
        return {"status": "unresolved", "reasons": ["configured_local_git_mirror_missing"]}

    verified: list[dict[str, Any]] = []
    failures: list[str] = []
    for path in paths:
        if not _is_git_repo(path):
            continue
        if _remote_identity(path) != repo_id:
            failures.append("canonical_upstream_remote_identity_mismatch")
            continue
        if not _object_exists(path, commit):
            failures.append("authoritative_base_commit_git_object_missing")
            continue
        tree = _tree_digest(path, commit)
        if tree is None:
            failures.append("clean_base_tree_digest_unavailable")
            continue
        if not _patch_applies(path, commit, record["patch"]):
            failures.append("authoritative_patch_not_applicable_at_base")
            continue
        verified.append({
            "mirror_path": str(path),
            "commit": commit,
            "commit_object_verified": True,
            "canonical_upstream_remote": repo_id,
            "upstream_remote_verified": True,
            "base_tree_object": tree[0],
            "clean_tree_sha256": tree[1],
            "patch_applicability_verified": True,
        })
    if len(verified) == 1:
        return {"status": "resolved", "checkout": verified[0]}
    if len(verified) > 1:
        return {"status": "blocked", "reasons": ["multiple_verified_local_mirrors_ambiguous"]}
    blocked = {"canonical_upstream_remote_identity_mismatch", "authoritative_patch_not_applicable_at_base"}
    status = "blocked" if blocked.intersection(failures) else "unresolved"
    return {"status": status, "reasons": sorted(set(failures)) or ["configured_local_git_mirror_unverifiable"]}


def resolve_rows(
    recovery_rows: list[dict[str, Any]],
    source_rows: list[dict[str, Any]],
    mirror_roots: Iterable[Path],
) -> dict[str, list[dict[str, Any]]]:
    """Resolve exact dataset+instance records and reject every ambiguity."""
    index: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in source_rows:
        if authoritative_source_record(row):
            key = source_key(row)
            assert key is not None
            index[key[:2]].append(row)

    resolved: list[dict[str, Any]] = []
    unresolved: list[dict[str, Any]] = []
    conflicting: list[dict[str, Any]] = []
    for recovery in recovery_rows:
        identity = recovery_identity(recovery)
        matches = index.get(identity, [])
        unique = {stable_hash(row): row for row in matches}
        matches = [unique[digest] for digest in sorted(unique)]
        if not matches:
            unresolved.append(_base(recovery, ["authoritative_upstream_source_record_missing"], "unresolved"))
            continue

        binding_errors = sorted({
            reason
            for row in matches
            for reason in recovery_binding_errors(recovery, row)
        })
        if binding_errors:
            conflicting.append(_base(
                recovery,
                ["authoritative_source_binding_conflict", *binding_errors],
                "blocked",
            ))
            continue

        semantic = {(source_key(row)[2], str(row["base_commit"]).lower(), stable_hash(row["patch"])) for row in matches}  # type: ignore[index]
        if len(semantic) != 1:
            reasons = ["authoritative_source_records_conflict"]
            if len({item[1] for item in semantic}) > 1:
                reasons.append("conflicting_authoritative_base_commits")
            if len({item[0] for item in semantic}) > 1:
                reasons.append("conflicting_authoritative_repo_identities")
            if len({item[2] for item in semantic}) > 1:
                reasons.append("conflicting_authoritative_patches")
            conflicting.append(_base(recovery, reasons, "blocked"))
            continue

        source = matches[0]
        verification = verify_mirrors(source, mirror_roots)
        if verification["status"] != "resolved":
            target = conflicting if verification["status"] == "blocked" else unresolved
            target.append(_base(recovery, verification["reasons"], verification["status"]))
            continue
        key = source_key(source)
        assert key is not None
        row = _base(recovery, [], "resolved_checkout_candidate")
        row.update({
            "canonical_repo": key[2],
            "base_commit": str(source["base_commit"]).lower(),
            "authoritative_source_record_sha256": stable_hash(source),
            "patch_sha256": hashlib.sha256(source["patch"].encode()).hexdigest(),
            "checkout_binding": verification["checkout"],
        })
        resolved.append(row)
    return {"resolved": resolved, "unresolved": unresolved, "conflicting": conflicting}


def build_summary(
    recovery_rows: list[dict[str, Any]],
    adapter_paths: list[Path],
    source_rows: list[dict[str, Any]],
    mirror_roots: list[Path],
    result: dict[str, list[dict[str, Any]]],
) -> dict[str, Any]:
    reasons = Counter(
        reason
        for kind in ("unresolved", "conflicting")
        for row in result[kind]
        for reason in row["blocking_reasons"]
    )
    return {
        "stage": STAGE,
        "stage12550_recovery_rows_loaded": len(recovery_rows),
        "configured_metadata_adapter_count": len(adapter_paths),
        "metadata_rows_loaded": len(source_rows),
        "authoritative_metadata_rows_accepted": sum(authoritative_source_record(row) for row in source_rows),
        "configured_git_mirror_root_count": len(mirror_roots),
        "resolved_checkout_candidate_count": len(result["resolved"]),
        "unresolved_worklist_count": len(result["unresolved"]),
        "ambiguous_or_conflicting_count": len(result["conflicting"]),
        "reason_counts": dict(sorted(reasons.items())),
        "filesystem_search_bounded_to_configured_roots": True,
        "trajectory_or_shell_sha_trusted": False,
        "metadata_similarity_trusted": False,
        "protected_universe_status": "unresolved_separate_gate",
        **ZERO_FLAGS,
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=INPUT)
    parser.add_argument("--metadata-adapter", type=Path, action="append", default=[])
    parser.add_argument("--git-mirror-root", type=Path, action="append", default=[])
    parser.add_argument("--output-dir", type=Path, default=OUT)
    parser.add_argument("--summary", type=Path, default=SUMMARY)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    recovery = read_jsonl(args.input)
    source_rows = [row for path in args.metadata_adapter for row in read_adapter(path)]
    result = resolve_rows(recovery, source_rows, args.git_mirror_root)
    write_jsonl(args.output_dir / RESOLVED_OUT.name, result["resolved"])
    write_jsonl(args.output_dir / UNRESOLVED_OUT.name, result["unresolved"])
    write_jsonl(args.output_dir / CONFLICT_OUT.name, result["conflicting"])
    summary = build_summary(recovery, args.metadata_adapter, source_rows, args.git_mirror_root, result)
    write_json(args.output_dir / OUT_SUMMARY.name, summary)
    write_json(args.summary, summary)
    print(json.dumps(summary, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
