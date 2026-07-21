#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12293_commit_pair_queue_exhaustion_and_next_source_decision"
OUT = ROOT / "runs/local/artifacts" / STAGE
SUMMARY = ROOT / "runs/summaries" / f"{STAGE}.json"


def read_json(path: Path) -> dict:
    if not path.exists():
        return {"missing": True, "path": str(path)}
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    stage12290 = read_json(ROOT / "runs/summaries/stage12290_replay_queue_repair_or_retarget_decision.json")
    stage12291 = read_json(ROOT / "runs/summaries/stage12291_commit_pair_after_pass_prefilter.json")
    stage12292 = read_json(ROOT / "runs/summaries/stage12292_after_pass_eligible_before_fail_patch_effect_replay.json")

    summary = {
        "stage": STAGE,
        "decision": "stage12244_commit_pair_queue_exhausted_for_patch_effect_proof",
        "training_allowed": False,
        "admitted_rows": 0,
        "training_rows_emitted": 0,
        "external_comparable_patch_trace_rows": 0,
        "external_FAIL_TO_PASS_rows": 0,
        "evidence": {
            "stage12290": {
                "targets_attempted_across_smoke": stage12290.get("targets_attempted_across_smoke"),
                "PE2_candidates_across_smoke": stage12290.get("PE2_candidates_across_smoke"),
                "after_failed_or_timeout_targets": len(stage12290.get("after_failed_or_timeout_targets", [])),
            },
            "stage12291": {
                "targets_checked": stage12291.get("targets_checked"),
                "eligible_after_pass": stage12291.get("eligible_for_before_and_before_plus_patch_replay"),
                "after_status_counts": stage12291.get("after_status_counts"),
                "eligible_by_language": stage12291.get("eligible_by_language"),
            },
            "stage12292": {
                "targets_attempted": stage12292.get("targets_attempted"),
                "PE2_candidates": stage12292.get("PE2_candidates"),
                "reject_counts": stage12292.get("reject_counts"),
            },
        },
        "root_cause": (
            "The initial commit-pair queue mixed two invalid shapes: targets whose exact verifier fails even "
            "at commit_after, and targets whose exact verifier already passes at commit_before. Neither shape "
            "proves patch effect. The queue therefore cannot supply external comparable repair rows without "
            "retargeting its source construction."
        ),
        "hard_rules_for_next_source_adapter": [
            "build_target_only_if_exact_after_verifier_passes",
            "then_require_exact_before_verifier_fails",
            "then_require_before_plus_reference_patch_passes",
            "use_full_resolved_commit_ids_not_symbolic_parent_or_short_ref_only",
            "emit_no_raw_source_patch_command_or_output_payloads",
            "count_as_external_comparable_only_after_semantic_patch_effect_audit",
        ],
        "next_source_priority": [
            {
                "source": "benchmark_task_corpora_with_explicit_failing_tests_and_reference_patches",
                "why": "these sources encode fail/pass semantics directly instead of inferring from arbitrary commits",
                "next_stage": "stage12294_patch_task_source_adapter_atlas",
            },
            {
                "source": "maintainer_500_external_backlog_retargeted_with_after_first_gate",
                "why": "has external roots but must be rebuilt with executable verifier brackets before replay",
                "next_stage": "stage12295_maintainer500_after_first_retarget_request",
            },
            {
                "source": "codex_chat_horizon_transition_rows",
                "why": "valuable for next_action/verifier/continue_stop, but not counted as patch-effect proof unless V5",
                "next_stage": "stage12296_horizon_transition_projection_ledger",
            },
        ],
        "raw_output_emitted": False,
    }

    (OUT / "commit_pair_queue_exhaustion_decision.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (OUT / "COMMIT_PAIR_QUEUE_EXHAUSTION_AND_NEXT_SOURCE_DECISION_STAGE12293.md").write_text(
        "# Stage12293 Commit-Pair Queue Exhaustion And Next Source Decision\n\n"
        + "No training rows are emitted. Stage12244 is exhausted for patch-effect proof under current local replay.\n\n"
        + "```json\n"
        + json.dumps(summary, indent=2, sort_keys=True)
        + "\n```\n",
        encoding="utf-8",
    )
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
