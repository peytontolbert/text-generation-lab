#!/usr/bin/env python3
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12290_replay_queue_repair_or_retarget_decision"
OUT = ROOT / "runs/local/artifacts" / STAGE
SUMMARY = ROOT / "runs/summaries" / f"{STAGE}.json"

SMOKE_SUMMARIES = [
    ROOT / "runs/summaries/stage12286_external_repair_replay_smoke_executor.json",
    ROOT / "runs/summaries/stage12288_external_repair_replay_second_smoke_executor.json",
]
AFTER_SUMMARY = ROOT / "runs/summaries/stage12289_replay_failure_after_phase_diagnostic.json"


def read_json(path: Path) -> dict:
    if not path.exists():
        return {"missing": True, "path": str(path)}
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    smoke = [read_json(path) for path in SMOKE_SUMMARIES]
    after = read_json(AFTER_SUMMARY)

    targets_attempted = sum(int(s.get("targets_attempted", 0)) for s in smoke)
    pe2_candidates = sum(int(s.get("PE2_candidates", 0)) for s in smoke)
    external_comparable = sum(int(s.get("external_comparable_patch_trace_rows", 0)) for s in smoke)
    external_fail_to_pass = sum(int(s.get("external_fail_to_pass_rows", 0)) for s in smoke)
    reject_counts: Counter[str] = Counter()
    for s in smoke:
        reject_counts.update(s.get("reject_counts", {}))

    after_counts = after.get("after_status_counts", {})
    after_passed = after.get("targets_where_after_passed", [])
    after_failed = after.get("targets_where_after_failed_or_timeout", [])

    decision = "block_stage12244_replay_queue_for_patch_effect_training"
    blockers = []
    if targets_attempted == 0:
        blockers.append("no_smoke_targets_attempted")
    if pe2_candidates == 0:
        blockers.append("zero_PE2_candidates_across_smoke_batches")
    if external_comparable == 0:
        blockers.append("zero_external_comparable_patch_trace_rows")
    if external_fail_to_pass == 0:
        blockers.append("zero_external_FAIL_TO_PASS_rows")
    if after_passed:
        blockers.append("some_after_commits_pass_executor_patch_apply_may_need_repair")
    if after_failed:
        blockers.append("patched_fail_targets_also_fail_at_commit_after_target_verifier_not_locally_replayable")

    root_cause = (
        "Stage12244 is not currently a dependable patch-effect-proof source under local replay. "
        "The smoke executors found no before FAIL -> before+patch PASS targets, and Stage12289 "
        "showed every patched-fail smoke target also fails at commit_after. That falsifies the "
        "assumption that these target/verifier pairs prove patch effect in this environment."
    )

    deterministic_checks_to_add = [
        "preflight_commit_after_must_pass_exact_verifier_before_smoke",
        "require_before_fail_and_after_pass_before_attempting_before_plus_patch",
        "require_same_verifier_identity_for_before_after_and_before_plus_patch",
        "reject_targets_where_commit_after_fails_or_times_out",
        "record_environment_failure_separately_from_software_failure",
        "do_not_count_metadata_commit_pairs_as_patch_effect_without_command_output",
    ]

    retarget_plan = [
        {
            "lane": "external_repair_commit_pairs_v2",
            "requirement": "build targets from sources where exact selected verifier is known to fail before and pass after",
            "first_stage": "stage12291_commit_pair_after_pass_prefilter",
        },
        {
            "lane": "benchmark_patch_tasks_with_reference_tests",
            "requirement": "prefer task corpora with explicit failing tests and reference patches over inferred commit-pair selectors",
            "first_stage": "stage12292_patch_task_source_atlas",
        },
        {
            "lane": "codex_chat_horizon_training",
            "requirement": "mine next-action/verifier/continue-stop rows from causal turns, but do not count them as repair proof",
            "first_stage": "stage12293_horizon_projection_without_repair_claims",
        },
    ]

    summary = {
        "stage": STAGE,
        "decision": decision,
        "training_allowed": False,
        "admitted_rows": 0,
        "training_rows_emitted": 0,
        "targets_attempted_across_smoke": targets_attempted,
        "PE2_candidates_across_smoke": pe2_candidates,
        "external_comparable_patch_trace_rows": external_comparable,
        "external_FAIL_TO_PASS_rows": external_fail_to_pass,
        "smoke_reject_counts": dict(sorted(reject_counts.items())),
        "after_status_counts_for_patched_fail_targets": after_counts,
        "after_passed_targets": after_passed,
        "after_failed_or_timeout_targets": after_failed,
        "blockers": blockers,
        "root_cause": root_cause,
        "deterministic_checks_to_add": deterministic_checks_to_add,
        "retarget_plan": retarget_plan,
        "next_stage": "stage12291_commit_pair_after_pass_prefilter",
        "raw_output_emitted": False,
    }

    (OUT / "replay_queue_repair_or_retarget_decision.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (OUT / "REPLAY_QUEUE_REPAIR_OR_RETARGET_DECISION_STAGE12290.md").write_text(
        "# Stage12290 Replay Queue Repair Or Retarget Decision\n\n"
        + "Stage12244 is blocked for patch-effect training until target construction is repaired.\n\n"
        + "```json\n"
        + json.dumps(summary, indent=2, sort_keys=True)
        + "\n```\n",
        encoding="utf-8",
    )
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
