#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12295_transition_function_ledger"
PAIRS = ROOT / "runs/local/artifacts/stage12259_codex_tool_call_observation_pairer/tool_call_observation_pairs.jsonl"
WINDOWS = ROOT / "runs/local/artifacts/stage12260_codex_chat_task_boundary_miner/codex_task_windows.jsonl"
CHILD_LOOPS = ROOT / "runs/local/artifacts/stage12274_status_join_for_root_repaired_child_loops/status_joined_child_loop_candidates.jsonl"
OUT = ROOT / "runs/local/artifacts" / STAGE
SUMMARY = ROOT / "runs/summaries" / f"{STAGE}.json"

MAX_ROWS_PER_CHAT = 80
MAX_ROWS_PER_ACTION_FAMILY_PER_CHAT = 20
MAX_CHILD_LOOP_ROWS_PER_ROOT = 8


def stable_id(prefix: str, *parts) -> str:
    payload = json.dumps(parts, sort_keys=True, default=str).encode("utf-8")
    return f"{prefix}_{hashlib.sha256(payload).hexdigest()[:20]}"


def iter_jsonl(path: Path):
    if not path.exists():
        return
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                yield json.loads(line)


def write_jsonl(path: Path, rows) -> int:
    count = 0
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")
            count += 1
    return count


def action_family(pair: dict) -> str:
    tool = pair.get("tool_name")
    head = (pair.get("command_head") or "").lower()
    if tool == "apply_patch":
        return "EDIT_PATCH"
    if head in {"rg", "grep", "find", "fd", "ls", "cat", "sed", "head", "tail", "jq", "wc"}:
        return "READ_OR_SEARCH"
    if head in {"pytest", "cargo", "npm", "pnpm", "yarn", "node", "npx", "make", "cmake", "ctest", "go", "python", "python3"}:
        return "RUN_OR_VERIFY"
    if head == "git":
        return "VERSION_CONTROL"
    if head in {"pip", "uv", "conda", "apt", "brew"}:
        return "ENVIRONMENT_SETUP"
    if tool in {"update_plan", "create_goal", "update_goal", "get_goal"}:
        return "CONTROL_PLANE"
    return "OTHER_ACTION"


def output_kind(pair: dict) -> str:
    out_type = pair.get("output_payload_type")
    if out_type == "function_call_output":
        return "OBSERVED_TOOL_OUTPUT"
    if out_type:
        return f"OBSERVED_{out_type.upper()}"
    return "OBSERVED_UNKNOWN"


def candidate_set_for_action(correct: str) -> list[dict]:
    options = [
        ("A", "READ_OR_SEARCH"),
        ("B", "RUN_OR_VERIFY"),
        ("C", "EDIT_PATCH"),
        ("D", "VERSION_CONTROL"),
        ("E", "ENVIRONMENT_SETUP"),
        ("F", "OTHER_ACTION"),
    ]
    # Model-visible candidates must stay neutral. The observed action is target-only elsewhere.
    return [
        {
            "candidate_id": cid,
            "semantic_action": action,
        }
        for cid, action in options
    ]


def window_index() -> dict[str, list[dict]]:
    by_chat: dict[str, list[dict]] = defaultdict(list)
    for window in iter_jsonl(WINDOWS) or []:
        by_chat[window["chat_id"]].append(window)
    for rows in by_chat.values():
        rows.sort(key=lambda row: row["start_line"])
    return by_chat


def find_window(windows_by_chat: dict[str, list[dict]], pair: dict) -> dict | None:
    rows = windows_by_chat.get(pair["chat_id"], [])
    line = pair.get("call_line_number")
    for row in rows:
        if row["start_line"] <= line <= row["end_line"]:
            return row
    return None


