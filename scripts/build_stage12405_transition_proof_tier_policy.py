#!/usr/bin/env python3
"""Stage12405 transition proof tier policy.

Consumes Stage12402 private event digests, Stage12403 replay-target windows,
and Stage12404 reconstruction requests. Emits a fail-closed policy artifact
that assigns proof-tier and supervision-strength candidates only. It creates no
training rows, runs no replay, invokes no proof assistant, and emits no raw
commands, outputs, paths, URLs, source text, issue bodies, patch bodies/diffs,
or line contents.
"""
from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12405_transition_proof_tier_policy"
OUT = ROOT / "runs/local/artifacts" / STAGE
SUMMARY = ROOT / "runs/summaries" / f"{STAGE}.json"

STAGE12402_DIGESTS = (
    ROOT
    / "runs/local/artifacts/stage12402_open_swe_private_event_digest_extractor/"
    / "open_swe_private_event_digests.jsonl"
)
STAGE12402_SUMMARY = (
    ROOT
    / "runs/local/artifacts/stage12402_open_swe_private_event_digest_extractor/"
    / "open_swe_private_event_digest_summary.json"
)
STAGE12403_WINDOWS = (
    ROOT
    / "runs/local/artifacts/stage12403_open_swe_event_digest_window_segmenter/"
    / "open_swe_event_digest_replay_target_windows.jsonl"
)
STAGE12403_SUMMARY = (
    ROOT
    / "runs/local/artifacts/stage12403_open_swe_event_digest_window_segmenter/"
    / "open_swe_event_digest_window_segmenter_summary.json"
)
STAGE12404_REQUEST_ITEMS = (
    ROOT
    / "runs/local/artifacts/stage12404_open_swe_replay_state_reconstruction_request/"
    / "open_swe_replay_state_reconstruction_request_items.jsonl"
)
STAGE12404_REQUEST = (
    ROOT
    / "runs/local/artifacts/stage12404_open_swe_replay_state_reconstruction_request/"
    / "open_swe_replay_state_reconstruction_request.json"
)
STAGE12404_SUMMARY = (
    ROOT
    / "runs/local/artifacts/stage12404_open_swe_replay_state_reconstruction_request/"
    / "open_swe_replay_state_reconstruction_request_summary.json"
)

POLICY_ROWS_NAME = "open_swe_transition_proof_tier_policy_records.jsonl"
FORMAL_RULES_NAME = "open_swe_formal_rule_candidates.jsonl"
POLICY_NAME = "open_swe_transition_proof_tier_policy.json"
LOCAL_SUMMARY_NAME = "open_swe_transition_proof_tier_policy_summary.json"
GUARDRAIL_NAME = "guardrail_scan.json"

