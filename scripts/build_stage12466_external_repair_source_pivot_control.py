#!/usr/bin/env python3
"""Build Stage12466 external repair source pivot control.

This stage is fail-closed and public-safe. It does not execute, hydrate, train,
package, admit, or access the network. It only ranks non-Bears source lanes for
a later request/preflight stage that could pursue external comparable
FAIL_TO_PASS proof.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12466_external_repair_source_pivot_control"
OUT_DIR = ROOT / "runs/local/artifacts" / STAGE
SUMMARY_OUT = ROOT / "runs/summaries" / f"{STAGE}.json"

INPUT_SUMMARIES = {
    "stage12465": ROOT
    / "runs/summaries/stage12465_bears_source_acquisition_hydration_executor_preflight.json",
    "stage12459": ROOT
    / "runs/summaries/stage12459_external_comparable_patch_effect_source_preflight.json",
    "stage12392": ROOT
    / "runs/summaries/stage12392_raw_visible_review_packet_builder_or_external_root_pivot.json",
    "stage12284": ROOT / "runs/summaries/stage12284_external_repair_commit_pair_preflight.json",
    "stage12285": ROOT / "runs/summaries/stage12285_external_repair_replay_executor_request.json",
    "stage12286": ROOT / "runs/summaries/stage12286_external_repair_replay_smoke_executor.json",
    "stage12287": ROOT / "runs/summaries/stage12287_external_repair_replay_second_smoke_request.json",
    "stage12288": ROOT / "runs/summaries/stage12288_external_repair_replay_second_smoke_executor.json",
    "stage12289": ROOT / "runs/summaries/stage12289_replay_failure_after_phase_diagnostic.json",
    "stage12290": ROOT / "runs/summaries/stage12290_replay_queue_repair_or_retarget_decision.json",
    "stage12291": ROOT / "runs/summaries/stage12291_commit_pair_after_pass_prefilter.json",
    "stage12292": ROOT
    / "runs/summaries/stage12292_after_pass_eligible_before_fail_patch_effect_replay.json",
    "stage12327": ROOT / "runs/summaries/stage12327_external_adapter_preflight.json",
    "stage12425": ROOT / "runs/summaries/stage12425_source_adapter_feasibility_miner.json",
}

DECISION = "pivot_control_ready_no_execution_no_training"
BEARS_BLOCKED_STATUS = "blocked_java_only_requires_approval_or_source_hydration"
RECOMMENDED_NEXT_STAGE = (
    "stage12467_non_bears_trace_transition_repair_proof_request_preflight"
)

ZERO_GUARDS = {
    "external_comparable_repair_credit_count": 0,
    "remaining_external_fail_to_pass_gap": 15,
    "training_allowed": False,
    "admission_allowed": False,
    "packaging_allowed": False,
    "execution_performed_by_stage": False,
    "emitted_training_rows": 0,
    "sealed_eval_rows": 0,
}

REQUIRED_SUMMARY_FIELDS = {
    "decision",
    "bears_lane_status",
    "external_comparable_repair_credit_count",
    "remaining_external_fail_to_pass_gap",
    "training_allowed",
    "admission_allowed",
    "packaging_allowed",
    "execution_performed_by_stage",
    "emitted_training_rows",
    "sealed_eval_rows",
    "ranked_non_bears_source_lanes",
    "hard_rejected_lanes",
    "recommended_next_stage",
    "guardrail_scan_passed",
    "raw_leak_count",
    "schema_issue_count",
}

FORBIDDEN_PUBLIC_KEYS = {
    "path",
    "paths",
    "url",
    "urls",
    "uri",
    "command",
    "commands",
    "stdout",
    "stderr",
    "diff",
    "patch",
    "patch_body",
    "raw_text",
    "source_text",
    "repo",
    "repo_id",
    "repo_name",
    "repository",
    "sha",
    "commit",
}
KEY_ALLOW_RE = re.compile(
    r"(hash|hashes|ref|refs|stage|schema|slot|slots|policy|guardrail|"
    r"requirement|status|bucket|count)",
    re.IGNORECASE,
)
RAW_LEAK_RE = re.compile(
    r"https?://|www\.|diff --git|@@ |^\+\+\+ |^--- |<<<<<<<|>>>>>>>|"
    r"(?<![A-Za-z0-9_])/(?:[A-Za-z0-9._-]+/){2,}[A-Za-z0-9._-]+|"
    r"\b(?:git clone|git apply|pytest\s|python -c|bash -|sh -|curl\s|"
    r"stdout|stderr|traceback|terminal output|command output)\b|"
    r"\b[0-9a-f]{40}\b|"
    r"\b(?:Open-SWE|RepairThemAll|SakanaAI|SWE-Hero|SWE-Zero)\b",
    re.IGNORECASE | re.MULTILINE,
)


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path.name} must contain a JSON object")
    return value


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


def count_bucket(count: int) -> str:
    if count <= 0:
        return "0"
    if count == 1:
        return "1"
    if count <= 4:
        return "2-4"
    if count <= 9:
        return "5-9"
    if count <= 24:
        return "10-24"
    if count <= 74:
        return "25-74"
    if count <= 249:
        return "75-249"
    return "250-plus"


def language_coverage_bucket(language_counts: Any) -> str:
    if not isinstance(language_counts, dict) or not language_counts:
        return "unknown_or_not_public"
    languages = {str(key).lower() for key in language_counts if language_counts[key]}
    if not languages:
        return "unknown_or_not_public"
    if languages == {"java"}:
        return "single_jvm"
    if languages == {"python"}:
        return "single_python"
    if languages <= {"javascript", "typescript", "html", "css"}:
        return "web_script"
    if languages & {"c", "cpp", "c++", "cuda", "rust"} and len(languages) <= 3:
        return "systems_mixed"
    if len(languages) >= 4:
        return "multilingual_mixed"
    return "small_language_mix"


def int_value(value: Any, default: int = 0) -> int:
    if isinstance(value, bool):
        return default
    if isinstance(value, int):
        return value
    return default


def scan_public(label: str, value: Any) -> list[str]:
    issues: list[str] = []
    leaf = label.rsplit(".", 1)[-1].split("[", 1)[0].lower()
    if leaf in FORBIDDEN_PUBLIC_KEYS and not KEY_ALLOW_RE.search(label):
        issues.append(f"{label}:forbidden_public_key")
    if isinstance(value, str):
        if RAW_LEAK_RE.search(value):
            issues.append(f"{label}:raw_locator_or_source_identifier:{stable_hash(value)}")
    elif isinstance(value, dict):
        for key, child in value.items():
            issues.extend(scan_public(f"{label}.{key}", child))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            issues.extend(scan_public(f"{label}[{index}]", child))
    return issues


def build_ranked_lanes(inputs: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    stage12327 = inputs["stage12327"]
    stage12392 = inputs["stage12392"]
    stage12425 = inputs["stage12425"]

    trace_counts = (
        stage12327.get("open_swe_import_artifact", {}).get("language_counts")
        if isinstance(stage12327.get("open_swe_import_artifact"), dict)
        else {}
    )
    trace_total = sum(int_value(value) for value in trace_counts.values())
    metadata_counts = {}
    for adapter in stage12425.get("ranked_adapter_feasibility", []) or []:
        if adapter.get("adapter_family") == "open_swe_traces":
            metadata_counts = adapter.get("metadata_language_counts") or {}
            break

    pivot_worklist = stage12392.get("external_root_pivot_worklist") or []
    non_bears_private_review_counts = [
        int_value(row.get("candidate_count"))
        for row in pivot_worklist
        if isinstance(row, dict)
        and row.get("source_family") != "Bears/RepairThemAll"
        and row.get("source_family") != "Open-SWE-Traces"
    ]

    lanes = [
        {
            "rank": 1,
            "lane_ref": "lane_ref_non_bears_trace_transition_repair_proof_preflight",
            "candidate_count_bucket": count_bucket(max(trace_total, sum(int_value(v) for v in metadata_counts.values()))),
            "language_coverage_bucket": language_coverage_bucket(metadata_counts or trace_counts),
            "external_fail_to_pass_fit": "highest_non_bears_potential_after_private_replay_and_causality_preflight",
            "required_next_stage_type": "request_preflight_only",
            "required_private_proof_slots": [
                "safe_transition_record_refs",
                "checkout_before_ref_hash",
                "patch_apply_ref_hash",
                "same_verifier_before_after_ref_hash",
                "before_status_fail",
                "after_or_before_plus_patch_status_pass",
                "causal_linkage_ref",
                "anti_leak_public_rendering_pass",
            ],
            "blocking_conditions_before_credit": [
                "resolved_or_observed_trace_status_is_not_fail_to_pass_proof",
                "same_verifier_identity_and_patch_causality_not_yet_proven",
                "private_raw_visible_review_required_before_public_artifacts",
            ],
            "source_stage_refs": [
                "stage12327_external_adapter_preflight",
                "stage12392_raw_visible_review_packet_builder_or_external_root_pivot",
                "stage12425_source_adapter_feasibility_miner",
            ],
        },
        {
            "rank": 2,
            "lane_ref": "lane_ref_non_bears_external_benchmark_patch_log_preflight",
            "candidate_count_bucket": "unknown_control_only",
            "language_coverage_bucket": "unknown_or_not_public",
            "external_fail_to_pass_fit": "plausible_if_patch_logs_include_pre_post_same_verifier_status",
            "required_next_stage_type": "request_preflight_only",
            "required_private_proof_slots": [
                "patch_diff_ref_hash",
                "pre_status_fail_ref",
                "post_status_pass_ref",
                "same_verifier_identity_ref",
                "same_source_lineage_ref",
                "anti_leak_public_rendering_pass",
            ],
            "blocking_conditions_before_credit": [
                "control_artifact_only_no_candidate_scan_run",
                "no_before_after_verifier_status_proven",
                "no_same_source_lineage_proven",
            ],
            "source_stage_refs": ["stage12425_source_adapter_feasibility_miner"],
        },
        {
            "rank": 3,
            "lane_ref": "lane_ref_non_bears_private_review_pivot_preflight",
            "candidate_count_bucket": count_bucket(sum(non_bears_private_review_counts)),
            "language_coverage_bucket": "unknown_or_not_public",
            "external_fail_to_pass_fit": "small_review_pivot_if_private_packets_can_prove_repair_causality",
            "required_next_stage_type": "request_preflight_only",
            "required_private_proof_slots": [
                "non_self_identity_ref",
                "safe_semantic_extraction_ref",
                "selected_verifier_relevance_ref",
                "state_delta_semantics_ref",
                "unique_patch_verifier_binding_ref",
                "anti_leak_public_rendering_pass",
            ],
            "blocking_conditions_before_credit": [
                "private_review_packet_only_no_training_admission",
                "candidate_count_small",
                "language_coverage_not_public",
            ],
            "source_stage_refs": [
                "stage12392_raw_visible_review_packet_builder_or_external_root_pivot"
            ],
        },
        {
            "rank": 4,
            "lane_ref": "lane_ref_non_bears_trajectory_dataset_adapter_preflight",
            "candidate_count_bucket": "250-plus",
            "language_coverage_bucket": "unknown_or_not_public",
            "external_fail_to_pass_fit": "candidate_only_until_verifier_or_replay_layer_exists",
            "required_next_stage_type": "request_preflight_only",
            "required_private_proof_slots": [
                "language_inference_ref",
                "verifier_result_ref",
                "same_verifier_before_after_ref",
                "causal_linkage_ref",
                "anti_leak_public_rendering_pass",
            ],
            "blocking_conditions_before_credit": [
                "verifier_result_absent",
                "same_verifier_before_after_absent",
                "causal_linkage_absent",
            ],
            "source_stage_refs": ["stage12425_source_adapter_feasibility_miner"],
        },
    ]
    return lanes


def build_rejected_lanes() -> list[dict[str, Any]]:
    return [
        {
            "lane_ref": "lane_ref_bears_failing_passing_private_hydration",
            "candidate_count_bucket": "10-24",
            "language_coverage_bucket": "single_jvm",
            "hard_reject_reason": BEARS_BLOCKED_STATUS,
            "may_reconsider_after": "explicit_approval_or_local_source_hydration_preflight_passes",
            "source_stage_refs": [
                "stage12327_external_adapter_preflight",
                "stage12459_external_comparable_patch_effect_source_preflight",
                "stage12465_bears_source_acquisition_hydration_executor_preflight",
            ],
        },
        {
            "lane_ref": "lane_ref_controlled_or_mutation_support",
            "candidate_count_bucket": "5-9",
            "language_coverage_bucket": "unknown_or_not_public",
            "hard_reject_reason": "controlled_or_mutation_support_is_not_external_comparable_fail_to_pass_repair_proof",
            "source_stage_refs": ["stage12459_external_comparable_patch_effect_source_preflight"],
        },
        {
            "lane_ref": "lane_ref_selected_test_verifier_observation",
            "candidate_count_bucket": "25-74",
            "language_coverage_bucket": "unknown_or_not_public",
            "hard_reject_reason": "selected_test_observation_support_cannot_close_external_repair_credit_floor",
            "source_stage_refs": ["stage12459_external_comparable_patch_effect_source_preflight"],
        },
        {
            "lane_ref": "lane_ref_pass_to_pass",
            "candidate_count_bucket": "1",
            "language_coverage_bucket": "unknown_or_not_public",
            "hard_reject_reason": "pass_to_pass_is_not_fail_to_pass_patch_effect",
            "source_stage_refs": ["stage12459_external_comparable_patch_effect_source_preflight"],
        },
        {
            "lane_ref": "lane_ref_commit_pair_replay_cache",
            "candidate_count_bucket": "10-24",
            "language_coverage_bucket": "systems_mixed",
            "hard_reject_reason": "prior_replay_smokes_and_retarget_checks_produced_zero_patch_effect_credit",
            "source_stage_refs": [
                "stage12284_external_repair_commit_pair_preflight",
                "stage12285_external_repair_replay_executor_request",
                "stage12286_external_repair_replay_smoke_executor",
                "stage12287_external_repair_replay_second_smoke_request",
                "stage12288_external_repair_replay_second_smoke_executor",
                "stage12289_replay_failure_after_phase_diagnostic",
                "stage12290_replay_queue_repair_or_retarget_decision",
                "stage12291_commit_pair_after_pass_prefilter",
                "stage12292_after_pass_eligible_before_fail_patch_effect_replay",
            ],
        },
        {
            "lane_ref": "lane_ref_co_presence_only_or_identity_only",
            "candidate_count_bucket": "250-plus",
            "language_coverage_bucket": "unknown_or_not_public",
            "hard_reject_reason": "patch_and_verifier_co_presence_or_identity_without_before_fail_after_pass_causality_is_insufficient",
            "source_stage_refs": [
                "stage12327_external_adapter_preflight",
                "stage12459_external_comparable_patch_effect_source_preflight",
            ],
        },
    ]


def schema_issues(summary: dict[str, Any]) -> list[str]:
    issues: list[str] = []
    missing = sorted(REQUIRED_SUMMARY_FIELDS - set(summary))
    issues.extend(f"missing:{field}" for field in missing)
    for key, expected in ZERO_GUARDS.items():
        if summary.get(key) != expected:
            issues.append(f"guard_mismatch:{key}")
    if summary.get("decision") != DECISION:
        issues.append("decision_mismatch")
    if summary.get("bears_lane_status") != BEARS_BLOCKED_STATUS:
        issues.append("bears_lane_status_mismatch")
    if not isinstance(summary.get("ranked_non_bears_source_lanes"), list):
        issues.append("ranked_non_bears_source_lanes_not_list")
    if not isinstance(summary.get("hard_rejected_lanes"), list):
        issues.append("hard_rejected_lanes_not_list")
    return issues


def main() -> None:
    inputs = {label: read_json(path) for label, path in INPUT_SUMMARIES.items()}
    input_inventory = {
        label: {
            "present": bool(data),
            "summary_ref": label,
            "sha256_24": file_hash(path),
        }
        for label, (path, data) in zip(
            INPUT_SUMMARIES.keys(),
            ((path, inputs[label]) for label, path in INPUT_SUMMARIES.items()),
        )
    }

    ranked_lanes = build_ranked_lanes(inputs)
    hard_rejected = build_rejected_lanes()

    control_artifact = {
        "stage": STAGE,
        "record_type": "external_repair_source_pivot_control_public_safe_v1",
        "decision": DECISION,
        "bears_lane_status": BEARS_BLOCKED_STATUS,
        **ZERO_GUARDS,
        "ranked_non_bears_source_lanes": ranked_lanes,
        "hard_rejected_lanes": hard_rejected,
        "recommended_next_stage": RECOMMENDED_NEXT_STAGE,
        "recommended_next_stage_contract": {
            "stage_type": "request_preflight",
            "target_lane_ref": ranked_lanes[0]["lane_ref"],
            "must_not_execute": True,
            "must_not_hydrate": True,
            "must_not_train": True,
            "must_not_package": True,
            "must_not_admit": True,
            "public_rendering_policy": "bucketed_counts_stage_refs_hash_refs_only_no_raw_paths_urls_commands_shas_repo_names",
            "minimum_success_condition_for_later_non_preflight_stage": "private proof plan is not repair proof; later credit requires at least 15 validator-complete external comparable FAIL_TO_PASS returns with same-source before-fail after-pass causality",
        },
        "input_inventory": input_inventory,
    }

    public_scan_payload = {
        "control_artifact": control_artifact,
        "ranked_non_bears_source_lanes": ranked_lanes,
        "hard_rejected_lanes": hard_rejected,
    }
    raw_issues = scan_public("stage12466_public_artifacts", public_scan_payload)
    schema_issue_list = schema_issues(control_artifact)
    guardrail_scan = {
        "stage": STAGE,
        "scan_scope": "stage12466_public_control_artifacts",
        "policy": "public_safe_refs_only_no_raw_paths_urls_commands_shas_repo_names_diffs_outputs_or_source",
        "issues": raw_issues,
        "raw_leak_count": len(raw_issues),
        "schema_issues": schema_issue_list,
        "schema_issue_count": len(schema_issue_list),
        "scan_passed": len(raw_issues) == 0 and len(schema_issue_list) == 0,
    }

    control_artifact["guardrail_scan"] = guardrail_scan
    control_artifact["guardrail_scan_passed"] = guardrail_scan["scan_passed"]
    control_artifact["raw_leak_count"] = guardrail_scan["raw_leak_count"]
    control_artifact["schema_issue_count"] = guardrail_scan["schema_issue_count"]
    control_artifact["artifact_hashes"] = {
        "ranked_non_bears_source_lanes": stable_hash(ranked_lanes),
        "hard_rejected_lanes": stable_hash(hard_rejected),
        "guardrail_scan": stable_hash(guardrail_scan),
    }

    # Re-scan the final public object after adding guardrail/hash fields.
    final_raw_issues = scan_public("stage12466_summary", control_artifact)
    final_schema_issues = schema_issues(control_artifact)
    guardrail_scan.update(
        {
            "issues": final_raw_issues,
            "raw_leak_count": len(final_raw_issues),
            "schema_issues": final_schema_issues,
            "schema_issue_count": len(final_schema_issues),
            "scan_passed": len(final_raw_issues) == 0 and len(final_schema_issues) == 0,
        }
    )
    control_artifact["guardrail_scan"] = guardrail_scan
    control_artifact["guardrail_scan_passed"] = guardrail_scan["scan_passed"]
    control_artifact["raw_leak_count"] = guardrail_scan["raw_leak_count"]
    control_artifact["schema_issue_count"] = guardrail_scan["schema_issue_count"]
    control_artifact["artifact_hashes"]["guardrail_scan"] = stable_hash(guardrail_scan)
    control_artifact["summary_hash"] = stable_hash(control_artifact)

    write_json(OUT_DIR / "pivot_control.json", control_artifact)
    write_jsonl(OUT_DIR / "ranked_non_bears_source_lanes.jsonl", ranked_lanes)
    write_jsonl(OUT_DIR / "hard_rejected_lanes.jsonl", hard_rejected)
    write_json(OUT_DIR / "guardrail_scan.json", guardrail_scan)
    write_json(SUMMARY_OUT, control_artifact)

    print(
        json.dumps(
            {
                "stage": STAGE,
                "decision": control_artifact["decision"],
                "bears_lane_status": control_artifact["bears_lane_status"],
                "external_comparable_repair_credit_count": control_artifact[
                    "external_comparable_repair_credit_count"
                ],
                "remaining_external_fail_to_pass_gap": control_artifact[
                    "remaining_external_fail_to_pass_gap"
                ],
                "ranked_non_bears_source_lane_count": len(ranked_lanes),
                "hard_rejected_lane_count": len(hard_rejected),
                "guardrail_scan_passed": control_artifact["guardrail_scan_passed"],
                "raw_leak_count": control_artifact["raw_leak_count"],
                "schema_issue_count": control_artifact["schema_issue_count"],
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
