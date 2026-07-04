#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path

from training_data_attribution_influence import attribution_card


ROOT = Path(__file__).resolve().parents[1]
STAGE = 8725
NAME = "stage8725_training_data_attribution_influence_readiness"
OUT_DIR = ROOT / "runs" / "local" / "artifacts" / NAME
SUMMARY = ROOT / "runs" / "summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "TRAINING_DATA_ATTRIBUTION_INFLUENCE_READINESS_STAGE8725.md"

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
    eval_rows = [
        {"row_id": "eval_auth", "task": "fix auth token expiry", "task_tags": ["auth", "pytest"], "label": "FIX_AUTH"},
        {"row_id": "eval_import", "task": "fix missing import error", "task_tags": ["import", "runtime"], "label": "FIX_IMPORT"},
    ]
    train_rows = [
        {"row_id": "good_auth", "task": "repair auth token expiry pytest", "task_tags": ["auth", "pytest"], "label": "FIX_AUTH"},
        {"row_id": "bad_auth", "task": "repair auth token expiry pytest", "task_tags": ["auth", "pytest"], "label": "CHANGE_DOCS", "label_issue_score": 0.8},
        {"row_id": "unrelated", "task": "update CSS theme", "task_tags": ["frontend"], "label": "STYLE"},
    ]
    card = attribution_card(eval_rows, train_rows, top_k=2)
    sample_path = OUT_DIR / "training_data_attribution_influence_sample_card.json"
    sample_path.write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    recommendations = [row["recommendation"] for row in card["eval_cards"]]
    passed = (
        card["eval_rows"] == 2
        and card["train_rows"] == 3
        and "review_harmful_conflicts" in recommendations
        and "generate_or_retrieve_neighbors" in recommendations
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
            "eval_rows": card["eval_rows"],
            "train_rows": card["train_rows"],
            "helpful_neighbors": card["global_type_counts"].get("helpful_neighbor", 0),
            "harmful_conflicts": card["global_type_counts"].get("harmful_conflicting", 0),
            "missing_neighborhood": card["global_type_counts"].get("missing_neighborhood", 0),
        },
        "decision": "Recovered deterministic training-data attribution/influence contract; no influence-function training or model execution authority opened.",
        "next_best_step": "Attach training-data attribution to central graph, then recover fusion_logits_forward_pass_contract.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join(["# Stage8725 Training Data Attribution Influence Readiness", "", f"Passed: `{passed}`", "", "Recovered deterministic eval-to-train helpful/harmful/missing-neighbor attribution contracts.", "", "Authority remains closed.", ""]), encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
