#!/usr/bin/env python3
"""Build Stage12443 representative private review packet preflight.

This stage consumes Stage12442 public-safe representative review packet
requests and emits only bounded preflight counters/gates. It does not inspect
or emit raw commands, outputs, diffs, paths, source, or private labels.
"""
from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12443_representative_private_review_packet_preflight"
OUT = ROOT / "runs/local/artifacts" / STAGE
SUMMARY = ROOT / "runs/summaries" / f"{STAGE}.json"

STAGE12442 = "stage12442_representative_private_review_and_source_adapter_expansion_request"
STAGE12442_OUT = ROOT / "runs/local/artifacts" / STAGE12442
STAGE12442_SUMMARY = ROOT / "runs/summaries" / f"{STAGE12442}.json"
STAGE12442_MANIFEST = STAGE12442_OUT / "representative_private_review_packet_manifest.jsonl"

ZERO_COUNTERS: dict[str, bool | int] = {
    "training_allowed": False,
    "admission_allowed": False,
    "execution_allowed": False,
    "emitted_training_rows": 0,
    "admitted_rows": 0,
    "countable_new_rows": 0,
    "level3_candidate_count": 0,
    "level4_candidate_count": 0,
    "patch_trace_candidate_count": 0,
    "sealed_eval_rows_emitted": 0,
}

RAW_CONTENT_POLICY = {
    "raw_private_trace_text_inspected": False,
    "raw_private_trace_text_emitted": False,
    "raw_command_values_emitted": False,
    "raw_output_values_emitted": False,
    "raw_diff_values_emitted": False,
    "raw_patch_values_emitted": False,
    "raw_path_values_emitted": False,
    "raw_source_values_emitted": False,
    "raw_url_values_emitted": False,
    "representative_labels_emitted": False,
    "representative_labels_propagated_to_cluster_members": False,
}

FORBIDDEN_KEYS = {
    "command",
    "command_text",
    "commands",
    "diff",
    "output",
    "outputs",
    "patch",
    "path",
    "paths",
    "private_locator",
    "raw",
    "raw_text",
    "source",
    "source_path",
    "source_text",
    "stderr",
    "stdout",
    "trace",
    "trace_text",
    "url",
    "urls",
}

RAW_LEAK_RE = re.compile(
    r"https?://|www\.|diff --git|@@ |^\+\+\+ |^--- |<<<<<<<|>>>>>>>|"
    r"(?<![A-Za-z0-9_])/(?:[A-Za-z0-9._-]+/){2,}[A-Za-z0-9._-]+|"
    r"\b(?:Traceback \(most recent call last\)|stdout:|stderr:|stack trace|"
    r"terminal output:|command output:|git clone\s+\S|git apply\s+\S|"
    r"curl\s+\S|bash -|sh -|python -c)\b",
    re.IGNORECASE | re.MULTILINE,
)

OVERCLAIM_RE = re.compile(
    r"\b(?:admitted|training row|trainable|accepted row|verified repair|"
    r"level-3 complete|level3 complete|patch-trace complete|execution succeeded|"
    r"tests passed|private review completed|semantic review complete)\b",
    re.IGNORECASE,
)

ALLOWED_OVERCLAIM_CONTEXT_RE = re.compile(
    r"(false|zero|none|blocked|request|required|future|must not|not |no |"
    r"fail.closed|fail-closed|counter|policy|guardrail|private review|"
    r"not admitted|not training|preflight)",
    re.IGNORECASE,
)


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    value = json.loads(path.read_text(encoding="utf-8"))
    return value if isinstance(value, dict) else {}


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            value = json.loads(line)
            if not isinstance(value, dict):
                raise ValueError(f"JSONL row {line_number} is not an object")
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


def stable_hash(value: Any, n: int = 24) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(f"{STAGE}:{payload}".encode("utf-8")).hexdigest()[:n]


def file_hash(path: Path, n: int = 24) -> str:
    if not path.exists() or not path.is_file():
        return "missing"
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()[:n]


def count_top(values: list[Any], limit: int = 20) -> dict[str, int]:
    counts = Counter(str(value) for value in values)
    return dict(sorted(counts.items(), key=lambda item: (-item[1], item[0]))[:limit])


