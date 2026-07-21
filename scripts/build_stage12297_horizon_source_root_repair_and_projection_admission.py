#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12297_horizon_source_root_repair_and_projection_admission"
HORIZON = ROOT / "runs/local/artifacts/stage12271_horizon_slice_miner_pilot/horizon_slice_candidates.jsonl"
MANIFEST = ROOT / "runs/local/artifacts/stage12258_live_codex_chat_reconstruction_index/per_chat_manifest.jsonl"
OUT = ROOT / "runs/local/artifacts" / STAGE
SUMMARY = ROOT / "runs/summaries" / f"{STAGE}.json"

SELF_ROOTS = {"agentkernel-seq2seq-text-lab", "parameter-golf"}
MAX_ROWS_PER_CHAT = 80
MAX_ROWS_PER_ROOT = 80
MAX_ROWS_PER_TASK_FAMILY_PER_ROOT = 20
MAX_ROWS_PER_DEDUPE_CLUSTER = 3

SAFE_TRAIN_FAMILIES = {
    "transition_next_action",
    "transition_candidate_action_rank",
}


def stable_id(prefix: str, *parts: Any) -> str:
    raw = json.dumps(parts, sort_keys=True, default=str).encode("utf-8")
    return f"{prefix}_{hashlib.sha256(raw).hexdigest()[:20]}"


def iter_jsonl(path: Path):
    if not path.exists():
        return
    with path.open("r", encoding="utf-8", errors="ignore") as handle:
        for line in handle:
            line = line.strip()
            if line:
                yield json.loads(line)


def write_jsonl(path: Path, rows: list[dict]) -> int:
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")
    return len(rows)


def path_family(path: str | None) -> str:
    if not path:
        return "unknown"
    cleaned = path.rstrip("/")
    return cleaned.split("/")[-1] or "unknown"


def language_from_family(family: str, heads: dict[str, int]) -> str:
    head_keys = {str(k).split("/")[-1].lower() for k in heads}
    if {"cargo", "rustc"} & head_keys:
        return "rust"
    if {"npm", "npx", "pnpm", "yarn", "node", "tsc", "vitest"} & head_keys or family in {"bddy", "staticpeytonsite", "website"}:
        return "web_js_ts_html"
    if {"cmake", "make", "gcc", "g++", "cc", "ctest"} & head_keys:
        return "c_cpp"
    return "python"


def build_chat_roots() -> dict[str, dict]:
    roots = {}
    for row in iter_jsonl(MANIFEST) or []:
        chat_id = row.get("chat_id")
        cwd = None
        if row.get("workspace_root_hints_top"):
            cwd = row["workspace_root_hints_top"][0][0]
        elif row.get("cwd_hints_top"):
            cwd = row["cwd_hints_top"][0][0]
        family = path_family(cwd)
        roots[chat_id] = {
            "root_status": "candidate_proven" if cwd else "missing_cwd_hint",
            "repo_family_label": family,
            "repo_family_digest": stable_id("repo_family", cwd or chat_id),
            "cwd_hint_digest": stable_id("cwd_hint", cwd or chat_id),
            "repo_kind": "self_research_repo" if family in SELF_ROOTS else "external_or_other_repo",
            "language_family": language_from_family(family, row.get("command_head_counts") or {}),
            "cwd_hint_count": (row.get("workspace_root_hints_top") or row.get("cwd_hints_top") or [[None, 0]])[0][1],
            "raw_cwd_path_emitted": False,
        }
    return roots


def map_projection_family(family: str) -> str:
    return {
        "next_action": "transition_next_action",
        "candidate_action_rank": "transition_candidate_action_rank",
        "state_update": "transition_state_update",
        "verifier_interpretation": "transition_verifier_transition",
        "continue_or_stop": "transition_continue_or_stop",
        "evidence_role": "transition_evidence_role",
        "patch_selection": "transition_patch_selection",
        "verifier_transition": "transition_verifier_transition",
        "repair_vs_continue": "transition_continue_or_stop",
    }.get(family, f"transition_{family}")


def target_for(row: dict, task_family: str) -> dict:
    chosen = row.get("chosen_action") or {}
    state_update = row.get("state_update") or {}
    if task_family == "transition_next_action":
        return {
            "target_semantic_action": chosen.get("action_type", "unknown"),
            "chosen_action": chosen,
            "observation": row.get("observation"),
        }
    if task_family == "transition_candidate_action_rank":
        return {
            "target_semantic_action": "rank_chosen_action_first",
            "chosen_action": chosen,
            "observation": row.get("observation"),
        }
    if task_family == "transition_state_update":
        return {
            "target_semantic_action": state_update.get("safe_update_label", "needs_semantic_review"),
            "state_update": state_update,
            "observation": row.get("observation"),
        }
    return {
        "target_semantic_action": "blocked_unproven_target",
        "chosen_action": chosen,
        "observation": row.get("observation"),
    }


