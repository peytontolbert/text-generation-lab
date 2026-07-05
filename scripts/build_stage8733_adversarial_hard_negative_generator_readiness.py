#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path

from adversarial_hard_negative_generator import ATTACK_TYPES, hard_negative_card


ROOT = Path(__file__).resolve().parents[1]
STAGE = 8733
NAME = "stage8733_adversarial_hard_negative_generator_readiness"
OUT_DIR = ROOT / "runs" / "local" / "artifacts" / NAME
SUMMARY = ROOT / "runs" / "summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "ADVERSARIAL_HARD_NEGATIVE_GENERATOR_READINESS_STAGE8733.md"

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
    seeds = [
        {"row_id": "seed_symbol", "objective_family": "symbol_binding", "semantic_key": "symbol:x", "corrupted_state": {"language": "python", "evidence": "source span", "source_excerpt": "def x(): pass"}},
        {"row_id": "seed_patch", "objective_family": "patch_operator", "semantic_key": "patch:y", "corrupted_state": {"language": "python", "evidence": "patch span", "source_excerpt": "return y"}},
    ]
    card = hard_negative_card(seeds)
    sample_path = OUT_DIR / "adversarial_hard_negative_generator_sample_card.json"
    manifest_path = OUT_DIR / "adversarial_hard_negative_rows.jsonl"
    sample_path.write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    manifest_path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in card["rows"]), encoding="utf-8")
    audit = card["audit"]
    passed = (
        audit["passed"]
        and card["generated_rows"] == len(seeds) * len(ATTACK_TYPES)
        and audit["authority_rows"] == 0
        and audit["loss_enabled_rows"] == 0
        and audit["decode_enabled_rows"] == 0
    )
    summary = {
        "stage": STAGE,
        "name": NAME,
        "stage_name": NAME,
        "passed": passed,
        "authority": AUTHORITY_CLOSED,
        "artifacts": {
            "sample_card": str(sample_path.relative_to(ROOT)),
            "manifest": str(manifest_path.relative_to(ROOT)),
        },
        "metrics": {
            **AUTHORITY_CLOSED,
            "seed_rows": card["seed_rows"],
            "generated_rows": card["generated_rows"],
            "attack_counts": audit["attack_counts"],
            "authority_rows": audit["authority_rows"],
            "loss_enabled_rows": audit["loss_enabled_rows"],
            "decode_enabled_rows": audit["decode_enabled_rows"],
        },
        "decision": "Recovered no-authority adversarial hard-negative generator for shortcut/leakage/proxy audit hardening.",
        "next_best_step": "Attach adversarial hard-negative generator to central graph, then recover confidence_ood_head_contract.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join(["# Stage8733 Adversarial Hard-Negative Generator Readiness", "", f"Passed: `{passed}`", "", "Recovered no-authority generator for proxy-label swaps, evidence-removed rows, leak-injection rows, duplicate collisions, and misleading retrieval probes.", "", "Generated rows are audit negatives only: no losses, no decode, no training, no runtime.", ""]), encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
