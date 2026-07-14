#!/usr/bin/env python3
"""Decision artifact for Stage11960 augmented Transition-5K diagnostic probe."""

from __future__ import annotations

import json
import shutil
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "runs/local/artifacts"
SUMMARIES = ROOT / "runs/summaries"
STAGE = 11962
NAME = "stage11962_transition_5k_augmented_decision"
OUT = ART / NAME
SUMMARY = OUT / "transition_5k_augmented_decision.json"

AUDIT = ART / "stage11961_transition_5k_augmented_postrun_audit/transition_5k_augmented_postrun_audit.json"
REQUEST = ART / "stage11959_transition_5k_augmented_probe_request/transition_5k_augmented_probe_request.json"
PACKAGE = ART / "stage11958_transition_5k_v1_augmented_package/transition_5k_v1_augmented_package.json"


def now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def rel(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def metric(summary: dict[str, Any], runtime: str, key: str) -> dict[str, Any]:
    return summary["scoreboard"][runtime][key]


def main() -> None:
    audit = read_json(AUDIT)
    request = read_json(REQUEST)
    package = read_json(PACKAGE)
    stage11924 = audit["scoreboard"]["stage11924_selected_transition"]
    stage11960 = audit["scoreboard"]["stage11960_augmented_5k"]
    deltas = {
        "old_transition_640": stage11960["old_transition_640"]["correct"] - stage11924["old_transition_640"]["correct"],
        "aug_train": stage11960["aug_train"]["correct"] - stage11924["aug_train"]["correct"],
        "aug_validation": stage11960["aug_validation"]["correct"] - stage11924["aug_validation"]["correct"],
        "aug_strict_eval": stage11960["aug_strict_eval"]["correct"] - stage11924["aug_strict_eval"]["correct"],
        "residual_bank": stage11960["residual_bank"]["correct"] - stage11924["residual_bank"]["correct"],
        "source_heldout_smoke": stage11960["source_heldout_smoke"]["correct"] - stage11924["source_heldout_smoke"]["correct"],
    }
    results = audit["results"]["stage11960_augmented_5k"]
    task_deltas = {}
    for split in ("old_transition_640", "aug_validation", "aug_strict_eval"):
        base = audit["results"]["stage11924_selected_transition"][split]["by_task_type"]
        post = results[split]["by_task_type"]
        task_deltas[split] = {
            task: {
                "baseline_correct": base.get(task, {}).get("correct", 0),
                "postrun_correct": post.get(task, {}).get("correct", 0),
                "delta": post.get(task, {}).get("correct", 0) - base.get(task, {}).get("correct", 0),
                "rows": post.get(task, {}).get("rows", base.get(task, {}).get("rows")),
            }
            for task in sorted(set(base) | set(post))
        }
    payload = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now(),
        "decision": "reject_stage11960_keep_stage11924_transition_frontier",
        "selected_transition_frontier": {
            "runtime": "runs/local/artifacts/stage11924_transition_listwise_head_only_probe/runtime_model/runtime_model_bundle.json",
            "scorer": "encoder_option_retrieval_semantic_candidate_head",
            "old_transition_640": metric(audit, "stage11924_selected_transition", "old_transition_640"),
        },
        "rejected_runtime": {
            "runtime": "runs/local/artifacts/stage11960_transition_5k_augmented_probe/runtime_model/runtime_model_bundle.json",
            "weights_sha256": "f7a24a534ca2774a2df41b28ec33de2052a91ddf4fda6632062bf66efe998e6f",
            "old_transition_640": metric(audit, "stage11960_augmented_5k", "old_transition_640"),
        },
        "deltas_vs_stage11924": deltas,
        "promotion_gates": audit["gates"],
        "task_deltas_vs_stage11924": task_deltas,
        "interpretation": [
            "The augmented package is learnable on train support: Stage11960 improves aug_train from 784/5176 to 2700/5176.",
            "The gain does not transfer: aug_validation drops from 91/248 to 35/248 and aug_strict drops from 123/356 to 59/356.",
            "Old transition retention collapses from 364/640 to 143/640.",
            "Protected compact gates stay preserved, so the damage is isolated to the transition semantic-candidate head.",
            "Counterfactual status rows over-pushed the head toward train geometry instead of learning robust verifier-status semantics.",
        ],
        "stop_condition": {
            "do_not_rerun_same_augmented_objective": True,
            "do_not_promote_stage11960": True,
            "do_not_claim_counterfactual_rows_as_root_scale": True,
        },
        "next_recommendation": [
            "Do not do another full augmented-head run with this objective.",
            "Split transition heads by projection family or add task-specific routing before using counterfactual status rows.",
            "For verifier_transition and continue_or_stop, build direct status-specific candidate heads or a status-balanced sampler; current shared semantic candidate head is too brittle.",
            "Continue independent root materialization for Python/C++/Rust; the augmented counterfactual package is not a substitute for source-root breadth.",
        ],
        "source_artifacts": {
            "audit": rel(AUDIT),
            "request": rel(REQUEST),
            "package": rel(PACKAGE),
        },
        "package_readiness": {
            "train_support_probe_ready": package.get("passed_for_train_support_probe"),
            "frontier_source_claim_ready": package.get("passed_for_frontier_source_claim"),
            "counts": package.get("counts"),
        },
        "outputs": {"summary": rel(SUMMARY)},
    }
    write_json(SUMMARY, payload)
    SUMMARIES.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(SUMMARY, SUMMARIES / f"{NAME}.json")
    print(json.dumps({"decision": payload["decision"], "deltas_vs_stage11924": deltas, "next": payload["next_recommendation"]}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
