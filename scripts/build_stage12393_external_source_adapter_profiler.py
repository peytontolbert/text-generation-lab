#!/usr/bin/env python3
"""Stage12393 no-admission profiler over Stage12392 pivot sources.

This profiler emits only sanitized availability, schema, and count metadata.
It does not emit training rows, raw commands, raw outputs, patch bodies, source
text, or absolute raw paths in row-like records.
"""
from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12393_external_source_adapter_profiler"
OUT = ROOT / "runs/local/artifacts" / STAGE
SUMMARY = ROOT / "runs/summaries" / f"{STAGE}.json"

PIVOT = ROOT / "runs/local/artifacts/stage12392_raw_visible_review_packet_builder_or_external_root_pivot"
PIVOT_WORKLIST = PIVOT / "external_root_private_review_packet_pivot_worklist.jsonl"
PIVOT_SUMMARY = ROOT / "runs/summaries/stage12392_raw_visible_review_packet_builder_or_external_root_pivot.json"

STAGE12327_SUMMARY = ROOT / "runs/summaries/stage12327_external_adapter_preflight.json"
STAGE12328_SUMMARY = ROOT / "runs/summaries/stage12328_external_adapter_qc_materialization_request.json"
STAGE12341_SUMMARY = (
    ROOT
    / "runs/local/artifacts/stage12341_open_swe_safe_transition_qc_candidates/open_swe_safe_transition_qc_candidates_summary.json"
)
STAGE12333_SUMMARY = (
    ROOT / "runs/local/artifacts/stage12333_bears_hydration_request/bears_hydration_request_summary.json"
)
STAGE12336_SUMMARY = (
    ROOT / "runs/local/artifacts/stage12336_bears_local_hydration_blocker_audit/bears_local_hydration_blocker_audit.json"
)

OPEN_SWE_PREFLIGHT_ROWS = (
    ROOT / "runs/local/artifacts/stage12327_external_adapter_preflight/open_swe_trace_support_candidates.jsonl"
)
OPEN_SWE_QC_ROWS = (
    ROOT / "runs/local/artifacts/stage12341_open_swe_safe_transition_qc_candidates/open_swe_safe_transition_qc_candidates.jsonl"
)
BEARS_PREFLIGHT_ROWS = (
    ROOT / "runs/local/artifacts/stage12327_external_adapter_preflight/bears_failing_passing_candidates.jsonl"
)

EXTERNAL_PROBES = {
    "defects4j": [
        Path("/arxiv/repositories/RepairThemAll/data/benchmarks/defects4j"),
        Path("/arxiv/repositories/RepairThemAll/benchmarks/defects4j"),
    ],
    "swe_bench_live": [
        Path("/arxiv/repositories/SWE-bench-Live"),
        Path("/arxiv/root-cleanup/agentkernel_space_reclaimed_20260513/verified_leaderboard"),
        Path("/arxiv/root-cleanup/agentkernel_space_reclaimed_20260513/verified_leaderboard/queue_agentkernel_swe_bench_live_verified_leaderboard"),
        Path("/arxiv/datasets/SWE-bench_Live"),
        Path("/arxiv/datasets/swe-bench-live"),
    ],
}

ADMISSION_ZERO = {
    "training_allowed": False,
    "level3_admitted": 0,
    "patch_trace_admitted": 0,
    "strict_eval_eligible": 0,
    "source_heldout_admissible": 0,
}
HARD_BLOCKERS = [
    "resolved_is_not_verifier_proof",
    "metadata_is_not_command_output",
    "co_presence_is_not_causality",
    "raw_private_only_before_safe_semantic_extraction",
    "dedupe_required",
    "repo/source-family caps required",
]
RAW_TEXT_RE = [
    re.compile(r"/(?:data|home|tmp|var|mnt|workspace|arxiv)/"),
    re.compile(r"(?m)^\s*(?:diff --git|@@ |\+\+\+ |--- )"),
    re.compile(r"\b(?:stdout|stderr|traceback|failureDetails|patch_body|raw_output|raw_command)\b", re.I),
]
RAWISH_KEY_RE = re.compile(
    r"(raw|command|output|stdout|stderr|patch|diff|source_text|failureDetails|path|root|args)$",
    re.I,
)


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def read_jsonl(path: Path, limit: int | None = None) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                rows.append(json.loads(line))
                if limit is not None and len(rows) >= limit:
                    break
    return rows


