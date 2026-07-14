#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "runs/local/artifacts"
SUMMARIES = ROOT / "runs/summaries"
STAGE = 11544
NAME = "stage11544_web_supply_after_mcp_sep_heldout_admission"
OUT = ART / NAME
SUMMARY = OUT / "web_supply_after_mcp_sep_heldout_admission.json"

STAGE11538 = SUMMARIES / "stage11538_web_supply_after_openclaw_extra_admission.json"
STAGE11541 = SUMMARIES / "stage11541_mcp_typescript_sdk_web_gold_heldout_rows.json"
STAGE11543 = SUMMARIES / "stage11543_sep_automation_web_gold_heldout_rows.json"


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
    base = load(STAGE11538)
    mcp = load(STAGE11541)
    sep = load(STAGE11543)
    previous_train = int(base["counts"]["updated_executed_train_roots"])
    previous_heldout = int(base["counts"]["updated_heldout_roots"])
    added_heldout = int(mcp["counts"]["admitted_heldout_roots"]) + int(sep["counts"]["admitted_heldout_roots"])
    updated_train = previous_train
    updated_heldout = previous_heldout + added_heldout
    required_train = int(base["counts"]["required_executed_train_roots"])
    required_heldout = int(base["counts"]["required_heldout_roots"])
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now(),
        "passed": True,
        "decision": "web_heldout_gate_met_train_gate_still_short",
        "counts": {
            "previous_executed_train_roots": previous_train,
            "previous_heldout_roots": previous_heldout,
            "added_mcp_typescript_sdk_heldout_roots": int(mcp["counts"]["admitted_heldout_roots"]),
            "added_sep_automation_heldout_roots": int(sep["counts"]["admitted_heldout_roots"]),
            "updated_executed_train_roots": updated_train,
            "updated_heldout_roots": updated_heldout,
            "required_executed_train_roots": required_train,
            "required_heldout_roots": required_heldout,
            "remaining_train_root_shortfall": max(0, required_train - updated_train),
            "remaining_heldout_root_shortfall": max(0, required_heldout - updated_heldout),
            "new_heldout_strict_rows": int(mcp["counts"]["strict_eval_rows"]) + int(sep["counts"]["strict_eval_rows"]),
        },
        "gates": {
            "minimum_train_roots_met": updated_train >= required_train,
            "minimum_heldout_roots_met": updated_heldout >= required_heldout,
            "stage11527_gate_met": updated_train >= required_train and updated_heldout >= required_heldout,
            "mcp_heldout_admitted": bool(mcp["passed"]),
            "sep_heldout_admitted": bool(sep["passed"]),
        },
        "claim_boundary": [
            "The Web heldout-root count is now satisfied, but the executed Web train-support count is still short.",
            "No Web training probe should be promoted until train support also reaches the Stage11527 gate and a root-overlap audit passes.",
            "The new heldout rows are sealed and must not be replayed into train.",
        ],
        "source_artifacts": {
            "stage11538": rel(STAGE11538),
            "stage11541": rel(STAGE11541),
            "stage11543": rel(STAGE11543),
        },
        "outputs": {"summary": rel(SUMMARY)},
        "next_actions": [
            "Materialize at least 3 more executed Web train-support roots from non-heldout families.",
            "Keep Stage11541 and Stage11543 rows sealed for Web transfer evaluation.",
            "Run root-overlap and prompt-target leak audits before any Web same-manifest comparison.",
        ],
    }
    write_json(SUMMARY, summary)
    write_json(SUMMARIES / f"{NAME}.json", summary)


if __name__ == "__main__":
    main()
