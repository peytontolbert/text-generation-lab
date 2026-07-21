#!/usr/bin/env python3
"""Stage12399 fail-closed Open-SWE semantic transition reviewer.

Consumes Stage12398 ordered skeletons plus Stage12395/12327 references. The
reviewer may inspect raw-private parquet internally, but emits only bounded
hashes, classes, counts, status codes, blockers, and proof-gate decisions.
"""
from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12399_open_swe_semantic_transition_reviewer"
OUT = ROOT / "runs/local/artifacts" / STAGE
SUMMARY = ROOT / "runs/summaries" / f"{STAGE}.json"

STAGE12398_SKELETONS = (
    ROOT
    / "runs/local/artifacts/stage12398_open_swe_ordered_event_skeleton_35_preflight/"
    / "open_swe_ordered_event_skeleton_35_preflight.jsonl"
)
STAGE12395_PACKETS = (
    ROOT
    / "runs/local/artifacts/stage12395_open_swe_multilingual_semantic_packet_preflight/"
    / "open_swe_multilingual_semantic_packet_preflight.jsonl"
)
STAGE12327_OPEN_SWE = (
    ROOT
    / "runs/local/artifacts/stage12327_external_adapter_preflight/"
    / "open_swe_trace_support_candidates.jsonl"
)

ROWS_NAME = "open_swe_semantic_transition_reviewer_packets.jsonl"
LOCAL_SUMMARY_NAME = "open_swe_semantic_transition_reviewer_summary.json"
GUARDRAIL_NAME = "guardrail_scan.json"

PROOF_GATES = (
    "authoritative_state_before",
    "authoritative_state_after",
    "explicit_action_label",
    "verifier_relevance_proof",
    "patch_application_proof",
    "causal_verifier_linkage",
)

CRITIC_GATE_ALIASES = {
    "authoritative_state_before": "authoritative_state_before_gate",
    "authoritative_state_after": "authoritative_state_after_gate",
    "explicit_action_label": "explicit_action_label_gate",
    "verifier_relevance_proof": "verifier_relevance_proof_gate",
    "patch_application_proof": "patch_application_proof_gate",
    "causal_verifier_linkage": "causal_verifier_before_after_linkage_gate",
}

RAW_CONTENT_POLICY: dict[str, bool] = {
    "raw_trajectory_text_emitted": False,
    "raw_commands_emitted": False,
    "raw_outputs_emitted": False,
    "raw_patches_emitted": False,
    "source_text_emitted": False,
    "absolute_paths_emitted": False,
    "urls_emitted": False,
    "issue_bodies_emitted": False,
    "line_contents_emitted": False,
}

ZERO_ADMISSION: dict[str, int | bool] = {
    "training_allowed": False,
    "level3_admitted": 0,
    "patch_trace_admitted": 0,
    "strict_eval_eligible": 0,
    "source_heldout_admissible": 0,
}

MISSING_CODES = {
    "authoritative_state_before": "missing_authoritative_state_before",
    "authoritative_state_after": "missing_authoritative_state_after",
    "explicit_action_label": "missing_explicit_action_label",
    "verifier_relevance_proof": "missing_verifier_relevance_proof",
    "patch_application_proof": "missing_patch_application_proof",
    "causal_verifier_linkage": "missing_causal_verifier_linkage",
}

ABS_PATH_RE = re.compile(r"(?<![A-Za-z0-9_])/(?:[A-Za-z0-9._-]+/){2,}[A-Za-z0-9._-]+")
URL_RE = re.compile(r"https?://|www\.", re.IGNORECASE)
MULTILINE_RE = re.compile(r"[\r\n]")
HEX_RE = re.compile(r"^[0-9a-f]{12,64}$")
RAW_KEY_RE = re.compile(
    r"(?:^|_)(trajectory|command|output|patch|diff|source_text|issue_body|line_content|stdout|stderr|url|path)(?:$|_)",
    re.IGNORECASE,
)
SAFE_KEY_CONTEXT_RE = re.compile(
    r"(?:status|code|codes|proof|gate|hash|hashes|class|classes|signal|policy|count|counts|bucket|ref|refs|emitted|allowed)",
    re.IGNORECASE,
)


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


