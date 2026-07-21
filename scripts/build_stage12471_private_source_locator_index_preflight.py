#!/usr/bin/env python3
"""Build Stage12471 private source locator index.

This stage bridges Stage12469 lane-level work items to concrete private source
adapter candidates. It emits a private locator index containing raw/local source
record refs for executor use, and a public-safe summary containing only hashes,
counts, lanes, and blocker codes.

It does not execute, hydrate, replay, train, admit, package, or claim repair
credit. Locators are not proof; they only make a later private executor
possible.
"""
from __future__ import annotations

import hashlib
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12471_private_source_locator_index_preflight"
OUT_DIR = ROOT / "runs/local/artifacts" / STAGE
SUMMARY_OUT = ROOT / "runs/summaries" / f"{STAGE}.json"

STAGE12469 = "stage12469_non_bears_private_proof_return_work_order"
STAGE12470 = "stage12470_non_bears_private_return_locator_preflight"
WORK_ITEMS = ROOT / "runs/local/artifacts" / STAGE12469 / "private_return_work_items.jsonl"
STAGE12470_SUMMARY = ROOT / "runs/summaries" / f"{STAGE12470}.json"

OPEN_SWE_CANDIDATES = [
    ROOT / "runs/local/artifacts/stage12327_external_adapter_preflight/open_swe_priority_capped_trace_support_candidates.jsonl",
    ROOT / "runs/local/artifacts/stage12327_external_adapter_preflight/open_swe_trace_support_candidates.jsonl",
]
REPRESENTATIVE_REVIEW = ROOT / "runs/local/artifacts/stage12442_representative_private_review_and_source_adapter_expansion_request/representative_private_review_packet_manifest.jsonl"
ADAPTER_REQUESTS = ROOT / "runs/local/artifacts/stage12444_adapter_execution_request_manifest/adapter_execution_requests.jsonl"

PRIVATE_LOCATOR_OUT = OUT_DIR / "private_source_locator_index.raw_private.jsonl"
PUBLIC_LOCATOR_OUT = OUT_DIR / "public_locator_index_refs.jsonl"
BLOCKED_OUT = OUT_DIR / "blocked_locator_requests.jsonl"
GUARDRAIL_OUT = OUT_DIR / "guardrail_scan.json"
LOCAL_SUMMARY_OUT = OUT_DIR / "summary.json"

EXPECTED_GAP = 15
TRACE_LANE = "lane_ref_non_bears_trace_transition_repair_proof_preflight"
BENCHMARK_LANE = "lane_ref_non_bears_external_benchmark_patch_log_preflight"
PRIVATE_REVIEW_LANE = "lane_ref_non_bears_private_review_pivot_preflight"

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
    "stdout", "stderr", "diff", "patch", "patch_body", "raw", "raw_text",
    "source", "source_text", "repo", "repo_id", "repo_name", "repository",
    "sha", "commit", "commit_sha", "content", "file_content", "dataset_file",
    "source_record_ref", "instance_id", "trajectory_id",
}
PUBLIC_SAFE_KEY_RE = re.compile(r"(hash|hashes|ref_hash|refs_hash|count|bucket|status|stage|lane|language|guardrail|blocker|policy|allowed|credit)", re.I)
RAW_LEAK_RE = re.compile(
    r"https?://|www\.|diff --git|@@ |^\+\+\+ |^--- |<<<<<<<|>>>>>>>|"
    r"(?<![A-Za-z0-9_])/(?:[A-Za-z0-9._-]+/){2,}[A-Za-z0-9._-]+|"
    r"\b(?:git clone|git apply|pytest\s|python -c|bash -|sh -|curl\s|stdout|stderr|traceback|command output|terminal output)\b|"
    r"\b[0-9a-f]{40}\b",
    re.I | re.M,
)

LANG_MAP = {
    "python": "python",
    "py": "python",
    "rust": "rust",
    "rs": "rust",
    "c": "c_cpp",
    "cpp": "c_cpp",
    "c++": "c_cpp",
    "cuda": "c_cpp",
    "javascript": "web_js_ts_html",
    "typescript": "web_js_ts_html",
    "html": "web_js_ts_html",
    "css": "web_js_ts_html",
    "web_js_ts_html": "web_js_ts_html",
}


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
    if not path.exists():
        return {}
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain object")
    return value


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.exists():
        return rows
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            value = json.loads(line)
            if isinstance(value, dict):
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


