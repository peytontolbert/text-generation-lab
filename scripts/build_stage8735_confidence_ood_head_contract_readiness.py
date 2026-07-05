#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path

from confidence_ood_head_contract import calibration_card


ROOT = Path(__file__).resolve().parents[1]
STAGE = 8735
NAME = "stage8735_confidence_ood_head_contract_readiness"
OUT_DIR = ROOT / "runs" / "local" / "artifacts" / NAME
SUMMARY = ROOT / "runs" / "summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "CONFIDENCE_OOD_HEAD_CONTRACT_READINESS_STAGE8735.md"

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
        {"row_id": "accept", "logits": {"SAFE": 3.0, "RETRIEVE": 0.1, "UNSAFE": -0.4}, "target": "SAFE", "evidence_sufficient": True, "ood_score": .1},
        {"row_id": "wrong", "logits": {"SAFE": 3.0, "RETRIEVE": 0.1, "UNSAFE": -0.4}, "target": "RETRIEVE", "evidence_sufficient": True, "ood_score": .1},
        {"row_id": "ood", "logits": {"SAFE": .4, "RETRIEVE": .3, "UNSAFE": .2}, "target": "RETRIEVE", "evidence_sufficient": False, "ood_score": .8},
        {"row_id": "blocked", "confidence": .95, "pred": "SAFE", "target": "SAFE", "correct": True, "evidence_sufficient": True, "authority": {"runtime": True}},
    ]
    card = calibration_card(rows)
    sample_path = OUT_DIR / "confidence_ood_head_contract_sample_card.json"
    sample_path.write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    passed = (
        card["rows"] == 4
        and card["unsafe_decisions"] == 0
        and card["high_confidence_wrong_rows"] == 1
        and card["calibrated_shadow_accept_rows"] == 1
        and card["route_counts"].get("REVIEW_HIGH_CONFIDENCE_WRONG") == 1
        and card["route_counts"].get("RETRIEVE_OOD_OR_INSUFFICIENT") == 1
        and card["route_counts"].get("BLOCK_AUTHORITY_OR_LEAK") == 1
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
            "brier": card["brier"],
            "ece": card["ece"],
            "high_confidence_wrong_rows": card["high_confidence_wrong_rows"],
            "calibrated_shadow_accept_rows": card["calibrated_shadow_accept_rows"],
            "unsafe_decisions": card["unsafe_decisions"],
            "routes": card["route_counts"],
        },
        "decision": "Recovered confidence/OOD head contract with Brier/ECE, entropy/margin thresholds, high-confidence-wrong review, OOD retrieval, and authority/leak blocking. It authorizes no training or execution.",
        "next_best_step": "Attach confidence/OOD head contract to central graph, then recover structured_data_operation_curriculum.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage8735 Confidence/OOD Head Contract Readiness",
        "",
        f"Passed: `{passed}`",
        "",
        "Recovered no-execution confidence/OOD head contract with Brier/ECE, entropy, margin, abstain, retrieve, and high-confidence-wrong gates.",
        "",
        "Learned confidence is telemetry and shadow acceptance only; it cannot authorize source/body emission, decoder CE, runtime, or training.",
        "",
    ]), encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
