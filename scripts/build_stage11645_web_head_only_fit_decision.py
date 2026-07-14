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
STAGE = 11645
NAME = "stage11645_web_head_only_fit_decision"
OUT = ART / NAME
SUMMARY = OUT / "web_head_only_fit_decision.json"

AUDIT = ART / "stage11644_normalized_web_head_only_fit_audit/normalized_web_head_only_fit_audit.json"


def now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def count(summary: dict[str, Any], key: str) -> str:
    result = summary["results"][key]
    return f"{result['correct']}/{result['rows']}"


def main() -> None:
    audit = load_json(AUDIT)
    results = audit["results"]
    gates = audit["gates"]
    support_fit = results["normalized_web_train_support"]["correct"] == results["normalized_web_train_support"]["rows"] == 206
    protected_destroyed = not (
        gates["filtered_strict_22_of_22"]
        and gates["old_canary_strict_23_of_23"]
        and gates["filtered_validation_at_least_20_of_22"]
        and gates["old_canary_validation_at_least_21_of_23"]
        and gates["residual_at_least_7_of_10"]
    )
    heldout_transfer_failed = (results["web_heldout"]["correct"] or 0) <= 38
    successor_geometry_fit = (results["web_successor_strict"]["correct"] or 0) >= 30

    if support_fit and protected_destroyed and heldout_transfer_failed:
        decision = "reject_head_only_web_task_head_as_product_runtime"
    elif support_fit and successor_geometry_fit:
        decision = "diagnostic_head_fit_only"
    else:
        decision = "head_fit_inconclusive"

    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now(),
        "decision": decision,
        "source_audit": rel(AUDIT),
        "key_results": {
            "normalized_web_train_support": count(audit, "normalized_web_train_support"),
            "web_successor_strict": count(audit, "web_successor_strict"),
            "web_heldout": count(audit, "web_heldout"),
            "filtered_strict": count(audit, "filtered_strict"),
            "old_canary_strict": count(audit, "old_canary_strict"),
            "filtered_validation": count(audit, "filtered_validation"),
            "old_canary_validation": count(audit, "old_canary_validation"),
            "residual_bank": count(audit, "residual_bank"),
        },
        "mechanism_read": {
            "head_capacity_for_normalized_support": support_fit,
            "successor_geometry_fit": successor_geometry_fit,
            "protected_behavior_destroyed": protected_destroyed,
            "web_heldout_transfer_failed": heldout_transfer_failed,
            "interpretation": (
                "The web task candidate head can memorize or fit the normalized OpenHands/Llama support geometry, "
                "but the learned boundary does not transfer to the 66-row web heldout and is incompatible with "
                "the protected compact maintainer scorer. The bottleneck is heldout geometry/objective routing, "
                "not raw support-row capacity."
            ),
        },
        "next_experiment_constraints": [
            "Do not promote Stage11643 or route it in product scoring.",
            "Do not run another full-model generic web support probe from the same rows.",
            "Compare support/successor/heldout geometry before training again.",
            "Mine hard negatives from Gemma-correct/routed-wrong heldout rows, not from already-fit support rows.",
            "If training resumes, use task-specific or repo-family-specific scorer heads with protected replay gates attached during training selection.",
        ],
        "training_note": (
            "The Prime-RL style description is useful conceptually: meaningful progress comes from many graded complete attempts per update, "
            "not from counting optimizer steps. For this lab, the analogous next scale-up is grouped root-local candidate rollouts with verifier-graded "
            "outcomes and listwise/pairwise updates, while keeping GPU2-only execution and protected gates."
        ),
        "claim_boundary": [
            "Stage11643 proves representability on normalized support rows only.",
            "It does not improve the selected product frontier.",
            "Stage11507 remains the selected compact frontier; Stage11634 routed policy remains better than this head-only Web runtime on heldout.",
        ],
    }
    write_json(SUMMARY, summary)
    SUMMARIES.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(SUMMARY, SUMMARIES / f"{NAME}.json")
    print(json.dumps({"decision": decision, "key_results": summary["key_results"]}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
