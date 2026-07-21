#!/usr/bin/env python3
"""Stage12397 no-admission Open-SWE ordered event skeleton preflight.

Consumes Stage12395 safe packets, privately joins back to Stage12327 raw refs,
reads parquet trajectories, and emits only class-level ordered event skeletons.
No raw trajectory text, commands, outputs, patches, source text, absolute paths,
or URLs are emitted.
"""
from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12397_open_swe_ordered_event_skeleton_preflight"
OUT = ROOT / "runs/local/artifacts" / STAGE
SUMMARY = ROOT / "runs/summaries" / f"{STAGE}.json"

SOURCE_STAGE = "stage12395_open_swe_multilingual_semantic_packet_preflight"
SOURCE_PACKETS = (
    ROOT
    / "runs/local/artifacts"
    / SOURCE_STAGE
    / "open_swe_multilingual_semantic_packet_preflight.jsonl"
)
STAGE12327_OPEN_SWE = (
    ROOT
    / "runs/local/artifacts/stage12327_external_adapter_preflight/open_swe_trace_support_candidates.jsonl"
)

ROWS_NAME = "open_swe_ordered_event_skeleton_preflight.jsonl"
LOCAL_SUMMARY_NAME = "open_swe_ordered_event_skeleton_preflight_summary.json"
GUARDRAIL_NAME = "guardrail_scan.json"
MAX_PACKETS = 7
LANGUAGE_ORDER = ("python", "go", "typescript", "javascript", "rust", "php", "java")

ZERO_FLAGS: dict[str, int | bool] = {
    "admission": False,
    "training_allowed": False,
    "level3_admitted": 0,
    "patch_trace_admitted": 0,
    "strict_eval_eligible": 0,
    "source_heldout_admissible": 0,
    "training_row_count": 0,
}

RAW_CONTENT_POLICY: dict[str, bool] = {
    "raw_trajectory_text_emitted": False,
    "raw_commands_emitted": False,
    "raw_outputs_emitted": False,
    "raw_patches_emitted": False,
    "source_text_emitted": False,
    "absolute_paths_emitted": False,
    "urls_emitted": False,
}

BLOCKERS = [
    "admission_boundary_false",
    "correctness_not_inferred",
    "raw_private_only",
    "state_delta_not_inferred",
    "stop_continue_gold_not_inferred",
    "verifier_causality_not_inferred",
]

