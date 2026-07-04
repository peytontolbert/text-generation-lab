#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path

from dataset_cartography_active_learning import active_learning_batch


ROOT = Path(__file__).resolve().parents[1]
STAGE = 8723
NAME = "stage8723_dataset_cartography_active_learning_readiness"
OUT_DIR = ROOT / "runs" / "local" / "artifacts" / NAME
SUMMARY = ROOT / "runs" / "summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "DATASET_CARTOGRAPHY_ACTIVE_LEARNING_READINESS_STAGE8723.md"

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
    rows = [
        {"row_id": "easy", "confidence_history": [0.95, 0.96], "loss_history": [0.05, 0.04], "correct_history": [True, True], "duplicate_score": 0.9},
        {"row_id": "ambiguous", "confidence_history": [0.2, 0.8, 0.4], "loss_history": [1.5, 0.3, 1.1], "correct_history": [False, True, False]},
        {"row_id": "hard", "confidence_history": [0.3, 0.35], "loss_history": [1.6, 1.4], "correct_history": [False, False]},
        {"row_id": "noisy", "confidence_history": [0.1, 0.12], "loss_history": [2.0, 2.1], "correct_history": [False, False], "label_issue_score": 0.8},
    ]
    card = active_learning_batch(rows, budget=3)
    sample_path = OUT_DIR / "dataset_cartography_active_learning_sample_card.json"
    sample_path.write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    cart = card["cartography"]
    passed = (
        cart["rows"] == 4
        and cart["label_review_rows"] == 1
        and cart["downsample_rows"] == 1
        and cart["neighbor_generation_rows"] >= 2
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
            "rows": cart["rows"],
            "label_review_rows": cart["label_review_rows"],
            "downsample_rows": cart["downsample_rows"],
            "neighbor_generation_rows": cart["neighbor_generation_rows"],
            "forgetting_event_rows": cart["forgetting_event_rows"],
            "selected_count": card["selected_count"],
        },
        "decision": "Recovered deterministic dataset cartography and active-learning sampler contract; no training or model execution authority opened.",
        "next_best_step": "Attach dataset cartography to central graph, then recover training_data_attribution_influence.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text(
        "\n".join([
            "# Stage8723 Dataset Cartography Active Learning Readiness",
            "",
            f"Passed: `{passed}`",
            "",
            "Recovered deterministic confidence/variability/forgetting/loss cartography and active-learning sampler contracts.",
            "",
            "No training, model execution, decoder CE, denoise CE, runtime, source/body emission, Gemma, scoring, or promotion is authorized.",
            "",
        ]),
        encoding="utf-8",
    )
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
