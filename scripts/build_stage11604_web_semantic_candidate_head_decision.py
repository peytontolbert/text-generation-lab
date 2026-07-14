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
STAGE = 11604
NAME = "stage11604_web_semantic_candidate_head_decision"
OUT = ART / NAME
SUMMARY = OUT / "web_semantic_candidate_head_decision.json"
POSTRUN = SUMMARIES / "stage11603_web_semantic_candidate_head_postrun_audit.json"
REQUEST = SUMMARIES / "stage11602_web_semantic_candidate_head_probe_request.json"
SELECTED_RUNTIME = ART / "stage11507_preservation_strengthened_evidence_judgment_probe/runtime_model/runtime_model_bundle.json"
REJECTED_RUNTIME = ART / "stage11602_web_semantic_candidate_head_probe/runtime_model/runtime_model_bundle.json"


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
        "decision": "reject_stage11602_keep_stage11507_selected_frontier",
        "selected_frontier": {
            "stage": "stage11507_preservation_strengthened_evidence_judgment_probe",
            "runtime": rel(SELECTED_RUNTIME),
            "scorer": "encoder_option_retrieval_evidence_judgment_head",
            "weights_sha256": selected_bundle.get("weights_sha256"),
        },
        "rejected_runtime": {
            "stage": "stage11602_web_semantic_candidate_head_probe",
            "runtime": rel(REJECTED_RUNTIME),
            "scorer": "encoder_option_retrieval_semantic_candidate_head",
            "weights_sha256": rejected_bundle.get("weights_sha256"),
        },
        "request_objective": request.get("objective_settings") or request.get("probe_command"),
        "postrun_compact_results": compact,
        "postrun_gates": postrun.get("gates"),
        "why_rejected": [
            "Stage11602 preserved filtered strict, old strict, filtered validation, and old validation under the semantic-candidate-head scorer.",
            "Residual regressed from the selected frontier gate of 7/10 to 6/10.",
            "Web heldout stayed 35/66, below the required >42/66 and below Gemma's 52/66 same-manifest reference.",
            "No-abstain web successor strict remained essentially unsolved at 1/36, only below the prior 2/36 no-abstain probe.",
            "Therefore the semantic-candidate-head reuse does not solve the Web scorer geometry problem and should remain diagnostic-only.",
        ],
        "next_recommended_work": [
            "Keep Stage11507 + encoder_option_retrieval_evidence_judgment_head as selected frontier.",
            "Stop reusing generic evidence/semantic heads for Web; the successor rows need a real Web/task-specific candidate scorer or staged frozen-head training.",
            "If continuing Web, train a separate task-family scorer over (state, option, task_family, semantic_role, verifier metadata) and audit against the same gates before touching selected frontier.",
            "Do not claim web improvement from Stage11602; it is a controlled negative result.",
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
        "selected_frontier": summary["selected_frontier"],
        "rejected_runtime": summary["rejected_runtime"],
        "postrun_compact_results": compact,
    }, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
