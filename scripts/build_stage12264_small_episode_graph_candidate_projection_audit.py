#!/usr/bin/env python3
"""Build Stage12264 small episode-graph candidate projection audit.

This stage converts only the capped Stage12263 audit windows into source-agnostic
episode_graph_candidate skeletons. It intentionally performs no admission and
emits no raw chat/tool/patch content.
"""

from __future__ import annotations

import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12264_small_episode_graph_candidate_projection_audit"
TOP25 = ROOT / "runs/local/artifacts/stage12263_high_value_window_profiler/top25_audit_set.jsonl"
PAIRS = ROOT / "runs/local/artifacts/stage12259_codex_tool_call_observation_pairer/tool_call_observation_pairs.jsonl"

VERIFIER_HEADS = {
    "pytest",
    "ctest",
    "cargo",
    "npm",
    "pnpm",
    "yarn",
    "node",
    "npx",
    "make",
    "cmake",
    "python",
    "python3",
    "/home/peyton/miniconda3/envs/ai/bin/python",
    "./node_modules/.bin/vitest",
    "./node_modules/.bin/tsc",
}


def stable_id(prefix: str, *parts: Any) -> str:
    raw = "\n".join(json.dumps(p, sort_keys=True, default=str) for p in parts)
    return f"{prefix}_{hashlib.sha256(raw.encode('utf-8')).hexdigest()[:20]}"


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


def command_category(head: str | None, tool_name: str | None) -> str:
    if tool_name == "apply_patch":
        return "patch_edit"
    head = head or ""
    if head in {"rg", "grep", "find", "sed", "cat", "ls", "jq", "tail", "head"}:
        return "inspect_or_search"
    if head in {"git"}:
        return "version_control"
    if head in VERIFIER_HEADS:
        return "verifier_or_execution"
    return "other_command"


def is_verifier_like(head: str | None, category: str) -> bool:
    if category == "verifier_or_execution":
        return True
    head = head or ""
    return head in VERIFIER_HEADS


def build_pair_index() -> dict[str, list[dict[str, Any]]]:
    by_chat: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for _, pair in iter_jsonl(PAIRS):
        chat_id = pair.get("chat_id")
        if not chat_id:
            continue
        call_line = int(pair.get("call_line_number") or 0)
        output_line = int(pair.get("output_line_number") or 0)
        category = command_category(pair.get("command_head"), pair.get("tool_name"))
        rec = {
            "tool_pair_ref": stable_id("tool_pair_ref", chat_id, pair.get("call_id"), call_line, output_line),
            "call_id_digest": hashlib.sha256(str(pair.get("call_id") or "").encode()).hexdigest()[:16],
            "tool_name": pair.get("tool_name"),
            "command_head": pair.get("command_head"),
            "command_category": category,
            "call_event_id": pair.get("call_event_id"),
            "output_event_id": pair.get("output_event_id"),
            "call_line_number": call_line,
            "output_line_number": output_line,
            "arguments_digest": pair.get("arguments_digest"),
            "output_digest": pair.get("output_digest"),
            "call_before_output": bool(pair.get("call_before_output")),
            "raw_arguments_emitted": False,
            "raw_output_emitted": False,
            "is_patch": pair.get("tool_name") == "apply_patch",
            "is_verifier_like": is_verifier_like(pair.get("command_head"), category),
        }
        by_chat[chat_id].append(rec)
    for rows in by_chat.values():
        rows.sort(key=lambda r: (r["call_line_number"], r["output_line_number"], r["tool_pair_ref"]))
    return by_chat


