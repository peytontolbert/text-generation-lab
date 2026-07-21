#!/usr/bin/env python3
"""Stage12398 no-admission Open-SWE ordered event skeleton scale preflight.

Scales the Stage12397 safe ordered-event skeleton extraction to all 35
Stage12395 packets. Emits only class-level ordered event skeletons and
aggregate statistics; raw private trajectory content stays non-emitted.
"""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

import build_stage12397_open_swe_ordered_event_skeleton_preflight as base


ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12398_open_swe_ordered_event_skeleton_35_preflight"
OUT = ROOT / "runs/local/artifacts" / STAGE
SUMMARY = ROOT / "runs/summaries" / f"{STAGE}.json"

ROWS_NAME = "open_swe_ordered_event_skeleton_35_preflight.jsonl"
LOCAL_SUMMARY_NAME = "open_swe_ordered_event_skeleton_35_preflight_summary.json"
GUARDRAIL_NAME = "guardrail_scan.json"
MAX_PACKETS = 35


def configure_base() -> None:
    base.STAGE = STAGE
    base.OUT = OUT
    base.SUMMARY = SUMMARY
    base.ROWS_NAME = ROWS_NAME
    base.LOCAL_SUMMARY_NAME = LOCAL_SUMMARY_NAME
    base.GUARDRAIL_NAME = GUARDRAIL_NAME
    base.MAX_PACKETS = MAX_PACKETS


