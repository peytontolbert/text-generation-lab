#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path

from cross_encoder_reranker_calibration import calibration_card


ROOT = Path(__file__).resolve().parents[1]
STAGE = 8721
NAME = "stage8721_cross_encoder_reranker_calibration_readiness"
OUT_DIR = ROOT / "runs" / "local" / "artifacts" / NAME
SUMMARY = ROOT / "runs" / "summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "CROSS_ENCODER_RERANKER_CALIBRATION_READINESS_STAGE8721.md"

AUTHORITY_CLOSED = {
    "model_execution_authorized_next": False,
    "training_authorized_next": False,
    "decoder_ce_training_authorized_next": False,
    "denoise_ce_training_authorized_next": False,
    "runtime_authorized": False,
    "source_body_authorized": False,
    "gemma_authorized": False,
    "promotion_ready": False,
}


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)

    sample_rows = [
        {
            "row_id": "relevant_source",
            "task": "repair pytest auth token expiry failure",
            "evidence": "tests/test_auth.py asserts token expiry and auth.py validates token expiry",
            "source_type": "source",
            "retrieval_score": 0.9,
            "grounding_score": 0.8,
            "path_match": True,
            "label": True,
        },
        {
            "row_id": "irrelevant_doc",
            "task": "repair pytest auth token expiry failure",
            "evidence": "README installation instructions for unrelated package setup",
            "source_type": "doc",
            "retrieval_score": 0.05,
            "label": False,
        },
        {
            "row_id": "locked_leak",
            "task": "fix symbol binding",
            "evidence": "expected_answer includes clean_state target_body",
            "split": "locked_eval",
            "label": True,
        },
        {
            "row_id": "confident_wrong",
            "task": "auth token auth token auth token",
            "evidence": "auth token auth token auth token auth token",
            "source_type": "source",
            "retrieval_score": 1.0,
            "grounding_score": 1.0,
            "path_match": True,
            "label": False,
        },
    ]
    card = calibration_card(sample_rows)
    sample_path = OUT_DIR / "cross_encoder_reranker_calibration_sample_card.json"
    sample_path.write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    passed = (
        card["rows"] == 4
        and card["blocked_rows"] == 1
        and card["high_confidence_wrong_rows"] == 1
        and card["authority"]["training"] is False
    )
    summary = {
        "stage": STAGE,
        "name": NAME,
        "stage_name": NAME,
        "passed": passed,
        "authority": AUTHORITY_CLOSED,
        "artifacts": {"sample_card": str(sample_path.relative_to(ROOT))},
        "metrics": {
            **AUTHORITY_CLOSED,
            "authority_rows": 0,
            "rows": card["rows"],
            "labeled_rows": card["labeled_rows"],
            "blocked_rows": card["blocked_rows"],
            "high_confidence_wrong_rows": card["high_confidence_wrong_rows"],
            "brier": card["brier"],
            "ece": card["ece"],
        },
        "decision": "Recovered deterministic cross-encoder reranker calibration contract; no model execution, training, or scoring authority opened.",
        "next_best_step": "Attach cross-encoder reranker calibration to central graph, then recover dataset_cartography_active_learning.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text(
        "\n".join(
            [
                "# Stage8721 Cross-Encoder Reranker Calibration Readiness",
                "",
                f"Passed: `{passed}`",
                "",
                "Recovered a deterministic no-authority calibration contract for task/evidence pairs.",
                "",
                "It reports reranker probabilities, Brier/ECE, blocked leak/locked rows, and high-confidence-wrong review routes.",
                "",
                "No model execution, training, decoder CE, denoise CE, runtime, source/body emission, Gemma, scoring, or promotion is authorized.",
                "",
            ]
        ),
        encoding="utf-8",
    )
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
