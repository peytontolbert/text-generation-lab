#!/usr/bin/env python3
from __future__ import annotations

import json
import shutil
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "runs/local/artifacts"
SUMMARIES = ROOT / "runs/summaries"
STAGE = 11588
NAME = "stage11588_web_task_aware_contrast_probe_decision"
OUT = ART / NAME
SUMMARY = OUT / "web_task_aware_contrast_probe_decision.json"
POSTRUN = SUMMARIES / "stage11587_web_task_aware_contrast_postrun_audit.json"
READINESS = SUMMARIES / "stage11585_web_task_aware_contrast_readiness_audit.json"
REQUEST = SUMMARIES / "stage11586_web_task_aware_contrast_probe_request.json"
SELECTED_RUNTIME = ART / "stage11507_preservation_strengthened_evidence_judgment_probe/runtime_model/runtime_model_bundle.json"
REJECTED_RUNTIME = ART / "stage11586_web_task_aware_contrast_probe/runtime_model/runtime_model_bundle.json"
LOSS_PATH = ART / "stage11586_web_task_aware_contrast_probe/bounded_decoder_probe/loss_by_step.jsonl"


def now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()] if path.exists() else []


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> None:
    postrun = load_json(POSTRUN)
    readiness = load_json(READINESS)
    request = load_json(REQUEST)
    losses = load_jsonl(LOSS_PATH)
    contrast_rows = sum(int(((row.get("bounded_choice_contrast_card") or {}).get("applicable_rows") or 0)) for row in losses)
    contrast_satisfied = sum(int(((row.get("bounded_choice_contrast_card") or {}).get("margin_satisfied_rows") or 0)) for row in losses)
    results = postrun.get("results") or {}
    compact = {name: {"correct": card.get("correct"), "rows": card.get("rows"), "accuracy": card.get("accuracy")} for name, card in results.items()}
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now(),
        "decision": "reject_stage11586_keep_stage11507_selected_frontier",
        "selected_frontier_runtime": rel(SELECTED_RUNTIME),
        "rejected_runtime": rel(REJECTED_RUNTIME),
        "rejected_runtime_weights_sha256": load_json(REJECTED_RUNTIME).get("weights_sha256") if REJECTED_RUNTIME.exists() else None,
        "why_rejected": [
            "Stage11587 failed promotion gates despite task-aware contrast coverage.",
            "Filtered strict and old canary strict were preserved, but validation, residual bank, web heldout, and successor strict all failed.",
            "Contrast was active during training, so the failure is not missing contrast coverage; it is objective/row-geometry mismatch for verifier-attached Web rows.",
        ],
        "postrun_compact_results": compact,
        "postrun_gates": postrun.get("gates"),
        "contrast_training_telemetry": {
            "loss_steps": len(losses),
            "contrast_applicable_rows_seen": contrast_rows,
            "contrast_margin_satisfied_rows_seen": contrast_satisfied,
            "contrast_margin_satisfied_rate": (contrast_satisfied / contrast_rows) if contrast_rows else None,
            "sampler": ((losses[-1] if losses else {}).get("bounded_decoder_train_sampler")),
        },
        "readiness_decision": readiness.get("decision"),
        "request_decision": request.get("decision"),
        "next_recommended_work": [
            "Do not run another same-objective Web support probe.",
            "Treat Stage11580 verifier-attached rows as useful material but not safe direct train targets under current row-wise CE/aux geometry.",
            "Next useful code change is a same-root/listwise candidate objective or a row rebuild where successor strict targets are answerable under the selected scorer before training.",
            "Selected frontier remains Stage11507 + encoder_option_retrieval_evidence_judgment_head.",
        ],
        "source_artifacts": {
            "readiness": rel(READINESS),
            "request": rel(REQUEST),
            "postrun": rel(POSTRUN),
            "loss_by_step": rel(LOSS_PATH),
        },
    }
    OUT.mkdir(parents=True, exist_ok=True)
    write_json(SUMMARY, summary)
    SUMMARIES.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(SUMMARY, SUMMARIES / f"{NAME}.json")
    print(json.dumps({"decision": summary["decision"], "postrun_compact_results": compact, "contrast_training_telemetry": summary["contrast_training_telemetry"]}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
