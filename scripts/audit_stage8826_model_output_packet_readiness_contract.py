#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path

from model_output_packet_readiness_audit import audit_rows
from model_output_packet_telemetry_contract_builder import AUTHORITY_CLOSED

ROOT = Path(__file__).resolve().parents[1]
STAGE = 8826
NAME = "stage8826_model_output_packet_readiness_contract_audit"
SOURCE = ROOT / "runs/local/artifacts/stage8823_model_output_packet_telemetry_contract_manifest/model_output_packet_telemetry_contract_manifest.jsonl"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "MODEL_OUTPUT_PACKET_READINESS_CONTRACT_AUDIT_STAGE8826.md"


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
        "ready_for_model_execution": False,
        "ready_for_decoder_ce": False,
    }
    card = {
        "stage": STAGE,
        "stage_name": NAME,
        "passed": passed,
        "authority": AUTHORITY_CLOSED,
        "metrics": metrics,
        "artifacts": {"source": str(SOURCE.relative_to(ROOT)), "audit_card": str((OUT_DIR / "model_output_packet_readiness_contract_audit_card.json").relative_to(ROOT))},
        "decision": "Packet contract is schema-ready for a future no-execution packet validator design; it is not model-probe-ready or CE-ready." if passed else "Packet readiness contract audit failed.",
        "next_best_step": "Build a no-execution packet validator dry-run using synthetic placeholder packets, not model outputs. Keep model execution/training/CE closed.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    (OUT_DIR / "model_output_packet_readiness_contract_audit_card.json").write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    SUMMARY.write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage8826 Model Output Packet Readiness Contract Audit",
        "",
        f"Passed: `{passed}`",
        "",
        f"Rows: `{metrics['rows']}`",
        f"Contract-ready rows: `{metrics['contract_ready_rows']}`",
        f"Authority rows: `{metrics['authority_rows']}`",
        f"Loss-open rows: `{metrics['loss_open_rows']}`",
        f"Unexpected probe-ready rows: `{metrics['unexpected_probe_ready_rows']}`",
        "",
        "This audit validates schema readiness only. It does not authorize model execution, decoder CE, denoise CE, runtime, scoring, Gemma, or promotion.",
        "",
    ]), encoding="utf-8")
    print(json.dumps(card, indent=2, sort_keys=True))
    raise SystemExit(0 if passed else 1)


if __name__ == "__main__":
    main()