TIERS = [
    "weak_digest_supervision",
    "replay_request_pending",
    "replay_calibrated_supervision",
    "level3_reconstructed_proof",
    "formal_rule_grounded",
    "sealed_eval_only",
    "quarantine",
]
ZERO_ADMISSION_FLAGS: dict[str, int | bool] = {
    "admission": False,
    "training_allowed": False,
    "training_row_count": 0,
    "level3_admitted": 0,
    "patch_trace_admitted": 0,
    "strict_eval_eligible": 0,
    "source_heldout_admissible": 0,
    "repair_claim_admitted": 0,
    "transition_window_admitted": 0,
    "replay_target_admitted": 0,
    "reconstruction_request_admitted": 0,
    "policy_candidate_admitted": 0,
    "formal_rule_admitted": 0,
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
    "patch_diffs_emitted": False,
}
CLAIM_BOUNDARY: dict[str, bool] = {
    "policy_assignment_only": True,
    "proof_assistant_invoked": False,
    "replay_executed": False,
    "training_rows_created": False,
    "state_before_claim_emitted": False,
    "state_after_claim_emitted": False,
    "patch_application_claim_emitted": False,
    "verifier_relevance_claim_emitted": False,
    "causal_linkage_claim_emitted": False,
    "stop_continue_claim_emitted": False,
    "correct_next_action_policy_claim_emitted": False,
    "transition_proof_claim_emitted": False,
    "training_admission_claim_emitted": False,
}
PROOF_SLOT_STATUS = {
    "state_before": "blocked_missing_authoritative_state_before",
    "state_after": "blocked_missing_authoritative_state_after",
    "patch_application": "blocked_missing_patch_application_proof",
    "verifier_relevance": "blocked_missing_verifier_relevance_proof",
    "causal_linkage": "blocked_missing_causal_verifier_linkage",
    "stop_continue": "blocked_missing_stop_continue_proof",
    "correct_next_action_policy": "blocked_correct_next_action_not_authoritatively_proven",
    "root_split_no_leak": "blocked_root_split_no_leak_not_reverified",
    "option_permutation": "blocked_option_permutation_safety_not_reverified",
}
BASE_BLOCKERS = [
    "blocked_fail_closed_policy_assignment_only",
    "blocked_not_training_row",
    "blocked_no_level3_reconstruction_proof",
    "blocked_missing_authoritative_state_before",
    "blocked_missing_authoritative_state_after",
    "blocked_missing_patch_application_proof",
    "blocked_missing_verifier_relevance_proof",
    "blocked_missing_causal_verifier_linkage",
    "blocked_missing_stop_continue_proof",
    "blocked_correct_next_action_not_authoritatively_proven",
    "blocked_root_split_no_leak_not_reverified",
    "blocked_option_permutation_safety_not_reverified",
    "training_admission_blocked",
    "no_raw_content_emitted",
]
FORMAL_RULE_CANDIDATES = [
    {
        "rule_family": "temporal_verifier_order",
        "rule_code": "no_verifier_success_before_verifier_ran",
        "obligation_class": "verifier_success_requires_prior_verifier_action_ref",
        "blocked_by": ["blocked_missing_verifier_identity_order_proof", "blocked_missing_authoritative_status_transition"],
    },
    {
        "rule_family": "patch_application_boundary",
        "rule_code": "patch_signal_is_not_apply_proof",
        "obligation_class": "patch_signal_requires_application_status_evidence",
        "blocked_by": ["blocked_missing_patch_application_proof", "blocked_patch_body_not_emitted"],
    },
    {
        "rule_family": "causality_boundary",
        "rule_code": "co_presence_is_not_causality",
        "obligation_class": "ordered_co_presence_requires_causal_linkage_evidence",
        "blocked_by": ["blocked_missing_causal_verifier_linkage", "co_presence_order_candidate_not_causality"],
    },
    {
        "rule_family": "stop_continue_boundary",
        "rule_code": "stop_blocked_without_verifier_state_proof",
        "obligation_class": "stop_continue_requires_state_and_verifier_status_proof",
        "blocked_by": [
            "blocked_missing_authoritative_state_before",
            "blocked_missing_authoritative_state_after",
            "blocked_missing_verifier_relevance_proof",
            "blocked_missing_stop_continue_proof",
        ],
    },
    {
        "rule_family": "source_split_leakage",
        "rule_code": "root_split_no_leak_gates",
        "obligation_class": "root_identity_and_split_gate_requires_no_leak_audit",
        "blocked_by": ["blocked_root_split_no_leak_not_reverified", "blocked_source_heldout_not_admissible"],
    },
    {
        "rule_family": "option_permutation_safety",
        "rule_code": "option_permutation_safety",
        "obligation_class": "candidate_option_order_must_not_change_policy_label",
        "blocked_by": ["blocked_option_permutation_safety_not_reverified", "blocked_correct_next_action_not_authoritatively_proven"],
    },
]

