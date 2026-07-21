#!/usr/bin/env python3
"""Build Stage12422 Open-SWE replay micro-pilot preflight artifact.

This is a fail-closed preflight only. It does not execute replay, apply
patches, run tests, admit rows, or emit raw commands/locators/content.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12422_open_swe_replay_micro_pilot_preflight"
SUMMARY = ROOT / "runs/summaries" / f"{STAGE}.json"
OUT = ROOT / "runs/local/artifacts" / STAGE

INPUTS = {
    "stage12413_summary": ROOT / "runs/summaries/stage12413_open_swe_level3_proof_gap_replay_manifest.json",
    "stage12420_summary": ROOT / "runs/summaries/stage12420_next_step_spine_aligned_execution_plan.json",
}

FORBIDDEN_TEXT_RE = re.compile(
    r"https?://|www\.|diff --git|@@ |^\+\+\+ |^--- |<<<<<<<|"
    r"(?:^|[\s:=])/(?:[A-Za-z0-9._-]+/){2,}[A-Za-z0-9._-]+",
    re.IGNORECASE | re.MULTILINE,
)

ZERO_COUNTERS = {
    "admitted_rows": 0,
    "emitted_rows": 0,
    "countable_new_rows": 0,
    "replay_attempted_count": 0,
    "patch_apply_attempted_count": 0,
    "tests_run_count": 0,
}

RAW_CONTENT_POLICY = {
    "raw_commands_emitted": False,
    "command_descriptors_only": True,
    "raw_paths_emitted": False,
    "urls_emitted": False,
    "diffs_emitted": False,
    "source_text_emitted": False,
    "stdout_stderr_emitted": False,
    "issue_bodies_emitted": False,
    "raw_row_content_emitted": False,
    "raw_locator_values_emitted": False,
}


def stable_hash(value: Any, n: int = 24) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:n]


def file_hash(path: Path, n: int = 24) -> str:
    if not path.exists():
        return "missing"
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()[:n]


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return value if isinstance(value, dict) else {}


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def find_replay_lane(stage12420: dict[str, Any]) -> dict[str, Any]:
    for lane in stage12420.get("execution_lanes") or []:
        if isinstance(lane, dict) and lane.get("lane_id") == "replay_proof_gap_work":
            return lane
    return {}


def bounded_micro_pilot_requests(stage12413: dict[str, Any]) -> list[dict[str, Any]]:
    limit = int(stage12413.get("micro_pilot_limit") or 0)
    candidates = stage12413.get("top_candidate_hashes") or []
    requests: list[dict[str, Any]] = []
    for candidate in candidates[:limit]:
        if not isinstance(candidate, dict):
            continue
        row_hashes = candidate.get("row_hashes") if isinstance(candidate.get("row_hashes"), dict) else {}
        requests.append(
            {
                "request_index": len(requests) + 1,
                "pilot_rank": candidate.get("rank"),
                "priority_bucket": candidate.get("priority_bucket"),
                "priority_reason_code": candidate.get("priority_reason"),
                "safe_hash_refs": {
                    "row_ref_hash": row_hashes.get("row_ref_hash"),
                    "stage12411_request_hash": row_hashes.get("stage12411_request_hash"),
                    "stage12411_request_row_hash": row_hashes.get("stage12411_request_row_hash"),
                    "instance_ref_hash": row_hashes.get("instance_ref_hash"),
                    "repo_family_hash": row_hashes.get("repo_family_hash"),
                    "trajectory_ref_hash": row_hashes.get("trajectory_ref_hash"),
                },
                "replay_scope": "bounded_micro_pilot_hash_only_reference",
                "admission_status": "not_admitted_preflight_only",
            }
        )
    return requests


def replay_command_descriptors(requirements: list[str]) -> list[dict[str, Any]]:
    descriptors = []
    for index, requirement in enumerate(requirements, 1):
        descriptors.append(
            {
                "descriptor_id": f"redacted_replay_step_{index:02d}",
                "requirement": requirement,
                "command_material": "redacted_not_emitted",
                "path_material": "redacted_not_emitted",
                "url_material": "redacted_not_emitted",
                "executor_output_contract": "safe_status_codes_and_hashes_only",
            }
        )
    return descriptors


def guardrail_scan(value: Any) -> dict[str, Any]:
    payload = json.dumps(value, sort_keys=True)
    issues = sorted(set(FORBIDDEN_TEXT_RE.findall(payload)))
    return {
        "scan_passed": not issues,
        "issue_count": len(issues),
        "issues": ["forbidden_raw_text_pattern_detected"] if issues else [],
        "raw_content_policy": RAW_CONTENT_POLICY,
    }


def main() -> None:
    stage12413 = read_json(INPUTS["stage12413_summary"])
    stage12420 = read_json(INPUTS["stage12420_summary"])
    replay_lane = find_replay_lane(stage12420)
    replay_state = replay_lane.get("current_state") if isinstance(replay_lane.get("current_state"), dict) else {}

    safe_return_schema = (
        stage12413.get("stage12414_safe_return_schema")
        or replay_state.get("safe_return_schema")
        or []
    )
    required_proof_slots = (
        stage12413.get("required_missing_proof_slots")
        or replay_state.get("required_missing_proof_slots")
        or []
    )
    replay_requirements = (
        stage12413.get("stage12414_replay_requirements")
        or replay_state.get("replay_requirements")
        or []
    )
    requests = bounded_micro_pilot_requests(stage12413)

    preflight = {
        **ZERO_COUNTERS,
        "stage": STAGE,
        "record_type": "open_swe_replay_micro_pilot_preflight",
        "decision": "fail_closed_preflight_only_no_replay_no_admission",
        "training_allowed": False,
        "admission_allowed": False,
        "execution_run": False,
        "raw_content_policy": RAW_CONTENT_POLICY,
        "input_summary_hashes": {name: file_hash(path) for name, path in INPUTS.items()},
        "input_summary_presence": {name: path.exists() for name, path in INPUTS.items()},
        "source_controls": {
            "stage12413_decision": stage12413.get("decision"),
            "stage12413_boundary": (stage12413.get("claim_boundary") or {}).get("boundary"),
            "stage12420_replay_lane_training_allowed": replay_lane.get("training_allowed", False),
            "stage12420_replay_lane_id": replay_lane.get("lane_id"),
        },
        "micro_pilot_request_count": len(requests),
        "micro_pilot_expected_request_count": int(
            stage12413.get("micro_pilot_request_count")
            or replay_state.get("micro_pilot_request_count")
            or 0
        ),
        "required_safe_return_schema": safe_return_schema,
        "required_proof_slots": required_proof_slots,
        "proof_slot_status_counts": {slot: "missing_executor_result" for slot in required_proof_slots},
        "raw_content_guardrail": RAW_CONTENT_POLICY,
        "next_required_action": (
            "Run a separate bounded replay executor for exactly the enumerated micro-pilot hash references, "
            "using the required safe return schema and returning only hashes/status codes; keep all rows blocked "
            "unless every required proof slot passes."
        ),
        "micro_pilot": {
            "bounded": True,
            "limit": int(stage12413.get("micro_pilot_limit") or replay_state.get("micro_pilot_limit") or 0),
            "request_count": len(requests),
            "expected_request_count": int(
                stage12413.get("micro_pilot_request_count")
                or replay_state.get("micro_pilot_request_count")
                or 0
            ),
            "requests": requests,
        },
        "replay_command_descriptors": replay_command_descriptors(replay_requirements),
        "proof_acceptance_gate": {
            "all_required_slots_must_pass": True,
            "allowed_return_material": "row hashes, state hashes, verifier hashes, status codes, and boolean policy flags only",
            "promotion_before_executor_result": False,
            "fail_closed_if_missing_any_required_slot": True,
        },
        "executor_next_required_action": (
            "Run a separate bounded replay executor for exactly the enumerated micro-pilot hash references, "
            "using the required safe return schema and returning only hashes/status codes; keep all rows blocked "
            "unless every required proof slot passes."
        ),
        "local_artifacts": {
            "preflight_workbook_name_hash": stable_hash("open_swe_replay_micro_pilot_preflight_workbook.json"),
            "guardrail_scan_name_hash": stable_hash("guardrail_scan.json"),
        },
    }

    scan = guardrail_scan(preflight)
    preflight["guardrail_scan"] = scan
    if not scan["scan_passed"]:
        preflight["decision"] = "fail_closed_guardrail_scan_failed"
        preflight["micro_pilot"]["requests"] = []
        preflight["micro_pilot"]["request_count"] = 0

    workbook = {
        "stage": STAGE,
        "training_allowed": False,
        **ZERO_COUNTERS,
        "micro_pilot_requests": requests if scan["scan_passed"] else [],
        "replay_command_descriptors": replay_command_descriptors(replay_requirements),
        "raw_content_policy": RAW_CONTENT_POLICY,
    }

    write_json(OUT / "open_swe_replay_micro_pilot_preflight_workbook.json", workbook)
    write_json(OUT / "guardrail_scan.json", scan)
    write_json(SUMMARY, preflight)


if __name__ == "__main__":
    main()
