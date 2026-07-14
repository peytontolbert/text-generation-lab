#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

ARTIFACTS = ROOT / "runs" / "local" / "artifacts"
STAGE = 11006
NAME = "stage11006_semantic_evidence_bridge_postrun_audit"
OUT_DIR = ARTIFACTS / NAME
SUMMARY_JSON = OUT_DIR / "semantic_evidence_bridge_postrun_audit.json"
PROBE_DIR = ARTIFACTS / "stage11005_semantic_evidence_bridge_probe" / "bounded_decoder_probe"
RUNTIME_BUNDLE = ARTIFACTS / "stage11005_semantic_evidence_bridge_probe" / "runtime_model" / "runtime_model_bundle.json"
CANDIDATE_ROWS = ARTIFACTS / "stage10974_multilingual_reviewed_replenishment_package" / "strict_candidate_rows.jsonl"
BASELINE_AUDIT = ARTIFACTS / "stage10978_multilingual_reviewed_replenishment_postrun_audit" / "multilingual_reviewed_replenishment_postrun_audit.json"

from scripts.build_stage10999_fresh_evidence_candidate_runtime_audit import (  # type: ignore
    load_json,
    load_jsonl,
    load_runtime,
    rel,
    summarize,
)
from legacy_src.agentkernel_lite.training_loop import _write_bounded_choice_eval_audit


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def now_utc() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def main() -> None:
    _runtime_bundle = load_json(RUNTIME_BUNDLE)
    baseline = load_json(BASELINE_AUDIT)
    model, tokenizer, init_card, source = load_runtime()
    candidate_card = _write_bounded_choice_eval_audit(
        OUT_DIR,
        model=model,
        rows=load_jsonl(CANDIDATE_ROWS),
        tokenizer=tokenizer,
        max_encoder_tokens=768,
        max_decoder_tokens=8,
        split_name="reviewed_replenishment_candidates",
        bounded_choice_aux_source=source,
        eval_batch_size=8,
    )
    overlay_eval = load_json(PROBE_DIR / "bounded_choice_eval_audit_eval.json")
    overlay_strict = load_json(PROBE_DIR / "bounded_choice_eval_audit_strict_eval.json")

    payload = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": True,
        "runtime_bundle": rel(RUNTIME_BUNDLE),
        "runtime_initialization": init_card,
        "bounded_choice_aux_source": source,
        "reviewed_replenishment_candidates": {
            "overall": summarize(candidate_card),
            "by_language": candidate_card.get("language_accuracy") or {},
        },
        "overlay": {
            "eval_accuracy": overlay_eval["constrained_choice_top1_accuracy"],
            "strict_accuracy": overlay_strict["constrained_choice_top1_accuracy"],
            "strict_miss_rows": [
                row["row_id"]
                for row in overlay_strict.get("row_cards", [])
                if not row.get("constrained_choice_match")
            ],
        },
        "baseline_reference": {
            "candidate_accuracy": baseline["reviewed_replenishment_candidates"]["overall"]["exact_accuracy"],
            "overlay_eval_accuracy": baseline["overlay"]["eval_accuracy"],
            "overlay_strict_accuracy": baseline["overlay"]["strict_accuracy"],
        },
        "findings": [
            "A useful result must improve the 6-row reviewed replenishment candidate slice beyond the prior 2/6 baseline.",
            "Overlay preservation remains necessary; if the candidate slice stays flat, the branch still needs new row geometry rather than another small probe.",
        ],
    }
    write_json(SUMMARY_JSON, payload)
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
