#!/usr/bin/env python3
"""Build Stage12472 locator-augmented non-Bears work order.

Stage12472 merges Stage12471 public locator refs into Stage12469 work items.
It produces public-safe locator-augmented work items for the subset with real
candidate locator hashes, and blocked records for the rest.

This is still not proof, not admission, not execution, and not training.
"""
from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12472_locator_augmented_non_bears_work_order"
OUT_DIR = ROOT / "runs/local/artifacts" / STAGE
SUMMARY_OUT = ROOT / "runs/summaries" / f"{STAGE}.json"

STAGE12469 = "stage12469_non_bears_private_proof_return_work_order"
STAGE12471 = "stage12471_private_source_locator_index_preflight"
WORK_ITEMS_IN = ROOT / "runs/local/artifacts" / STAGE12469 / "private_return_work_items.jsonl"
LOCATOR_REFS_IN = ROOT / "runs/local/artifacts" / STAGE12471 / "public_locator_index_refs.jsonl"
BLOCKED_IN = ROOT / "runs/local/artifacts" / STAGE12471 / "blocked_locator_requests.jsonl"
STAGE12471_SUMMARY = ROOT / "runs/summaries" / f"{STAGE12471}.json"

AUGMENTED_OUT = OUT_DIR / "locator_augmented_work_items.jsonl"
BLOCKED_OUT = OUT_DIR / "blocked_locator_augmented_requests.jsonl"
GUARDRAIL_OUT = OUT_DIR / "guardrail_scan.json"
LOCAL_SUMMARY_OUT = OUT_DIR / "summary.json"

EXPECTED_GAP = 15
REQUIRED_LOCATOR_FIELDS = [
    "source_adapter_candidate_ref_hash",
    "private_locator_ref_hash",
    "source_root_label_hash",
    "lane_candidate_family_hash",
    "private_execution_context_ref_hash",
]
FALSE_GUARDS = {
    "training_allowed": False,
    "admission_allowed": False,
    "packaging_allowed": False,
    "execution_performed_by_stage": False,
    "hydration_performed_by_stage": False,
    "replay_performed_by_stage": False,
    "network_performed_by_stage": False,
}
ZERO_GUARDS = {
    "external_comparable_repair_credit_count": 0,
    "remaining_external_fail_to_pass_gap": EXPECTED_GAP,
    "emitted_training_rows": 0,
    "sealed_eval_rows": 0,
}
FORBIDDEN_PUBLIC_KEYS = {
    "path", "paths", "url", "urls", "uri", "uris", "command", "commands",
    "stdout", "stderr", "diff", "patch", "raw", "raw_text", "source",
    "source_text", "repo", "repo_id", "repo_name", "repository", "sha",
    "commit", "commit_sha", "content", "file_content", "dataset_file",
    "source_record_ref", "instance_id", "trajectory_id",
}
PUBLIC_SAFE_KEY_RE = re.compile(r"(hash|hashes|ref_hash|count|status|stage|lane|language|guardrail|blocker|policy|allowed|credit|locator)", re.I)
RAW_LEAK_RE = re.compile(r"https?://|www\.|diff --git|@@ |^\+\+\+ |^--- |(?<![A-Za-z0-9_])/(?:[A-Za-z0-9._-]+/){2,}[A-Za-z0-9._-]+|\b(?:stdout|stderr|traceback|command output|terminal output|git clone|git apply|pytest\s|python -c|bash -|sh -|curl\s)\b|\b[0-9a-f]{40}\b", re.I | re.M)
HASH_RE = re.compile(r"^(?:[0-9a-f]{24}|[0-9a-f]{32}|[0-9a-f]{40}|[0-9a-f]{64}|sha256:[0-9a-f]{64})$", re.I)


def stable_hash(value: Any, n: int = 24) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(f"{STAGE}:{payload}".encode()).hexdigest()[:n]


def file_hash(path: Path, n: int = 24) -> str:
    if not path.exists() or not path.is_file():
        return "missing"
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()[:n]


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists(): return {}
    value = json.loads(path.read_text(encoding="utf-8"))
    return value if isinstance(value, dict) else {}


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows=[]
    if not path.exists(): return rows
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            v=json.loads(line)
            if isinstance(v, dict): rows.append(v)
    return rows


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True)+"\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as h:
        for row in rows: h.write(json.dumps(row, sort_keys=True)+"\n")


def public_scan(label: str, value: Any) -> list[str]:
    issues=[]
    leaf=label.rsplit('.',1)[-1].split('[',1)[0].lower()
    if leaf in FORBIDDEN_PUBLIC_KEYS and not PUBLIC_SAFE_KEY_RE.search(label):
        issues.append(f"{label}:forbidden_public_key")
    if isinstance(value, str):
        if RAW_LEAK_RE.search(value): issues.append(f"{label}:raw_pattern:{stable_hash(value)}")
    elif isinstance(value, dict):
        for k,v in value.items(): issues.extend(public_scan(f"{label}.{k}", v))
    elif isinstance(value, list):
        for i,v in enumerate(value): issues.extend(public_scan(f"{label}[{i}]", v))
    return issues


def valid_hash(value: Any) -> bool:
    return isinstance(value, str) and bool(HASH_RE.fullmatch(value))