def candidate_set(row: dict, task_family: str) -> list[dict]:
    actions = (row.get("candidate_action_set") or {}).get("actions") or []
    if task_family in {"transition_next_action", "transition_candidate_action_rank"} and actions:
        return [
            {
                "candidate_id": chr(ord("A") + idx),
                "semantic_action": action.get("action_type", "unknown"),
                "command_head_digest": stable_id("command_head", action.get("command_head")),
                "role": "observed_chosen_action" if action.get("position_role") == "chosen" else "nearby_negative_action",
            }
            for idx, action in enumerate(actions[:6])
        ]
    return [
        {"candidate_id": "A", "semantic_action": "needs_semantic_review"},
        {"candidate_id": "B", "semantic_action": "no_progress"},
        {"candidate_id": "C", "semantic_action": "continue_after_observation"},
    ]


def hard_rejects(row: dict, root: dict, task_family: str) -> list[str]:
    reasons = []
    source = row.get("source_refs") or {}
    guard = row.get("guardrails") or {}
    cand = row.get("candidate_action_set") or {}
    if root.get("root_status") != "candidate_proven":
        reasons.append("source_root_not_repaired")
    if root.get("repo_kind") == "self_research_repo":
        reasons.append("self_research_root_blocked_from_horizon_training")
    if not cand.get("future_actions_masked"):
        reasons.append("future_actions_not_masked")
    for field in ["raw_message_text_emitted", "raw_tool_arguments_emitted", "raw_tool_output_emitted", "raw_patch_body_emitted"]:
        if guard.get(field):
            reasons.append(field)
    if source.get("source_root_label") and source.get("source_root_label") == "codex_sessions":
        # The generic adapter label is not the repaired root label.
        pass
    if task_family not in SAFE_TRAIN_FAMILIES:
        reasons.append("target_family_requires_semantic_or_causal_review")
    if (row.get("verifier_linkage") or {}).get("status") == "temporal_only_needs_causal_review" and task_family in {
        "transition_verifier_transition",
        "transition_continue_or_stop",
        "transition_patch_selection",
    }:
        reasons.append("temporal_patch_verifier_linkage_not_causal")
    return reasons


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    roots = build_chat_roots()
    admitted = []
    blocked = []
    chat_counts: Counter[str] = Counter()
    root_counts: Counter[str] = Counter()
    root_family_counts: Counter[tuple[str, str]] = Counter()
    dedupe_counts: Counter[str] = Counter()

    for horizon in iter_jsonl(HORIZON) or []:
        chat_id = (horizon.get("source_refs") or {}).get("chat_id")
        root = roots.get(chat_id, {"root_status": "missing_chat_manifest", "repo_family_label": "unknown", "repo_kind": "unknown", "language_family": "unknown"})
        repaired_root_lineage = stable_id(
            "root_lineage",
            horizon.get("lineage", {}).get("root_lineage_key"),
            root.get("repo_family_digest"),
            root.get("cwd_hint_digest"),
        )
        for raw_family in horizon.get("allowed_projection_families", []):
            task_family = map_projection_family(raw_family)
            reasons = hard_rejects(horizon, root, task_family)
            if chat_counts[chat_id] >= MAX_ROWS_PER_CHAT:
                reasons.append("chat_cap_reached")
            if root_counts[repaired_root_lineage] >= MAX_ROWS_PER_ROOT:
                reasons.append("root_cap_reached")
            if root_family_counts[(repaired_root_lineage, task_family)] >= MAX_ROWS_PER_TASK_FAMILY_PER_ROOT:
                reasons.append("root_task_family_cap_reached")
            dedupe_key = stable_id("dedupe", horizon.get("lineage", {}).get("dedupe_cluster_id"), task_family)
            if dedupe_counts[dedupe_key] >= MAX_ROWS_PER_DEDUPE_CLUSTER:
                reasons.append("dedupe_cluster_cap_reached")

            base = {
                "schema_version": "horizon_source_root_repaired_projection_row_v1",
                "stage": STAGE,
                "row_id": stable_id("transition_row", horizon.get("horizon_slice_id"), task_family, root.get("repo_family_digest")),
                "source_horizon_slice_id": horizon.get("horizon_slice_id"),
                "task_family": task_family,
                "horizon_label": horizon.get("horizon_label"),
                "validation_level": horizon.get("admission", {}).get("validation_level"),
                "root_lineage_key": repaired_root_lineage,
                "split_group_id": stable_id("split_group", chat_id, root.get("repo_family_digest")),
                "repo_family_label": root.get("repo_family_label"),
                "repo_family_digest": root.get("repo_family_digest"),
                "repo_kind": root.get("repo_kind"),
                "language_family": root.get("language_family"),
                "source_refs": {
                    "chat_id": chat_id,
                    "task_window_id": (horizon.get("source_refs") or {}).get("task_window_id"),
                    "snapshot_id": (horizon.get("source_refs") or {}).get("snapshot_id"),
                    "source_file_hash_compat": (horizon.get("source_refs") or {}).get("source_file_hash_compat"),
                    "source_root_repaired": root.get("root_status") == "candidate_proven",
                },
                "pre_action_fields": {
                    "state_before": horizon.get("state_before"),
                    "candidate_action_set": candidate_set(horizon, task_family),
                },
                "target_only": target_for(horizon, task_family),
                "admission": {
                    "train_support_allowed": not reasons,
                    "strict_eval_eligible": False,
                    "source_heldout_admissible": False,
                    "external_comparable_patch_trace_countable": False,
                    "external_fail_to_pass_countable": False,
                    "blocked_reasons": reasons,
                },
                "visibility_masks": {
                    "pre_action_model_input": ["pre_action_fields"],
                    "target_only": ["target_only"],
                    "never_emit": ["raw_tool_output", "raw_tool_arguments", "raw_patch_body", "raw_source_path", "full_command_text"],
                },
                "guardrails": {
                    "raw_message_text_emitted": False,
                    "raw_tool_arguments_emitted": False,
                    "raw_tool_output_emitted": False,
                    "raw_patch_body_emitted": False,
                    "raw_source_path_emitted": False,
                },
            }
            if reasons:
                blocked.append(base)
            else:
                admitted.append(base)
                chat_counts[chat_id] += 1
                root_counts[repaired_root_lineage] += 1
                root_family_counts[(repaired_root_lineage, task_family)] += 1
                dedupe_counts[dedupe_key] += 1

    write_jsonl(OUT / "admitted_horizon_transition_train_support_rows.jsonl", admitted)
    write_jsonl(OUT / "blocked_horizon_transition_projection_rows.jsonl", blocked)
    blocked_reason_counts: Counter[str] = Counter()
    for row in blocked:
        blocked_reason_counts.update(row["admission"]["blocked_reasons"])

    summary = {
        "stage": STAGE,
        "decision": "horizon_source_root_repair_projection_admission_complete",
        "claim_boundary": "Train-support transition rows only. No strict eval, source-heldout, or patch-effect repair proof emitted.",
        "admitted_train_support_rows": len(admitted),
        "blocked_projection_rows": len(blocked),
        "admitted_task_family_counts": dict(Counter(row["task_family"] for row in admitted)),
        "blocked_task_family_counts": dict(Counter(row["task_family"] for row in blocked)),
        "admitted_language_counts": dict(Counter(row["language_family"] for row in admitted)),
        "admitted_repo_family_counts": dict(Counter(row["repo_family_label"] for row in admitted)),
        "blocked_reason_counts": dict(blocked_reason_counts),
        "caps": {
            "MAX_ROWS_PER_CHAT": MAX_ROWS_PER_CHAT,
            "MAX_ROWS_PER_ROOT": MAX_ROWS_PER_ROOT,
            "MAX_ROWS_PER_TASK_FAMILY_PER_ROOT": MAX_ROWS_PER_TASK_FAMILY_PER_ROOT,
            "MAX_ROWS_PER_DEDUPE_CLUSTER": MAX_ROWS_PER_DEDUPE_CLUSTER,
        },
        "proof_counts": {
            "strict_eval_eligible": 0,
            "source_heldout_admissible": 0,
            "external_comparable_patch_trace_countable": 0,
            "external_fail_to_pass_countable": 0,
        },
        "next_stage": "stage12298_transition_training_package_candidate_from_12295_12297",
        "training_allowed": False,
        "raw_output_emitted": False,
    }
    (OUT / "horizon_source_root_repair_projection_admission_summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (OUT / "HORIZON_SOURCE_ROOT_REPAIR_AND_PROJECTION_ADMISSION_STAGE12297.md").write_text(
        "# Stage12297 Horizon Source-Root Repair And Projection Admission\n\n"
        + "This stage admits only safe train-support transition projections after source-root repair. "
        + "Patch/verifier temporal rows remain blocked until causal review.\n\n"
        + "```json\n"
        + json.dumps(summary, indent=2, sort_keys=True)
        + "\n```\n",
        encoding="utf-8",
    )
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
