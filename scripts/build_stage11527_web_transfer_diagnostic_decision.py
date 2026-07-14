#!/usr/bin/env python3
from __future__ import annotations

import json
import shutil
import time
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SUMMARIES = ROOT / "runs/summaries"
ART = ROOT / "runs/local/artifacts"
STAGE = 11527
NAME = "stage11527_web_transfer_diagnostic_decision"
OUT = ART / NAME
SUMMARY = OUT / "web_transfer_diagnostic_decision.json"

INPUTS = {
    "stage11521_llama_stage11507": SUMMARIES / "stage11521_web_llama_stack_stage11507_same_manifest_comparison.json",
    "stage11522_openhands_stage11507": SUMMARIES / "stage11522_openhands_web_stage11507_same_manifest_comparison.json",
    "stage11524_openhands_all_support": SUMMARIES / "stage11524_openhands_from_stage11507_support_postrun_audit.json",
    "stage11526_openhands_non_evidence_support": SUMMARIES / "stage11526_openhands_non_evidence_from_stage11507_postrun_audit.json",
}


def now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def compact_score(obj: dict[str, Any]) -> dict[str, Any]:
    comparison = obj.get("comparison") or {}
    if comparison:
        return {
            "hundred_m_correct": comparison.get("hundred_m_correct"),
            "hundred_m_rows": comparison.get("hundred_m_rows"),
            "hundred_m_accuracy": comparison.get("hundred_m_accuracy"),
            "gemma_correct": comparison.get("gemma12b_correct"),
            "gemma_rows": comparison.get("gemma12b_rows"),
            "gemma_accuracy": comparison.get("gemma12b_accuracy"),
            "delta_accuracy": comparison.get("delta_accuracy"),
        }
    product = ((obj.get("scored") or {}).get("encoder_option_retrieval_evidence_judgment_head") or {})
    gemma = obj.get("gemma_existing_artifacts") or {}
    return {
        "filtered_strict": product.get("filtered_strict", {}).get("correct"),
        "old_canary_strict": product.get("old_canary_strict", {}).get("correct"),
        "filtered_validation": product.get("filtered_validation", {}).get("correct"),
        "old_canary_validation": product.get("old_canary_validation", {}).get("correct"),
        "openhands_correct": product.get("openhands_heldout", {}).get("correct"),
        "openhands_rows": product.get("openhands_heldout", {}).get("rows"),
        "openhands_gemma_correct": (gemma.get("openhands") or {}).get("correct"),
        "llama_correct": product.get("llama_stack_heldout", {}).get("correct"),
        "llama_rows": product.get("llama_stack_heldout", {}).get("rows"),
        "llama_gemma_correct": (gemma.get("llama_stack") or {}).get("correct"),
    }


def main() -> None:
    loaded = {name: load_json(path) for name, path in INPUTS.items()}
    scores = {name: compact_score(obj) for name, obj in loaded.items()}
    decisions = {
        "selected_frontier_remains_stage11507": True,
        "reject_stage11523_all_openhands_support": True,
        "reject_stage11525_non_evidence_support": True,
        "reason": [
            "Stage11523 improves OpenHands from 0/18 to 6/18 but regresses filtered strict to 19/22 and old canary strict to 20/23.",
            "Stage11525 improves Llama from 0/6 to 1/6 and OpenHands from 0/18 to 4/18, but regresses filtered strict to 16/22 and old canary strict to 17/23.",
            "Neither support probe beats existing Gemma artifacts on the Web heldout packets.",
            "The Web gap is real under source/verifier-backed heldout rows; narrow OpenHands support overfits and damages preserved evidence/abstention behavior.",
        ],
    }
    next_stage_requirements = {
        "do_not_promote": ["stage11523", "stage11525"],
        "minimum_next_web_package": {
            "fresh_web_repo_families": ">=3, not only OpenHands or Llama Stack",
            "train_roots": ">=20 Web verifier-backed roots",
            "heldout_roots": ">=10 Web source/verifier-backed roots",
            "task_balance": [
                "symptom_localization",
                "evidence_citation",
                "verifier_outcome",
                "minimal_fix_selection",
                "alternative_hypothesis_elimination",
                "abstention_insufficient_evidence",
            ],
            "negative_controls": [
                "candidate_change_surface is sometimes correct and sometimes tempting wrong",
                "verifier/test constraint is sometimes correct and sometimes tempting wrong",
                "abstention rows include real insufficient-evidence cases",
            ],
            "promotion_gates": [
                "filtered strict remains 22/22",
                "old canary strict remains 23/23",
                "OpenHands heldout improves without repo-family training leakage being used as headline",
                "Llama Stack heldout improves",
                "same-manifest Gemma is beaten on a sealed Web slice",
            ],
        },
    }
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now(),
        "passed": True,
        "decision": "web_transfer_diagnostics_reject_support_probes_keep_stage11507",
        "scores": scores,
        "decisions": decisions,
        "next_stage_requirements": next_stage_requirements,
        "claim_boundary": [
            "Stage11507 remains selected for compact canary/harness claims.",
            "Current 100M does not beat Gemma on executed Web transfer packets.",
            "Web needs broader source/verifier-backed root supply and balanced training, not another tiny OpenHands-only support probe.",
        ],
        "source_artifacts": {name: rel(path) for name, path in INPUTS.items()},
        "outputs": {"summary": rel(SUMMARY)},
    }
    write_json(SUMMARY, summary)
    SUMMARIES.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(SUMMARY, SUMMARIES / f"{NAME}.json")
    print(json.dumps({"decision": summary["decision"], "scores": scores, "next": next_stage_requirements}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
