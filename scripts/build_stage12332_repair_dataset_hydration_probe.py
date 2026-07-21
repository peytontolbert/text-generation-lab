#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12332_repair_dataset_hydration_probe"
OUT = ROOT / "runs/local/artifacts" / STAGE
SUMMARY = ROOT / "runs/summaries" / f"{STAGE}.json"


def exists(path: str) -> bool:
    return Path(path).exists()


def load(path: str) -> dict[str, Any]:
    p = Path(path)
    if not p.exists():
        return {}
    return json.loads(p.read_text(encoding="utf-8"))


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    stage12327 = load(str(ROOT / "runs/summaries/stage12327_external_adapter_preflight.json"))
    sources = [
        {
            "source_id": "repairthem_all_bears",
            "status": "candidate_qc_only",
            "local_bug_specs": True,
            "patches_available": "embedded_diff_hashes_only_in_stage12327; raw diff in source metadata",
            "commit_refs_available": True,
            "verifier_command_available": "Bears.py maven full-test command exists, but no raw before/after output materialized",
            "candidate_count": (stage12327.get("bears_inventory") or {}).get("failing_passing_candidates", 19),
            "blocked_reasons": [
                "benchmark_submodule_uninitialized_or_empty",
                "missing_authoritative_before_after_command_output",
                "missing_checkout_content_lineage",
                "requires_same_source_patch_verifier_causality_qc",
            ],
            "can_move_now": ["candidate", "materialized_if_checkout_hydrated", "qc_passed_if_logs_joined"],
            "cannot_move_now": ["train_support", "Level3", "patch_trace", "repair_claim", "sealed_eval"],
        },
        {
            "source_id": "repairthem_all_defects4j",
            "status": "blocked_before_qc",
            "local_bug_specs": exists("/arxiv/repositories/RepairThemAll/data/benchmarks/defects4j"),
            "patches_available": False,
            "commit_refs_available": "weak_bug_ids_only",
            "verifier_command_available": "Defects4J.py commands exist, but local logs/checkouts absent",
            "candidate_count": 395,
            "blocked_reasons": [
                "benchmark_submodule_uninitialized_or_empty",
                "missing_exact_buggy_fixed_refs",
                "missing_patch_lineage",
                "missing_before_after_defects4j_output",
                "legacy_runtime_guardrails_needed",
            ],
            "can_move_now": ["candidate_preflight_only"],
            "cannot_move_now": ["train_support", "Level3", "patch_trace", "repair_claim", "sealed_eval"],
        },
        {
            "source_id": "repairthem_all_quixbugs",
            "status": "blocked_before_qc",
            "local_bug_specs": "partial_only",
            "patches_available": False,
            "commit_refs_available": False,
            "verifier_command_available": "QuixBugs.py maven commands exist, but corpus/checkouts/logs absent",
            "candidate_count": 0,
            "blocked_reasons": [
                "benchmark_submodule_uninitialized_or_empty",
                "missing_java_programs_corpus",
                "missing_buggy_fixed_refs",
                "missing_patch_lineage",
                "missing_before_after_maven_output",
            ],
            "can_move_now": [],
            "cannot_move_now": ["candidate", "train_support", "Level3", "patch_trace", "repair_claim", "sealed_eval"],
        },
        {
            "source_id": "swe_bench_live_local",
            "status": "candidate_qc_only",
            "local_bug_specs": exists("/arxiv/root-cleanup/agentkernel_space_reclaimed_20260513/verified_leaderboard/prediction_tasks_agentkernel_swe_bench_live_verified_leaderboard.json"),
            "patches_available": exists("/arxiv/root-cleanup/agentkernel_space_reclaimed_20260513/verified_leaderboard/patches_agentkernel_swe_bench_live_verified_leaderboard"),
            "commit_refs_available": True,
            "verifier_command_available": "partial progress/checkpoint artifacts; top-level harness failed at drain_patch_jobs return -9",
            "candidate_count": 499,
            "patch_diff_candidates": 336,
            "patch_apply_validation_checkpoints": 255,
            "blocked_reasons": [
                "missing_normalized_verifier_command",
                "missing_pre_patch_failing_output",
                "missing_post_patch_passing_output",
                "missing_patch_apply_lineage",
                "top_level_harness_failed_return_minus_9",
                "patch_apply_validation_is_not_before_after_test_proof",
            ],
            "can_move_now": ["candidate", "materialized_if_patch_and_log_refs_joined", "qc_passed_if_verifier_artifacts_normalized"],
            "cannot_move_now": ["train_support", "Level3", "patch_trace", "repair_claim", "sealed_eval"],
        },
    ]
    probe = {
        "stage": STAGE,
        "decision": "repair_dataset_hydration_probe_ready_training_still_blocked",
        "training_allowed": False,
        "claim_boundary": "Control/probe artifact only. No repair dataset rows admitted. Bears and SWE-bench Live are viable next QC candidates; Defects4J/QuixBugs are blocked earlier.",
        "sources": sources,
        "recommended_order": [
            "Bears failing_passing checkout/content hydration attempt",
            "SWE-bench Live patch/log normalization attempt only after before/after verifier logs are found or regenerated",
            "Defects4J only after benchmark checkout/runtime is materialized",
            "QuixBugs only after full corpus/refs/logs exist",
        ],
        "minimum_to_admit_any_repair_row": [
            "same-source checkout/content lineage",
            "patch diff/apply proof or authoritative patch lineage",
            "exact verifier command",
            "pre-patch failing output class",
            "post-patch passing output class",
            "source/test/verifier hash refs",
            "anti-leak renderer pass",
            "repo-family cap pass",
        ],
    }
    (OUT / "repair_dataset_hydration_probe.json").write_text(json.dumps(probe, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (OUT / "REPAIR_DATASET_HYDRATION_PROBE_STAGE12332.md").write_text(
        "# Stage12332 Repair Dataset Hydration Probe\n\n"
        "Bears and SWE-bench Live are candidate/QC material. No repair rows are admitted until before/after verifier proof exists.\n",
        encoding="utf-8",
    )
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    SUMMARY.write_text(json.dumps(probe, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