def count_jsonl(path: Path) -> int:
    if not path.exists():
        return 0
    count = 0
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                count += 1
    return count


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")


def schema_fingerprint(rows: list[dict[str, Any]]) -> dict[str, Any]:
    key_counts: Counter[str] = Counter()
    nested_counts: Counter[str] = Counter()
    for row in rows:
        for key, value in row.items():
            if RAWISH_KEY_RE.search(key):
                key_counts[f"{key}:redacted_rawish_key"] += 1
            else:
                key_counts[key] += 1
            if isinstance(value, dict):
                for nested_key in value:
                    label = f"{key}.{nested_key}"
                    if RAWISH_KEY_RE.search(label):
                        label = f"{key}.{nested_key}:redacted_rawish_key"
                    nested_counts[label] += 1
    return {
        "sampled_rows_for_schema": len(rows),
        "top_level_keys": sorted(key_counts),
        "nested_key_sample": sorted(nested_counts)[:80],
    }


def counter(rows: list[dict[str, Any]], key: str) -> dict[str, int]:
    values: Counter[str] = Counter()
    for row in rows:
        value = row.get(key)
        if isinstance(value, str) and not any(pattern.search(value) for pattern in RAW_TEXT_RE):
            values[value] += 1
        elif value is None:
            values["missing"] += 1
        else:
            values["redacted_or_non_scalar"] += 1
    return dict(sorted(values.items()))


def scalar_distribution_summary(rows: list[dict[str, Any]], key: str) -> dict[str, Any]:
    values: Counter[str] = Counter()
    for row in rows:
        value = row.get(key)
        if isinstance(value, str) and value:
            values[value] += 1
        elif value is None:
            values["missing"] += 1
        else:
            values["redacted_or_non_scalar"] += 1
    count_histogram = Counter(str(count) for count in values.values())
    return {
        "unique_value_count": len(values),
        "max_rows_per_value": max(values.values(), default=0),
        "count_histogram": dict(sorted(count_histogram.items(), key=lambda item: int(item[0]) if item[0].isdigit() else -1)),
        "raw_values_emitted": False,
    }


def list_counter(rows: list[dict[str, Any]], key: str) -> dict[str, int]:
    values: Counter[str] = Counter()
    for row in rows:
        items = row.get(key)
        if isinstance(items, list):
            for item in items:
                if isinstance(item, str) and not any(pattern.search(item) for pattern in RAW_TEXT_RE):
                    values[item] += 1
    return dict(sorted(values.items()))


def bool_count(rows: list[dict[str, Any]], path: tuple[str, ...]) -> dict[str, int]:
    counts: Counter[str] = Counter()
    for row in rows:
        value: Any = row
        for part in path:
            value = value.get(part) if isinstance(value, dict) else None
        counts[str(value)] += 1
    return dict(sorted(counts.items()))


def probe_availability(paths: list[Path]) -> dict[str, Any]:
    hits = [path for path in paths if path.exists()]
    return {
        "present": bool(hits),
        "probe_count": len(paths),
        "present_probe_count": len(hits),
        "location_labels": [f"configured_probe_{index + 1}" for index, _ in enumerate(hits)],
    }


