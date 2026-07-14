#!/usr/bin/env python3
"""Decision card for verifier-grounded source-heldout successor scoring."""

from __future__ import annotations

import json
import shutil
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "runs/local/artifacts"
SUMMARIES = ROOT / "runs/summaries"
STAGE = 11741
NAME = "stage11741_verifier_grounded_successor_decision"
OUT = ART / NAME
SUMMARY = OUT / "verifier_grounded_successor_decision.json"

STATUS = ART / "stage11738_source_heldout_smoke_status_with_verifiers/source_heldout_smoke_status_with_verifiers.json"
SCORE = ART / "stage11740_verifier_grounded_source_heldout_successor_score/verifier_grounded_source_heldout_successor_score.json"
GEMMA_BACKEND = ART / "stage11739_gpu2_gemma_backend_audit/gpu2_gemma_backend_audit.json"


def now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def miss_summary(misses: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "language_family": row.get("language_family"),
            "task_type": row.get("task_type"),
            "target_role": row.get("target_role"),
            "predicted_role": row.get("predicted_role"),
            "target_value": row.get("target_value"),
            "predicted_value": row.get("predicted_value"),
        }
        for row in misses
    ]


def main() -> None:
    status = load_json(STATUS)
    score = load_json(SCORE)
    backend = load_json(GEMMA_BACKEND)
    metrics = score.get("metrics") or {}
    by_language = score.get("by_language") or {}
    gates = {
        "verifier_execution_attached": (status.get("gates") or {}).get("all_executable_verifiers_attached") is True,
        "verifier_grounded_full_coverage": (score.get("gates") or {}).get("full_coverage") is True,
        "verifier_grounded_no_prompt_leaks": (score.get("gates") or {}).get("no_prompt_target_label_leaks") is True
        and (score.get("gates") or {}).get("no_prompt_target_value_leaks") is True,
        "score_lift_over_static_smoke": False,
        "hundred_m_all_correct": metrics.get("correct") == metrics.get("rows") == 12,
        "gemma_same_manifest_ready": (backend.get("decision") != "gpu2_safe_gemma_same_manifest_backend_not_ready"),
    }
    artifact: dict[str, Any] = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now(),
        "decision": "verifier_grounding_does_not_break_source_heldout_smoke_plateau",
        "passed": True,
        "gates": gates,
        "metrics": metrics,
        "by_language": by_language,
        "misses": miss_summary(score.get("misses") or []),
        "interpretation": [
            "Executable verifier evidence is now attached and rendered without target label/value leaks.",
            "The selected Stage11507 product scorer still scores only 6/12 on the Python/C++/Rust verifier-grounded source-heldout smoke set.",
            "This is not a prompt-evidence omission problem: adding current-state verifier observations did not fix C++ abstain selection or Python/Rust verifier_outcome selected-test discrimination.",
            "C++ remains an abstain attractor on all four smoke tasks.",
            "Python and Rust remain selected-test verifier_outcome failures while preserving their other three smoke rows.",
        ],
        "next_actions": [
            "Build targeted train-support analogues for verifier_outcome selected-test discrimination using the newly attached executable verifier logs.",
            "For C++, create abstain counterfactuals where executable verifier evidence is present versus removed, so abstain is correct only when evidence is genuinely insufficient.",
            "Keep Stage11740 as a source-heldout smoke failure canary; do not train on these strict rows directly.",
            "Recover GPU2-safe Gemma3-12B same-manifest backend before making any smoke comparison claim.",
        ],
        "claim_boundary": [
            "Supported: verifier-grounded source-heldout smoke failure surface is now explicit and leak-clean.",
            "Not supported: 100M source-heldout smoke win over Gemma for Python/C++/Rust.",
            "Not supported: full-product patch repair or fail-to-pass verifier transition.",
        ],
        "source_artifacts": {
            "status_with_verifiers": rel(STATUS),
            "verifier_grounded_score": rel(SCORE),
            "gemma_backend_audit": rel(GEMMA_BACKEND),
        },
        "outputs": {"summary": rel(SUMMARY)},
    }
    write_json(SUMMARY, artifact)
    SUMMARIES.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(SUMMARY, SUMMARIES / f"{NAME}.json")
    print(json.dumps({"decision": artifact["decision"], "gates": gates, "metrics": metrics}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
