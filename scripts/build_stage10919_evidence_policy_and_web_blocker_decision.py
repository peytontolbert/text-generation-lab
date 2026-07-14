#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "runs" / "local" / "artifacts"
STAGE = 10919
NAME = "stage10919_evidence_policy_and_web_blocker_decision"
OUT_DIR = ARTIFACTS / NAME
OUT_JSON = OUT_DIR / "evidence_policy_and_web_blocker_decision.json"

FRESH_POLICY = ARTIFACTS / "stage10918_fresh_evidence_successor_policy_audit" / "fresh_evidence_successor_policy_audit.json"
CURRENT_POLICY = ARTIFACTS / "stage10912_current_evidence_policy_decision" / "current_evidence_policy_decision.json"
WEB_GAP = ARTIFACTS / "stage10418_pure_web_verifier_anchor_gap_audit" / "pure_web_verifier_anchor_gap_audit.json"


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
    fresh = load_json(FRESH_POLICY)
    current = load_json(CURRENT_POLICY)
    web = load_json(WEB_GAP)
    raw = fresh["policies"]["encoder_raw"]
    role = fresh["policies"]["encoder_evidence_role_map"]
    payload = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": True,
        "decision": "evidence_policy_still_blocked_by_missing_pure_web_control",
        "claim_scope": [
            "Summarize the fresh Python/C++ evidence successor policy audit together with the standing pure-web source-supply gap.",
            "Define the next admissible evidence-policy move without overstating current multilingual support.",
        ],
        "source_artifacts": {
            "fresh_policy_audit": rel(FRESH_POLICY),
            "current_policy_decision": rel(CURRENT_POLICY),
            "pure_web_gap_audit": rel(WEB_GAP),
        },
        "headline": {
            "fresh_python_cpp_slice": {
                "encoder_raw_accuracy": raw["accuracy"],
                "encoder_role_map_accuracy": role["accuracy"],
                "encoder_raw_correct": raw["correct"],
                "encoder_role_map_correct": role["correct"],
                "f_rows_recovered_by_role_map": [
                    row["row_id"]
                    for row in role["by_repo"]
                    if False
                ],
            },
            "web_supply": {
                "pure_web_bundle_count": web["current_web_reviewed_state"]["pure_web_bundle_count"],
                "verifier_anchored_pure_web_bundle_count": web["current_web_reviewed_state"]["verifier_anchored_pure_web_bundle_count"],
                "fresh_source_heldout_pure_web_candidates_available_now": web["verdict"]["fresh_source_heldout_pure_web_candidates_available_now"],
            },
        },
        "findings": [
            "On the fresh Python/C++ slice, raw retrieval stays at 1/3 while evidence-role mapped retrieval rises to 2/3 by fixing both verifier_and_test_constraint rows.",
            "That same role-mapped policy still breaks the candidate_change_surface control row, so it is not honest to promote it as the new multilingual evidence scorer.",
            current.get("decision"),
            "The web blocker remains unchanged: there is still no verifier-anchored pure-web control family, so there is no clean multilingual safeguard against overfitting the role-mapped evidence policy to Python/C++ only.",
        ],
        "next_best_step": "Acquire or build one verifier-anchored pure-web evidence-citation control root where candidate_change_surface is genuinely correct, then rerun the role-mapped evidence scorer on web + fresh Python/C++ before considering promotion.",
    }
    role_misses = role.get("misses") or []
    raw_misses = raw.get("misses") or []
    payload["headline"]["fresh_python_cpp_slice"]["role_map_fixed_rows"] = [
        row["row_id"]
        for row in raw_misses
        if any(other["row_id"] == row["row_id"] for other in role_misses) is False
    ]
    payload["headline"]["fresh_python_cpp_slice"]["role_map_control_regression_rows"] = [
        row["row_id"]
        for row in role_misses
        if str(row.get("target_value") or "") == "candidate_change_surface"
    ]
    write_json(OUT_JSON, payload)
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
