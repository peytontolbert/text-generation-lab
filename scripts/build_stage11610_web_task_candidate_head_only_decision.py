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
STAGE = 11610
NAME = "stage11610_web_task_candidate_head_only_decision"
OUT = ART / NAME
SUMMARY = OUT / "web_task_candidate_head_only_decision.json"
POSTRUN = SUMMARIES / "stage11609_web_task_candidate_head_only_postrun_audit.json"
REQUEST = SUMMARIES / "stage11608_web_task_candidate_head_only_probe_request.json"
SELECTED_RUNTIME = ART / "stage11507_preservation_strengthened_evidence_judgment_probe/runtime_model/runtime_model_bundle.json"
REJECTED_RUNTIME = ART / "stage11608_web_task_candidate_head_only_probe/runtime_model/runtime_model_bundle.json"
PREVIOUS_FULL_HEAD_DECISION = SUMMARIES / "stage11607_web_task_candidate_head_decision.json"


def now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> None:
    postrun = load_json(POSTRUN)
    request = load_json(REQUEST)
    previous = load_json(PREVIOUS_FULL_HEAD_DECISION) if PREVIOUS_FULL_HEAD_DECISION.exists() else {}
    results = postrun.get("results") or {}
    compact = {
        name: {
            "correct": card.get("correct"),
            "rows": card.get("rows"),
            "accuracy": card.get("accuracy"),
        }
        for name, card in results.items()
    }
    selected_bundle = load_json(SELECTED_RUNTIME)
    rejected_bundle = load_json(REJECTED_RUNTIME)
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now(),
        "decision": "reject_stage11608_keep_stage11507_selected_frontier",
        "selected_frontier": {
            "stage": "stage11507_preservation_strengthened_evidence_judgment_probe",
            "runtime": rel(SELECTED_RUNTIME),
            "scorer": "encoder_option_retrieval_evidence_judgment_head",
            "weights_sha256": selected_bundle.get("weights_sha256"),
        },
        "rejected_runtime": {
            "stage": "stage11608_web_task_candidate_head_only_probe",
            "runtime": rel(REJECTED_RUNTIME),
            "scorer": "encoder_option_retrieval_web_task_candidate_head",
            "weights_sha256": rejected_bundle.get("weights_sha256"),
            "head_only": True,
        },
        "request_objective": request.get("objective_settings"),
        "postrun_compact_results": compact,
        "postrun_gates": postrun.get("gates"),
        "comparison_to_full_update_stage11605": (previous.get("postrun_compact_results") or {}),
        "why_rejected": [
            "Head-only training improved the no-abstain Web successor strict slice to 13/36, compared with 2/36 for the full-update Web head probe.",
            "The gain did not transfer to the independent Web heldout: 34/66, worse than the selected Stage11507 baseline of 35/66 and below the >42/66 gate.",
            "Filtered strict regressed to 21/22 and old canary strict regressed to 22/23, so preservation gates failed.",
            "Residual stayed below the selected frontier at 6/10 rather than the required >=7/10.",
        ],
        "inference": [
            "The Web task-candidate head can learn part of the successor row geometry when isolated, so the scorer path is trainable.",
            "The current Stage11597 no-abstain successor geometry is not a sufficient generalization target; it overfits without improving OpenHands/Llama heldout.",
            "The next useful work should prioritize better Web root quality and verifier transitions, or add a heldout-aware validation stopper for the head rather than training longer on the same successor-shaped rows.",
        ],
        "next_recommended_work": [
            "Keep Stage11507 selected.",
            "Do not run longer head-only training on the same Stage11597 rows without a validation-stopping criterion; it already overfits successor geometry.",
            "Materialize real fail-to-pass or behavior-changing Web verifier roots, then train/evaluate with root-heldout OpenHands/Llama rows.",
            "If testing architecture further, use a heldout-calibrated Web head with early stopping against web_heldout and protected canaries, not fixed-step training.",
        ],
        "source_artifacts": {
            "request": rel(REQUEST),
            "postrun": rel(POSTRUN),
            "previous_full_head_decision": rel(PREVIOUS_FULL_HEAD_DECISION),
            "selected_runtime": rel(SELECTED_RUNTIME),
            "rejected_runtime": rel(REJECTED_RUNTIME),
        },
    }
    OUT.mkdir(parents=True, exist_ok=True)
    write_json(SUMMARY, summary)
    SUMMARIES.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(SUMMARY, SUMMARIES / f"{NAME}.json")
    print(json.dumps({
        "decision": summary["decision"],
        "postrun_compact_results": compact,
        "selected_frontier": summary["selected_frontier"],
        "rejected_runtime": summary["rejected_runtime"],
        "inference": summary["inference"],
    }, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
