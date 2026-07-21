#!/usr/bin/env python3
"""Build Stage12269 external semantic review result ingest.

Ingests bounded semantic-review outputs for Stage12268. The reviews are
ref-only/safe classifications from subagents. No admission or training rows.
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12269_external_semantic_review_result_ingest"

REVIEW_ROWS: list[dict[str, Any]] = [
    {
        "candidate_id": "episode_graph_candidate_f80a3251f908c76ec921",
        "semantic_review_packet_id": "semantic_review_001",
        "semantic_verifier_relevance": "ambiguous",
        "same_verifier_pre_post": "ambiguous",
        "failure_origin": "ambiguous",
        "external_task_validity": "valid_external",
        "split_required": "yes",
        "review_decision": "split_required",
        "external_comparable_patch_trace_countable": False,
        "fail_to_pass_countable": False,
        "hard_reject_codes": [
            "semantic_verifier_relevance_not_proven",
            "same_verifier_pre_post_not_proven",
            "multi_loop_window_split_required",
            "failure_origin_not_classifiable_from_safe_materialization",
            "fail_to_pass_not_established",
        ],
    },
    {
        "candidate_id": "episode_graph_candidate_7b01486ba671109f1e7a",
        "semantic_review_packet_id": "semantic_review_002",
        "semantic_verifier_relevance": "relevant",
        "same_verifier_pre_post": "not_applicable",
        "failure_origin": "ambiguous",
        "external_task_validity": "valid_external",
        "split_required": "yes",
        "review_decision": "split_required",
        "external_comparable_patch_trace_countable": False,
        "fail_to_pass_countable": False,
        "hard_reject_codes": [
            "NO_OBSERVED_PRE_PATCH_FAILURE",
            "MULTI_PATCH_MULTI_VERIFIER_WINDOW",
            "MIXED_POST_VERIFIER_OUTCOMES",
            "NOT_FAIL_TO_PASS",
        ],
    },
    {
        "candidate_id": "episode_graph_candidate_c6450a72013f4039dc33",
        "semantic_review_packet_id": "semantic_review_003",
        "semantic_verifier_relevance": "relevant",
        "same_verifier_pre_post": "not_applicable",
        "failure_origin": "not_applicable",
        "external_task_validity": "valid_external",
        "split_required": "yes",
        "review_decision": "split_required",
        "external_comparable_patch_trace_countable": False,
        "fail_to_pass_countable": False,
        "hard_reject_codes": [
            "NO_OBSERVED_PRE_PATCH_FAILURE",
            "MULTI_PATCH_WINDOW",
            "PASS_ONLY_POST_VERIFIER",
            "NOT_FAIL_TO_PASS",
        ],
    },
    {
        "candidate_id": "episode_graph_candidate_8a970b279b3966afa6eb",
        "semantic_review_packet_id": "semantic_review_004",
        "semantic_verifier_relevance": "ambiguous",
        "same_verifier_pre_post": "not_applicable",
        "failure_origin": "not_applicable",
        "external_task_validity": "valid_external",
        "split_required": "yes",
        "review_decision": "quarantine",
        "external_comparable_patch_trace_countable": False,
        "fail_to_pass_countable": False,
        "hard_reject_codes": [
            "POST_VERIFIER_REF_JOIN_MISSING",
            "NO_OBSERVED_PRE_PATCH_FAILURE",
            "PRE_AND_POST_PASS_ONLY",
            "MULTI_LOOP_WINDOW",
            "VERIFIER_RELEVANCE_UNPROVEN",
        ],
    },
    {
        "candidate_id": "episode_graph_candidate_a0ed4c17ad98c574f4a2",
        "semantic_review_packet_id": "semantic_review_005",
        "semantic_verifier_relevance": "relevant",
        "same_verifier_pre_post": "not_applicable",
        "failure_origin": "task_failure",
        "external_task_validity": "valid_external",
        "split_required": "no",
        "review_decision": "quarantine",
        "external_comparable_patch_trace_countable": False,
        "fail_to_pass_countable": False,
        "hard_reject_codes": [
            "NO_OBSERVED_PRE_PATCH_FAILURE",
            "POST_VERIFIER_FAILURES_REMAIN",
            "MIXED_POST_VERIFIER_OUTCOMES",
            "NOT_FAIL_TO_PASS",
        ],
    },
    {
        "candidate_id": "episode_graph_candidate_db313a88872e8e903352",
        "semantic_review_packet_id": "semantic_review_006",
        "semantic_verifier_relevance": "not_relevant",
        "same_verifier_pre_post": "not_applicable",
        "failure_origin": "not_applicable",
        "external_task_validity": "valid_external",
        "split_required": "yes",
        "review_decision": "split_required",
        "external_comparable_patch_trace_countable": False,
        "fail_to_pass_countable": False,
        "hard_reject_codes": [
            "LAST_PATCH_VERIFIER_SEMANTIC_MISMATCH",
            "VERIFIERS_ATTACH_TO_PRIOR_CODE_PATCHES",
            "NO_OBSERVED_PRE_PATCH_FAILURE",
            "PASS_ONLY_POST_VERIFIER",
            "NOT_FAIL_TO_PASS",
        ],
    },
    {
        "candidate_id": "episode_graph_candidate_f2e92cf81ed8923cc451",
        "semantic_review_packet_id": "semantic_review_007",
        "semantic_verifier_relevance": "not_relevant_to_materialized_chosen_patch",
        "same_verifier_pre_post": "not_applicable",
        "failure_origin": "tooling_failure",
        "external_task_validity": "valid_external",
        "split_required": "yes",
        "review_decision": "quarantine",
        "external_comparable_patch_trace_countable": False,
        "fail_to_pass_countable": False,
        "hard_reject_codes": [
            "selected_patch_ref_not_effective",
            "effective_edit_unmaterialized_as_patch",
            "pre_patch_fail_missing",
            "fail_to_pass_status_not_observed",
            "multi_loop_split_required",
        ],
    },
    {
        "candidate_id": "episode_graph_candidate_c0374f69884c467e9326",
        "semantic_review_packet_id": "semantic_review_008",
        "semantic_verifier_relevance": "not_relevant_to_materialized_chosen_patch",
        "same_verifier_pre_post": "not_applicable",
        "failure_origin": "tooling_failure",
        "external_task_validity": "private_site_unclear",
        "split_required": "yes",
        "review_decision": "quarantine",
        "external_comparable_patch_trace_countable": False,
        "fail_to_pass_countable": False,
        "hard_reject_codes": [
            "selected_patch_ref_not_effective",
            "effective_edit_unmaterialized_as_patch",
            "pre_patch_fail_missing",
            "fail_to_pass_status_not_observed",
            "post_unknown_status_present",
            "private_site_externality_unclear",
        ],
    },
    {
        "candidate_id": "episode_graph_candidate_78331f0c6fb32dd2b518",
        "semantic_review_packet_id": "semantic_review_009",
        "semantic_verifier_relevance": "not_relevant_to_materialized_chosen_patch",
        "same_verifier_pre_post": "not_applicable",
        "failure_origin": "tooling_failure",
        "external_task_validity": "private_site_unclear",
        "split_required": "yes",
        "review_decision": "quarantine",
        "external_comparable_patch_trace_countable": False,
        "fail_to_pass_countable": False,
        "hard_reject_codes": [
            "selected_patch_ref_not_effective",
            "effective_edit_unmaterialized_as_patch",
            "pre_patch_fail_missing",
            "fail_to_pass_status_not_observed",
            "private_site_externality_unclear",
        ],
    },
    {
        "candidate_id": "episode_graph_candidate_ea2e38c644618694e1b9",
        "semantic_review_packet_id": "semantic_review_010",
        "semantic_verifier_relevance": "not_relevant_to_materialized_chosen_patch",
        "same_verifier_pre_post": "not_applicable",
        "failure_origin": "tooling_failure",
        "external_task_validity": "private_site_unclear",
        "split_required": "yes",
        "review_decision": "quarantine",
        "external_comparable_patch_trace_countable": False,
        "fail_to_pass_countable": False,
        "hard_reject_codes": [
            "selected_patch_ref_not_effective",
            "effective_edit_unmaterialized_as_patch",
            "pre_patch_fail_missing",
            "fail_to_pass_status_not_observed",
            "post_unknown_status_present",
            "private_site_externality_unclear",
        ],
    },
    {
        "candidate_id": "episode_graph_candidate_1a0d06ffe0ee84af7a92",
        "semantic_review_packet_id": "semantic_review_011",
        "semantic_verifier_relevance": "not_relevant_to_materialized_chosen_patch",
        "same_verifier_pre_post": "not_applicable",
        "failure_origin": "tooling_failure",
        "external_task_validity": "private_site_unclear",
        "split_required": "yes",
        "review_decision": "quarantine",
        "external_comparable_patch_trace_countable": False,
        "fail_to_pass_countable": False,
        "hard_reject_codes": [
            "selected_patch_ref_not_effective",
            "effective_edit_unmaterialized_as_patch",
            "pre_patch_fail_missing",
            "fail_to_pass_status_not_observed",
            "private_site_externality_unclear",
        ],
    },
]


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, sort_keys=True) + "\n")


def write_text(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value, encoding="utf-8")


def main() -> int:
    decisions = Counter(r["review_decision"] for r in REVIEW_ROWS)
    relevance = Counter(r["semantic_verifier_relevance"] for r in REVIEW_ROWS)
    validity = Counter(r["external_task_validity"] for r in REVIEW_ROWS)
    rejects = Counter(code for r in REVIEW_ROWS for code in r["hard_reject_codes"])
    external_countable = sum(1 for r in REVIEW_ROWS if r["external_comparable_patch_trace_countable"])
    fail_to_pass = sum(1 for r in REVIEW_ROWS if r["fail_to_pass_countable"])
    split_required = sum(1 for r in REVIEW_ROWS if r["split_required"] == "yes")
    summary = {
        "stage": STAGE,
        "artifact_type": "external_semantic_review_result_ingest",
        "decision": "semantic_reviews_ingested_all_external_candidates_blocked_training_blocked",
        "training_allowed": False,
        "claim_boundary": "Review-result ingest only. No roots admitted and no training rows emitted.",
        "counts": {
            "reviewed_candidates": len(REVIEW_ROWS),
            "external_comparable_patch_trace_countable": external_countable,
            "fail_to_pass_countable": fail_to_pass,
            "split_required": split_required,
            "review_decision_counts": dict(decisions),
            "semantic_relevance_counts": dict(relevance),
            "external_task_validity_counts": dict(validity),
            "hard_reject_counts": dict(rejects.most_common()),
        },
        "decisive_counter_progress": {
            "sealed_transition_eval_rows": 0,
            "external_comparable_patch_trace_repair_rows": external_countable,
            "external_fail_to_pass_rows": fail_to_pass,
            "non_python_external_repair_rows": 0,
            "level3_same_source_closed_loop_candidates": 25,
            "level3_same_source_closed_loop_admitted": 0,
        },
        "quality_decision": {
            "admission_allowed": False,
            "training_allowed": False,
            "reason": "All reviewed external candidates are split-required or quarantined; none prove comparable FAIL_TO_PASS repair.",
        },
        "guardrails": {
            "raw_message_text_emitted": False,
            "raw_patch_body_emitted": False,
            "raw_tool_arguments_emitted": False,
            "raw_tool_output_emitted": False,
            "root_admission_emitted": False,
            "training_rows_emitted_now": False,
        },
        "next_stage": {
            "stage": "stage12270_child_loop_splitter_for_external_candidates",
            "scope": "split selected multi-loop external windows into child patch-verifier loops, then re-run semantic relevance and pre/post filters",
            "training_allowed": False,
        },
    }
    out_dir = ROOT / "runs/local/artifacts" / STAGE
    write_jsonl(out_dir / "external_semantic_review_results.jsonl", REVIEW_ROWS)
    write_json(ROOT / "runs/summaries" / f"{STAGE}.json", summary)
    write_json(out_dir / "external_semantic_review_result_ingest.json", summary)
    md = f"""# Stage12269 External Semantic Review Result Ingest

## Decision

`{summary["decision"]}`

No training is allowed.

The capped top25 path yielded V3-like structure, but `0` external comparable repair rows and `0` FAIL_TO_PASS rows after semantic review.
"""
    write_text(out_dir / "EXTERNAL_SEMANTIC_REVIEW_RESULT_INGEST_STAGE12269.md", md)
    print(ROOT / "runs/summaries" / f"{STAGE}.json")
    print(out_dir / "external_semantic_review_results.jsonl")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
