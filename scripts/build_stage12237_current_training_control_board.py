#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12237_current_training_control_board"
OUT = ROOT / "runs/local/artifacts" / STAGE
SUMMARY = ROOT / "runs/summaries" / f"{STAGE}.json"


def load_summary(stage: str) -> dict[str, Any]:
    path = ROOT / "runs/summaries" / f"{stage}.json"
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def metric(stage: str, key: str, default: Any = None) -> Any:
    return load_summary(stage).get(key, default)


def main() -> int:
    s12216 = load_summary("stage12216_normalized_verifier_observation_dataset")
    s12229 = load_summary("stage12229_patch_trace_projection_qc")
    s12232 = load_summary("stage12232_controlled_fixture_projection_qc")
    s12233 = load_summary("stage12233_external_acquisition_blocker_decision")
    s12234 = load_summary("stage12234_plateau_mechanism_audit")
    s12235 = load_summary("stage12235_patch_trace_task_routing_contract")
    s12236 = load_summary("stage12236_stage11977_candidate_audit")

    lanes = {
        "external_patch_trace_repair": {
            "status": "blocked",
            "training_allowed": False,
            "available_qc_projection_rows": s12229.get("admitted_count", 0),
            "reason": "No comparable external FAIL_TO_PASS repair supply under strict same-verifier gates.",
            "next_allowed_work": [
                "acquire new locally hydratable external roots",
                "materialize before / before_plus_patch / after verifier triples",
                "reject missing-test, ENV, dependency, network, syntax-only, or weak-verifier rows",
            ],
        },
        "controlled_fixture_curriculum": {
            "status": "audit_only",
            "training_allowed": False,
            "available_qc_projection_rows": s12232.get("admitted_count", 0),
            "reason": "Controlled fixtures are useful for protocol smoke tests, but they are not external maintainer repair evidence.",
            "next_allowed_work": [
                "build a separate curriculum gate",
                "never count these rows toward external repair or source-heldout floors",
            ],
        },
        "verifier_observation_auxiliary": {
            "status": "conversion_audit_allowed",
            "training_allowed": False,
            "available_rows": s12216.get("row_count", s12216.get("normalized_rows")),
            "reason": "Rows can teach verifier/status policy only if converted without claiming Level-3 patch traces.",
            "next_allowed_work": [
                "build conversion contract",
                "split ENV/dependency/timeouts from true verifier observations",
                "map only safe rows to status/stop/next-action auxiliary targets",
            ],
        },
        "transition_route_confirmation": {
            "status": "audit_allowed",
            "training_allowed": False,
            "reason": "Stage12099-style routing must be option-permutation and sealed-slice confirmed before it becomes a product baseline.",
            "next_allowed_work": [
                "confirm route components",
                "check option-permutation stability",
                "check sealed/root-disjoint transition slice availability",
            ],
        },
    }

    payload = {
        "stage": STAGE,
        "decision": "training_blocked_but_audit_and_conversion_work_allowed",
        "plateau_assessment": {
            "is_plateau": True,
            "plateau_type": "data_protocol_plateau_not_activity_plateau",
            "primary_mechanisms": [
                "external comparable repair supply is effectively zero",
                "closed-loop patch-trace projections exist but loss masks must stay disabled",
                "controlled fixtures and verifier observations are useful auxiliary lanes but not frontier repair proof",
                "next model progress needs either sealed route confirmation or new admitted repair roots, not more tiny support probes",
            ],
        },
        "lane_control": lanes,
        "hard_training_blocks": {
            "stage12233": s12233.get("hard_training_blockers"),
            "stage12235_training_allowed": s12235.get("training_allowed"),
            "stage12236_decision": s12236.get("decision"),
        },
        "progress_since_stage12213": {
            "verifier_observation_rows": lanes["verifier_observation_auxiliary"]["available_rows"],
            "external_patch_trace_projection_rows_qc_passed": lanes["external_patch_trace_repair"]["available_qc_projection_rows"],
            "controlled_fixture_projection_rows_qc_passed": lanes["controlled_fixture_curriculum"]["available_qc_projection_rows"],
            "patch_trace_routing_contract_ready": bool(s12235),
            "stale_stage11977_lead_closed": s12236.get("decision") == "stage11977_blocked_no_external_repair_candidate",
        },
        "next_stage_queue": [
            {
                "stage": "stage12238_verifier_observation_auxiliary_conversion_audit",
                "allowed": True,
                "training_allowed": False,
                "purpose": "Convert Stage12216 only into safe verifier/status auxiliary candidates, not Level-3 repair rows.",
            },
            {
                "stage": "stage12239_stage12099_route_confirmation_audit",
                "allowed": True,
                "training_allowed": False,
                "purpose": "Decide whether the routed transition policy is stable enough to keep as a non-training baseline.",
            },
            {
                "stage": "stage12240_external_repair_acquisition_request_v2",
                "allowed": True,
                "training_allowed": False,
                "purpose": "Issue stricter acquisition requests for genuinely comparable external repair roots.",
            },
        ],
        "do_not_run": [
            "No patch_trace training on Stage12228/12231 rows.",
            "No training on Stage11977.",
            "No controlled fixture rows counted as source-heldout or external repair progress.",
            "No broad support probe unless it declares the exact frontier metric and uses admitted non-leaky rows.",
        ],
        "claim_boundary": "Control board only. This stage authorizes audits/conversion planning, not training.",
        "source_stages": [
            "stage12216_normalized_verifier_observation_dataset",
            "stage12229_patch_trace_projection_qc",
            "stage12232_controlled_fixture_projection_qc",
            "stage12233_external_acquisition_blocker_decision",
            "stage12234_plateau_mechanism_audit",
            "stage12235_patch_trace_task_routing_contract",
            "stage12236_stage11977_candidate_audit",
        ],
        "training_allowed": False,
    }

    OUT.mkdir(parents=True, exist_ok=True)
    write_json(OUT / "current_training_control_board.json", payload)
    write_json(SUMMARY, payload)
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
