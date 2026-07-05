#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path

from model_output_packet_telemetry_contract_builder import AUTHORITY_CLOSED, build_card, build_contract_rows

ROOT = Path(__file__).resolve().parents[1]
STAGE = 8823
NAME = "stage8823_model_output_packet_telemetry_contract_manifest"
SOURCE = ROOT / "runs/local/artifacts/stage8820_heldout_non_ce_decoder_eval_design_manifest/heldout_non_ce_decoder_eval_design_manifest.jsonl"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "MODEL_OUTPUT_PACKET_TELEMETRY_CONTRACT_MANIFEST_STAGE8823.md"


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    design_rows = [json.loads(line) for line in SOURCE.read_text(encoding="utf-8").splitlines() if line.strip()]
    rows = build_contract_rows(design_rows)
    manifest = OUT_DIR / "model_output_packet_telemetry_contract_manifest.jsonl"
    manifest.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")
    metrics = {**AUTHORITY_CLOSED, **build_card(rows), "source_rows": len(design_rows), "source_failures": [] if SOURCE.exists() else [f"missing:{SOURCE}"]}
    passed = (
        bool(rows)
        and metrics["source_failures"] == []
        and metrics["authority_rows"] == 0
        and metrics["loss_rows"] == 0
        and metrics["probe_ready_rows"] == 0
        and metrics["decoder_ce_eligible_now_rows"] == 0
        and metrics["missing_required_field_rows"] == 0
        and metrics["missing_required_check_rows"] == 0
        and metrics["missing_required_telemetry_rows"] == 0
        and metrics["forbidden_visible_rows"] == 0
    )
    card = {
        "stage": STAGE,
        "stage_name": NAME,
        "passed": passed,
        "authority": AUTHORITY_CLOSED,
        "metrics": metrics,
        "artifacts": {"manifest": str(manifest.relative_to(ROOT)), "source": str(SOURCE.relative_to(ROOT))},
        "decision": "Defined future model-output packet schema/telemetry contract with no execution, no loss, and no raw target/body/runtime/Gemma fields." if passed else "Packet schema/telemetry contract failed.",
        "next_best_step": "Attach packet telemetry contract to graph, then build a no-execution future probe packet readiness audit.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    (OUT_DIR / "model_output_packet_telemetry_contract_card.json").write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    SUMMARY.write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage8823 Model Output Packet Telemetry Contract Manifest",
        "",
        f"Passed: `{passed}`",
        "",
        f"Rows: `{metrics['rows']}`",
        f"Source rows: `{metrics['source_rows']}`",
        f"Authority rows: `{metrics['authority_rows']}`",
        f"Loss rows: `{metrics['loss_rows']}`",
        f"Probe-ready rows: `{metrics['probe_ready_rows']}`",
        f"Decoder CE eligible now rows: `{metrics['decoder_ce_eligible_now_rows']}`",
        "",
        "This is a schema/telemetry contract only. It defines required future packet fields, checks, and tensor/logit decode telemetry, but does not run a model or authorize CE/runtime/scoring.",
        "",
    ]), encoding="utf-8")
    print(json.dumps(card, indent=2, sort_keys=True))
    raise SystemExit(0 if passed else 1)


if __name__ == "__main__":
    main()
