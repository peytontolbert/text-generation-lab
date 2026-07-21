#!/usr/bin/env python3
"""Build Stage12249 replay preflight execution request.

This request narrows the next work to falsifying/admitting repair candidates by
executing preflight checks. It intentionally avoids training and avoids counting
current-state/pass-only verifier observations as repair roots.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12249_replay_preflight_execution_request"


def load_json(rel: str) -> dict[str, Any]:
    path = ROOT / rel
    if not path.exists():
        return {"_missing": rel}
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, sort_keys=True) + "\n")


def write_text(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value, encoding="utf-8")


def main() -> int:
    audit12248 = load_json("runs/summaries/stage12248_root_supply_discrepancy_audit.json")
    validation12246 = load_json("runs/summaries/stage12246_replay_target_validation_audit.json")
    shortlist_count = validation12246.get("top_shortlist_count") or validation12246.get("shortlist_count") or 8

    checks = [
        {
            "check_id": "pre_patch_verifier_exists",
            "command_requirement": "The exact selected verifier command can run or be proven runnable in the before checkout.",
            "hard_fail_if": ["test file/path does not exist before patch", "command requires network/GPU/unknown secret"],
        },
        {
            "check_id": "diff_is_source_bearing",
            "command_requirement": "The patch changes production/source behavior, not only tests, docs, snapshots, generated files, or dependency locks.",
            "hard_fail_if": ["test_added_only", "docs_only", "snapshot_only", "dependency_lock_only"],
        },
        {
            "check_id": "before_state_falsifies",
            "command_requirement": "The before checkout produces a real behavioral fail for the selected verifier, not dependency/env/setup failure.",
            "hard_fail_if": ["ENV_BLOCKED", "DEPENDENCY_BLOCKED", "NO_TESTS_COLLECTED", "PASS_BEFORE_PATCH"],
        },
        {
            "check_id": "apply_patch_clean",
            "command_requirement": "The candidate patch applies cleanly to the before checkout with recorded changed paths and diff digest.",
            "hard_fail_if": ["patch_does_not_apply", "cross_repo_patch", "changed_path_not_in_repo"],
        },
        {
            "check_id": "after_state_passes_same_verifier",
            "command_requirement": "The patched checkout passes the same selected verifier command with command output captured.",
            "hard_fail_if": ["after_fails_same_verifier", "after_uses_different_test_identity", "after_only_builds_without_selected_verifier"],
        },
    ]

    work_items = [
        {
            "work_item_id": f"stage12249_preflight_slot_{idx:02d}",
            "source_stage": "stage12246_replay_target_validation_audit",
            "candidate_selector": "top_shortlist_by_low_dependency_risk_and_not_test_added_only",
            "slot": idx,
            "required_tuple": [
                "repo_family",
                "commit_before",
                "candidate_patch_diff",
                "selected_verifier_command",
                "before_command_output",
                "patch_apply_output",
                "after_command_output",
                "state_before",
                "state_after",
                "stop_continue_label",
            ],
            "admit_only_if_all_checks_pass": [c["check_id"] for c in checks],
            "training_allowed": False,
        }
        for idx in range(1, int(shortlist_count) + 1)
    ]

    request = {
        "stage": STAGE,
        "artifact_type": "replay_preflight_execution_request",
        "decision": "execute_shortlist_preflight_before_more_candidate_rollups",
        "training_allowed": False,
        "claim_boundary": (
            "Execution request only. It may create command-output evidence, but no training rows are admitted until "
            "a follow-up QC stage proves before-fail/apply/after-pass same-verifier tuples."
        ),
        "parent_diagnosis": {
            "source": "stage12248_root_supply_discrepancy_audit",
            "decision": audit12248.get("decision"),
            "main_flaw": audit12248.get("main_flaw"),
        },
        "input_stage": "stage12246_replay_target_validation_audit",
        "shortlist_slots_requested": int(shortlist_count),
        "execution_policy": {
            "gpu_allowed": False,
            "network_allowed": False,
            "repo_mutation_allowed": "throwaway_checkout_only",
            "training_allowed": False,
            "count_current_state_pass_as_repair": False,
            "count_build_only_as_selected_test_repair": False,
            "count_syntax_error_mutation_as_semantic_repair": False,
        },
        "preflight_checks": checks,
        "success_outputs_required": [
            "preflight_results.jsonl",
            "command_logs/",
            "patch_apply_logs/",
            "admission_candidates_level3.jsonl",
            "blocked_candidates.jsonl",
            "summary.json",
        ],
        "minimum_admission_for_next_training_discussion": {
            "external_comparable_repair_roots": 25,
            "fail_to_pass_roots": 15,
            "non_python_repair_roots": 10,
            "repo_families": 10,
            "languages": 3,
        },
        "work_items": work_items,
    }

    out_dir = ROOT / "runs" / "local" / "artifacts" / STAGE
    write_json(ROOT / "runs" / "summaries" / f"{STAGE}.json", request)
    write_json(out_dir / "replay_preflight_execution_request.json", request)
    write_jsonl(out_dir / "preflight_work_items.jsonl", work_items)

    md = f"""# Stage12249 Replay Preflight Execution Request

## Decision

`{request["decision"]}`

No training is allowed.

## Why This Stage Exists

Stage12248 showed the root supply collapse is caused by missing same-lineage executable phase tuples, not by excessive QC. Stage12249 therefore asks for execution preflights against the Stage12246 shortlist instead of another scout rollup.

## Admission Tuple

Every admitted candidate must contain:

- `repo_family`
- `commit_before`
- candidate source-bearing patch diff
- selected verifier command
- before command output
- patch apply output
- after command output for the same verifier
- structured state_before/state_after
- stop/continue label

## Hard Rejections

- test-added-only or docs-only patch
- dependency/network/GPU/env blocked command
- before state already passes
- patch does not apply
- after state uses a different verifier
- build-only result presented as selected-test repair
- syntax-only mutation presented as semantic maintainer repair

## Requested Slots

`{shortlist_count}` shortlist slots from Stage12246, each with the same preflight checks.
"""
    write_text(out_dir / "REPLAY_PREFLIGHT_EXECUTION_REQUEST_STAGE12249.md", md)
    print(ROOT / "runs" / "summaries" / f"{STAGE}.json")
    print(out_dir / "preflight_work_items.jsonl")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
