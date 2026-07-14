#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = 10559
NAME = "stage10559_preservation_successor_failure_audit"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
SUMMARY_PATH = OUT_DIR / "preservation_successor_failure_audit.json"
SUMMARY_REF = ROOT / "runs/summaries" / f"{NAME}.json"

STAGE10554 = ROOT / "runs/local/artifacts/stage10554_cuda_masked_projection_successor_bounded_strict_audit/cuda_masked_projection_successor_bounded_strict_audit.json"
STAGE10557 = ROOT / "runs/local/artifacts/stage10557_masked_projection_successor_with_v27_preservation_same_manifest_comparison/masked_projection_successor_with_v27_preservation_same_manifest_comparison.json"
STAGE10558 = ROOT / "runs/local/artifacts/stage10558_masked_projection_successor_with_v27_preservation_canary_audit/masked_projection_successor_with_v27_preservation_canary_audit.json"
STAGE10556 = ROOT / "runs/local/artifacts/stage10556_masked_projection_successor_with_v27_preservation_probe/bounded_decoder_probe/execution_result.json"


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def display(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def now_utc() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def main() -> None:
    a54 = load_json(STAGE10554)
    c57 = load_json(STAGE10557)
    c58 = load_json(STAGE10558)
    e56 = load_json(STAGE10556)
    payload = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": True,
        "claim_scope": [
            "Post-run failure audit for the stage10556 preservation-aware successor probe.",
            "Summarizes what improved, what stayed intact, and why the strict successor slice is still not a promotable multilingual win surface.",
            "This is an audit artifact, not a new benchmark claim.",
        ],
        "source_artifacts": {
            "stage10554_bounded_strict_contract_audit": display(STAGE10554),
            "stage10556_execution_result": display(STAGE10556),
            "stage10557_same_manifest_comparison": display(STAGE10557),
            "stage10558_canary_audit": display(STAGE10558),
        },
        "observed_outcome": {
            "strict_successor_exact": c57["hundred_m"]["overall"]["exact_accuracy"],
            "strict_successor_semantic": c57["hundred_m"]["overall_semantic"]["exact_accuracy"],
            "gemma_strict_successor_exact": c57["gemma12b"]["overall"]["exact_accuracy"],
            "canary_bounded_accuracy": c58["summary"]["bounded_accuracy"],
            "canary_greedy_exact_accuracy": c58["summary"]["greedy_exact_accuracy"],
            "strict_contract_blocked_for_bounded_choice": a54["contract_blocked"],
            "strict_contract_block_reason": a54["contract_block_reason"],
        },
        "key_findings": [
            "Adding reviewed v2.7 bounded-choice preservation support kept the repaired maintainer canary at 22/24 bounded accuracy.",
            "The same preservation support did not make the stage10555 strict successor generation slice scoreable as a multilingual win: both 100M and Gemma remained at 0/54 exact and 0/54 semantic.",
            "The strict successor slice is still generation-only and stores no candidate-option contract, so bounded semantic scoring cannot be used there honestly.",
            "The 100M runtime no longer emits a single-token 'A' everywhere, but it still collapses toward a generic ANSWER_* prefix rather than exact source-backed targets.",
        ],
        "promotion_decision": {
            "promotable": False,
            "reason": "strict_successor_surface_remains_interface_invalid_for_exact_generation_headline",
        },
        "next_best_step": {
            "decision": "rebuild_strict_successor_targets_into_short_canonical_exact_outputs",
            "requirements": [
                "Keep the same root/repo heldout hygiene as stage10555",
                "Replace long opaque target strings with short canonical exact outputs that are still reversibly mapped to source-backed evidence/verifier outcomes",
                "Preserve anti-cheat checks so the canonical target code is not revealed in the visible prompt",
                "Attach a parallel semantic mapping card so exact and semantic scoring can both be reported honestly",
                "Only compare 100M and Gemma again after the rebuilt strict surface supports exact generation without hidden option contracts",
            ],
        },
        "known_non_moves": [
            "Do not run more identical stage10555/10556-style preservation sweeps on the current strict surface",
            "Do not reinterpret the 54-row strict slice as a bounded-choice benchmark until candidate-option contracts are actually stored",
            "Do not upgrade the multilingual claim based on stage10557, because it is a 0/54 tie",
        ],
        "runtime_weights_sha256": (e56.get("runtime_model_bundle") or {}).get("weights_sha256"),
    }
    write_json(SUMMARY_PATH, payload)
    write_json(SUMMARY_REF, payload)
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
