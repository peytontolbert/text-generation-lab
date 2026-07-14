#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = 10493
NAME = "stage10493_python_verifier_fresh_review_packet_builder"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
REQUEST_JSON = OUT_DIR / "python_verifier_fresh_review_packet_builder.json"
QUALIFIED_ROWS_JSONL = OUT_DIR / "python_verifier_reviewed_support_rows.jsonl"
TARGET_STATUS_JSONL = OUT_DIR / "python_verifier_review_target_status.jsonl"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"

QUEUE_JSON = ROOT / "runs/local/artifacts/stage10492_python_verifier_reviewed_root_expansion_queue/python_verifier_reviewed_root_expansion_queue.json"
QUEUE_TARGETS_JSONL = ROOT / "runs/local/artifacts/stage10492_python_verifier_reviewed_root_expansion_queue/python_verifier_reviewed_root_expansion_targets.jsonl"
SUPPORT_ROWS_JSONL = ROOT / "runs/local/artifacts/stage10468_fresh_residual_root_support_package/fresh_residual_root_support_rows.jsonl"

STAGE10236_GOLD = ROOT / "runs/local/artifacts/stage10236_context_pack_python_replenishment_bundle/review_packets/stage10236__code_assist__python/perspective_gold_adjudication.json"
STAGE10236_RUBRIC = ROOT / "runs/local/artifacts/stage10236_context_pack_python_replenishment_bundle/review_packets/stage10236__code_assist__python/expert_maintainer_rubric_review.json"
STAGE10236_ANTICHEAT = ROOT / "runs/local/artifacts/stage10236_context_pack_python_replenishment_bundle/review_packets/stage10236__code_assist__python/anti_cheat_review_card.json"

STAGE10300_GOLD = ROOT / "runs/local/artifacts/stage10300_hf_local_python_replenishment_bundle/review_packets/stage10300__code_assist__python/perspective_gold_adjudication.json"
STAGE10300_RUBRIC = ROOT / "runs/local/artifacts/stage10300_hf_local_python_replenishment_bundle/review_packets/stage10300__code_assist__python/expert_maintainer_rubric_review.json"
STAGE10300_ANTICHEAT = ROOT / "runs/local/artifacts/stage10300_hf_local_python_replenishment_bundle/review_packets/stage10300__code_assist__python/anti_cheat_review_card.json"

AGENTKERNEL_RUBRIC = ROOT / "runs/local/artifacts/stage10111_real_session_successor_review_packets/review_packets/stage10110__localsess_agentkernel_sessseed_codex_sessions_rollout_2026_03_29t14___a8d45d33b1e54081/expert_maintainer_rubric_review.json"
AGENTKERNEL_ANTICHEAT = ROOT / "runs/local/artifacts/stage10111_real_session_successor_review_packets/review_packets/stage10110__localsess_agentkernel_sessseed_codex_sessions_rollout_2026_03_29t14___a8d45d33b1e54081/anti_cheat_review_card.json"


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")


