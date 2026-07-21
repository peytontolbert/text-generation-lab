#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12234_plateau_mechanism_audit"
OUT = ROOT / "runs/local/artifacts" / STAGE
SUMMARY = ROOT / "runs/summaries" / f"{STAGE}.json"


def load(path: str) -> dict[str, Any]:
    p = ROOT / path
    return json.loads(p.read_text()) if p.exists() else {}


def write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> int:
    s12216 = load("runs/summaries/stage12216_normalized_verifier_observation_dataset.json")
    s12229 = load("runs/summaries/stage12229_patch_trace_projection_qc.json")
    s12232 = load("runs/summaries/stage12232_controlled_fixture_projection_qc.json")
    s12233 = load("runs/summaries/stage12233_external_acquisition_blocker_decision.json")
    payload = {
        "stage": STAGE,
        "decision": "plateau_is_external_repair_supply_and_training_protocol_not_more_scoring",
        "evidence": {
            "verifier_observation_support_rows": s12216.get("row_count"),
            "external_patch_trace_projection_rows_qc_passed": s12229.get("admitted_count"),
            "controlled_curriculum_projection_rows_qc_passed": s12232.get("admitted_count"),
            "external_repair_training_allowed": s12233.get("training_allowed"),
            "external_acquisition_blockers": s12233.get("hard_training_blockers"),
        },
        "plateau_mechanisms": [
            {
                "mechanism": "external_comparable_repair_supply_zero",
                "symptom": "no source-heldout/external before-fail after-pass patch roots under strict gates",
                "do_not_do": "train on syntax-only, test-added, or weak-verifier rows",
                "productive_move": "new source acquisition or locally hydratable repo episodes with same selected verifier across before/patch/after",
            },
            {
                "mechanism": "projection_plumbing_ahead_of_training_authority",
                "symptom": "Stage12228/12231 projections exist but loss masks disabled",
                "do_not_do": "enable losses before task routing and supply floors",
                "productive_move": "define patch_trace task routing/adapters and train only after data floor",
            },
            {
                "mechanism": "controlled_curriculum_not_external_generalization",
                "symptom": "40 balanced controlled rows exist but are toy one-function fixtures",
                "do_not_do": "claim broad maintainer progress from controlled fixtures",
                "productive_move": "use as a curriculum/protocol smoke only after a separate gate",
            },
        ],
        "real_progress_conditions": [
            "external comparable patch-trace rows >= 25",
            "external fail-to-pass rows >= 15",
            "non-python external patch-trace rows >= 10",
            "patch_trace task routing implemented without regressing Stage11924/12099 protected gates",
            "heldout/source-heldout eval slice assembled before promotion",
        ],
        "active_subagents": {
            "019f6b72-8e50-7be1-a6bd-e2dc4b6c0b26": "alternate_source_pool_mining",
            "019f6b72-ae10-7b32-bb75-cab474288860": "gate_relaxation_or_split_audit",
            "019f6b72-c61b-7122-90b7-0db64045297a": "alternative_training_progress_plan",
        },
        "training_allowed": False,
        "claim_boundary": "Plateau audit only. This stage does not authorize training.",
    }
    OUT.mkdir(parents=True, exist_ok=True)
    write_json(OUT / "plateau_mechanism_audit.json", payload)
    write_json(SUMMARY, payload)
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
