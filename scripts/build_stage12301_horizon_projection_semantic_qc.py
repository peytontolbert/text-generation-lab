#!/usr/bin/env python3
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12301_horizon_projection_semantic_qc"
INPUT = ROOT / "runs/local/artifacts/stage12300_root_repaired_horizon_projection_candidates/root_repaired_horizon_projection_candidates.jsonl"
OUT = ROOT / "runs/local/artifacts" / STAGE
SUMMARY = ROOT / "runs/summaries" / f"{STAGE}.json"

MAX_ROWS_PER_REPO = 20
MAX_ROWS_PER_LANGUAGE = 40
MAX_ROWS_PER_CHOSEN_ACTION = 30
PREFERRED_TASK = "transition_candidate_action_rank"


def iter_jsonl(path: Path):
    if not path.exists():
        return
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                yield json.loads(line)


def write_jsonl(path: Path, rows: list[dict]) -> int:
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")
    return len(rows)


def actions(row: dict) -> list[dict]:
    return ((row.get("pre_action_fields") or {}).get("candidate_action_set") or {}).get("actions") or []


def chosen_actions(row: dict) -> list[dict]:
    return [a for a in actions(row) if a.get("position_role") == "chosen"]


def action_types(row: dict) -> set[str]:
    return {a.get("action_type") or "unknown" for a in actions(row)}


def base_rejects(row: dict) -> list[str]:
    reasons = []
    root = row.get("root_recovery") or {}
    guard = row.get("guardrails") or {}
    cand = (row.get("pre_action_fields") or {}).get("candidate_action_set") or {}
    acts = actions(row)
    chosen = chosen_actions(row)
    if root.get("repo_kind") != "external_or_other_repo":
        reasons.append("not_external_root")
    if root.get("root_status") != "candidate_proven":
        reasons.append("source_root_not_repaired")
    if row.get("task_family") != PREFERRED_TASK:
        reasons.append("non_preferred_duplicate_or_unreviewed_task_family")
    if not cand.get("future_actions_masked"):
        reasons.append("future_actions_not_masked")
    if len(acts) < 2:
        reasons.append("singleton_or_missing_candidate_set")
    if len(action_types(row)) < 2:
        reasons.append("candidate_set_lacks_action_type_contrast")
    if len(chosen) != 1:
        reasons.append("chosen_action_not_unique")
    if (row.get("target_or_post_action_fields") or {}).get("observation", {}).get("model_visible_for_pre_action_projection"):
        reasons.append("observation_visible_before_action")
    for key in [
        "raw_message_text_emitted",
        "raw_tool_arguments_emitted",
        "raw_tool_output_emitted",
        "raw_patch_body_emitted",
        "raw_source_path_emitted",
        "raw_cwd_path_emitted",
    ]:
        if guard.get(key):
            reasons.append(key)
    return sorted(set(reasons))