def scan_payload(label: str, payload: Any) -> list[str]:
    issues: list[str] = []
    if isinstance(payload, str):
        if RAW_LEAK_RE.search(payload):
            issues.append(f"{label}:raw_leak:{stable_hash(payload)}")
        for match in OVERCLAIM_RE.finditer(payload):
            start = max(0, match.start() - 80)
            end = min(len(payload), match.end() + 80)
            if not ALLOWED_OVERCLAIM_CONTEXT_RE.search(payload[start:end]):
                issues.append(f"{label}:overclaim:{stable_hash(payload[start:end])}")
    elif isinstance(payload, dict):
        for key, value in payload.items():
            if str(key).lower() in FORBIDDEN_KEYS:
                issues.append(f"{label}.{key}:forbidden_key")
            issues.extend(scan_payload(f"{label}.{key}", value))
    elif isinstance(payload, list):
        for index, value in enumerate(payload):
            issues.extend(scan_payload(f"{label}[{index}]", value))
    return issues


def required_slots_for(row: dict[str, Any]) -> list[str]:
    slots = row.get("review_must_fill_slots")
    if isinstance(slots, list):
        return [str(slot) for slot in slots]
    return []


def hard_reject_slots_for(row: dict[str, Any]) -> list[str]:
    slots = row.get("hard_reject_if_missing")
    if isinstance(slots, list):
        return [str(slot) for slot in slots]
    return []


def provided_slots_for(row: dict[str, Any], required_slots: list[str]) -> set[str]:
    """Infer public-safe slot presence from explicit status booleans only."""
    provided = row.get("provided_review_slots")
    if isinstance(provided, list):
        return {str(slot) for slot in provided if str(slot) in required_slots}
    status = row.get("review_slot_status")
    if isinstance(status, dict):
        return {slot for slot in required_slots if status.get(slot) in (True, "provided", "present")}
    return set()


