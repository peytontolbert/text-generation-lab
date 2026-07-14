#!/usr/bin/env python3
"""Decision artifact after Stage11965 routed audit."""

from __future__ import annotations

import json
import shutil
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "runs/local/artifacts"
SUMMARIES = ROOT / "runs/summaries"
STAGE = 11966
NAME = "stage11966_transition_status_control_decision"
OUT = ART / NAME
SUMMARY = OUT / "transition_status_control_decision.json"
AUDIT = ART / "stage11965_transition_status_control_postrun_audit/transition_status_control_postrun_audit.json"


def now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def rel(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> None:
    audit = json.loads(AUDIT.read_text(encoding="utf-8"))
    scoreboard = audit.get("scoreboard") or {}
    base = scoreboard.get("stage11924_selected_transition") or {}
    status = scoreboard.get("stage11964_status_control") or {}
    artifact = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now(),
        "decision": "reject_stage11964_keep_stage11924_transition_frontier",
        "selected_transition_frontier": {
            "stage": "stage11924_transition_listwise_head_only_probe",
            "runtime": "runs/local/artifacts/stage11924_transition_listwise_head_only_probe/runtime_model/runtime_model_bundle.json",
            "scorer": "encoder_option_retrieval_semantic_candidate_head",
            "old_transition_640": base.get("old_transition_640"),
        },
        "rejected_candidate": {
            "stage": "stage11964_transition_status_control_probe",
            "runtime": "runs/local/artifacts/stage11964_transition_status_control_probe/runtime_model/runtime_model_bundle.json",
            "scorer": "encoder_option_retrieval_semantic_plus_transition_status_head",
            "old_transition_640": status.get("old_transition_640"),
            "status_validation": status.get("status_validation"),
            "status_strict_eval": status.get("status_strict_eval"),
            "aug_validation": status.get("aug_validation"),
            "aug_strict_eval": status.get("aug_strict_eval"),
        },
        "protected_gates_status": {
            "filtered_strict": status.get("filtered_strict"),
            "filtered_validation": status.get("filtered_validation"),
            "old_canary_strict": status.get("old_canary_strict"),
            "old_canary_validation": status.get("old_canary_validation"),
            "residual_bank": status.get("residual_bank"),
            "source_heldout_smoke": status.get("source_heldout_smoke"),
        },
        "finding": [
            "A separate transition status/control head fit train support better but failed heldout transfer.",
            "Old transition score regressed from 364/640 to 188/640.",
            "Status/control validation regressed from 64/124 to 6/124 and strict from 79/178 to 13/178.",
            "Compact gates stayed preserved, so the failure is isolated to transition scorer generalization rather than global model damage.",
        ],
        "root_cause_interpretation": [
            "Counterfactual status augmentation is overpowering real execution evidence and inducing label/status priors.",
            "The current 120 independent roots are insufficient for status/control transfer despite 5,780 projected rows.",
            "More head variants on the same augmented rows are unlikely to help without fresh executable roots and stronger validation gating.",
        ],
        "stop_conditions": [
            "Do not promote Stage11964.",
            "Do not rerun status/control head on Stage11958 with only hyperparameter changes.",
            "Do not count Stage11957 counterfactual rows as independent root scale.",
        ],
        "next_program": {
            "stage": "stage11967_transition_root_250_supply_contract",
            "goal": "Define and enforce a clean Transition-Root-250 package before any further transition training.",
            "minimum_requirements": {
                "independent_roots_total": 250,
                "python_roots": 50,
                "rust_roots": 50,
                "c_cpp_roots": 50,
                "web_cap_fraction": 0.40,
                "fail_to_pass_records": 50,
                "pass_to_pass_records": 100,
                "pass_current_build_records": 40,
                "pass_current_build_and_run_records": 40,
                "insufficient_evidence_records": 40,
                "not_exercised_records": 40,
                "verifier_removed_cap": "capped; not allowed to dominate",
            },
            "required_transition_shape": [
                "baseline observed",
                "relevant artifact found",
                "verifier/test selected",
                "evidence sufficiency judged",
                "patch or no-patch decision",
                "verifier transition predicted",
                "continue/stop decision",
            ],
            "training_gate_before_long_run": [
                "evaluate every 100-200 steps on old 640, v2 validation/strict, source-heldout smoke, and status/control eval",
                "early stop if old 640 drops below 350",
                "early stop if train improves while validation drops for two checkpoints",
                "report confusion by semantic status, not just answer label",
            ],
        },
        "milestone_decomposition_note": "Add milestone_decomposition_policy as a separate future projection lane after transition baseline stabilizes; do not mix it into the rejected Stage11964 line.",
        "source_artifacts": {
            "audit": rel(AUDIT),
            "stage11963_request": "runs/local/artifacts/stage11963_transition_status_control_probe_request/transition_status_control_probe_request.json",
            "stage11964_runtime": "runs/local/artifacts/stage11964_transition_status_control_probe/runtime_model/runtime_model_bundle.json",
        },
        "outputs": {"summary": rel(SUMMARY)},
    }
    write_json(SUMMARY, artifact)
    SUMMARIES.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(SUMMARY, SUMMARIES / f"{NAME}.json")
    print(json.dumps({"decision": artifact["decision"], "selected": artifact["selected_transition_frontier"], "rejected": artifact["rejected_candidate"], "next_stage": artifact["next_program"]["stage"]}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
