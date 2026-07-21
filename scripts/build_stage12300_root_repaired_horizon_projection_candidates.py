#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12300_root_repaired_horizon_projection_candidates"
HORIZON = ROOT / "runs/local/artifacts/stage12271_horizon_slice_miner_pilot/horizon_slice_candidates.jsonl"
MANIFEST = ROOT / "runs/local/artifacts/stage12258_live_codex_chat_reconstruction_index/per_chat_manifest.jsonl"
OUT = ROOT / "runs/local/artifacts" / STAGE
SUMMARY = ROOT / "runs/summaries" / f"{STAGE}.json"

SELF_ROOTS = {"agentkernel-seq2seq-text-lab", "parameter-golf"}


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


def path_family(path: str | None) -> str:
    if not path:
        return "unknown"
    clean = path.rstrip("/")
    return clean.split("/")[-1] or "unknown"


def language_from_family(family: str, heads: dict[str, int]) -> str:
    head_keys = {str(k).split("/")[-1].lower() for k in heads}
    if {"cargo", "rustc"} & head_keys:
        return "rust"
    if {"npm", "npx", "pnpm", "yarn", "node", "tsc", "vitest"} & head_keys or family in {"bddy", "staticpeytonsite", "website"}:
        return "web_js_ts_html"
    if {"cmake", "make", "gcc", "g++", "cc", "ctest"} & head_keys:
        return "c_cpp"
    return "python"


