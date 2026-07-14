#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path
from typing import Any

import torch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from legacy_src.agentkernel_lite.modeling_transformer import AgentKernelLiteTransformerConfig, AgentKernelLiteTransformerSeq2Seq
from legacy_src.agentkernel_lite.training_data import AgentKernelBPETokenizer
from legacy_src.agentkernel_lite.training_loop import _load_runtime_model_bundle, _write_bounded_choice_eval_audit

ARTIFACTS = ROOT / "runs/local/artifacts"
STAGE = 11118
NAME = "stage11118_trainable_evidence_scorer_source_audit"
OUT_DIR = ARTIFACTS / NAME
SUMMARY_JSON = OUT_DIR / "trainable_evidence_scorer_source_audit.json"

RUNTIME_BUNDLE = ARTIFACTS / "stage11116_trainable_evidence_support_probe" / "runtime_model" / "runtime_model_bundle.json"
VALIDATION_ROWS = ARTIFACTS / "stage11114_fresh_family_support_package_with_trainable_admitted_evidence" / "agentkernel_lite_encdec_validation.jsonl"
STRICT_ROWS = ARTIFACTS / "stage11114_fresh_family_support_package_with_trainable_admitted_evidence" / "agentkernel_lite_encdec_strict_eval.jsonl"
RESERVED_ROWS = ARTIFACTS / "stage11051_successor_residual_support_plus_priority_evidence" / "reserved_residual_candidates.jsonl"
STAGE11117 = ARTIFACTS / "stage11117_trainable_evidence_support_postrun_audit" / "trainable_evidence_support_postrun_audit.json"

SOURCES = [
    "encoder_option_retrieval",
    "encoder_option_retrieval_conditioned",
    "encoder_option_retrieval_evidence_role_map",
    "encoder_option_retrieval_dynamic_productized",
]

TORCH_THREADS = max(1, int(os.environ.get("AGENTKERNEL_EVAL_THREADS", "8")))
torch.set_num_threads(TORCH_THREADS)
torch.set_num_interop_threads(max(1, min(4, TORCH_THREADS)))
EVAL_DEVICE = torch.device(os.environ.get("AGENTKERNEL_EVAL_DEVICE", "cuda" if torch.cuda.is_available() else "cpu"))


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()] if path.exists() else []


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def now_utc() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def load_runtime() -> tuple[AgentKernelLiteTransformerSeq2Seq, AgentKernelBPETokenizer, dict[str, Any]]:
    bundle = load_json(RUNTIME_BUNDLE)
    metadata = bundle["metadata"]
    config = AgentKernelLiteTransformerConfig.from_recovered_target_json(load_json(Path(str(metadata["model_config"]))))
    model = AgentKernelLiteTransformerSeq2Seq(config)
    init_card = _load_runtime_model_bundle(RUNTIME_BUNDLE, model=model)
    model.to(EVAL_DEVICE)
    model.eval()
    tokenizer = AgentKernelBPETokenizer(Path(str(metadata["tokenizer_json"])), Path(str(metadata["tokenizer_config"])))
    return model, tokenizer, init_card


def accuracy(card: dict[str, Any]) -> float | None:
    value = card.get("constrained_choice_top1_accuracy")
    return float(value) if isinstance(value, (float, int)) else None


def evidence_accuracy(card: dict[str, Any], source_rows: list[dict[str, Any]]) -> dict[str, Any]:
    task_by_id = {str(row.get("row_id") or ""): str(row.get("task_type") or "") for row in source_rows}
    cards = [
        row
        for row in list(card.get("row_cards") or [])
        if task_by_id.get(str(row.get("row_id") or "")) == "evidence_citation"
    ]
    scored = [row for row in cards if isinstance(row.get("constrained_choice_match"), bool)]
    correct = sum(1 for row in scored if row.get("constrained_choice_match") is True)
    return {
        "rows": len(cards),
        "scored_rows": len(scored),
        "correct": correct,
        "accuracy": (correct / len(scored)) if scored else None,
        "miss_rows": [row.get("row_id") for row in scored if row.get("constrained_choice_match") is False],
    }


def main() -> None:
    validation_rows = load_jsonl(VALIDATION_ROWS)
    strict_rows = load_jsonl(STRICT_ROWS)
    reserved_rows = load_jsonl(RESERVED_ROWS)
    baseline = load_json(STAGE11117) if STAGE11117.exists() else {}
    model, tokenizer, init_card = load_runtime()

    results: dict[str, Any] = {}
    for source in SOURCES:
        source_dir = OUT_DIR / source
        validation_card = _write_bounded_choice_eval_audit(
            source_dir,
            model=model,
            rows=validation_rows,
            tokenizer=tokenizer,
            max_encoder_tokens=768,
            max_decoder_tokens=16,
            split_name="validation",
            bounded_choice_aux_source=source,
            eval_batch_size=8,
        )
        strict_card = _write_bounded_choice_eval_audit(
            source_dir,
            model=model,
            rows=strict_rows,
            tokenizer=tokenizer,
            max_encoder_tokens=768,
            max_decoder_tokens=16,
            split_name="strict",
            bounded_choice_aux_source=source,
            eval_batch_size=8,
        )
        reserved_card = _write_bounded_choice_eval_audit(
            source_dir,
            model=model,
            rows=reserved_rows,
            tokenizer=tokenizer,
            max_encoder_tokens=768,
            max_decoder_tokens=16,
            split_name="reserved",
            bounded_choice_aux_source=source,
            eval_batch_size=8,
        )
        results[source] = {
            "validation_accuracy": accuracy(validation_card),
            "strict_accuracy": accuracy(strict_card),
            "reserved_accuracy": accuracy(reserved_card),
            "validation_evidence": evidence_accuracy(validation_card, validation_rows),
            "strict_evidence": evidence_accuracy(strict_card, strict_rows),
            "reserved_evidence": evidence_accuracy(reserved_card, reserved_rows),
            "strict_miss_rows": [row.get("row_id") for row in strict_card.get("row_cards", []) if row.get("constrained_choice_match") is False],
            "reserved_miss_rows": [row.get("row_id") for row in reserved_card.get("row_cards", []) if row.get("constrained_choice_match") is False],
        }

    overlay_floor = ((baseline.get("successor_surface_result") or {}).get("strict_accuracy"))
    reserved_floor = (((baseline.get("reserved_candidate_result") or {}).get("overall") or {}).get("exact_accuracy"))
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": True,
        "claim_scope": [
            "Compare current non-persistent bounded scorer text variants on the stage11116 runtime.",
            "Use this only as an architecture-routing audit; it does not train or promote a new model.",
        ],
        "source_artifacts": {
            "runtime_bundle": rel(RUNTIME_BUNDLE),
            "validation_rows": rel(VALIDATION_ROWS),
            "strict_rows": rel(STRICT_ROWS),
            "reserved_rows": rel(RESERVED_ROWS),
            "stage11117_baseline": rel(STAGE11117) if STAGE11117.exists() else None,
        },
        "baseline": {
            "stage11117_strict_accuracy": overlay_floor,
            "stage11117_reserved_accuracy": reserved_floor,
        },
        "results": results,
        "decision": "no_global_scorer_source_promoted",
        "decision_basis": [
            "A scorer source must preserve the strict overlay while improving the reserved residual bank before it can replace encoder_option_retrieval.",
            "If no existing source satisfies both gates, the next implementation step is a real evidence-role/ledger scorer head or objective rather than more support-row probes.",
        ],
        "runtime_initialization": init_card,
        "outputs": {
            "summary_json": rel(SUMMARY_JSON),
        },
    }
    write_json(SUMMARY_JSON, summary)
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
