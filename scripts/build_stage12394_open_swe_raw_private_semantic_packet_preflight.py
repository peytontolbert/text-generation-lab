#!/usr/bin/env python3
"""Stage12394 no-admission Open-SWE private semantic packet preflight.

This stage reads Stage12327 and Stage12341 Open-SWE candidate records, may use
private raw refs only for aggregate semantic counts, and emits no raw trajectory,
command, output, patch, source text, or absolute path material.
"""
from __future__ import annotations

import hashlib
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12394_open_swe_raw_private_semantic_packet_preflight"
OUT = ROOT / "runs/local/artifacts" / STAGE
SUMMARY = ROOT / "runs/summaries" / f"{STAGE}.json"

STAGE12327 = ROOT / "runs/local/artifacts/stage12327_external_adapter_preflight"
STAGE12341 = ROOT / "runs/local/artifacts/stage12341_open_swe_safe_transition_qc_candidates"
STAGE12327_OPEN_SWE = STAGE12327 / "open_swe_trace_support_candidates.jsonl"
STAGE12327_PRIORITY = STAGE12327 / "open_swe_priority_capped_trace_support_candidates.jsonl"
STAGE12341_QC = STAGE12341 / "open_swe_safe_transition_qc_candidates.jsonl"

REQUIRED_BLOCKERS = [
    "resolved_is_not_verifier_proof",
    "model_patch_is_not_apply_proof",
    "co_presence_is_not_causality",
    "raw_private_only",
    "state_before_after_not_proven",
    "selected_verifier_relevance_not_proven",
    "duplicate_and_repo_cap_review_required",
]

RAW_FIELD_HINTS = {
    "trajectory",
    "content",
    "command",
    "output",
    "patch",
    "diff",
    "source",
    "text",
    "stdout",
    "stderr",
    "model_patch",
}

SAFE_STATUS_MARKERS = {
    "PASSED": "verifier_pass_marker",
    "FAILED": "verifier_fail_marker",
    "ERROR": "verifier_error_marker",
    "Traceback": "traceback_marker",
    "AssertionError": "assertion_marker",
    "pytest": "pytest_marker",
    "mvn test": "maven_test_marker",
    "cargo test": "cargo_test_marker",
    "npm test": "npm_test_marker",
}

ABS_PATH_RE = re.compile(r"(?<![A-Za-z0-9_])/(?:[A-Za-z0-9._-]+/){2,}[A-Za-z0-9._-]+")


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                rows.append(json.loads(line))
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
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:n]


def safe_counter(values: list[Any]) -> dict[str, int]:
    return dict(sorted(Counter(str(value or "unknown") for value in values).items()))


def admission_zero() -> dict[str, int | bool | str]:
    return {
        "training_allowed": False,
        "level3_admitted": 0,
        "patch_trace_admitted": 0,
        "strict_eval_eligible": 0,
        "source_heldout_admissible": 0,
        "repair_claim_admitted": 0,
        "admission_status": "no_admission_preflight_only",
    }


def strip_private_ref(ref: dict[str, Any]) -> dict[str, Any]:
    return {
        "private_raw_ref_hash": stable_hash(ref),
        "dataset_ref_hash": stable_hash(ref.get("dataset_file") or ref.get("dataset_name") or "missing"),
        "trajectory_family_hash": stable_hash(ref.get("trajectory_family") or "missing", 16),
        "instance_ref_hash": stable_hash(ref.get("instance_id") or "missing", 16),
        "trajectory_ref_hash": stable_hash(ref.get("trajectory_id") or "missing", 16),
        "raw_ref_scope": "private_not_model_facing",
        "raw_ref_abs_path_emitted": False,
    }


