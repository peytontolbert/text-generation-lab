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
STAGE = 11607
NAME = "stage11607_web_task_candidate_head_decision"
OUT = ART / NAME
SUMMARY = OUT / "web_task_candidate_head_decision.json"
POSTRUN = SUMMARIES / "stage11606_web_task_candidate_head_postrun_audit.json"
REQUEST = SUMMARIES / "stage11605_web_task_candidate_head_probe_request.json"
SELECTED_RUNTIME = ART / "stage11507_preservation_strengthened_evidence_judgment_probe/runtime_model/runtime_model_bundle.json"
REJECTED_RUNTIME = ART / "stage11605_web_task_candidate_head_probe/runtime_model/runtime_model_bundle.json"


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
        "decision": "reject_stage11605_keep_stage11507_selected_frontier",
        "selected_frontier": {
            "stage": "stage11507_preservation_strengthened_evidence_judgment_probe",
            "runtime": rel(SELECTED_RUNTIME),
            "scorer": "encoder_option_retrieval_evidence_judgment_head",
            "weights_sha256": selected_bundle.get("weights_sha256"),
        },
        "rejected_runtime": {
            "stage": "stage11605_web_task_candidate_head_probe",
            "runtime": rel(REJECTED_RUNTIME),
            "scorer": "encoder_option_retrieval_web_task_candidate_head",
            "weights_sha256": rejected_bundle.get("weights_sha256"),
        },
        "request_objective": request.get("objective_settings"),
        "postrun_compact_results": compact,
        "postrun_gates": postrun.get("gates"),
        "why_rejected": [
            "The new Web task-candidate scorer source was trained and evaluated successfully, so this is not a runtime-code blocker.",
            "Filtered strict, old canary strict, filtered validation, and old validation were preserved.",
            "Residual bank regressed from selected frontier 7/10 to 6/10.",
            "Web heldout stayed 35/66, below the >42/66 improvement gate and below Gemma's 52/66 reference.",
            "No-abstain Web successor strict stayed weak at 2/36, matching the earlier no-abstain run and not proving task-family transfer.",
        ],
        "inference": [
            "A separate Web task-candidate head by itself is insufficient when trained through the current shared encoder/update path.",
            "The next useful experiment should isolate whether interference comes from encoder updates or from insufficient Web supervision: freeze the base encoder and train only the new Web head, or build fail-to-pass/verifier-transition Web rows rather than PASS_TO_PASS selected-test relevance rows.",
        ],
        "next_recommended_work": [
            "Keep Stage11507 + encoder_option_retrieval_evidence_judgment_head as selected frontier.",
            "Run a head-only/frozen-base Web task-candidate probe before any more full-model Web probes.",
            "If head-only also stays at 35/66 and 2/36, stop this row geometry and materialize real fail-to-pass Web verifier roots.",
        ],
        "source_artifacts": {
            "request": rel(REQUEST),
            "postrun": rel(POSTRUN),
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
    }, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