def validate_candidate(candidate: dict[str, Any]) -> dict[str, Any]:
    blockers: list[str] = []
    levels: dict[str, str] = {}
    refs = candidate["source_refs"]
    task = candidate["task"]
    root = candidate["root"]
    ordered_events = candidate["ordered_events"]
    decision_steps = candidate["decision_steps"]
    patch_trace = candidate["patch_trace"]
    verifier_results = candidate["verifier_results"]
    states = candidate["states"]
    stop_continue = candidate["stop_continue"]

    if not refs.get("snapshot_id") or not refs.get("source_root_label") or not refs.get("chat_or_session_ids"):
        blockers.append("v0_missing_source_lineage")
    if refs.get("raw_payloads_emitted"):
        blockers.append("v0_raw_payload_leak")
    levels["V0_source_envelope"] = "pass" if not any(b.startswith("v0_") for b in blockers) else "fail"

    if not ordered_events.get("monotonic_line_order"):
        blockers.append("v1_nonmonotonic_event_order")
    if ordered_events.get("paired_tool_call_count", 0) <= 0:
        blockers.append("v1_no_paired_tool_observations")
    if ordered_events.get("unpaired_execution_used_as_evidence"):
        blockers.append("v1_unpaired_execution_used_as_evidence")
    levels["V1_ordering_pairing"] = "pass" if not any(b.startswith("v1_") for b in blockers) else "fail"

    if not task.get("task_window_id") or not task.get("boundary_confidence"):
        blockers.append("v2_missing_task_boundary")
    if task.get("boundary_confidence") != "lifecycle_exact":
        blockers.append("v2_non_lifecycle_boundary")
    if not root.get("language_family_candidate"):
        blockers.append("v2_missing_language_candidate")
    levels["V2_task_boundary"] = "pass" if not any(b.startswith("v2_") for b in blockers) else "fail"

    if not states.get("state_before_materialized"):
        blockers.append("v3_state_before_missing")
    if not decision_steps or not all(step.get("candidate_actions_materialized") for step in decision_steps):
        blockers.append("v3_candidate_actions_missing")
    if not decision_steps or not all(step.get("chosen_action_materialized") for step in decision_steps):
        blockers.append("v3_chosen_action_missing")
    if not verifier_results.get("observation_refs"):
        blockers.append("v3_observation_refs_missing")
    if not states.get("state_after_materialized"):
        blockers.append("v3_state_after_missing")
    if not stop_continue.get("stop_continue_materialized"):
        blockers.append("v3_stop_continue_missing")
    levels["V3_causal_tuple"] = "pass" if not any(b.startswith("v3_") for b in blockers) else "fail"

    if not patch_trace.get("has_patch_ref"):
        blockers.append("v4_patch_ref_missing")
    if not verifier_results.get("has_verifier_ref"):
        blockers.append("v4_verifier_ref_missing")
    if not patch_trace.get("patch_before_verifier_proven"):
        blockers.append("v4_patch_before_verifier_not_proven")
    if not verifier_results.get("paired_verifier_observation_exists"):
        blockers.append("v4_paired_verifier_observation_missing")
    if not verifier_results.get("verifier_relevance_materialized"):
        blockers.append("v4_verifier_relevance_not_materialized")
    levels["V4_patch_verifier"] = "pass" if not any(b.startswith("v4_") for b in blockers) else "fail"

    blockers.append("v5_no_admission_in_stage12264")
    levels["V5_admission_qc"] = "fail"

    highest = "V2_task_boundary"
    if levels["V3_causal_tuple"] == "pass" and levels["V4_patch_verifier"] == "pass":
        highest = "V4_patch_verifier"
    elif levels["V3_causal_tuple"] == "pass":
        highest = "V3_causal_tuple"
    elif levels["V0_source_envelope"] == "pass" and levels["V1_ordering_pairing"] == "pass" and levels["V2_task_boundary"] == "pass":
        highest = "V2_task_boundary"

    return {
        "validation_levels": levels,
        "highest_validated_level": highest,
        "blocker_codes": sorted(set(blockers)),
        "admission_allowed": False,
        "training_allowed": False,
        "strict_eval_eligible": False,
    }