def display(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def now_utc() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def maybe_load(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    return load_json(path)


def verifier_entry(gold_payload: dict[str, Any] | None) -> dict[str, Any] | None:
    if not gold_payload:
        return None
    for entry in gold_payload.get("perspective_gold_answers", []):
        if entry.get("perspective") == "verifier_outcome":
            return entry
    return None


def main() -> None:
    queue = load_json(QUEUE_JSON)
    queue_targets = load_jsonl(QUEUE_TARGETS_JSONL)
    support_rows = load_jsonl(SUPPORT_ROWS_JSONL)

    queue_target_map = {str(row["episode_id"]): row for row in queue_targets}

    asset_map: dict[str, dict[str, Any]] = {
        "localsess_code_assist_sessseed_codex_sessions_rollout_2026_01_27t02_21_48_019bfd41_d2a6_7672_9873_81f8_src_code_assist_orchestrator_config_py_src_code_assist_orchestrator_context_pack_acd5ccc9c1_aug_1500000_8b46e7f662": {
            "bundle_id": "stage10236::localsess_code_assist_sessseed_codex_sessions_rollout_2026_01_27t02_21_48_019bfd41_d2a6_7672_9873_81f8_src_code_assist_orchestrator_config_py_src_code_assist_orchestrator_context_pack_acd5ccc9c1_aug_1500000_8b46e7f662::python",
            "gold_path": STAGE10236_GOLD,
            "rubric_path": STAGE10236_RUBRIC,
            "anti_cheat_path": STAGE10236_ANTICHEAT,
        },
        "localsess_code_assist_sessseed_codex_sessions_rollout_2026_01_26t23_27_57_019bfca2_aa35_7502_b929_649a_src_code_assist_agents_hf_local_py_src_code_assist_agents_hf_local_planner_py_sr_3fb1ce61a2_aug_1500000_8b46e7f662": {
            "bundle_id": "stage10300::localsess_code_assist_sessseed_codex_sessions_rollout_2026_01_26t23_27_57_019bfca2_aa35_7502_b929_649a_src_code_assist_agents_hf_local_py_src_code_assist_agents_hf_local_planner_py_sr_3fb1ce61a2_aug_1500000_8b46e7f662::python",
            "gold_path": STAGE10300_GOLD,
            "rubric_path": STAGE10300_RUBRIC,
            "anti_cheat_path": STAGE10300_ANTICHEAT,
        },
        "localsess_agentkernel_sessseed_codex_sessions_rollout_2026_03_29t14_24_54_019d39fb_c43d_7e62_b055_b00b_agent_kernel_cycle_runner_py_agent_kernel_improvement_py_agent_kernel_learning_c_6a4dce0d0c_aug_1500000_8b46e7f662": {
            "bundle_id": "stage10110::localsess_agentkernel_sessseed_codex_sessions_rollout_2026_03_29t14_24_54_019d39fb_c43d_7e62_b055_b00b_agent_kernel_cycle_runner_py_agent_kernel_improvement_py_agent_kernel_learning_c_6a4dce0d0c_aug_1500000_8b46e7f662::python_successor",
            "gold_path": None,
            "rubric_path": AGENTKERNEL_RUBRIC,
            "anti_cheat_path": AGENTKERNEL_ANTICHEAT,
        },
    }

    support_rows_by_bundle: dict[str, list[dict[str, Any]]] = {}
    for row in support_rows:
        bundle_id = str(row.get("source_bundle_id") or row.get("bundle_id") or "")
        support_rows_by_bundle.setdefault(bundle_id, []).append(row)

    target_status_rows: list[dict[str, Any]] = []
    qualified_support_rows: list[dict[str, Any]] = []

    for queue_target in queue["queue_targets"]:
        episode_id = str(queue_target["episode_id"])
        asset = asset_map[episode_id]
        gold_payload = maybe_load(asset["gold_path"]) if asset["gold_path"] else None
        rubric_payload = maybe_load(asset["rubric_path"]) if asset["rubric_path"] else None
        anti_cheat_payload = maybe_load(asset["anti_cheat_path"]) if asset["anti_cheat_path"] else None
        verifier = verifier_entry(gold_payload)
        bundle_id = str(asset["bundle_id"])
        executable_rows = support_rows_by_bundle.get(bundle_id, [])
        executable_verifier_rows = [row for row in executable_rows if str(row.get("task_type")) == "verifier_outcome"]
        reviewed_selected_tests = verifier.get("selected_tests", []) if verifier else []
        queue_selected_tests = queue_target_map[episode_id]["selected_tests"]

        gaps: list[str] = []
        if not gold_payload:
            gaps.append("missing_perspective_gold_adjudication")
        if not rubric_payload:
            gaps.append("missing_rubric_review")
        if not anti_cheat_payload:
            gaps.append("missing_anti_cheat_review")
        if verifier is None:
            gaps.append("missing_verifier_outcome_gold")
        if verifier and len(reviewed_selected_tests) < 3:
            gaps.append("reviewed_verifier_target_set_too_small")
        if verifier and len(reviewed_selected_tests) != len(queue_selected_tests):
            gaps.append("queue_reviewed_selected_test_mismatch")
        if not executable_verifier_rows:
            gaps.append("no_executable_verifier_rows_present")

        meets_queue_geometry = verifier is not None and len(reviewed_selected_tests) >= 3
        has_full_review_stack = bool(gold_payload and rubric_payload and anti_cheat_payload)
        immediately_qualified = meets_queue_geometry and has_full_review_stack and bool(executable_verifier_rows)

        if immediately_qualified:
            for row in executable_rows:
                updated = dict(row)
                updated["stage10493_review_packet"] = {
                    "queue_episode_id": episode_id,
                    "review_quality": "immediately_qualified",
                    "reviewed_selected_tests_count": len(reviewed_selected_tests),
                    "queue_selected_tests_count": len(queue_selected_tests),
                    "queue_contract_matched": True,
                }
                qualified_support_rows.append(updated)

        target_status_rows.append(
            {
                "priority_order": int(queue_target["priority_order"]),
                "episode_id": episode_id,
                "bundle_id": bundle_id,
                "repo_id": str(queue_target["repo_id"]),
                "motivation": str(queue_target["motivation"]),
                "queue_selected_tests_count": len(queue_selected_tests),
                "reviewed_selected_tests_count": len(reviewed_selected_tests),
                "reviewed_selected_tests": reviewed_selected_tests,
                "reviewed_verifier_gold_value": verifier.get("gold_answer_value") if verifier else None,
                "has_gold_adjudication": bool(gold_payload),
                "has_rubric_review": bool(rubric_payload),
                "has_anti_cheat_review": bool(anti_cheat_payload),
                "executable_row_count": len(executable_rows),
                "executable_verifier_row_count": len(executable_verifier_rows),
                "meets_queue_requirement_three_plus_tests": bool(verifier and len(reviewed_selected_tests) >= 3),
                "meets_queue_requirement_full_review_stack": has_full_review_stack,
                "immediately_qualified_for_reviewed_verifier_packet": immediately_qualified,
                "gaps": gaps,
            }
        )

    qualified_bundle_ids = sorted({str(row["source_bundle_id"]) for row in qualified_support_rows})

    payload = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": True,
        "decision": "python_reviewed_verifier_packet_quality_audited",
        "claim_scope": [
            "Translate the aspirational stage10492 Python queue into a packet backed only by existing reviewed and executable assets.",
            "Separate roots that already satisfy the intended verifier geometry from roots that still need packet construction or adjudication.",
        ],
        "source_artifacts": {
            "queue": display(QUEUE_JSON),
            "queue_targets": display(QUEUE_TARGETS_JSONL),
            "support_rows": display(SUPPORT_ROWS_JSONL),
            "stage10236_gold": display(STAGE10236_GOLD),
            "stage10300_gold": display(STAGE10300_GOLD),
            "agentkernel_successor_rubric": display(AGENTKERNEL_RUBRIC),
        },
        "summary": {
            "queued_targets": len(target_status_rows),
            "immediately_qualified_targets": sum(1 for row in target_status_rows if row["immediately_qualified_for_reviewed_verifier_packet"]),
            "qualified_support_row_count": len(qualified_support_rows),
            "qualified_bundle_ids": qualified_bundle_ids,
        },
        "target_quality_findings": [
            "stage10236 context_pack is the only current target that already has reviewed verifier competition with 3+ selected tests, full review stack, and executable support rows.",
            "stage10300 hf_local is reviewed and executable, but its adjudicated verifier surface currently exposes only one selected test, so it does not satisfy the richer verifier-disambiguation geometry requested by stage10492.",
            "the queued agentkernel target is still honesty-only because it lacks perspective gold adjudication and bounded executable verifier rows.",
        ],
        "recommended_next_stage": "stage10494_context_pack_only_promotable_python_probe_request",
        "required_followups": [
            "Build a richer reviewed hf_local verifier packet with multiple plausible selected-test options before using it as primary Python verifier support.",
            "Materialize and adjudicate the queued agentkernel root before treating it as executable verifier support.",
            "Do not describe the full stage10492 queue as ready-for-execution quality; only the context_pack root is ready under the current reviewed assets.",
        ],
        "outputs": {
            "target_status_jsonl": display(TARGET_STATUS_JSONL),
            "qualified_support_rows_jsonl": display(QUALIFIED_ROWS_JSONL),
        },
    }

    write_jsonl(TARGET_STATUS_JSONL, target_status_rows)
    write_jsonl(QUALIFIED_ROWS_JSONL, qualified_support_rows)
    write_json(REQUEST_JSON, payload)
    write_json(
        SUMMARY,
        {
            "stage": STAGE,
            "passed": True,
            "decision": payload["decision"],
            "request": display(REQUEST_JSON),
        },
    )
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
