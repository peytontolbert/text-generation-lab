#!/usr/bin/env python3
"""Anti-collapse dataset generation contract for maintainer training.

This stage turns the recent failure lessons into a concrete generator contract.
It does not generate model-facing training rows, execute private proof work,
admit rows, or claim credit. It separates three lanes that were previously
conflated:

1. concept expansion: local models/embeddings propose semantic variants;
2. train-support admission: deterministic review admits non-proof supervision;
3. proof-grade repair: Stage12468-compatible evidence earns external credit.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12489_anti_collapse_dataset_generation_contract"
OUT = ROOT / "runs/local/artifacts" / STAGE
SUMMARY = ROOT / "runs/summaries" / f"{STAGE}.json"

INPUTS = {
    "stage12295": ROOT / "runs/summaries/stage12295_transition_function_ledger.json",
    "stage12320": ROOT / "runs/summaries/stage12320_event_local_semantic_review_admission.json",
    "stage12441": ROOT / "runs/summaries/stage12441_embedding_transition_candidate_expansion_gate.json",
    "stage12488": ROOT / "runs/summaries/stage12488_source_to_private_proof_bundle_funnel.json",
}

RAW_LEAK_RE = re.compile(
    r"https?://|www\.|diff --git|@@ |^\+\+\+ |^--- |<<<<<<<|>>>>>>>|"
    r"(?<![A-Za-z0-9_])/(?:[A-Za-z0-9._-]+/){2,}[A-Za-z0-9._-]+|"
    r"\b(?:git clone|git apply|pytest\s|python -c|bash -|sh -|curl\s|"
    r"stdout|stderr|traceback|terminal output|command output)\b|"
    r"\b[0-9a-f]{40}\b",
    re.IGNORECASE | re.MULTILINE,
)


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


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    value = json.loads(path.read_text(encoding="utf-8"))
    return value if isinstance(value, dict) else {}


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")


def scan(value: Any) -> list[str]:
    issues: list[str] = []
    if isinstance(value, str):
        if RAW_LEAK_RE.search(value):
            issues.append(stable_hash(value))
    elif isinstance(value, dict):
        for child in value.values():
            issues.extend(scan(child))
    elif isinstance(value, list):
        for child in value:
            issues.extend(scan(child))
    return issues


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    loaded = {name: read_json(path) for name, path in INPUTS.items()}

    observed_counters = {
        "transition_ledger_records": loaded["stage12295"].get("transition_ledger_records", 120314),
        "stage12295_train_support_rows": loaded["stage12295"].get("train_support_rows", 3853),
        "stage12295_external_proof_rows": loaded["stage12295"].get("proof_counts", {}).get("external_fail_to_pass_countable", 0),
        "stage12320_admitted_train_support_rows": loaded["stage12320"].get("admitted_train_support_rows", 76),
        "stage12441_candidate_vector_count": loaded["stage12441"].get("candidate_vector_count", 185),
        "stage12441_collapsed_duplicate_candidate_count": loaded["stage12441"].get("collapsed_duplicate_candidate_count", 175),
        "stage12441_representative_priority_queue_count": loaded["stage12441"].get("representative_priority_queue_count", 10),
        "stage12488_estimated_candidate_records_total": loaded["stage12488"].get("estimated_candidate_records_total", 348111),
        "stage12488_stage12468_capable_queue_item_count": loaded["stage12488"].get("stage12468_capable_queue_item_count", 3),
        "stage12488_remaining_external_fail_to_pass_gap": loaded["stage12488"].get("remaining_external_fail_to_pass_gap", 15),
    }

    lanes = [
        {
            "lane_id": "concept_expansion_public_safe",
            "purpose": "expand canonical transition-function coverage using local embeddings/models over safe surrogate fields",
            "may_use_local_models": True,
            "may_emit_training_rows": False,
            "may_claim_external_repair_credit": False,
            "truth_source": "none_model_outputs_are_review_hints_only",
            "required_outputs": [
                "transition_function_key",
                "semantic_rule_candidate",
                "state_code_candidate",
                "hard_negative_family",
                "novelty_cluster_id",
                "review_priority",
            ],
        },
        {
            "lane_id": "train_support_reviewed_concepts",
            "purpose": "admit non-proof supervision only after deterministic semantic review",
            "may_use_local_models": True,
            "may_emit_training_rows": True,
            "may_claim_external_repair_credit": False,
            "truth_source": "deterministic_review_and_source_lineage",
            "required_outputs": [
                "independent_policy_label",
                "state_before_codes",
                "observation_status_class",
                "state_delta_codes",
                "stop_continue_label",
                "anti_shortcut_audit",
            ],
        },
        {
            "lane_id": "proof_grade_external_repair",
            "purpose": "produce Stage12468-compatible fail-to-pass repair proof bundles",
            "may_use_local_models": False,
            "may_emit_training_rows": False,
            "may_claim_external_repair_credit": True,
            "truth_source": "same_source_before_fail_after_patch_pass_verifier_evidence",
            "required_outputs": [
                "all_28_stage12468_slots_present",
                "same_verifier_identity",
                "ordered_patch_before_pass_causality",
                "non_placeholder_evidence_hashes",
                "anti_leak_pass",
                "protected_overlap_pass",
            ],
        },
    ]

    anti_collapse_gates = [
        {
            "gate_id": "no_observed_action_imitation",
            "reject_if": "target_is_only_next_observed_tool_family",
            "required_fix": "target_must_be_independent_policy_label_or_marked_behavior_clone_support_only",
        },
        {
            "gate_id": "candidate_role_entropy",
            "reject_if": "one_candidate_role_or_answer_label_dominates_package",
            "required_fix": "balance correct roles and hard negatives within each task family",
        },
        {
            "gate_id": "template_similarity_cap",
            "reject_if": "near_duplicate_cluster_share_exceeds_0_20_for_train_support_or_0_10_for_eval",
            "required_fix": "sample representative roots across clusters and generate counterfactual variants only after dedupe",
        },
        {
            "gate_id": "source_family_cap",
            "reject_if": "single_source_family_exceeds_0_15_of_package_or_0_05_of_eval",
            "required_fix": "route excess rows to curriculum-only queue",
        },
        {
            "gate_id": "proof_training_separation",
            "reject_if": "concept_rows_claim_external_repair_credit_or_proof_rows_train_before_stage12468",
            "required_fix": "Stage12468 validator_complete is the only external repair credit source",
        },
        {
            "gate_id": "renderer_consistency",
            "reject_if": "train_and_eval_use_different_candidate_object_schema",
            "required_fix": "render TASK OBSERVED_STATE EVIDENCE CANDIDATES QUESTION with semantic candidate objects",
        },
        {
            "gate_id": "local_model_non_authority",
            "reject_if": "local_model_label_used_as_gold_without_deterministic_review",
            "required_fix": "store local model output as proposal_hint only",
        },
    ]

    package_targets = {
        "concept_support_pilot": {
            "target_roots": 200,
            "target_rows": 1200,
            "transition_function_families_min": 12,
            "languages_min": 4,
            "max_duplicate_cluster_share": 0.20,
            "local_model_role": "proposal_and_diversity_only",
            "training_allowed_after_review": True,
        },
        "proof_grade_repair_floor": {
            "target_stage12468_validator_complete_returns": 15,
            "current_validator_complete_returns": 0,
            "current_gap": observed_counters["stage12488_remaining_external_fail_to_pass_gap"],
            "training_allowed_before_stage12468": False,
        },
        "sealed_eval_pilot": {
            "target_roots": 100,
            "target_rows": 400,
            "must_be_root_disjoint": True,
            "must_have_option_permutation_audit": True,
            "local_model_selection_allowed": False,
        },
    }

    next_stage_plan = [
        {
            "stage": "stage12490_local_model_concept_proposal_queue",
            "objective": "use local models/embeddings to propose concept-balanced transition-function candidates from Stage12295 and Stage12441 safe metadata",
            "success_condition": "nonzero diversified concept proposals with no admission or proof claims",
        },
        {
            "stage": "stage12491_concept_proposal_semantic_review_gate",
            "objective": "convert proposals into reviewed train-support candidates only when independent policy labels and state deltas are available",
            "success_condition": "at_least_200_reviewed_concept_support_rows_zero_external_repair_credit_claim",
        },
        {
            "stage": "stage12492_concept_support_training_package_preflight",
            "objective": "package reviewed concept rows with anti-collapse balance gates and protected replay",
            "success_condition": "package_passes_role_entropy_cluster_source_renderer_and_leak_audits",
        },
    ]

    contract = {
        "stage": STAGE,
        "record_type": "anti_collapse_dataset_generation_contract_v1",
        "source_stage_refs": sorted(INPUTS),
        "observed_counters": observed_counters,
        "lanes": lanes,
        "anti_collapse_gates": anti_collapse_gates,
        "package_targets": package_targets,
        "next_stage_plan": next_stage_plan,
        "non_actions": [
            "does_not_train",
            "does_not_admit_rows",
            "does_not_execute_private_proof",
            "does_not_hydrate_sources",
            "does_not_claim_external_repair_credit",
        ],
        "training_allowed": False,
        "admission_allowed": False,
        "external_repair_credit_count": 0,
    }
    issue_hashes = scan(contract)
    guardrail = {
        "stage": STAGE,
        "scan_passed": not issue_hashes,
        "raw_leak_count": len(issue_hashes),
        "issue_hashes": issue_hashes[:80],
    }
    summary = {
        "stage": STAGE,
        "decision": "anti_collapse_generation_contract_ready_no_training_no_credit" if guardrail["scan_passed"] else "blocked_raw_leak_guardrail",
        "observed_counters": observed_counters,
        "lane_count": len(lanes),
        "anti_collapse_gate_count": len(anti_collapse_gates),
        "concept_support_pilot_target_rows": package_targets["concept_support_pilot"]["target_rows"],
        "proof_grade_repair_current_gap": package_targets["proof_grade_repair_floor"]["current_gap"],
        "next_stage": "stage12490_local_model_concept_proposal_queue",
        "raw_leak_count": guardrail["raw_leak_count"],
        "training_allowed": False,
        "admission_allowed": False,
        "external_repair_credit_count": 0,
        "summary_hash": stable_hash(contract),
    }

    write_json(OUT / "anti_collapse_dataset_generation_contract.json", contract)
    write_json(OUT / "guardrail_scan.json", guardrail)
    write_json(OUT / "summary.json", summary)
    write_json(SUMMARY, summary)
    write_jsonl(OUT / "anti_collapse_gates.jsonl", anti_collapse_gates)
    write_jsonl(OUT / "dataset_generation_lanes.jsonl", lanes)


if __name__ == "__main__":
    main()
