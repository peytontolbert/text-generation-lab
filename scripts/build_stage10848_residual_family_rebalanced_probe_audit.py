#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "runs" / "local" / "artifacts"
STAGE = 10848
NAME = "stage10848_residual_family_rebalanced_probe_audit"
OUT_DIR = ARTIFACTS / NAME
AUDIT_JSON = OUT_DIR / "residual_family_rebalanced_probe_audit.json"
SUMMARY = ROOT / "runs" / "summaries" / f"{NAME}.json"

BASE_DIR = ARTIFACTS / "stage10820_queue_aligned_multilingual_support_probe" / "bounded_decoder_probe"
RUN_DIR = ARTIFACTS / "stage10847_residual_family_rebalanced_probe" / "bounded_decoder_probe"

PY_STRICT_ROW = "stage10119::localsess_repository_library_sessseed_codex_sessions_rollout_2025_11_28t20_02_25_019acc0f_4bd7_77f2_b15f_3b0c_models_mirrormind_init_py_models_mirrormind_context_py_models_mirrormind_coordin_fd8013631e_aug_1500000_8b46e7f662::python::verifier_outcome::reviewed_v27_compact"
RUST_STRICT_ROW = "stage10126::tokenizers::tokenizers::rust::evidence_citation::reviewed_v27_compact"


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def now_utc() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def load_cards(run_dir: Path, split: str) -> list[dict[str, Any]]:
    return load_json(run_dir / f"bounded_choice_eval_audit_{split}.json")["row_cards"]


def accuracy(cards: list[dict[str, Any]]) -> float:
    return sum(1 for card in cards if card["constrained_choice_match"]) / len(cards)


def find(cards: list[dict[str, Any]], row_id: str) -> dict[str, Any] | None:
    return next((card for card in cards if card["row_id"] == row_id), None)


def main() -> None:
    base_eval = load_cards(BASE_DIR, "eval")
    base_strict = load_cards(BASE_DIR, "strict_eval")
    run_eval = load_cards(RUN_DIR, "eval")
    run_strict = load_cards(RUN_DIR, "strict_eval")
    execution_result = load_json(RUN_DIR / "execution_result.json")

    eval_regressions = [
        card for card in run_eval
        if not card["constrained_choice_match"]
    ]

    payload = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": True,
        "decision": "residual_family_rebalanced_probe_no_frontier_gain",
        "source_runs": {
            "baseline_10820": rel(BASE_DIR / "execution_result.json"),
            "diagnostic_10847": rel(RUN_DIR / "execution_result.json"),
        },
        "headline": {
            "baseline_eval_accuracy": accuracy(base_eval),
            "baseline_strict_accuracy": accuracy(base_strict),
            "diagnostic_eval_accuracy": accuracy(run_eval),
            "diagnostic_strict_accuracy": accuracy(run_strict),
            "eval_delta": accuracy(run_eval) - accuracy(base_eval),
            "strict_delta": accuracy(run_strict) - accuracy(base_strict),
        },
        "strict_residuals": {
            "python_verifier": find(run_strict, PY_STRICT_ROW),
            "rust_evidence": find(run_strict, RUST_STRICT_ROW),
        },
        "evaluation_readout": {
            "strict_status": "unchanged_22_of_24",
            "eval_status": "regressed_to_21_of_24",
            "new_eval_miss_set": eval_regressions,
        },
        "generation_readout": {
            "contentful_rate": execution_result["contentful_generation_rate"],
            "generated_rows": execution_result["generated_rows"],
            "note": "decoder generation remains contentful but still collapses to short label-token outputs rather than solving the bounded decision residuals directly",
        },
        "interpretation": [
            "Lowering preservation KL and modestly rebalancing train geometry did not flip either of the two strict residual rows.",
            "The Rust strict evidence row still has full-vocab E at rank 1 while constrained scoring chooses B, so scorer alignment remains a first-order issue.",
            "Validation regressed by one row, which means this package is diagnostic-only and should not replace the cleaner baseline frontier.",
        ],
        "next_best_step": "Stop promotion-style probing on this package. Build fresh Python verifier-transition roots and fresh Rust E-vs-F evidence roots, and separately audit scorer alignment for rows where full-vocab top1 is correct but constrained top1 is wrong.",
    }

    write_json(AUDIT_JSON, payload)
    write_json(
        SUMMARY,
        {
            "stage": STAGE,
            "passed": True,
            "decision": payload["decision"],
            "artifact": rel(AUDIT_JSON),
        },
    )
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