def build_pair_ledgers():
    windows_by_chat = window_index()
    for pair in iter_jsonl(PAIRS) or []:
        family = action_family(pair)
        window = find_window(windows_by_chat, pair)
        source_refs = {
            "chat_id": pair.get("chat_id"),
            "call_event_id": pair.get("call_event_id"),
            "output_event_id": pair.get("output_event_id"),
            "call_line_number": pair.get("call_line_number"),
            "output_line_number": pair.get("output_line_number"),
            "tool_pair_ref": stable_id("tool_pair_ref", pair.get("chat_id"), pair.get("call_id")),
        }
        if window:
            source_refs.update(
                {
                    "snapshot_id": window.get("snapshot_id"),
                    "task_window_id": window.get("task_window_id"),
                    "session_id_hint": window.get("session_id_hint"),
                    "source_file_hash_compat": window.get("source_file_hash_compat"),
                    "window_training_potential": window.get("training_potential"),
                }
            )
        transition_id = stable_id("transition", source_refs, pair.get("arguments_digest"), pair.get("output_digest"))
        yield {
            "schema_version": "transition_function_ledger_v1",
            "stage": STAGE,
            "transition_id": transition_id,
            "source_refs": source_refs,
            "lineage": {
                "root_lineage_key": stable_id(
                    "root_lineage",
                    pair.get("chat_id"),
                    window.get("task_window_id") if window else None,
                    window.get("session_id_hint") if window else None,
                ),
                "split_group_id": stable_id("split_group", pair.get("chat_id")),
                "sibling_loss_group": stable_id("sibling_loss", pair.get("chat_id"), window.get("task_window_id") if window else None),
                "dedupe_cluster_id": stable_id("dedupe", family, pair.get("command_head"), pair.get("arguments_digest")),
            },
            "validation_level": "V1_PAIRED_ACTION_OBSERVATION",
            "horizon_label": "H1",
            "task_family_candidates": ["transition_next_action"],
            "state_before_ref": stable_id("state_before", pair.get("chat_id"), pair.get("call_line_number")),
            "candidate_action_set_hash": stable_id("candidate_action_set", "generic_action_family_v1", family),
            "chosen_action": {
                "semantic_action": family,
                "command_head_digest": stable_id("command_head", pair.get("command_head")),
            },
            "observation_ref": {
                "observation_kind": output_kind(pair),
                "output_digest": pair.get("output_digest"),
                "raw_output_emitted": False,
            },
            "proof_flags": {
                "observed_pre_patch_failure": False,
                "observed_post_patch_pass": False,
                "same_verifier_exact": False,
                "semantic_verifier_relevance_proven": False,
                "external_comparable_patch_trace_countable": False,
                "external_fail_to_pass_countable": False,
            },
            "guardrails": {
                "raw_message_text_emitted": False,
                "raw_tool_arguments_emitted": False,
                "raw_tool_output_emitted": False,
                "raw_patch_body_emitted": False,
                "raw_source_path_emitted": False,
            },
        }


def post_status_summary(statuses: list[dict]) -> Counter:
    c: Counter[str] = Counter()
    for row in statuses or []:
        c[row.get("status", "UNKNOWN")] += 1
    return c


def verifier_label(loop: dict) -> str:
    status_join = loop.get("status_join", {})
    pre = post_status_summary(status_join.get("pre_verifier_statuses", []))
    post = post_status_summary(status_join.get("post_verifier_statuses", []))
    if pre.get("FAIL") and post.get("PASS") and not post.get("FAIL"):
        return "FAIL_TO_PASS_SMOKE_NOT_COMPARABLE"
    if pre.get("PASS") and post.get("PASS") and not post.get("FAIL"):
        return "PASS_TO_PASS_AFTER_PATCH"
    if post.get("FAIL"):
        return "POST_PATCH_FAILURE_REMAINS"
    if post.get("PASS"):
        return "POST_PATCH_PASS_ONLY"
    return "UNKNOWN_VERIFIER_TRANSITION"


def continue_label(loop: dict) -> str:
    status_join = loop.get("status_join", {})
    if status_join.get("post_patch_failure_remains"):
        return "CONTINUE_REPAIR"
    if loop.get("admission", {}).get("external_comparable_patch_trace_countable"):
        return "MAY_STOP_AFTER_COMPARABLE_REPAIR"
    if status_join.get("observed_post_patch_pass"):
        return "CONTINUE_NOT_PROMOTABLE"
    return "CONTINUE_GATHER_EVIDENCE"