def lang_bucket(value: Any) -> str:
    return LANG_MAP.get(str(value or "").strip().lower(), "unknown")


def scan_public(label: str, value: Any) -> list[str]:
    issues: list[str] = []
    leaf = label.rsplit(".", 1)[-1].split("[", 1)[0].lower()
    if leaf in FORBIDDEN_PUBLIC_KEYS and not PUBLIC_SAFE_KEY_RE.search(label):
        issues.append(f"{label}:forbidden_public_key")
    if isinstance(value, str):
        if RAW_LEAK_RE.search(value):
            issues.append(f"{label}:raw_locator_or_content:{stable_hash(value)}")
    elif isinstance(value, dict):
        for key, child in value.items():
            issues.extend(scan_public(f"{label}.{key}", child))
    elif isinstance(value, list):
        for i, child in enumerate(value):
            issues.extend(scan_public(f"{label}[{i}]", child))
    return issues


def load_open_swe_candidates() -> list[dict[str, Any]]:
    seen: set[str] = set()
    out: list[dict[str, Any]] = []
    for path in OPEN_SWE_CANDIDATES:
        for row in read_jsonl(path):
            key = str(row.get("candidate_id") or stable_hash(row))
            if key in seen:
                continue
            seen.add(key)
            row["_source_artifact_ref_hash"] = stable_hash(str(path.relative_to(ROOT)))
            row["_source_artifact_private_path"] = str(path)
            out.append(row)
    return out


def source_record_hash(row: dict[str, Any]) -> str:
    return stable_hash(row.get("source_record_ref") or row)


def make_private_locator(work_item: dict[str, Any], candidate: dict[str, Any]) -> dict[str, Any]:
    source_record_ref = candidate.get("source_record_ref") if isinstance(candidate.get("source_record_ref"), dict) else {}
    source_adapter_candidate_ref_hash = stable_hash({
        "candidate_id": candidate.get("candidate_id"),
        "source_record_ref": source_record_ref,
    })
    private_locator_payload = {
        "source_adapter": candidate.get("source_adapter"),
        "candidate_id": candidate.get("candidate_id"),
        "source_record_ref": source_record_ref,
        "source_artifact_private_path": candidate.get("_source_artifact_private_path"),
    }
    private_execution_context = {
        "candidate_type": candidate.get("candidate_type"),
        "trace_metadata": candidate.get("trace_metadata"),
        "seed_path_hashes": candidate.get("seed_path_hashes"),
        "selected_test_hashes": candidate.get("selected_test_hashes"),
    }
    language = lang_bucket(candidate.get("language_family"))
    return {
        "record_type": "stage12471_private_source_locator_raw_private_v1",
        "work_order_item_ref_hash": work_item.get("work_order_item_ref_hash"),
        "proof_request_id": work_item.get("proof_request_id"),
        "proof_request_ref_hash": work_item.get("proof_request_ref_hash"),
        "lane_ref": work_item.get("lane_ref"),
        "language_priority_hint": work_item.get("language_priority_hint"),
        "language_family_label": language,
        "candidate_language_verified": language != "unknown",
        "source_adapter_candidate_ref_hash": source_adapter_candidate_ref_hash,
        "private_locator_ref_hash": stable_hash(private_locator_payload),
        "source_root_label_hash": stable_hash(candidate.get("repo_family")),
        "lane_candidate_family_hash": stable_hash({
            "lane_ref": work_item.get("lane_ref"),
            "source_adapter": candidate.get("source_adapter"),
            "candidate_type": candidate.get("candidate_type"),
        }),
        "private_execution_context_ref_hash": stable_hash(private_execution_context),
        "raw_private_locator": private_locator_payload,
        "raw_private_execution_context": private_execution_context,
        "locator_is_proof": False,
        "training_allowed": False,
        "admission_allowed": False,
        "packaging_allowed": False,
        "execution_performed_by_stage": False,
        "hydration_performed_by_stage": False,
        "replay_performed_by_stage": False,
        **ZERO_GUARDS,
    }


