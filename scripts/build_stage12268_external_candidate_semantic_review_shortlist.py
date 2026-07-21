#!/usr/bin/env python3
"""Build Stage12268 external candidate semantic review shortlist.

Creates bounded review packets for external candidate-proven Stage12267 rows.
No admission, no training rows, and no raw payload content.
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12268_external_candidate_semantic_review_shortlist"
QUEUE = ROOT / "runs/local/artifacts/stage12267_semantic_verifier_relevance_and_external_filter_audit/external_candidate_review_queue.jsonl"
MATERIALIZED = ROOT / "runs/local/artifacts/stage12266_capped_episode_graph_review_result_ingest/materialized_review_results.jsonl"


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


def priority(row: dict[str, Any]) -> tuple[int, int, str]:
    status = row.get("status_shape")
    repo = row.get("repo_family") or ""
    return (
        0 if status == "potential_fail_to_pass" else 1,
        0 if repo not in {"staticpeytonsite"} else 1,
        repo,
    )


def main() -> int:
    queue = [row for _, row in iter_jsonl(QUEUE)]
    materialized = {row["candidate_id"]: row for _, row in iter_jsonl(MATERIALIZED)}
    queue.sort(key=priority)
    packets: list[dict[str, Any]] = []
    repo_counts: Counter[str] = Counter()
    status_counts: Counter[str] = Counter()
    for idx, row in enumerate(queue, 1):
        mat = materialized.get(row["candidate_id"], {})
        pv = mat.get("patch_verifier") or {}
        root = mat.get("root_recovery") or {}
        repo_counts[row.get("repo_family") or "unknown"] += 1
        status_counts[row.get("status_shape") or "unknown"] += 1
        packets.append({
            "semantic_review_packet_id": f"semantic_review_{idx:03d}",
            "candidate_id": row["candidate_id"],
            "priority_rank": idx,
            "repo_family": row.get("repo_family"),
            "repo_kind": row.get("repo_kind"),
            "root_status": row.get("root_status"),
            "status_shape": row.get("status_shape"),
            "pre_patch_verifier_outcomes": row.get("pre_patch_verifier_outcomes"),
            "post_last_patch_verifier_outcomes": row.get("post_last_patch_verifier_outcomes"),
            "patch_pair_count": row.get("patch_pair_count"),
            "post_last_patch_verifier_count": row.get("post_last_patch_verifier_count"),
            "source_refs": row.get("source_refs"),
            "safe_materialized_refs": {
                "chosen_action": mat.get("chosen_action"),
                "state_before_ref": (mat.get("state_before") or {}).get("state_before_ref"),
                "state_update_ref": (mat.get("state_update") or {}).get("state_update_ref"),
                "post_last_patch_verifier_pair_refs": pv.get("post_last_patch_verifier_pair_refs"),
                "pre_patch_verifier_count": pv.get("pre_patch_verifier_count"),
                "post_last_patch_verifier_count": pv.get("post_last_patch_verifier_count"),
                "cwd_ref": root.get("cwd_ref"),
                "cwd_tail": root.get("cwd_tail"),
                "raw_content_emitted": False,
            },
            "review_questions": [
                "Does the selected post-last-patch verifier semantically test the chosen patch/action?",
                "If pre-patch failures exist, are they same-verifier/same-task failures comparable to the post-patch verifier?",
                "Is any fail status an environment/dependency/tooling failure rather than task failure?",
                "Is this a real external software-maintenance task rather than self-research/dataset construction?",
                "Should the row be split into child patch-verifier loops before any future admission?",
                "Can this candidate count as external comparable patch-trace repair? Can it count as FAIL_TO_PASS?",
            ],
            "required_review_output_schema": {
                "candidate_id": "string",
                "review_decision": "external_comparable_candidate|fail_to_pass_candidate|pass_only_support|split_required|quarantine",
                "semantic_verifier_relevance": "relevant|not_relevant|ambiguous",
                "same_verifier_pre_post": "yes|no|not_applicable|ambiguous",
                "failure_origin": "task_failure|env_blocked|dependency_failure|tooling_failure|ambiguous|not_applicable",
                "external_task_validity": "valid_external|self_research|private_site_unclear|ambiguous",
                "split_required": "yes|no|ambiguous",
                "admission_allowed": False,
                "training_allowed": False,
                "hard_reject_codes": ["string"],
                "evidence_refs": ["tool_pair_ref_or_event_id"],
                "raw_content_emitted": False,
            },
            "admission_allowed": False,
            "training_allowed": False,
            "raw_content_emitted": False,
        })

    summary = {
        "stage": STAGE,
        "artifact_type": "external_candidate_semantic_review_shortlist",
        "decision": "semantic_review_shortlist_ready_no_admission_training_blocked",
        "training_allowed": False,
        "claim_boundary": "Shortlist/review-control artifact only. It does not admit rows or create training data.",
        "counts": {
            "review_packets": len(packets),
            "repo_family_counts": dict(repo_counts),
            "status_shape_counts": dict(status_counts),
            "potential_fail_to_pass_packets": sum(1 for p in packets if p["status_shape"] == "potential_fail_to_pass"),
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
            "stage": "stage12269_external_semantic_review_result_ingest",
            "scope": "ingest bounded semantic review outputs and update decisive counters; still deterministic admission-gated",
            "training_allowed": False,
        },
    }
    out_dir = ROOT / "runs/local/artifacts" / STAGE
    write_jsonl(out_dir / "external_semantic_review_packets.jsonl", packets)
    write_json(ROOT / "runs/summaries" / f"{STAGE}.json", summary)
    write_json(out_dir / "external_candidate_semantic_review_shortlist.json", summary)
    md = f"""# Stage12268 External Candidate Semantic Review Shortlist

## Decision

`{summary["decision"]}`

No training is allowed.

Reviewers must decide whether any external candidate has semantic verifier relevance and true FAIL_TO_PASS evidence. They cannot admit rows.
"""
    write_text(out_dir / "EXTERNAL_CANDIDATE_SEMANTIC_REVIEW_SHORTLIST_STAGE12268.md", md)
    print(ROOT / "runs/summaries" / f"{STAGE}.json")
    print(out_dir / "external_semantic_review_packets.jsonl")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