def slot_requirement_rows(manifest: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for index, packet in enumerate(manifest, start=1):
        required = required_slots_for(packet)
        hard_reject = set(hard_reject_slots_for(packet))
        provided = provided_slots_for(packet, required)
        missing = [slot for slot in required if slot not in provided]
        rows.append(
            {
                "preflight_slot_record_id_hash": stable_hash(
                    {
                        "packet": packet.get("review_packet_id_hash"),
                        "rank": packet.get("representative_priority_rank", index),
                    }
                ),
                "review_packet_id_hash": packet.get("review_packet_id_hash"),
                "representative_candidate_id_hash": packet.get("representative_candidate_id_hash"),
                "representative_priority_rank": packet.get("representative_priority_rank", index),
                "required_slot_count": len(required),
                "provided_slot_count": len(provided),
                "missing_slot_count": len(missing),
                "hard_reject_missing_slot_count": len([slot for slot in missing if slot in hard_reject]),
                "all_required_slots_provided": not missing,
                "hard_reject_clear": not any(slot in hard_reject for slot in missing),
                "training_allowed": False,
                "admission_allowed": False,
                "cluster_member_admission_policy": "review_representative_only_no_automatic_propagation_to_cluster_members",
            }
        )
    return rows


def aggregate_slot_counters(manifest: list[dict[str, Any]]) -> dict[str, Any]:
    required_counts: Counter[str] = Counter()
    provided_counts: Counter[str] = Counter()
    missing_counts: Counter[str] = Counter()
    hard_missing_counts: Counter[str] = Counter()
    for packet in manifest:
        required = required_slots_for(packet)
        hard_reject = set(hard_reject_slots_for(packet))
        provided = provided_slots_for(packet, required)
        required_counts.update(required)
        provided_counts.update(provided)
        missing = [slot for slot in required if slot not in provided]
        missing_counts.update(missing)
        hard_missing_counts.update(slot for slot in missing if slot in hard_reject)
    return {
        "required_slot_counts": dict(sorted(required_counts.items())),
        "provided_slot_counts": dict(sorted(provided_counts.items())),
        "missing_slot_counts": dict(sorted(missing_counts.items())),
        "hard_reject_missing_slot_counts": dict(sorted(hard_missing_counts.items())),
        "global_required_slot_count": len(required_counts),
        "total_required_slot_instances": sum(required_counts.values()),
        "total_provided_slot_instances": sum(provided_counts.values()),
        "total_missing_slot_instances": sum(missing_counts.values()),
        "total_hard_reject_missing_slot_instances": sum(hard_missing_counts.values()),
    }


def build_artifact() -> tuple[dict[str, Any], list[dict[str, Any]], dict[str, Any], dict[str, Any]]:
    stage12442_summary = read_json(STAGE12442_SUMMARY)
    manifest = read_jsonl(STAGE12442_MANIFEST)
    slot_rows = slot_requirement_rows(manifest)
    slot_counters = aggregate_slot_counters(manifest)

    packet_count = len(manifest)
    ready_count = sum(1 for row in slot_rows if row["all_required_slots_provided"] and row["hard_reject_clear"])
    represented_total = sum(int(row.get("represented_candidate_count") or 0) for row in manifest)
    stage12442_requested = int(stage12442_summary.get("private_review_packet_requested_count") or -1)
    stage12442_represented_total = int(stage12442_summary.get("represented_candidate_count_total") or -1)
    manifest_public_safe = all(
        packet.get("public_safe_raw_refs_absent") is True
        and packet.get("training_allowed") is False
        and packet.get("admission_allowed") is False
        and packet.get("cluster_member_admission_policy")
        == "review_representative_only_no_automatic_propagation_to_cluster_members"
        for packet in manifest
    )

    fail_closed_gate_status = {
        "stage12442_summary_present": bool(stage12442_summary),
        "stage12442_guardrail_passed": stage12442_summary.get("guardrail_scan_passed") is True,
        "stage12442_training_blocked": stage12442_summary.get("training_allowed") is False,
        "stage12442_admission_blocked": stage12442_summary.get("admission_allowed") is False,
        "manifest_present": packet_count > 0,
        "manifest_count_matches_stage12442": packet_count == stage12442_requested,
        "manifest_represented_total_matches_stage12442": represented_total == stage12442_represented_total,
        "manifest_public_safe_policy_flags_present": manifest_public_safe,
        "private_semantic_review_not_executed": ready_count == 0,
        "hard_reject_slots_missing": slot_counters["total_hard_reject_missing_slot_instances"] > 0,
        "training_blocked": True,
        "admission_blocked": True,
        "cluster_member_label_propagation_blocked": True,
    }

    next_action_request = {
        "request_type": "private_semantic_reviewer_execution_required",
        "execution_scope": "Stage12442 representative packets only",
        "public_artifact_boundary": "return slot presence/status counters and aggregate review decisions only; do not emit raw commands, outputs, diffs, paths, source, or private text",
        "review_unit": "representative_candidate_only",
        "cluster_member_rule": "do not propagate representative labels to unreviewed cluster members",
        "required_slots": sorted(slot_counters["required_slot_counts"].keys()),
        "hard_reject_if_missing": sorted(slot_counters["hard_reject_missing_slot_counts"].keys()),
        "requested_review_packet_count": packet_count,
        "training_allowed": False,
        "admission_allowed": False,
    }

    artifact = {
        "stage": STAGE,
        "record_type": "representative_private_review_packet_preflight_public_safe_v1",
        "decision": "fail_closed_private_semantic_reviewer_execution_required",
        **ZERO_COUNTERS,
        "input_fingerprints": {
            "stage12442_summary_sha256_24": file_hash(STAGE12442_SUMMARY),
            "stage12442_manifest_sha256_24": file_hash(STAGE12442_MANIFEST),
            "stage12442_stage": stage12442_summary.get("stage"),
            "stage12442_record_type": stage12442_summary.get("record_type"),
        },
        "representative_review_packet_count": packet_count,
        "private_review_packet_ready_count": ready_count,
        "private_review_packet_missing_count": packet_count - ready_count,
        "represented_candidate_count_total": represented_total,
        "representative_cluster_coverage_counts": {
            "language_family": count_top([row.get("language_family") for row in manifest]),
            "task_family": count_top([row.get("task_family") for row in manifest]),
            "priority_bucket": count_top([row.get("priority_bucket") for row in manifest]),
        },
        "slot_counters": slot_counters,
        "fail_closed_gate_status": fail_closed_gate_status,
        "hard_gate_blockers": [
            "private_semantic_review_not_executed",
            "required_review_slots_missing",
            "hard_reject_slots_missing",
            "representative_labels_not_available",
            "cluster_member_label_propagation_blocked",
            "level3_admission_blocked",
        ],
        "raw_content_policy": RAW_CONTENT_POLICY,
        "claim_boundary": "public-safe preflight only; no private semantic review was executed and no rows are admitted or emitted for training",
        "next_action_request": next_action_request,
        "summary_hash": "pending",
    }

    guardrail_payload = {
        "main": artifact,
        "slot_requirement_rows": slot_rows,
        "slot_counters": slot_counters,
        "next_action_request": next_action_request,
        "fail_closed_gate_status": fail_closed_gate_status,
    }
    issues: list[str] = []
    for name, payload in guardrail_payload.items():
        issues.extend(scan_payload(name, payload))
    for key, expected in ZERO_COUNTERS.items():
        if artifact.get(key) != expected:
            issues.append(f"zero_counter_mismatch:{key}")
    if not all(fail_closed_gate_status.values()):
        issues.append("fail_closed_gate_status_not_all_true")
    guardrail = {
        "scan_passed": not issues,
        "issue_count": len(set(issues)),
        "issues": sorted(set(issues)),
        "raw_leak_count": len({issue for issue in issues if ":raw_leak:" in issue}),
        "overclaim_count": len({issue for issue in issues if ":overclaim:" in issue}),
        "forbidden_key_count": len({issue for issue in issues if issue.endswith(":forbidden_key")}),
        "scan_scope": "stage12443_public_safe_preflight_artifacts",
    }
    artifact["guardrail_scan"] = guardrail
    artifact["guardrail_scan_passed"] = guardrail["scan_passed"]
    artifact["raw_leak_count"] = guardrail["raw_leak_count"]
    artifact["overclaim_count"] = guardrail["overclaim_count"]
    artifact["summary_hash"] = stable_hash({k: v for k, v in artifact.items() if k != "summary_hash"})
    return artifact, slot_rows, slot_counters, next_action_request


def main() -> None:
    artifact, slot_rows, slot_counters, next_action_request = build_artifact()
    OUT.mkdir(parents=True, exist_ok=True)
    write_json(OUT / f"{STAGE}.json", artifact)
    write_json(OUT / "summary.json", artifact)
    write_json(SUMMARY, artifact)
    write_jsonl(OUT / "representative_review_slot_requirements.jsonl", slot_rows)
    write_json(OUT / "representative_review_slot_counters.json", slot_counters)
    write_json(OUT / "fail_closed_gate_status.json", artifact["fail_closed_gate_status"])
    write_json(OUT / "next_action_request.json", next_action_request)
    write_json(OUT / "guardrail_scan.json", artifact["guardrail_scan"])
    print(
        json.dumps(
            {
                "stage": artifact["stage"],
                "decision": artifact["decision"],
                "representative_review_packet_count": artifact["representative_review_packet_count"],
                "private_review_packet_ready_count": artifact["private_review_packet_ready_count"],
                "private_review_packet_missing_count": artifact["private_review_packet_missing_count"],
                "total_required_slot_instances": slot_counters["total_required_slot_instances"],
                "total_provided_slot_instances": slot_counters["total_provided_slot_instances"],
                "total_missing_slot_instances": slot_counters["total_missing_slot_instances"],
                "total_hard_reject_missing_slot_instances": slot_counters[
                    "total_hard_reject_missing_slot_instances"
                ],
                "training_allowed": artifact["training_allowed"],
                "admission_allowed": artifact["admission_allowed"],
                "emitted_training_rows": artifact["emitted_training_rows"],
                "level3_candidate_count": artifact["level3_candidate_count"],
                "patch_trace_candidate_count": artifact["patch_trace_candidate_count"],
                "guardrail_scan_passed": artifact["guardrail_scan_passed"],
                "raw_leak_count": artifact["raw_leak_count"],
                "overclaim_count": artifact["overclaim_count"],
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