def build_child_loop_ledgers():
    for loop in iter_jsonl(CHILD_LOOPS) or []:
        source_refs = loop.get("source_refs", {})
        lineage = loop.get("lineage", {})
        transition_id = stable_id("transition_child_loop", loop.get("child_loop_id"))
        label = verifier_label(loop)
        yield {
            "schema_version": "transition_function_ledger_v1",
            "stage": STAGE,
            "transition_id": transition_id,
            "source_refs": {
                "chat_id": source_refs.get("chat_id"),
                "snapshot_id": source_refs.get("snapshot_id"),
                "task_window_id": source_refs.get("task_window_id"),
                "session_id_hint": source_refs.get("session_id_hint"),
                "source_file_hash_compat": source_refs.get("source_file_hash_compat"),
                "event_start_id": source_refs.get("event_start_id"),
                "event_end_id": source_refs.get("event_end_id"),
                "child_loop_id": loop.get("child_loop_id"),
            },
            "lineage": {
                "root_lineage_key": lineage.get("root_lineage_key"),
                "split_group_id": lineage.get("split_group_id"),
                "sibling_loss_group": lineage.get("sibling_loss_group"),
                "dedupe_cluster_id": lineage.get("dedupe_cluster_id"),
            },
            "validation_level": "V3_PATCH_VERIFIER_STATUS_JOIN_NOT_REPAIR_PROOF",
            "horizon_label": loop.get("horizon_bucket"),
            "task_family_candidates": ["transition_verifier_transition", "transition_continue_or_stop", "state_update"],
            "state_before_ref": stable_id("state_before", loop.get("child_loop_id"), "pre_patch"),
            "chosen_action": {
                "semantic_action": "APPLY_PATCH_THEN_VERIFY",
                "patch_ref_digest": (loop.get("patch_ref") or {}).get("output_digest"),
            },
            "observation_ref": {
                "pre_status_counts": dict(post_status_summary(loop.get("status_join", {}).get("pre_verifier_statuses", []))),
                "post_status_counts": dict(post_status_summary(loop.get("status_join", {}).get("post_verifier_statuses", []))),
                "raw_output_emitted": False,
            },
            "target_labels": {
                "verifier_transition_label": label,
                "continue_stop_label": continue_label(loop),
                "state_update_codes": [
                    "post_patch_failure_remains" if loop.get("status_join", {}).get("post_patch_failure_remains") else "no_post_patch_failure_observed",
                    "not_external_comparable_repair_proof",
                ],
            },
            "proof_flags": {
                "observed_pre_patch_failure": bool(loop.get("status_join", {}).get("observed_pre_patch_failure")),
                "observed_post_patch_pass": bool(loop.get("status_join", {}).get("observed_post_patch_pass")),
                "same_verifier_exact": False,
                "same_verifier_head_only": bool(loop.get("status_join", {}).get("same_verifier_pre_post_by_command_head")),
                "semantic_verifier_relevance_proven": bool(loop.get("status_join", {}).get("semantic_verifier_relevance_proven")),
                "external_comparable_patch_trace_countable": False,
                "external_fail_to_pass_countable": False,
            },
            "guardrails": {
                "raw_message_text_emitted": False,
                "raw_tool_arguments_emitted": False,
                "raw_tool_output_emitted": False,
                "raw_patch_body_emitted": False,
                "raw_source_path_emitted": False,
            },
        }


