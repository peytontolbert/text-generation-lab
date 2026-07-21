#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12310_state_code_hydration_design"
OUT = ROOT / "runs/local/artifacts" / STAGE
SUMMARY = ROOT / "runs/summaries" / f"{STAGE}.json"


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    design = {
        "stage": STAGE,
        "decision": "state_code_hydration_design_ready_no_rows_admitted",
        "claim_boundary": "Design/control artifact only. It admits no rows and authorizes no training.",
        "training_allowed": False,
        "problem": "Stage12306/12308 candidates have refs and aggregate window metadata, but no explicit pre-action semantic state codes. Without state codes, semantic labels would be observed-action imitation.",
        "input_artifacts": {
            "task_windows": "runs/local/artifacts/stage12260_codex_chat_task_boundary_miner/codex_task_windows.jsonl",
            "horizon_slices": "runs/local/artifacts/stage12271_horizon_slice_miner_pilot/horizon_slice_candidates.jsonl",
            "transition_ledger": "runs/local/artifacts/stage12295_transition_function_ledger/transition_function_ledger.jsonl",
            "episode_candidates": "runs/local/artifacts/stage12306_session_episode_graph_candidate_materializer/stage12306_session_episode_graph_candidate_materializer.jsonl",
            "h1_feasibility": "runs/local/artifacts/stage12308_h1_semantic_rule_feasibility_audit/h1_semantic_rule_feasibility_records.jsonl",
        },
        "hydratable_state_codes_from_current_metadata": {
            "source_evidence_present": {
                "rule": "true when command_family_counts.read_or_search > 0 or paired_tool_call_count > 0 before the candidate transition",
                "confidence": "coarse_window_level",
                "claim_limit": "cannot prove exact evidence relevance",
            },
            "patch_exists": {
                "rule": "true when patch_pair_count > 0 before or inside the task window",
                "confidence": "coarse_window_level",
                "claim_limit": "cannot prove patch applies to current transition without ordered event join",
            },
            "verifier_selected": {
                "rule": "true when verifier_like_pair_count > 0 or command_family_counts.verifier_or_execution > 0",
                "confidence": "coarse_window_level",
                "claim_limit": "cannot prove selected verifier targets changed behavior",
            },
            "env_blocked": {
                "rule": "not reliably derivable from current metadata because raw output and failure class are hidden",
                "confidence": "not_hydratable_without_observation_classifier",
                "claim_limit": "must remain unknown unless a prior stage emits structured env/dependency failure class",
            },
        },
        "not_hydratable_without_new_joiner": {
            "failure_localized": "requires source/evidence role state or explicit localization event, not just command counts",
            "verifier_run_status": "requires structured command exit/failure/pass class, not output digest alone",
            "requirement_covered": "requires task requirement mapping and final verifier relation",
            "open_question": "requires state ledger or hypothesis tracking",
            "S0_to_S10_lifecycle_state": "requires ordered transition-local facts; current refs are insufficient",
        },
        "safe_derivation_policy": {
            "model_visible": [
                "boolean/coarse state codes",
                "candidate semantic action labels",
                "redacted refs and digests",
                "semantic_rule_id only after deterministic derivation",
            ],
            "target_only": [
                "chosen_action_ref",
                "observation_ref",
                "output_digest",
                "state_update_ref",
                "stop_continue label",
                "verifier linkage",
            ],
            "never_emit": [
                "raw tool output",
                "raw tool args",
                "raw source path",
                "raw patch body",
                "full command text",
                "chosen/gold/correct markers",
            ],
        },
        "stage12311_required_extractor": {
            "name": "stage12311_task_window_state_code_hydrator",
            "inputs": [
                "stage12260 task-window aggregate metadata",
                "stage12306 episode graph candidate refs",
                "stage12295 transition ledger coarse semantic families",
            ],
            "outputs": [
                "state_code_hydration_candidates.jsonl",
                "blocked_state_code_hydration_records.jsonl",
                "summary with yield by state code and task family",
            ],
            "fail_closed_rules": [
                "Do not assign exact TF-H1 semantic rule from coarse window metadata alone.",
                "Only emit coarse state codes with confidence labels unless transition-local ordered event proof exists.",
                "Do not use observed chosen action to infer state code.",
                "Do not infer verifier pass/fail from output digest or terminal task_complete.",
                "Do not admit train rows; emit candidates for semantic review only.",
            ],
        },
        "expected_yield": {
            "stage12306_episode_candidates": "coarse source_evidence_present/patch_exists/verifier_selected may be derivable for some rows",
            "stage12308_h1_items": "still zero deterministic TF-H1 labels until state refs are hydrated with transition-local facts",
            "level_3_plus": 0,
            "training_rows": 0,
        },
    }
    (OUT / "state_code_hydration_design.json").write_text(json.dumps(design, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (OUT / "STATE_CODE_HYDRATION_DESIGN_STAGE12310.md").write_text(
        "# Stage12310 State Code Hydration Design\n\n"
        "No rows are admitted. This stage defines how to hydrate explicit pre-action state codes without raw content leakage.\n\n"
        "## Decision\n\n"
        f"`{design['decision']}`\n\n"
        "## Next\n\n"
        "`stage12311_task_window_state_code_hydrator`\n",
        encoding="utf-8",
    )
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    SUMMARY.write_text(json.dumps(design, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
