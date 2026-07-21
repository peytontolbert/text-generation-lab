#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12235_patch_trace_task_routing_contract"
OUT = ROOT / "runs/local/artifacts" / STAGE
SUMMARY = ROOT / "runs/summaries" / f"{STAGE}.json"


def load(path: str) -> dict[str, Any]:
    p = ROOT / path
    return json.loads(p.read_text()) if p.exists() else {}


def write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> int:
    s12229 = load("runs/summaries/stage12229_patch_trace_projection_qc.json")
    s12232 = load("runs/summaries/stage12232_controlled_fixture_projection_qc.json")
    contract = {
        "stage": STAGE,
        "decision": "patch_trace_task_routing_contract_ready_training_still_blocked",
        "source_stages": [
            "stage12229_patch_trace_projection_qc",
            "stage12232_controlled_fixture_projection_qc",
        ],
        "input_rows_available": {
            "external_projection_qc_rows": s12229.get("admitted_count"),
            "controlled_curriculum_qc_rows": s12232.get("admitted_count"),
        },
        "routing_contract": {
            "patch_trace_next_action": {
                "route_to_existing_task_type": "transition_next_action",
                "allowed_aux_sources": [
                    "encoder_option_retrieval_transition_next_action_head",
                    "encoder_option_retrieval_semantic_plus_transition_next_action_head",
                ],
                "status": "route_defined_but_loss_disabled_until_supply_gate",
                "risk": "next_action was historically interference-prone; require protected gate replay before enabling",
            },
            "patch_trace_verifier_transition": {
                "route_to_existing_task_type": "transition_verifier_transition",
                "allowed_aux_sources": [
                    "encoder_option_retrieval_transition_status_head",
                    "encoder_option_retrieval_semantic_plus_transition_status_head",
                ],
                "status": "route_defined_but_loss_disabled_until_supply_gate",
                "risk": "must preserve phase tuple; do not collapse before/before_plus_patch/after to one status in prompt",
            },
            "patch_trace_stop_continue": {
                "route_to_existing_task_type": "transition_continue_or_stop",
                "allowed_aux_sources": [
                    "encoder_option_retrieval_transition_status_head",
                    "encoder_option_retrieval_semantic_candidate_head",
                ],
                "status": "route_defined_but_loss_disabled_until_supply_gate",
                "risk": "STOP is only valid for comparable direct repair; weak/pass-to-pass should continue or abstain",
            },
            "patch_trace_patch_apply": {
                "route_to_existing_task_type": None,
                "allowed_aux_sources": [],
                "status": "disabled_requires_new_patch_apply_head_or_explicit_adapter",
                "risk": "generic verifier/status heads may learn syntax/apply shortcuts instead of maintainer judgment",
            },
            "patch_trace_patch_judgment": {
                "route_to_existing_task_type": None,
                "allowed_aux_sources": [],
                "status": "disabled_requires_new_patch_judgment_head_or_explicit_adapter",
                "risk": "mixes repair proof, safe refactor, weak verifier, and test-added shortcut labels; high shortcut risk",
            },
        },
        "minimum_enablement_gate": {
            "external_comparable_patch_trace_rows": 25,
            "external_fail_to_pass_rows": 15,
            "non_python_external_rows": 10,
            "controlled_curriculum_rows_can_be_enabled_only_under_separate_gate": True,
            "protected_gates_required": [
                "Stage11924 old transition >= 364/640",
                "Stage12099 routed transition >= 375/640 if route is used",
                "compact canary/residual gates unchanged",
                "option permutation stability audit attached",
            ],
        },
        "trainer_change_recommendation": {
            "do_now": "no trainer code change; rows remain loss_mask disabled",
            "later": "add explicit task-type aliasing from patch_trace_* to transition_* only after supply gate; add separate heads for patch_apply and patch_judgment if those losses are ever enabled",
        },
        "training_allowed": False,
        "claim_boundary": "Routing contract only. No training authorized because data floors are not met.",
    }
    OUT.mkdir(parents=True, exist_ok=True)
    write_json(OUT / "patch_trace_task_routing_contract.json", contract)
    write_json(SUMMARY, contract)
    print(json.dumps(contract, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
