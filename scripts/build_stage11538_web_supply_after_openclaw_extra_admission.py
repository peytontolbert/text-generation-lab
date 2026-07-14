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
STAGE = 11538
NAME = "stage11538_web_supply_after_openclaw_extra_admission"
OUT = ART / NAME
SUMMARY = OUT / "web_supply_after_openclaw_extra_admission.json"

STAGE11536 = SUMMARIES / "stage11536_web_supply_after_openclaw_admission.json"
STAGE11537 = SUMMARIES / "stage11537_openclaw_extra_web_gold_support_rows.json"


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
    s11536 = load(STAGE11536)
    s11537 = load(STAGE11537)
    prev = s11536.get("counts") or {}
    base_train = int(prev.get("updated_executed_train_roots") or 0)
    train_required = int(prev.get("required_executed_train_roots") or 20)
    heldout = int(prev.get("updated_heldout_roots") or 0)
    heldout_required = int(prev.get("required_heldout_roots") or 10)
    added = int((s11537.get("counts") or {}).get("roots") or 0) if (s11537.get("admission") or {}).get("trainable_now") is True else 0
    updated_train = base_train + added
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now(),
        "passed": True,
        "decision": "web_train_supply_near_gate_heldout_still_short",
        "counts": {
            "previous_executed_train_roots": base_train,
            "added_stage11537_train_roots": added,
            "updated_executed_train_roots": updated_train,
            "required_executed_train_roots": train_required,
            "remaining_train_root_shortfall": max(0, train_required - updated_train),
            "updated_heldout_roots": heldout,
            "required_heldout_roots": heldout_required,
            "remaining_heldout_root_shortfall": max(0, heldout_required - heldout),
        },
        "gates": {
            "stage11537_train_support_admitted": added > 0,
            "minimum_train_roots_met": updated_train >= train_required,
            "minimum_heldout_roots_met": heldout >= heldout_required,
            "stage11527_gate_met": updated_train >= train_required and heldout >= heldout_required,
        },
        "admitted_new_roots": [
            {
                "repo_family": "openclaw_clawhub",
                "role": "train_support",
                "roots": added,
                "rows": (s11537.get("counts") or {}).get("rows"),
                "source": rel(STAGE11537),
            }
        ],
        "next_actions": [
            "Need 3 more executed Web train-support roots if using 17/20 accounting.",
            "Need 6 more sealed Web heldout roots; train-support additions do not solve heldout.",
            "Do not run another Web training probe until heldout supply is expanded or the experiment is explicitly train-supply-only diagnostic.",
        ],
        "source_artifacts": {"stage11536": rel(STAGE11536), "stage11537": rel(STAGE11537)},
        "outputs": {"summary": rel(SUMMARY)},
    }
    write_json(SUMMARY, summary)
    SUMMARIES.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(SUMMARY, SUMMARIES / f"{NAME}.json")
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