def main() -> int:
    work_items = read_jsonl(WORK_ITEMS_IN)
    locator_refs = read_jsonl(LOCATOR_REFS_IN)
    blocked_stage12471 = read_jsonl(BLOCKED_IN)
    stage12471 = read_json(STAGE12471_SUMMARY)
    by_item = {r.get("work_order_item_ref_hash"): r for r in locator_refs}
    augmented=[]
    blocked=[]
    for item in work_items:
        item_ref = item.get("work_order_item_ref_hash")
        loc = by_item.get(item_ref)
        if not loc:
            blocked.append({
                "record_type": "stage12472_blocked_locator_augmented_request_v1",
                "work_order_item_ref_hash": item_ref,
                "proof_request_ref_hash": item.get("proof_request_ref_hash"),
                "lane_ref": item.get("lane_ref"),
                "language_priority_hint": item.get("language_priority_hint"),
                "blocker_reasons": ["no_stage12471_public_locator_ref_for_work_item"],
                **FALSE_GUARDS,
                **ZERO_GUARDS,
            })
            continue
        missing=[field for field in REQUIRED_LOCATOR_FIELDS if not valid_hash(loc.get(field))]
        lang_mismatch = loc.get("language_priority_hint") != item.get("language_priority_hint")
        if missing or lang_mismatch or loc.get("locator_is_proof") is not False:
            reasons=[f"missing_or_invalid_locator_field:{f}" for f in missing]
            if lang_mismatch: reasons.append("locator_language_mismatch")
            if loc.get("locator_is_proof") is not False: reasons.append("locator_claims_proof")
            blocked.append({
                "record_type": "stage12472_blocked_locator_augmented_request_v1",
                "work_order_item_ref_hash": item_ref,
                "proof_request_ref_hash": item.get("proof_request_ref_hash"),
                "lane_ref": item.get("lane_ref"),
                "language_priority_hint": item.get("language_priority_hint"),
                "blocker_reasons": sorted(reasons),
                **FALSE_GUARDS,
                **ZERO_GUARDS,
            })
            continue
        row = dict(item)
        for field in REQUIRED_LOCATOR_FIELDS:
            row[field] = loc[field]
        row["language_family_label"] = loc.get("language_family_label")
        row["candidate_language_verified"] = loc.get("candidate_language_verified") is True
        row["locator_augmented"] = True
        row["locator_is_proof"] = False
        row["source_stage_refs"] = [STAGE12469, STAGE12471]
        row.update(FALSE_GUARDS)
        row.update(ZERO_GUARDS)
        augmented.append(row)
    payload={"augmented": augmented, "blocked": blocked}
    issues=public_scan("stage12472_public", payload)
    lang_counts=Counter(r.get("language_family_label") for r in augmented)
    lane_counts=Counter(r.get("lane_ref") for r in augmented)
    blocker_counts=Counter(reason for r in blocked for reason in r.get("blocker_reasons", []))
    decision = "locator_augmented_work_order_ready_zero_credit" if augmented and not issues else "blocked_no_locator_augmented_work_order_zero_credit"
    summary={
        "stage": STAGE,
        "record_type": "stage12472_locator_augmented_non_bears_work_order_summary_v1",
        "decision": decision,
        "claim_boundary": "Locator-augmented work items are executor logistics only, not proof, admission, or training data.",
        "input_stage_refs": [STAGE12469, STAGE12471],
        "work_item_count": len(work_items),
        "locator_augmented_work_item_count": len(augmented),
        "blocked_work_item_count": len(blocked),
        "language_counts_from_verified_locator_candidates": dict(sorted(lang_counts.items())),
        "lane_counts_from_locator_candidates": dict(sorted(lane_counts.items())),
        "blocker_counts": dict(sorted(blocker_counts.items())),
        "stage12471_private_locator_record_count": stage12471.get("private_locator_record_count"),
        "required_locator_fields": REQUIRED_LOCATOR_FIELDS,
        "next_recommendation": "rerun_locator_preflight_on_stage12472_augmented_work_items_then_build_private_executor_request_for_actionable_subset_only",
        "guardrail_scan_passed": not issues,
        "raw_leak_count": len(issues),
        "schema_issue_count": 0 if not issues else len(issues),
        **FALSE_GUARDS,
        **ZERO_GUARDS,
        "artifact_refs": {
            "locator_augmented_work_items": "stage12472_locator_augmented_work_items_jsonl",
            "blocked_locator_augmented_requests": "stage12472_blocked_locator_augmented_requests_jsonl",
            "guardrail_scan": "stage12472_guardrail_scan_json",
        },
        "source_input_hashes": {
            "stage12469_work_items": file_hash(WORK_ITEMS_IN),
            "stage12471_public_locator_refs": file_hash(LOCATOR_REFS_IN),
            "stage12471_blocked_locator_requests": file_hash(BLOCKED_IN),
        },
    }
    summary["summary_hash"] = stable_hash({k:v for k,v in summary.items() if k != "summary_hash"})
    guardrail={"stage": STAGE, "scan_passed": not issues, "raw_leak_count": len(issues), "issue_hashes": [stable_hash(i) for i in issues[:50]], "policy": "public artifacts only contain hash refs/status/counts; no raw locators"}
    write_jsonl(AUGMENTED_OUT, augmented)
    write_jsonl(BLOCKED_OUT, blocked)
    write_json(GUARDRAIL_OUT, guardrail)
    write_json(LOCAL_SUMMARY_OUT, summary)
    write_json(SUMMARY_OUT, summary)
    print(json.dumps({"stage": STAGE, "decision": decision, "locator_augmented_work_item_count": len(augmented), "blocked_work_item_count": len(blocked), "external_comparable_repair_credit_count": 0, "remaining_external_fail_to_pass_gap": EXPECTED_GAP, "guardrail_scan_passed": not issues, "raw_leak_count": len(issues)}, indent=2, sort_keys=True))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
