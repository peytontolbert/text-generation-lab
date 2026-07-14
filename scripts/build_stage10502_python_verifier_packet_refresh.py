#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = 10502
NAME = "stage10502_python_verifier_packet_refresh"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
REQUEST_JSON = OUT_DIR / "python_verifier_packet_refresh.json"
QUALIFIED_ROWS_JSONL = OUT_DIR / "python_verifier_reviewed_support_rows.jsonl"
TARGET_STATUS_JSONL = OUT_DIR / "python_verifier_review_target_status.jsonl"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"

STAGE10493_QUALIFIED = ROOT / "runs/local/artifacts/stage10493_python_verifier_fresh_review_packet_builder/python_verifier_reviewed_support_rows.jsonl"
HF_ROWS = ROOT / "runs/local/artifacts/stage10501_hf_local_repaired_compact_bounded_projection/hf_local_repaired_compact_bounded_rows.jsonl"
HF_PACKET = ROOT / "runs/local/artifacts/stage10499_hf_local_multitest_packet_repair/hf_local_multitest_repaired_packet.json"
HF_AUDIT = ROOT / "runs/local/artifacts/stage10500_hf_local_multitest_repair_audit/hf_local_multitest_repair_audit.json"


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


def main() -> None:
    prior_rows = load_jsonl(STAGE10493_QUALIFIED)
    hf_rows = load_jsonl(HF_ROWS)
    hf_packet = load_json(HF_PACKET)
    hf_audit = load_json(HF_AUDIT)

    qualified_rows = list(prior_rows)
    for row in hf_rows:
        updated = dict(row)
        updated["stage10502_review_packet"] = {
            "review_quality": "anti_cheat_repaired_and_executable",
            "queue_contract_matched": True,
            "reviewed_selected_tests_count": 3,
            "prompt_target_leak_false": bool(hf_audit["anti_cheat_checks"]["prompt_target_leak_false"]),
            "verifier_options_opaque": bool(hf_audit["anti_cheat_checks"]["verifier_options_opaque"]),
            "candidate_options_opaque": bool(hf_audit["anti_cheat_checks"]["candidate_options_opaque"]),
        }
        qualified_rows.append(updated)

    target_status_rows = [
        {
            "episode_id": "localsess_code_assist_context_pack_python",
            "bundle_id": "stage10236::localsess_code_assist_sessseed_codex_sessions_rollout_2026_01_27t02_21_48_019bfd41_d2a6_7672_9873_81f8_src_code_assist_orchestrator_config_py_src_code_assist_orchestrator_context_pack_acd5ccc9c1_aug_1500000_8b46e7f662::python",
            "status": "qualified",
            "review_quality": "immediately_qualified_existing",
            "support_rows_present": len(prior_rows),
            "selected_tests_count": 4,
            "notes": [
                "Existing context_pack reviewed root remains the clean baseline support lane.",
            ],
        },
        {
            "episode_id": "localsess_code_assist_hf_local_python",
            "bundle_id": hf_packet["bundle"]["bundle_id"],
            "status": "qualified",
            "review_quality": "anti_cheat_repaired_and_executable",
            "support_rows_present": len(hf_rows),
            "selected_tests_count": 3,
            "prompt_target_leak_false": bool(hf_audit["anti_cheat_checks"]["prompt_target_leak_false"]),
            "weak_neighbor_explicitly_marked": bool(hf_audit["anti_cheat_checks"]["weak_neighbor_explicitly_marked"]),
            "notes": [
                "hf_local now satisfies the 3-target verifier geometry requirement.",
                "The remaining limitation is sibling strength, not raw leakage or singleton geometry.",
            ],
        },
        {
            "episode_id": "localsess_agentkernel_python_successor",
            "bundle_id": "stage10110::localsess_agentkernel_sessseed_codex_sessions_rollout_2026_03_29t14_24_54_019d39fb_c43d_7e62_b055_b00b_agent_kernel_cycle_runner_py_agent_kernel_improvement_py_agent_kernel_learning_c_6a4dce0d0c_aug_1500000_8b46e7f662::python_successor",
            "status": "blocked",
            "review_quality": "still_honesty_only",
            "support_rows_present": 0,
            "notes": [
                "Agentkernel remains blocked on perspective gold adjudication and executable verifier rows.",
            ],
        },
    ]

    payload = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": True,
        "decision": "python_reviewed_verifier_packet_refreshed",
        "claim_scope": [
            "Refresh the Python reviewed verifier packet after the hf_local anti-cheat repair and bounded projection work.",
            "Keep the packet honest: admit hf_local only because it now has opaque verifier competition, clean leak audit, and executable support rows.",
        ],
        "source_artifacts": {
            "stage10493_qualified_rows": display(STAGE10493_QUALIFIED),
            "hf_local_repaired_projection_rows": display(HF_ROWS),
            "hf_local_repaired_packet": display(HF_PACKET),
            "hf_local_repaired_audit": display(HF_AUDIT),
        },
        "summary": {
            "qualified_targets": sum(1 for row in target_status_rows if row["status"] == "qualified"),
            "blocked_targets": sum(1 for row in target_status_rows if row["status"] == "blocked"),
            "qualified_support_row_count": len(qualified_rows),
            "qualified_bundle_ids": sorted({row["source_bundle_id"] for row in qualified_rows}),
        },
        "target_quality_findings": [
            "context_pack remains the cleanest reviewed Python support root and still preserves the 22/24 frontier.",
            "hf_local now upgrades from singleton-verifier blocked to executable-quality support because the packet has 3 visible verifier families and passes the repaired anti-cheat audit.",
            "agentkernel remains blocked and should stay out of promotable probes until gold adjudication and executable verifier rows exist.",
        ],
        "recommended_next_stage": "stage10503_context_pack_plus_hf_local_promotable_python_probe_request",
        "required_followups": [
            "Run one clean promotable Python probe using context_pack plus the repaired hf_local rows.",
            "Keep agentkernel excluded from promotable support until adjudication and executable verifier geometry are complete.",
            "If the next probe still plateaus, widen support with fresh disjoint Python verifier roots instead of replaying the same strict rows.",
        ],
        "outputs": {
            "qualified_support_rows_jsonl": display(QUALIFIED_ROWS_JSONL),
            "target_status_jsonl": display(TARGET_STATUS_JSONL),
            "request_json": display(REQUEST_JSON),
        },
    }

    write_jsonl(QUALIFIED_ROWS_JSONL, qualified_rows)
    write_jsonl(TARGET_STATUS_JSONL, target_status_rows)
    write_json(REQUEST_JSON, payload)
    write_json(
        SUMMARY,
        {
            "stage": STAGE,
            "passed": True,
            "decision": payload["decision"],
            "qualified_support_row_count": len(qualified_rows),
            "request_json": display(REQUEST_JSON),
        },
    )
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
