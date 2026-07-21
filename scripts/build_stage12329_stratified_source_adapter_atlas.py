#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12329_stratified_source_adapter_atlas"
OUT = ROOT / "runs/local/artifacts" / STAGE
SUMMARY = ROOT / "runs/summaries" / f"{STAGE}.json"


def load(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def exists(path: str) -> bool:
    return Path(path).exists()


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    ledger = load(ROOT / "runs/summaries/stage12324_combined_train_support_ledger.json")
    preflight = load(ROOT / "runs/summaries/stage12327_external_adapter_preflight.json")
    qc_request = load(ROOT / "runs/summaries/stage12328_external_adapter_qc_materialization_request.json")

    adapters = [
        {
            "adapter_id": "codex_chat_episode_graphs",
            "primary_paths": [
                "runs/local/artifacts/stage12260_codex_chat_task_boundary_miner",
                "runs/local/artifacts/stage12306_session_episode_graph_candidate_materializer",
                "runs/local/artifacts/stage12316_transition_local_event_joiner",
                "runs/local/artifacts/stage12320_event_local_semantic_review_admission",
            ],
            "current_status": "Some event-local train-support admitted; Level-3 still blocked by state/action/observation/state_delta gaps.",
            "can_move": ["train_support_observation_status", "transition_function_coverage"],
            "cannot_move_yet": ["Level3", "patch_trace", "repair_claim", "sealed_eval"],
            "first_batch_cap": 75,
            "hard_gate": "No observed-action imitation as next-action policy; require safe state codes and semantic rule IDs.",
        },
        {
            "adapter_id": "selected_test_roots",
            "primary_paths": [
                "runs/local/artifacts/stage12322_priority_rust_cpp_selected_test_admission",
                "runs/local/artifacts/stage12326_direct_python_selected_test_admission",
                "runs/local/artifacts/stage12307_rust_cpp_selected_test_root_candidate_queue",
            ],
            "current_status": "45 selected-test train-support rows admitted across Python/Rust/C++; web still thin.",
            "can_move": ["train_support_selected_test", "verifier_transition_support"],
            "cannot_move_yet": ["repair_claim", "Level3"],
            "first_batch_cap": 75,
            "hard_gate": "Every row needs selected-test/verifier refs, non-singleton opaque options, deterministic shuffle, no target value leak.",
        },
        {
            "adapter_id": "open_swe_traces",
            "primary_paths": [
                "runs/local/artifacts/stage12327_external_adapter_preflight/open_swe_priority_capped_trace_support_candidates.jsonl",
                "runs/local/artifacts/stage12327_external_adapter_preflight/open_swe_trace_support_candidates.jsonl",
            ],
            "current_status": "50 priority capped Python trace-support candidates plus 250 broad inventory candidates; zero admitted.",
            "can_move": ["trace_support_train_support_after_qc"],
            "cannot_move_yet": ["repair_claim", "external_fail_to_pass_floor", "sealed_eval"],
            "first_batch_cap": 50,
            "hard_gate": "Resolved/model_patch is priority signal only; recover safe semantic transition records and same-source verifier causality before admission.",
        },
        {
            "adapter_id": "repairthem_all_bears",
            "primary_paths": [
                "runs/local/artifacts/stage12327_external_adapter_preflight/bears_failing_passing_candidates.jsonl",
                "/arxiv/repositories/RepairThemAll/data/benchmarks/bears/bugs.json",
            ],
            "current_status": "19 failing_passing metadata candidates; 232 passing_passing blocked; zero admitted.",
            "can_move": ["external_repair_candidate_after_hydration", "java_patch_trace_after_verifier_qc"],
            "cannot_move_yet": ["train_support", "repair_claim", "Level3"],
            "first_batch_cap": 19,
            "hard_gate": "Need local or authoritative checkout/content plus before/after command output; passing_passing never counts as repair proof.",
        },
        {
            "adapter_id": "repairthem_all_defects4j_quixbugs",
            "primary_paths": [
                "/arxiv/repositories/RepairThemAll/data/benchmarks/defects4j",
                "/arxiv/repositories/RepairThemAll/data/benchmarks/QuixBugs",
            ],
            "current_status": "Local metadata/scripts exist; not yet profiled into current spine counters.",
            "can_move": ["external_repair_candidate_preflight", "java_patch_trace_after_verifier_qc"],
            "cannot_move_yet": ["train_support_without_checkout_verifier_qc"],
            "first_batch_cap": 50,
            "hard_gate": "Do not admit metadata-only bug IDs; require exact buggy/fixed refs, test command/output, and patch lineage.",
        },
        {
            "adapter_id": "swe_bench_live_local",
            "primary_paths": [
                "/arxiv/repositories/SWE-bench-Live",
                "/arxiv/root-cleanup/agentkernel_space_reclaimed_20260513/verified_leaderboard",
            ],
            "current_status": "Local repository/artifact traces exist; not yet normalized into Stage12328-style QC.",
            "can_move": ["source_heldout_candidate", "patch_trace_candidate_after_lineage_qc"],
            "cannot_move_yet": ["train_support_without_instance_materialization"],
            "first_batch_cap": 50,
            "hard_gate": "Need instance spec, patch diff, verifier command/output, and train/eval lineage separation.",
        },
        {
            "adapter_id": "strict_long_context_traces",
            "primary_paths": [
                "runs/local/artifacts/strict_long_context_train_ready_plus_audit_v1",
                "runs/local/artifacts/strict_long_context_retrieval_mixture_v1",
                "runs/local/artifacts/strict_long_context_step_judgment_datasets_v1",
            ],
            "current_status": "Good refinery material; must remain source adapter, not raw transcript imitation.",
            "can_move": ["retrieval_evidence_support", "state_summary_support", "transition_support_after_event_join"],
            "cannot_move_yet": ["repair_claim_without_patch_verifier_trace"],
            "first_batch_cap": 75,
            "hard_gate": "Compile to typed state/action/verifier records; no raw long-context continuation targets as maintainer proof.",
        },
    ]
    for adapter in adapters:
        adapter["path_status"] = {path: exists(path) for path in adapter["primary_paths"]}

    current = int(ledger.get("admitted_train_support_count") or ledger.get("train_support_count") or 136)
    atlas = {
        "stage": STAGE,
        "decision": "stratified_source_adapter_atlas_ready_training_still_blocked",
        "training_allowed": False,
        "claim_boundary": "Control/atlas artifact only. It prevents Open-SWE localization and defines capped multi-source routes toward 500 high-quality train-support tasks.",
        "current_ledger": {
            "admitted_train_support": current,
            "remaining_to_500": 500 - current,
            "source_counts": ledger.get("source_counts", {}),
            "language_counts": ledger.get("language_counts", {}),
            "stage12327_open_swe_priority": (preflight.get("open_swe_import_artifact") or {}).get("priority_capped_candidates", 0),
            "stage12327_bears_failing_passing": (preflight.get("bears_inventory") or {}).get("failing_passing_candidates", 0),
            "stage12328_training_allowed": qc_request.get("training_allowed"),
        },
        "adapters": adapters,
        "cap_policy": {
            "total_admitted_train_support_target": 500,
            "candidate_rows": "track separately; never count toward 500",
            "qc_passed_rows": "track separately; train-support only after explicit admission gate",
            "any_source_adapter_or_lane_train_support_cap": 125,
            "any_source_adapter_or_lane_new_addition_cap": 75,
            "any_repo_family_train_support_cap": 25,
            "first_external_batch_repo_cap": "10 rows or 20%, whichever is stricter",
            "any_language_family_cap": 150,
            "python_cap": 140,
            "session_unknown_language_cap": 100,
            "any_task_family_cap": 110,
            "event_local_observation_status_cap": 100,
            "external_trace_adapter_cap_until_two_adapters_pass_qc": 100,
            "selected_test_roots_cap": 175,
            "per_selected_test_root_cap": 5,
            "open_swe_train_support_cap_until_second_source_validation": 50,
            "bears_repair_admitted_current_cap": 0,
            "counter_separation": [
                "candidate",
                "materialized",
                "qc_passed",
                "train_support_admitted",
                "Level3_admitted",
                "patch_trace_admitted",
                "repair_claim_admitted",
                "sealed_eval_admitted",
            ],
        },
        "near_term_allocation": {
            "selected_test_roots": 75,
            "codex_chat_episode_graphs": 50,
            "open_swe_traces": 50,
            "strict_long_context_traces": 50,
            "repair_datasets": "candidate/QC only until verifier hydration passes",
            "web_specific_roots": "must be prioritized because current selected-test supply is Python/Rust/C++ heavy",
        },
        "hard_reject_rules": [
            "Reject any row counted in more than one of candidate, QC-passed, train-support, Level-3, repair, sealed-eval.",
            "Reject candidate/review rows as train-support until explicit admission stage passes.",
            "Reject raw observed-action imitation as next-action policy.",
            "Reject rows with model-visible chosen/gold/correct/target role markers.",
            "Reject event-local observation/status rows as Level-3, repair, strict-eval, or source-heldout.",
            "Reject external adapter rows without same-source event ordering, source/test hashes, verifier identity class, and anti-leak rendering.",
            "Reject Bears passing_passing as repair proof; reject Bears failing_passing unless command output, checkout lineage, patch diff/apply proof, and before/after verifier classes are materialized.",
            "Reject Open-SWE rows that expose raw trajectory/verifier text or treat resolved/patch-test co-presence as fail-to-pass proof.",
            "Reject any admission that exceeds repo, language, adapter, source-lane, or task-family caps.",
        ],
        "plateau_risks": [
            "Open-SWE sorted-order scanning over-centers one trace family/language.",
            "Counting metadata candidates as training rows.",
            "Counting PASS_TO_PASS or passing_passing as repair proof.",
            "Using observed action telemetry as next-action policy.",
            "Letting session_unknown_language dominate the 500-task target.",
            "Training before Level-3/state-delta fields exist.",
        ],
        "recommended_next_stages": [
            {
                "stage": "stage12330_selected_test_and_language_balance_queue",
                "purpose": "Recover language-family attribution and select enough Rust/C++/Web selected-test roots to meet floors.",
            },
            {
                "stage": "stage12331_open_swe_priority_safe_transition_extractor",
                "purpose": "Convert the 50 priority Open-SWE candidates into safe semantic transition review records, not train rows.",
            },
            {
                "stage": "stage12332_repair_dataset_hydration_probe",
                "purpose": "Attempt Bears/Defects4J/SWE-bench local hydration with explicit before/after verifier output requirements.",
            },
        ],
    }

    (OUT / "stratified_source_adapter_atlas.json").write_text(json.dumps(atlas, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (OUT / "STRATIFIED_SOURCE_ADAPTER_ATLAS_STAGE12329.md").write_text(
        "# Stage12329 Stratified Source Adapter Atlas\n\n"
        "This control artifact makes Open-SWE one capped source lane among several and keeps repair datasets out of train-support counters until verifier QC passes.\n",
        encoding="utf-8",
    )
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    SUMMARY.write_text(json.dumps(atlas, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
