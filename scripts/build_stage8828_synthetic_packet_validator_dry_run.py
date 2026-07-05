#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path

from model_output_packet_telemetry_contract_builder import AUTHORITY_CLOSED
from model_output_packet_validator_dry_run import build_placeholder_packets, validate_packets

ROOT = Path(__file__).resolve().parents[1]
STAGE = 8828
NAME = "stage8828_synthetic_packet_validator_dry_run"
SOURCE = ROOT / "runs/local/artifacts/stage8823_model_output_packet_telemetry_contract_manifest/model_output_packet_telemetry_contract_manifest.jsonl"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "SYNTHETIC_PACKET_VALIDATOR_DRY_RUN_STAGE8828.md"


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    contract_rows = [json.loads(line) for line in SOURCE.read_text(encoding="utf-8").splitlines() if line.strip()]
    packets = build_placeholder_packets(contract_rows)
    audit = validate_packets(packets)
    packet_path = OUT_DIR / "synthetic_placeholder_packets.jsonl"
    packet_path.write_text("".join(json.dumps(packet, sort_keys=True) + "\n" for packet in packets), encoding="utf-8")
    failures = [] if SOURCE.exists() else [f"missing:{SOURCE}"]
    passed = audit["passed"] and not failures
    metrics = {
        **AUTHORITY_CLOSED,
        **{k: v for k, v in audit.items() if k != "passed"},
        "authority_rows": audit["authority_open_rows"],
        "source_rows": len(contract_rows),
        "source_failures": failures,
        "synthetic_packet_rows": len(packets),
        "real_model_output_rows": 0,
        "model_execution_authorized_now": False,
        "ready_for_model_execution": False,
        "ready_for_decoder_ce": False,
    }
    card = {
        "stage": STAGE,
        "stage_name": NAME,
        "passed": passed,
        "authority": AUTHORITY_CLOSED,
        "metrics": metrics,
        "artifacts": {"packets": str(packet_path.relative_to(ROOT)), "source": str(SOURCE.relative_to(ROOT))},
        "decision": "Synthetic placeholder packets validate against the packet contract. This proves validator structure, not model decode quality." if passed else "Synthetic packet validator dry run failed.",
        "next_best_step": "Attach dry-run validator to graph and then design the smallest authority-closed model-output capture preflight. Do not run a model yet.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    (OUT_DIR / "synthetic_packet_validator_dry_run_card.json").write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    SUMMARY.write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage8828 Synthetic Packet Validator Dry Run",
        "",
        f"Passed: `{passed}`",
        "",
        f"Synthetic packet rows: `{metrics['synthetic_packet_rows']}`",
        f"Valid packet rows: `{metrics['valid_packet_rows']}`",
        f"Real model output rows: `{metrics['real_model_output_rows']}`",
        f"Authority rows: `{metrics['authority_rows']}`",
        "",
        "This validates the packet structure using synthetic placeholder packets only. It is not a decoder probe and does not authorize execution, CE, runtime, scoring, Gemma, or promotion.",
        "",
    ]), encoding="utf-8")
    print(json.dumps(card, indent=2, sort_keys=True))
    raise SystemExit(0 if passed else 1)


if __name__ == "__main__":
    main()
