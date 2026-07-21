#!/usr/bin/env python3
"""Build Stage12265 bounded review packet for capped episode candidates.

This stage prepares review tasks for the 25 Stage12264 candidate skeletons.
It does not admit roots, emit training rows, or expose raw session content.
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12265_gpt_review_packet_for_capped_episode_graph_candidates"
SKELETONS = ROOT / "runs/local/artifacts/stage12264_small_episode_graph_candidate_projection_audit/episode_graph_candidate_skeletons.jsonl"
VALIDATION = ROOT / "runs/local/artifacts/stage12264_small_episode_graph_candidate_projection_audit/candidate_validation_audit.jsonl"


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


def main() -> int:
    validations = {row["candidate_id"]: row for _, row in iter_jsonl(VALIDATION)}
    packets: list[dict[str, Any]] = []
    per_chat: Counter[str] = Counter()
    per_level: Counter[str] = Counter()
    pre_patch: Counter[str] = Counter()
    post_last: Counter[str] = Counter()

    for _, cand in iter_jsonl(SKELETONS):
        cid = cand["candidate_id"]
        val = validations.get(cid, {})
        source_refs = cand.get("source_refs") or {}
        root = cand.get("root") or {}
        ordered = cand.get("ordered_events") or {}
        patch = cand.get("patch_trace") or {}
        verifier = cand.get("verifier_results") or {}
        audit = cand.get("audit_trail") or {}
        chat_id = (source_refs.get("chat_or_session_ids") or [None])[0]
        per_chat[str(chat_id)] += 1
        per_level[str(val.get("highest_validated_level"))] += 1
        pre_patch["has_pre_patch_verifier" if val.get("pre_patch_verifier_pair_count", 0) > 0 else "no_pre_patch_verifier"] += 1
        post_last["has_post_last_patch_verifier" if val.get("post_last_patch_verifier_pair_count", 0) > 0 else "no_post_last_patch_verifier"] += 1

        packet = {
            "review_packet_id": f"review_packet_{cid.removeprefix('episode_graph_candidate_')}",
            "candidate_id": cid,
            "source_adapter": cand.get("source_adapter"),
            "source_refs": {
                "snapshot_id": source_refs.get("snapshot_id"),
                "source_root_label": source_refs.get("source_root_label"),
                "chat_or_session_ids": source_refs.get("chat_or_session_ids"),
                "session_id_hint": source_refs.get("session_id_hint"),
                "task_window_id": source_refs.get("task_window_id"),
                "event_span_refs": source_refs.get("event_span_refs"),
                "raw_payload_digests": source_refs.get("raw_payload_digests"),
                "adapter_payload_refs": source_refs.get("adapter_payload_refs"),
            },
            "current_validation": {
                "highest_validated_level": val.get("highest_validated_level"),
                "blocker_codes": val.get("blocker_codes"),
                "admission_allowed": False,
                "training_allowed": False,
            },
            "root_recovery": {
                "status": "chat_hint_only",
                "candidate_level_root_proven": False,
                "cwd_boundary_ref": root.get("cwd_boundary_ref"),
                "cwd_hint_ref": "stage12258_per_chat_manifest.cwd_hints_top",
                "workspace_root_hint_ref": "stage12258_per_chat_manifest.workspace_root_hints_top",
                "cwd_hint_cardinality": "not_materialized_in_stage12265_packet",
                "workspace_root_hint_cardinality": "not_materialized_in_stage12265_packet",
                "repo_family_candidate": root.get("repo_family"),
                "repo_family_confidence": "none",
                "promotion_rule": "must_be_upgraded_from_chat_hint_only_to_window_direct_before_admission",
                "promotion_blockers": ["no_window_cwd_key", "repo_family_unjoined"],
                "source_join": {
                    "candidate_id": cid,
                    "chat_id": chat_id,
                    "task_window_id": source_refs.get("task_window_id"),
                    "session_id_hint": source_refs.get("session_id_hint"),
                    "snapshot_id": source_refs.get("snapshot_id"),
                    "event_span_refs": source_refs.get("event_span_refs"),
                },
            },
            "metadata_evidence": {
                "language_family_candidate": root.get("language_family_candidate"),
                "repo_family": root.get("repo_family"),
                "cwd_boundary_ref": root.get("cwd_boundary_ref"),
                "paired_tool_call_count": ordered.get("paired_tool_call_count"),
                "patch_pair_count": ordered.get("patch_pair_count"),
                "verifier_like_pair_count": ordered.get("verifier_like_pair_count"),
                "first_patch_call_line": patch.get("first_patch_call_line"),
                "last_patch_call_line": patch.get("last_patch_call_line"),
                "pre_patch_verifier_pair_count": verifier.get("pre_patch_verifier_pair_count"),
                "post_patch_verifier_pair_count": val.get("post_patch_verifier_pair_count"),
                "post_last_patch_verifier_pair_count": verifier.get("post_last_patch_verifier_pair_count"),
                "command_category_counts": ordered.get("command_category_counts"),
                "command_head_counts": ordered.get("command_head_counts"),
                "known_limitations": audit.get("known_limitations"),
            },
            "review_scope": {
                "allowed": [
                    "segmentation_check",
                    "repo_cwd_root_boundary_inference",
                    "state_before_after_distillation",
                    "candidate_action_set_reconstruction",
                    "chosen_action_identification",
                    "verifier_relevance_classification",
                    "stop_continue_classification",
                    "hard_reject_reasoning",
                ],
                "forbidden": [
                    "root_admission",
                    "training_row_generation",
                    "strict_eval_marking",
                    "raw_chat_text_emission",
                    "raw_patch_body_emission",
                    "raw_tool_argument_emission",
                    "raw_tool_output_emission",
                    "gpt_override_of_deterministic_gates",
                ],
            },
            "required_review_output_schema": {
                "candidate_id": "string",
                "review_decision": "materializable|blocked|split_required|quarantine",
                "hard_reject_codes": ["string"],
                "raw_content_emitted": False,
                "root_recovery": {
                    "status": "candidate_proven|chat_hint_only|blocked",
                    "cwd_boundary_ref": "ref_or_null",
                    "cwd_hint_ref": "ref_or_null",
                    "workspace_root_hint_ref": "ref_or_null",
                    "cwd_hint_cardinality": "integer_or_unknown",
                    "workspace_root_hint_cardinality": "integer_or_unknown",
                    "repo_family_candidate": "string_or_null",
                    "repo_family_confidence": "none|chat_singleton|window_direct",
                    "promotion_rule": "string",
                    "promotion_blockers": ["string"],
                    "source_join": {
                        "candidate_id": "string",
                        "chat_id": "string",
                        "task_window_id": "string",
                        "session_id_hint": "string_or_null",
                        "snapshot_id": "string",
                        "event_span_refs": "object",
                    },
                },
                "repo_cwd_boundary": {
                    "status": "proven|unproven|conflicting",
                    "repo_family": "string_or_null",
                    "cwd_ref": "digest_or_ref_only",
                    "evidence_refs": ["tool_pair_ref_or_event_id"],
                },
                "segmentation": {
                    "status": "single_task|multi_task_split_required|ambiguous",
                    "task_boundary_refs": ["event_id_or_line_span_ref"],
                    "child_window_proposals": ["ref_only_optional"],
                },
                "state_before": {
                    "status": "materialized|missing|ambiguous",
                    "state_before_ref": "ref_or_null",
                    "safe_state_summary": "short_no_raw_payload_text",
                    "evidence_refs": ["tool_pair_ref_or_event_id"],
                },
                "candidate_action_set": {
                    "status": "materialized|missing|ambiguous",
                    "actions": [
                        {
                            "action_id": "stable_ref",
                            "action_type": "inspect|search|run|edit|patch|verify|abstain|stop|delegate|handoff",
                            "action_ref": "tool_pair_ref_or_event_id_or_null",
                            "safe_action_summary": "short_no_raw_payload_text",
                            "source_event_refs": ["event_id"],
                            "evidence_refs": ["tool_pair_ref_or_event_id"],
                        }
                    ],
                },
                "chosen_action": {
                    "status": "materialized|missing|ambiguous",
                    "action_id": "stable_ref_or_null",
                    "action_ref": "tool_pair_ref_or_event_id_or_null",
                    "tool_pair_ref": "tool_pair_ref_or_null",
                    "patch_pair_ref": "tool_pair_ref_or_null",
                    "evidence_refs": ["tool_pair_ref_or_event_id"],
                },
                "observations": {
                    "status": "materialized|missing|ambiguous",
                    "items": [
                        {
                            "observation_ref": "stable_ref",
                            "tool_pair_ref": "tool_pair_ref_or_null",
                            "observation_kind": "command_result|patch_result|verifier_result|search_result|other",
                            "outcome_status": "pass|fail|mixed|env_blocked|unknown",
                            "relevance_to_chosen_action": "relevant|not_relevant|ambiguous",
                            "evidence_refs": ["tool_pair_ref_or_event_id"],
                        }
                    ],
                },
                "state_update": {
                    "status": "materialized|missing|ambiguous",
                    "state_update_ref": "ref_or_null",
                    "from_state_ref": "ref_or_null",
                    "chosen_action_ref": "ref_or_null",
                    "observation_refs": ["observation_ref"],
                    "safe_update_summary": "short_no_raw_payload_text",
                    "evidence_refs": ["tool_pair_ref_or_event_id"],
                },
                "causal_tuple": {
                    "state_before_status": "materialized|missing|ambiguous",
                    "candidate_actions_status": "materialized|missing|ambiguous",
                    "chosen_action_status": "materialized|missing|ambiguous",
                    "observation_status": "materialized|missing|ambiguous",
                    "state_update_status": "materialized|missing|ambiguous",
                    "stop_continue_status": "materialized|missing|ambiguous",
                },
                "patch_verifier": {
                    "ordering_status": "post_last_patch_verifier|multi_loop_ambiguous|not_proven",
                    "patch_pair_refs": ["tool_pair_ref"],
                    "verifier_pair_refs": ["tool_pair_ref"],
                    "post_last_patch_verifier_pair_refs": ["tool_pair_ref"],
                    "verifier_relevance_status": "relevant|not_relevant|ambiguous|missing",
                    "verifier_outcome_status": "pass|fail|mixed|env_blocked|unknown",
                    "evidence_refs": ["tool_pair_ref_or_event_id"],
                },
                "stop_continue": {
                    "status": "materialized|missing|ambiguous",
                    "label": "STOP|CONTINUE|UNKNOWN",
                    "terminal_status": "task_complete|turn_aborted|no_terminal_event|unknown",
                    "reason_code": "string_or_null",
                    "next_action_ref": "ref_or_null",
                    "evidence_refs": ["tool_pair_ref_or_event_id"],
                },
                "next_required_deterministic_join": ["string"],
            },
        }
        packets.append(packet)

    summary = {
        "stage": STAGE,
        "artifact_type": "bounded_gpt_review_packet",
        "decision": "review_packet_ready_no_admission_training_blocked",
        "training_allowed": False,
        "claim_boundary": (
            "Review-control artifact only. It packages Stage12264 candidate skeleton refs for bounded review. "
            "No roots are admitted and no training rows are emitted."
        ),
        "counts": {
            "review_packets": len(packets),
            "per_chat": dict(per_chat),
            "max_per_chat": max(per_chat.values(), default=0),
            "highest_validated_level_counts": dict(per_level),
            "pre_patch_verifier_counts": dict(pre_patch),
            "post_last_patch_verifier_counts": dict(post_last),
        },
        "review_policy": {
            "gpt_review_allowed": True,
            "gpt_can_admit_rows": False,
            "deterministic_revalidation_required_after_review": True,
            "source_root_label_is_repo_root": False,
            "raw_content_emission_allowed": False,
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
            "stage": "stage12266_capped_episode_graph_review_result_ingest",
            "scope": "ingest bounded review outputs, revalidate deterministically, still no admission unless V3/V4 fields are proven",
            "training_allowed": False,
        },
    }

    out_dir = ROOT / "runs/local/artifacts" / STAGE
    write_jsonl(out_dir / "bounded_review_packets.jsonl", packets)
    write_json(ROOT / "runs/summaries" / f"{STAGE}.json", summary)
    write_json(out_dir / "bounded_review_packet_summary.json", summary)
    md = f"""# Stage12265 Bounded GPT Review Packet

## Decision

`{summary["decision"]}`

This stage authorizes bounded review only. It does not admit roots or create training rows.

## Required Reviewer Rule

Reviewers may propose materialized fields and hard reject codes, but deterministic validation must re-check source lineage, segmentation, causal tuple completeness, patch/verifier order, verifier relevance, and raw-content guardrails before any future admission.
"""
    write_text(out_dir / "BOUNDED_GPT_REVIEW_PACKET_STAGE12265.md", md)
    print(ROOT / "runs/summaries" / f"{STAGE}.json")
    print(out_dir / "bounded_review_packets.jsonl")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