def public_ref(private: dict[str, Any]) -> dict[str, Any]:
    return {
        "record_type": "stage12471_public_locator_ref_v1",
        "work_order_item_ref_hash": private["work_order_item_ref_hash"],
        "proof_request_ref_hash": private["proof_request_ref_hash"],
        "lane_ref": private["lane_ref"],
        "language_priority_hint": private.get("language_priority_hint"),
        "language_family_label": private.get("language_family_label"),
        "candidate_language_verified": private.get("candidate_language_verified"),
        "source_adapter_candidate_ref_hash": private["source_adapter_candidate_ref_hash"],
        "private_locator_ref_hash": private["private_locator_ref_hash"],
        "source_root_label_hash": private["source_root_label_hash"],
        "lane_candidate_family_hash": private["lane_candidate_family_hash"],
        "private_execution_context_ref_hash": private["private_execution_context_ref_hash"],
        "locator_is_proof": False,
        "training_allowed": False,
        "admission_allowed": False,
        **ZERO_GUARDS,
    }


def main() -> int:
    work_items = read_jsonl(WORK_ITEMS)
    stage12470 = read_json(STAGE12470_SUMMARY)
    open_swe = load_open_swe_candidates()
    review_manifest = read_jsonl(REPRESENTATIVE_REVIEW)
    adapter_requests = read_jsonl(ADAPTER_REQUESTS)

    by_lang: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in open_swe:
        by_lang[lang_bucket(row.get("language_family"))].append(row)

    selected_private: list[dict[str, Any]] = []
    public_rows: list[dict[str, Any]] = []
    blocked: list[dict[str, Any]] = []
    used_candidates: set[str] = set()

    for item in work_items:
        lane = item.get("lane_ref")
        hint = item.get("language_priority_hint")
        if lane != TRACE_LANE:
            blocked.append({
                "record_type": "stage12471_blocked_locator_request_v1",
                "work_order_item_ref_hash": item.get("work_order_item_ref_hash"),
                "proof_request_ref_hash": item.get("proof_request_ref_hash"),
                "lane_ref": lane,
                "language_priority_hint": hint,
                "blocker_reasons": ["no_per_candidate_raw_locator_source_for_lane_yet"],
                "recommended_source": "build_or_attach_candidate_locator_sidecar_for_this_lane",
                "training_allowed": False,
                "admission_allowed": False,
                **ZERO_GUARDS,
            })
            continue
        pool = by_lang.get(str(hint), [])
        if not pool:
            blocked.append({
                "record_type": "stage12471_blocked_locator_request_v1",
                "work_order_item_ref_hash": item.get("work_order_item_ref_hash"),
                "proof_request_ref_hash": item.get("proof_request_ref_hash"),
                "lane_ref": lane,
                "language_priority_hint": hint,
                "blocker_reasons": ["no_candidate_locator_for_requested_language_hint"],
                "training_allowed": False,
                "admission_allowed": False,
                **ZERO_GUARDS,
            })
            continue
        candidate = None
        for row in pool:
            candidate_key = str(row.get("candidate_id") or source_record_hash(row))
            if candidate_key not in used_candidates:
                candidate = row
                used_candidates.add(candidate_key)
                break
        if candidate is None:
            blocked.append({
                "record_type": "stage12471_blocked_locator_request_v1",
                "work_order_item_ref_hash": item.get("work_order_item_ref_hash"),
                "proof_request_ref_hash": item.get("proof_request_ref_hash"),
                "lane_ref": lane,
                "language_priority_hint": hint,
                "blocker_reasons": ["no_unused_candidate_for_language_hint"],
                "training_allowed": False,
                "admission_allowed": False,
                **ZERO_GUARDS,
            })
            continue
        private = make_private_locator(item, candidate)
        selected_private.append(private)
        public_rows.append(public_ref(private))

    public_payload = {"public_locator_refs": public_rows, "blocked": blocked}
    scan_issues = scan_public("stage12471_public", public_payload)
    locator_count = len(public_rows)
    blocked_count = len(blocked)
    language_counts = Counter(row.get("language_family_label") for row in public_rows)
    lane_counts = Counter(row.get("lane_ref") for row in public_rows)
    blocker_counts = Counter(reason for row in blocked for reason in row.get("blocker_reasons", []))

    decision = (
        "private_source_locator_index_ready_for_trace_lane_zero_credit"
        if locator_count and not scan_issues
        else "blocked_no_public_safe_private_locator_index_zero_credit"
    )
    summary = {
        "stage": STAGE,
        "record_type": "stage12471_private_source_locator_index_preflight_summary_v1",
        "decision": decision,
        "claim_boundary": "Private locators make later execution possible; they are not proof, admission, training rows, or repair credit.",
        "input_stage_refs": [STAGE12469, STAGE12470, "stage12327_external_adapter_preflight", "stage12442_representative_private_review_and_source_adapter_expansion_request", "stage12444_adapter_execution_request_manifest"],
        "work_item_count": len(work_items),
        "private_locator_record_count": locator_count,
        "public_locator_ref_count": len(public_rows),
        "blocked_locator_request_count": blocked_count,
        "language_counts_from_located_candidates": dict(sorted(language_counts.items())),
        "lane_counts_from_located_candidates": dict(sorted(lane_counts.items())),
        "blocker_counts": dict(sorted(blocker_counts.items())),
        "stage12470_prior_actionable_locator_requirement_count": stage12470.get("actionable_locator_requirement_count"),
        "stage12470_prior_blocked_locator_requirement_count": stage12470.get("blocked_locator_requirement_count"),
        "available_source_artifact_counts": {
            "open_swe_candidate_records": len(open_swe),
            "representative_review_manifest_records": len(review_manifest),
            "adapter_execution_request_records": len(adapter_requests),
        },
        "private_artifacts": {
            "private_source_locator_index": "raw_private_not_model_facing_not_public_summary_safe",
        },
        "public_artifact_refs": {
            "public_locator_index_refs": "stage12471_public_locator_index_refs_jsonl",
            "blocked_locator_requests": "stage12471_blocked_locator_requests_jsonl",
            "guardrail_scan": "stage12471_guardrail_scan_json",
        },
        "next_recommendation": "merge_locator_refs_into_stage12469_style_work_items_then_rerun_stage12470_before_any_executor",
        "non_actions": ["does_not_execute", "does_not_hydrate", "does_not_replay", "does_not_train", "does_not_admit", "does_not_package", "does_not_claim_repair_credit"],
        "guardrail_scan_passed": not scan_issues,
        "raw_leak_count": len(scan_issues),
        "schema_issue_count": 0 if not scan_issues else len(scan_issues),
        **FALSE_GUARDS,
        **ZERO_GUARDS,
        "source_input_hashes": {
            "stage12469_work_items": file_hash(WORK_ITEMS),
            "stage12470_summary": file_hash(STAGE12470_SUMMARY),
            "open_swe_priority_candidates": file_hash(OPEN_SWE_CANDIDATES[0]),
            "open_swe_candidates": file_hash(OPEN_SWE_CANDIDATES[1]),
            "representative_review_manifest": file_hash(REPRESENTATIVE_REVIEW),
            "adapter_requests": file_hash(ADAPTER_REQUESTS),
        },
    }
    summary["summary_hash"] = stable_hash({k: v for k, v in summary.items() if k != "summary_hash"})
    guardrail = {
        "stage": STAGE,
        "scan_scope": "public_locator_refs_and_summary_only_private_locator_index_excluded",
        "scan_passed": not scan_issues,
        "raw_leak_count": len(scan_issues),
        "issue_hashes": [stable_hash(issue) for issue in scan_issues[:50]],
        "policy": "public artifacts contain only hashes/counts/statuses; raw private locators are stored only in raw_private artifact",
    }

    write_jsonl(PRIVATE_LOCATOR_OUT, selected_private)
    write_jsonl(PUBLIC_LOCATOR_OUT, public_rows)
    write_jsonl(BLOCKED_OUT, blocked)
    write_json(GUARDRAIL_OUT, guardrail)
    write_json(LOCAL_SUMMARY_OUT, summary)
    write_json(SUMMARY_OUT, summary)

    print(json.dumps({
        "stage": STAGE,
        "decision": decision,
        "private_locator_record_count": locator_count,
        "blocked_locator_request_count": blocked_count,
        "external_comparable_repair_credit_count": 0,
        "remaining_external_fail_to_pass_gap": EXPECTED_GAP,
        "guardrail_scan_passed": not scan_issues,
        "raw_leak_count": len(scan_issues),
    }, indent=2, sort_keys=True))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
