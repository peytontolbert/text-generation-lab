#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12333_bears_hydration_request"
OUT = ROOT / "runs/local/artifacts" / STAGE
SUMMARY = ROOT / "runs/summaries" / f"{STAGE}.json"
CANDIDATES = ROOT / "runs/local/artifacts/stage12327_external_adapter_preflight/bears_failing_passing_candidates.jsonl"
BUGS = Path("/arxiv/repositories/RepairThemAll/data/benchmarks/bears/bugs.json")
PRIORITY = ["Bears_157", "Bears_144", "Bears_251", "Bears_209", "Bears_98"]


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")


def load_bugs() -> dict[str, dict[str, Any]]:
    if not BUGS.exists():
        return {}
    data = json.loads(BUGS.read_text(encoding="utf-8"))
    return {str(row.get("bugId")): row for row in data}


def branch_id(row: dict[str, Any], bugs: dict[str, dict[str, Any]]) -> str:
    bug_id = row.get("source_record_ref", {}).get("bug_id")
    source = bugs.get(str(bug_id)) or {}
    branch_url = str(source.get("branchUrl") or "")
    if branch_url.rstrip("/"):
        return branch_url.rstrip("/").split("/")[-1]
    repo = str(row.get("repo_family") or "").rstrip("/").split("/")[-1]
    return f"{repo}-{row.get('buggy_build_id')}-{row.get('fixer_build_id')}"


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    rows = read_jsonl(CANDIDATES)
    by_id = {row.get("source_record_ref", {}).get("bug_id"): row for row in rows}
    bugs = load_bugs()
    requests = []
    missing = []
    for rank, bug_id in enumerate(PRIORITY, 1):
        row = by_id.get(bug_id)
        if not row:
            missing.append(bug_id)
            continue
        source = bugs.get(bug_id) or {}
        patch_diff = source.get("patchDiff") or {}
        tests = source.get("tests") or {}
        requests.append({
            "stage": STAGE,
            "record_type": "bears_failing_passing_hydration_request",
            "priority_rank": rank,
            "candidate_id": row.get("candidate_id"),
            "bug_id": bug_id,
            "branch_id": branch_id(row, bugs),
            "repo_family": row.get("repo_family"),
            "language_family": "java",
            "buggy_build_id": row.get("buggy_build_id"),
            "fixer_build_id": row.get("fixer_build_id"),
            "buggy_commit_sha": row.get("buggy_commit_sha"),
            "fixer_commit_sha": row.get("fixer_commit_sha"),
            "patch_diff_hash": row.get("patch_diff_hash"),
            "patch_path_count": row.get("patch_path_count"),
            "patch_line_added": (patch_diff.get("lines") or {}).get("numberAdded"),
            "patch_line_deleted": (patch_diff.get("lines") or {}).get("numberDeleted"),
            "selected_test_count": row.get("selected_test_count"),
            "test_metrics": row.get("test_metrics"),
            "failure_name_sample": [f.get("failureName") for f in (tests.get("overallMetrics") or {}).get("failures", [])[:4]],
            "hydration_command_template": "python /arxiv/repositories/RepairThemAll/script/checkout.py --benchmark Bears --id <branch_id> --working_directory <materialization_root>",
            "admission": {
                "training_allowed": False,
                "train_support_allowed": False,
                "strict_eval_eligible": False,
                "source_heldout_admissible": False,
                "level3_admitted": False,
                "patch_trace_admitted": False,
                "repair_claim_admitted": False,
                "admission_status": "hydration_request_only",
            },
            "required_qc_fields_before_any_admission": [
                "branch_checkout_exit_code",
                "branch_head_sha",
                "buggy_code_checkout_sha",
                "fixed_code_checkout_sha",
                "metadata_buggy_sha_match",
                "metadata_fixer_sha_match",
                "bears_json_sha256",
                "raw_diff_sha256",
                "changed_paths",
                "project_root_pom_path",
                "effective_module_path",
                "compile_buggy_exit_code",
                "compile_fixed_exit_code",
                "buggy_test_exit_code",
                "fixed_test_exit_code",
                "buggy_surefire_totals",
                "fixed_surefire_totals",
                "selected_test_names",
                "selected_test_failure_types_buggy",
                "selected_test_passed_fixed",
                "nonselected_regression_count_fixed",
                "stdout_stderr_artifact_hashes",
                "same_source_patch_verifier_causality_pass",
                "anti_leak_rendering_pass",
            ],
            "hard_rejects": [
                "metadata-only row admitted",
                "branch checkout absent",
                "buggy failure not reproduced",
                "fixed selected test not passing",
                "metadata sha mismatch",
                "raw verifier output emitted to model row",
                "raw diff emitted to model row",
            ],
        })
    write_jsonl(OUT / "bears_priority_hydration_requests.jsonl", requests)
    summary = {
        "stage": STAGE,
        "decision": "bears_priority_hydration_request_ready_training_still_blocked",
        "training_allowed": False,
        "claim_boundary": "Hydration request only. No Bears row admitted as train-support, Level-3, patch-trace, repair, or sealed eval.",
        "requested_candidates": len(requests),
        "missing_priority_candidates": missing,
        "priority_order": PRIORITY,
        "source_candidates": str(CANDIDATES),
        "source_bugs_json": str(BUGS),
        "next_stage": "stage12334_bears_priority_hydration_executor_or_manual_replay",
    }
    (OUT / "bears_hydration_request_summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (OUT / "BEARS_HYDRATION_REQUEST_STAGE12333.md").write_text(
        "# Stage12333 Bears Hydration Request\n\n"
        "Requests hydration for the five easiest Bears failing_passing candidates. This admits zero rows.\n",
        encoding="utf-8",
    )
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
