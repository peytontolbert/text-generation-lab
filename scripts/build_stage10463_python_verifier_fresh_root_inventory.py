#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STAGE = 10463
NAME = "stage10463_python_verifier_fresh_root_inventory"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
OUT_JSON = OUT_DIR / "python_verifier_fresh_root_inventory.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def now_utc() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def main() -> None:
    payload = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": True,
        "decision": "python_verifier_fresh_root_supply_inventory_ready",
        "current_live_residual": {
            "row_id": "stage10119::localsess_repository_library_sessseed_codex_sessions_rollout_2025_11_28t20_02_25_019acc0f_4bd7_77f2_b15f_3b0c_models_mirrormind_init_py_models_mirrormind_context_py_models_mirrormind_coordin_fd8013631e_aug_1500000_8b46e7f662::python::verifier_outcome::reviewed_v27_compact",
            "target": "B",
            "predicted": "C",
            "task_boundary": "multiple plausible tests are visible, but only one verifier target should move",
        },
        "candidate_root_families": [
            {
                "bundle_id": "stage10327::localsess_repository_library_sessseed_codex_sessions_rollout_2025_11_29t02_41_34_019acd7c_b80e_7880_9f45_f500_models_mirrormind_coordinator_py_models_mirrormind_domain_py_models_mirrormind_m_3b079208d1_aug_1500000_8b46e7f662::python",
                "role": "closest disjoint verifier-only family",
                "available_rows": 4,
                "why_useful": "same broad subsystem as the live miss but train-only and already separated from Python citation contamination",
                "promotion_status": "train_support_only",
            },
            {
                "bundle_id": "stage10119::localsess_repository_library_sessseed_codex_sessions_rollout_2025_11_26t00_55_44_019abda8_c0d8_7803_8a77_1e0f_scripts_universe_build_py_64d2cf209b_aug_1500000_8b46e7f662::python",
                "role": "fresh repo family candidate",
                "available_rows": 1,
                "why_useful": "different repository family and single clear verifier target; useful as a seed for new root expansion rather than enough by itself",
                "promotion_status": "insufficient_count_for_curriculum_alone",
            },
            {
                "bundle_id": "stage10300::localsess_code_assist_sessseed_codex_sessions_rollout_2026_01_26t23_27_57_019bfca2_aa35_7502_b929_649a_src_code_assist_agents_hf_local_py_src_code_assist_agents_hf_local_planner_py_sr_3fb1ce61a2_aug_1500000_8b46e7f662::python",
                "role": "non-verifier contamination source",
                "available_rows": 1,
                "why_useful": "helpful for code-assist supply generally, but prior probes show mixing this family with citation support can regress unrelated Python rows",
                "promotion_status": "exclude_from_next_verifier_fresh_root_builder",
            },
        ],
        "builder_requirements": [
            "create at least 6 new root-disjoint Python verifier roots",
            "each root should expose 3 or more plausible tests or verification targets",
            "at least one tempting wrong integration-style target must be visible",
            "the gold verifier should depend on evidence, not on filename priors or candidate order",
        ],
    }
    write_json(OUT_JSON, payload)
    write_json(SUMMARY, {"stage": STAGE, "passed": True, "inventory": str(OUT_JSON.relative_to(ROOT))})
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
