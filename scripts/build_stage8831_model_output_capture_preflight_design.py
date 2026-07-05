#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path

from model_output_capture_preflight_design_builder import build_card, build_preflight_rows
from model_output_packet_telemetry_contract_builder import AUTHORITY_CLOSED

ROOT = Path(__file__).resolve().parents[1]
STAGE = 8831
NAME = "stage8831_model_output_capture_preflight_design"
SOURCE = ROOT / "runs/local/artifacts/stage8828_synthetic_packet_validator_dry_run/synthetic_placeholder_packets.jsonl"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "MODEL_OUTPUT_CAPTURE_PREFLIGHT_DESIGN_STAGE8831.md"


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    packets = [json.loads(line) for line in SOURCE.read_text(encoding="utf-8").splitlines() if line.strip()]
    rows = build_preflight_rows(packets)
    manifest = OUT_DIR / "model_output_capture_preflight_design_manifest.jsonl"
    manifest.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")
    metrics = {**AUTHORITY_CLOSED, **build_card(rows), "source_rows": len(packets), "source_failures": [] if SOURCE.exists() else [f"missing:{SOURCE}"]}
    passed = (
        bool(rows)
        and metrics["source_failures"] == []
        and metrics["authority_rows"] == 0
        and metrics["loss_rows"] == 0
        and metrics["probe_ready_rows"] == 0
        and metrics["ready_for_model_execution_rows"] == 0
        and metrics["ready_for_decoder_ce_rows"] == 0
        and metrics["model_output_rows"] == 0
        and metrics["missing_preflight_field_rows"] == 0
        and metrics["missing_blocked_operation_rows"] == 0
    )
    card = {
        "stage": STAGE,
        "stage_name": NAME,
        "passed": passed,
        "authority": AUTHORITY_CLOSED,
        "metrics": metrics,
        "artifacts": {"manifest": str(manifest.relative_to(ROOT)), "source": str(SOURCE.relative_to(ROOT))},
        "decision": "Defined authority-closed model-output capture preflight design without model execution." if passed else "Model-output capture preflight design failed.",
        "next_best_step": "Attach capture preflight design to graph, then build a static preflight gate audit. Keep model execution/training/CE closed.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    (OUT_DIR / "model_output_capture_preflight_design_card.json").write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    SUMMARY.write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage8831 Model Output Capture Preflight Design",
        "",
        f"Passed: `{passed}`",
        "",
        f"Rows: `{metrics['rows']}`",
        f"Source rows: `{metrics['source_rows']}`",
        f"Authority rows: `{metrics['authority_rows']}`",
        f"Loss rows: `{metrics['loss_rows']}`",
        f"Ready for model execution rows: `{metrics['ready_for_model_execution_rows']}`",
        f"Model output rows: `{metrics['model_output_rows']}`",
        "",
        "This is a design manifest only. It defines future capture inputs/outputs and blocked operations, while keeping model execution, CE, runtime, Gemma, scoring, source/body emission, and promotion closed.",
        "",
    ]), encoding="utf-8")
    print(json.dumps(card, indent=2, sort_keys=True))
    raise SystemExit(0 if passed else 1)


if __name__ == "__main__":
    main()
