#!/usr/bin/env python3
"""Stage12396 no-admission transition-function review candidate extractor.

Consumes Stage12395 safe semantic packets only. Emits bounded review candidates
with hashes, classes, gates, blockers, and zero admission flags. It never emits
raw trajectory text, commands, outputs, patches, source text, absolute paths, or
URLs, and it does not create training rows.
"""
from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12396_open_swe_transition_function_candidate_extractor"
OUT = ROOT / "runs/local/artifacts" / STAGE
SUMMARY = ROOT / "runs/summaries" / f"{STAGE}.json"

SOURCE_STAGE = "stage12395_open_swe_multilingual_semantic_packet_preflight"
SOURCE = (
    ROOT
    / "runs/local/artifacts"
    / SOURCE_STAGE
    / "open_swe_multilingual_semantic_packet_preflight.jsonl"
)

ROWS_NAME = "blocked_transition_function_inventory_records.jsonl"
LOCAL_SUMMARY_NAME = "blocked_transition_function_inventory_summary.json"
GUARDRAIL_NAME = "guardrail_scan.json"

REQUIRED_ROW_FIELDS = [
    "packet_id",
    "source_packet_id",
    "language_family",
    "repo_family_hash",
    "transition_function_key_candidate",
    "semantic_rule_id_candidate",
    "candidate_action_set_classes",
    "chosen_action_class_candidate",
    "observation_status_class_candidate",
    "state_before_codes_candidate",
    "state_after_codes_candidate",
    "state_delta_codes_candidate",
    "stop_continue_candidate",
    "evidence_available_codes",
    "missing_proof_codes",
    "gate_results",
    "blockers",
    "admission",
]

ZERO_FLAGS: dict[str, int | bool] = {
    "training_allowed": False,
    "level3_admitted": 0,
    "patch_trace_admitted": 0,
    "strict_eval_eligible": 0,
    "source_heldout_admissible": 0,
    "admitted_candidate_count": 0,
}

ABS_PATH_RE = re.compile(r"(?<![A-Za-z0-9_])/(?:[A-Za-z0-9._-]+/){2,}[A-Za-z0-9._-]+")
URL_RE = re.compile(r"https?://|www\.", re.IGNORECASE)
LONG_FREEFORM_RE = re.compile(r"\s.{160,}\s")
HEX_RE = re.compile(r"^[0-9a-f]{12,64}$")

SAFE_STRING_EXACT = {
    STAGE,
    SOURCE_STAGE,
    ROWS_NAME,
    LOCAL_SUMMARY_NAME,
    GUARDRAIL_NAME,
    "no_admission_aggregate_transition_inventory_only",
    "stage12395_safe_packets_only",
    "review_candidate_only",
}

SAFE_PREFIXES = (
    "stage12396_open_swe_transition_function_candidate_extractor::",
    "tf_candidate_",
    "tf_rule_",
)

ALLOWED_ACTION_CLASSES = {
    "file_mutation_tool_call",
    "other_tool_call",
    "selected_test_target_hash_observed",
    "shell_tool_call",
    "tool_call_name_hash_observed",
    "no_action_class_signal",
}

ALLOWED_OBSERVATION_CLASSES = {
    "assertion_marker",
    "cargo_test_marker",
    "maven_test_marker",
    "npm_test_marker",
    "pytest_marker",
    "traceback_marker",
    "verifier_error_marker",
    "verifier_fail_marker",
    "verifier_pass_marker",
    "observation_status_missing",
}

BLOCKERS = [
    "admission_boundary_false",
    "causal_transition_function_not_proven",
    "chosen_action_is_review_candidate_not_policy_gold",
    "raw_private_stage12395_source_only",
    "state_before_after_not_authoritatively_hydrated",
    "transition_function_semantic_rule_not_admitted",
    "verifier_relevance_not_proven",
]


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


def stable_hash(value: Any, n: int = 20) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:n]


def safe_count_map(value: Any) -> dict[str, int]:
    if not isinstance(value, dict):
        return {}
    return {str(key): int(count) for key, count in value.items() if int(count or 0) > 0}


def packet_counts(packet: dict[str, Any], name: str) -> dict[str, int]:
    semantic_counts = packet.get("semantic_counts") if isinstance(packet.get("semantic_counts"), dict) else {}
    return safe_count_map(semantic_counts.get(name))


def action_set_classes(packet: dict[str, Any]) -> list[str]:
    counts = packet_counts(packet, "command_class_counts")
    classes = sorted(key for key in counts if key in ALLOWED_ACTION_CLASSES)
    return classes or ["no_action_class_signal"]


