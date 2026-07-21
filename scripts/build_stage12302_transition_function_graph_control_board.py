#!/usr/bin/env python3
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12302_transition_function_graph_control_board"
OUT = ROOT / "runs/local/artifacts" / STAGE
SUMMARY = ROOT / "runs/summaries" / f"{STAGE}.json"

S12295 = ROOT / "runs/summaries/stage12295_transition_function_ledger.json"
S12300 = ROOT / "runs/summaries/stage12300_root_repaired_horizon_projection_candidates.json"
S12301 = ROOT / "runs/summaries/stage12301_horizon_projection_semantic_qc.json"
R12301 = (
    ROOT
    / "runs/local/artifacts/stage12301_horizon_projection_semantic_qc/"
    / "admitted_horizon_transition_rank_train_support_rows.jsonl"
)

RAW_TOOL_ACTIONS = {"inspect", "read", "search", "run", "verify", "patch", "edit", "other"}


def read_json(path: Path) -> dict:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def iter_jsonl(path: Path):
    if not path.exists():
        return
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                yield json.loads(line)


def row_target_action(row: dict) -> str:
    return ((row.get("target_only") or {}).get("target_semantic_action") or "").lower()


def candidate_actions(row: dict) -> list[dict]:
    return ((row.get("pre_action_fields") or {}).get("candidate_action_set") or [])


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)

    stage12295 = read_json(S12295)
    stage12300 = read_json(S12300)
    stage12301 = read_json(S12301)
    rows12301 = list(iter_jsonl(R12301) or [])

    raw_target_actions = Counter(row_target_action(r) for r in rows12301)
    raw_candidate_actions = Counter()
    model_visible_role_markers = Counter()
    missing_train_contract = 0
    for row in rows12301:
        candidates = candidate_actions(row)
        if not candidates:
            missing_train_contract += 1
        for candidate in candidates:
            action = (candidate.get("semantic_action") or "").lower()
            if action:
                raw_candidate_actions[action] += 1
            role = (candidate.get("role") or "").lower()
            if role in {"chosen", "correct", "gold", "target", "answer"}:
                model_visible_role_markers[role] += 1

    stage12301_training_blockers = []
    if rows12301:
        if any(action in RAW_TOOL_ACTIONS for action in raw_target_actions):
            stage12301_training_blockers.append("target_uses_raw_tool_action_not_maintainer_semantic_action")
        if any(action in RAW_TOOL_ACTIONS for action in raw_candidate_actions):
            stage12301_training_blockers.append("candidate_uses_raw_tool_action_not_maintainer_semantic_action")
        if model_visible_role_markers:
            stage12301_training_blockers.append("model_visible_candidate_role_marks_chosen_or_gold")
        if missing_train_contract:
            stage12301_training_blockers.append("missing_candidate_action_set_contract")
        stage12301_training_blockers.append("missing_deterministic_semantic_qc_rule_id")
        stage12301_training_blockers.append("missing_transition_function_key_dedup_contract")

    corrected_decision = (
        "stage12301_candidate_only_semantic_reconstruction_required"
        if stage12301_training_blockers
        else "stage12301_train_support_ready_pending_distribution_floor"
    )

    summary = {
        "stage": STAGE,
        "decision": corrected_decision,
        "claim_boundary": (
            "The transition-function graph is useful as a candidate ledger, but no new training "
            "request should be emitted until raw tool actions are reconstructed into deterministic "
            "maintainer semantic labels and candidate-role leakage is removed from model-visible input."
        ),
        "graph_state": {
            "stage12295_transition_ledger_records": stage12295.get("ledger_records"),
            "stage12295_decision": stage12295.get("decision"),
            "stage12300_root_repaired_projection_candidates": stage12300.get("projection_candidates"),
            "stage12300_training_rows_emitted": stage12300.get("training_rows_emitted"),
            "stage12300_decision": stage12300.get("decision"),
            "stage12301_previous_admitted_rows": stage12301.get("admitted_train_support_rows"),
            "stage12301_previous_decision": stage12301.get("decision"),
        },
        "stage12301_schema_audit": {
            "rows_inspected": len(rows12301),
            "raw_target_action_counts": dict(raw_target_actions),
            "raw_candidate_action_counts": dict(raw_candidate_actions),
            "model_visible_role_marker_counts": dict(model_visible_role_markers),
            "missing_candidate_action_set_contract_rows": missing_train_contract,
            "training_blockers": stage12301_training_blockers,
        },
        "corrected_admission": {
            "stage12301_rows_train_support_allowed": 0 if stage12301_training_blockers else len(rows12301),
            "stage12301_rows_candidate_only": len(rows12301) if stage12301_training_blockers else 0,
            "training_allowed": False,
            "strict_eval_eligible": 0,
            "source_heldout_admissible": 0,
            "external_patch_trace_countable": 0,
            "external_fail_to_pass_countable": 0,
        },
        "semantic_action_vocabulary_required": [
            "RETRIEVE_EVIDENCE",
            "LOCALIZE_FAILURE",
            "PLAN_PATCH",
            "APPLY_PATCH",
            "SELECT_TEST",
            "RUN_VERIFIER",
            "INTERPRET_VERIFIER",
            "REPAIR_AFTER_FAILURE",
            "ROLLBACK_OR_ABSTAIN",
            "FINISH",
        ],
        "next_required_stage": {
            "stage": "stage12303_semantic_transition_function_reconstruction",
            "must_do": [
                "Reconstruct candidates from pre-action state only.",
                "Remove chosen/gold role markers from model-visible candidate records.",
                "Map raw tool actions into maintainer semantic actions using deterministic rule IDs.",
                "Emit transition_function_key for dedupe and split isolation.",
                "Keep post-action observation, chosen action ref, output digest, and state update target-only.",
                "Admit no rows without at least three semantic candidates and two hard negatives.",
            ],
            "minimum_training_floor_after_reconstruction": {
                "rows": 120,
                "unique_roots": 30,
                "external_repo_fraction_min": 0.70,
                "max_repo_family_fraction": 0.15,
                "required_task_families": [
                    "transition_next_action",
                    "transition_candidate_action_rank",
                    "transition_verifier_transition",
                    "transition_continue_or_stop",
                ],
            },
        },
        "plateau_risk": [
            "Scaling H1 raw action imitation will teach localization/tool priors instead of maintainer transition functions.",
            "Using candidate-role markers or raw chosen action IDs lets the model learn artifact shortcuts.",
            "Training before verifier/continue/patch-selection semantic review repeats the bounded-classification plateau.",
            "Self-research-root dominance would make the model learn this lab's workflow rather than multilingual maintainer behavior.",
        ],
    }

    (OUT / "transition_function_graph_control_board.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (OUT / "TRANSITION_FUNCTION_GRAPH_CONTROL_BOARD_STAGE12302.md").write_text(
        "# Stage12302 Transition Function Graph Control Board\n\n"
        "Stage12301 is corrected to candidate-only pending semantic reconstruction.\n\n"
        "## Decision\n\n"
        f"`{summary['decision']}`\n\n"
        "## Current Graph\n\n"
        f"- Stage12295 transition ledger records: {summary['graph_state']['stage12295_transition_ledger_records']}\n"
        f"- Stage12300 root-repaired projection candidates: {summary['graph_state']['stage12300_root_repaired_projection_candidates']}\n"
        f"- Stage12301 previous admitted rows now treated as candidate-only: "
        f"{summary['corrected_admission']['stage12301_rows_candidate_only']}\n\n"
        "## Training Blockers\n\n"
        + "\n".join(f"- {item}" for item in stage12301_training_blockers)
        + "\n\n## Next Stage\n\n"
        "Build `stage12303_semantic_transition_function_reconstruction` before any training request.\n",
        encoding="utf-8",
    )
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
