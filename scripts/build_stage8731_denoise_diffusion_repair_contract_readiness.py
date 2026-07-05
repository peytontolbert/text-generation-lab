#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path

from denoise_diffusion_repair_contract import repair_contract_card


ROOT = Path(__file__).resolve().parents[1]
STAGE = 8731
NAME = "stage8731_denoise_diffusion_repair_contract_readiness"
OUT_DIR = ROOT / "runs" / "local" / "artifacts" / NAME
SUMMARY = ROOT / "runs" / "summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "DENOISE_DIFFUSION_REPAIR_CONTRACT_READINESS_STAGE8731.md"

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
        {"row_id": "leak", "bad_output": "<SEM_SLOT_X> POLICY_CONTINUE"},
        {"row_id": "short", "bad_output": "def f("},
        {"row_id": "repeat", "bad_output": "hello hello hello hello hello"},
        {"row_id": "wrong_surface", "bad_output": "Traceback (most recent call last): boom"},
        {"row_id": "abstain", "bad_output": "safe text", "authority": {"runtime": True}},
    ]
    card = repair_contract_card(rows)
    sample_path = OUT_DIR / "denoise_diffusion_repair_contract_sample_card.json"
    sample_path.write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    passed = (
        card["rows"] == 5
        and card["denoise_candidate_rows"] == 4
        and card["denoise_ce_rows"] == 0
        and card["decoder_ce_rows"] == 0
        and card["unsafe_authority_rows"] == 0
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
            "denoise_candidate_rows": card["denoise_candidate_rows"],
            "denoise_ce_rows": card["denoise_ce_rows"],
            "decoder_ce_rows": card["decoder_ce_rows"],
            "unsafe_authority_rows": card["unsafe_authority_rows"],
            "routes": card["route_counts"],
        },
        "decision": "Recovered denoise/diffusion repair contract for masked-span repair planning. Denoise CE remains closed.",
        "next_best_step": "Attach denoise/diffusion repair contract to central graph, then recover adversarial_hard_negative_generator.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join(["# Stage8731 Denoise/Diffusion Repair Contract Readiness", "", f"Passed: `{passed}`", "", "Recovered no-execution masked-span repair planning for bad outputs. Denoise CE, decoder CE, and model execution remain closed.", ""]), encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
