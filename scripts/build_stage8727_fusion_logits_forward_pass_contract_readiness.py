#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path

from fusion_logits_forward_pass_contract import fusion_card


ROOT = Path(__file__).resolve().parents[1]
STAGE = 8727
NAME = "stage8727_fusion_logits_forward_pass_contract_readiness"
OUT_DIR = ROOT / "runs" / "local" / "artifacts" / NAME
SUMMARY = ROOT / "runs" / "summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "FUSION_LOGITS_FORWARD_PASS_CONTRACT_READINESS_STAGE8727.md"

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
        {"row_id": "ok", "structured_confidence": .92, "retrieval_confidence": .9, "retrieval_coverage": .88, "verifier_pass": True, "verifier_confidence": .8, "decoder_confidence": .8, "decoder_budget_ok": True, "decoder_schema_ok": True, "ood_score": .1},
        {"row_id": "retrieve", "structured_confidence": .9, "retrieval_confidence": .2, "retrieval_coverage": .3, "verifier_pass": True, "decoder_budget_ok": True, "decoder_schema_ok": True},
        {"row_id": "repair", "structured_confidence": .9, "retrieval_confidence": .9, "retrieval_coverage": .9, "verifier_failure": "symbol_binding_failure", "decoder_budget_ok": True, "decoder_schema_ok": True},
        {"row_id": "abstain", "authority": {"decoder_ce": True}, "internal_leak": True, "structured_confidence": 1.0, "retrieval_confidence": 1.0, "retrieval_coverage": 1.0},
    ]
    card = fusion_card(rows)
    sample_path = OUT_DIR / "fusion_logits_forward_pass_contract_sample_card.json"
    sample_path.write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    passed = (
        card["rows"] == 4
        and card["unsafe_decisions"] == 0
        and card["decoder_shadow_rows"] == 1
        and card["route_counts"].get("ABSTAIN_UNSAFE") == 1
        and card["route_counts"].get("RETRIEVE_MORE") == 1
        and card["route_counts"].get("REPAIR_STRUCTURED") == 1
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
            "unsafe_decisions": card["unsafe_decisions"],
            "decoder_shadow_rows": card["decoder_shadow_rows"],
            "routes": card["route_counts"],
        },
        "decision": "Recovered no-execution fusion logits/forward-pass contract; it gates decoder shadow access but authorizes no decoder CE or model execution.",
        "next_best_step": "Attach fusion contract to central graph, then recover moe_lora_adapter_router_contract.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join(["# Stage8727 Fusion Logits Forward-Pass Contract Readiness", "", f"Passed: `{passed}`", "", "Recovered conservative no-execution fusion contract over structured heads, retrieval, verifier, uncertainty, and decoder-readiness signals.", "", "Authority remains closed.", ""]), encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
