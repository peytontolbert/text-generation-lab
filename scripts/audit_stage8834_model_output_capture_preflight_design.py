#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path

from model_output_capture_preflight_audit import audit_rows
from model_output_packet_telemetry_contract_builder import AUTHORITY_CLOSED

ROOT = Path(__file__).resolve().parents[1]
STAGE = 8834
NAME = "stage8834_model_output_capture_preflight_design_audit"
SOURCE = ROOT / "runs/local/artifacts/stage8831_model_output_capture_preflight_design/model_output_capture_preflight_design.jsonl"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "MODEL_OUTPUT_CAPTURE_PREFLIGHT_DESIGN_AUDIT_STAGE8834.md"


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    rows = [json.loads(line) for line in SOURCE.read_text(encoding="utf-8").splitlines() if line.strip()]
    audit = audit_rows(rows)
    failures = [] if SOURCE.exists() else [f"missing:{SOURCE}"]
    passed = audit["passed"] and not failures
    metrics = {
        **AUTHORITY_CLOSED,
        **{k: v for k, v in audit.items() if k not in {"passed", "authority"}},
        "authority_rows": audit["authority_open_rows"],
        "source_failures": failures,
        "model_probe_authorized_now": False,
    }
    card = {
        "stage": STAGE,
        "stage_name": NAME,
        "passed": passed,
        "authority": AUTHORITY_CLOSED,
        "metrics": metrics,
        "artifacts": {"source": str(SOURCE.relative_to(ROOT)), "audit_card": str((OUT_DIR / "model_output_capture_preflight_design_audit_card.json").relative_to(ROOT))},
        "decision": "Capture preflight design passed closed-authority audit; it is still not a model run or CE authorization." if passed else "Capture preflight design audit failed.",
        "next_best_step": "Attach preflight audit to graph and then design future runner interface statically. Do not run a model yet.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    (OUT_DIR / "model_output_capture_preflight_design_audit_card.json").write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    SUMMARY.write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join(["# Stage8834 Model Output Capture Preflight Design Audit", "", f"Passed: `{passed}`", "", f"Rows: `{metrics['rows']}`", f"Audit-ready rows: `{metrics['audit_ready_rows']}`", f"Execution-allowed rows: `{metrics['execution_allowed_rows']}`", f"Model output rows: `{metrics['model_output_rows']}`", f"Artifact write rows: `{metrics['artifact_write_rows']}`", f"Authority rows: `{metrics['authority_rows']}`", "", "This audit confirms the capture preflight remains design-only. It does not authorize model execution, decoder CE, runtime, Gemma, scoring, or promotion.", ""]), encoding="utf-8")
    print(json.dumps(card, indent=2, sort_keys=True))
    raise SystemExit(0 if passed else 1)


if __name__ == "__main__":
    main()
