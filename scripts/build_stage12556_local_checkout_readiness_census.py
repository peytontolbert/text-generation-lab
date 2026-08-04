#!/usr/bin/env python3
"""Census train-only local Git objects that can seed isolated replay."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12556_local_checkout_readiness_census"
INPUT = ROOT / "runs/local/artifacts/stage12555_swe_rebench_identity_adapter/exact_task_authority_bindings.jsonl"
OUT = ROOT / "runs/local/artifacts" / STAGE
SUMMARY = ROOT / "runs/summaries" / f"{STAGE}.json"
DEFAULT_ROOTS = (
    Path("/data/agentkernel/benchmarks/repo_cache"),
    Path("/data/agentkernel/other_repos"),
    Path("/data/parametergolf/helpful_repos"),
)
SHA40 = re.compile(r"^[0-9a-f]{40}$", re.I)
ZERO_FLAGS = {
    "admission_allowed": False, "training_allowed": False, "gpu_allowed": False,
    "replay_allowed": False, "root_credit": False, "repair_credit": False,
    "strict_eval_eligible": False, "level3_credit": False,
}


def run(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", "-C", str(repo), *args], text=True, capture_output=True, timeout=20, check=False)


def canonical_repo(value: Any) -> str | None:
    text = str(value or "").strip()
    if text.startswith("git@github.com:"):
        text = text.split(":", 1)[1]
    elif "://" in text:
        parsed = urlparse(text)
        if parsed.hostname not in {"github.com", "www.github.com"}:
            return None
        text = parsed.path
    text = text.strip("/")
    if text.endswith(".git"):
        text = text[:-4]
    parts = text.split("/")
    return f"{parts[0].lower()}/{parts[1].lower()}" if len(parts) == 2 else None


def discover(roots: list[Path]) -> list[Path]:
    repos: set[Path] = set()
    for root in roots:
        if not root.is_dir():
            continue
        for current, directories, _ in os.walk(root):
            path = Path(current)
            if ".git" in directories:
                repos.add(path)
                directories[:] = []
            elif path.name.endswith(".git") and (path / "HEAD").is_file():
                repos.add(path)
                directories[:] = []
            elif len(path.relative_to(root).parts) >= 4:
                directories[:] = []
    return sorted(repos)


def mirror_record(path: Path) -> dict[str, Any]:
    origin = run(path, "config", "--get", "remote.origin.url").stdout.strip()
    shallow = run(path, "rev-parse", "--is-shallow-repository").stdout.strip() == "true"
    partial = bool(run(path, "config", "--get-regexp", r"^remote\..*\.promisor$").stdout.strip())
    return {
        "path": str(path), "origin_url": origin, "canonical_origin": canonical_repo(origin),
        "shallow": shallow, "partial_clone": partial,
    }


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()] if path.is_file() else []


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows))


def build(bindings: list[dict[str, Any]], mirror_roots: list[Path]) -> dict[str, Any]:
    train = [row for row in bindings if row.get("policy_split") == "train"]
    protected_count = len(bindings) - len(train)
    mirrors = [mirror_record(path) for path in discover(mirror_roots)]
    by_repo: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for mirror in mirrors:
        if mirror["canonical_origin"]:
            by_repo[mirror["canonical_origin"]].append(mirror)

    ready: list[dict[str, Any]] = []
    blocked: list[dict[str, Any]] = []
    for row in train:
        identity = row.get("task_identity") or {}
        repo = canonical_repo(identity.get("canonical_repo"))
        commit = str(identity.get("base_commit") or "").lower()
        candidates: list[dict[str, Any]] = []
        reasons: list[str] = []
        for mirror in by_repo.get(repo or "", []):
            local_reasons = []
            if mirror["shallow"]:
                local_reasons.append("shallow_repository")
            if not SHA40.fullmatch(commit) or run(Path(mirror["path"]), "cat-file", "-e", f"{commit}^{{commit}}").returncode:
                local_reasons.append("authoritative_base_commit_object_missing")
            closure = run(Path(mirror["path"]), "rev-list", "--objects", "--missing=print", commit)
            missing_objects = [line for line in closure.stdout.splitlines() if line.startswith("?")]
            if closure.returncode or missing_objects:
                local_reasons.append("authoritative_commit_object_closure_incomplete")
            refs = run(Path(mirror["path"]), "for-each-ref", "--format=%(refname)", f"--contains={commit}", "refs/heads", "refs/remotes", "refs/tags")
            ref_names = sorted(line for line in refs.stdout.splitlines() if line.strip())
            if not ref_names:
                local_reasons.append("base_commit_not_reachable_from_local_ref")
            tree = run(Path(mirror["path"]), "rev-parse", f"{commit}^{{tree}}").stdout.strip().lower() if not local_reasons else ""
            if not SHA40.fullmatch(tree):
                local_reasons.append("authoritative_base_tree_unavailable")
            if not local_reasons:
                candidates.append({**mirror, "base_tree": tree, "covering_refs": ref_names})
            else:
                reasons.extend(local_reasons)
        if not by_repo.get(repo or ""):
            reasons.append("canonical_origin_mirror_missing")
        if len(candidates) > 1:
            reasons.append("multiple_valid_local_mirrors_ambiguous")
        if len(candidates) != 1:
            blocked.append({
                "record_type": "stage12556_blocked_checkout_readiness_v1",
                "candidate_id": row.get("candidate_id"), "canonical_repo": repo,
                "language": identity.get("language"), "blocking_reasons": sorted(set(reasons)),
                **ZERO_FLAGS,
            })
            continue
        mirror = candidates[0]
        certificate = {
            "canonical_repo": repo, "origin_url": mirror["origin_url"],
            "base_commit": commit, "base_tree": mirror["base_tree"],
            "covering_refs": mirror["covering_refs"], "mirror_path": mirror["path"],
        }
        ready.append({
            "record_type": "stage12556_local_checkout_object_ready_v1",
            "candidate_id": row.get("candidate_id"), "task_key": row.get("task_key"),
            "language": identity.get("language"), "checkout_object_certificate": certificate,
            "certificate_sha256": hashlib.sha256(json.dumps(certificate, sort_keys=True).encode()).hexdigest(),
            "lineage_status": "provisional_local_origin_and_reachable_ref_only",
            "next_required_proofs": ["independent_upstream_lineage", "disposable_clean_worktree", "same_command_fail_patch_pass", "candidate_action_set", "chosen_action", "state_update", "stop_continue"],
            "protected_content_used": False, **ZERO_FLAGS,
        })

    language_ready = Counter(row["language"] for row in ready)
    language_blocked = Counter(row["language"] for row in blocked)
    summary = {
        "stage": STAGE, "record_type": "stage12556_local_checkout_readiness_census_summary_v1",
        "input_binding_count": len(bindings), "train_binding_count": len(train),
        "protected_binding_count_excluded": protected_count,
        "discovered_git_repository_count": len(mirrors),
        "exact_checkout_object_ready_count": len(ready), "blocked_count": len(blocked),
        "unique_ready_repo_count": len({row["checkout_object_certificate"]["canonical_repo"] for row in ready}),
        "ready_language_counts": dict(sorted(language_ready.items())),
        "blocked_language_counts": dict(sorted(language_blocked.items())),
        "mirror_roots": [str(path) for path in mirror_roots],
        "protected_rows_enumerated_in_outputs": False,
        "gold_or_reference_fields_read": False, "root_count_increment": 0,
        "level3_count_increment": 0,
        "default_disposition": "readiness_only_no_replay_or_lineage_credit",
        **ZERO_FLAGS,
    }
    return {"ready": ready, "blocked": blocked, "summary": summary}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=INPUT)
    parser.add_argument("--mirror-root", type=Path, action="append", default=[])
    parser.add_argument("--output-dir", type=Path, default=OUT)
    parser.add_argument("--summary", type=Path, default=SUMMARY)
    args = parser.parse_args()
    result = build(read_jsonl(args.input), args.mirror_root or list(DEFAULT_ROOTS))
    write_jsonl(args.output_dir / "checkout_object_ready.jsonl", result["ready"])
    write_jsonl(args.output_dir / "blocked_checkout_readiness.jsonl", result["blocked"])
    write_json(args.output_dir / "summary.json", result["summary"])
    write_json(args.summary, result["summary"])
    print(json.dumps(result["summary"], sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