def build_chat_roots() -> dict[tuple[str, str, str], dict]:
    roots = {}
    for row in iter_jsonl(MANIFEST) or []:
        cwd = None
        if row.get("workspace_root_hints_top"):
            cwd = row["workspace_root_hints_top"][0][0]
        elif row.get("cwd_hints_top"):
            cwd = row["cwd_hints_top"][0][0]
        family = path_family(cwd)
        key = (row.get("chat_id"), row.get("session_id_hint"), row.get("source_file_hash_compat"))
        roots[key] = {
            "root_status": "candidate_proven" if cwd else "missing_cwd_hint",
            "source_root_label_present": bool(cwd),
            "repo_family_label": family,
            "repo_family_digest": stable_id("repo_family", cwd or key),
            "cwd_hint_digest": stable_id("cwd_hint", cwd or key),
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


def block_reasons(row: dict, root: dict, task_family: str) -> list[str]:
    reasons = ["requires_projection_qc_and_semantic_causal_review"]
    if root.get("root_status") != "candidate_proven":
        reasons.append("source_root_not_repaired")
    if root.get("repo_kind") == "self_research_repo":
        reasons.append("self_research_root_dev_only")
    if task_family in {
        "transition_verifier_transition",
        "transition_continue_or_stop",
        "transition_patch_selection",
        "transition_evidence_role",
    }:
        reasons.append("causal_or_semantic_label_review_required")
    if task_family == "transition_state_update":
        reasons.append("state_update_label_placeholder_or_weak")
    if (row.get("verifier_linkage") or {}).get("status") == "temporal_only_needs_causal_review":
        reasons.append("temporal_patch_verifier_linkage_not_causal")
    return sorted(set(reasons))


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    roots = build_chat_roots()
    candidates = []
    unmatched = 0

    for row in iter_jsonl(HORIZON) or []:
        src = row.get("source_refs") or {}
        key = (src.get("chat_id"), src.get("session_id_hint"), src.get("source_file_hash_compat"))
        root = roots.get(
            key,
            {
                "root_status": "missing_manifest_match",
                "source_root_label_present": False,
                "repo_family_label": "unknown",
                "repo_family_digest": stable_id("repo_family", key),
                "cwd_hint_digest": stable_id("cwd_hint", key),
                "repo_kind": "unknown",
                "language_family": "unknown",
                "raw_cwd_path_emitted": False,
            },
        )
        if root.get("root_status") != "candidate_proven":
            unmatched += 1
        repaired_split = stable_id("split_group", src.get("chat_id"), root.get("repo_family_digest"), src.get("source_file_hash_compat"))
        repaired_root = stable_id("root_lineage", repaired_split, src.get("task_window_id"))
        for raw_family in row.get("allowed_projection_families", []):
            task_family = map_projection_family(raw_family)
            candidates.append(
                {
                    "schema_version": "root_repaired_horizon_projection_candidate_v1",
                    "stage": STAGE,
                    "row_id": stable_id("projection_candidate", row.get("horizon_slice_id"), task_family),
                    "source_horizon_slice_id": row.get("horizon_slice_id"),
                    "source_transition_id": (row.get("lineage") or {}).get("transition_id"),
                    "task_family": task_family,
                    "horizon_label": row.get("horizon_label"),
                    "original_lineage": row.get("lineage"),
                    "repaired_lineage": {
                        "repaired_split_group_id": repaired_split,
                        "repaired_root_lineage_key": repaired_root,
                        "repo_family_digest": root.get("repo_family_digest"),
                        "cwd_hint_digest": root.get("cwd_hint_digest"),
                    },
                    "root_recovery": root,
                    "source_refs": {
                        "chat_id": src.get("chat_id"),
                        "session_id_hint": src.get("session_id_hint"),
                        "snapshot_id": src.get("snapshot_id"),
                        "source_file_hash_compat": src.get("source_file_hash_compat"),
                        "task_window_id": src.get("task_window_id"),
                        "source_root_label_present": root.get("source_root_label_present", False),
                    },
                    "pre_action_fields": {
                        "state_before": row.get("state_before"),
                        "candidate_action_set": row.get("candidate_action_set"),
                    },
                    "target_or_post_action_fields": {
                        "chosen_action": row.get("chosen_action"),
                        "observation": row.get("observation"),
                        "state_update": row.get("state_update"),
                        "stop_continue": row.get("stop_continue"),
                        "verifier_linkage": row.get("verifier_linkage"),
                    },
                    "admission": {
                        "candidate_only": True,
                        "admitted": False,
                        "train_support_allowed": False,
                        "strict_eval_eligible": False,
                        "source_heldout_admissible": False,
                        "external_comparable_patch_trace_countable": False,
                        "external_fail_to_pass_countable": False,
                        "blocked_reasons": block_reasons(row, root, task_family),
                    },
                    "visibility_masks": row.get("visibility_masks"),
                    "guardrails": {
                        "raw_message_text_emitted": False,
                        "raw_tool_arguments_emitted": False,
                        "raw_tool_output_emitted": False,
                        "raw_patch_body_emitted": False,
                        "raw_source_path_emitted": False,
                        "raw_cwd_path_emitted": False,
                    },
                }
            )

    with (OUT / "root_repaired_horizon_projection_candidates.jsonl").open("w", encoding="utf-8") as handle:
        for candidate in candidates:
            handle.write(json.dumps(candidate, sort_keys=True) + "\n")

    blocked_reason_counts: Counter[str] = Counter()
    for candidate in candidates:
        blocked_reason_counts.update(candidate["admission"]["blocked_reasons"])

    summary = {
        "stage": STAGE,
        "decision": "root_repaired_horizon_projection_candidates_ready_training_blocked",
        "claim_boundary": "Root-repaired projection candidates only. No train rows admitted.",
        "projection_candidates": len(candidates),
        "unmatched_horizon_slices": unmatched,
        "task_family_counts": dict(Counter(c["task_family"] for c in candidates)),
        "horizon_counts": dict(Counter(c["horizon_label"] for c in candidates)),
        "repo_family_counts": dict(Counter(c["root_recovery"]["repo_family_label"] for c in candidates)),
        "repo_kind_counts": dict(Counter(c["root_recovery"]["repo_kind"] for c in candidates)),
        "language_counts": dict(Counter(c["root_recovery"]["language_family"] for c in candidates)),
        "blocked_reason_counts": dict(blocked_reason_counts),
        "admitted_rows": 0,
        "training_rows_emitted": 0,
        "strict_eval_rows": 0,
        "source_heldout_rows": 0,
        "external_comparable_patch_trace_rows": 0,
        "external_fail_to_pass_rows": 0,
        "next_stage": "stage12301_horizon_projection_semantic_qc",
        "training_allowed": False,
        "raw_output_emitted": False,
    }
    (OUT / "root_repaired_horizon_projection_candidates_summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (OUT / "ROOT_REPAIRED_HORIZON_PROJECTION_CANDIDATES_STAGE12300.md").write_text(
        "# Stage12300 Root-Repaired Horizon Projection Candidates\n\n"
        + "All candidates remain blocked until projection QC and semantic/causal review.\n\n"
        + "```json\n"
        + json.dumps(summary, indent=2, sort_keys=True)
        + "\n```\n",
        encoding="utf-8",
    )
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
