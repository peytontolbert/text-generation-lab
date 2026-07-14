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

ARTIFACTS = ROOT / "runs" / "local" / "artifacts"
STAGE = 11055
NAME = "stage11055_selective_evidence_scorer_policy_audit"
OUT_DIR = ARTIFACTS / NAME
SUMMARY_JSON = OUT_DIR / "selective_evidence_scorer_policy_audit.json"

RUNTIME_BUNDLE = ARTIFACTS / "stage11053_successor_residual_support_plus_priority_probe" / "runtime_model" / "runtime_model_bundle.json"
EVAL_ROWS = ARTIFACTS / "stage11051_successor_residual_support_plus_priority_evidence" / "agentkernel_lite_encdec_validation.jsonl"
STRICT_ROWS = ARTIFACTS / "stage11051_successor_residual_support_plus_priority_evidence" / "agentkernel_lite_encdec_strict_eval.jsonl"
RESERVED_ROWS = ARTIFACTS / "stage11051_successor_residual_support_plus_priority_evidence" / "reserved_residual_candidates.jsonl"

BASE_SOURCE = "encoder_option_retrieval"
ALT_SOURCE = "encoder_option_retrieval_evidence_role_map"

TORCH_THREADS = max(1, int(os.environ.get("AGENTKERNEL_EVAL_THREADS", "8")))
torch.set_num_threads(TORCH_THREADS)
torch.set_num_interop_threads(max(1, min(4, TORCH_THREADS)))
EVAL_DEVICE = torch.device(os.environ.get("AGENTKERNEL_EVAL_DEVICE", "cuda" if torch.cuda.is_available() else "cpu"))


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


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


def summarize_card(card: dict[str, Any]) -> dict[str, Any]:
    rows = list(card.get("row_cards") or [])
    evidence_rows = [row for row in rows if "evidence_citation" in str(row.get("row_id") or "")]
    verifier_rows = [row for row in rows if "verifier_outcome" in str(row.get("row_id") or "")]
    return {
        "rows": card.get("rows"),
        "constrained_choice_rows": card.get("constrained_choice_rows"),
        "constrained_choice_top1_accuracy": card.get("constrained_choice_top1_accuracy"),
        "full_vocab_top1_accuracy": card.get("full_vocab_top1_accuracy"),
        "rows_with_target_rank_1": card.get("rows_with_target_rank_1"),
        "evidence_rows": len(evidence_rows),
        "evidence_accuracy": (
            sum(1 for row in evidence_rows if row.get("constrained_choice_match") is True) / len(evidence_rows)
            if evidence_rows else None
        ),
        "verifier_rows": len(verifier_rows),
        "verifier_accuracy": (
            sum(1 for row in verifier_rows if row.get("constrained_choice_match") is True) / len(verifier_rows)
            if verifier_rows else None
        ),
    }


def row_accuracy(rows: list[dict[str, Any]]) -> float | None:
    scored = [row for row in rows if isinstance(row.get("constrained_choice_match"), bool)]
    if not scored:
        return None
    return sum(1 for row in scored if row.get("constrained_choice_match") is True) / len(scored)


def task_accuracy(rows: list[dict[str, Any]], token: str) -> float | None:
    subset = [row for row in rows if token in str(row.get("row_id") or "")]
    return row_accuracy(subset)