ABS_PATH_RE = re.compile(r"(?<![A-Za-z0-9_])/(?:[A-Za-z0-9._-]+/){2,}[A-Za-z0-9._-]+")
URL_RE = re.compile(r"https?://|www\.", re.IGNORECASE)
MULTILINE_RE = re.compile(r"[\r\n]")
HEX_RE = re.compile(r"^[0-9a-f]{12,64}$")
RAW_KEY_RE = re.compile(
    r"(?:^|_)(trajectory|command|output|patch|diff|source_text|issue_body|line_content|stdout|stderr|url|path)(?:$|_)",
    re.IGNORECASE,
)
SAFE_KEY_CONTEXT_RE = re.compile(
    r"(?:status|code|codes|proof|gate|hash|hashes|class|classes|signal|policy|count|counts|bucket|ref|refs|emitted|allowed|scan|claim|application|body|boundary)",
    re.IGNORECASE,
)


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


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


def stage_file_hash(path: Path) -> str:
    if not path.exists():
        return "missing"
    return hashlib.sha256(path.read_bytes()).hexdigest()[:24]


def is_hash(value: Any, allow_missing: bool = True) -> bool:
    text = str(value or "")
    return (allow_missing and text == "missing") or bool(HEX_RE.match(text))


def zero_ok(summary: dict[str, Any]) -> bool:
    flags = summary.get("zero_admission_flags") if isinstance(summary.get("zero_admission_flags"), dict) else {}
    return (
        summary.get("training_allowed", flags.get("training_allowed")) is False
        and int(summary.get("training_row_count", flags.get("training_row_count", -1)) or 0) == 0
    )


def non_absent_count(counts: dict[str, Any], key: str, absent_class: str) -> int:
    values = counts.get(key) if isinstance(counts.get(key), dict) else {}
    return sum(int(count) for klass, count in values.items() if str(klass) != absent_class)


def proof_slots_all_blocked(extra_evidence_class: str) -> dict[str, dict[str, str]]:
    return {
        slot: {
            "proof_status": "blocked",
            "status_code": status_code,
            "evidence_class": extra_evidence_class,
            "proof_ref_hash": "missing",
        }
        for slot, status_code in PROOF_SLOT_STATUS.items()
    }


def blocker_union(*groups: Any) -> list[str]:
    blockers: set[str] = set(BASE_BLOCKERS)
    for group in groups:
        if isinstance(group, dict):
            blockers.update(str(value) for value in group.values())
        elif isinstance(group, list):
            blockers.update(str(value) for value in group)
    return sorted(blockers)


