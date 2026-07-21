#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12241_maintainer_500_root_campaign_contract"
OUT = ROOT / "runs/local/artifacts" / STAGE
SUMMARY = ROOT / "runs/summaries" / f"{STAGE}.json"


def write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def main() -> int:
    payload: dict[str, Any] = {
        "stage": STAGE,
        "decision": "maintainer_500_root_campaign_open_training_blocked_until_admission",
        "target": {
            "root_rows": 500,
            "root_rows_definition": "one root-level candidate with repo lineage, task family, verifier evidence status, split eligibility, and admission decision; not row variants",
            "languages": {
                "python": 125,
                "rust": 125,
                "c_cpp": 125,
                "web_js_ts_html": 125,
            },
            "minimum_external_repair_subset": {
                "external_comparable_patch_trace_rows": 25,
                "external_fail_to_pass_rows": 15,
                "non_python_external_rows": 10,
            },
        },
        "lane_quotas": {
            "comparable_patch_trace_repair": {
                "target_roots": 100,
                "minimum_before_training": 25,
                "status": "hardest_lane_primary_frontier_blocker",
            },
            "sealed_transition_eval_candidates": {
                "target_roots": 150,
                "minimum_before_scoring_stage12099": 100,
                "status": "required_to_confirm_route_generalization",
            },
            "verifier_observation_auxiliary": {
                "target_roots": 150,
                "current_safe_candidate_rows": 368,
                "status": "auxiliary_only_loss_disabled_until_request",
            },
            "safe_refactor_or_pass_to_pass_patch_trace": {
                "target_roots": 50,
                "status": "useful_for_no_regression_and_patch_apply_not_repair_floor",
            },
            "negative_abstain_or_not_comparable": {
                "target_roots": 50,
                "status": "useful_for stop/abstain calibration, not repair proof",
            },
        },
        "root_record_schema": {
            "required_fields": [
                "candidate_root_id",
                "repo_family",
                "language_family",
                "lane",
                "source_path_or_artifact",
                "lineage_key",
                "verifier_command",
                "verifier_output_available",
                "patch_diff_available",
                "selected_test_or_verifier_anchor",
                "split_eligibility",
                "admission_status",
                "blockers",
                "next_materialization_step",
            ],
            "optional_but_preferred_fields": [
                "commit_before",
                "commit_after",
                "patch_apply_evidence",
                "stdout_sha256",
                "stderr_sha256",
                "candidate_action_set_status",
                "root_family_cap_bucket",
            ],
        },
        "hard_rejects": [
            "missing-test or no-tests-collected counted as failure",
            "ENV/dependency/network/install/GPU failure unless the explicit task is environment repair",
            "syntax-only or forced compile-error mutation counted as maintainer repair",
            "commit metadata inferred PASS/FAIL without command output",
            "selected test added only by patch",
            "weak/unrelated verifier",
            "cross-source joins for diff/command/verifier",
            "controlled fixture counted as external or source-heldout",
            "PASS_TO_PASS counted as FAIL_TO_PASS",
            "row variants counted as independent roots",
        ],
        "subagent_assignments": {
            "python": "scout high-quality Python roots across all lanes",
            "rust": "scout locally hydratable Cargo/test roots across all lanes",
            "c_cpp": "scout CMake/CTest/build/test roots across all lanes",
            "web_js_ts_html": "pending slot; run after current agents finish or local pre-scout",
        },
        "campaign_metrics": {
            "accepted_root_rows": 0,
            "blocked_root_rows": 0,
            "pending_review_root_rows": 0,
            "training_allowed": False,
        },
        "next_stage": {
            "stage": "stage12242_maintainer_500_candidate_intake_rollup",
            "purpose": "Normalize subagent/local scout outputs into root records and enforce caps/rejects.",
            "training_allowed": False,
        },
        "claim_boundary": "Campaign contract only. This does not admit rows or authorize training.",
        "training_allowed": False,
    }
    brief = f"""# {STAGE}

Target: 500 root rows, not 500 variants.

Language quotas:
- Python: 125
- Rust: 125
- C/C++: 125
- Web/JS/TS/HTML: 125

Primary blocker lane: comparable patch trace repair. Minimum before training remains 25 external comparable patch traces with 15 FAIL_TO_PASS and 10 non-Python.

Hard rejects:
{chr(10).join('- ' + item for item in payload['hard_rejects'])}

Every scout output must be converted into the root_record_schema before it can count.
"""
    OUT.mkdir(parents=True, exist_ok=True)
    write_json(OUT / "maintainer_500_root_campaign_contract.json", payload)
    write_text(OUT / "MAINTAINER_500_ROOT_CAMPAIGN_CONTRACT_STAGE12241.md", brief)
    write_json(SUMMARY, payload)
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
