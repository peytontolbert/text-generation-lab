#!/usr/bin/env python3
"""Recover same-source patch evidence from existing local git objects.

This stage is read-only. It may inspect JSONL artifacts and run read-only git
plumbing/diff commands against already-present local repositories. It must not
run tests, train models, install packages, fetch/clone/pull, or mutate repos.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
LEVEL_2 = "level_2_patch_context_no_execution"

FORBIDDEN_PATH_PARTS = {
    ".cache",
    ".git",
    ".mypy_cache",
    ".pytest_cache",
    ".tox",
    ".venv",
    "__pycache__",
    "node_modules",
    "target",
    "venv",
}


def as_path(value: str | Path) -> Path:
    path = Path(value)
    return path if path.is_absolute() else ROOT / path


def json_dump(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def jsonl_write(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")


def iter_jsonl(path: Path):
    with path.open("r", encoding="utf-8", errors="ignore") as handle:
        for line_no, line in enumerate(handle, 1):
            line = line.strip()
            if not line:
                continue
            try:
                yield line_no, json.loads(line)
            except Exception as exc:
                yield line_no, {"_json_error": str(exc), "_line_no": line_no}


def stable_id(prefix: str, *parts: Any) -> str:
    raw = "\n".join(json.dumps(part, sort_keys=True, default=str) for part in parts)
    return f"{prefix}_{hashlib.sha256(raw.encode()).hexdigest()[:16]}"


def source_ref_parts(ref: str) -> tuple[Path, int | None]:
    if ":" in ref:
        maybe_path, maybe_line = ref.rsplit(":", 1)
        if maybe_line.isdigit():
            return as_path(maybe_path), int(maybe_line)
    return as_path(ref), None


def load_source_row(ref: str, source_record_id: str) -> dict[str, Any] | None:
    path, line_no = source_ref_parts(ref)
    if not path.exists():
        return None
    for current_line, row in iter_jsonl(path):
        if line_no is not None and current_line != line_no:
            continue
        row_id = str(row.get("episode_id") or row.get("seed_id") or row.get("source_record_id") or row.get("id") or "")
        if line_no is not None or row_id == source_record_id or source_record_id in json.dumps(row, sort_keys=True, default=str):
            return row
    return None


def nested(row: dict[str, Any], *keys: str) -> Any:
    value: Any = row
    for key in keys:
        if not isinstance(value, dict):
            return None
        value = value.get(key)
    return value


def changed_paths(row: dict[str, Any]) -> list[str]:
    paths: list[str] = []
    for item in row.get("changes") or []:
        if isinstance(item, dict):
            value = item.get("path") or item.get("file")
        else:
            value = item
        if value:
            paths.append(normalize_repo_path(str(value), str(row.get("repo_id") or "")))
    return sorted(set(paths))


def normalize_repo_path(path: str, repo_id: str = "") -> str:
    path = path.strip().lstrip("/")
    if repo_id and path.startswith(repo_id + "/"):
        path = path[len(repo_id) + 1 :]
    return path


def has_bad_path(paths: list[str]) -> bool:
    for path in paths:
        parts = {part.lower() for part in Path(path).parts}
        if parts & FORBIDDEN_PATH_PARTS:
            return True
    return False


def infer_language(paths: list[str]) -> str:
    counts: Counter[str] = Counter()
    for path in paths:
        suffix = Path(path).suffix.lower()
        if suffix == ".py":
            counts["python"] += 1
        elif suffix == ".rs":
            counts["rust"] += 1
        elif suffix in {".c", ".cc", ".cpp", ".cxx", ".h", ".hpp"}:
            counts["c_cpp"] += 1
        elif suffix in {".js", ".jsx", ".ts", ".tsx", ".html", ".css", ".json"}:
            counts["web_js_ts_html"] += 1
    return counts.most_common(1)[0][0] if counts else "unknown"


def run_git(repo: Path, args: list[str], *, text: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=text,
    )


def commit_parent(repo: Path, commit: str) -> tuple[str | None, list[str], str | None]:
    proc = run_git(repo, ["cat-file", "-p", commit])
    if proc.returncode != 0:
        return None, [], proc.stderr.strip() or proc.stdout.strip()
    parents = []
    for line in proc.stdout.splitlines():
        if line.startswith("parent "):
            parents.append(line.split()[1])
    if len(parents) != 1:
        return None, parents, "merge_or_root_commit_parent_count_not_one"
    return parents[0], parents, None


def recover_diff(repo: Path, parent: str, commit: str) -> tuple[bytes | None, str | None]:
    proc = subprocess.run(
        ["git", "-C", str(repo), "diff", "--binary", "--full-index", parent, commit],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if proc.returncode != 0:
        return None, proc.stderr.decode("utf-8", errors="replace").strip()
    if not proc.stdout.strip():
        return None, "empty_diff"
    return proc.stdout, None


def diff_paths(repo: Path, parent: str, commit: str) -> tuple[list[str], str | None]:
    proc = run_git(repo, ["diff", "--name-only", parent, commit])
    if proc.returncode != 0:
        return [], proc.stderr.strip() or proc.stdout.strip()
    return sorted(set(line.strip() for line in proc.stdout.splitlines() if line.strip())), None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage12200-dir", required=True)
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--allow-local-git-readonly", action="store_true")
    parser.add_argument("--no-network", action="store_true")
    parser.add_argument("--no-tests", action="store_true")
    parser.add_argument("--no-training", action="store_true")
    parser.add_argument("--no-repo-mutation", action="store_true")
    args = parser.parse_args()

    required_flags = [args.allow_local_git_readonly, args.no_network, args.no_tests, args.no_training, args.no_repo_mutation]
    if not all(required_flags):
        raise SystemExit("all no-execution boundary flags plus --allow-local-git-readonly are required")

    stage12200_dir = as_path(args.stage12200_dir)
    out_dir = as_path(args.out_dir)
    diff_dir = out_dir / "diffs"
    out_dir.mkdir(parents=True, exist_ok=True)
    diff_dir.mkdir(parents=True, exist_ok=True)

    recovered_episode_records: list[dict[str, Any]] = []
    recovered_patch_traces: list[dict[str, Any]] = []
    evidence_manifest: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []

    for _, blocked in iter_jsonl(stage12200_dir / "blocked_candidates.jsonl"):
        source_family = blocked.get("source_family")
        if source_family != "external_commit_episode":
            rejected.append({**blocked, "recovery_status": "rejected", "recovery_blockers": ["not_external_commit_episode"]})
            continue
        source_row = load_source_row(str(blocked.get("source_record_ref") or ""), str(blocked.get("source_record_id") or ""))
        if not source_row:
            rejected.append({**blocked, "recovery_status": "rejected", "recovery_blockers": ["source_row_missing"]})
            continue
        repo = Path(str(nested(source_row, "source_metadata", "repo_root") or ""))
        commit = str(nested(source_row, "source_metadata", "commit_sha") or "")
        expected_paths = changed_paths(source_row)
        blockers: list[str] = []
        if not repo.exists() or not (repo / ".git").exists():
            blockers.append("local_git_repo_missing")
        if not commit:
            blockers.append("commit_after_missing")
        if not expected_paths:
            blockers.append("changed_paths_missing")
        if has_bad_path(expected_paths):
            blockers.append("source_path_dependency_cache_or_build_artifact")
        if blockers:
            rejected.append({**blocked, "recovery_status": "rejected", "recovery_blockers": blockers})
            continue
        parent, parents, parent_error = commit_parent(repo, commit)
        if parent_error or not parent:
            rejected.append({**blocked, "recovery_status": "rejected", "recovery_blockers": ["parent_commit_unresolved"], "parent_candidates": parents, "git_error": parent_error})
            continue
        names, names_error = diff_paths(repo, parent, commit)
        if names_error:
            rejected.append({**blocked, "recovery_status": "rejected", "recovery_blockers": ["diff_name_recovery_failed"], "git_error": names_error})
            continue
        expected_set = set(expected_paths)
        diff_set = set(names)
        if not expected_set.issubset(diff_set):
            rejected.append({**blocked, "recovery_status": "rejected", "recovery_blockers": ["changed_path_mismatch"], "expected_paths": sorted(expected_set), "diff_paths": sorted(diff_set)[:200]})
            continue
        diff_bytes, diff_error = recover_diff(repo, parent, commit)
        if diff_error or not diff_bytes:
            rejected.append({**blocked, "recovery_status": "rejected", "recovery_blockers": ["diff_recovery_failed"], "git_error": diff_error})
            continue
        digest = hashlib.sha256(diff_bytes).hexdigest()
        diff_path = diff_dir / f"{digest}.patch"
        diff_path.write_bytes(diff_bytes)
        episode_id = stable_id("stage12201_episode", blocked.get("source_record_id"), parent, commit)
        patch_id = stable_id("stage12201_patch", digest)
        language = infer_language(expected_paths)
        selected_tests = source_row.get("selected_tests") or []
        episode = {
            "episode_id": episode_id,
            "source_stage": "stage12201_patch_evidence_recovery",
            "source_family": source_family,
            "source_record_ref": blocked.get("source_record_ref"),
            "source_record_id": blocked.get("source_record_id"),
            "same_source_lineage_id": blocked.get("same_source_lineage_id") or commit,
            "root_id": str(repo),
            "repo_family": str(source_row.get("repo_id") or repo.name),
            "language": language,
            "task_ref": stable_id("task", source_row.get("goal"), commit),
            "repo_commit_before": parent,
            "repo_commit_after": commit,
            "admission_level": LEVEL_2,
            "projection_permissions": ["patch_intent", "edit_localization", "patch_minimality_risk"],
            "has_real_patch_diff": True,
            "has_command_output": False,
            "has_verifier_result": False,
            "has_state_before": True,
            "has_state_after_or_update": bool(source_row.get("target")),
            "has_stop_decision": False,
            "candidate_action_count": 0,
            "semantic_hard_negative_count": 0,
            "changed_paths": expected_paths,
            "selected_tests": selected_tests,
            "strict_eval_eligible": False,
            "train_support_only": True,
        }
        patch = {
            "patch_id": patch_id,
            "episode_id": episode_id,
            "patch_kind": "read_only_git_diff_parent_to_commit",
            "diff_ref": str(diff_path),
            "diff_digest": digest,
            "repo_commit_before": parent,
            "repo_commit_after": commit,
            "changed_paths": expected_paths,
            "diff_changed_paths": names,
            "changed_file_count": len(expected_paths),
            "apply_evidence_ref": None,
            "no_patch_reason": None,
        }
        recovered_episode_records.append(episode)
        recovered_patch_traces.append(patch)
        evidence_manifest.append({
            "episode_id": episode_id,
            "source_record_id": blocked.get("source_record_id"),
            "repo_root": str(repo),
            "commit_before": parent,
            "commit_after": commit,
            "diff_ref": str(diff_path),
            "diff_digest": digest,
            "source_record_ref": blocked.get("source_record_ref"),
            "recovery_method": "git_cat_file_parent_plus_git_diff_readonly",
            "level_after_recovery": LEVEL_2,
            "training_allowed": False,
        })

    jsonl_write(out_dir / "recovered_episode_records.jsonl", recovered_episode_records)
    jsonl_write(out_dir / "recovered_patch_traces.jsonl", recovered_patch_traces)
    jsonl_write(out_dir / "recovery_evidence_manifest.jsonl", evidence_manifest)
    jsonl_write(out_dir / "rejected_candidates.jsonl", rejected)

    language_counts = Counter(row["language"] for row in recovered_episode_records)
    repo_count = len({row["repo_family"] for row in recovered_episode_records})
    reject_counts = Counter(code for row in rejected for code in row.get("recovery_blockers", []))
    summary = {
        "stage": "stage12201_patch_evidence_recovery",
        "artifact_type": "read_only_patch_evidence_recovery",
        "training_executed": False,
        "training_allowed": False,
        "network_used": False,
        "tests_executed": False,
        "repo_mutation_performed": False,
        "source_stage": str(stage12200_dir),
        "recovered_level_2_episode_count": len(recovered_episode_records),
        "recovered_level_3_episode_count": 0,
        "recovered_patch_trace_count": len(recovered_patch_traces),
        "rejected_candidate_count": len(rejected),
        "repository_count": repo_count,
        "language_counts": dict(sorted(language_counts.items())),
        "top_recovery_blockers": reject_counts.most_common(20),
        "decision": "patch_evidence_recovered_training_still_blocked" if recovered_episode_records else "training_blocked_no_recovered_patch_evidence",
        "why_training_blocked": [
            "stage12201_is_read_only_recovery_not_training",
            "level_3_closed_loop_episodes_still_zero",
            "verifier_command_output_not_recovered",
            "candidate_action_sets_not_recovered",
        ],
        "output_artifacts": {
            "recovered_episode_records": str(out_dir / "recovered_episode_records.jsonl"),
            "recovered_patch_traces": str(out_dir / "recovered_patch_traces.jsonl"),
            "recovery_evidence_manifest": str(out_dir / "recovery_evidence_manifest.jsonl"),
            "rejected_candidates": str(out_dir / "rejected_candidates.jsonl"),
            "admission_audit": str(out_dir / "admission_audit.json"),
            "summary": str(out_dir / "summary.json"),
        },
    }
    audit = {
        **summary,
        "admission_rules": {
            "diff_ref_actual_patch_required": True,
            "diff_digest_sha256_required": True,
            "repo_commit_before_must_be_parent": True,
            "external_commit_max_level": LEVEL_2,
            "stage12190_rows_never_counted_as_patch_episodes": True,
        },
    }
    json_dump(out_dir / "admission_audit.json", audit)
    json_dump(out_dir / "summary.json", summary)
    json_dump(ROOT / "runs/summaries/stage12201_patch_evidence_recovery.json", summary)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