def bucket_count(count: int) -> str:
    if count <= 0:
        return "none"
    if count == 1:
        return "one"
    if count <= 3:
        return "two_to_three"
    if count <= 8:
        return "four_to_eight"
    return "many"


def source_packet_index(packets: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {stable_hash(packet.get("packet_id") or "missing", 20): packet for packet in packets}


def source_ref_index(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    index: dict[str, dict[str, Any]] = {}
    for row in rows:
        ref = row.get("source_record_ref") if isinstance(row.get("source_record_ref"), dict) else {}
        if ref:
            index[stable_hash(ref, 24)] = ref
    return index


def raw_private_observation_codes(ref: dict[str, Any]) -> tuple[list[str], str]:
    dataset_file = ref.get("dataset_file")
    if not dataset_file:
        return ["raw_ref_missing_dataset_file"], "raw_ref_missing_dataset_file"
    parquet_path = Path(str(dataset_file))
    if not parquet_path.exists():
        return ["raw_ref_not_accessible"], "raw_ref_not_accessible"
    try:
        import pyarrow.parquet as pq  # type: ignore
    except Exception:
        return ["pyarrow_unavailable"], "pyarrow_unavailable"

    try:
        table = pq.read_table(
            parquet_path,
            columns=["instance_id", "trajectory_id", "trajectory", "resolved"],
            filters=[
                ("instance_id", "=", ref.get("instance_id")),
                ("trajectory_id", "=", ref.get("trajectory_id")),
            ],
        )
    except Exception:
        return ["raw_ref_read_failed"], "raw_ref_read_failed"

    for record in table.to_pylist():
        if record.get("instance_id") != ref.get("instance_id") or record.get("trajectory_id") != ref.get("trajectory_id"):
            continue
        codes = ["raw_ref_private_inspected"]
        trajectory = record.get("trajectory")
        if isinstance(trajectory, list):
            role_counts = Counter(str(turn.get("role") or "unknown") for turn in trajectory if isinstance(turn, dict))
            codes.extend(f"role_{role}_bucket_{bucket_count(count)}" for role, count in sorted(role_counts.items()))
        if record.get("resolved") is not None:
            codes.append("resolved_metadata_present_not_proof")
        return sorted(codes), "raw_ref_private_inspected"
    return ["raw_ref_record_not_found"], "raw_ref_record_not_found"


def top_codes(counter: Counter[str], *, limit: int = 8) -> list[str]:
    return [code for code, _ in sorted(counter.items(), key=lambda item: (-item[1], item[0]))[:limit]]


def event_counters(events: list[dict[str, Any]]) -> dict[str, Counter[str]]:
    actions: Counter[str] = Counter()
    observations: Counter[str] = Counter()
    patches: Counter[str] = Counter()
    verifiers: Counter[str] = Counter()
    roles: Counter[str] = Counter()
    for event in events:
        actions[str(event.get("event_action_class") or event.get("action_class") or "missing_action_class")] += 1
        observations[str(event.get("observation_status_class") or "observation_status_missing")] += 1
        patches[str(event.get("patch_signal_class") or "patch_signal_missing")] += 1
        verifiers[str(event.get("verifier_signal_class") or "verifier_signal_missing")] += 1
        roles[str(event.get("event_role_class") or event.get("role_class") or "role_missing")] += 1
    return {
        "actions": actions,
        "observations": observations,
        "patches": patches,
        "verifiers": verifiers,
        "roles": roles,
    }


def proof_gates_for(events: list[dict[str, Any]], source_packet: dict[str, Any]) -> dict[str, dict[str, Any]]:
    counters = event_counters(events)
    has_explicit_action = any(
        code not in {"missing_action_class", "no_tool_call_action"} for code in counters["actions"]
    )
    source_action_signal = bool(source_packet.get("patch_signal_class") or source_packet.get("test_signal_class"))
    return {
        "authoritative_state_before": {
            "passed": False,
            "status": "missing_authoritative_state_before",
            "proof_code": None,
        },
        "authoritative_state_after": {
            "passed": False,
            "status": "missing_authoritative_state_after",
            "proof_code": None,
        },
        "explicit_action_label": {
            "passed": bool(has_explicit_action or source_action_signal),
            "status": "explicit_action_class_present" if has_explicit_action or source_action_signal else "missing_explicit_action_label",
            "proof_code": "bounded_action_class_signal" if has_explicit_action or source_action_signal else None,
        },
        "verifier_relevance_proof": {
            "passed": False,
            "status": "selected_verifier_relevance_not_proven",
            "proof_code": None,
        },
        "patch_application_proof": {
            "passed": False,
            "status": "patch_application_not_proven",
            "proof_code": None,
        },
        "causal_verifier_linkage": {
            "passed": False,
            "status": "causal_verifier_linkage_not_proven",
            "proof_code": None,
        },
    }


def critic_gate_results(gates: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
    results = {
        "raw_non_emission_gate": {
            "passed": True,
            "status": "raw_content_not_emitted",
            "proof_code": "bounded_hash_status_class_fields_only",
        },
        "bounded_packet_schema_gate": {
            "passed": True,
            "status": "bounded_packet_schema_emitted",
            "proof_code": "safe_null_packet_until_all_transition_proofs_pass",
        },
        "training_admission_gate": {
            "passed": False,
            "status": "training_admission_blocked",
            "proof_code": None,
        },
    }
    for gate, alias in CRITIC_GATE_ALIASES.items():
        results[alias] = gates[gate]
    return results


def bounded_transition_review_packet(
    *,
    skeleton: dict[str, Any],
    source_packet: dict[str, Any],
    ref: dict[str, Any],
    window_basis: dict[str, Any],
    gates: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    """Emit only bounded hashes/classes; never raw commands, outputs, source, or patches."""
    return {
        "state_before_hash": None,
        "state_after_hash": None,
        "action_label_class": gates["explicit_action_label"]["status"],
        "patch_effect_hash": None,
        "verifier_command_hash": None,
        "verifier_target_hash": None,
        "verifier_before_status_class": "unknown_without_authoritative_before_verifier",
        "verifier_after_status_class": "unknown_without_authoritative_after_verifier",
        "causal_linkage_class": gates["causal_verifier_linkage"]["status"],
        "proof_artifact_hashes": {
            "window_basis_hash": stable_hash(window_basis, 24),
            "source_packet_hash": str(skeleton.get("source_packet_hash") or "missing"),
            "source_record_ref_hash": stable_hash(ref, 24) if ref else "missing",
            "source_packet_private_hash": stable_hash(source_packet, 24) if source_packet else "missing",
        },
    }


def build_packet(
    skeleton: dict[str, Any],
    source_packet: dict[str, Any],
    ref: dict[str, Any],
    ordinal: int,
) -> dict[str, Any]:
    events = skeleton.get("ordered_event_skeletons") or skeleton.get("ordered_event_skeleton") or []
    events = [event for event in events if isinstance(event, dict)]
    counters = event_counters(events)
    gates = proof_gates_for(events, source_packet)
    missing = [MISSING_CODES[gate] for gate in PROOF_GATES if not gates[gate]["passed"]]
    raw_codes, raw_status = raw_private_observation_codes(ref)
    source_skeleton_packet_id = str(skeleton.get("packet_id") or "missing")
    repo_hash = str(source_packet.get("repo_family_hash") or stable_hash(ref.get("dataset_name") or "missing", 16))
    window_basis = {
        "skeleton_packet_id": source_skeleton_packet_id,
        "event_count": int(skeleton.get("event_count") or len(events)),
        "actions": dict(sorted(counters["actions"].items())),
        "observations": dict(sorted(counters["observations"].items())),
        "patches": dict(sorted(counters["patches"].items())),
        "verifiers": dict(sorted(counters["verifiers"].items())),
    }
    fully_proven = all(bool(gates[gate]["passed"]) for gate in PROOF_GATES)
    gate_results = critic_gate_results(gates)
    bounded_packet = bounded_transition_review_packet(
        skeleton=skeleton,
        source_packet=source_packet,
        ref=ref,
        window_basis=window_basis,
        gates=gates,
    )
    blockers = sorted(
        set(
            missing
            + [
                "blocked_fail_closed_semantic_review",
                "training_admission_blocked",
                "admission_boundary_false",
                "raw_private_only",
                "ordered_skeleton_not_training_row",
                "ordered_skeleton_is_not_transition_proof",
                "patch_signal_is_not_apply_proof",
                "verifier_marker_is_not_relevance_proof",
                "co_presence_is_not_causal_linkage",
                "no_raw_content_emitted",
            ]
        )
    )
    state_delta_codes = [
        "state_delta_not_inferred",
        f"patch_signal_bucket_{bucket_count(sum(count for code, count in counters['patches'].items() if code != 'patch_signal_absent'))}",
        f"verifier_signal_bucket_{bucket_count(sum(count for code, count in counters['verifiers'].items() if code != 'verifier_signal_absent'))}",
    ]
    return {
        "stage": STAGE,
        "record_type": "blocked_open_swe_semantic_transition_review_packet",
        "packet_id": f"{STAGE}::{stable_hash({'source': source_skeleton_packet_id, 'ordinal': ordinal}, 20)}",
        "source_skeleton_packet_id": source_skeleton_packet_id,
        "language_family": str(skeleton.get("language_family") or source_packet.get("language_family") or "unknown"),
        "repo_family_hash": repo_hash,
        "candidate_transition_window_ref_hash": stable_hash(window_basis, 24),
        "action_label_candidate": gates["explicit_action_label"]["status"],
        "state_before_status": gates["authoritative_state_before"]["status"],
        "state_after_status": gates["authoritative_state_after"]["status"],
        "verifier_relevance_status": gates["verifier_relevance_proof"]["status"],
        "patch_application_status": gates["patch_application_proof"]["status"],
        "causal_linkage_status": gates["causal_verifier_linkage"]["status"],
        "proof_gate_results": gates,
        "gate_results": gate_results,
        "bounded_transition_review_packet": bounded_packet,
        "authoritative_state_before_status": gates["authoritative_state_before"]["status"],
        "authoritative_state_before_proof": None,
        "authoritative_state_after_status": gates["authoritative_state_after"]["status"],
        "authoritative_state_after_proof": None,
        "explicit_action_label_status": gates["explicit_action_label"]["status"],
        "explicit_action_label": gates["explicit_action_label"]["proof_code"],
        "explicit_action_label_proof": gates["explicit_action_label"]["proof_code"],
        "verifier_relevance_proof": None,
        "patch_application_proof": None,
        "causal_verifier_before_after_status": gates["causal_verifier_linkage"]["status"],
        "causal_verifier_before_after_linkage_proof": None,
        "transition_candidate_class": "blocked_aggregate_ordered_skeleton_candidate",
        "state_delta_class": "state_delta_not_authoritatively_proven",
        "verifier_transition_class": "verifier_transition_not_authoritatively_proven",
        "stop_continue_class": "stop_continue_not_authoritatively_proven",
        "reviewer_emitted_raw_text": False,
        "missing_proof_codes": missing,
        "bounded_candidate_actions": [
            {
                "action_code": code,
                "count_bucket": bucket_count(count),
            }
            for code, count in sorted(counters["actions"].items())
            if code != "missing_action_class"
        ][:12],
        "observation_status_codes": top_codes(counters["observations"], limit=12),
        "state_delta_codes": state_delta_codes,
        "blockers": [] if fully_proven else blockers,
        "admission": False,
        "raw_private_inspection_status": raw_status,
        "raw_private_observation_status_codes": raw_codes,
        "source_ref_hashes": {
            "source_record_ref_hash": stable_hash(ref, 24) if ref else "missing",
            "source_packet_hash": str(skeleton.get("source_packet_hash") or "missing"),
            "skeleton_packet_hash": stable_hash(source_skeleton_packet_id, 24),
        },
        "bounded_counts": {
            "event_count_bucket": bucket_count(int(skeleton.get("event_count") or len(events))),
            "role_codes": top_codes(counters["roles"]),
            "patch_signal_codes": top_codes(counters["patches"]),
            "verifier_signal_codes": top_codes(counters["verifiers"]),
        },
        "claim_boundary": {
            "authoritative_state_claim_emitted": False,
            "verifier_relevance_claim_emitted": False,
            "patch_application_claim_emitted": False,
            "causal_linkage_claim_emitted": False,
        },
        "raw_content_policy": RAW_CONTENT_POLICY,
        **ZERO_ADMISSION,
    }


def validate_packet(packet: dict[str, Any], row_index: int) -> list[str]:
    issues: list[str] = []
    required = [
        "packet_id",
        "source_skeleton_packet_id",
        "language_family",
        "repo_family_hash",
        "candidate_transition_window_ref_hash",
        "action_label_candidate",
        "state_before_status",
        "state_after_status",
        "verifier_relevance_status",
        "patch_application_status",
        "causal_linkage_status",
        "proof_gate_results",
        "gate_results",
        "bounded_transition_review_packet",
        "authoritative_state_before_status",
        "authoritative_state_before_proof",
        "authoritative_state_after_status",
        "authoritative_state_after_proof",
        "explicit_action_label_status",
        "explicit_action_label",
        "explicit_action_label_proof",
        "verifier_relevance_proof",
        "patch_application_proof",
        "causal_verifier_before_after_status",
        "causal_verifier_before_after_linkage_proof",
        "transition_candidate_class",
        "state_delta_class",
        "verifier_transition_class",
        "stop_continue_class",
        "reviewer_emitted_raw_text",
        "missing_proof_codes",
        "bounded_candidate_actions",
        "observation_status_codes",
        "state_delta_codes",
        "blockers",
        "admission",
    ]
    for key in required:
        if key not in packet:
            issues.append(f"row_{row_index}_missing_{key}")
    for key, expected in ZERO_ADMISSION.items():
        if packet.get(key) != expected:
            issues.append(f"row_{row_index}_{key}_not_zero_or_false")
    if packet.get("admission") is not False:
        issues.append(f"row_{row_index}_admission_not_false")
    gates = packet.get("proof_gate_results") if isinstance(packet.get("proof_gate_results"), dict) else {}
    if sorted(gates) != sorted(PROOF_GATES):
        issues.append(f"row_{row_index}_proof_gate_set_mismatch")
    gate_results = packet.get("gate_results") if isinstance(packet.get("gate_results"), dict) else {}
    for required_gate in [
        "raw_non_emission_gate",
        "authoritative_state_before_gate",
        "authoritative_state_after_gate",
        "explicit_action_label_gate",
        "verifier_relevance_proof_gate",
        "patch_application_proof_gate",
        "causal_verifier_before_after_linkage_gate",
        "bounded_packet_schema_gate",
        "training_admission_gate",
    ]:
        if required_gate not in gate_results:
            issues.append(f"row_{row_index}_missing_{required_gate}")
    bounded_packet = packet.get("bounded_transition_review_packet")
    if not isinstance(bounded_packet, dict):
        issues.append(f"row_{row_index}_bounded_transition_review_packet_not_object")
    fully_proven = bool(gates) and all(bool(gates.get(gate, {}).get("passed")) for gate in PROOF_GATES)
    if not fully_proven and not packet.get("blockers"):
        issues.append(f"row_{row_index}_blocked_record_missing_blockers")
    return issues


def scan_value(value: Any, artifact: str, issues: list[dict[str, Any]], key_path: str = "") -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            child_path = f"{key_path}.{key}" if key_path else str(key)
            if (
                RAW_KEY_RE.search(str(key))
                and not SAFE_KEY_CONTEXT_RE.search(str(key))
                and isinstance(child, str)
                and child
                and not HEX_RE.match(child)
            ):
                issues.append({"artifact": artifact, "issue": "raw_like_key_with_string_value", "key": child_path})
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
    skeletons = read_jsonl(STAGE12398_SKELETONS)
    stage12395_packets = read_jsonl(STAGE12395_PACKETS)
    stage12327_rows = read_jsonl(STAGE12327_OPEN_SWE)
    packets_by_hash = source_packet_index(stage12395_packets)
    refs_by_hash = source_ref_index(stage12327_rows)

    rows: list[dict[str, Any]] = []
    missing_source_packet_count = 0
    missing_ref_count = 0
    for ordinal, skeleton in enumerate(skeletons, 1):
        source_hash = str(skeleton.get("source_packet_hash") or "")
        source_packet = packets_by_hash.get(source_hash, {})
        if not source_packet:
            missing_source_packet_count += 1
        ref_hash = str(source_packet.get("source_record_ref_hash") or skeleton.get("raw_ref_hashes", {}).get("source_record_ref_hash") or "")
        ref = refs_by_hash.get(ref_hash, {})
        if not ref:
            missing_ref_count += 1
        rows.append(build_packet(skeleton, source_packet, ref, ordinal))

    row_path = OUT / ROWS_NAME
    local_summary_path = OUT / LOCAL_SUMMARY_NAME
    guardrail_path = OUT / GUARDRAIL_NAME
    write_jsonl(row_path, rows)

    schema_issues = [issue for idx, row in enumerate(rows, 1) for issue in validate_packet(row, idx)]
    proof_pass_count = {
        gate: sum(1 for row in rows if bool(row["proof_gate_results"][gate]["passed"])) for gate in PROOF_GATES
    }
    fully_proven_packet_count = sum(
        1 for row in rows if all(bool(row["proof_gate_results"][gate]["passed"]) for gate in PROOF_GATES)
    )
    blocked_packet_count = sum(1 for row in rows if not row.get("admission"))
    language_counts = Counter(str(row.get("language_family") or "unknown") for row in rows)
    blocker_counts = Counter(blocker for row in rows for blocker in row.get("blockers", []))
    raw_status_counts = Counter(str(row.get("raw_private_inspection_status") or "unknown") for row in rows)

    summary: dict[str, Any] = {
        "stage": STAGE,
        "decision": "no_admission_fail_closed_transition_review_packet_critic",
        "source_stage": "stage12398_open_swe_ordered_event_skeleton_35_preflight",
        "source_boundary": "stage12398_ordered_skeletons_plus_stage12395_and_stage12327_private_refs",
        "input_ordered_skeleton_count": len(skeletons),
        "reviewed_packet_count": len(rows),
        "bounded_review_packet_count": len(rows),
        "input_skeleton_packet_count": len(skeletons),
        "candidate_windows_inspected": len(rows),
        "review_packet_count": len(rows),
        "proof_pass_count": proof_pass_count,
        "fully_proven_packet_count": fully_proven_packet_count,
        "blocked_packet_count": blocked_packet_count,
        "admitted_packet_count": fully_proven_packet_count if fully_proven_packet_count else 0,
        "missing_source_packet_count": missing_source_packet_count,
        "missing_private_ref_count": missing_ref_count,
        "language_family_counts": dict(sorted(language_counts.items())),
        "blocker_counts": dict(sorted(blocker_counts.items())),
        "raw_private_inspection_status_counts": dict(sorted(raw_status_counts.items())),
        "raw_leak_findings": [],
        "guardrail_scan": None,
        "schema_issue_count": len(schema_issues),
        "schema_issues": schema_issues,
        "raw_content_policy": RAW_CONTENT_POLICY,
        "claim_boundary": {
            "raw_private_semantic_reviewer": True,
            "all_records_blocked_unless_all_six_proof_gates_pass": True,
            "raw_trajectory_text_emitted": False,
            "raw_commands_emitted": False,
            "raw_outputs_emitted": False,
            "raw_patches_emitted": False,
            "source_text_emitted": False,
            "absolute_paths_emitted": False,
            "urls_emitted": False,
            "issue_bodies_emitted": False,
            "line_contents_emitted": False,
        },
        "generated_artifacts": [ROWS_NAME, LOCAL_SUMMARY_NAME, GUARDRAIL_NAME],
        **ZERO_ADMISSION,
    }
    write_json(local_summary_path, summary)
    write_json(SUMMARY, summary)

    guardrail = guardrail_scan([row_path, local_summary_path, SUMMARY])
    write_json(guardrail_path, guardrail)
    summary["guardrail_scan"] = guardrail
    summary["raw_leak_findings"] = guardrail["issues"]
    summary["guardrail_issue_count"] = len(guardrail["issues"])
    write_json(local_summary_path, summary)
    write_json(SUMMARY, summary)

    if schema_issues or guardrail["issues"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