def admitted_row(row: dict) -> dict:
    chosen = chosen_actions(row)[0]
    out = {
        "schema_version": "horizon_projection_semantic_qc_train_support_v1",
        "stage": STAGE,
        "row_id": row["row_id"].replace("projection_candidate", "semantic_qc_row"),
        "source_candidate_row_id": row["row_id"],
        "source_horizon_slice_id": row.get("source_horizon_slice_id"),
        "source_transition_id": row.get("source_transition_id"),
        "task_family": row.get("task_family"),
        "horizon_label": row.get("horizon_label"),
        "root_lineage_key": row.get("repaired_lineage", {}).get("repaired_root_lineage_key"),
        "split_group_id": row.get("repaired_lineage", {}).get("repaired_split_group_id"),
        "repo_family_label": row.get("root_recovery", {}).get("repo_family_label"),
        "repo_family_digest": row.get("root_recovery", {}).get("repo_family_digest"),
        "language_family": row.get("root_recovery", {}).get("language_family"),
        "pre_action_fields": {
            "state_before": (row.get("pre_action_fields") or {}).get("state_before"),
            "candidate_action_set": [
                {
                    "candidate_id": chr(ord("A") + idx),
                    "semantic_action": action.get("action_type"),
                    "command_head_digest": action.get("command_head") and f"command_head_hidden_{idx}",
                    "role": "chosen" if action.get("position_role") == "chosen" else "nearby_negative",
                }
                for idx, action in enumerate(actions(row)[:6])
            ],
        },
        "target_only": {
            "target_semantic_action": chosen.get("action_type"),
            "chosen_action_ref": chosen.get("action_id"),
            "observation": (row.get("target_or_post_action_fields") or {}).get("observation"),
        },
        "admission": {
            "train_support_allowed": True,
            "strict_eval_eligible": False,
            "source_heldout_admissible": False,
            "external_comparable_patch_trace_countable": False,
            "external_fail_to_pass_countable": False,
        },
        "qc": {
            "candidate_count": len(actions(row)),
            "distinct_action_type_count": len(action_types(row)),
            "duplicate_projection_family_collapsed": True,
            "semantic_qc_level": "ranked_action_contrast_train_support",
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
    return out


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    rows = list(iter_jsonl(INPUT) or [])
    admitted = []
    blocked = []
    seen_slices = set()
    repo_counts: Counter[str] = Counter()
    lang_counts: Counter[str] = Counter()
    action_counts: Counter[str] = Counter()

    # Prefer candidate-rank rows to avoid duplicating next-action and rank projections for one slice.
    rows.sort(key=lambda r: (0 if r.get("task_family") == PREFERRED_TASK else 1, r.get("source_horizon_slice_id") or ""))
    for row in rows:
        reasons = base_rejects(row)
        slice_id = row.get("source_horizon_slice_id")
        repo = row.get("root_recovery", {}).get("repo_family_label", "unknown")
        lang = row.get("root_recovery", {}).get("language_family", "unknown")
        chosen = chosen_actions(row)
        chosen_type = chosen[0].get("action_type") if len(chosen) == 1 else "unknown"
        if slice_id in seen_slices:
            reasons.append("duplicate_projection_for_horizon_slice")
        if repo_counts[repo] >= MAX_ROWS_PER_REPO:
            reasons.append("repo_cap_reached")
        if lang_counts[lang] >= MAX_ROWS_PER_LANGUAGE:
            reasons.append("language_cap_reached")
        if action_counts[chosen_type] >= MAX_ROWS_PER_CHOSEN_ACTION:
            reasons.append("chosen_action_cap_reached")
        if reasons:
            blocked.append(
                {
                    "row_id": row.get("row_id"),
                    "source_horizon_slice_id": slice_id,
                    "task_family": row.get("task_family"),
                    "repo_family_label": repo,
                    "language_family": lang,
                    "blocked_reasons": sorted(set(reasons)),
                }
            )
            continue
        out = admitted_row(row)
        admitted.append(out)
        seen_slices.add(slice_id)
        repo_counts[repo] += 1
        lang_counts[lang] += 1
        action_counts[chosen_type] += 1

    write_jsonl(OUT / "admitted_horizon_transition_rank_train_support_rows.jsonl", admitted)
    write_jsonl(OUT / "blocked_horizon_projection_semantic_qc_rows.jsonl", blocked)
    reason_counts: Counter[str] = Counter()
    for row in blocked:
        reason_counts.update(row["blocked_reasons"])
    summary = {
        "stage": STAGE,
        "decision": "horizon_projection_semantic_qc_complete",
        "claim_boundary": "Admitted rows are train-support action-ranking rows only; no eval or repair-proof claims.",
        "input_candidates": len(rows),
        "admitted_train_support_rows": len(admitted),
        "blocked_rows": len(blocked),
        "admitted_task_family_counts": dict(Counter(r["task_family"] for r in admitted)),
        "admitted_language_counts": dict(Counter(r["language_family"] for r in admitted)),
        "admitted_repo_family_counts": dict(Counter(r["repo_family_label"] for r in admitted)),
        "admitted_target_action_counts": dict(Counter(r["target_only"]["target_semantic_action"] for r in admitted)),
        "blocked_reason_counts": dict(reason_counts),
        "caps": {
            "MAX_ROWS_PER_REPO": MAX_ROWS_PER_REPO,
            "MAX_ROWS_PER_LANGUAGE": MAX_ROWS_PER_LANGUAGE,
            "MAX_ROWS_PER_CHOSEN_ACTION": MAX_ROWS_PER_CHOSEN_ACTION,
            "preferred_task_family": PREFERRED_TASK,
        },
        "proof_counts": {
            "strict_eval_eligible": 0,
            "source_heldout_admissible": 0,
            "external_comparable_patch_trace_countable": 0,
            "external_fail_to_pass_countable": 0,
        },
        "next_stage": "stage12302_transition_function_graph_training_candidate",
        "training_allowed": False,
        "raw_output_emitted": False,
    }
    (OUT / "horizon_projection_semantic_qc_summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (OUT / "HORIZON_PROJECTION_SEMANTIC_QC_STAGE12301.md").write_text(
        "# Stage12301 Horizon Projection Semantic QC\n\n"
        + "Admits only robust external candidate-action-rank support rows. No training request emitted.\n\n"
        + "```json\n"
        + json.dumps(summary, indent=2, sort_keys=True)
        + "\n```\n",
        encoding="utf-8",
    )
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
