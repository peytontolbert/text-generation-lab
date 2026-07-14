#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "runs/local/artifacts"
SUMMARIES = ROOT / "runs/summaries"
STAGE = 11546
NAME = "stage11546_web_supply_gate_after_train_completion"
OUT = ART / NAME
SUMMARY = OUT / "web_supply_gate_after_train_completion.json"

STAGE11544 = SUMMARIES / "stage11544_web_supply_after_mcp_sep_heldout_admission.json"
STAGE11545 = SUMMARIES / "stage11545_openclaw_more_web_gold_train_rows.json"


def now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> None:
    base = load(STAGE11544)
    train = load(STAGE11545)
    updated_train = int(base["counts"]["updated_executed_train_roots"]) + int(train["counts"]["admitted_train_roots"])
    updated_heldout = int(base["counts"]["updated_heldout_roots"])
    required_train = int(base["counts"]["required_executed_train_roots"])
    required_heldout = int(base["counts"]["required_heldout_roots"])
    gate_met = updated_train >= required_train and updated_heldout >= required_heldout
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now(),
        "passed": gate_met,
        "decision": "stage11527_web_root_supply_gate_met" if gate_met else "stage11527_web_root_supply_gate_still_short",
        "counts": {
            "previous_executed_train_roots": int(base["counts"]["updated_executed_train_roots"]),
            "added_stage11545_train_roots": int(train["counts"]["admitted_train_roots"]),
            "updated_executed_train_roots": updated_train,
            "required_executed_train_roots": required_train,
            "updated_heldout_roots": updated_heldout,
            "required_heldout_roots": required_heldout,
            "remaining_train_root_shortfall": max(0, required_train - updated_train),
            "remaining_heldout_root_shortfall": max(0, required_heldout - updated_heldout),
            "new_train_rows": int(train["counts"]["train_rows"]),
            "new_heldout_strict_rows_from_stage11544": int(base["counts"]["new_heldout_strict_rows"]),
        },
        "gates": {
            "minimum_train_roots_met": updated_train >= required_train,
            "minimum_heldout_roots_met": updated_heldout >= required_heldout,
            "stage11527_root_supply_gate_met": gate_met,
            "stage11545_train_support_admitted": bool(train["passed"]),
        },
        "claim_boundary": [
            "This completes the Web root-supply gate only.",
            "It does not prove Stage11507 generalizes to the new Web heldout rows.",
            "Next required work is a root-overlap/leak audit and then a same-manifest 100M/Gemma comparison on the sealed Web heldout package.",
        ],
        "source_artifacts": {
            "stage11544": rel(STAGE11544),
            "stage11545": rel(STAGE11545),
        },
        "outputs": {"summary": rel(SUMMARY)},
        "next_actions": [
            "Build a combined Web train/heldout manifest from Stage11535/11537/11545 train rows and Stage11541/11543 heldout rows.",
            "Run root-overlap, prompt-target leak, singleton-option, deterministic-shuffle, and train/heldout family audits.",
            "Only after the audit passes, run Stage11507 100M and Gemma on the sealed Web heldout manifest using GPU2-pinned runtimes.",
        ],
    }
    write_json(SUMMARY, summary)
    write_json(SUMMARIES / f"{NAME}.json", summary)


if __name__ == "__main__":
    main()
