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
STAGE = 11536
NAME = "stage11536_web_supply_after_openclaw_admission"
OUT = ART / NAME
SUMMARY = OUT / "web_supply_after_openclaw_admission.json"

STAGE11528 = SUMMARIES / "stage11528_web_verifier_root_supply_audit.json"
STAGE11534 = SUMMARIES / "stage11534_web_execution_admission_decision.json"
STAGE11535 = SUMMARIES / "stage11535_openclaw_web_gold_adjudicated_support_rows.json"


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
    s11528 = load(STAGE11528)
    s11534 = load(STAGE11534)
    s11535 = load(STAGE11535)
    gate = s11528.get("stage11527_gate") or {}
    base_train = int(gate.get("train_roots_available") or 0)
    base_train_required = int(gate.get("train_roots_required") or 20)
    base_heldout = int(gate.get("heldout_roots_available") or 0)
    base_heldout_required = int(gate.get("heldout_roots_required") or 10)
    openclaw_admitted = (s11535.get("admission") or {}).get("trainable_now") is True
    added_train_roots = 1 if openclaw_admitted else 0
    updated_train = base_train + added_train_roots
    updated_heldout = base_heldout
    gates = {
        "openclaw_train_support_admitted": openclaw_admitted,
        "minimum_train_roots_met": updated_train >= base_train_required,
        "minimum_heldout_roots_met": updated_heldout >= base_heldout_required,
        "do_not_count_dspy_without_gold": True,
        "do_not_count_ai_town_without_real_test": True,
    }
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now(),
        "passed": True,
        "decision": "web_supply_improved_but_stage11527_gate_still_unmet",
        "counts": {
            "base_executed_train_roots": base_train,
            "added_openclaw_train_roots": added_train_roots,
            "updated_executed_train_roots": updated_train,
            "required_executed_train_roots": base_train_required,
            "remaining_train_root_shortfall": max(0, base_train_required - updated_train),
            "updated_heldout_roots": updated_heldout,
            "required_heldout_roots": base_heldout_required,
            "remaining_heldout_root_shortfall": max(0, base_heldout_required - updated_heldout),
        },
        "gates": gates,
        "admitted_new_roots": [
            {
                "root_id": "stage11535::openclaw_clawhub::convex::skills_versions_public_sanitization_train_support",
                "repo_family": "openclaw_clawhub",
                "role": "train_support",
                "rows": (s11535.get("counts") or {}).get("rows"),
                "source": rel(STAGE11535),
            }
        ] if openclaw_admitted else [],
        "not_admitted": [
            {
                "repo_family": "dspy",
                "reason": "verifier failed before assertions; requires adjudication as dependency/test-environment routing or quarantine",
                "source": rel(STAGE11534),
            },
            {
                "repo_family": "ai_town",
                "reason": "selected verifier is helper-like testing.ts, not a focused test/spec",
                "source": rel(STAGE11534),
            },
        ],
        "next_actions": [
            "Materialize at least 7 more executed Web train-support roots if using the updated 13/20 accounting.",
            "Materialize at least 6 more sealed Web heldout roots; OpenClaw Stage11535 does not help heldout.",
            "Prioritize new repo families and avoid training on existing Llama Stack/OpenHands heldout roots.",
        ],
        "source_artifacts": {
            "stage11528": rel(STAGE11528),
            "stage11534": rel(STAGE11534),
            "stage11535": rel(STAGE11535),
        },
        "outputs": {"summary": rel(SUMMARY)},
    }
    write_json(SUMMARY, summary)
    SUMMARIES.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(SUMMARY, SUMMARIES / f"{NAME}.json")
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