def chosen_action_class(actions: list[str]) -> str:
    action_set = set(actions)
    if {"file_mutation_tool_call", "shell_tool_call"} <= action_set:
        return "file_mutation_plus_shell_verification_candidate"
    if "file_mutation_tool_call" in action_set:
        return "file_mutation_candidate"
    if "shell_tool_call" in action_set:
        return "shell_verification_candidate"
    if "selected_test_target_hash_observed" in action_set:
        return "selected_test_reference_candidate"
    return "no_chosen_action_candidate"


def observation_status_class(packet: dict[str, Any]) -> str:
    counts = packet_counts(packet, "safe_status_class_counts")
    present = {key for key in counts if key in ALLOWED_OBSERVATION_CLASSES}
    if {"verifier_pass_marker", "verifier_fail_marker"} <= present:
        return "mixed_pass_fail_observation_candidate"
    if "verifier_error_marker" in present and "verifier_pass_marker" in present:
        return "mixed_pass_error_observation_candidate"
    if "verifier_pass_marker" in present:
        return "pass_marker_observation_candidate"
    if "verifier_fail_marker" in present:
        return "fail_marker_observation_candidate"
    if "verifier_error_marker" in present:
        return "error_marker_observation_candidate"
    if present:
        return "nonverifier_status_marker_observation_candidate"
    return "observation_status_missing"


def state_codes(packet: dict[str, Any]) -> tuple[list[str], list[str], list[str]]:
    before = str(packet.get("state_before_hydration_status") or "missing_authoritative_state_before")
    after = str(packet.get("state_after_hydration_status") or "missing_authoritative_state_after")
    patch_signal = str(packet.get("patch_signal_class") or "")
    test_signal = str(packet.get("test_signal_class") or "")

    before_codes = ["state_before_not_authoritatively_hydrated"]
    after_codes = ["state_after_not_authoritatively_hydrated"]
    if before != "missing_authoritative_state_before":
        before_codes.append("state_before_status_class_present")
    if after != "missing_authoritative_state_after":
        after_codes.append("state_after_status_class_present")

    delta_codes = ["state_delta_not_proven"]
    if "metadata_present" in patch_signal:
        delta_codes.append("patch_metadata_signal_present_not_apply_proof")
    if "hashes_present" in test_signal:
        delta_codes.append("selected_test_hash_signal_present_not_relevance_proof")
    return sorted(before_codes), sorted(after_codes), sorted(delta_codes)


def evidence_codes(packet: dict[str, Any], actions: list[str]) -> list[str]:
    codes = set()
    event_counts = packet_counts(packet, "event_class_counts")
    status_counts = packet_counts(packet, "safe_status_class_counts")
    if event_counts:
        codes.add("aggregate_event_class_counts_available")
    if actions and actions != ["no_action_class_signal"]:
        codes.add("aggregate_action_class_counts_available")
    if status_counts:
        codes.add("aggregate_status_marker_counts_available")
    if packet.get("source_record_ref_hash"):
        codes.add("source_packet_hash_lineage_available")
    if packet.get("repo_family_hash"):
        codes.add("repo_family_hash_available")
    if int(packet.get("selected_test_hash_count") or 0) > 0:
        codes.add("selected_test_hash_count_available")
    return sorted(codes)


def missing_proof_codes(packet: dict[str, Any]) -> list[str]:
    proof = packet.get("proof_boundary") if isinstance(packet.get("proof_boundary"), dict) else {}
    codes = []
    checks = {
        "co_presence_is_causality": "causality_proof_missing",
        "model_patch_is_apply_proof": "patch_apply_proof_missing",
        "resolved_is_verifier_proof": "resolved_metadata_not_verifier_proof",
        "selected_verifier_relevance_proven": "selected_verifier_relevance_proof_missing",
        "state_before_after_proven": "state_before_after_proof_missing",
    }
    for key, code in checks.items():
        if not bool(proof.get(key)):
            codes.append(code)
    return sorted(set(codes))


def transition_key(language: str, chosen: str, observation: str, deltas: list[str]) -> str:
    delta_part = "patch_signal" if "patch_metadata_signal_present_not_apply_proof" in deltas else "no_patch_signal"
    payload = {
        "language": language,
        "chosen": chosen,
        "observation": observation,
        "delta": delta_part,
    }
    return "tf_candidate_" + stable_hash(payload, 18)


