#!/usr/bin/env python3
"""Locate exact TRAIN task commits in explicitly configured local Git mirrors."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
from collections import Counter
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12556_authoritative_checkout_locator"
INPUT = ROOT / "runs/local/artifacts/stage12555_swe_rebench_identity_adapter/exact_task_authority_bindings.jsonl"
OUT = ROOT / "runs/local/artifacts" / STAGE
SUMMARY = ROOT / "runs/summaries" / f"{STAGE}.json"
SHA40 = re.compile(r"^[0-9a-f]{40}$", re.I)
SAFE_PART = re.compile(r"^[A-Za-z0-9_.-]+$")
FORBIDDEN_FIELDS = {"patch", "test_patch", "problem_statement", "pr_description", "FAIL_TO_PASS", "PASS_TO_PASS"}
ZERO_FLAGS = {"training_allowed": False, "admission_allowed": False, "replay_allowed": False,
              "root_credit": False, "repair_credit": False, "level_3_credit": False}


def stable_hash(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()).hexdigest()


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
    if len(parts) != 2 or not all(SAFE_PART.fullmatch(part) for part in parts):
        return None
    return f"{parts[0].lower()}/{parts[1].lower()}"


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    rows = []
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if line.strip():
            row = json.loads(line)
            if not isinstance(row, dict):
                raise ValueError(f"{path}:{number}: expected object")
            rows.append(row)
    return rows


def write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def run_git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    for key in ("GIT_ALTERNATE_OBJECT_DIRECTORIES", "GIT_OBJECT_DIRECTORY", "GIT_REPLACE_REF_BASE", "GIT_SHALLOW_FILE"):
        env.pop(key, None)
    env.update({"GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_SYSTEM": os.devnull,
                "GIT_CONFIG_GLOBAL": os.devnull, "GIT_NO_REPLACE_OBJECTS": "1",
                "GIT_OPTIONAL_LOCKS": "0", "GIT_TERMINAL_PROMPT": "0"})
    return subprocess.run(["git", "-C", str(repo), *args], text=True, stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE, check=False, timeout=15, env=env)


def candidates(repo_id: str, roots: Iterable[Path]) -> list[Path]:
    owner, name = repo_id.split("/")
    found: set[Path] = set()
    for configured in roots:
        root = configured.expanduser().resolve()
        for raw in (root, root / owner / name, root / owner / f"{name}.git",
                    root / f"{owner}__{name}", root / f"{owner}__{name}.git"):
            try:
                path = raw.resolve()
                path.relative_to(root)
            except (OSError, ValueError):
                continue
            if path.is_dir():
                found.add(path)
    return sorted(found, key=str)


def inspect_mirror(path: Path, repo_id: str, commit: str) -> tuple[dict[str, Any] | None, str | None]:
    bare = run_git(path, "rev-parse", "--is-bare-repository")
    top = run_git(path, "rev-parse", "--show-toplevel")
    if bare.returncode or (bare.stdout.strip() != "true" and (top.returncode or Path(top.stdout.strip()).resolve() != path)):
        return None, "not_exact_git_repository_root"
    origin = run_git(path, "remote", "get-url", "origin")
    if origin.returncode or canonical_repo(origin.stdout.strip()) != repo_id:
        return None, "canonical_origin_identity_mismatch"
    shallow = run_git(path, "rev-parse", "--is-shallow-repository")
    replacements = run_git(path, "for-each-ref", "--format=%(refname)", "refs/replace")
    git_dir = run_git(path, "rev-parse", "--absolute-git-dir")
    if shallow.returncode or shallow.stdout.strip() != "false" or replacements.returncode or replacements.stdout.strip():
        return None, "unsafe_or_incomplete_object_store"
    if git_dir.returncode:
        return None, "unsafe_or_incomplete_object_store"
    gd = Path(git_dir.stdout.strip())
    if (gd / "info/grafts").exists() or (gd / "objects/info/alternates").exists():
        return None, "unsafe_or_incomplete_object_store"
    obj = run_git(path, "cat-file", "-e", f"{commit}^{{commit}}")
    if obj.returncode:
        return None, "authoritative_base_commit_missing"
    peeled = run_git(path, "rev-parse", f"{commit}^{{commit}}")
    tree = run_git(path, "rev-parse", f"{commit}^{{tree}}")
    tree_type = run_git(path, "cat-file", "-t", tree.stdout.strip()) if not tree.returncode else tree
    if peeled.returncode or peeled.stdout.strip().lower() != commit or tree.returncode or not SHA40.fullmatch(tree.stdout.strip()) or tree_type.returncode or tree_type.stdout.strip() != "tree":
        return None, "exact_commit_or_tree_verification_failed"
    return {"mirror_path": str(path), "canonical_origin": repo_id, "origin_verified": True,
            "base_commit": commit, "commit_object_verified": True,
            "base_tree": tree.stdout.strip().lower(), "tree_object_verified": True}, None


def build(rows: list[dict[str, Any]], roots: list[Path], max_worklist: int) -> dict[str, Any]:
    if max_worklist < 0:
        raise ValueError("max_worklist must be non-negative")
    certs, blocked = [], []
    excluded = Counter()
    for row in sorted(rows, key=lambda r: (str(r.get("candidate_id") or ""), stable_hash(r))):
        split = row.get("policy_split")
        if split != "train":
            excluded[str(split or "missing") ] += 1
            continue
        identity = row.get("task_identity") if isinstance(row.get("task_identity"), dict) else {}
        repo_id = canonical_repo(identity.get("canonical_repo"))
        commit = str(identity.get("base_commit") or "").lower()
        reasons: list[str] = []
        verified: list[dict[str, Any]] = []
        if repo_id is None or not SHA40.fullmatch(commit):
            reasons.append("invalid_authoritative_task_identity")
        else:
            paths = candidates(repo_id, roots)
            if not paths:
                reasons.append("configured_local_mirror_missing")
            for path in paths:
                result, reason = inspect_mirror(path, repo_id, commit)
                if result:
                    verified.append(result)
                elif reason:
                    reasons.append(reason)
            if len(verified) > 1:
                reasons.append("multiple_verified_local_mirrors_ambiguous")
            elif len(verified) == 1:
                checkout = verified[0]
                payload = {"candidate_id": row.get("candidate_id"), "task_identity_sha256": row.get("task_identity_sha256"),
                           "task_snapshot_sha256": row.get("task_snapshot_sha256"), "policy_split": "train",
                           "canonical_repo": repo_id, "base_commit": commit, "base_tree": checkout["base_tree"],
                           "canonical_origin": repo_id, "mirror_path": checkout["mirror_path"]}
                certs.append({"record_type": "stage12556_trusted_lineage_certificate_v1", **payload,
                              "checkout": checkout, "lineage_certificate_sha256": stable_hash(payload),
                              "forbidden_task_fields_read": [], "current_head_inference_used": False,
                              "repo_name_only_guess_used": False, "patch_similarity_used": False, **ZERO_FLAGS})
                continue
        blocked.append({"record_type": "stage12556_blocked_checkout_locator_v1", "candidate_id": row.get("candidate_id"),
                        "blocking_reasons": sorted(set(reasons)) or ["mirror_unverifiable"], **ZERO_FLAGS})
    certs.sort(key=lambda r: (r["canonical_repo"], r["base_commit"], str(r["candidate_id"])))
    work = [{"record_type": "stage12556_replay_readiness_work_item_v1", "ordinal": i,
             "candidate_id": c["candidate_id"], "lineage_certificate_sha256": c["lineage_certificate_sha256"],
             "mirror_path": c["mirror_path"], "base_commit": c["base_commit"], "base_tree": c["base_tree"],
             "readiness_status": "checkout_located_pending_replay", **ZERO_FLAGS}
            for i, c in enumerate(certs[:max_worklist])]
    reason_counts = Counter(reason for row in blocked for reason in row["blocking_reasons"])
    summary = {"stage": STAGE, "record_type": "stage12556_authoritative_checkout_locator_summary_v1",
               "input_count": len(rows), "train_input_count": len(certs) + len(blocked),
               "excluded_non_train_counts": dict(sorted(excluded.items())), "configured_mirror_roots": [str(p) for p in roots],
               "filesystem_search_bounded_to_fixed_paths_under_configured_roots": True,
               "trusted_lineage_certificate_count": len(certs), "blocked_count": len(blocked),
               "replay_worklist_count": len(work), "max_replay_worklist": max_worklist,
               "reason_counts": dict(sorted(reason_counts.items())), "forbidden_task_fields_read": [],
               "current_head_inference_used": False, "patch_similarity_used": False, "repo_name_only_guess_used": False,
               **ZERO_FLAGS}
    return {"certificates": certs, "blocked": blocked, "worklist": work, "summary": summary}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=INPUT)
    parser.add_argument("--git-mirror-root", type=Path, action="append", default=[])
    parser.add_argument("--max-worklist", type=int, default=256)
    parser.add_argument("--output-dir", type=Path, default=OUT)
    parser.add_argument("--summary", type=Path, default=SUMMARY)
    args = parser.parse_args()
    result = build(read_jsonl(args.input), args.git_mirror_root, args.max_worklist)
    write_jsonl(args.output_dir / "trusted_lineage_certificates.jsonl", result["certificates"])
    write_jsonl(args.output_dir / "blocked_checkout_locators.jsonl", result["blocked"])
    write_jsonl(args.output_dir / "replay_readiness_worklist.jsonl", result["worklist"])
    write_json(args.output_dir / "summary.json", result["summary"])
    write_json(args.summary, result["summary"])
    print(json.dumps(result["summary"], sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
