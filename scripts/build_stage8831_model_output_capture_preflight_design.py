#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path

from model_output_capture_preflight_builder import build_card, build_preflight_rows
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
    manifest = OUT_DIR / "model_output_capture_preflight_design.jsonl"
    manifest.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")
    failures = [] if SOURCE.exists() else [f"missing:{SOURCE}"]
    base_metrics = build_card(rows)
    metrics = {
        **AUTHORITY_CLOSED,
        **{k: v for k, v in base_metrics.items() if k != "passed"},
        "authority_rows": base_metrics["authority_open_rows"],
        "source_rows": len(packets),
        "source_failures": failures,
    }
    passed = base_metrics["passed"] and not failures
    card = {
        "stage": STAGE,
        "stage_name": NAME,
        "passed": passed,
        "authority": AUTHORITY_CLOSED,
        "metrics": metrics,
        "artifacts": {
            "manifest": str(manifest.relative_to(ROOT)),
            "source": str(SOURCE.relative_to(ROOT)),
        },
        "decision": "Designed authority-closed model-output capture preflight with no model output artifacts and no CE/runtime/scoring authority." if passed else "Model-output capture preflight design failed.",
        "next_best_step": "Audit capture preflight design and attach it to the graph. Do not run a model yet.",
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
        f"Preflight-design-ready rows: `{metrics['preflight_design_ready_rows']}`",
        f"Model output rows: `{metrics['model_output_rows']}`",
        f"Artifact write rows: `{metrics['artifact_write_rows']}`",
        f"Authority rows: `{metrics['authority_rows']}`",
        "",
        "This is a design-only preflight for future model-output capture. It does not run a model, write model outputs, open decoder CE, open runtime, score, call Gemma, or authorize promotion.",
        "",
    ]), encoding="utf-8")
    print(json.dumps(card, indent=2, sort_keys=True))
    raise SystemExit(0 if passed else 1)


if __name__ == "__main__":
    main()
