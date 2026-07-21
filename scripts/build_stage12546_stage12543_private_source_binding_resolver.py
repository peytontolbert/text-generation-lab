#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import re
import subprocess
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12546_stage12543_private_source_binding_resolver"
OUT = ROOT / "runs/local/artifacts" / STAGE
SUMMARY = ROOT / "runs/summaries" / f"{STAGE}.json"

STAGE12543_WORK_ITEMS = ROOT / "runs/local/artifacts/stage12543_remaining_gap_execution_request/stage12543_remaining_gap_execution_work_items.jsonl"
STAGE12209_LOG_INDEX = ROOT / "runs/local/artifacts/stage12209_command_log_candidate_scanner/clean_candidate_command_logs.jsonl"
STAGE12541_ROWS = ROOT / "runs/local/artifacts/stage12541_command_log_no_test_insufficient_evidence_preflight/stage12541_command_log_insufficient_evidence_preflight_rows.jsonl"

PRIVATE_BINDINGS_NAME = "stage12546_private_source_bindings.jsonl"
PUBLIC_BINDINGS_NAME = "stage12546_public_binding_audit_rows.jsonl"
AUDIT_NAME = "stage12546_private_source_binding_audit.json"

SELECTED_RE = re.compile(r"(?:^|\s)(?:-R|--exact|-k)(?:\s|=)|(?:^|\s)[^\s]+\.py(?::|\s|$)", re.I)
ENV_RE = re.compile(
    r"file or directory not found|offline mode|failed to (?:download|resolve)|"
    r"no matching package|module not found|dependency|network|timeout",
    re.I,
)
NO_TEST_RE = re.compile(r"no tests? (?:were )?(?:found|collected|ran)|total tests:\s*0", re.I)


def namespaced_hash(namespace: str, value: Any, n: int = 24) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(f"{namespace}:{payload}".encode("utf-8")).hexdigest()[:n]


def full_hash(value: Any) -> str:
    if isinstance(value, bytes):
        payload = value
    elif isinstance(value, str):
        payload = value.encode("utf-8")
    else:
        payload = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def file_hash(path: Path) -> str:
    if not path.exists() or not path.is_file():
        return "missing"
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8", errors="replace") as handle:
        for line_no, line in enumerate(handle, 1):
            if not line.strip():
                continue
            value = json.loads(line)
            if isinstance(value, dict):
                value["__line_no"] = line_no
                rows.append(value)
    return rows


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")


def risky_claims_false() -> dict[str, bool]:
    return {
        "training_allowed": False,
        "countable_train_support": False,
        "strict_eval_eligible": False,
        "source_heldout_admissible": False,
        "level3_admitted": False,
        "level4_admitted": False,
        "patch_trace_admitted": False,
        "repair_claim_admitted": False,
        "fail_to_pass_claim_admitted": False,
    }


