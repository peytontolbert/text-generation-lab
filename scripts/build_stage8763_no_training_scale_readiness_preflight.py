#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path

from audit_curriculum_compiler_outputs import audit_dir
from curriculum_compiler import AUTHORITY_CLOSED, compile_rows, write_jsonl
from gate_status_contract import passed_gate_status

ROOT = Path(__file__).resolve().parents[1]
STAGE = 8763
NAME = "stage8763_no_training_scale_readiness_preflight"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "NO_TRAINING_SCALE_READINESS_PREFLIGHT_STAGE8763.md"


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    rows = [
        {"row_id": "clean_structured", "split": "train", "route": "KEEP_STRUCTURED", "gate_status": passed_gate_status()},
        {"row_id": "clean_bounded_decoder", "split": "eval", "route": "KEEP_BOUNDED_DECODER", "gate_status": passed_gate_status()},
        {"row_id": "missing_gate_card", "split": "train", "route": "KEEP_STRUCTURED"},
        {"row_id": "schema_failed", "split": "eval", "route": "KEEP_STRUCTURED", "gate_status": passed_gate_status(schema_drift_detector=False)},
        {"row_id": "contamination_failed_decoder", "split": "strict_eval", "route": "KEEP_BOUNDED_DECODER", "gate_status": passed_gate_status(contamination_leakage_detector=False)},
    ]
    input_path = OUT_DIR / "preflight_input_rows.jsonl"
    write_jsonl(input_path, rows)
    compiled_dir = OUT_DIR / "compiled"
    buckets, compile_card = compile_rows(rows, allow_decoder=False, allow_denoise=False, allow_runtime=False, require_recovered_gates=True)
    compiled_dir.mkdir(parents=True, exist_ok=True)
    for objective, objective_rows in buckets.items():
        write_jsonl(compiled_dir / f"{objective}.jsonl", objective_rows)
    (compiled_dir / "compile_card.json").write_text(json.dumps(compile_card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    audit_card = audit_dir(compiled_dir, allow_decoder=False, allow_denoise=False, allow_runtime=False)
    audit_path = OUT_DIR / "compiler_output_audit.json"
    audit_path.write_text(json.dumps(audit_card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    failures: list[str] = []
    if compile_card["gate_rejected_rows"] != 3:
        failures.append("expected three gate-rejected rows")
    if compile_card["objective_counts"].get("human_review") != 3:
        failures.append("gate failures did not route to human_review")
    if compile_card["loss_counts"].get("decoder_ce", 0) != 0:
        failures.append("decoder CE loss opened during no-training preflight")
    if compile_card["loss_counts"].get("denoise_ce", 0) != 0:
        failures.append("denoise CE loss opened during no-training preflight")
    if compile_card["loss_counts"].get("runtime_reward", 0) != 0:
        failures.append("runtime reward loss opened during no-training preflight")
    if not audit_card.get("passed"):
        failures.append("compiled output audit failed")
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "passed": not failures,
        "authority": AUTHORITY_CLOSED,
        "metrics": {
            **AUTHORITY_CLOSED,
            "authority_rows": audit_card.get("authority_rows", 0),
            "input_rows": len(rows),
            "gate_rejected_rows": compile_card["gate_rejected_rows"],
            "objective_counts": compile_card["objective_counts"],
            "loss_counts": compile_card["loss_counts"],
            "compiler_audit_passed": audit_card.get("passed"),
            "failures": failures,
        },
        "artifacts": {
            "input_rows": str(input_path.relative_to(ROOT)),
            "compiled_dir": str(compiled_dir.relative_to(ROOT)),
            "compile_card": str((compiled_dir / "compile_card.json").relative_to(ROOT)),
            "compiler_output_audit": str(audit_path.relative_to(ROOT)),
        },
        "decision": "No-training compiler preflight passed: full recovered gates allow only audited rows, failed/missing gates route to human_review, and decoder/denoise/runtime gradients remain closed." if not failures else "No-training compiler preflight failed.",
        "next_best_step": "Attach gate_status contract and no-training preflight to the central graph, then use full gate_status cards in all future source-backed builders before mining.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage8763 No-Training Scale Readiness Preflight",
        "",
        f"Passed: `{summary['passed']}`",
        "",
        "This preflight compiled synthetic rows through `--require-recovered-gates` semantics without opening decoder CE, denoise CE, runtime reward, model execution, or authority.",
        "",
        f"- Gate rejected rows: `{compile_card['gate_rejected_rows']}`",
        f"- Objective counts: `{compile_card['objective_counts']}`",
        f"- Loss counts: `{compile_card['loss_counts']}`",
        "",
        "Failed or missing recovered gates route to `human_review` and cannot create gradients.",
        "",
    ]), encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))
    raise SystemExit(0 if summary["passed"] else 1)


if __name__ == "__main__":
    main()
