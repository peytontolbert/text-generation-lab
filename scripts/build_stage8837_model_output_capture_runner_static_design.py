#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path

from model_output_capture_runner_static_design_builder import build_card, build_runner_design_rows
from model_output_packet_telemetry_contract_builder import AUTHORITY_CLOSED

ROOT = Path(__file__).resolve().parents[1]
STAGE = 8837
NAME = "stage8837_model_output_capture_runner_static_design"
SOURCE = ROOT / "runs/local/artifacts/stage8831_model_output_capture_preflight_design/model_output_capture_preflight_design.jsonl"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "MODEL_OUTPUT_CAPTURE_RUNNER_STATIC_DESIGN_STAGE8837.md"


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    rows_in = [json.loads(line) for line in SOURCE.read_text(encoding="utf-8").splitlines() if line.strip()]
    rows = build_runner_design_rows(rows_in)
    manifest = OUT_DIR / "model_output_capture_runner_static_design_manifest.jsonl"
    manifest.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")
    metrics = {**AUTHORITY_CLOSED, **build_card(rows), "source_rows": len(rows_in), "source_failures": [] if SOURCE.exists() else [f"missing:{SOURCE}"]}
    passed = (
        metrics["source_failures"] == []
        and metrics["passed"] is True
        and metrics["authority_open_rows"] == 0
        and metrics["loss_open_rows"] == 0
        and metrics["execution_open_rows"] == 0
        and metrics["model_output_rows"] == 0
    )
    card = {
        "stage": STAGE,
        "stage_name": NAME,
        "passed": passed,
        "authority": AUTHORITY_CLOSED,
        "metrics": metrics,
        "artifacts": {"manifest": str(manifest.relative_to(ROOT)), "source": str(SOURCE.relative_to(ROOT))},
        "decision": "Defined future model-output capture runner interface statically without execution." if passed else "Future runner static design failed.",
        "next_best_step": "Attach runner static design to graph, then recover authority-ticket schema. Do not run a model yet.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    (OUT_DIR / "model_output_capture_runner_static_design_card.json").write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    SUMMARY.write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage8837 Model Output Capture Runner Static Design",
        "",
        f"Passed: `{passed}`",
        "",
        f"Rows: `{metrics['rows']}`",
        f"Runner static design ready rows: `{metrics['runner_static_design_ready_rows']}`",
        f"Execution-open rows: `{metrics['execution_open_rows']}`",
        f"Model output rows: `{metrics['model_output_rows']}`",
        "",
        "This is a static runner-interface design only. It defines required flags, artifact paths, and assertions for a future capture runner while keeping model execution, decode, CE, runtime, Gemma, scoring, and promotion closed.",
        "",
    ]), encoding="utf-8")
    print(json.dumps(card, indent=2, sort_keys=True))
    raise SystemExit(0 if passed else 1)


if __name__ == "__main__":
    main()
