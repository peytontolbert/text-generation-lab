#!/usr/bin/env python3
"""Stage12424 new-source-adapter scouting request/control artifact.

This stage does not mine or admit rows. It captures the post-Stage12421 lesson:
the current Stage122 direct/derived pool is exhausted under strict accounting,
so the next useful work is new source adapters or safe replay execution.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12424_new_source_adapter_scouting_request_control_artifact"
OUT = ROOT / "runs/local/artifacts" / STAGE
SUMMARY = ROOT / "runs/summaries" / f"{STAGE}.json"
INPUTS = {
    "stage12419_control": ROOT / "runs/local/artifacts/stage12419_current_dataset_control_board_v17/current_dataset_control_board_v17.json",
    "stage12420_summary": ROOT / "runs/summaries/stage12420_next_step_spine_aligned_execution_plan.json",
    "stage12421_summary": ROOT / "runs/summaries/stage12421_new_direct_real_verifier_observation_miner.json",
    "stage12422_summary": ROOT / "runs/summaries/stage12422_open_swe_replay_micro_pilot_preflight.json",
    "unbounded_spine": ROOT / "docs/UNBOUNDED_SOFTWARE_TASK_COMPLETION_SPINE_STAGE12195.md",
}
FORBIDDEN_RE = re.compile(r"https?://|www\.|diff --git|@@ |(?:^|[\s:=])/(?:[A-Za-z0-9._-]+/){2,}[A-Za-z0-9._-]+", re.I | re.M)


def stable_hash(value: Any, n: int = 24) -> str:
    data = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(data.encode("utf-8")).hexdigest()[:n]


def file_hash(path: Path) -> str | None:
    if not path.exists():
        return None
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return value if isinstance(value, dict) else {}


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def guardrail_scan(value: Any) -> dict[str, Any]:
    payload = json.dumps(value, sort_keys=True)
    issues = FORBIDDEN_RE.findall(payload)
    return {"scan_passed": len(issues) == 0, "issue_count": len(issues), "issues": ["forbidden_raw_pattern_detected"] if issues else []}


def main() -> None:
    s12421 = read_json(INPUTS["stage12421_summary"])
    s12422 = read_json(INPUTS["stage12422_summary"])
    bottleneck = {
        "current_countable_before_stage12421": int(s12421.get("current_countable_train_support_tasks_before_stage") or 190),
        "stage12421_emitted_sanitized_projection_rows": int(s12421.get("total_emitted_sanitized_projection_rows") or s12421.get("emitted_rows") or 0),
        "stage12421_countable_external_rows": int(s12421.get("countable_as_new_train_support_rows") or 0),
        "stage12421_auxiliary_controlled_fixture_rows": int(s12421.get("auxiliary_controlled_fixture_train_support_rows") or 0),
        "current_countable_after_stage12421": int(s12421.get("total_current_train_support_tasks_if_accepted") or 190),
        "remaining_gap_to_500": int(s12421.get("remaining_gap_to_500") or 310),
        "stage12422_replay_requests_preflighted": int(s12422.get("micro_pilot_request_count") or 0),
        "stage12422_replay_attempted_count": int(s12422.get("replay_attempted_count") or 0),
        "diagnosis": "same-pool mining is exhausted; strict accounting converted 26 emitted projections into only 2 countable external rows",
    }
    required_top_level_fields = [
        "stage", "decision", "claim_boundary", "training_allowed", "admitted_rows", "emitted_rows",
        "emitted_training_rows", "countable_new_rows", "countable_as_new_train_support_rows",
        "countable_as_new_proof_floor_rows", "source_adapter_id", "source_family_counts",
        "language_counts", "repo_family_counts", "root_count", "dedupe_key_policy", "direct_vs_derived_counts",
        "target_semantic_counts", "proof_slot_status_counts", "raw_content_policy", "guardrail_scan_passed",
        "raw_leak_count", "overclaim_count", "strict_source_heldout_status", "dominance_report",
        "blocked_reason_counts", "promotion_gate_status", "next_stage_recommendation",
    ]
    adapter_acceptance_quotas = {
        "minimum_external_verifier_train_support_rows_for_next_miner": 40,
        "minimum_replayable_patch_trace_candidates_for_next_miner": 12,
        "minimum_unbounded_level3_candidates_for_next_miner": 20,
        "minimum_distinct_source_families": 10,
        "minimum_distinct_language_families": 3,
        "maximum_controlled_fixture_share": 0.10,
        "maximum_single_source_family_share": 0.25,
        "minimum_records_with_direct_verifier_anchor": 40,
        "minimum_records_with_state_transition_anchor": 30,
        "minimum_records_with_stop_or_continue_anchor": 20,
        "minimum_patch_trace_records_with_before_after_verifier_status": 8,
        "minimum_records_absent_from_existing_countable_ledgers": 40,
        "raw_leak_count_required": 0,
        "overclaim_count_required": 0,
        "training_allowed_required": False,
    }
    candidate_adapter_families = [
        {
            "adapter_family": "codex_session_episode_graphs",
            "purpose": "mine task-window transition functions from long Codex sessions after source-root and event-state hydration",
            "must_prove": ["source_root_label", "ordered_events", "state_before", "chosen_action", "observation", "state_update", "stop_continue"],
            "countability_warning": "short-horizon projections can count only after dedupe and safe semantic extraction; not raw observed-action imitation",
        },
        {
            "adapter_family": "open_swe_replay_micro_pilot",
            "purpose": "turn two Stage12422 hash-only proof-gap requests into candidate Level-3/patch-trace evidence if replay proves all slots",
            "must_prove": ["checkout_before", "patch_apply", "state_after", "same_verifier_before_after", "causal_linkage"],
            "countability_warning": "executor output is candidate evidence only; later admission gate required",
        },
        {
            "adapter_family": "external_benchmark_patch_logs",
            "purpose": "ingest existing authoritative fail/pass repair logs from local benchmark artifacts if same-source patch/verifier lineage exists",
            "must_prove": ["patch_diff_hash", "pre_status", "post_status", "same_verifier_identity", "repo_lineage"],
            "countability_warning": "metadata-only issue/commit records are not enough",
        },
        {
            "adapter_family": "locally_hydratable_repo_tasks",
            "purpose": "generate fresh executable verifier observations and patch-effect proofs from local repos under controlled checkout workspaces",
            "must_prove": ["commit_before", "command_result", "selected_verifier", "state_update", "stop_continue"],
            "countability_warning": "build-only/pass-current rows help policy but do not count as repair proof",
        },
    ]
    artifact = {
        "stage": STAGE,
        "record_type": "new_source_adapter_scouting_request_control_v2",
        "decision": "control_artifact_only_fail_closed_no_rows_admitted",
        "claim_boundary": "Stage12424 requests new source-adapter scouting because Stage12421 proved the old Stage122 pool is exhausted under strict accounting. It emits no rows and admits nothing.",
        "training_allowed": False,
        "admitted_rows": 0,
        "emitted_rows": 0,
        "emitted_training_rows": 0,
        "countable_new_rows": 0,
        "countable_as_new_train_support_rows": 0,
        "countable_as_new_proof_floor_rows": 0,
        "stage12421_bottleneck": bottleneck,
        "adapter_acceptance_quotas": adapter_acceptance_quotas,
        "required_top_level_fields": required_top_level_fields,
        "candidate_adapter_families": candidate_adapter_families,
        "raw_content_policy": {
            "commands_emitted": False,
            "outputs_emitted": False,
            "paths_emitted": False,
            "urls_emitted": False,
            "source_text_emitted": False,
            "diffs_emitted": False,
            "patches_emitted": False,
            "issue_bodies_emitted": False,
            "input_text_emitted": False,
        },
        "reject_conditions": [
            "adapter counts derivative/projection/control artifacts as new source supply",
            "adapter emits raw commands, outputs, paths, URLs, source text, diffs, patches, or issue bodies",
            "adapter lacks exact dedupe against Stage12385/12416/12418/12421",
            "adapter counts controlled fixtures above quota as high-quality external rows",
            "adapter claims Level-3 or patch-trace without all proof slots",
            "adapter claims source-heldout or strict eligibility without split/root/protected-overlap proof",
        ],
        "promotion_gate_status": {
            "artifact_is_control_only": "PASS",
            "no_rows_admitted": "PASS",
            "stage12421_bottleneck_encoded": "PASS",
            "new_adapter_miner_required": "PASS",
            "training_allowed": "PASS_FALSE",
        },
        "next_stage_recommendation": "stage12425_source_adapter_feasibility_miner",
        "input_inventory": {name: {"present": path.exists(), "sha256": file_hash(path)} for name, path in INPUTS.items()},
    }
    scan = guardrail_scan(artifact)
    artifact["guardrail_scan_passed"] = scan["scan_passed"]
    artifact["raw_leak_count"] = scan["issue_count"]
    artifact["overclaim_count"] = 0
    artifact["summary_hash"] = stable_hash({k: v for k, v in artifact.items() if k != "summary_hash"})
    write_json(OUT / "new_source_adapter_scouting_request_control_artifact.json", artifact)
    write_json(OUT / "guardrail_scan.json", scan)
    write_json(SUMMARY, artifact)
    print(json.dumps(artifact, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