SAFE_MARKERS = {
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
URL_RE = re.compile(r"https?://|www\.", re.IGNORECASE)
MULTILINE_RE = re.compile(r"[\r\n]")
HEX_RE = re.compile(r"^[0-9a-f]{12,64}$")


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


def select_one_per_language(packets: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_language: dict[str, list[dict[str, Any]]] = {language: [] for language in LANGUAGE_ORDER}
    for packet in packets:
        language = str(packet.get("language_family") or "unknown")
        if language in by_language:
            by_language[language].append(packet)
    selected: list[dict[str, Any]] = []
    for language in LANGUAGE_ORDER:
        if by_language[language]:
            selected.append(sorted(by_language[language], key=lambda row: int(row.get("rank") or 0))[0])
        if len(selected) >= MAX_PACKETS:
            break
    if len(selected) < MAX_PACKETS:
        selected_ids = {str(row.get("packet_id")) for row in selected}
        for packet in packets:
            if str(packet.get("packet_id")) not in selected_ids:
                selected.append(packet)
            if len(selected) >= MAX_PACKETS:
                break
    return selected


def source_ref_index(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    index: dict[str, dict[str, Any]] = {}
    for row in rows:
        ref = row.get("source_record_ref") if isinstance(row.get("source_record_ref"), dict) else {}
        if ref:
            index[stable_hash(ref, 24)] = ref
    return index


def role_class(role: Any) -> str:
    role_name = str(role or "unknown").lower()
    if role_name in {"system", "user", "assistant", "tool"}:
        return f"role_{role_name}"
    return "role_other"


def classify_tool_name(name: str) -> str:
    lowered = name.lower()
    if any(token in lowered for token in ("bash", "shell", "terminal", "exec")):
        return "shell_tool_call"
    if any(token in lowered for token in ("edit", "patch", "write", "replace")):
        return "file_mutation_tool_call"
    if any(token in lowered for token in ("read", "open", "view", "grep", "search")):
        return "file_inspection_tool_call"
    return "other_tool_call"


def action_class(turn: dict[str, Any]) -> str:
    calls = turn.get("tool_calls") if isinstance(turn.get("tool_calls"), list) else []
    classes = []
    for call in calls:
        fn = call.get("function") if isinstance(call, dict) else {}
        classes.append(classify_tool_name(str((fn or {}).get("name") or "")))
    if not classes:
        return "no_tool_call_action"
    unique = sorted(set(classes))
    if len(unique) == 1:
        return unique[0]
    return "mixed_tool_call_action"


def observation_marker_classes(turn: dict[str, Any]) -> list[str]:
    if str(turn.get("role") or "").lower() != "tool":
        return []
    content = str(turn.get("content") or "")
    return sorted({klass for marker, klass in SAFE_MARKERS.items() if marker in content})


def patch_signal_class(turn: dict[str, Any]) -> str:
    if not isinstance(turn, dict):
        return "patch_signal_absent"
    calls = turn.get("tool_calls") if isinstance(turn.get("tool_calls"), list) else []
    for call in calls:
        fn = call.get("function") if isinstance(call, dict) else {}
        if classify_tool_name(str((fn or {}).get("name") or "")) == "file_mutation_tool_call":
            return "patch_tool_call_class_present_not_apply_proof"
    return "patch_signal_absent"


def verifier_signal_class(markers: list[str]) -> str:
    present = set(markers)
    if {"verifier_pass_marker", "verifier_fail_marker"} <= present:
        return "mixed_pass_fail_marker_not_causality"
    if "verifier_pass_marker" in present:
        return "pass_marker_not_correctness_proof"
    if "verifier_fail_marker" in present:
        return "fail_marker_not_correctness_proof"
    if "verifier_error_marker" in present:
        return "error_marker_not_correctness_proof"
    if present:
        return "nonverifier_marker_present"
    return "verifier_signal_absent"


def read_private_trajectory(ref: dict[str, Any]) -> tuple[list[dict[str, Any]], str]:
    dataset_file = ref.get("dataset_file")
    if not dataset_file:
        return [], "raw_ref_missing_dataset_file"
    parquet_path = Path(str(dataset_file))
    if not parquet_path.exists():
        return [], "raw_ref_not_accessible"
    try:
        import pyarrow.parquet as pq  # type: ignore
    except Exception:
        return [], "pyarrow_unavailable"

    wanted_instance = ref.get("instance_id")
    wanted_trajectory = ref.get("trajectory_id")
    try:
        table = pq.read_table(
            parquet_path,
            columns=["instance_id", "trajectory_id", "trajectory"],
            filters=[
                ("instance_id", "=", wanted_instance),
                ("trajectory_id", "=", wanted_trajectory),
            ],
        )
    except Exception:
        return [], "raw_ref_read_failed"
    for record in table.to_pylist():
        if record.get("instance_id") == wanted_instance and record.get("trajectory_id") == wanted_trajectory:
            trajectory = record.get("trajectory")
            if isinstance(trajectory, list):
                return [turn for turn in trajectory if isinstance(turn, dict)], "raw_ref_ordered_events_available"
            return [], "raw_ref_trajectory_not_list"
    return [], "raw_ref_record_not_found"


def relative_order_relations(events: list[dict[str, Any]]) -> list[str]:
    relations: set[str] = set()
    patch_indices = [event["ordinal"] for event in events if event.get("patch_signal_class") != "patch_signal_absent"]
    verifier_indices = [event["ordinal"] for event in events if event.get("verifier_signal_class") != "verifier_signal_absent"]
    tool_indices = [event["ordinal"] for event in events if event.get("has_tool_result")]
    assistant_indices = [event["ordinal"] for event in events if event.get("event_role_class") == "role_assistant"]
    if patch_indices and verifier_indices and min(patch_indices) < max(verifier_indices):
        relations.add("patch_before_verifier_unproven_causality")
    if patch_indices and verifier_indices and min(verifier_indices) > min(patch_indices):
        relations.add("verifier_after_patch_unproven_causality")
    if assistant_indices and tool_indices and min(assistant_indices) < max(tool_indices):
        relations.add("tool_after_assistant_relative_order")
    if not relations:
        relations.add("unknown_order")
    return sorted(relations)


def skeleton_from_packet(packet: dict[str, Any], ref: dict[str, Any], rank: int) -> dict[str, Any]:
    trajectory, status = read_private_trajectory(ref)
    event_skeletons: list[dict[str, Any]] = []
    for event_index, turn in enumerate(trajectory):
        markers = observation_marker_classes(turn)
        role = role_class(turn.get("role"))
        action = action_class(turn)
        observation = markers[0] if markers else "observation_marker_absent"
        patch_signal = patch_signal_class(turn)
        verifier_signal = verifier_signal_class(markers)
        event_skeletons.append(
            {
                "ordinal": event_index,
                "event_index": event_index,
                "event_role_class": role,
                "role_class": role,
                "event_action_class": action,
                "action_class": action,
                "observation_status_class": observation,
                "observation_marker_classes": markers,
                "safe_order_evidence": "relative_order_only",
                "has_tool_call": bool(turn.get("tool_calls")),
                "has_tool_result": str(turn.get("role") or "").lower() == "tool",
                "patch_signal_class": patch_signal,
                "verifier_signal_class": verifier_signal,
                "raw_ref_hashes": {
                    "source_record_ref_hash": stable_hash(ref, 24),
                    "dataset_ref_hash": stable_hash(ref.get("dataset_file") or ref.get("dataset_name") or "missing", 24),
                    "instance_ref_hash": stable_hash(ref.get("instance_id") or "missing", 16),
                    "trajectory_ref_hash": stable_hash(ref.get("trajectory_id") or "missing", 16),
                    "source_packet_hash": stable_hash(packet.get("packet_id") or "missing", 20),
                },
            }
        )
    packet_id = f"{STAGE}::{stable_hash({'packet': packet.get('packet_id'), 'rank': rank}, 20)}"
    return {
        "stage": STAGE,
        "record_type": "blocked_raw_private_ordered_event_skeleton",
        "packet_id": packet_id,
        "source_stage": SOURCE_STAGE,
        "source_packet_hash": stable_hash(packet.get("packet_id") or "missing", 20),
        "language_family": str(packet.get("language_family") or "unknown"),
        "rank": rank,
        "private_parquet_read_status": status,
        "event_count": len(event_skeletons),
        "ordered_event_skeleton": event_skeletons,
        "ordered_event_skeletons": event_skeletons,
        "safe_order_relations": relative_order_relations(event_skeletons),
        "forbidden_claims_absent": True,
        "gate_results": {
            "raw_content_guard": {"passed": True, "blocker": None},
            "ordered_evidence_guard": {"passed": True, "blocker": None},
            "action_correctness_guard": {"passed": False, "blocker": "ordered_skeleton_is_not_action_correctness_proof"},
            "state_proof_guard": {"passed": False, "blocker": "state_before_after_not_authoritatively_hydrated"},
            "resolved_model_patch_guard": {"passed": False, "blocker": "resolved_or_model_patch_not_proof"},
            "causality_guard": {"passed": False, "blocker": "co_presence_is_not_causality"},
            "admission_guard": {"passed": False, "blocker": "training_admission_blocked"},
        },
        "raw_ref_hashes": {
            "source_record_ref_hash": stable_hash(ref, 24),
            "dataset_ref_hash": stable_hash(ref.get("dataset_file") or ref.get("dataset_name") or "missing", 24),
            "instance_ref_hash": stable_hash(ref.get("instance_id") or "missing", 16),
            "trajectory_ref_hash": stable_hash(ref.get("trajectory_id") or "missing", 16),
        },
        "claim_boundary": {
            "no_correctness_inference": True,
            "no_state_delta_inference": True,
            "no_stop_continue_gold": True,
            "no_verifier_causality_inference": True,
        },
        "raw_content_policy": RAW_CONTENT_POLICY,
        "blockers": BLOCKERS,
        **ZERO_FLAGS,
    }


def validate_rows(rows: list[dict[str, Any]]) -> list[str]:
    issues: list[str] = []
    for row_index, row in enumerate(rows, 1):
        for key, expected in ZERO_FLAGS.items():
            if row.get(key) != expected:
                issues.append(f"row_{row_index}_{key}_not_zero_or_false")
        events = row.get("ordered_event_skeleton") or []
        if row.get("event_count") != len(events):
            issues.append(f"row_{row_index}_event_count_mismatch")
        for event_index, event in enumerate(events):
            if event.get("ordinal") != event_index or event.get("event_index") != event_index:
                issues.append(f"row_{row_index}_event_{event_index}_index_not_ordered")
            for required_event_field in ["event_role_class", "event_action_class", "observation_status_class", "safe_order_evidence"]:
                if required_event_field not in event:
                    issues.append(f"row_{row_index}_event_{event_index}_missing_{required_event_field}")
    return issues


def scan_value(value: Any, artifact: str, issues: list[dict[str, Any]], key_path: str = "") -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            scan_value(child, artifact, issues, f"{key_path}.{key}" if key_path else str(key))
        return
    if isinstance(value, list):
        for index, child in enumerate(value):
            scan_value(child, artifact, issues, f"{key_path}[{index}]")
        return
    if not isinstance(value, str):
        return
    if ABS_PATH_RE.search(value):
        issues.append({"artifact": artifact, "issue": "absolute_path_string", "key": key_path})
    if URL_RE.search(value):
        issues.append({"artifact": artifact, "issue": "url_string", "key": key_path})
    if MULTILINE_RE.search(value):
        issues.append({"artifact": artifact, "issue": "multiline_string", "key": key_path})
    if key_path.endswith("_hash") and not HEX_RE.match(value) and value != "missing":
        issues.append({"artifact": artifact, "issue": "non_hash_value_in_hash_field", "key": key_path})


def guardrail_scan(paths: list[Path]) -> dict[str, Any]:
    issues: list[dict[str, Any]] = []
    parsed_json_values = 0
    scanned_jsonl_rows = 0
    for path in paths:
        text = path.read_text(encoding="utf-8")
        if ABS_PATH_RE.search(text):
            issues.append({"artifact": path.name, "issue": "absolute_path_pattern"})
        if URL_RE.search(text):
            issues.append({"artifact": path.name, "issue": "url_pattern"})
        if path.suffix == ".jsonl":
            for line_number, line in enumerate(text.splitlines(), 1):
                if not line.strip():
                    continue
                scanned_jsonl_rows += 1
                try:
                    value = json.loads(line)
                except json.JSONDecodeError:
                    issues.append({"artifact": path.name, "issue": "invalid_jsonl", "line": line_number})
                    continue
                scan_value(value, path.name, issues, f"line[{line_number}]")
        else:
            try:
                value = json.loads(text)
            except json.JSONDecodeError:
                issues.append({"artifact": path.name, "issue": "invalid_json"})
                continue
            parsed_json_values += 1
            scan_value(value, path.name, issues)
    return {
        "scan_passed": not issues,
        "issues": issues,
        "scanned_artifact_count": len(paths),
        "parsed_json_values": parsed_json_values,
        "scanned_jsonl_rows": scanned_jsonl_rows,
    }


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    source_packets = read_jsonl(SOURCE_PACKETS)
    selected_packets = select_one_per_language(source_packets)
    raw_ref_by_hash = source_ref_index(read_jsonl(STAGE12327_OPEN_SWE))

    rows: list[dict[str, Any]] = []
    missing_private_refs = 0
    for rank, packet in enumerate(selected_packets, 1):
        ref_hash = str(packet.get("source_record_ref_hash") or "")
        ref = raw_ref_by_hash.get(ref_hash)
        if not ref:
            missing_private_refs += 1
            ref = {}
        rows.append(skeleton_from_packet(packet, ref, rank))

    row_path = OUT / ROWS_NAME
    local_summary_path = OUT / LOCAL_SUMMARY_NAME
    guardrail_path = OUT / GUARDRAIL_NAME
    write_jsonl(row_path, rows)

    schema_issues = validate_rows(rows)
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

    summary: dict[str, Any] = {
        "stage": STAGE,
        "decision": "no_admission_ordered_event_skeleton_preflight_complete",
        "source_stage": SOURCE_STAGE,
        "source_boundary": "stage12395_packets_plus_private_stage12327_raw_ref_join",
        "input_packet_count": len(source_packets),
        "selected_packet_count": len(selected_packets),
        "max_packets": MAX_PACKETS,
        "selection_policy": "one_per_language_if_available_using_stage12395_rank_order",
        "language_family_counts": dict(sorted(language_counts.items())),
        "total_ordered_event_count": sum(row["event_count"] for row in rows),
        "private_parquet_read_status_counts": dict(sorted(read_status_counts.items())),
        "missing_private_ref_count": missing_private_refs,
        "role_class_counts": dict(sorted(role_counts.items())),
        "action_class_counts": dict(sorted(action_counts.items())),
        "observation_marker_class_counts": dict(sorted(marker_counts.items())),
        "patch_signal_class_counts": dict(sorted(patch_signal_counts.items())),
        "verifier_signal_class_counts": dict(sorted(verifier_signal_counts.items())),
        "schema_issue_count": len(schema_issues),
        "schema_issues": schema_issues,
        "claim_boundary": {
            "correctness_inferred": False,
            "state_delta_inferred": False,
            "stop_continue_gold_inferred": False,
            "verifier_causality_inferred": False,
        },
        "raw_content_policy": RAW_CONTENT_POLICY,
        "blockers": BLOCKERS,
        "generated_artifacts": [ROWS_NAME, LOCAL_SUMMARY_NAME, GUARDRAIL_NAME],
        **ZERO_FLAGS,
    }
    write_json(local_summary_path, summary)
    write_json(SUMMARY, summary)

    guardrail = guardrail_scan([row_path, local_summary_path, SUMMARY])
    write_json(guardrail_path, guardrail)
    summary["guardrail_scan"] = guardrail
    summary["guardrail_issue_count"] = len(guardrail["issues"])
    write_json(local_summary_path, summary)
    write_json(SUMMARY, summary)
    if schema_issues or guardrail["issues"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