def build_source_policy_record(source_stage: str, source_type: str, source_ref_hash: str, row: dict[str, Any], rank: int) -> dict[str, Any]:
    if source_stage.endswith("private_event_digest_extractor"):
        tier = "weak_digest_supervision"
        strength = "weak_digest_class_signal_only"
        evidence_class = "safe_private_digest_counts_only_not_proof"
        blockers = blocker_union(row.get("unresolved_blockers", []), ["digest_only_not_training_row"])
    elif source_stage.endswith("event_digest_window_segmenter"):
        tier = "weak_digest_supervision"
        strength = "bounded_transition_window_candidate_not_label"
        evidence_class = "safe_replay_target_window_only_not_proof"
        blockers = blocker_union(row.get("blockers", []), ["co_presence_order_candidate_not_causality"])
    else:
        tier = "replay_request_pending"
        strength = "bounded_reconstruction_request_pending_not_replayed"
        evidence_class = "safe_reconstruction_request_only_not_proof"
        blockers = blocker_union(row.get("blockers", []), ["blocked_replay_not_executed"])

    counts = row.get("aggregate_counts") or row.get("window_class_counts") or {}
    if not isinstance(counts, dict):
        counts = {}
    basis = {
        "source_stage": source_stage,
        "source_type": source_type,
        "source_ref_hash": source_ref_hash,
        "rank": rank,
        "tier": tier,
    }
    return {
        "stage": STAGE,
        "record_type": "fail_closed_transition_proof_tier_policy_candidate",
        "policy_record_id": f"{STAGE}::{stable_hash(basis, 20)}",
        "source_stage": source_stage,
        "source_record_type": source_type,
        "source_record_ref_hash": source_ref_hash,
        "source_rank": rank,
        "language": str(row.get("language") or row.get("language_family") or "unknown"),
        "repo_hash": str(row.get("repo_hash") or row.get("repo_family_hash") or "missing"),
        "proof_tier_candidate": tier,
        "current_tier": tier,
        "supervision_strength_candidate": strength,
        "candidate_status": "blocked_fail_closed_candidate_only",
        "evidence_class": evidence_class,
        "proof_slots": proof_slots_all_blocked(evidence_class),
        "all_proof_slots_blocked": True,
        "class_count_digest": {
            "event_count": int(row.get("event_count") or counts.get("event_count") or 0),
            "patch_signal_count": non_absent_count(counts, "patch_signal_class_counts", "patch_signal_absent"),
            "verifier_signal_count": non_absent_count(counts, "verifier_signal_class_counts", "verifier_signal_absent"),
            "tool_action_observation_transition_count": int(counts.get("tool_action_observation_transition_count") or 0),
            "tool_observation_action_transition_count": int(counts.get("tool_observation_action_transition_count") or 0),
        },
        "blockers": blockers,
        "blocker_codes": blockers,
        "claim_boundary": CLAIM_BOUNDARY,
        "raw_content_policy": RAW_CONTENT_POLICY,
        "zero_admission_flags": ZERO_ADMISSION_FLAGS,
        **ZERO_ADMISSION_FLAGS,
    }


def build_formal_rule_record(rule: dict[str, Any], rank: int) -> dict[str, Any]:
    blockers = blocker_union(rule.get("blocked_by", []), ["blocked_formal_rule_candidate_not_machine_checked"])
    basis = {"rule_code": rule["rule_code"], "rank": rank, "stage": STAGE}
    return {
        "stage": STAGE,
        "record_type": "formal_rule_candidate",
        "policy_record_id": f"{STAGE}::{stable_hash(basis, 20)}",
        "source_stage": STAGE,
        "source_record_type": "formal_rule_candidate",
        "source_record_ref_hash": stable_hash(basis, 24),
        "source_rank": rank,
        "language": "all",
        "repo_hash": "missing",
        "proof_tier_candidate": "formal_rule_grounded",
        "current_tier": "formal_rule_grounded",
        "supervision_strength_candidate": "formal_rule_obligation_candidate_only",
        "candidate_status": "blocked_until_machine_checked_and_connected_to_authoritative_evidence",
        "rule_family": str(rule["rule_family"]),
        "rule_code": str(rule["rule_code"]),
        "obligation_class": str(rule["obligation_class"]),
        "formalization_status": "candidate_not_machine_checked",
        "proof_assistant_invoked": False,
        "training_label_source": "none",
        "proof_slots": proof_slots_all_blocked("formal_rule_candidate_not_machine_checked"),
        "all_proof_slots_blocked": True,
        "blockers": blockers,
        "blocker_codes": blockers,
        "claim_boundary": CLAIM_BOUNDARY,
        "raw_content_policy": RAW_CONTENT_POLICY,
        "zero_admission_flags": ZERO_ADMISSION_FLAGS,
        **ZERO_ADMISSION_FLAGS,
    }