def source_profile_open_swe(s12327: dict[str, Any], s12328: dict[str, Any], s12341: dict[str, Any]) -> dict[str, Any]:
    preflight_rows = read_jsonl(OPEN_SWE_PREFLIGHT_ROWS, limit=100)
    qc_rows = read_jsonl(OPEN_SWE_QC_ROWS, limit=100)
    inventory = s12327.get("open_swe_inventory", {})
    import_artifact = s12327.get("open_swe_import_artifact", {})
    contract = s12328.get("open_swe_qc_materialization_contract", {})
    return {
        **ADMISSION_ZERO,
        "source_family": "Open-SWE traces",
        "availability": {
            "inventory_present": bool(inventory.get("exists")),
            "local_preflight_rows_present": OPEN_SWE_PREFLIGHT_ROWS.exists(),
            "local_qc_rows_present": OPEN_SWE_QC_ROWS.exists(),
            "parquet_file_count": inventory.get("parquet_file_count", 0),
            "trajectory_family_counts": inventory.get("trajectory_family_counts", {}),
        },
        "sanitized_counts": {
            "preflight_rows": count_jsonl(OPEN_SWE_PREFLIGHT_ROWS),
            "sampled_preflight_candidates": import_artifact.get("sampled_preflight_candidates", 0),
            "priority_capped_candidates": import_artifact.get("priority_capped_candidates", 0),
            "qc_candidate_count": s12341.get("qc_candidate_count", 0),
            "blocked_by_repo_cap_count": s12341.get("blocked_by_repo_cap_count", 0),
            "language_counts": import_artifact.get("language_counts", {}),
            "candidate_type_counts": import_artifact.get("candidate_type_counts", {}),
            "qc_transition_function_candidate_counts": s12341.get("transition_function_candidate_counts", {}),
            "preflight_blocker_counts": list_counter(preflight_rows, "blocked_reasons"),
            "qc_blocker_counts": list_counter(qc_rows, "blocked_reasons"),
        },
        "sanitized_schema": {
            "preflight": schema_fingerprint(preflight_rows),
            "qc": schema_fingerprint(qc_rows),
            "required_safe_fields": contract.get("required_safe_fields", []),
        },
        "proof_gaps": {
            "resolved_is_not_verifier_proof": True,
            "same_source_order_proven_counts": bool_count(qc_rows, ("safe_derived_state", "same_source_order_proven")),
            "verifier_causality_proven_counts": bool_count(qc_rows, ("safe_derived_state", "verifier_causality_proven")),
            "state_before_hydrated_counts": bool_count(qc_rows, ("safe_derived_state", "state_before_hydrated")),
        },
        "hard_blockers": HARD_BLOCKERS,
    }


def source_profile_bears(s12327: dict[str, Any], s12328: dict[str, Any], s12333: dict[str, Any], s12336: dict[str, Any]) -> dict[str, Any]:
    rows = read_jsonl(BEARS_PREFLIGHT_ROWS, limit=100)
    inventory = s12327.get("bears_inventory", {})
    contract = s12328.get("bears_qc_materialization_contract", {})
    return {
        **ADMISSION_ZERO,
        "source_family": "Bears/RepairThemAll",
        "availability": {
            "metadata_inventory_present": bool(inventory.get("exists")),
            "local_preflight_rows_present": BEARS_PREFLIGHT_ROWS.exists(),
            "hydration_request_present": bool(s12333),
            "local_hydration_blocker_audit_present": bool(s12336),
            "local_hydration_blocked": s12336.get("decision") == "bears_local_hydration_blocked_fail_closed",
        },
        "sanitized_counts": {
            "total_metadata_records": inventory.get("total_records", 0),
            "failing_passing_candidates": inventory.get("failing_passing_candidates", 0),
            "nonrepair_blocked_candidates": inventory.get("nonrepair_blocked_candidates", 0),
            "preflight_rows": count_jsonl(BEARS_PREFLIGHT_ROWS),
            "requested_hydration_candidates": s12333.get("requested_candidates", 0),
            "requested_candidate_count_audited": s12336.get("requested_candidate_count", 0),
            "language_counts": inventory.get("language_counts", {}),
            "type_counts": inventory.get("type_counts", {}),
            "repo_family_distribution": scalar_distribution_summary(rows, "repo_family"),
            "preflight_blocker_counts": list_counter(rows, "blocked_reasons"),
        },
        "sanitized_schema": {
            "preflight": schema_fingerprint(rows),
            "admission_requires": contract.get("admission_requires", []),
            "requirements_before_next_execution_attempt": s12336.get("requirements_before_next_execution_attempt", []),
        },
        "proof_gaps": {
            "metadata_is_not_command_output": True,
            "local_checkout_materialized": False,
            "buggy_failure_reproduced": False,
            "fixed_selected_test_pass_reproduced": False,
            "same_source_patch_verifier_causality_proven": False,
            "blocked_reasons": s12336.get("blocked_reasons", []),
        },
        "hard_blockers": HARD_BLOCKERS,
    }


