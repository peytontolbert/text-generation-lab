#!/usr/bin/env python3
"""Build Stage12450 post-Stage12449 Level-3 supply control board."""
from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12450_post_stage12449_level3_supply_control_board"
OUT = ROOT / "runs/local/artifacts" / STAGE
SUMMARY = ROOT / "runs/summaries" / f"{STAGE}.json"

STAGE12445_SUMMARY = ROOT / "runs/summaries/stage12445_adapter_execution_return_ingest_and_level3_gate.json"
STAGE12448_SUMMARY = ROOT / "runs/summaries/stage12448_executor_shard_scale_and_admission_control.json"
STAGE12449_SUMMARY = ROOT / "runs/summaries/stage12449_external_repair_trace_fail_to_pass_projection.json"
STAGE12445_CANDIDATES = ROOT / "runs/local/artifacts/stage12445_adapter_execution_return_ingest_and_level3_gate/admitted_level3_candidates.jsonl"
STAGE12449_BLOCKED = ROOT / "runs/local/artifacts/stage12449_external_repair_trace_fail_to_pass_projection/blocked_artifact.json"

ZERO = {
    "training_allowed": False,
    "admission_allowed": False,
    "execution_allowed": False,
    "execution_performed_by_stage": False,
    "emitted_training_rows": 0,
    "sealed_eval_rows_emitted": 0,
}

FORBIDDEN_PUBLIC_KEYS = {"path", "paths", "url", "urls", "uri", "command", "command_text", "commands", "stdout", "stderr", "output", "outputs", "diff", "patch", "patch_body", "source", "source_path", "source_text", "private_locator", "raw", "raw_text", "trace", "trace_text", "issue_body"}
ALLOWED_KEY_CONTEXT_RE = re.compile(r"(policy|emitted|forbidden|required|slot|slots|schema|hash|hashes|ref|refs|class|status|proof|reason|contract|request|count|scan|supply|stage)", re.I)
RAW_LEAK_RE = re.compile(r"https?://|www\.|diff --git|@@ |^\+\+\+ |^--- |<<<<<<<|>>>>>>>|(?<![A-Za-z0-9_])/(?:[A-Za-z0-9._-]+/){2,}[A-Za-z0-9._-]+|\b(?:stdout:|stderr:|terminal output:|command output:|git clone\s+\S|git apply\s+\S|python -c|bash -)\b", re.I | re.M)


def read_json(path: Path) -> Any:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            value = json.loads(line)
            if isinstance(value, dict):
                rows.append(value)
    return rows


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, sort_keys=True) + "\n")


def stable_hash(value: Any, n: int = 24) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(f"{STAGE}:{payload}".encode()).hexdigest()[:n]


def file_hash(path: Path, n: int = 24) -> str:
    if not path.exists() or not path.is_file():
        return "missing"
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()[:n]


def scan(label: str, value: Any) -> list[str]:
    issues = []
    leaf = label.rsplit('.', 1)[-1].split('[', 1)[0].lower()
    if leaf in FORBIDDEN_PUBLIC_KEYS and not ALLOWED_KEY_CONTEXT_RE.search(label):
        issues.append(f"{label}:forbidden_public_key")
    if isinstance(value, str):
        if RAW_LEAK_RE.search(value):
            issues.append(f"{label}:raw_public_leak:{stable_hash(value)}")
    elif isinstance(value, dict):
        for k, v in value.items():
            issues.extend(scan(f"{label}.{k}", v))
    elif isinstance(value, list):
        for i, v in enumerate(value):
            issues.extend(scan(f"{label}[{i}]", v))
    return issues


