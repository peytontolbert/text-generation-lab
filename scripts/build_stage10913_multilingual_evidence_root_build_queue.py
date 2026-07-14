#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "runs" / "local" / "artifacts"
STAGE = 10913
NAME = "stage10913_multilingual_evidence_root_build_queue"
OUT_DIR = ARTIFACTS / NAME
OUT_JSON = OUT_DIR / "multilingual_evidence_root_build_queue.json"
OUT_JSONL = OUT_DIR / "root_build_queue.jsonl"

ATLAS_JSON = ARTIFACTS / "stage10417_multilingual_reviewed_scaling_atlas" / "multilingual_reviewed_scaling_atlas.json"
WEB_GAP_JSON = ARTIFACTS / "stage10418_pure_web_verifier_anchor_gap_audit" / "pure_web_verifier_anchor_gap_audit.json"
EVIDENCE_POLICY_JSON = ARTIFACTS / "stage10912_current_evidence_policy_decision" / "current_evidence_policy_decision.json"
CANARY_VALIDATION = ARTIFACTS / "stage10881_evidence_alias_quarantine_successor" / "agentkernel_lite_encdec_validation.jsonl"


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def now_utc() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def main() -> None:
    atlas = load_json(ATLAS_JSON)
    web_gap = load_json(WEB_GAP_JSON)
    evidence_policy = load_json(EVIDENCE_POLICY_JSON)
    canary_rows = [
        row
        for row in load_jsonl(CANARY_VALIDATION)
        if str(row.get("task_type") or "") == "evidence_citation"
    ]

    admitted = {row["bundle_id"]: row for row in atlas.get("admitted_bundle_rows") or []}
    canary_by_language = {str(row.get("language_family") or ""): row for row in canary_rows}
    agentkernel_cpp_bundle = "stage10119::localsess_agentkernel_sessseed_codex_sessions_rollout_2026_03_26t17_53_18_019d2b47_7d2d_7622_8e05_3513_agent_kernel_modeling_ssm_kernels_src_selective_scan_cpp_agent_kernel_modeling_w_5511e7fec6_aug_1500000_8b46e7f662::c_cpp"

    queue_rows = [
        {
            "queue_id": "python_repository_library_evidence_b_vs_f_replenishment",
            "priority": 1,
            "language_family": "python",
            "repo_id": "repository_library",
            "source_bundle_id": "stage10119::localsess_repository_library_sessseed_codex_sessions_rollout_2025_11_26t00_55_44_019abda8_c0d8_7803_8a77_1e0f_scripts_universe_build_py_64d2cf209b_aug_1500000_8b46e7f662::python",
            "packet_dir": admitted["stage10119::localsess_repository_library_sessseed_codex_sessions_rollout_2025_11_26t00_55_44_019abda8_c0d8_7803_8a77_1e0f_scripts_universe_build_py_64d2cf209b_aug_1500000_8b46e7f662::python"]["packet_dir"],
            "current_checked_row_id": canary_by_language["python"]["row_id"],
            "current_checked_target": canary_by_language["python"]["target_text"],
            "current_checked_failure": "retrieval collapses to candidate_change_surface instead of verifier_and_test_constraint",
            "selected_tests": admitted["stage10119::localsess_repository_library_sessseed_codex_sessions_rollout_2025_11_26t00_55_44_019abda8_c0d8_7803_8a77_1e0f_scripts_universe_build_py_64d2cf209b_aug_1500000_8b46e7f662::python"]["selected_tests"],
            "candidate_paths": admitted["stage10119::localsess_repository_library_sessseed_codex_sessions_rollout_2025_11_26t00_55_44_019abda8_c0d8_7803_8a77_1e0f_scripts_universe_build_py_64d2cf209b_aug_1500000_8b46e7f662::python"]["candidate_paths"],
            "task": "Build fresh source-backed evidence_citation rows where candidate_change_surface is tempting but verifier_and_test_constraint is the uniquely justified visible fact.",
            "anti_cheat_requirements": [
                "Preserve all six visible evidence roles.",
                "No visible target path string before options.",
                "At least one sibling candidate surface remains plausible.",
                "Gold F must be justifiable from selected test or verifier text, not file-name priors.",
            ],
            "status": "ready_to_materialize",
        },
        {
            "queue_id": "cpp_parametergolf_evidence_b_vs_f_replenishment",
            "priority": 1,
            "language_family": "c_cpp",
            "repo_id": "parametergolf",
            "source_bundle_id": "stage10119::localsess_parametergolf_sessseed_codex_sessions_rollout_2026_03_28t16_56_21_019d3560_1014_7761_9ea7_5638_parameter_golf_records_track_10min_16mb_2026_03_26_statespace_causalmachine_cuda_a018ca0b43_aug_1500000_8b46e7f662::c_cpp",
            "packet_dir": admitted["stage10119::localsess_parametergolf_sessseed_codex_sessions_rollout_2026_03_28t16_56_21_019d3560_1014_7761_9ea7_5638_parameter_golf_records_track_10min_16mb_2026_03_26_statespace_causalmachine_cuda_a018ca0b43_aug_1500000_8b46e7f662::c_cpp"]["packet_dir"],
            "current_checked_row_id": canary_by_language["c_cpp"]["row_id"],
            "current_checked_target": canary_by_language["c_cpp"]["target_text"],
            "current_checked_failure": "retrieval collapses to candidate_change_surface instead of verifier_and_test_constraint",
            "selected_tests": admitted["stage10119::localsess_parametergolf_sessseed_codex_sessions_rollout_2026_03_28t16_56_21_019d3560_1014_7761_9ea7_5638_parameter_golf_records_track_10min_16mb_2026_03_26_statespace_causalmachine_cuda_a018ca0b43_aug_1500000_8b46e7f662::c_cpp"]["selected_tests"],
            "candidate_paths": admitted["stage10119::localsess_parametergolf_sessseed_codex_sessions_rollout_2026_03_28t16_56_21_019d3560_1014_7761_9ea7_5638_parameter_golf_records_track_10min_16mb_2026_03_26_statespace_causalmachine_cuda_a018ca0b43_aug_1500000_8b46e7f662::c_cpp"]["candidate_paths"],
            "task": "Build fresh C/C++ evidence_citation rows with the same B-versus-F competition from disjoint root states inside the admitted packet family.",
            "anti_cheat_requirements": [
                "Gold F must cite concrete selected-test or verifier text.",
                "candidate_change_surface must remain plausible but insufficient.",
                "Avoid rows where benchmark or kernel filenames alone determine the answer.",
                "Keep root-level split isolation from the checked canary row.",
            ],
            "status": "ready_to_materialize",
        },
        {
            "queue_id": "cpp_agentkernel_counterfamily_evidence_replenishment",
            "priority": 2,
            "language_family": "c_cpp",
            "repo_id": "agentkernel",
            "source_bundle_id": agentkernel_cpp_bundle,
            "packet_dir": admitted[agentkernel_cpp_bundle]["packet_dir"],
            "selected_tests": admitted[agentkernel_cpp_bundle]["selected_tests"],
            "candidate_paths": admitted[agentkernel_cpp_bundle]["candidate_paths"],
            "task": "Build a second C/C++ evidence family so B-versus-F learning does not overfit to parametergolf naming or CUDA-kernel geometry.",
            "anti_cheat_requirements": [
                "Keep selected-test anchors visible.",
                "Ensure at least one non-kernel distractor remains plausible.",
                "Audit candidate path ordering and filename priors.",
            ],
            "status": "ready_to_materialize",
        },
        {
            "queue_id": "pure_web_positive_b_root_with_selected_tests",
            "priority": 1,
            "language_family": "web_js_ts_html",
            "repo_id": "new_source_family_required",
            "source_bundle_id": None,
            "packet_dir": None,
            "current_checked_row_id": canary_by_language["web_js_ts_html"]["row_id"],
            "current_checked_target": canary_by_language["web_js_ts_html"]["target_text"],
            "current_checked_failure": "No failure on current row, but no safe verifier-anchored pure-web counterweight exists for role-mapped evidence scoring.",
            "selected_tests": [],
            "candidate_paths": [],
            "task": "Acquire or build a new non-overlapping pure-web root with selected tests where candidate_change_surface is genuinely the correct evidence citation target.",
            "anti_cheat_requirements": [
                "Must be pure web, not mixed-language code_assist overlap.",
                "Must include selected tests or verifier text.",
                "Must remain source-heldout admissible for headline use.",
                "Use it as the web positive control against any future evidence-role scorer change.",
            ],
            "status": "blocked_on_source_supply",
            "blocker_reference": web_gap["next_best_step"],
        },
        {
            "queue_id": "overlap_web_stress_only_code_assist_bundle",
            "priority": 3,
            "language_family": "web_js_ts_html",
            "repo_id": "code_assist",
            "source_bundle_id": "stage10176::localsess_code_assist_sessseed_codex_sessions_rollout_2026_01_27t13_13_10_019bff96_2dc5_7162_88f8_83eb_src_code_assist_orchestrator_cognitive_perfection_py_src_code_assist_orchestrato_3a0f6d8311_aug_1500000_8b46e7f662::web_js_ts_html",
            "packet_dir": "runs/local/artifacts/stage10176_code_assist_web_replenishment_bundle/review_packets/stage10176__code_assist__web_js_ts_html",
            "selected_tests": ["tests/integration/test_dashboard_api.py"],
            "candidate_paths": [
                "src/code_assist/ui/fastapi_dashboard.py",
                "src/code_assist/ui/dashboard_assets/dashboard.js",
                "src/code_assist/ui/dashboard_assets/dashboard.css",
                "src/code_assist/ui/dashboard_assets/index.html",
            ],
            "task": "Use only as stress-eval or train-support material while pure-web heldout supply is absent.",
            "anti_cheat_requirements": [
                "Never upgrade to source-heldout headline evidence.",
                "Mark repo-overlap explicitly in any manifest.",
            ],
            "status": "stress_only",
        },
    ]

    payload = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": True,
        "claim_scope": [
            "Turn the current multilingual evidence-citation weakness into an explicit root build queue rather than another generic support sweep.",
            "Separate immediately materializable Python/C++ B-versus-F evidence work from the pure-web source-supply blocker.",
        ],
        "source_artifacts": {
            "atlas": rel(ATLAS_JSON),
            "web_gap": rel(WEB_GAP_JSON),
            "evidence_policy_decision": rel(EVIDENCE_POLICY_JSON),
            "checked_canary_validation": rel(CANARY_VALIDATION),
        },
        "queue_summary": {
            "ready_to_materialize": sum(1 for row in queue_rows if row["status"] == "ready_to_materialize"),
            "blocked_on_source_supply": sum(1 for row in queue_rows if row["status"] == "blocked_on_source_supply"),
            "stress_only": sum(1 for row in queue_rows if row["status"] == "stress_only"),
        },
        "findings": [
            "Python and C/C++ already have admitted reviewed source bundles with selected tests and the full six evidence roles, so the next evidence-citation improvement should come from materializing fresh disjoint rows from those packets.",
            "Pure-web does not yet have a verifier-anchored non-overlapping source family, so no honest multilingual evidence scorer change can be adopted until web positive-control supply exists.",
            "The code_assist web replenishment bundle is useful only as stress or train-support material because it overlaps consumed repo family evidence.",
        ],
        "next_best_step": "Materialize the two priority-1 Python/C++ evidence replenishment queues into fresh heldout/support candidate rows, and keep web conservative until a new pure-web selected-test family is ingested.",
        "root_build_queue_rows": rel(OUT_JSONL),
    }

    write_json(OUT_JSON, payload)
    write_jsonl(OUT_JSONL, queue_rows)
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