def source_profile_defects4j() -> dict[str, Any]:
    availability = probe_availability(EXTERNAL_PROBES["defects4j"])
    return {
        **ADMISSION_ZERO,
        "source_family": "Defects4J",
        "availability": availability,
        "sanitized_counts": {
            "local_candidate_rows": 0,
            "admitted_rows": 0,
            "profiled_raw_records": 0,
        },
        "sanitized_schema": {
            "known_required_private_fields": [
                "benchmark_bug_id",
                "project_family",
                "buggy_checkout_ref_hash",
                "fixed_checkout_ref_hash",
                "selected_test_identity_hashes",
                "before_status_class",
                "after_status_class",
                "patch_file_hashes",
                "changed_path_hashes",
                "verifier_identity_class",
            ],
            "local_safe_adapter_rows_present": False,
        },
        "proof_gaps": {
            "metadata_is_not_command_output": True,
            "raw_private_adapter_missing": True,
            "dedupe_required": True,
            "repo_source_family_caps_required": True,
        },
        "hard_blockers": HARD_BLOCKERS,
    }


def source_profile_swe_bench_live() -> dict[str, Any]:
    availability = probe_availability(EXTERNAL_PROBES["swe_bench_live"])
    return {
        **ADMISSION_ZERO,
        "source_family": "SWE-bench Live checkpoints",
        "availability": availability,
        "sanitized_counts": {
            "local_checkpoint_rows": 0,
            "admitted_rows": 0,
            "profiled_raw_records": 0,
        },
        "sanitized_schema": {
            "known_required_private_fields": [
                "instance_ref_hash",
                "checkpoint_family",
                "repo_family",
                "language_family",
                "base_commit_ref_hash",
                "candidate_patch_ref_hash",
                "selected_verifier_identity_class",
                "before_status_class",
                "after_status_class",
                "leakage_split_membership",
            ],
            "local_safe_adapter_rows_present": False,
        },
        "proof_gaps": {
            "resolved_is_not_verifier_proof": True,
            "checkpoint_metadata_is_not_execution_output": True,
            "raw_private_adapter_missing": True,
            "dedupe_required": True,
            "repo_source_family_caps_required": True,
        },
        "hard_blockers": HARD_BLOCKERS,
    }


