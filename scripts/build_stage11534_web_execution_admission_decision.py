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
STAGE = 11534
NAME = "stage11534_web_execution_admission_decision"
OUT = ART / NAME
SUMMARY = OUT / "web_execution_admission_decision.json"

STAGE11530 = SUMMARIES / "stage11530_web_new_family_materialization_packets.json"
STAGE11531 = SUMMARIES / "stage11531_web_new_family_verifier_feasibility_audit.json"
STAGE11532 = SUMMARIES / "stage11532_dspy_web_verifier_execution_artifact.json"
STAGE11533 = SUMMARIES / "stage11533_openclaw_web_verifier_execution_artifact.json"


def now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> None:
    s11530 = load(STAGE11530)
    s11531 = load(STAGE11531)
    s11532 = load(STAGE11532)
    s11533 = load(STAGE11533)
    lanes = [
        {
            "family": "openclaw_clawhub",
            "status": "verifier_executed_passed_pending_gold",
            "evidence": rel(STAGE11533),
            "admit_to_train_now": False,
            "admit_to_strict_now": False,
            "why": "Focused verifier passed, but no task/failure contract, gold perspective answers, split assignment, or anti-cheat signoff exists yet.",
            "recommended_next_action": "Use as the first priority for Stage11535 gold adjudication or controlled bug-injection root framing.",
        },
        {
            "family": "dspy",
            "status": "verifier_executed_failed_before_assertions_pending_adjudication",
            "evidence": rel(STAGE11532),
            "admit_to_train_now": False,
            "admit_to_strict_now": False,
            "why": "Focused test produced real failure evidence, but it appears to be Jest/axios ESM environment routing rather than a product-behavior verifier. Needs maintainer adjudication.",
            "recommended_next_action": "Adjudicate as dependency/test-environment routing root or quarantine as environment-only.",
        },
        {
            "family": "ai_town",
            "status": "blocked_weak_selected_verifier",
            "evidence": rel(STAGE11531),
            "admit_to_train_now": False,
            "admit_to_strict_now": False,
            "why": "Selected verifier is convex/testing.ts helper material, not a focused test/spec. No dependency hydration or verifier execution evidence.",
            "recommended_next_action": "Replace with a real selected test or keep source-only diagnostic.",
        },
    ]
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now(),
        "passed": True,
        "decision": "web_execution_evidence_improved_but_no_new_train_or_strict_admission",
        "counts": {
            "stage11530_root_packets": (s11530.get("counts") or {}).get("root_packets"),
            "stage11531_execution_ready_before_attempt": (s11531.get("counts") or {}).get("execution_ready_now"),
            "verifier_executed_passed_new_families": 1,
            "verifier_executed_failed_new_families": 1,
            "new_train_ready_roots": 0,
            "new_strict_ready_roots": 0,
        },
        "lanes": lanes,
        "next_required_stage": {
            "name": "stage11535_web_verifier_gold_adjudication_or_bug_injection",
            "purpose": "Turn executed Web verifier evidence into scoreable maintainer roots by adding task/failure framing, gold perspective answers, split assignment, and anti-cheat signoff.",
            "do_not_do": "Do not run training from Stage11530/11532/11533 row shells directly.",
        },
        "source_artifacts": {
            "stage11530": rel(STAGE11530),
            "stage11531": rel(STAGE11531),
            "stage11532": rel(STAGE11532),
            "stage11533": rel(STAGE11533),
        },
        "outputs": {"summary": rel(SUMMARY)},
    }
    write_json(SUMMARY, summary)
    SUMMARIES.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(SUMMARY, SUMMARIES / f"{NAME}.json")
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
