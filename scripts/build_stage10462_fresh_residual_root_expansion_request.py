#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STAGE = 10462
NAME = "stage10462_fresh_residual_root_expansion_request"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
REQUEST_JSON = OUT_DIR / "fresh_residual_root_expansion_request.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def now_utc() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def main() -> None:
    request = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": True,
        "decision": "fresh_residual_root_expansion_required",
        "claim_scope": [
            "Define the next curriculum expansion required to move beyond the repaired-overlay plateau.",
            "Replace more tiny same-surface support probes with fresh disjoint residual roots for the two surviving failure skills.",
        ],
        "root_requirements": {
            "python_verifier_outcome": {
                "target_skill": "multiple plausible tests are visible, but only one test or verifier actually determines whether the fix is correct",
                "minimum_new_roots": 6,
                "must_include": [
                    "at least three candidate tests or verification targets",
                    "at least one tempting wrong integration-style target",
                    "visible evidence linking the fix specifically to the gold verifier",
                    "repo/root disjointness from current Mirrormind heldout family when possible",
                ],
                "anti_cheat_gates": [
                    "gold verifier file must not be trivially inferable from candidate ordering",
                    "test names alone must not solve the row without the evidence block",
                    "selected support rows must stay train-only and root-disjoint from future strict slices",
                ],
            },
            "rust_evidence_citation": {
                "target_skill": "candidate_change_surface is tempting, but the best supporting evidence is specifically symptom_or_call_path_analogue rather than verifier_and_test_constraint",
                "minimum_new_roots": 6,
                "must_include": [
                    "both symptom_or_call_path_analogue and verifier_and_test_constraint as visible options",
                    "real source-backed evidence spans that make E vs F non-trivial",
                    "at least one repo family beyond tokenizers",
                    "selected tests or verifier anchors where possible",
                ],
                "anti_cheat_gates": [
                    "no direct copying of current tokenizers strict rows into train",
                    "same-surface tokenizers rows may only be used as diagnostic support, not promotable support",
                    "option-value permutations should be varied so E/F identity is not fixed",
                ],
            },
        },
        "acceptance_gate_for_next_probe": [
            "must attach fresh-root artifact ids for both residual skills",
            "must satisfy stage10461 residual promotion gate",
            "must beat 22/24 with zero new regressions before any claim upgrade",
        ],
        "recommended_next_stage_names": [
            "stage10463_python_verifier_fresh_root_builder",
            "stage10464_rust_citation_fresh_root_builder",
            "stage10465_fresh_residual_root_package_and_probe_request",
        ],
    }
    write_json(REQUEST_JSON, request)
    write_json(
        SUMMARY,
        {
            "stage": STAGE,
            "passed": True,
            "decision": request["decision"],
            "request": str(REQUEST_JSON.relative_to(ROOT)),
        },
    )
    print(json.dumps(request, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