def semantic_rule_id(language: str, actions: list[str], observation: str) -> str:
    payload = {
        "language": language,
        "actions": actions,
        "observation": observation,
        "boundary": "review_candidate_only",
    }
    return "tf_rule_" + stable_hash(payload, 18)


def stop_continue(observation: str, missing: list[str]) -> str:
    if "state_before_after_proof_missing" in missing or "causality_proof_missing" in missing:
        return "continue_review_candidate_missing_transition_proof"
    if observation.startswith("pass_marker"):
        return "stop_candidate_requires_manual_pass_relevance_review"
    return "continue_review_candidate_insufficient_observation_proof"


def candidate_from_packet(packet: dict[str, Any]) -> dict[str, Any]:
    language = str(packet.get("language_family") or "unknown")
    actions = action_set_classes(packet)
    chosen = chosen_action_class(actions)
    observation = observation_status_class(packet)
    before_codes, after_codes, delta_codes = state_codes(packet)
    missing = missing_proof_codes(packet)
    key = transition_key(language, chosen, observation, delta_codes)
    rule_id = semantic_rule_id(language, actions, observation)
    source_packet_id = str(packet.get("packet_id") or packet.get("semantic_packet_id") or "missing")
    packet_id = f"{STAGE}::{stable_hash({'source_packet_id': source_packet_id, 'key': key, 'rule': rule_id}, 20)}"
    source_gates = packet.get("gate_results") if isinstance(packet.get("gate_results"), dict) else {}
    gate_results = {
        "stage12395_safe_packet_gate": {"passed": True, "blocker": None},
        "safe_field_only_gate": {"passed": True, "blocker": None},
        "transition_function_admission_gate": {
            "passed": False,
            "blocker": "transition_function_semantic_rule_not_admitted",
        },
        "causal_proof_gate": {"passed": False, "blocker": "causal_transition_function_not_proven"},
        "state_proof_gate": {"passed": False, "blocker": "state_before_after_not_authoritatively_hydrated"},
        "policy_gold_gate": {
            "passed": False,
            "blocker": "chosen_action_is_review_candidate_not_policy_gold",
        },
        "source_packet_gate_failures": sorted(
            str(value.get("blocker"))
            for value in source_gates.values()
            if isinstance(value, dict) and value.get("blocker")
        ),
    }
    blockers = sorted(set(BLOCKERS + list(packet.get("blockers") or [])))
    row: dict[str, Any] = {
        "stage": STAGE,
        "record_type": "blocked_aggregate_transition_function_inventory_record",
        "packet_id": packet_id,
        "source_packet_id": source_packet_id,
        "review_candidate_promoted": False,
        "policy_gold_admitted": False,
        "aggregate_inventory_only": True,
        "language_family": language,
        "repo_family_hash": str(packet.get("repo_family_hash") or "missing"),
        "transition_function_key_candidate": key,
        "semantic_rule_id_candidate": rule_id,
        "candidate_action_set_classes": actions,
        "chosen_action_class_candidate": chosen,
        "observation_status_class_candidate": observation,
        "state_before_codes_candidate": before_codes,
        "state_after_codes_candidate": after_codes,
        "state_delta_codes_candidate": delta_codes,
        "stop_continue_candidate": stop_continue(observation, missing),
        "evidence_available_codes": evidence_codes(packet, actions),
        "missing_proof_codes": missing,
        "gate_results": gate_results,
        "blockers": blockers,
        "admission": False,
        **ZERO_FLAGS,
    }
    return row


def validate_schema(rows: list[dict[str, Any]]) -> list[str]:
    issues: list[str] = []
    for index, row in enumerate(rows, 1):
        missing = [field for field in REQUIRED_ROW_FIELDS if field not in row]
        if missing:
            issues.append(f"row_{index}_missing_required_fields")
        if row.get("admission") is not False:
            issues.append(f"row_{index}_admission_not_false")
        for flag, expected in ZERO_FLAGS.items():
            if row.get(flag) != expected:
                issues.append(f"row_{index}_{flag}_not_zero_or_false")
    return issues


