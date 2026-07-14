#!/usr/bin/env python3
from __future__ import annotations

import json
import shutil
import time
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "runs/local/artifacts"
SUMMARIES = ROOT / "runs/summaries"
STAGE = 11592
NAME = "stage11592_web_moderate_contrast_decision"
OUT = ART / NAME
SUMMARY = OUT / "web_moderate_contrast_decision.json"
POSTRUN = SUMMARIES / "stage11591_web_moderate_task_aware_contrast_postrun_audit.json"
REQUEST = SUMMARIES / "stage11590_web_moderate_task_aware_contrast_probe_request.json"
LOSS = ART / "stage11590_web_moderate_task_aware_contrast_probe/bounded_decoder_probe/loss_by_step.jsonl"
SUCCESSOR_AUDIT = ART / "stage11591_web_moderate_task_aware_contrast_postrun_audit/bounded_choice_eval_audit_web_successor_strict.json"
SELECTED_RUNTIME = ART / "stage11507_preservation_strengthened_evidence_judgment_probe/runtime_model/runtime_model_bundle.json"
REJECTED_RUNTIME = ART / "stage11590_web_moderate_task_aware_contrast_probe/runtime_model/runtime_model_bundle.json"


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
    request = load_json(REQUEST)
    losses = load_jsonl(LOSS)
    successor = load_json(SUCCESSOR_AUDIT)
    row_cards = successor.get("row_cards") or []
    contrast_applicable = sum(int(((row.get("bounded_choice_contrast_card") or {}).get("applicable_rows") or 0)) for row in losses)
    contrast_satisfied = sum(int(((row.get("bounded_choice_contrast_card") or {}).get("margin_satisfied_rows") or 0)) for row in losses)
    results = postrun.get("results") or {}
    compact = {name: {"correct": card.get("correct"), "rows": card.get("rows"), "accuracy": card.get("accuracy")} for name, card in results.items()}
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now(),
        "decision": "reject_stage11590_keep_stage11507_selected_frontier",
        "selected_frontier_runtime": rel(SELECTED_RUNTIME),
        "rejected_runtime": rel(REJECTED_RUNTIME),
        "rejected_runtime_weights_sha256": load_json(REJECTED_RUNTIME).get("weights_sha256") if REJECTED_RUNTIME.exists() else None,
        "objective_settings": request.get("objective_settings"),
        "postrun_compact_results": compact,
        "postrun_gates": postrun.get("gates"),
        "successor_strict_pattern": {
            "rows": successor.get("rows"),
            "correct": successor.get("constrained_choice_correct"),
            "target_counts": dict(Counter(str(row.get("bounded_choice_target_label")) for row in row_cards)),
            "prediction_counts": dict(Counter(str(row.get("constrained_choice_top1_label")) for row in row_cards)),
        },
        "contrast_training_telemetry": {
            "loss_steps": len(losses),
            "contrast_applicable_rows_seen": contrast_applicable,
            "contrast_margin_satisfied_rows_seen": contrast_satisfied,
            "contrast_margin_satisfied_rate": (contrast_satisfied / contrast_applicable) if contrast_applicable else None,
        },
        "why_rejected": [
            "The request artifact correctly used web_task_family_balanced, contrast weight 0.5, margin 0.08, and preservation KL 5.0.",
            "Filtered strict and old canary strict were preserved, but validation, residual, web heldout, and successor strict failed promotion gates.",
            "Web successor strict remained 0/36 with a uniform D/abstain prediction despite A/B targets.",
            "Contrast was active but never satisfied the requested margin, so same-objective contrast tuning is not sufficient for this row geometry.",
        ],
        "next_recommended_work": [
            "Do not run more weight-only task-aware contrast probes on Stage11580 rows.",
            "Build an abstain-attractor audit for option D under the selected scorer and remove/reformulate verifier-attached rows where ABSTAIN is a lexical shortcut.",
            "Next model-side change should be a scorer architecture that uses task-specific candidate metadata or a staged/frozen head, not another shared retrieval CE sweep.",
            "Keep Stage11507 + encoder_option_retrieval_evidence_judgment_head as selected frontier.",
        ],
        "source_artifacts": {
            "request": rel(REQUEST),
            "postrun": rel(POSTRUN),
            "loss_by_step": rel(LOSS),
            "successor_audit": rel(SUCCESSOR_AUDIT),
        },
    }
    OUT.mkdir(parents=True, exist_ok=True)
    write_json(SUMMARY, summary)
    SUMMARIES.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(SUMMARY, SUMMARIES / f"{NAME}.json")
    print(json.dumps({
        "decision": summary["decision"],
        "postrun_compact_results": compact,
        "successor_strict_pattern": summary["successor_strict_pattern"],
        "contrast_training_telemetry": summary["contrast_training_telemetry"],
    }, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