def validate_policy_record(row: dict[str, Any], index: int) -> list[str]:
    issues: list[str] = []
    required = [
        "policy_record_id",
        "source_stage",
        "source_record_type",
        "source_record_ref_hash",
        "language",
        "proof_tier_candidate",
        "current_tier",
        "supervision_strength_candidate",
        "candidate_status",
        "proof_slots",
        "blockers",
        "claim_boundary",
        "raw_content_policy",
        "zero_admission_flags",
    ]
    for key in required:
        if key not in row:
            issues.append(f"row_{index}_missing_{key}")
    tier = str(row.get("proof_tier_candidate") or "")
    if tier not in TIERS:
        issues.append(f"row_{index}_unknown_tier")
    if row.get("current_tier") != row.get("proof_tier_candidate"):
        issues.append(f"row_{index}_current_tier_alias_mismatch")
    if not is_hash(row.get("source_record_ref_hash"), allow_missing=False):
        issues.append(f"row_{index}_source_record_ref_hash_not_hash")
    slots = row.get("proof_slots") if isinstance(row.get("proof_slots"), dict) else {}
    for slot, status_code in PROOF_SLOT_STATUS.items():
        status = slots.get(slot) if isinstance(slots.get(slot), dict) else {}
        if status.get("proof_status") != "blocked":
            issues.append(f"row_{index}_proof_slot_{slot}_not_blocked")
        if status.get("status_code") != status_code:
            issues.append(f"row_{index}_proof_slot_{slot}_status_code_mismatch")
        if status.get("proof_ref_hash") != "missing":
            issues.append(f"row_{index}_proof_slot_{slot}_proof_ref_not_missing")
    if row.get("all_proof_slots_blocked") is not True:
        issues.append(f"row_{index}_all_proof_slots_blocked_not_true")
    if not row.get("blockers"):
        issues.append(f"row_{index}_blockers_empty")
    if row.get("blocker_codes") != row.get("blockers"):
        issues.append(f"row_{index}_blocker_codes_alias_mismatch")
    claim_boundary = row.get("claim_boundary") if isinstance(row.get("claim_boundary"), dict) else {}
    for key, expected in CLAIM_BOUNDARY.items():
        if claim_boundary.get(key) != expected:
            issues.append(f"row_{index}_claim_boundary_{key}_mismatch")
    raw_policy = row.get("raw_content_policy") if isinstance(row.get("raw_content_policy"), dict) else {}
    for key, expected in RAW_CONTENT_POLICY.items():
        if raw_policy.get(key) != expected:
            issues.append(f"row_{index}_raw_content_policy_{key}_mismatch")
    zero_flags = row.get("zero_admission_flags") if isinstance(row.get("zero_admission_flags"), dict) else {}
    for key, expected in ZERO_ADMISSION_FLAGS.items():
        if zero_flags.get(key) != expected:
            issues.append(f"row_{index}_zero_admission_flags_{key}_mismatch")
        if row.get(key) != expected:
            issues.append(f"row_{index}_{key}_not_zero_or_false")
    if row.get("record_type") == "formal_rule_candidate":
        for key in ["rule_family", "rule_code", "obligation_class", "formalization_status"]:
            if not row.get(key):
                issues.append(f"row_{index}_formal_rule_missing_{key}")
        if row.get("proof_assistant_invoked") is not False:
            issues.append(f"row_{index}_formal_rule_invoked_proof_assistant")
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
        for list_index, child in enumerate(value):
            scan_value(child, artifact, issues, f"{key_path}[{list_index}]")
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
            continue
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
    digest_rows = read_jsonl(STAGE12402_DIGESTS)
    window_rows = read_jsonl(STAGE12403_WINDOWS)
    request_items = read_jsonl(STAGE12404_REQUEST_ITEMS)
    stage12402_summary = read_json(STAGE12402_SUMMARY)
    stage12403_summary = read_json(STAGE12403_SUMMARY)
    stage12404_summary = read_json(STAGE12404_SUMMARY)

    policy_rows: list[dict[str, Any]] = []
    for rank, row in enumerate(digest_rows, 1):
        policy_rows.append(
            build_source_policy_record(
                "stage12402_open_swe_private_event_digest_extractor",
                "private_event_digest",
                stable_hash(row.get("digest_item_id") or "missing", 24),
                row,
                rank,
            )
        )
    for rank, row in enumerate(window_rows, 1):
        policy_rows.append(
            build_source_policy_record(
                "stage12403_open_swe_event_digest_window_segmenter",
                "replay_target_window",
                stable_hash(row.get("window_id") or "missing", 24),
                row,
                rank,
            )
        )
    for rank, row in enumerate(request_items, 1):
        policy_rows.append(
            build_source_policy_record(
                "stage12404_open_swe_replay_state_reconstruction_request",
                "reconstruction_request_item",
                stable_hash(row.get("request_id") or "missing", 24),
                row,
                rank,
            )
        )

    formal_rule_rows = [build_formal_rule_record(rule, rank) for rank, rule in enumerate(FORMAL_RULE_CANDIDATES, 1)]
    all_records = policy_rows + formal_rule_rows

    policy_rows_path = OUT / POLICY_ROWS_NAME
    formal_rules_path = OUT / FORMAL_RULES_NAME
    policy_path = OUT / POLICY_NAME
    local_summary_path = OUT / LOCAL_SUMMARY_NAME
    guardrail_path = OUT / GUARDRAIL_NAME

    write_jsonl(policy_rows_path, all_records)
    write_jsonl(formal_rules_path, formal_rule_rows)

    schema_issues = [issue for index, row in enumerate(all_records, 1) for issue in validate_policy_record(row, index)]
    source_stage_counts = Counter(str(row.get("source_stage") or "missing") for row in all_records)
    tier_counts = Counter(str(row.get("proof_tier_candidate") or "missing") for row in all_records)
    for tier in TIERS:
        tier_counts.setdefault(tier, 0)
    language_counts = Counter(str(row.get("language") or "unknown") for row in all_records)
    rule_family_counts = Counter(
        str(row.get("rule_family") or "not_formal_rule") for row in all_records if row.get("record_type") == "formal_rule_candidate"
    )
    blocker_counts = Counter(blocker for row in all_records for blocker in row.get("blockers", []))
    zero_admission = all(row.get(key) == value for row in all_records for key, value in ZERO_ADMISSION_FLAGS.items())
    upstream_zero = all(zero_ok(summary) for summary in [stage12402_summary, stage12403_summary, stage12404_summary])

    policy = {
        "stage": STAGE,
        "artifact_type": "fail_closed_transition_proof_tier_policy",
        "decision": "proof_tier_candidates_assigned_no_training_rows_no_admission",
        "tier_vocab": TIERS,
        "tier_policy": {
            "weak_digest_supervision": "safe_digest_class_signal_only_not_proof",
            "replay_request_pending": "safe_reconstruction_request_only_replay_not_executed",
            "replay_calibrated_supervision": "requires_completed_replay_calibration_with_authoritative_status_codes",
            "level3_reconstructed_proof": "requires_authoritative_state_patch_verifier_and_causal_linkage_proofs",
            "formal_rule_grounded": "rule_obligation_candidate_not_training_label_until_machine_checked",
            "sealed_eval_only": "request_or_candidate_kept_eval_only_until_proofs_recovered",
            "quarantine": "validation_or_guardrail_failure_only_no_admission",
        },
        "source_stages": [
            "stage12402_open_swe_private_event_digest_extractor",
            "stage12403_open_swe_event_digest_window_segmenter",
            "stage12404_open_swe_replay_state_reconstruction_request",
        ],
        "record_count": len(all_records),
        "total_records": len(all_records),
        "policy_candidate_record_count": len(policy_rows),
        "formal_rule_candidate_count": len(formal_rule_rows),
        "counts_by_tier": dict(sorted(tier_counts.items())),
        "proof_tier_counts": dict(sorted(tier_counts.items())),
        "supervision_strength_counts": dict(
            sorted(Counter(str(row.get("supervision_strength_candidate") or "missing") for row in all_records).items())
        ),
        "counts_by_source_stage": dict(sorted(source_stage_counts.items())),
        "counts_by_language": dict(sorted(language_counts.items())),
        "counts_by_rule_family": dict(sorted(rule_family_counts.items())),
        "claim_boundary": CLAIM_BOUNDARY,
        "raw_content_policy": RAW_CONTENT_POLICY,
        "zero_admission_flags": {
            **ZERO_ADMISSION_FLAGS,
            "upstream_stage12402_zero_admission_confirmed": zero_ok(stage12402_summary),
            "upstream_stage12403_zero_admission_confirmed": zero_ok(stage12403_summary),
            "upstream_stage12404_zero_admission_confirmed": zero_ok(stage12404_summary),
        },
        **ZERO_ADMISSION_FLAGS,
    }
    write_json(policy_path, policy)

    scan = guardrail_scan([policy_rows_path, formal_rules_path, policy_path])
    write_json(guardrail_path, scan)

    summary: dict[str, Any] = {
        "stage": STAGE,
        "decision": "fail_closed_transition_proof_tier_policy_ready_no_admission",
        "generated_artifacts": [POLICY_ROWS_NAME, FORMAL_RULES_NAME, POLICY_NAME, LOCAL_SUMMARY_NAME, GUARDRAIL_NAME],
        "source_stages": policy["source_stages"],
        "source_stage_artifact_hashes": {
            "stage12402_digests_hash": stage_file_hash(STAGE12402_DIGESTS),
            "stage12402_summary_hash": stage_file_hash(STAGE12402_SUMMARY),
            "stage12403_windows_hash": stage_file_hash(STAGE12403_WINDOWS),
            "stage12403_summary_hash": stage_file_hash(STAGE12403_SUMMARY),
            "stage12404_request_items_hash": stage_file_hash(STAGE12404_REQUEST_ITEMS),
            "stage12404_request_hash": stage_file_hash(STAGE12404_REQUEST),
            "stage12404_summary_hash": stage_file_hash(STAGE12404_SUMMARY),
        },
        "input_counts": {
            "stage12402_digest_items": len(digest_rows),
            "stage12403_windows": len(window_rows),
            "stage12404_request_items": len(request_items),
        },
        "record_count": len(all_records),
        "total_records": len(all_records),
        "policy_candidate_record_count": len(policy_rows),
        "formal_rule_candidate_count": len(formal_rule_rows),
        "counts_by_tier": dict(sorted(tier_counts.items())),
        "proof_tier_counts": dict(sorted(tier_counts.items())),
        "supervision_strength_counts": dict(
            sorted(Counter(str(row.get("supervision_strength_candidate") or "missing") for row in all_records).items())
        ),
        "counts_by_source_stage": dict(sorted(source_stage_counts.items())),
        "counts_by_language": dict(sorted(language_counts.items())),
        "counts_by_rule_family": dict(sorted(rule_family_counts.items())),
        "blocker_counts": dict(sorted(blocker_counts.items())),
        "zero_admission": zero_admission and upstream_zero,
        "schema_issue_count": len(schema_issues),
        "schema_issues": schema_issues,
        "guardrail_issue_count": len(scan["issues"]),
        "guardrail_scan": scan,
        "raw_leak_findings": scan["issues"],
        "claim_boundary": CLAIM_BOUNDARY,
        "raw_content_policy": RAW_CONTENT_POLICY,
        "zero_admission_flags": {
            **ZERO_ADMISSION_FLAGS,
            "upstream_stage12402_zero_admission_confirmed": zero_ok(stage12402_summary),
            "upstream_stage12403_zero_admission_confirmed": zero_ok(stage12403_summary),
            "upstream_stage12404_zero_admission_confirmed": zero_ok(stage12404_summary),
        },
        **ZERO_ADMISSION_FLAGS,
    }
    write_json(local_summary_path, summary)
    write_json(SUMMARY, summary)


if __name__ == "__main__":
    main()