def build() -> tuple[dict[str, Any], list[dict[str, Any]]]:
    s45 = read_json(STAGE12445_SUMMARY)
    s48 = read_json(STAGE12448_SUMMARY)
    s49 = read_json(STAGE12449_SUMMARY)
    candidates = read_jsonl(STAGE12445_CANDIDATES)
    blocked = read_json(STAGE12449_BLOCKED)
    ret = s45.get("return_ingest_counters", {}) if isinstance(s45.get("return_ingest_counters"), dict) else {}
    target_supply = int(s48.get("target_countable_supply") or 500)
    prior_supply = int(s48.get("current_countable_supply_before_future_ingest") or 190)
    validated_delta = int(s45.get("level3_candidate_count") or 0)
    stage12449_fail_to_pass_delta = int(s49.get("projected_return_row_count") or 0)
    effective_supply_after_validated_delta = prior_supply + validated_delta
    remaining_gap = max(0, target_supply - effective_supply_after_validated_delta)
    language_counts = Counter()
    request_counts = Counter()
    for row in candidates:
        request_counts.update([str(row.get("admission_status") or "unknown")])
        # Stage12445 admitted records intentionally expose only proof hashes/statuses, not language.
    next_actions = [
        {
            "priority": 1,
            "action": "produce_or_block_remaining_stage12445_return_files",
            "reason": "remaining Stage12445 return slots are missing or empty-blocked; no further training should occur until nonempty proof-complete returns are materialized and ingested",
        },
        {
            "priority": 2,
            "action": "expand_external_fail_to_pass_source_supply",
            "reason": "Stage12449 found zero proof-complete external FAIL_TO_PASS rows; external FAIL_TO_PASS floor still needs fifteen more before the minimum gate",
        },
        {
            "priority": 3,
            "action": "materialize_non_web_selected_test_transition_returns",
            "reason": "Rust/C/C++/Python selected-test transition lane is the best non-web path toward balanced maintainer tasks",
        },
    ]
    present_return_file_count = int(ret.get("present_return_file_count") or 0)
    empty_return_file_count = int(ret.get("empty_return_file_count") or 0)
    if validated_delta > 0:
        decision = "validated_level3_candidate_delta_recorded_remaining_returns_incomplete_training_blocked"
    elif present_return_file_count > 0 or empty_return_file_count > 0:
        decision = "zero_validated_level3_candidate_delta_some_empty_blocked_returns_training_blocked"
    else:
        decision = "zero_validated_level3_candidate_delta_all_return_files_missing_training_blocked"
    artifact = {
        "stage": STAGE,
        "record_type": "post_stage12449_level3_supply_control_board_v1",
        "decision": decision,
        **ZERO,
        "prior_countable_supply_from_stage12448": prior_supply,
        "target_countable_supply": target_supply,
        "stage12445_validated_level3_candidate_delta": validated_delta,
        "effective_supply_after_validated_delta": effective_supply_after_validated_delta,
        "remaining_gap_to_500_after_validated_delta": remaining_gap,
        "stage12445_expected_return_count": ret.get("expected_return_count", 0),
        "stage12445_present_return_file_count": ret.get("present_return_file_count", 0),
        "stage12445_empty_return_file_count": ret.get("empty_return_file_count", 0),
        "stage12445_found_return_file_count": ret.get("found_return_file_count", 0),
        "stage12445_missing_return_file_count": ret.get("missing_return_file_count", 0),
        "stage12445_missing_return_count_by_kind": ret.get("missing_return_count_by_kind", {}),
        "stage12445_empty_return_count_by_kind": ret.get("empty_return_count_by_kind", {}),
        "stage12445_return_row_count": ret.get("return_row_count", 0),
        "stage12445_admitted_return_row_count": ret.get("admitted_return_row_count", 0),
        "stage12449_projected_return_row_count": s49.get("projected_return_row_count", 0),
        "stage12449_blocked_record_count": s49.get("blocked_record_count", 0),
        "stage12449_blocked_reason_counts": blocked.get("reason_code_counts", {}) if isinstance(blocked, dict) else {},
        "external_fail_to_pass_floor": 15,
        "external_fail_to_pass_validated_delta": stage12449_fail_to_pass_delta,
        "external_fail_to_pass_remaining_floor_gap": max(0, 15 - stage12449_fail_to_pass_delta),
        "selected_test_verifier_observation_validated_delta": validated_delta,
        "stage12448_requested_floor_exceeds_known_public_denominator": s48.get("requested_floor_exceeds_known_public_denominator"),
        "stage12448_feasibility_status": s48.get("feasibility_status"),
        "next_actions": next_actions,
        "source_fingerprints": {
            "stage12445_summary_sha256_24": file_hash(STAGE12445_SUMMARY),
            "stage12448_summary_sha256_24": file_hash(STAGE12448_SUMMARY),
            "stage12449_summary_sha256_24": file_hash(STAGE12449_SUMMARY),
            "stage12445_candidates_sha256_24": file_hash(STAGE12445_CANDIDATES),
            "stage12449_blocked_sha256_24": file_hash(STAGE12449_BLOCKED),
        },
        "claim_boundary": "This is a scoreboard/control artifact. It records a validated candidate delta after Stage12445 but emits no training/eval rows and does not authorize training.",
        "guardrail_scan": {},
        "guardrail_scan_passed": False,
        "raw_leak_count": 0,
        "schema_issue_count": 0,
        "summary_hash": "pending",
    }
    issues = scan("artifact", artifact)
    artifact["guardrail_scan"] = {
        "scan_passed": not issues,
        "issue_count": len(set(issues)),
        "issues": sorted(set(issues)),
        "raw_leak_count": len({i for i in issues if "raw_public_leak" in i or "forbidden_public_key" in i}),
        "scan_scope": "stage12450_public_safe_control_board",
    }
    artifact["guardrail_scan_passed"] = artifact["guardrail_scan"]["scan_passed"]
    artifact["raw_leak_count"] = artifact["guardrail_scan"]["raw_leak_count"]
    artifact["summary_hash"] = stable_hash({k: v for k, v in artifact.items() if k != "summary_hash"})
    return artifact, next_actions


def main() -> None:
    artifact, next_actions = build()
    OUT.mkdir(parents=True, exist_ok=True)
    write_json(OUT / f"{STAGE}.json", artifact)
    write_json(OUT / "summary.json", artifact)
    write_json(SUMMARY, artifact)
    write_jsonl(OUT / "next_actions.jsonl", next_actions)
    print(json.dumps({
        "stage": artifact["stage"],
        "decision": artifact["decision"],
        "stage12445_validated_level3_candidate_delta": artifact["stage12445_validated_level3_candidate_delta"],
        "effective_supply_after_validated_delta": artifact["effective_supply_after_validated_delta"],
        "remaining_gap_to_500_after_validated_delta": artifact["remaining_gap_to_500_after_validated_delta"],
        "stage12445_present_return_file_count": artifact["stage12445_present_return_file_count"],
        "stage12445_empty_return_file_count": artifact["stage12445_empty_return_file_count"],
        "stage12445_missing_return_file_count": artifact["stage12445_missing_return_file_count"],
        "external_fail_to_pass_remaining_floor_gap": artifact["external_fail_to_pass_remaining_floor_gap"],
        "training_allowed": artifact["training_allowed"],
        "guardrail_scan_passed": artifact["guardrail_scan_passed"],
        "raw_leak_count": artifact["raw_leak_count"],
    }, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
