#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12303_semantic_transition_function_reconstruction"
INPUT = ROOT / "runs/local/artifacts/stage12300_root_repaired_horizon_projection_candidates/root_repaired_horizon_projection_candidates.jsonl"
OUT = ROOT / "runs/local/artifacts" / STAGE
SUMMARY = ROOT / "runs/summaries" / f"{STAGE}.json"

TARGET_TASKS = {"transition_next_action", "transition_candidate_action_rank"}
SELF_RESEARCH_REPOS = {"agentkernel-seq2seq-text-lab", "parameter-golf"}
RAW_TO_SEMANTIC_OPTIONS = {
    "inspect": ["RETRIEVE_EVIDENCE", "LOCALIZE_FAILURE"],
    "read": ["RETRIEVE_EVIDENCE", "LOCALIZE_FAILURE"],
    "search": ["RETRIEVE_EVIDENCE", "LOCALIZE_FAILURE"],
    "run": ["RUN_VERIFIER", "SELECT_TEST", "INTERPRET_VERIFIER"],
    "verify": ["RUN_VERIFIER", "SELECT_TEST", "INTERPRET_VERIFIER"],
    "patch": ["PLAN_PATCH", "APPLY_PATCH", "REPAIR_AFTER_FAILURE"],
    "edit": ["PLAN_PATCH", "APPLY_PATCH", "REPAIR_AFTER_FAILURE"],
    "other": ["RETRIEVE_EVIDENCE", "ROLLBACK_OR_ABSTAIN", "FINISH"],
}


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


def stable_digest(payload: object, prefix: str) -> str:
    text = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return f"{prefix}_{hashlib.sha1(text.encode('utf-8')).hexdigest()[:20]}"


def actions(row: dict) -> list[dict]:
    return ((row.get("pre_action_fields") or {}).get("candidate_action_set") or {}).get("actions") or []


def chosen_actions(row: dict) -> list[dict]:
    return [a for a in actions(row) if a.get("position_role") == "chosen"]


def action_type_counts(rows: list[dict]) -> Counter[str]:
    counts: Counter[str] = Counter()
    for row in rows:
        for action in actions(row):
            counts[action.get("action_type") or "unknown"] += 1
    return counts


def is_external_target(row: dict) -> bool:
    root = row.get("root_recovery") or {}
    repo = root.get("repo_family_label")
    return (
        row.get("task_family") in TARGET_TASKS
        and row.get("horizon_label") == "H1_next_action"
        and root.get("repo_kind") == "external_or_other_repo"
        and root.get("root_status") == "candidate_proven"
        and bool(root.get("source_root_label_present"))
        and repo not in SELF_RESEARCH_REPOS
    )


