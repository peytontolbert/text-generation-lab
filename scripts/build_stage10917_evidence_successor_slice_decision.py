#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "runs" / "local" / "artifacts"
STAGE = 10917
NAME = "stage10917_evidence_successor_slice_decision"
OUT_DIR = ARTIFACTS / NAME
OUT_JSON = OUT_DIR / "evidence_successor_slice_decision.json"

SLICE_COMPARISON = ARTIFACTS / "stage10916_evidence_successor_candidate_slice_comparison" / "evidence_successor_candidate_slice_comparison.json"
POLICY_DECISION = ARTIFACTS / "stage10912_current_evidence_policy_decision" / "current_evidence_policy_decision.json"


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
    comparison = load_json(SLICE_COMPARISON)
    policy = load_json(POLICY_DECISION)
    rows = list(comparison.get("rows") or [])
    f_rows = [row for row in rows if str(row.get("target_value") or "") == "verifier_and_test_constraint"]
    b_rows = [row for row in rows if str(row.get("target_value") or "") == "candidate_change_surface"]
    payload = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": True,
        "decision": "fresh_evidence_successors_confirm_multilingual_b_vs_f_gap",
        "claim_scope": [
            "Interpret only the fresh 3-row Python/C++ evidence successor candidate slice.",
            "Do not promote any new evidence scorer from this artifact; it is a decision summary for the next dataset move.",
        ],
        "source_artifacts": {
            "slice_comparison": rel(SLICE_COMPARISON),
            "current_policy_decision": rel(POLICY_DECISION),
        },
        "headline": {
            "hundred_m_accuracy": comparison["hundred_m"]["overall"]["exact_accuracy"],
            "gemma12b_accuracy": comparison["gemma12b"]["overall"]["exact_accuracy"],
            "fresh_f_rows": {
                "rows": len(f_rows),
                "hundred_m_correct": sum(1 for row in f_rows if row.get("constrained_choice_match") is True),
                "gemma12b_correct": sum(1 for row in f_rows if row.get("gemma12b_correct") is True),
                "hundred_m_predictions": [row.get("constrained_choice_top1_label") for row in f_rows],
                "target_labels": [row.get("target_text") for row in f_rows],
            },
            "fresh_b_control_rows": {
                "rows": len(b_rows),
                "hundred_m_correct": sum(1 for row in b_rows if row.get("constrained_choice_match") is True),
                "gemma12b_correct": sum(1 for row in b_rows if row.get("gemma12b_correct") is True),
            },
        },
        "findings": [
            "The fresh Python/C++ successor slice preserves the same semantic split as the cleaned reviewed-v2.7 evidence lane: the 100M model keeps the candidate_change_surface positive control but misses both fresh verifier_and_test_constraint rows.",
            "Because the fresh failures survive option-order changes and reviewed packet rematerialization, the B-vs-F issue is not just stale row contamination.",
            "Gemma remains weaker overall at 0/3, but the 100M evidence lane is still not good enough to justify a new scorer policy or a broad evidence-citation breakthrough claim.",
            policy.get("decision"),
        ],
        "next_best_step": "Build at least one fresh pure-web positive-control evidence root and additional Python/C++ F-target successors, then revisit scorer changes only if a policy candidate preserves B controls while lifting all F rows.",
    }
    write_json(OUT_JSON, payload)
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