def candidate_index(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {str(row.get("candidate_id") or row.get("source_candidate_id") or ""): row for row in rows}


def classify_from_metadata(row: dict[str, Any]) -> dict[str, Any]:
    meta = row.get("trace_metadata") if isinstance(row.get("trace_metadata"), dict) else {}
    if not meta:
        meta = row.get("trace_counts") if isinstance(row.get("trace_counts"), dict) else {}
    markers = [str(marker) for marker in (meta.get("failure_markers") or row.get("trace_marker_classes") or [])]
    event_classes = Counter()
    if int(meta.get("turn_count") or 0) > 0:
        event_classes["conversation_turn"] += int(meta.get("turn_count") or 0)
    if int(meta.get("tool_turn_count") or 0) > 0:
        event_classes["tool_result_event"] += int(meta.get("tool_turn_count") or 0)
    if int(meta.get("verification_turn_count") or 0) > 0:
        event_classes["verification_observation_event"] += int(meta.get("verification_turn_count") or 0)

    status_classes = Counter(SAFE_STATUS_MARKERS.get(marker, "other_status_marker") for marker in markers)
    command_classes = Counter()
    tool_hashes = meta.get("tool_name_hashes") or row.get("tool_name_hashes") or []
    if tool_hashes:
        command_classes["tool_call_name_hash_observed"] = len(set(str(value) for value in tool_hashes))
    if row.get("selected_test_count"):
        command_classes["selected_test_target_hash_observed"] += int(row.get("selected_test_count") or 0)

    return {
        "event_class_counts": dict(sorted(event_classes.items())),
        "command_class_counts": dict(sorted(command_classes.items())),
        "safe_status_class_counts": dict(sorted(status_classes.items())),
        "numeric_trace_counts": {
            "turn_count": int(meta.get("turn_count") or 0),
            "tool_turn_count": int(meta.get("tool_turn_count") or 0),
            "verification_turn_count": int(meta.get("verification_turn_count") or 0),
            "metadata_num_modified_files": int(meta.get("metadata_num_modified_files") or 0),
            "metadata_num_modified_lines": int(meta.get("metadata_num_modified_lines") or 0),
        },
    }


def classify_tool_name(name: str) -> str:
    lowered = name.lower()
    if any(token in lowered for token in ("bash", "shell", "terminal", "exec")):
        return "shell_tool_call"
    if any(token in lowered for token in ("edit", "patch", "write", "replace")):
        return "file_mutation_tool_call"
    if any(token in lowered for token in ("read", "open", "view", "grep", "search")):
        return "file_inspection_tool_call"
    return "other_tool_call"


def raw_semantics_from_private_ref(ref: dict[str, Any]) -> tuple[dict[str, Any], str]:
    dataset_file = ref.get("dataset_file")
    if not dataset_file:
        return ({}, "raw_ref_missing_dataset_file")
    parquet_path = Path(str(dataset_file))
    if not parquet_path.exists():
        return ({}, "raw_ref_not_accessible")
    try:
        import pyarrow.parquet as pq  # type: ignore
    except Exception:
        return ({}, "pyarrow_unavailable")

    wanted_instance = ref.get("instance_id")
    wanted_trajectory = ref.get("trajectory_id")
    try:
        table = pq.read_table(
            parquet_path,
            columns=["instance_id", "trajectory_id", "trajectory", "metadata", "resolved"],
            filters=[
                ("instance_id", "=", wanted_instance),
                ("trajectory_id", "=", wanted_trajectory),
            ],
        )
    except Exception:
        return ({}, "raw_ref_read_failed")

    for record in table.to_pylist():
        if record.get("instance_id") != wanted_instance or record.get("trajectory_id") != wanted_trajectory:
            continue
        trajectory = record.get("trajectory")
        event_classes: Counter[str] = Counter()
        command_classes: Counter[str] = Counter()
        status_classes: Counter[str] = Counter()
        role_classes: Counter[str] = Counter()
        if isinstance(trajectory, list):
            for turn in trajectory:
                if not isinstance(turn, dict):
                    event_classes["non_object_turn"] += 1
                    continue
                role = str(turn.get("role") or "unknown")
                role_classes[f"role_{role}"] += 1
                if role == "assistant":
                    event_classes["assistant_turn"] += 1
                    calls = turn.get("tool_calls") if isinstance(turn.get("tool_calls"), list) else []
                    for call in calls:
                        fn = call.get("function") if isinstance(call, dict) else {}
                        name = str((fn or {}).get("name") or "")
                        command_classes[classify_tool_name(name)] += 1
                elif role == "tool":
                    event_classes["tool_result_event"] += 1
                    content = str(turn.get("content") or "")
                    for marker, status_class in SAFE_STATUS_MARKERS.items():
                        if marker in content:
                            status_classes[status_class] += 1
                else:
                    event_classes[f"{role}_turn"] += 1
        metadata = record.get("metadata") if isinstance(record.get("metadata"), dict) else {}
        return (
            {
                "raw_private_access_status": "raw_ref_aggregate_semantics_available",
                "raw_resolved_flag_present": record.get("resolved") is not None,
                "raw_resolved_true_count": int(bool(record.get("resolved"))),
                "raw_metadata_category_hash": stable_hash(metadata.get("category") or "missing", 16),
                "raw_event_class_counts": dict(sorted(event_classes.items())),
                "raw_role_class_counts": dict(sorted(role_classes.items())),
                "raw_command_class_counts": dict(sorted(command_classes.items())),
                "raw_safe_status_class_counts": dict(sorted(status_classes.items())),
            },
            "raw_ref_aggregate_semantics_available",
        )
    return ({}, "raw_ref_record_not_found")


def merge_counts(*items: dict[str, int]) -> dict[str, int]:
    counter: Counter[str] = Counter()
    for item in items:
        counter.update({str(key): int(value) for key, value in item.items()})
    return dict(sorted(counter.items()))


def packet_from_row(row: dict[str, Any], source_row: dict[str, Any] | None, rank: int) -> dict[str, Any]:
    base = source_row or row
    ref = base.get("source_record_ref") if isinstance(base.get("source_record_ref"), dict) else {}
    raw_semantics, raw_status = raw_semantics_from_private_ref(ref)
    safe_semantics = classify_from_metadata(base)
    raw_event_counts = raw_semantics.get("raw_event_class_counts") if raw_semantics else {}
    raw_command_counts = raw_semantics.get("raw_command_class_counts") if raw_semantics else {}
    raw_status_counts = raw_semantics.get("raw_safe_status_class_counts") if raw_semantics else {}

    candidate_key = {
        "stage12341_qc_candidate_id": row.get("qc_candidate_id"),
        "source_candidate_id": row.get("source_candidate_id") or base.get("candidate_id"),
        "private_raw_ref_hash": stable_hash(ref),
    }
    packet_id = f"{STAGE}::{stable_hash(candidate_key, 20)}"
    gate_results = {
        "raw_private_boundary_gate": {"passed": True, "blocker": None},
        "resolved_model_patch_shortcut_gate": {"passed": False, "blocker": "resolved_or_model_patch_shortcut_detected"},
        "patch_test_causality_gate": {"passed": False, "blocker": "patch_test_copresence_without_causality"},
        "command_output_classification_gate": {"passed": False, "blocker": "command_output_classification_missing_or_inexact"},
        "state_hydration_gate": {"passed": False, "blocker": "state_before_after_not_authoritatively_hydrated"},
        "repo_family_balance_gate": {"passed": False, "blocker": "repo_family_cap_review_required"},
        "duplicate_trajectory_gate": {"passed": False, "blocker": "duplicate_trajectory_review_required"},
        "admission_boundary_gate": {"passed": False, "blocker": "training_admission_blocked"},
    }
    blockers = sorted(set(REQUIRED_BLOCKERS + [
        "resolved_or_model_patch_shortcut_detected",
        "patch_test_copresence_without_causality",
        "command_output_classification_missing_or_inexact",
        "state_before_after_not_authoritatively_hydrated",
        "repo_family_cap_review_required",
        "duplicate_trajectory_review_required",
        "training_admission_blocked",
    ]))
    patch_signal_class = "model_patch_metadata_present_not_apply_proof" if ref else "patch_signal_not_authoritatively_recovered"
    test_signal_class = "selected_test_hashes_present_not_relevance_proof" if int(base.get("selected_test_count") or row.get("selected_test_count") or 0) else "selected_test_signal_missing"
    command_output_status_class = "aggregate_status_markers_present_not_exact_output_class" if raw_status_counts else "command_output_classification_missing"
    return {
        "stage": STAGE,
        "record_type": "open_swe_raw_private_semantic_packet_preflight",
        "packet_id": packet_id,
        "semantic_packet_id": packet_id,
        "source_adapter": "open_swe_trace_safe_transition_adapter",
        "source_record_ref_hash": stable_hash(ref, 24),
        "trajectory_identity_hash": stable_hash({"instance": ref.get("instance_id"), "trajectory": ref.get("trajectory_id")}, 24),
        "dedupe_key_hash": stable_hash({"source_record_ref": ref, "repo": base.get("repo_family"), "language": base.get("language_family")}, 24),
        "repo_family": "repo_family_hash_only",
        "rank": rank,
        "source_candidate_hash": stable_hash(row.get("source_candidate_id") or base.get("candidate_id") or "missing", 20),
        "qc_candidate_hash": stable_hash(row.get("qc_candidate_id") or "missing", 20),
        "private_raw_refs": strip_private_ref(ref),
        "language_family": str(base.get("language_family") or row.get("language_family") or "unknown"),
        "repo_family_hash": stable_hash(base.get("repo_family") or row.get("repo_family") or "unknown", 16),
        "repo_family_public_label_emitted": False,
        "state_before_status_class": "not_authoritatively_hydrated",
        "state_after_status_class": "not_authoritatively_hydrated",
        "state_before_hydration_status": "missing_authoritative_state_before",
        "state_after_hydration_status": "missing_authoritative_state_after",
        "patch_signal_class": patch_signal_class,
        "test_signal_class": test_signal_class,
        "command_output_status_class": command_output_status_class,
        "patch_test_causality_status": "not_proven_co_presence_only",
        "resolved_metadata_used_as_proof": False,
        "model_patch_used_as_proof": False,
        "seed_path_count": int(base.get("seed_path_count") or row.get("seed_path_count") or 0),
        "seed_path_hash_count": len(base.get("seed_path_hashes") or row.get("seed_path_hashes") or []),
        "selected_test_count": int(base.get("selected_test_count") or row.get("selected_test_count") or 0),
        "selected_test_hash_count": len(base.get("selected_test_hashes") or row.get("selected_test_hashes") or []),
        "semantic_counts": {
            "event_class_counts": merge_counts(safe_semantics["event_class_counts"], raw_event_counts),
            "command_class_counts": merge_counts(safe_semantics["command_class_counts"], raw_command_counts),
            "safe_status_class_counts": merge_counts(safe_semantics["safe_status_class_counts"], raw_status_counts),
            "candidate_trace_counts": safe_semantics["numeric_trace_counts"],
        },
        "raw_private_source_probe": {
            "status": raw_status,
            "aggregate_counts_only": True,
            "raw_trajectory_text_emitted": False,
            "raw_commands_emitted": False,
            "raw_outputs_emitted": False,
            "raw_patches_emitted": False,
            "source_text_emitted": False,
            **raw_semantics,
        },
        "proof_boundary": {
            "resolved_is_verifier_proof": False,
            "model_patch_is_apply_proof": False,
            "co_presence_is_causality": False,
            "state_before_after_proven": False,
            "selected_verifier_relevance_proven": False,
        },
        "raw_visibility": {
            "raw_trajectory_text_emitted": False,
            "raw_commands_emitted": False,
            "raw_outputs_emitted": False,
            "raw_patches_emitted": False,
            "source_text_emitted": False,
            "absolute_paths_emitted": False,
        },
        "gate_results": gate_results,
        "blockers": blockers,
        "admission": admission_zero(),
        "training_allowed": False,
        "level3_admitted": 0,
        "patch_trace_admitted": 0,
        "strict_eval_eligible": 0,
        "source_heldout_admissible": 0,
        "candidate_blockers": blockers,
        "raw_content_policy": {
            "raw_trajectory_text_emitted": False,
            "raw_commands_emitted": False,
            "raw_outputs_emitted": False,
            "raw_patches_emitted": False,
            "source_text_emitted": False,
            "absolute_paths_emitted": False,
        },
    }


def guardrail_scan(paths: list[Path]) -> dict[str, Any]:
    issues: list[dict[str, Any]] = []
    for path in paths:
        text = path.read_text(encoding="utf-8")
        if ABS_PATH_RE.search(text):
            issues.append({"artifact": path.name, "issue": "absolute_path_pattern"})
        try:
            value = json.loads(text) if path.suffix == ".json" else None
        except json.JSONDecodeError:
            value = None
        if value is not None:
            scan_json_for_raw_keys(value, path.name, issues)
    return {
        "scan_passed": not issues,
        "issues": issues,
        "scanned_artifact_count": len(paths),
    }


def scan_json_for_raw_keys(value: Any, artifact: str, issues: list[dict[str, Any]], key_path: str = "") -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            child_path = f"{key_path}.{key}" if key_path else str(key)
            lowered = str(key).lower()
            if lowered in RAW_FIELD_HINTS and isinstance(child, str) and len(child) > 0:
                issues.append({"artifact": artifact, "issue": "raw_text_like_key", "key": child_path})
            scan_json_for_raw_keys(child, artifact, issues, child_path)
    elif isinstance(value, list):
        for index, child in enumerate(value):
            scan_json_for_raw_keys(child, artifact, issues, f"{key_path}[{index}]")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    stage12327_rows = read_jsonl(STAGE12327_OPEN_SWE)
    stage12327_priority_rows = read_jsonl(STAGE12327_PRIORITY)
    stage12341_rows = read_jsonl(STAGE12341_QC)
    source_by_id = candidate_index(stage12327_rows + stage12327_priority_rows)

    packets = [
        packet_from_row(row, source_by_id.get(str(row.get("source_candidate_id") or "")), rank)
        for rank, row in enumerate(stage12341_rows, 1)
    ]

    packet_path = OUT / "open_swe_raw_private_semantic_packet_preflight.jsonl"
    write_jsonl(packet_path, packets)

    language_counts = Counter(packet["language_family"] for packet in packets)
    repo_hash_counts = Counter(packet["repo_family_hash"] for packet in packets)
    blocker_counts = Counter(blocker for packet in packets for blocker in packet["candidate_blockers"])
    raw_status_counts = Counter(packet["raw_private_source_probe"]["status"] for packet in packets)
    aggregate_event_counts: Counter[str] = Counter()
    aggregate_command_counts: Counter[str] = Counter()
    aggregate_status_counts: Counter[str] = Counter()
    for packet in packets:
        aggregate_event_counts.update(packet["semantic_counts"]["event_class_counts"])
        aggregate_command_counts.update(packet["semantic_counts"]["command_class_counts"])
        aggregate_status_counts.update(packet["semantic_counts"]["safe_status_class_counts"])

    summary = {
        "stage": STAGE,
        "decision": "no_admission_open_swe_private_semantic_packet_preflight_complete",
        "training_allowed": False,
        "level3_admitted": 0,
        "patch_trace_admitted": 0,
        "strict_eval_eligible": 0,
        "source_heldout_admissible": 0,
        "new_training_rows_emitted": 0,
        "input_candidate_count": len(stage12341_rows),
        "preflight_packet_count": len(packets),
        "blocked_packet_count": len(packets),
        "admitted_packet_count": 0,
        "candidate_packet_count": len(packets),
        "source_stage12327_candidate_count": len(stage12327_rows),
        "source_stage12327_priority_candidate_count": len(stage12327_priority_rows),
        "source_stage12341_qc_candidate_count": len(stage12341_rows),
        "private_raw_ref_status_counts": dict(sorted(raw_status_counts.items())),
        "language_family_counts": dict(sorted(language_counts.items())),
        "repo_family_hash_distribution": dict(sorted(repo_hash_counts.items())),
        "unique_repo_family_hash_count": len(repo_hash_counts),
        "aggregate_event_class_counts": dict(sorted(aggregate_event_counts.items())),
        "aggregate_command_class_counts": dict(sorted(aggregate_command_counts.items())),
        "aggregate_safe_status_class_counts": dict(sorted(aggregate_status_counts.items())),
        "candidate_blocker_counts": dict(sorted(blocker_counts.items())),
        "blocker_counts": dict(sorted(blocker_counts.items())),
        "repo_family_counts": {"hash_only_unique": len(repo_hash_counts), "max_rows_per_repo_hash": max(repo_hash_counts.values(), default=0)},
        "duplicate_trajectory_groups": sum(1 for count in repo_hash_counts.values() if count > 1),
        "raw_leak_findings": [],
        "required_blockers": REQUIRED_BLOCKERS,
        "raw_content_policy": {
            "raw_trajectory_text_emitted": False,
            "raw_commands_emitted": False,
            "raw_outputs_emitted": False,
            "raw_patches_emitted": False,
            "source_text_emitted": False,
            "absolute_paths_emitted": False,
            "private_raw_refs_only_hashed": True,
        },
        "claim_boundary": (
            "Hashes, counts, classes, blockers, aggregate distributions, and private raw ref hashes only. "
            "No raw trajectory, command, output, patch, source text, absolute path, training, Level-3, "
            "patch-trace, strict-eval, or source-heldout admission."
        ),
        "generated_artifacts": [
            "open_swe_raw_private_semantic_packet_preflight.jsonl",
            "open_swe_raw_private_semantic_packet_preflight_summary.json",
            "guardrail_scan.json",
        ],
    }
    summary_path = OUT / "open_swe_raw_private_semantic_packet_preflight_summary.json"
    write_json(summary_path, summary)

    guardrail = guardrail_scan([packet_path, summary_path])
    guardrail_path = OUT / "guardrail_scan.json"
    write_json(guardrail_path, guardrail)
    summary["guardrail_scan"] = guardrail
    write_json(summary_path, summary)
    write_json(SUMMARY, summary)


if __name__ == "__main__":
    main()
