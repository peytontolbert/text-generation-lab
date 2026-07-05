#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path

from learning_signal_implementation_plan_builder import build_card, build_plan_rows
from model_output_packet_telemetry_contract_builder import AUTHORITY_CLOSED

ROOT = Path(__file__).resolve().parents[1]
STAGE = 8847
NAME = "stage8847_learning_signal_implementation_plan"
SOURCE = ROOT / "runs/local/artifacts/stage8844_learning_signal_contract/learning_signal_contract_manifest.jsonl"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "LEARNING_SIGNAL_IMPLEMENTATION_PLAN_STAGE8847.md"


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    contract_rows = [json.loads(line) for line in SOURCE.read_text(encoding="utf-8").splitlines() if line.strip()]
    rows = build_plan_rows(contract_rows)
    manifest = OUT_DIR / "learning_signal_implementation_plan_manifest.jsonl"
    manifest.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")
    metrics = {**AUTHORITY_CLOSED, **build_card(rows), "source_rows": len(contract_rows), "source_failures": [] if SOURCE.exists() else [f"missing:{SOURCE}"], "authority_rows": 0}
    passed = metrics["passed"] is True and metrics["source_failures"] == []
    card = {
        "stage": STAGE,
        "stage_name": NAME,
        "passed": passed,
        "authority": AUTHORITY_CLOSED,
        "metrics": metrics,
        "artifacts": {"manifest": str(manifest.relative_to(ROOT)), "source": str(SOURCE.relative_to(ROOT))},
        "decision": "Recovered dataset/trainer implementation plan for learning-signal improvements. No code patch or training opened.",
        "next_best_step": "Attach implementation plan to graph, then recover implementation-plan gate audit. Keep training and decoder CE closed.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    (OUT_DIR / "learning_signal_implementation_plan_card.json").write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    SUMMARY.write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage8847 Learning Signal Implementation Plan",
        "",
        f"Passed: `{passed}`",
        "",
        f"Plan rows: `{metrics['rows']}`",
        f"Ready rows: `{metrics['implementation_plan_ready_rows']}`",
        f"Training authorized: `{metrics['training_authorized']}`",
        f"Decoder CE authorized: `{metrics['decoder_ce_authorized']}`",
        "",
        "This is an implementation plan only. It specifies future changes to `training_data.py`, `training_loop.py`, `training_telemetry_metrics.py`, and `modeling_transformer.py`, but does not apply those changes and does not authorize training.",
        "",
    ]), encoding="utf-8")
    print(json.dumps(card, indent=2, sort_keys=True))
    raise SystemExit(0 if passed else 1)


if __name__ == "__main__":
    main()
