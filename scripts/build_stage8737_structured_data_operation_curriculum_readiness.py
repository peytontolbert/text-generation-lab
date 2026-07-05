#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path

from structured_data_operation_curriculum import build_seed_rows, curriculum_card


ROOT = Path(__file__).resolve().parents[1]
STAGE = 8737
NAME = "stage8737_structured_data_operation_curriculum_readiness"
OUT_DIR = ROOT / "runs" / "local" / "artifacts" / NAME
SUMMARY = ROOT / "runs" / "summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "STRUCTURED_DATA_OPERATION_CURRICULUM_READINESS_STAGE8737.md"

AUTHORITY_CLOSED = {
    "model_execution_authorized_next": False,
    "training_authorized_next": False,
    "decoder_ce_training_authorized_next": False,
    "denoise_ce_training_authorized_next": False,
    "runtime_authorized": False,
    "source_body_authorized": False,
    "gemma_authorized": False,
    "promotion_ready": False,
}


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)
    rows = build_seed_rows()
    card = curriculum_card(rows)
    sample_path = OUT_DIR / "structured_data_operation_curriculum_sample_card.json"
    manifest_path = OUT_DIR / "structured_data_operation_curriculum_rows.jsonl"
    sample_path.write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    manifest_path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")
    forbidden_loss_rows = 0
    authority_rows = 0
    for row in rows:
        authority_rows += int(any(value is True for value in row.get("authority", {}).values()))
        forbidden_loss_rows += int(any(row.get("loss_mask", {}).get(key) is True for key in ["decoder_ce", "denoise_ce", "runtime_reward"]))
    passed = (
        card["passed"]
        and card["rows"] == 7
        and len(card["structure_counts"]) == 7
        and authority_rows == 0
        and forbidden_loss_rows == 0
    )
    summary = {
        "stage": STAGE,
        "name": NAME,
        "stage_name": NAME,
        "passed": passed,
        "authority": AUTHORITY_CLOSED,
        "artifacts": {
            "sample_card": str(sample_path.relative_to(ROOT)),
            "manifest": str(manifest_path.relative_to(ROOT)),
        },
        "metrics": {
            **AUTHORITY_CLOSED,
            "authority_rows": authority_rows,
            "rows": card["rows"],
            "structure_counts": card["structure_counts"],
            "operator_counts": card["operator_counts"],
            "audit_failures": len(card["audit_failures"]),
            "forbidden_loss_rows": forbidden_loss_rows,
        },
        "decision": "Recovered structured data operation curriculum contract for table/json/graph/AST/log/workflow/memory state operations. It is structured-only and opens no decoder, denoise, runtime, or training authority.",
        "next_best_step": "Attach structured data operation curriculum to central graph, then recover semantic_equivalence_metamorphic_verifier.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage8737 Structured Data Operation Curriculum Readiness",
        "",
        f"Passed: `{passed}`",
        "",
        "Recovered structured operation rows for table, JSON, graph, AST, log trace, workflow, and memory state operations.",
        "",
        "Rows are structured-only. Decoder CE, denoise CE, runtime reward, source/body emission, model execution, Gemma, and promotion remain closed.",
        "",
    ]), encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