def build_worklist(profiles: list[dict[str, Any]], pivot_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    pivot_counts = {
        str(row.get("source_family")): int(row.get("candidate_count") or 0)
        for row in pivot_rows
        if row.get("source_family")
    }
    ranked = [
        {
            **ADMISSION_ZERO,
            "rank": 1,
            "source_family": "Open-SWE traces",
            "work_item": "raw_private_semantic_transition_packet_materialization",
            "candidate_budget": min(25, pivot_counts.get("Open-SWE-Traces", 0) or 25),
            "not_training_rows": True,
            "packet_scope": "private reviewer packets with safe semantic fields only",
            "required_before_any_future_admission": [
                "private raw trace semantic extraction",
                "same-source event ordering proof",
                "verifier causality proof",
                "state before/after hydration",
                "dedupe and repo/source-family caps",
                "anti-leak rendering scan",
            ],
            "hard_blockers": HARD_BLOCKERS,
        },
        {
            **ADMISSION_ZERO,
            "rank": 2,
            "source_family": "Bears/RepairThemAll",
            "work_item": "raw_private_repair_packet_hydration_after_checkout_fix",
            "candidate_budget": min(5, pivot_counts.get("Bears/RepairThemAll", 0) or 5),
            "not_training_rows": True,
            "packet_scope": "private buggy/fixed checkout and verifier-class materialization",
            "required_before_any_future_admission": [
                "initialized Bears repository or authoritative content mirror",
                "buggy and fixed refs resolve in the same source family",
                "before failure and after pass status classes from verifier output",
                "patch lineage and changed path hashes",
                "dedupe and repo/source-family caps",
                "anti-leak rendering scan",
            ],
            "hard_blockers": HARD_BLOCKERS,
        },
        {
            **ADMISSION_ZERO,
            "rank": 3,
            "source_family": "Defects4J",
            "work_item": "raw_private_benchmark_adapter_discovery",
            "candidate_budget": 0,
            "not_training_rows": True,
            "packet_scope": "availability-first private packet contract; no safe local rows found yet",
            "required_before_any_future_admission": [
                "discover authoritative local benchmark metadata",
                "materialize checkout/verifier status classes privately",
                "dedupe against Bears and existing Java repair families",
                "repo/source-family caps",
            ],
            "hard_blockers": HARD_BLOCKERS,
        },
        {
            **ADMISSION_ZERO,
            "rank": 4,
            "source_family": "SWE-bench Live checkpoints",
            "work_item": "raw_private_checkpoint_adapter_discovery",
            "candidate_budget": 0,
            "not_training_rows": True,
            "packet_scope": "checkpoint availability and schema discovery only; no model-facing raw checkpoint contents",
            "required_before_any_future_admission": [
                "discover local checkpoint metadata",
                "prove split safety and leakage boundary",
                "recover verifier status classes from private execution or authoritative logs",
                "dedupe and repo/source-family caps",
            ],
            "hard_blockers": HARD_BLOCKERS,
        },
    ]
    present = {profile["source_family"]: profile["availability"] for profile in profiles}
    for item in ranked:
        item["availability_summary"] = present.get(item["source_family"], {})
    return ranked


def scan_guardrails(paths: list[Path]) -> dict[str, Any]:
    findings: list[dict[str, Any]] = []
    for path in paths:
        text = path.read_text(encoding="utf-8")
        for pattern in RAW_TEXT_RE:
            if pattern.search(text):
                findings.append({"artifact": path.name, "pattern": pattern.pattern})
    return {
        "passed": not findings,
        "scanned_artifacts": [path.name for path in paths],
        "findings": findings,
    }


def main() -> None:
    s12327 = read_json(STAGE12327_SUMMARY)
    s12328 = read_json(STAGE12328_SUMMARY)
    s12341 = read_json(STAGE12341_SUMMARY)
    s12333 = read_json(STAGE12333_SUMMARY)
    s12336 = read_json(STAGE12336_SUMMARY)
    pivot_summary = read_json(PIVOT_SUMMARY)
    pivot_rows = read_jsonl(PIVOT_WORKLIST)

    profiles = [
        source_profile_open_swe(s12327, s12328, s12341),
        source_profile_bears(s12327, s12328, s12333, s12336),
        source_profile_defects4j(),
        source_profile_swe_bench_live(),
    ]
    worklist = build_worklist(profiles, pivot_rows)

    OUT.mkdir(parents=True, exist_ok=True)
    profile_path = OUT / "source_family_profiles.json"
    worklist_path = OUT / "raw_private_reviewer_packet_materialization_worklist.jsonl"
    guardrail_path = OUT / "guardrail_scan.json"
    summary_path = OUT / "summary.json"

    profile_doc = {
        **ADMISSION_ZERO,
        "stage": STAGE,
        "purpose": "no-admission profiler over Stage12392 pivot sources",
        "profiles": profiles,
        "hard_blockers": HARD_BLOCKERS,
        "pivot_source": {
            "stage": "stage12392_raw_visible_review_packet_builder_or_external_root_pivot",
            "decision": pivot_summary.get("decision"),
            "worklist_rows": len(pivot_rows),
        },
    }
    write_json(profile_path, profile_doc)
    write_jsonl(worklist_path, worklist)

    summary = {
        **ADMISSION_ZERO,
        "stage": STAGE,
        "decision": "external_source_adapter_profiler_complete_no_admission",
        "claim_boundary": (
            "Profiler/control artifact only. It ranks raw-private reviewer packet materialization work; "
            "it emits no training rows and admits no Level-3, patch-trace, strict-eval, or source-heldout rows."
        ),
        "source_families_profiled": len(profiles),
        "source_family_names": [profile["source_family"] for profile in profiles],
        "ranked_worklist_rows": len(worklist),
        "hard_blockers": HARD_BLOCKERS,
        "counts": {
            "open_swe_preflight_rows": count_jsonl(OPEN_SWE_PREFLIGHT_ROWS),
            "open_swe_qc_candidate_rows": count_jsonl(OPEN_SWE_QC_ROWS),
            "bears_preflight_rows": count_jsonl(BEARS_PREFLIGHT_ROWS),
            "defects4j_safe_rows": 0,
            "swe_bench_live_safe_rows": 0,
        },
        "generated_artifacts": [
            "source_family_profiles.json",
            "raw_private_reviewer_packet_materialization_worklist.jsonl",
            "guardrail_scan.json",
            "summary.json",
        ],
    }
    write_json(summary_path, summary)
    write_json(SUMMARY, summary)

    guardrail = scan_guardrails([profile_path, worklist_path, summary_path, SUMMARY])
    write_json(guardrail_path, guardrail)
    if not guardrail["passed"]:
        raise SystemExit(f"guardrail scan failed: {guardrail['findings']}")
    print(json.dumps({"stage": STAGE, "summary": str(SUMMARY.relative_to(ROOT)), "guardrail_passed": True}, sort_keys=True))


if __name__ == "__main__":
    main()
