#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STAGE = 10560
NAME = "stage10560_canonical_short_target_successor_request"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
SUMMARY_PATH = OUT_DIR / "canonical_short_target_successor_request.json"
SUMMARY_REF = ROOT / "runs/summaries" / f"{NAME}.json"


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
        "decision": "strict_successor_target_interface_rebuild_required",
        "claim_scope": [
            "Request artifact for the next strict successor rebuild after stage10557/10558 showed that preservation support alone is not enough.",
            "The target of the rebuild is the strict 54-row multilingual successor slice, not the repaired 24-row canary.",
            "This is a dataset/eval interface request, not a training result.",
        ],
        "problem_statement": {
            "current_strict_surface_failure": "Both 100M and Gemma score 0/54 exact and semantic on the current generation-only strict successor surface.",
            "current_canary_status": "The old reviewed v2.7 bounded-choice canary remains 22/24 and is still useful as a regression gate.",
            "root_cause": "The strict successor rows use long source-backed opaque target strings with no candidate-option contract, making exact generation a poor interface and bounded semantic scoring unavailable.",
        },
        "requested_rebuild": {
            "surface_name": "canonical_short_target_successor_v1",
            "requirements": [
                "Reuse the stage10555 strict rows and root-heldout split discipline",
                "Map each strict target to a short canonical exact output such as a reversible code or compact canonical token sequence",
                "Store a reversible target-map artifact that links canonical outputs back to the source-backed target text",
                "Ensure the visible prompt does not contain the canonical output code directly",
                "Preserve target-subtype coverage across decisive_evidence_top1, retrieve_answer_abstain, and verifier_outcome_masked",
                "Emit an anti-cheat audit specifically for prompt-to-canonical-target leakage",
                "Emit both exact scoring on canonical outputs and semantic scoring on the reconstructed source-backed values",
            ],
        },
        "promotion_gate_for_next_run": [
            "No regression on the repaired 24-row v2.7 canary",
            "Improvement over 0/54 on the rebuilt strict successor slice",
            "Same-manifest Gemma comparison on the rebuilt strict successor slice",
            "Leak audit clean for canonical target codes",
        ],
        "non_goals": [
            "This request does not broaden the benchmark beyond the existing strict successor roots",
            "This request does not replace the maintainer-grade reviewed v2.7 eval",
            "This request does not claim harness-level completion",
        ],
    }
    write_json(SUMMARY_PATH, payload)
    write_json(SUMMARY_REF, payload)
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
