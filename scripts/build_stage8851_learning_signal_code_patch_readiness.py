#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path

from learning_signal_code_patch_readiness_builder import build_card, build_readiness_rows
from model_output_packet_telemetry_contract_builder import AUTHORITY_CLOSED

ROOT = Path(__file__).resolve().parents[1]
STAGE = 8851
NAME = "stage8851_learning_signal_code_patch_readiness"
SOURCE = ROOT / "runs/local/artifacts/stage8847_learning_signal_implementation_plan/learning_signal_implementation_plan_manifest.jsonl"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "LEARNING_SIGNAL_CODE_PATCH_READINESS_STAGE8851.md"


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    plan_rows = [json.loads(line) for line in SOURCE.read_text(encoding="utf-8").splitlines() if line.strip()]
    rows = build_readiness_rows(plan_rows)
    manifest = OUT_DIR / "learning_signal_code_patch_readiness_manifest.jsonl"
    manifest.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")
    metrics = {**AUTHORITY_CLOSED, **build_card(rows), "source_rows": len(plan_rows), "source_failures": [] if SOURCE.exists() else [f"missing:{SOURCE}"], "authority_rows": 0}
    passed = metrics["passed"] is True and metrics["source_failures"] == []
    card = {
        "stage": STAGE,
        "stage_name": NAME,
        "passed": passed,
        "authority": AUTHORITY_CLOSED,
        "metrics": metrics,
        "artifacts": {"manifest": str(manifest.relative_to(ROOT)), "source": str(SOURCE.relative_to(ROOT))},
        "decision": "Recovered code-patch readiness checklist for learning-signal implementation. No code patch or training opened.",
        "next_best_step": "Attach code-patch readiness checklist to graph, then audit readiness gates. Keep training and decoder CE closed.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    (OUT_DIR / "learning_signal_code_patch_readiness_card.json").write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    SUMMARY.write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage8851 Learning Signal Code Patch Readiness",
        "",
        f"Passed: `{passed}`",
        "",
        f"Rows: `{metrics['rows']}`",
        f"Readiness rows: `{metrics['code_patch_readiness_rows']}`",
        f"Code patch authorized: `{metrics['code_patch_authorized']}`",
        f"Training authorized: `{metrics['training_authorized']}`",
        f"Decoder CE authorized: `{metrics['decoder_ce_authorized']}`",
        "",
        "This is a readiness checklist only. It does not apply code changes or authorize training.",
        "",
    ]), encoding="utf-8")
    print(json.dumps(card, indent=2, sort_keys=True))
    raise SystemExit(0 if passed else 1)


if __name__ == "__main__":
    main()
