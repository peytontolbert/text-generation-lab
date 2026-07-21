#!/usr/bin/env python3
"""Stage12429 Open-SWE scaling ramp control.

This is a fail-closed public control artifact. It reads only the Stage12428
public request summary, treats the 100 candidate sample as a pilot rather than
a ceiling, and defines gated ramps for 100/1k/10k/full processing. It does not
read raw Open-SWE rows, emit training rows, execute replay, or admit records.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12429_open_swe_scaling_ramp_control"
OUT = ROOT / "runs/local/artifacts" / STAGE
SUMMARY = ROOT / "runs/summaries" / f"{STAGE}.json"
STAGE12428_SUMMARY = ROOT / "runs/summaries/stage12428_open_swe_private_admission_packet_request.json"

ZERO_COUNTERS: dict[str, bool | int] = {
    "training_allowed": False,
    "admission_allowed": False,
    "execution_allowed": False,
    "sampler_run": False,
    "admitted_rows": 0,
    "emitted_rows": 0,
    "emitted_training_rows": 0,
    "countable_rows": 0,
    "countable_new_rows": 0,
    "countable_as_new_train_support_rows": 0,
    "countable_as_new_proof_floor_rows": 0,
    "raw_rows_inspected": 0,
    "raw_rows_copied": 0,
    "raw_content_emitted": False,
    "replay_attempted_count": 0,
    "patch_apply_attempted_count": 0,
    "tests_run_count": 0,
}

RAW_CONTENT_POLICY = {
    "raw_trajectories_emitted": False,
    "raw_commands_emitted": False,
    "raw_outputs_emitted": False,
    "raw_diffs_emitted": False,
    "raw_patches_emitted": False,
    "raw_issue_bodies_emitted": False,
    "urls_emitted": False,
    "source_text_emitted": False,
    "raw_paths_emitted": False,
    "training_rows_emitted": False,
    "row_values_emitted": False,
    "locator_values_emitted": False,
    "schema_field_names_emitted": False,
    "private_only_fields_emitted": False,
}

FORBIDDEN_TEXT_RE = re.compile(
    r"https?://|www\.|diff --git|@@ |^\+\+\+ |^--- |<<<<<<<|"
    r"(?<![A-Za-z0-9_])/(?:[A-Za-z0-9._-]+/){2,}[A-Za-z0-9._-]+|"
    r"\b(?:Traceback \(most recent call last\)|stdout|stderr|pytest |npm |pip |git clone)\b",
    re.IGNORECASE | re.MULTILINE,
)

OVERCLAIM_RE = re.compile(
    r"\b(?:admitted|training rows|countable rows|level[_ -]?3|level[_ -]?4|closed[- ]loop|"
    r"fail[- ]to[- ]pass|verified repair|causal proof|full processing)\b",
    re.IGNORECASE,
)

ALLOWED_OVERCLAIM_CONTEXT_RE = re.compile(
    r"(not_|no_|zero|blocked|reject|required|gate|gated|candidate|pilot|control|"
    r"not claimable|not_claimable|training_allowed|admitted_rows|countable_rows|"
    r"countable_new_rows|countable_as_new|level3_candidate|level_3_diagnostic_floor|"
    r"processing_allowed|training_release_allowed|admission_release_allowed)",
    re.IGNORECASE,
)


def stable_hash(value: Any, n: int = 24) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:n]


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
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return value if isinstance(value, dict) else {}


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def safe_int(value: Any) -> int:
    try:
        return int(value)
    except Exception:
        return 0


def summarize_stage12428(packet: dict[str, Any]) -> dict[str, Any]:
    first_quota = packet.get("first_private_sample_quota")
    private_quotas = packet.get("private_sampler_quotas")
    guardrail_scan = packet.get("guardrail_scan")
    promotion_gate_status = packet.get("promotion_gate_status")
    proof_slot_counts = packet.get("proof_slot_status_counts")
    blocked_reason_counts = packet.get("blocked_reason_counts")
    bucket_status_counts = packet.get("bucket_status_counts")
    return {
        "source_stage": packet.get("stage"),
        "source_decision": packet.get("decision"),
        "source_training_allowed": packet.get("training_allowed", False),
        "source_admission_allowed": packet.get("admission_allowed", False),
        "source_guardrail_scan_passed": packet.get("guardrail_scan_passed", False),
        "source_raw_leak_count": safe_int(packet.get("raw_leak_count")),
        "source_overclaim_count": safe_int(packet.get("overclaim_count")),
        "source_candidate_supply_rows": safe_int(packet.get("candidate_supply_rows")),
        "source_first_private_sample_quota": first_quota if isinstance(first_quota, dict) else {},
        "source_private_sampler_quotas": private_quotas if isinstance(private_quotas, dict) else {},
        "source_promotion_gate_status": promotion_gate_status if isinstance(promotion_gate_status, dict) else {},
        "source_guardrail_scan": guardrail_scan if isinstance(guardrail_scan, dict) else {},
        "source_proof_slot_status_counts": proof_slot_counts if isinstance(proof_slot_counts, dict) else {},
        "source_blocked_reason_counts": blocked_reason_counts if isinstance(blocked_reason_counts, dict) else {},
        "source_bucket_status_counts": bucket_status_counts if isinstance(bucket_status_counts, dict) else {},
        "source_raw_rows_inspected": safe_int(packet.get("raw_rows_inspected")),
        "source_raw_rows_copied": safe_int(packet.get("raw_rows_copied")),
        "source_raw_content_emitted": bool(packet.get("raw_content_emitted")),
        "source_emitted_training_rows": safe_int(packet.get("emitted_training_rows")),
        "source_admitted_rows": safe_int(packet.get("admitted_rows")),
    }


def gate_bundle(
    *,
    prior_phase: str | None,
    target_candidates: int | str,
    min_prior_public_summary_passes: int,
    min_distinct_repositories: int,
    min_distinct_language_families: int,
    min_same_verifier_before_after: int,
    min_patch_apply_proven: int,
    min_state_transition_anchors: int,
    max_duplicate_cluster_share: float,
    max_repo_family_share: float,
) -> dict[str, Any]:
    gates = [
        "previous_phase_public_summary_present_and_guardrail_clean",
        "raw_leak_count_zero",
        "overclaim_count_zero",
        "private_material_remains_private",
        "dedupe_against_existing_countable_ledgers_complete",
        "protected_split_overlap_count_zero",
        "same_verifier_before_after_status_count_meets_floor",
        "patch_apply_proof_count_meets_floor",
        "state_transition_anchor_count_meets_floor",
        "repo_and_language_diversity_floors_met",
        "quota_caps_not_exceeded",
        "manual_or_semantic_qc_reject_rate_within_tolerance",
    ]
    return {
        "target_private_candidates_to_process": target_candidates,
        "processing_allowed_by_this_artifact": False,
        "admission_release_allowed_by_this_artifact": False,
        "training_release_allowed_by_this_artifact": False,
        "prior_phase_required": prior_phase,
        "must_have_prior_clean_public_summaries": min_prior_public_summary_passes,
        "minimum_distinct_repositories": min_distinct_repositories,
        "minimum_distinct_language_families": min_distinct_language_families,
        "minimum_same_verifier_before_after_proofs": min_same_verifier_before_after,
        "minimum_patch_apply_proofs": min_patch_apply_proven,
        "minimum_state_transition_anchors": min_state_transition_anchors,
        "maximum_duplicate_cluster_share": max_duplicate_cluster_share,
        "maximum_repo_family_share": max_repo_family_share,
        "required_gates": gates,
        "gate_status": {gate: "BLOCKED_NOT_RUN" for gate in gates},
        "failure_mode": "remain_fail_closed_and_do_not_emit_rows",
    }


def build_ramp_control(stage12428: dict[str, Any]) -> dict[str, Any]:
    source = summarize_stage12428(stage12428)
    source_ok = (
        bool(stage12428)
        and source["source_training_allowed"] is False
        and source["source_admission_allowed"] is False
        and source["source_guardrail_scan_passed"] is True
        and source["source_raw_leak_count"] == 0
        and source["source_overclaim_count"] == 0
        and source["source_raw_rows_inspected"] == 0
        and source["source_raw_rows_copied"] == 0
        and source["source_raw_content_emitted"] is False
        and source["source_emitted_training_rows"] == 0
        and source["source_admitted_rows"] == 0
    )
    candidate_supply = source["source_candidate_supply_rows"]
    pilot_quota = safe_int(source["source_first_private_sample_quota"].get("sample_exactly"))

    ramp_phases = {
        "pilot_100": gate_bundle(
            prior_phase=None,
            target_candidates=100,
            min_prior_public_summary_passes=1,
            min_distinct_repositories=10,
            min_distinct_language_families=3,
            min_same_verifier_before_after=8,
            min_patch_apply_proven=12,
            min_state_transition_anchors=30,
            max_duplicate_cluster_share=0.10,
            max_repo_family_share=0.10,
        ),
        "scale_500": gate_bundle(
            prior_phase="pilot_100",
            target_candidates=500,
            min_prior_public_summary_passes=1,
            min_distinct_repositories=25,
            min_distinct_language_families=4,
            min_same_verifier_before_after=50,
            min_patch_apply_proven=60,
            min_state_transition_anchors=150,
            max_duplicate_cluster_share=0.08,
            max_repo_family_share=0.08,
        ),
        "ramp_1k": gate_bundle(
            prior_phase="scale_500",
            target_candidates=1000,
            min_prior_public_summary_passes=1,
            min_distinct_repositories=50,
            min_distinct_language_families=5,
            min_same_verifier_before_after=120,
            min_patch_apply_proven=150,
            min_state_transition_anchors=300,
            max_duplicate_cluster_share=0.06,
            max_repo_family_share=0.05,
        ),
        "scale_2k": gate_bundle(
            prior_phase="ramp_1k",
            target_candidates=2000,
            min_prior_public_summary_passes=2,
            min_distinct_repositories=80,
            min_distinct_language_families=6,
            min_same_verifier_before_after=240,
            min_patch_apply_proven=300,
            min_state_transition_anchors=700,
            max_duplicate_cluster_share=0.05,
            max_repo_family_share=0.04,
        ),
        "scale_5k": gate_bundle(
            prior_phase="scale_2k",
            target_candidates=5000,
            min_prior_public_summary_passes=2,
            min_distinct_repositories=150,
            min_distinct_language_families=7,
            min_same_verifier_before_after=700,
            min_patch_apply_proven=900,
            min_state_transition_anchors=1800,
            max_duplicate_cluster_share=0.04,
            max_repo_family_share=0.03,
        ),
        "ramp_10k": gate_bundle(
            prior_phase="scale_5k",
            target_candidates=10000,
            min_prior_public_summary_passes=2,
            min_distinct_repositories=250,
            min_distinct_language_families=8,
            min_same_verifier_before_after=1500,
            min_patch_apply_proven=1800,
            min_state_transition_anchors=3500,
            max_duplicate_cluster_share=0.035,
            max_repo_family_share=0.025,
        ),
        "full_processing": gate_bundle(
            prior_phase="ramp_10k",
            target_candidates="all_remaining_private_candidates_after_quota_and_dedupe",
            min_prior_public_summary_passes=3,
            min_distinct_repositories=500,
            min_distinct_language_families=8,
            min_same_verifier_before_after=5000,
            min_patch_apply_proven=6000,
            min_state_transition_anchors=12000,
            max_duplicate_cluster_share=0.02,
            max_repo_family_share=0.01,
        ),
    }

    control = {
        **ZERO_COUNTERS,
        "stage": STAGE,
        "record_type": "open_swe_scaling_ramp_control_v1",
        "decision": "fail_closed_control_only_no_processing_no_rows_admitted",
        "claim_boundary": (
            "Stage12429 defines public-safe scaling controls only. The 100 candidate sample from Stage12428 "
            "is a pilot and calibration gate, not a ceiling on eventual private processing. This artifact "
            "does not read raw Open-SWE rows, does not sample private rows, does not emit training rows, "
            "does not admit rows, and cannot be counted as training data."
        ),
        "input_summary_hashes": {
            "stage12428_summary": file_hash(STAGE12428_SUMMARY),
        },
        "input_summary_presence": {
            "stage12428_summary": STAGE12428_SUMMARY.exists(),
        },
        "source_summary": source,
        "source_preconditions": {
            "stage12428_present": bool(stage12428),
            "stage12428_fail_closed_public_request_only": stage12428.get("decision")
            == "fail_closed_public_request_only_no_sampling_no_rows_admitted",
            "stage12428_training_allowed_false": source["source_training_allowed"] is False,
            "stage12428_admission_allowed_false": source["source_admission_allowed"] is False,
            "stage12428_guardrail_scan_passed": source["source_guardrail_scan_passed"] is True,
            "stage12428_raw_leak_count_zero": source["source_raw_leak_count"] == 0,
            "stage12428_overclaim_count_zero": source["source_overclaim_count"] == 0,
            "stage12428_no_raw_rows_inspected": source["source_raw_rows_inspected"] == 0,
            "stage12428_no_rows_admitted": source["source_admitted_rows"] == 0,
            "source_eligible_for_control_only": source_ok,
        },
        "candidate_supply_rows_from_stage12428_metadata": candidate_supply,
        "candidate_supply_rows": candidate_supply,
        "trajectory_shard_count": safe_int(
            source["source_bucket_status_counts"].get("trajectory_shard_count_from_stage12427")
        ),
        "candidate_supply_rows_are_not_training_rows": True,
        "pilot_not_ceiling_policy": {
            "stage12428_sample_exactly": pilot_quota,
            "pilot_candidate_count": 100,
            "pilot_is_ceiling": False,
            "pilot_purpose": "calibrate private review, leak checks, dedupe collapse, verifier proof rates, and quota balance",
            "larger_ramps_require_separate_private_runs": True,
            "larger_ramps_require_public_safe_postrun_summaries": True,
            "no_training_or_admission_from_pilot_without_separate_gate": True,
        },
        "ramp_sequence": [
            "pilot_100",
            "scale_500",
            "ramp_1k",
            "scale_2k",
            "scale_5k",
            "ramp_10k",
            "full_processing",
        ],
        "pilot_100": ramp_phases["pilot_100"],
        "scale_500": ramp_phases["scale_500"],
        "scale_1k": ramp_phases["ramp_1k"],
        "scale_2k": ramp_phases["scale_2k"],
        "scale_5k": ramp_phases["scale_5k"],
        "scale_10k": ramp_phases["ramp_10k"],
        "full_corpus": ramp_phases["full_processing"],
        "scaling_ramp": ramp_phases,
        "proof_floors": {
            phase: {
                "target_private_candidates_to_process": spec["target_private_candidates_to_process"],
                "minimum_distinct_repositories": spec["minimum_distinct_repositories"],
                "minimum_distinct_language_families": spec["minimum_distinct_language_families"],
                "minimum_same_verifier_before_after_proofs": spec[
                    "minimum_same_verifier_before_after_proofs"
                ],
                "minimum_patch_apply_proofs": spec["minimum_patch_apply_proofs"],
                "minimum_state_transition_anchors": spec["minimum_state_transition_anchors"],
            }
            for phase, spec in ramp_phases.items()
        },
        "stop_conditions": [
            "any_public_raw_leak_count_nonzero",
            "any_public_overclaim_count_nonzero",
            "protected_split_overlap_count_nonzero",
            "resolved_label_used_as_repair_or_patch_success_proof",
            "candidate_sample_fails_dedupe_or_cluster_caps",
            "admission_artifact_claims_training_rows_before_proof_slots_pass",
            "pilot_or_ramp_proof_rates_below_required_floors",
        ],
        "ramp_phases": ramp_phases,
        "cross_phase_release_gates": {
            "all_public_summaries_have_raw_leak_count_zero": "REQUIRED",
            "all_public_summaries_have_overclaim_count_zero": "REQUIRED",
            "all_public_summaries_keep_training_allowed_false_until_final_admission": "REQUIRED",
            "admission_requires_separate_named_admission_artifact": "REQUIRED",
            "training_requires_separate_named_training_artifact_after_admission": "REQUIRED",
            "raw_private_fields_never_return_to_public_artifacts": "REQUIRED",
            "dedupe_against_stage12385_stage12416_stage12418_stage12421": "REQUIRED",
            "resolved_label_not_used_as_repair_proof": "REQUIRED",
            "same_verifier_before_after_proof_required_for_repair_claims": "REQUIRED",
        },
        "blocked_reason_counts": {
            "control_artifact_only": 1,
            "no_private_sampler_run": 1,
            "no_raw_rows_read": 1,
            "no_rows_admitted": 1,
            "pilot_100_not_yet_publicly_postrun_validated": 1,
            "ramp_1k_requires_clean_pilot_100_summary": 1,
            "ramp_10k_requires_clean_1k_summary": 1,
            "full_processing_requires_clean_10k_summary": 1,
            "separate_admission_and_training_gates_required": 1,
        },
        "promotion_gate_status": {
            "artifact_is_public_control_only": "PASS",
            "training_allowed": "PASS_FALSE",
            "admission_allowed": "PASS_FALSE",
            "no_rows_admitted": "PASS",
            "no_rows_emitted": "PASS",
            "no_raw_rows_inspected": "PASS",
            "stage12428_public_summary_reused_only": "PASS" if source_ok else "BLOCKED",
            "pilot_100_is_not_ceiling": "PASS",
            "ramp_processing_not_run": "PASS",
        },
        "raw_content_policy": RAW_CONTENT_POLICY,
        "local_artifacts": {
            "ramp_control_name_hash": stable_hash("open_swe_scaling_ramp_control.json"),
            "ramp_gate_matrix_name_hash": stable_hash("ramp_gate_matrix.json"),
            "guardrail_scan_name_hash": stable_hash("guardrail_scan.json"),
        },
        "next_stage_recommendation": "private_pilot_100_postrun_summary_or_private_ramp_sampler_kept_raw_private",
    }
    return control


def guardrail_scan(value: dict[str, Any]) -> dict[str, Any]:
    payload = json.dumps(value, sort_keys=True)
    raw_matches = FORBIDDEN_TEXT_RE.findall(payload)
    overclaim_matches = []
    for match in OVERCLAIM_RE.finditer(payload):
        start = max(0, match.start() - 100)
        end = min(len(payload), match.end() + 100)
        context = payload[start:end]
        if not ALLOWED_OVERCLAIM_CONTEXT_RE.search(context):
            overclaim_matches.append(match.group(0))
    zero_counter_failures = [
        key for key, expected in ZERO_COUNTERS.items() if value.get(key) != expected
    ]
    raw_policy_failures = [
        key
        for key, expected in RAW_CONTENT_POLICY.items()
        if value.get("raw_content_policy", {}).get(key) != expected
    ]
    return {
        "scan_passed": not raw_matches and not overclaim_matches and not zero_counter_failures and not raw_policy_failures,
        "raw_leak_count": len(raw_matches),
        "overclaim_count": len(overclaim_matches),
        "issue_count": len(raw_matches) + len(overclaim_matches) + len(zero_counter_failures) + len(raw_policy_failures),
        "issues": (
            (["forbidden_raw_text_pattern_detected"] if raw_matches else [])
            + (["unsupported_overclaim_pattern_detected"] if overclaim_matches else [])
            + [f"nonzero_or_true_zero_counter:{key}" for key in zero_counter_failures]
            + [f"raw_content_policy_failure:{key}" for key in raw_policy_failures]
        ),
        "zero_counter_keys_checked": sorted(ZERO_COUNTERS),
        "raw_content_policy_keys_checked": sorted(RAW_CONTENT_POLICY),
    }


def main() -> None:
    stage12428 = read_json(STAGE12428_SUMMARY)
    control = build_ramp_control(stage12428)
    scan = guardrail_scan(control)
    control["guardrail_scan"] = scan
    control["guardrail_scan_passed"] = scan["scan_passed"]
    control["raw_leak_count"] = scan["raw_leak_count"]
    control["overclaim_count"] = scan["overclaim_count"]
    control["summary_hash"] = stable_hash({k: v for k, v in control.items() if k != "summary_hash"})

    write_json(OUT / "open_swe_scaling_ramp_control.json", control)
    write_json(OUT / "ramp_gate_matrix.json", control["ramp_phases"])
    write_json(OUT / "guardrail_scan.json", scan)
    write_json(OUT / "summary.json", control)
    write_json(SUMMARY, control)
    if not scan["scan_passed"]:
        raise SystemExit(f"guardrail scan failed with {scan['issue_count']} issues")

    print(
        json.dumps(
            {
                "stage": STAGE,
                "decision": control["decision"],
                "training_allowed": False,
                "admitted_rows": 0,
                "emitted_training_rows": 0,
                "candidate_supply_rows_from_stage12428_metadata": control[
                    "candidate_supply_rows_from_stage12428_metadata"
                ],
                "pilot_is_ceiling": False,
                "ramp_sequence": control["ramp_sequence"],
                "guardrail_scan_passed": True,
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