def scan_value(value: Any, artifact: str, issues: list[dict[str, Any]], key_path: str = "") -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            child_path = f"{key_path}.{key}" if key_path else str(key)
            scan_value(child, artifact, issues, child_path)
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
    if "\n" in value or "\r" in value:
        issues.append({"artifact": artifact, "issue": "multiline_string", "key": key_path})
    if LONG_FREEFORM_RE.search(value):
        issues.append({"artifact": artifact, "issue": "long_freeform_string", "key": key_path})
    if key_path.endswith("_hash") and not HEX_RE.match(value) and value != "missing":
        issues.append({"artifact": artifact, "issue": "non_hash_value_in_hash_field", "key": key_path})
    if value.startswith(SAFE_PREFIXES) or value in SAFE_STRING_EXACT:
        return


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
                try:
                    value = json.loads(line)
                except json.JSONDecodeError:
                    issues.append({"artifact": path.name, "issue": "invalid_jsonl", "line": line_number})
                    continue
                scanned_jsonl_rows += 1
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
    source_packets = read_jsonl(SOURCE)
    candidates = [candidate_from_packet(packet) for packet in source_packets]
    schema_issues = validate_schema(candidates)

    row_path = OUT / ROWS_NAME
    local_summary_path = OUT / LOCAL_SUMMARY_NAME
    guardrail_path = OUT / GUARDRAIL_NAME
    write_jsonl(row_path, candidates)

    language_counts = Counter(row["language_family"] for row in candidates)
    repo_counts = Counter(row["repo_family_hash"] for row in candidates)
    action_counts = Counter(action for row in candidates for action in row["candidate_action_set_classes"])
    observation_counts = Counter(row["observation_status_class_candidate"] for row in candidates)
    transition_counts = Counter(row["transition_function_key_candidate"] for row in candidates)
    blocker_counts = Counter(blocker for row in candidates for blocker in row["blockers"])
    missing_counts = Counter(code for row in candidates for code in row["missing_proof_codes"])
    gate_blocker_counts = Counter()
    for row in candidates:
        gates = row["gate_results"]
        for result in gates.values():
            if isinstance(result, dict) and result.get("blocker"):
                gate_blocker_counts[str(result["blocker"])] += 1
        for blocker in gates.get("source_packet_gate_failures", []):
            gate_blocker_counts[str(blocker)] += 1

    summary: dict[str, Any] = {
        "stage": STAGE,
        "decision": "no_admission_aggregate_transition_inventory_only",
        "source_stage": SOURCE_STAGE,
        "source_boundary": "stage12395_safe_packets_only",
        "claim_boundary": "aggregate_inventory_only_no_review_candidate_promotion",
        "input_packet_count": len(source_packets),
        "inventory_record_count": len(candidates),
        "candidate_count": 0,
        "review_candidate_count": 0,
        "output_review_candidate_count": 0,
        "blocked_inventory_count": len(candidates),
        "blocked_candidate_count": len(candidates),
        "admitted_candidate_count": 0,
        "required_row_fields": REQUIRED_ROW_FIELDS,
        "schema_issue_count": len(schema_issues),
        "schema_issues": schema_issues,
        "language_family_counts": dict(sorted(language_counts.items())),
        "repo_family_hash_count": len(repo_counts),
        "max_rows_per_repo_family_hash": max(repo_counts.values(), default=0),
        "candidate_action_set_class_counts": dict(sorted(action_counts.items())),
        "observation_status_class_candidate_counts": dict(sorted(observation_counts.items())),
        "transition_function_key_candidate_count": len(transition_counts),
        "transition_function_key_candidate_counts": dict(sorted(transition_counts.items())),
        "missing_proof_code_counts": dict(sorted(missing_counts.items())),
        "blocker_counts": dict(sorted(blocker_counts.items())),
        "gate_blocker_counts": dict(sorted(gate_blocker_counts.items())),
        "raw_content_policy": {
            "raw_trajectory_text_emitted": False,
            "raw_commands_emitted": False,
            "raw_outputs_emitted": False,
            "raw_patches_emitted": False,
            "source_text_emitted": False,
            "absolute_paths_emitted": False,
            "urls_emitted": False,
        },
        "generated_artifacts": [ROWS_NAME, LOCAL_SUMMARY_NAME, GUARDRAIL_NAME],
        "forbidden_promotions": [
            "aggregate-count-derived transition candidates",
            "trajectory-observed action correctness",
            "hallucinated state deltas",
            "resolved/model_patch-derived proof",
            "patch/verifier co-presence-derived causality",
        ],
        "minimum_future_requirement": "authoritative_raw_to_safe_transition_review_packet_required",
        "minimum_future_requirement_codes": [
            "authoritative_state_before",
            "authoritative_state_after",
            "explicit_action_label",
            "verifier_relevance_proof",
            "patch_application_proof",
            "causal_before_after_verifier_linkage",
        ],
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