def make_work_item(transition_id: str, rows: list[dict]) -> dict:
    rows = sorted(rows, key=lambda r: r.get("task_family") or "")
    primary = next((r for r in rows if r.get("task_family") == "transition_candidate_action_rank"), rows[0])
    root = primary.get("root_recovery") or {}
    lineage = primary.get("repaired_lineage") or {}
    all_actions = actions(primary)
    chosen = chosen_actions(primary)
    raw_chosen = chosen[0].get("action_type") if len(chosen) == 1 else "ambiguous"
    raw_action_types = sorted({a.get("action_type") or "unknown" for a in all_actions})
    semantic_option_space = sorted(
        {
            semantic
            for raw in raw_action_types
            for semantic in RAW_TO_SEMANTIC_OPTIONS.get(raw, ["RETRIEVE_EVIDENCE"])
        }
    )
    function_key_payload = {
        "repo_family_digest": root.get("repo_family_digest"),
        "candidate_raw_action_types": raw_action_types,
        "horizon_label": primary.get("horizon_label"),
        "task_window_id": (primary.get("source_refs") or {}).get("task_window_id"),
    }
    reject_reasons = []
    if len(all_actions) < 3:
        reject_reasons.append("candidate_count_below_semantic_training_floor")
    if len(raw_action_types) < 2:
        reject_reasons.append("candidate_action_types_lack_contrast")
    if len(chosen) != 1:
        reject_reasons.append("chosen_action_not_unique")
    if ((primary.get("target_or_post_action_fields") or {}).get("state_update") or {}).get("safe_update_label") == "needs_semantic_review":
        reject_reasons.append("state_update_requires_semantic_review")

    return {
        "schema_version": "semantic_transition_reconstruction_work_item_v1",
        "stage": STAGE,
        "work_item_id": stable_digest({"transition_id": transition_id, "rows": [r.get("row_id") for r in rows]}, "semantic_work"),
        "source_transition_id": transition_id,
        "source_horizon_slice_id": primary.get("source_horizon_slice_id"),
        "source_candidate_row_ids": [r.get("row_id") for r in rows],
        "source_task_families": sorted({r.get("task_family") for r in rows}),
        "repo_family_label": root.get("repo_family_label"),
        "repo_family_digest": root.get("repo_family_digest"),
        "language_family": root.get("language_family"),
        "root_lineage_key": lineage.get("repaired_root_lineage_key"),
        "split_group_id": lineage.get("repaired_split_group_id"),
        "task_window_id_digest": stable_digest((primary.get("source_refs") or {}).get("task_window_id"), "task_window"),
        "pre_action_refs": {
            "state_before_ref": ((primary.get("pre_action_fields") or {}).get("state_before") or {}).get("state_before_ref"),
            "previous_action_ref": ((primary.get("pre_action_fields") or {}).get("state_before") or {}).get("previous_action_ref"),
            "raw_content_emitted": False,
        },
        "candidate_set_audit": {
            "candidate_count": len(all_actions),
            "raw_action_type_counts": dict(action_type_counts([primary])),
            "raw_chosen_action_type": raw_chosen,
            "future_actions_masked": ((primary.get("pre_action_fields") or {}).get("candidate_action_set") or {}).get("future_actions_masked"),
            "raw_identifiers_are_target_only": False,
        },
        "semantic_reconstruction_needed": {
            "semantic_option_space": semantic_option_space,
            "required_state_codes": [
                "source_evidence_present",
                "failure_localized",
                "patch_exists",
                "verifier_selected",
                "verifier_run_status",
                "requirement_covered",
                "env_blocked",
                "open_question",
            ],
            "required_rule_id": "pending_semantic_rule_assignment",
            "required_hard_negative_reason_codes": True,
            "required_transition_function_key": stable_digest(function_key_payload, "transition_function_pending"),
        },
        "target_only_refs": {
            "observation_ref": (((primary.get("target_or_post_action_fields") or {}).get("observation") or {}).get("observation_ref")),
            "state_update_ref": (((primary.get("target_or_post_action_fields") or {}).get("state_update") or {}).get("state_update_ref")),
            "chosen_action_ref_visible_to_model": False,
        },
        "admission": {
            "candidate_only": True,
            "train_support_allowed": False,
            "strict_eval_eligible": False,
            "source_heldout_admissible": False,
        },
        "reject_reasons_until_reconstructed": sorted(set(reject_reasons + [
            "raw_tool_action_label_requires_semantic_mapping",
            "observed_action_imitation_must_be_removed",
            "deterministic_semantic_qc_rule_missing",
        ])),
    }


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    rows = list(iter_jsonl(INPUT) or [])
    target_rows = [r for r in rows if is_external_target(r)]
    by_transition: dict[str, list[dict]] = defaultdict(list)
    for row in target_rows:
        by_transition[row.get("source_transition_id") or row.get("row_id")].append(row)

    work_items = [make_work_item(tid, grouped) for tid, grouped in sorted(by_transition.items())]
    blocked_reason_counts: Counter[str] = Counter()
    for item in work_items:
        blocked_reason_counts.update(item["reject_reasons_until_reconstructed"])

    write_jsonl(OUT / "semantic_transition_reconstruction_work_items.jsonl", work_items)

    summary = {
        "stage": STAGE,
        "decision": "semantic_reconstruction_worklist_ready_no_training_rows",
        "input_projection_candidates": len(rows),
        "external_h1_target_rows": len(target_rows),
        "reconstruction_work_items": len(work_items),
        "training_rows_emitted": 0,
        "training_allowed": False,
        "work_item_language_counts": dict(Counter(i["language_family"] for i in work_items)),
        "work_item_repo_family_counts": dict(Counter(i["repo_family_label"] for i in work_items)),
        "work_item_raw_chosen_action_counts": dict(Counter(i["candidate_set_audit"]["raw_chosen_action_type"] for i in work_items)),
        "blocked_reason_counts": dict(blocked_reason_counts),
        "next_stage": "stage12304_semantic_rule_assignment_and_candidate_rewrite",
        "claim_boundary": "Work items are review targets only. They are not training rows and cannot be used for eval claims.",
    }
    (OUT / "semantic_transition_reconstruction_summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (OUT / "SEMANTIC_TRANSITION_FUNCTION_RECONSTRUCTION_STAGE12303.md").write_text(
        "# Stage12303 Semantic Transition Function Reconstruction\n\n"
        "Builds a review worklist from external H1 transition candidates. No training rows emitted.\n\n"
        "```json\n"
        + json.dumps(summary, indent=2, sort_keys=True)
        + "\n```\n",
        encoding="utf-8",
    )
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
