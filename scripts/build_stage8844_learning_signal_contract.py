#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path

from learning_signal_contract_builder import build_card, build_learning_signal_rows
from model_output_packet_telemetry_contract_builder import AUTHORITY_CLOSED

ROOT = Path(__file__).resolve().parents[1]
STAGE = 8844
NAME = "stage8844_learning_signal_contract"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "LEARNING_SIGNAL_CONTRACT_STAGE8844.md"


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    rows = build_learning_signal_rows()
    manifest = OUT_DIR / "learning_signal_contract_manifest.jsonl"
    manifest.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")
    metrics = {**AUTHORITY_CLOSED, **build_card(rows), "authority_rows": 0}
    passed = metrics["passed"] is True
    card = {
        "stage": STAGE,
        "stage_name": NAME,
        "passed": passed,
        "authority": AUTHORITY_CLOSED,
        "metrics": metrics,
        "artifacts": {"manifest": str(manifest.relative_to(ROOT))},
        "decision": "Recovered learning-signal improvement contract for typed supervision, contrastive siblings, telemetry, representation cleanup, and loss weighting. No training opened.",
        "next_best_step": "Attach learning-signal contract to graph, then recover dataset/trainer implementation plan. Keep training and decoder CE closed.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    (OUT_DIR / "learning_signal_contract_card.json").write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    SUMMARY.write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage8844 Learning Signal Contract",
        "",
        f"Passed: `{passed}`",
        "",
        f"Rows: `{metrics['rows']}`",
        f"Ready rows: `{metrics['learning_signal_contract_ready_rows']}`",
        f"Authority rows: `{metrics['authority_rows']}`",
        f"Loss-open rows: `{metrics['loss_open_rows']}`",
        "",
        "Contract scope:",
        "",
        "- local typed supervision for structured/policy heads",
        "- counterfactual sibling obligations",
        "- row-field logits/losses/confusion/high-confidence-wrong telemetry",
        "- lower-noise typed serialization requirements",
        "- explicit loss weighting and gradient-routing telemetry",
        "",
        "No training, decoder CE, model execution, runtime, Gemma, scoring, source/body emission, or promotion is authorized.",
        "",
    ]), encoding="utf-8")
    print(json.dumps(card, indent=2, sort_keys=True))
    raise SystemExit(0 if passed else 1)


if __name__ == "__main__":
    main()
