#!/usr/bin/env python3
"""Build Stage12267 semantic verifier relevance and external filter audit.

This stage filters Stage12266 materialized candidates for external-comparable
repair eligibility. It does not admit roots or create training rows.
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12267_semantic_verifier_relevance_and_external_filter_audit"
INPUT = ROOT / "runs/local/artifacts/stage12266_capped_episode_graph_review_result_ingest/materialized_review_results.jsonl"


def iter_jsonl(path: Path):
    with path.open("r", encoding="utf-8", errors="ignore") as f:
        for line_no, line in enumerate(f, 1):
            line = line.strip()
            if line:
                yield line_no, json.loads(line)


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


def classify(row: dict[str, Any]) -> dict[str, Any]:
    root = row["root_recovery"]
    pv = row["patch_verifier"]
    post = Counter(pv.get("post_last_verifier_outcome_status_counts") or pv.get("verifier_outcome_status_counts") or {})
    pre = Counter(pv.get("pre_patch_verifier_outcome_status_counts") or {})
    rejects = set(row.get("hard_reject_codes") or [])
    blockers: list[str] = []
    if root.get("status") != "candidate_proven":
        blockers.append("candidate_root_not_proven")
    if root.get("repo_kind") == "self_research_repo":
        blockers.append("self_research_repo")
    if pv.get("ordering_status") != "post_last_patch_verifier":
        blockers.append("patch_verifier_ordering_not_proven")
    if pv.get("verifier_relevance_status") != "relevant":
        blockers.append("verifier_relevance_not_semantically_proven")
    if not post:
        blockers.append("post_patch_verifier_outcome_missing")
    if post and not post.get("pass", 0):
        blockers.append("post_patch_pass_missing")
    if not pre.get("fail", 0):
        blockers.append("pre_patch_fail_missing")
    if "verifier_relevance_ambiguous_without_semantic_review" in rejects:
        blockers.append("semantic_review_required")
    if "state_update_safe_summary_requires_review" in rejects:
        blockers.append("state_update_review_required")

    status_shape = "unknown"
    if pre.get("fail", 0) and post.get("pass", 0):
        status_shape = "potential_fail_to_pass"
    elif post.get("pass", 0) and not pre.get("fail", 0):
        status_shape = "pass_after_patch_without_observed_pre_fail"
    elif post.get("fail", 0):
        status_shape = "post_patch_fail_or_mixed"

    external_comparable = not blockers
    return {
        "candidate_id": row["candidate_id"],
        "repo_family": root.get("repo_family"),
        "repo_kind": root.get("repo_kind"),
        "root_status": root.get("status"),
        "status_shape": status_shape,
        "pre_patch_verifier_outcomes": dict(pre),
        "post_last_patch_verifier_outcomes": dict(post),
        "patch_pair_count": len(pv.get("patch_pair_refs") or []),
        "post_last_patch_verifier_count": pv.get("post_last_patch_verifier_count"),
        "external_comparable_patch_trace_candidate": external_comparable,
        "external_fail_to_pass_candidate": external_comparable and status_shape == "potential_fail_to_pass",
        "blocker_codes": sorted(set(blockers)),
        "training_allowed": False,
        "admission_allowed": False,
        "source_refs": row.get("source_refs"),
        "next_required_deterministic_join": row.get("next_required_deterministic_join"),
        "raw_content_emitted": False,
    }


def main() -> int:
    rows = [classify(row) for _, row in iter_jsonl(INPUT)]
    blockers = Counter(code for row in rows for code in row["blocker_codes"])
    repo_kinds = Counter(row["repo_kind"] for row in rows)
    shapes = Counter(row["status_shape"] for row in rows)
    root_status = Counter(row["root_status"] for row in rows)
    external_candidates = [r for r in rows if r["external_comparable_patch_trace_candidate"]]
    fail_to_pass = [r for r in rows if r["external_fail_to_pass_candidate"]]
    external_review_queue = [
        r for r in rows
        if r["repo_kind"] == "external_or_other_repo" and r["root_status"] == "candidate_proven"
    ]

    summary = {
        "stage": STAGE,
        "artifact_type": "semantic_verifier_relevance_and_external_filter_audit",
        "decision": "external_filter_complete_no_admission_training_blocked",
        "training_allowed": False,
        "claim_boundary": (
            "Filter/audit artifact only. It counts external-comparable candidates and FAIL_TO_PASS candidates, "
            "but no row is admitted because semantic verifier relevance is not proven."
        ),
        "counts": {
            "input_candidates": len(rows),
            "external_review_queue": len(external_review_queue),
            "external_comparable_patch_trace_candidates": len(external_candidates),
            "external_fail_to_pass_candidates": len(fail_to_pass),
            "repo_kind_counts": dict(repo_kinds),
            "root_status_counts": dict(root_status),
            "status_shape_counts": dict(shapes),
            "blocker_counts": dict(blockers.most_common()),
        },
        "decisive_counter_progress": {
            "sealed_transition_eval_rows": 0,
            "external_comparable_patch_trace_repair_rows": len(external_candidates),
            "external_fail_to_pass_rows": len(fail_to_pass),
            "non_python_external_repair_rows": 0,
            "level3_same_source_closed_loop_candidates": len(rows),
            "level3_same_source_closed_loop_admitted": 0,
        },
        "quality_decision": {
            "admission_allowed": False,
            "training_allowed": False,
            "reason": "All rows still require semantic verifier relevance proof; PASS-after-patch without observed pre-fail is not FAIL_TO_PASS repair proof.",
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
            "stage": "stage12268_external_candidate_semantic_review_shortlist",
            "scope": "bounded semantic review of external candidate-proven rows only; no admission until verifier relevance and pre/post status pass",
            "training_allowed": False,
        },
    }

    out_dir = ROOT / "runs/local/artifacts" / STAGE
    write_jsonl(out_dir / "external_filter_audit_rows.jsonl", rows)
    write_jsonl(out_dir / "external_candidate_review_queue.jsonl", external_review_queue)
    write_json(ROOT / "runs/summaries" / f"{STAGE}.json", summary)
    write_json(out_dir / "semantic_verifier_relevance_and_external_filter_audit.json", summary)
    md = f"""# Stage12267 Semantic Verifier Relevance And External Filter Audit

## Decision

`{summary["decision"]}`

No training is allowed.

## Counts

- external review queue: `{len(external_review_queue)}`
- external comparable patch-trace candidates: `{len(external_candidates)}`
- external FAIL_TO_PASS candidates: `{len(fail_to_pass)}`

Rows with only post-patch PASS are not counted as FAIL_TO_PASS repair proof.
"""
    write_text(out_dir / "SEMANTIC_VERIFIER_RELEVANCE_AND_EXTERNAL_FILTER_AUDIT_STAGE12267.md", md)
    print(ROOT / "runs/summaries" / f"{STAGE}.json")
    print(out_dir / "external_candidate_review_queue.jsonl")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
