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
STAGE = 11008
NAME = "stage11008_evidence_geometry_runtime_audit"
OUT_DIR = ARTIFACTS / NAME
SUMMARY_JSON = OUT_DIR / "evidence_geometry_runtime_audit.json"
GEOMETRY_ROWS = ARTIFACTS / "stage11007_evidence_geometry_bank" / "geometry_candidate_rows.jsonl"
STANDARD_ROWS = ARTIFACTS / "stage11007_evidence_geometry_bank" / "standard_reviewed_candidate_rows.jsonl"
RUNTIME_BUNDLE = ARTIFACTS / "stage11005_semantic_evidence_bridge_probe" / "runtime_model" / "runtime_model_bundle.json"

from scripts.build_stage10999_fresh_evidence_candidate_runtime_audit import load_json, load_jsonl, load_runtime, rel, summarize  # type: ignore
from legacy_src.agentkernel_lite.training_loop import _write_bounded_choice_eval_audit


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def now_utc() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def main() -> None:
    _bundle = load_json(RUNTIME_BUNDLE)
    model, tokenizer, init_card, source = load_runtime()
    geometry_card = _write_bounded_choice_eval_audit(
        OUT_DIR,
        model=model,
        rows=load_jsonl(GEOMETRY_ROWS),
        tokenizer=tokenizer,
        max_encoder_tokens=768,
        max_decoder_tokens=8,
        split_name="geometry_candidate_bank",
        bounded_choice_aux_source=source,
        eval_batch_size=8,
    )
    standard_card = _write_bounded_choice_eval_audit(
        OUT_DIR,
        model=model,
        rows=load_jsonl(STANDARD_ROWS),
        tokenizer=tokenizer,
        max_encoder_tokens=768,
        max_decoder_tokens=8,
        split_name="standard_reviewed_candidates",
        bounded_choice_aux_source=source,
        eval_batch_size=8,
    )
    payload = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": True,
        "runtime_bundle": rel(RUNTIME_BUNDLE),
        "runtime_initialization": init_card,
        "bounded_choice_aux_source": source,
        "geometry_candidate_bank": {
            "overall": summarize(geometry_card),
            "language_accuracy": geometry_card.get("language_accuracy") or {},
        },
        "standard_reviewed_candidates": {
            "overall": summarize(standard_card),
            "language_accuracy": standard_card.get("language_accuracy") or {},
        },
        "findings": [
            "The geometry bank is the more informative evidence audit surface because it includes option-order and explicit-ledger variants.",
            "If standard reviewed candidates stay flat but geometry variants improve, the branch learned representation sensitivity rather than genuinely better root-level evidence selection.",
        ],
    }
    write_json(SUMMARY_JSON, payload)
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
