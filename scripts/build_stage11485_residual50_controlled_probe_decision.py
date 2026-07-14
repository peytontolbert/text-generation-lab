#!/usr/bin/env python3
from __future__ import annotations

import json
import shutil
import time
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "runs/local/artifacts"
SUMMARIES = ROOT / "runs/summaries"

STAGE = 11485
NAME = "stage11485_residual50_controlled_probe_decision"
OUT = ART / NAME
SUMMARY = OUT / "residual50_controlled_probe_decision.json"

POSTRUN = ART / "stage11484_residual50_controlled_probe_postrun_audit/residual50_controlled_probe_postrun_audit.json"
REQUEST = ART / "stage11482_residual50_controlled_probe_request/residual50_controlled_probe_request.json"
READINESS = ART / "stage11481_residual50_ready_package_with_rust_counters/residual50_ready_package_with_rust_counters.json"


def now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> None:
    postrun = load_json(POSTRUN)
    request = load_json(REQUEST)
    readiness = load_json(READINESS)
    product = (postrun.get("scored") or {}).get("encoder_option_retrieval") or {}
    gates = postrun.get("promotion_gates") or {}
    payload = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now(),
        "passed": True,
        "decision": "reject_stage11483_do_not_promote",
        "classification": "controlled_negative_result",
        "why_not_progress": {
            "residual_bank": {
                "required": ">5/10",
                "actual": f"{(product.get('residual_bank') or {}).get('correct')}/10",
            },
            "filtered_strict": {
                "required": "22/22",
                "actual": f"{(product.get('filtered_strict') or {}).get('correct')}/22",
            },
            "old_canary_strict": {
                "required": "23/23",
                "actual": f"{(product.get('old_canary_strict') or {}).get('correct')}/23",
            },
            "failed_gates": [gate for gate, ok in gates.items() if ok is not True],
        },
        "what_was_falsified": [
            "Adding the full Residual-50 train-support analogue package with the current CE+contrast objective is not sufficient to move the frozen residual bank.",
            "The same intervention over-pushes evidence-citation predictions toward F-like roles and regresses protected strict rows.",
            "The issue is not solved by semantic-candidate-head scoring or decoder-first-step scoring on this runtime.",
        ],
        "next_experiment_contract": {
            "hypothesis_id": "H_objective_or_sampler_overpush",
            "single_changed_variable": "objective/sampling, not new data",
            "recommended_intervention": "train a scorer-head-only or lower-LR encoder run on the same Stage11481 package with reduced evidence-role oversampling and explicit preservation weighting for protected evidence-citation B rows",
            "must_hold_constant": [
                "Stage11481 Residual-50 data package",
                "Stage11444 initialization",
                "product scorer encoder_option_retrieval",
                "protected validation/strict/residual splits",
            ],
            "promotion_requires": [
                "old canary strict 23/23",
                "filtered strict 22/22",
                "filtered validation >=20/22",
                "old validation >=21/23",
                "residual bank >=6/10",
                "full bounded-choice coverage",
            ],
            "kill_condition": "If objective/sampler-only runs preserve strict but keep residual at 5/10 twice, stop training variants and implement a direct same-root listwise scorer objective.",
        },
        "source_artifacts": {
            "postrun": rel(POSTRUN),
            "request": rel(REQUEST),
            "readiness": rel(READINESS),
        },
        "outputs": {"summary": rel(SUMMARY)},
    }
    write_json(SUMMARY, payload)
    SUMMARIES.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(SUMMARY, SUMMARIES / f"{NAME}.json")
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