def git_value(cwd: Path, args: list[str]) -> str | None:
    try:
        result = subprocess.run(
            ["git", "-C", str(cwd), *args],
            check=False,
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if result.returncode != 0:
        return None
    return result.stdout.strip()


def stage12543_repo_hash(repo: str) -> str:
    return namespaced_hash("stage12543_remaining_gap_execution_request", repo)


def stage12543_line_hash(line_no: int, repo: str) -> str:
    return namespaced_hash(
        "stage12543_remaining_gap_execution_request",
        {"line": line_no, "repo": repo},
    )


def stage12541_line_hash(line_no: int) -> str:
    return namespaced_hash(
        "stage12541_command_log_no_test_insufficient_evidence_preflight",
        {"source": str(STAGE12209_LOG_INDEX), "line": line_no},
    )


def source_evidence_class(row: dict[str, Any], consumed_lines: set[str]) -> tuple[str, list[str]]:
    command = str(row.get("command") or "")
    output = "\n".join(
        str(row.get(key) or "") for key in ("stdout_tail_preview", "stderr_tail_preview")
    )
    blockers: list[str] = []
    if SELECTED_RE.search(command) or "selected" in str(row.get("path") or "").lower():
        blockers.append("selected_or_exact_test_scope")
    if ENV_RE.search(output):
        blockers.append("environment_or_invalid_command_failure")
    if stage12541_line_hash(int(row["__line_no"])) in consumed_lines:
        blockers.append("already_consumed_stage12541_source")
    if blockers:
        return "blocked_source_command", blockers
    if NO_TEST_RE.search(output):
        return "direct_zero_test_or_no_test_observation", []
    if int(row.get("returncode") or 0) != 0:
        return "direct_nonzero_behavior_or_build_observation", []
    return "direct_pass_current_state_observation", []


def target_matches(target: str, evidence_class: str) -> bool:
    return (
        target == "FAIL_CURRENT_STATE"
        and evidence_class == "direct_nonzero_behavior_or_build_observation"
    ) or (
        target == "INSUFFICIENT_EVIDENCE"
        and evidence_class == "direct_zero_test_or_no_test_observation"
    )


def build_binding(
    item: dict[str, Any],
    source_rows: list[dict[str, Any]],
    consumed_lines: set[str],
) -> tuple[dict[str, Any], dict[str, Any]]:
    repo_matches = [
        row for row in source_rows
        if stage12543_repo_hash(str(row.get("repo_family") or "")) == item.get("repo_family_hash")
    ]
    expected_line_hashes = set(item.get("source_log_line_hashes") or [])
    matched = [
        row for row in repo_matches
        if stage12543_line_hash(int(row["__line_no"]), str(row.get("repo_family") or ""))
        in expected_line_hashes
    ]
    repos = sorted({str(row.get("repo_family") or "") for row in matched if row.get("repo_family")})
    cwds = sorted({str(row.get("cwd") or "") for row in matched if row.get("cwd")})
    repo = repos[0] if len(repos) == 1 else None
    cwd = Path(cwds[0]) if len(cwds) == 1 else None
    commit = git_value(cwd, ["rev-parse", "HEAD"]) if cwd and cwd.exists() else None
    tree = git_value(cwd, ["rev-parse", "HEAD^{tree}"]) if cwd and cwd.exists() else None
    dirty = git_value(cwd, ["status", "--porcelain=v1", "-uno"]) if cwd and cwd.exists() else None

    candidate_commands: list[dict[str, Any]] = []
    for row in matched:
        evidence_class, blockers = source_evidence_class(row, consumed_lines)
        candidate_commands.append(
            {
                "source_line_number": row["__line_no"],
                "source_record_path": row.get("path"),
                "repo_family": row.get("repo_family"),
                "cwd": row.get("cwd"),
                "command": row.get("command"),
                "prior_returncode": row.get("returncode"),
                "prior_status": row.get("status"),
                "evidence_class": evidence_class,
                "blocker_codes": blockers,
                "target_match": target_matches(str(item.get("target_status_needed") or ""), evidence_class),
            }
        )

    binding_blockers: list[str] = []
    if len(repos) != 1:
        binding_blockers.append("repo_family_not_uniquely_resolved")
    if len(cwds) != 1:
        binding_blockers.append("repo_root_not_uniquely_resolved")
    if cwd is None or not cwd.exists():
        binding_blockers.append("repo_root_missing")
    if commit is None or tree is None:
        binding_blockers.append("immutable_checkout_identity_missing")
    if len(matched) != len(expected_line_hashes):
        binding_blockers.append("source_line_hash_set_not_fully_resolved")

    admissible = [row for row in candidate_commands if row["target_match"] and not row["blocker_codes"]]
    if binding_blockers:
        outcome = "binding_blocked"
    elif not admissible:
        outcome = "no_admissible_command"
    elif len(admissible) > 1:
        outcome = "multiple_admissible_commands_manual_selection_required"
    else:
        outcome = "binding_resolved_execution_candidate"

    private = {
        "stage": STAGE,
        "record_type": "stage12546_private_source_binding_v1",
        "work_item_id": item.get("work_item_id"),
        "target_status_quota_metadata": item.get("target_status_needed"),
        "repo_family": repo,
        "repo_root": str(cwd) if cwd else None,
        "commit_sha": commit,
        "tree_sha": tree,
        "dirty_status": dirty,
        "candidate_commands": candidate_commands,
        "binding_outcome": outcome,
        "binding_blocker_codes": sorted(binding_blockers),
        "execution_authorized": False,
        **risky_claims_false(),
    }
    public = {
        "stage": STAGE,
        "record_type": "stage12546_public_source_binding_audit_v1",
        "work_item_id_digest": full_hash(item.get("work_item_id")),
        "request_repo_family_digest": full_hash(item.get("repo_family_hash")),
        "language_family": item.get("language_family"),
        "target_status_quota_metadata": item.get("target_status_needed"),
        "source_reference_count": len(expected_line_hashes),
        "source_reference_match_count": len(matched),
        "repo_family_unique": len(repos) == 1,
        "repo_root_unique": len(cwds) == 1,
        "repo_root_exists": bool(cwd and cwd.exists()),
        "immutable_checkout_identity_present": commit is not None and tree is not None,
        "repo_commit_digest": full_hash(commit) if commit else "missing",
        "repo_tree_digest": full_hash(tree) if tree else "missing",
        "dirty_state_digest": full_hash(dirty) if dirty is not None else "missing",
        "candidate_command_count": len(candidate_commands),
        "admissible_command_count": len(admissible),
        "binding_outcome": outcome,
        "binding_blocker_codes": sorted(binding_blockers),
        "execution_authorized": False,
        **risky_claims_false(),
    }
    return private, public


def build() -> dict[str, Any]:
    OUT.mkdir(parents=True, exist_ok=True)
    work_items = read_jsonl(STAGE12543_WORK_ITEMS)
    source_rows = read_jsonl(STAGE12209_LOG_INDEX)
    consumed_lines = {
        str(row.get("source_line_hash"))
        for row in read_jsonl(STAGE12541_ROWS)
        if row.get("source_line_hash")
    }

    private_rows: list[dict[str, Any]] = []
    public_rows: list[dict[str, Any]] = []
    for item in work_items:
        private, public = build_binding(item, source_rows, consumed_lines)
        private_rows.append(private)
        public_rows.append(public)

    private_path = OUT / PRIVATE_BINDINGS_NAME
    public_path = OUT / PUBLIC_BINDINGS_NAME
    audit_path = OUT / AUDIT_NAME
    write_jsonl(private_path, private_rows)
    write_jsonl(public_path, public_rows)

    outcomes = Counter(row["binding_outcome"] for row in public_rows)
    target_counts = Counter(row["target_status_quota_metadata"] for row in public_rows)
    ready_counts = Counter(
        row["target_status_quota_metadata"]
        for row in public_rows
        if row["binding_outcome"] == "binding_resolved_execution_candidate"
    )
    decision = (
        "private_bindings_resolved_execution_candidates_present_no_execution"
        if ready_counts
        else "private_bindings_resolved_no_admissible_commands_no_execution"
    )
    audit = {
        "stage": STAGE,
        "record_type": "stage12546_private_source_binding_audit_v1",
        "decision": decision,
        "work_item_count": len(work_items),
        "binding_outcome_counts": dict(sorted(outcomes.items())),
        "target_status_work_item_counts": dict(sorted(target_counts.items())),
        "execution_ready_target_counts": dict(sorted(ready_counts.items())),
        "source_artifact_digest": file_hash(STAGE12209_LOG_INDEX),
        "request_artifact_digest": file_hash(STAGE12543_WORK_ITEMS),
        "private_manifest_digest": file_hash(private_path),
        "public_manifest_digest": file_hash(public_path),
        "private_source_binding_required": True,
        "execution_performed": False,
        "new_preflight_row_count": 0,
        "new_countable_train_support_count": 0,
        **risky_claims_false(),
    }
    write_json(audit_path, audit)

    summary = {
        **audit,
        "record_type": "stage12546_stage12543_private_source_binding_resolver_summary_v1",
        "claim_boundary": "Stage12546 resolves Stage12543 salted work items back to private local source records and audits command admissibility. It performs no commands, emits no verifier observations, and admits no training, root, Level-3, patch, repair, or evaluation rows.",
        "authoritative_countable_root_progress_delta": 0,
        "artifact_refs": {
            "private_bindings": str(private_path),
            "public_binding_audit_rows": str(public_path),
            "audit": str(audit_path),
            "summary": str(SUMMARY),
        },
    }
    write_json(SUMMARY, summary)
    return summary


if __name__ == "__main__":
    print(json.dumps(build(), indent=2, sort_keys=True))
