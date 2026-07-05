#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path

from moe_lora_adapter_router_contract import router_card


ROOT = Path(__file__).resolve().parents[1]
STAGE = 8729
NAME = "stage8729_moe_lora_adapter_router_contract_readiness"
OUT_DIR = ROOT / "runs" / "local" / "artifacts" / NAME
SUMMARY = ROOT / "runs" / "summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "MOE_LORA_ADAPTER_ROUTER_CONTRACT_READINESS_STAGE8729.md"

AUTHORITY_CLOSED = {
    "model_execution_authorized_next": False,
    "training_authorized_next": False,
    "adapter_training_authorized_next": False,
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
        {"row_id": "composed", "language_family": "python", "task_family": "repo_repair", "repo_family": "test_heavy", "language_slice_ready": True, "task_slice_ready": True, "repo_slice_ready": True, "language_confidence": .92, "task_confidence": .86, "repo_confidence": .80},
        {"row_id": "slice", "language_family": "rust", "task_family": "repo_repair", "language_slice_ready": False, "task_slice_ready": True, "language_confidence": .84, "task_confidence": .80},
        {"row_id": "base", "language_family": "unknown_lang", "task_family": "repo_repair", "language_slice_ready": True, "task_slice_ready": True, "language_confidence": .90, "task_confidence": .90},
        {"row_id": "abstain", "language_family": "python", "task_family": "repo_repair", "language_slice_ready": True, "task_slice_ready": True, "authority": {"adapter_training": True}, "ood_score": .9},
    ]
    card = router_card(rows)
    sample_path = OUT_DIR / "moe_lora_adapter_router_contract_sample_card.json"
    sample_path.write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    passed = (
        card["rows"] == 4
        and card["unsafe_decisions"] == 0
        and card["adapter_shadow_rows"] == 1
        and card["route_counts"].get("ROUTE_COMPOSED_ADAPTER_SHADOW") == 1
        and card["route_counts"].get("REQUEST_SLICE_EVIDENCE") == 1
        and card["route_counts"].get("USE_BASE_SHARED") == 1
        and card["route_counts"].get("ABSTAIN_ADAPTER_ROUTE") == 1
        and card["authority"]["training"] is False
        and card["authority"]["adapter_training"] is False
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
            "adapter_shadow_rows": card["adapter_shadow_rows"],
            "routes": card["route_counts"],
        },
        "decision": "Recovered no-execution MoE/LoRA adapter router contract. It can emit shadow adapter route hints only; slice readiness, OOD, leak, and authority gates force base/shared, retrieval of slice evidence, or abstain.",
        "next_best_step": "Attach MoE/LoRA adapter router contract to central graph, then recover denoise_diffusion_repair_contract.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage8729 MoE/LoRA Adapter Router Contract Readiness",
        "",
        f"Passed: `{passed}`",
        "",
        "Recovered conservative no-execution adapter routing contract for task, language, and repo-family specialists.",
        "",
        "Adapter routes are shadow hints only. No adapter training, model execution, decoder CE, checkpoint export, runtime, Gemma, or promotion authority is opened.",
        "",
    ]), encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