def mismatch_ids(rows: list[dict[str, Any]]) -> list[str]:
    return [str(row.get("row_id") or "") for row in rows if row.get("constrained_choice_match") is False]


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    model, tokenizer, init_card = load_runtime()

    datasets = {
        "successor_eval": load_jsonl(EVAL_ROWS),
        "successor_strict": load_jsonl(STRICT_ROWS),
        "reserved_candidate_bank": load_jsonl(RESERVED_ROWS),
    }

    results: dict[str, dict[str, Any]] = {}
    comparison: dict[str, dict[str, Any]] = {}

    for dataset_name, rows in datasets.items():
        base_card = _write_bounded_choice_eval_audit(
            OUT_DIR,
            model=model,
            rows=rows,
            tokenizer=tokenizer,
            max_encoder_tokens=768,
            max_decoder_tokens=8,
            split_name=f"{dataset_name}_{BASE_SOURCE}",
            bounded_choice_aux_source=BASE_SOURCE,
            eval_batch_size=8,
        )
        alt_card = _write_bounded_choice_eval_audit(
            OUT_DIR,
            model=model,
            rows=rows,
            tokenizer=tokenizer,
            max_encoder_tokens=768,
            max_decoder_tokens=8,
            split_name=f"{dataset_name}_{ALT_SOURCE}",
            bounded_choice_aux_source=ALT_SOURCE,
            eval_batch_size=8,
        )

        base_rows = {str(row.get("row_id") or ""): row for row in (base_card.get("row_cards") or [])}
        alt_rows = {str(row.get("row_id") or ""): row for row in (alt_card.get("row_cards") or [])}

        hybrid_rows: list[dict[str, Any]] = []
        for source_row in rows:
            row_id = str(source_row.get("row_id") or "")
            task_type = str(source_row.get("task_type") or "")
            use_alt = task_type == "evidence_citation"
            selected = dict((alt_rows if use_alt else base_rows).get(row_id, {}))
            selected["selected_policy_source"] = ALT_SOURCE if use_alt else BASE_SOURCE
            hybrid_rows.append(selected)

        results[dataset_name] = {
            "base": {
                "summary": summarize_card(base_card),
                "mismatch_ids": mismatch_ids(list(base_rows.values())),
            },
            "alt": {
                "summary": summarize_card(alt_card),
                "mismatch_ids": mismatch_ids(list(alt_rows.values())),
            },
            "hybrid": {
                "summary": {
                    "rows": len(hybrid_rows),
                    "constrained_choice_rows": len(hybrid_rows),
                    "constrained_choice_top1_accuracy": row_accuracy(hybrid_rows),
                    "full_vocab_top1_accuracy": row_accuracy([
                        {**row, "constrained_choice_match": row.get("full_vocab_top1_match")} for row in hybrid_rows
                    ]),
                    "rows_with_target_rank_1": sum(1 for row in hybrid_rows if row.get("target_rank_full_vocab") == 1),
                    "evidence_rows": sum(1 for row in hybrid_rows if "evidence_citation" in str(row.get("row_id") or "")),
                    "evidence_accuracy": task_accuracy(hybrid_rows, "evidence_citation"),
                    "verifier_rows": sum(1 for row in hybrid_rows if "verifier_outcome" in str(row.get("row_id") or "")),
                    "verifier_accuracy": task_accuracy(hybrid_rows, "verifier_outcome"),
                },
                "mismatch_ids": mismatch_ids(hybrid_rows),
                "row_cards": hybrid_rows,
            },
        }

        comparison[dataset_name] = {
            "base_accuracy": results[dataset_name]["base"]["summary"]["constrained_choice_top1_accuracy"],
            "alt_accuracy": results[dataset_name]["alt"]["summary"]["constrained_choice_top1_accuracy"],
            "hybrid_accuracy": results[dataset_name]["hybrid"]["summary"]["constrained_choice_top1_accuracy"],
            "base_evidence_accuracy": results[dataset_name]["base"]["summary"]["evidence_accuracy"],
            "alt_evidence_accuracy": results[dataset_name]["alt"]["summary"]["evidence_accuracy"],
            "hybrid_evidence_accuracy": results[dataset_name]["hybrid"]["summary"]["evidence_accuracy"],
            "base_verifier_accuracy": results[dataset_name]["base"]["summary"]["verifier_accuracy"],
            "alt_verifier_accuracy": results[dataset_name]["alt"]["summary"]["verifier_accuracy"],
            "hybrid_verifier_accuracy": results[dataset_name]["hybrid"]["summary"]["verifier_accuracy"],
        }

    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": True,
        "decision": "selective_evidence_scorer_policy_audited",
        "claim_scope": [
            "Compare base, full role-map, and selective evidence-only scorer routing on the stage11053 runtime.",
            "Check whether routing only evidence_citation rows to the role-mapped scorer can lift the residual bank without regressing the strict overlay.",
        ],
        "runtime_bundle": {
            "runtime_bundle": rel(RUNTIME_BUNDLE),
            "runtime_initialization": init_card,
        },
        "comparison": comparison,
        "results": results,
        "headline_findings": [
            "The hybrid policy is only viable if it improves the reserved evidence bank while keeping successor strict at or above the current base scorer.",
            "If hybrid still fails, the next move is a scorer architecture change or a larger evidence-role materialization batch, not more support probes.",
        ],
        "next_best_step": "Adopt the hybrid policy only if it preserves successor strict and improves the reserved bank; otherwise keep scorer routing unchanged and pivot to architecture or data geometry work.",
        "source_artifacts": {
            "successor_eval_rows": rel(EVAL_ROWS),
            "successor_strict_rows": rel(STRICT_ROWS),
            "reserved_rows": rel(RESERVED_ROWS),
        },
        "outputs": {
            "summary_json": rel(SUMMARY_JSON),
        },
    }
    write_json(SUMMARY_JSON, summary)
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