def build_train_rows(ledger_rows: list[dict]):
    chat_counts: Counter[str] = Counter()
    chat_action_counts: Counter[tuple[str, str]] = Counter()
    root_child_counts: Counter[str] = Counter()
    seen: set[tuple[str, str]] = set()
    for row in ledger_rows:
        validation = row.get("validation_level")
        source = row.get("source_refs", {})
        chat_id = source.get("chat_id")
        root_key = row.get("lineage", {}).get("root_lineage_key")
        if validation == "V1_PAIRED_ACTION_OBSERVATION":
            action = row["chosen_action"]["semantic_action"]
            if chat_counts[chat_id] >= MAX_ROWS_PER_CHAT:
                continue
            if chat_action_counts[(chat_id, action)] >= MAX_ROWS_PER_ACTION_FAMILY_PER_CHAT:
                continue
            key = (row["lineage"]["dedupe_cluster_id"], "transition_next_action")
            if key in seen:
                continue
            seen.add(key)
            chat_counts[chat_id] += 1
            chat_action_counts[(chat_id, action)] += 1
            yield {
                "schema_version": "transition_function_train_row_v1",
                "stage": STAGE,
                "row_id": stable_id("transition_row", row["transition_id"], "next_action"),
                "source_transition_id": row["transition_id"],
                "task_family": "transition_next_action",
                "validation_level": validation,
                "split": "train_support_dev",
                "root_lineage_key": root_key,
                "split_group_id": row["lineage"]["split_group_id"],
                "state_before_ref": row["state_before_ref"],
                "candidate_action_set": candidate_set_for_action(action),
                "target_semantic_action": action,
                "target_only": {
                    "chosen_action": row["chosen_action"],
                    "observation_ref": row["observation_ref"],
                },
                "admission": {
                    "train_support_allowed": True,
                    "strict_eval_eligible": False,
                    "source_heldout_admissible": False,
                    "external_comparable_patch_trace_countable": False,
                    "external_fail_to_pass_countable": False,
                },
                "visibility_masks": {
                    "pre_action_model_input": ["state_before_ref", "candidate_action_set"],
                    "target_only": ["target_semantic_action", "chosen_action", "observation_ref"],
                    "never_emit": ["raw_tool_output", "raw_tool_arguments", "raw_patch_body", "raw_source_path", "full_command_text"],
                },
            }
        elif validation == "V3_PATCH_VERIFIER_STATUS_JOIN_NOT_REPAIR_PROOF":
            if root_child_counts[root_key] >= MAX_CHILD_LOOP_ROWS_PER_ROOT:
                continue
            root_child_counts[root_key] += 1
            for task_family, target_key in [
                ("transition_verifier_transition", "verifier_transition_label"),
                ("transition_continue_or_stop", "continue_stop_label"),
            ]:
                yield {
                    "schema_version": "transition_function_train_row_v1",
                    "stage": STAGE,
                    "row_id": stable_id("transition_row", row["transition_id"], task_family),
                    "source_transition_id": row["transition_id"],
                    "task_family": task_family,
                    "validation_level": validation,
                    "split": "train_support_dev",
                    "root_lineage_key": root_key,
                    "split_group_id": row["lineage"]["split_group_id"],
                    "state_before_ref": row["state_before_ref"],
                    "candidate_action_set": [
                        {"candidate_id": "A", "semantic_action": "FAIL_TO_PASS_SMOKE_NOT_COMPARABLE"},
                        {"candidate_id": "B", "semantic_action": "PASS_TO_PASS_AFTER_PATCH"},
                        {"candidate_id": "C", "semantic_action": "POST_PATCH_FAILURE_REMAINS"},
                        {"candidate_id": "D", "semantic_action": "POST_PATCH_PASS_ONLY"},
                        {"candidate_id": "E", "semantic_action": "CONTINUE_REPAIR"},
                        {"candidate_id": "F", "semantic_action": "CONTINUE_NOT_PROMOTABLE"},
                    ],
                    "target_semantic_action": row["target_labels"][target_key],
                    "target_only": {
                        "chosen_action": row["chosen_action"],
                        "observation_ref": row["observation_ref"],
                        "target_labels": row["target_labels"],
                    },
                    "admission": {
                        "train_support_allowed": True,
                        "strict_eval_eligible": False,
                        "source_heldout_admissible": False,
                        "external_comparable_patch_trace_countable": False,
                        "external_fail_to_pass_countable": False,
                    },
                    "visibility_masks": {
                        "pre_action_model_input": ["state_before_ref", "candidate_action_set"],
                        "target_only": ["target_semantic_action", "chosen_action", "observation_ref", "target_labels"],
                        "never_emit": ["raw_tool_output", "raw_tool_arguments", "raw_patch_body", "raw_source_path", "full_command_text"],
                    },
                }


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    pair_rows = list(build_pair_ledgers())
    child_rows = list(build_child_loop_ledgers())
    ledger_rows = pair_rows + child_rows
    train_rows = list(build_train_rows(ledger_rows))

    ledger_count = write_jsonl(OUT / "transition_function_ledger.jsonl", ledger_rows)
    train_count = write_jsonl(OUT / "transition_function_train_support_rows.jsonl", train_rows)

    summary = {
        "stage": STAGE,
        "decision": "transition_function_ledger_ready_train_support_only",
        "claim_boundary": "High-volume transition-function support only. No external comparable repair proof or strict eval rows emitted.",
        "ledger_records": ledger_count,
        "pair_action_observation_records": len(pair_rows),
        "child_loop_status_join_records": len(child_rows),
        "train_support_rows": train_count,
        "validation_level_counts": dict(Counter(row["validation_level"] for row in ledger_rows)),
        "train_task_family_counts": dict(Counter(row["task_family"] for row in train_rows)),
        "train_validation_level_counts": dict(Counter(row["validation_level"] for row in train_rows)),
        "action_family_counts_top20": dict(Counter(row.get("chosen_action", {}).get("semantic_action") for row in pair_rows).most_common(20)),
        "verifier_transition_label_counts": dict(Counter(row.get("target_labels", {}).get("verifier_transition_label") for row in child_rows).most_common()),
        "proof_counts": {
            "external_comparable_patch_trace_countable": 0,
            "external_fail_to_pass_countable": 0,
            "strict_eval_eligible": 0,
        },
        "caps": {
            "MAX_ROWS_PER_CHAT": MAX_ROWS_PER_CHAT,
            "MAX_ROWS_PER_ACTION_FAMILY_PER_CHAT": MAX_ROWS_PER_ACTION_FAMILY_PER_CHAT,
            "MAX_CHILD_LOOP_ROWS_PER_ROOT": MAX_CHILD_LOOP_ROWS_PER_ROOT,
        },
        "guardrails": {
            "raw_message_text_emitted": False,
            "raw_tool_arguments_emitted": False,
            "raw_tool_output_emitted": False,
            "raw_patch_body_emitted": False,
            "raw_source_path_emitted": False,
        },
        "next_stage": "stage12296_transition_function_projection_qc",
        "training_allowed": False,
    }
    (OUT / "transition_function_ledger_summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (OUT / "TRANSITION_FUNCTION_LEDGER_STAGE12295.md").write_text(
        "# Stage12295 Transition Function Ledger\n\n"
        + "This stage converts Codex chat/session artifacts into transition-function support records. "
        + "It does not emit strict eval rows or patch-effect proof rows.\n\n"
        + "```json\n"
        + json.dumps(summary, indent=2, sort_keys=True)
        + "\n```\n",
        encoding="utf-8",
    )
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