def all_stage12395_packets(packets: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(packets, key=lambda row: int(row.get("rank") or 0))[:MAX_PACKETS]


def sequence_shape(row: dict[str, Any]) -> tuple[tuple[str, str, str, str, str], ...]:
    return tuple(
        (
            str(event.get("event_role_class") or ""),
            str(event.get("event_action_class") or ""),
            str(event.get("observation_status_class") or ""),
            str(event.get("patch_signal_class") or ""),
            str(event.get("verifier_signal_class") or ""),
        )
        for event in row.get("ordered_event_skeleton", [])
        if isinstance(event, dict)
    )


def mean(values: list[int]) -> float:
    if not values:
        return 0.0
    return round(sum(values) / len(values), 6)


def event_count_bucket(count: int) -> str:
    if count < 75:
        return "lt_75"
    if count < 100:
        return "75_99"
    if count < 125:
        return "100_124"
    if count < 150:
        return "125_149"
    if count < 175:
        return "150_174"
    if count < 200:
        return "175_199"
    return "gte_200"


def row_safe_order_relations(row: dict[str, Any]) -> list[str]:
    relations = row.get("safe_order_relations")
    if isinstance(relations, list):
        return [str(item) for item in relations]
    return ["unknown_order"]


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> None:
    configure_base()
    OUT.mkdir(parents=True, exist_ok=True)

    source_packets = base.read_jsonl(base.SOURCE_PACKETS)
    selected_packets = all_stage12395_packets(source_packets)
    raw_ref_by_hash = base.source_ref_index(base.read_jsonl(base.STAGE12327_OPEN_SWE))

    rows: list[dict[str, Any]] = []
    missing_private_refs = 0
    for rank, packet in enumerate(selected_packets, 1):
        ref_hash = str(packet.get("source_record_ref_hash") or "")
        ref = raw_ref_by_hash.get(ref_hash)
        if not ref:
            missing_private_refs += 1
            ref = {}
        row = base.skeleton_from_packet(packet, ref, rank)
        row["event_count_bucket"] = event_count_bucket(int(row.get("event_count") or 0))
        row["rhythm_fingerprint_policy"] = "private_preflight_only_not_model_facing"
        row["rhythm_fingerprint_leakage_guard"] = "exact_ordered_skeleton_not_trainable_without_bucketing_or_review"
        row["model_facing_allowed"] = False
        rows.append(row)

    row_path = OUT / ROWS_NAME
    local_summary_path = OUT / LOCAL_SUMMARY_NAME
    guardrail_path = OUT / GUARDRAIL_NAME
    base.write_jsonl(row_path, rows)

    schema_issues = base.validate_rows(rows)
    language_counts = Counter(row["language_family"] for row in rows)
    role_counts = Counter(
        event["role_class"] for row in rows for event in row.get("ordered_event_skeletons", [])
    )
    action_counts = Counter(
        event["action_class"] for row in rows for event in row.get("ordered_event_skeletons", [])
    )
    marker_counts = Counter(
        marker
        for row in rows
        for event in row.get("ordered_event_skeletons", [])
        for marker in event.get("observation_marker_classes", [])
    )
    patch_signal_counts = Counter(
        event["patch_signal_class"] for row in rows for event in row.get("ordered_event_skeletons", [])
    )
    verifier_signal_counts = Counter(
        event["verifier_signal_class"] for row in rows for event in row.get("ordered_event_skeletons", [])
    )
    read_status_counts = Counter(row["private_parquet_read_status"] for row in rows)
    event_counts = [int(row["event_count"]) for row in rows]
    shape_counts = Counter(sequence_shape(row) for row in rows)
    sequence_length_distribution = Counter(str(count) for count in event_counts)
    per_language_event_counts = Counter()
    event_bucket_counts = Counter()
    safe_order_relation_counts = Counter()
    for row in rows:
        per_language_event_counts[str(row["language_family"])] += int(row["event_count"])
        event_bucket_counts[str(row.get("event_count_bucket") or event_count_bucket(int(row.get("event_count") or 0)))] += 1
        safe_order_relation_counts.update(row_safe_order_relations(row))
    expected_language_counts = {language: 5 for language in base.LANGUAGE_ORDER}

    summary: dict[str, Any] = {
        "stage": STAGE,
        "decision": "no_admission_ordered_event_skeleton_35_preflight_complete",
        "source_stage": base.SOURCE_STAGE,
        "source_boundary": "stage12395_packets_plus_private_stage12327_raw_ref_join",
        "input_packet_count": len(source_packets),
        "selected_packet_count": len(selected_packets),
        "expected_packet_count": MAX_PACKETS,
        "all_stage12395_packets_processed": len(selected_packets) == MAX_PACKETS == len(source_packets),
        "max_packets": MAX_PACKETS,
        "selection_policy": "all_stage12395_packets_in_rank_order",
        "language_family_counts": dict(sorted(language_counts.items())),
        "per_language_expected_counts": expected_language_counts,
        "source_family_hash_distribution": "not_emitted_hash_only_rows_no_source_family_values",
        "repo_hash_stats": {"repo_hashes_not_emitted_by_stage12397_source_rows": True},
        "duplicate_hash_stats": {"duplicate_sequence_shape_count": sum(1 for count in shape_counts.values() if count > 1)},
        "total_ordered_event_count": sum(event_counts),
        "total_ordered_event_count_bucketed": "gte_1000",
        "sequence_length_distribution": dict(sorted(sequence_length_distribution.items(), key=lambda item: int(item[0]))),
        "event_count_bucket_counts": dict(sorted(event_bucket_counts.items())),
        "event_count_min": min(event_counts) if event_counts else 0,
        "event_count_max": max(event_counts) if event_counts else 0,
        "event_count_mean": mean(event_counts),
        "per_language_event_counts": dict(sorted(per_language_event_counts.items())),
        "duplicate_sequence_shape_count": sum(1 for count in shape_counts.values() if count > 1),
        "fingerprinting_risk_declared": True,
        "rhythm_fingerprint_policy": "private_preflight_only_not_model_facing",
        "rhythm_fingerprint_leakage_guard": "exact_ordered_skeletons_are_blocked_inventory_not_training_rows",
        "private_parquet_read_status_counts": dict(sorted(read_status_counts.items())),
        "missing_private_ref_count": missing_private_refs,
        "role_class_counts": dict(sorted(role_counts.items())),
        "action_class_counts": dict(sorted(action_counts.items())),
        "observation_marker_class_counts": dict(sorted(marker_counts.items())),
        "patch_signal_class_counts": dict(sorted(patch_signal_counts.items())),
        "verifier_signal_class_counts": dict(sorted(verifier_signal_counts.items())),
        "safe_order_relation_counts": dict(sorted(safe_order_relation_counts.items())),
        "causality_claim_count": 0,
        "raw_leak_findings": [],
        "schema_issue_count": len(schema_issues),
        "schema_issues": schema_issues,
        "claim_boundary": {
            "correctness_inferred": False,
            "state_delta_inferred": False,
            "stop_continue_gold_inferred": False,
            "verifier_causality_inferred": False,
        },
        "raw_content_policy": base.RAW_CONTENT_POLICY,
        "blockers": base.BLOCKERS,
        "generated_artifacts": [ROWS_NAME, LOCAL_SUMMARY_NAME, GUARDRAIL_NAME],
        **base.ZERO_FLAGS,
    }
    write_json(local_summary_path, summary)
    write_json(SUMMARY, summary)

    guardrail = base.guardrail_scan([row_path, local_summary_path, SUMMARY])
    write_json(guardrail_path, guardrail)
    summary["guardrail_scan"] = guardrail
    summary["guardrail_issue_count"] = len(guardrail["issues"])
    write_json(local_summary_path, summary)
    write_json(SUMMARY, summary)
    if schema_issues or guardrail["issues"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
