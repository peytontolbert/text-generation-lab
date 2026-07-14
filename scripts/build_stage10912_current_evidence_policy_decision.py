#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "runs" / "local" / "artifacts"
STAGE = 10912
NAME = "stage10912_current_evidence_policy_decision"
OUT_DIR = ARTIFACTS / NAME
OUT_JSON = OUT_DIR / "current_evidence_policy_decision.json"

AUDIT_JSON = ARTIFACTS / "stage10911_current_evidence_role_policy_audit" / "current_evidence_role_policy_audit.json"


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def now_utc() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def main() -> None:
    audit = load_json(AUDIT_JSON)
    raw = audit["policies"]["encoder_raw"]
    mapped = audit["policies"]["encoder_evidence_role_map"]
    decoder = audit["policies"]["decoder_label"]
    hybrid = audit["policies"]["hybrid_decoder_on_evidence"]

    payload = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": True,
        "decision": "no_honest_multilingual_evidence_policy_candidate_yet",
        "claim_scope": [
            "Decide whether the current evidence-citation weakness can be improved with a safe scoring-interface change on the cleaned reviewed-v2.7 checked surface.",
            "Reject interface candidates that improve Python/C++ by regressing the clean web evidence row, because the objective is multilingual maintainer quality rather than per-language patching.",
        ],
        "source_audit": rel(AUDIT_JSON),
        "headline": {
            "encoder_raw_accuracy": raw["accuracy"],
            "encoder_evidence_role_map_accuracy": mapped["accuracy"],
            "decoder_label_accuracy": decoder["accuracy"],
            "hybrid_decoder_on_evidence_accuracy": hybrid["accuracy"],
        },
        "findings": [
            "Raw retrieval keeps the web evidence row correct but misses both Python and C/C++ verifier-and-test-constraint rows, giving 1/3 on the checked evidence slice.",
            "Role-mapped retrieval improves the checked evidence slice to 2/3 by flipping Python and C/C++ to F = verifier_and_test_constraint.",
            "Role-mapped retrieval is not safe to adopt as a multilingual interface candidate because it regresses the clean web row from B = candidate_change_surface to F = verifier_and_test_constraint.",
            "Decoder-based evidence policies are strictly worse and collapse away from the correct evidence role labels on all three rows.",
        ],
        "rejected_candidates": [
            {
                "policy": "encoder_evidence_role_map",
                "reason": "Improves Python and C/C++ but introduces a web regression on the checked surface.",
            },
            {
                "policy": "decoder_label",
                "reason": "0/3 on the checked evidence slice.",
            },
            {
                "policy": "hybrid_decoder_on_evidence",
                "reason": "0/3 on the checked evidence slice.",
            },
        ],
        "approved_candidates": [],
        "next_root_building_targets": [
            "Fresh Python evidence-citation roots where candidate_change_surface is tempting but verifier_and_test_constraint is the true decisive fact.",
            "Fresh C/C++ evidence-citation roots with the same B-versus-F competition from disjoint repo families.",
            "At least one fresh pure-web evidence-citation root where candidate_change_surface is genuinely correct so any future role-based policy can be audited against a clean web positive.",
        ],
        "next_best_step": "Do not adopt an evidence-citation interface change yet. Build fresh multilingual evidence roots, then rerun the same checked-surface policy audit before changing the standalone scoring contract.",
    }

    write_json(OUT_JSON, payload)
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