def main() -> int:
    pair_index = build_pair_index()
    candidates: list[dict[str, Any]] = []
    validation_rows: list[dict[str, Any]] = []
    per_chat: Counter[str] = Counter()
    per_lang: Counter[str] = Counter()
    highest_levels: Counter[str] = Counter()
    blocker_counts: Counter[str] = Counter()

    for _, row in iter_jsonl(TOP25):
        chat_id = row["chat_id"]
        line_start = int(row.get("line_start") or 0)
        line_end = int(row.get("line_end") or 0)
        pairs = [
            p for p in pair_index.get(chat_id, [])
            if line_start <= int(p["call_line_number"]) <= line_end
        ]
        patch_pairs = [p for p in pairs if p["is_patch"]]
        verifier_pairs = [p for p in pairs if p["is_verifier_like"]]
        first_patch_line = min((p["call_line_number"] for p in patch_pairs), default=None)
        last_patch_line = max((p["call_line_number"] for p in patch_pairs), default=None)
        pre_patch_verifier_pairs = [
            p for p in verifier_pairs
            if first_patch_line is not None and p["call_line_number"] < first_patch_line
        ]
        later_verifier_pairs = [
            p for p in verifier_pairs
            if first_patch_line is not None and p["call_line_number"] > first_patch_line
        ]
        post_last_patch_verifier_pairs = [
            p for p in verifier_pairs
            if last_patch_line is not None and p["call_line_number"] > last_patch_line
        ]
        patch_before_verifier = bool(first_patch_line is not None and later_verifier_pairs)

        event_summary = {
            "event_span_refs": {
                "start_event_id": row.get("event_start_id"),
                "end_event_id": row.get("event_end_id"),
                "line_start": line_start,
                "line_end": line_end,
                "event_count": row.get("event_count"),
            },
            "monotonic_line_order": bool(line_start and line_end and line_start <= line_end),
            "paired_tool_call_count": len(pairs),
            "patch_pair_count": len(patch_pairs),
            "verifier_like_pair_count": len(verifier_pairs),
            "unpaired_execution_used_as_evidence": False,
            "tool_pair_refs": [p["tool_pair_ref"] for p in pairs[:200]],
            "command_category_counts": dict(Counter(p["command_category"] for p in pairs)),
            "tool_name_counts": dict(Counter(p["tool_name"] for p in pairs)),
            "command_head_counts": dict(Counter(p.get("command_head") or "unknown" for p in pairs).most_common(20)),
        }

        candidate_id = stable_id("episode_graph_candidate", row.get("task_window_id"), chat_id, row.get("snapshot_id"))
        candidate = {
            "schema_version": "episode_graph_candidate_v1",
            "candidate_id": candidate_id,
            "stage": STAGE,
            "source_adapter": "codex_sessions",
            "source_refs": {
                "snapshot_id": row.get("snapshot_id"),
                "source_root_label": row.get("source_root_label"),
                "physical_source_ids": [row.get("source_file_hash_compat")],
                "chat_or_session_ids": [chat_id],
                "session_id_hint": row.get("session_id_hint"),
                "task_window_id": row.get("task_window_id"),
                "event_span_refs": event_summary["event_span_refs"],
                "raw_payload_digests": {
                    "source_file_hash_compat": row.get("source_file_hash_compat"),
                    "file_content_sha256": row.get("file_content_sha256"),
                },
                "adapter_payload_refs": [row.get("shard_id")],
                "raw_payloads_emitted": False,
            },
            "root": {
                "root_id_candidate": stable_id("root_candidate", row.get("source_file_hash_compat"), row.get("task_window_id")),
                "repo_family": "unknown_until_cwd_or_repo_join",
                "cwd_boundary_ref": None,
                "language_family_candidate": row.get("likely_language_family") or "unknown",
                "license_security_flags": [],
                "split_intent": "audit_only_no_split_assignment",
            },
            "task": {
                "task_window_id": row.get("task_window_id"),
                "boundary_confidence": "lifecycle_exact",
                "task_summary_materialized": False,
                "task_source": "codex_lifecycle_window_metadata_only",
                "overlap_relation": "no_overlap_detected_in_stage12262",
            },
            "ordered_events": event_summary,
            "states": {
                "state_before_materialized": False,
                "state_after_materialized": False,
                "state_update_materialized": False,
                "state_materialization_required_next": True,
            },
            "decision_steps": [
                {
                    "step_id": stable_id("decision_step", candidate_id, "metadata_only"),
                    "state_before_ref": None,
                    "candidate_actions": [],
                    "candidate_actions_materialized": False,
                    "chosen_action": None,
                    "chosen_action_materialized": False,
                    "action_grammar_type": None,
                    "observation_refs": [p["tool_pair_ref"] for p in later_verifier_pairs[:25]],
                    "state_update_ref": None,
                    "rationale_evidence_refs": [],
                }
            ],
            "observations": {
                "paired_observation_refs": [p["tool_pair_ref"] for p in pairs[:200]],
                "observation_digest_refs": [
                    {
                        "tool_pair_ref": p["tool_pair_ref"],
                        "arguments_digest": p["arguments_digest"],
                        "output_digest": p["output_digest"],
                        "command_category": p["command_category"],
                        "command_head": p["command_head"],
                    }
                    for p in pairs[:200]
                ],
                "raw_observation_text_emitted": False,
            },
            "patch_trace": {
                "has_patch_ref": bool(patch_pairs),
                "patch_pair_refs": [p["tool_pair_ref"] for p in patch_pairs[:50]],
                "first_patch_call_line": first_patch_line,
                "last_patch_call_line": last_patch_line,
                "patch_before_verifier_proven": patch_before_verifier,
                "verifier_after_last_patch_proven": bool(post_last_patch_verifier_pairs),
                "patch_diff_materialized": False,
                "raw_patch_body_emitted": False,
                "no_patch_reason": None if patch_pairs else "no_patch_pair_in_window",
            },
            "verifier_results": {
                "has_verifier_ref": bool(verifier_pairs),
                "verifier_pair_refs": [p["tool_pair_ref"] for p in verifier_pairs[:100]],
                "post_patch_verifier_pair_refs": [p["tool_pair_ref"] for p in later_verifier_pairs[:100]],
                "pre_patch_verifier_pair_refs": [p["tool_pair_ref"] for p in pre_patch_verifier_pairs[:100]],
                "post_last_patch_verifier_pair_refs": [p["tool_pair_ref"] for p in post_last_patch_verifier_pairs[:100]],
                "pre_patch_verifier_pair_count": len(pre_patch_verifier_pairs),
                "post_last_patch_verifier_pair_count": len(post_last_patch_verifier_pairs),
                "paired_verifier_observation_exists": bool(later_verifier_pairs),
                "verifier_relevance_materialized": False,
                "verifier_status_materialized": False,
                "observation_refs": [p["tool_pair_ref"] for p in later_verifier_pairs[:100]],
                "raw_verifier_output_emitted": False,
            },
            "stop_continue": {
                "stop_continue_materialized": False,
                "terminal_status": "unknown_until_state_distillation",
            },
            "admission": {
                "admission_status": "blocked_projection_audit_only",
                "train_support_allowed": False,
                "strict_eval_eligible": False,
                "source_heldout_admissible": False,
                "gpt_review_allowed_next": bool(row.get("source_root_repaired_from_chat_manifest")),
                "gpt_review_cannot_override_deterministic_gates": True,
            },
            "privacy_security": {
                "raw_message_text_emitted": False,
                "raw_patch_body_emitted": False,
                "raw_tool_arguments_emitted": False,
                "raw_tool_output_emitted": False,
                "secret_scan_required_before_raw_review": True,
            },
            "dedupe_lineage": {
                "lineage_key": stable_id("lineage", row.get("source_file_hash_compat"), line_start, line_end),
                "chat_cap_group": chat_id,
                "repo_family_cap_group": "unknown_until_cwd_or_repo_join",
                "selected_under_max3_per_chat_cap": True,
            },
            "audit_trail": {
                "source_stage": "stage12263_high_value_window_profiler",
                "source_rank": row.get("rank"),
                "source_score": row.get("score"),
                "selection_reason": row.get("selection_reason"),
                "known_limitations": [
                    "metadata_only_candidate_skeleton",
                    "repo_family_unknown_until_cwd_join",
                    "task_state_not_materialized",
                    "candidate_actions_not_materialized",
                    "verifier_relevance_not_materialized",
                    "selected_audit_set_all_python_inferred",
                ],
            },
            "training_allowed": False,
        }
        validation = validate_candidate(candidate)
        candidate["validation"] = validation
        candidates.append(candidate)
        validation_rows.append({
            "candidate_id": candidate_id,
            "task_window_id": row.get("task_window_id"),
            "chat_id": chat_id,
            "line_start": line_start,
            "line_end": line_end,
            "language_family_candidate": row.get("likely_language_family") or "unknown",
            "paired_tool_call_count": len(pairs),
            "patch_pair_count": len(patch_pairs),
            "verifier_like_pair_count": len(verifier_pairs),
            "post_patch_verifier_pair_count": len(later_verifier_pairs),
            "pre_patch_verifier_pair_count": len(pre_patch_verifier_pairs),
            "post_last_patch_verifier_pair_count": len(post_last_patch_verifier_pairs),
            "highest_validated_level": validation["highest_validated_level"],
            "blocker_codes": validation["blocker_codes"],
            "training_allowed": False,
            "admission_allowed": False,
        })
        per_chat[chat_id] += 1
        per_lang[row.get("likely_language_family") or "unknown"] += 1
        highest_levels[validation["highest_validated_level"]] += 1
        blocker_counts.update(validation["blocker_codes"])

    max_per_chat = max(per_chat.values(), default=0)
    summary = {
        "stage": STAGE,
        "artifact_type": "small_episode_graph_candidate_projection_audit",
        "decision": "candidate_skeletons_emitted_no_admission_training_blocked",
        "training_allowed": False,
        "claim_boundary": (
            "Projection audit only. Candidate skeletons use metadata/digest refs from the capped Stage12263 set. "
            "They are not admitted roots, not training rows, and not Level-3 closed-loop examples."
        ),
        "input": {
            "top25_audit_set": str(TOP25.relative_to(ROOT)),
            "paired_call_observation_index": str(PAIRS.relative_to(ROOT)),
        },
        "counts": {
            "candidate_skeletons": len(candidates),
            "per_chat": dict(per_chat),
            "max_per_chat": max_per_chat,
            "per_language_family_candidate": dict(per_lang),
            "highest_validated_level_counts": dict(highest_levels),
            "blocker_counts": dict(blocker_counts.most_common()),
        },
        "quality_decision": {
            "source_root_repair_required_before_gpt_review": "satisfied_for_stage12263_top25_via_chat_manifest",
            "gpt_review_allowed": True,
            "gpt_review_scope": "segmentation/causal/state-distillation review only; cannot admit rows",
            "admission_allowed": False,
            "reason_training_blocked": [
                "state_before/state_after not materialized",
                "candidate actions/chosen action not materialized",
                "verifier relevance/status not materialized",
                "repo/cwd boundary not joined",
                "selected audit set is all inferred Python",
            ],
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
            "stage": "stage12265_gpt_review_packet_for_capped_episode_graph_candidates",
            "scope": "bounded subagent review of 25 candidate skeletons for segmentation, causal relevance, and state fields; no admission",
            "training_allowed": False,
        },
    }

    out_dir = ROOT / "runs/local/artifacts" / STAGE
    write_jsonl(out_dir / "episode_graph_candidate_skeletons.jsonl", candidates)
    write_jsonl(out_dir / "candidate_validation_audit.jsonl", validation_rows)
    write_json(ROOT / "runs/summaries" / f"{STAGE}.json", summary)
    write_json(out_dir / "small_episode_graph_candidate_projection_audit.json", summary)
    md = f"""# Stage12264 Small Episode-Graph Candidate Projection Audit

## Decision

`{summary["decision"]}`

No admission or training is allowed.

## Counts

- candidate skeletons: `{len(candidates)}`
- max per chat: `{max_per_chat}`
- highest validated levels: `{dict(highest_levels)}`

These candidates are metadata/digest-ref skeletons. They are not Level-3 closed-loop examples until state, actions, observations, verifier relevance, state update, and stop/continue are materialized and audited.
"""
    write_text(out_dir / "SMALL_EPISODE_GRAPH_CANDIDATE_PROJECTION_AUDIT_STAGE12264.md", md)
    print(ROOT / "runs/summaries" / f"{STAGE}.json")
    print(out_dir / "episode_graph_candidate_skeletons.jsonl")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
