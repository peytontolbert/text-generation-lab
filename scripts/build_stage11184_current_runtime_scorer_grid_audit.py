#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
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
OUT_DIR = ARTIFACTS / "stage11184_current_runtime_scorer_grid_audit"
SUMMARY_JSON = OUT_DIR / "current_runtime_scorer_grid_audit.json"
RUNTIME_BUNDLE = ARTIFACTS / "stage11182_contract_evidence_support_probe/runtime_model/runtime_model_bundle.json"
VALIDATION_ROWS = ARTIFACTS / "stage11180_cleaned_plus_contract_evidence_support_package/agentkernel_lite_encdec_validation.jsonl"
STRICT_ROWS = ARTIFACTS / "stage11180_cleaned_plus_contract_evidence_support_package/agentkernel_lite_encdec_strict_eval.jsonl"
RESERVED_ROWS = ARTIFACTS / "stage11051_successor_residual_support_plus_priority_evidence/reserved_residual_candidates.jsonl"

SOURCES = [
    "decoder_first_step",
    "encoder_option_retrieval",
    "encoder_option_retrieval_verifier_conditioned",
    "encoder_option_retrieval_conditioned",
    "encoder_option_retrieval_evidence_role_map",
    "encoder_option_retrieval_dynamic_productized",
    "encoder_option_retrieval_evidence_conditioned_gated",
]


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def metric_from_cards(cards: list[dict[str, Any]], source_rows: list[dict[str, Any]]) -> dict[str, Any]:
    evidence_cards = [card for card, row in zip(cards, source_rows) if row.get("task_type") == "evidence_citation"]
    verifier_cards = [card for card, row in zip(cards, source_rows) if str(row.get("task_type") or "").startswith("verifier")]
    def acc(rows: list[dict[str, Any]]) -> float | None:
        if not rows:
            return None
        return sum(1 for row in rows if row.get("constrained_choice_match") is True) / len(rows)
    return {
        "rows": len(cards),
        "accuracy": acc(cards),
        "evidence_rows": len(evidence_cards),
        "evidence_accuracy": acc(evidence_cards),
        "verifier_rows": len(verifier_cards),
        "verifier_accuracy": acc(verifier_cards),
        "misses": [
            {
                "row_id": card.get("row_id"),
                "target_text": card.get("target_text"),
                "predicted": card.get("constrained_choice_top1_label"),
                "full_vocab_top1_text": card.get("full_vocab_top1_text"),
                "target_rank_full_vocab": card.get("target_rank_full_vocab"),
            }
            for card in cards
            if card.get("constrained_choice_match") is False
        ],
    }


def main() -> None:
    bundle = load_json(RUNTIME_BUNDLE)
    metadata = bundle["metadata"]
    config = AgentKernelLiteTransformerConfig.from_recovered_target_json(load_json(Path(metadata["model_config"])))
    model = AgentKernelLiteTransformerSeq2Seq(config)
    init_card = _load_runtime_model_bundle(RUNTIME_BUNDLE, model=model)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model.to(device)
    model.eval()
    tokenizer = AgentKernelBPETokenizer(Path(metadata["tokenizer_json"]), Path(metadata["tokenizer_config"]))

    row_sets = {
        "clean_validation": load_jsonl(VALIDATION_ROWS),
        "clean_strict": load_jsonl(STRICT_ROWS),
        "reserved": load_jsonl(RESERVED_ROWS),
    }
    results: dict[str, Any] = {}
    for source in SOURCES:
        source_results: dict[str, Any] = {}
        for split_name, rows in row_sets.items():
            card = _write_bounded_choice_eval_audit(
                OUT_DIR,
                model=model,
                rows=rows,
                tokenizer=tokenizer,
                max_encoder_tokens=768,
                max_decoder_tokens=8,
                split_name=f"{split_name}_{source}",
                bounded_choice_aux_source=source,
                eval_batch_size=8,
            )
            source_results[split_name] = metric_from_cards(list(card.get("row_cards") or []), rows)
        results[source] = source_results

    safe_candidates = []
    for source, metrics in results.items():
        strict_acc = metrics["clean_strict"]["accuracy"]
        reserved_ev = metrics["reserved"]["evidence_accuracy"]
        validation_acc = metrics["clean_validation"]["accuracy"]
        if strict_acc == 1.0 and validation_acc is not None and validation_acc >= 20 / 23 and reserved_ev is not None:
            safe_candidates.append(
                {
                    "source": source,
                    "clean_strict": strict_acc,
                    "clean_validation": validation_acc,
                    "reserved_evidence": reserved_ev,
                    "reserved": metrics["reserved"]["accuracy"],
                }
            )

    summary = {
        "stage": 11184,
        "runtime_bundle": str(RUNTIME_BUNDLE.relative_to(ROOT)),
        "runtime_initialization": init_card,
        "results": results,
        "safe_candidates": safe_candidates,
        "decision": "existing_scorer_candidate_found" if any(c["reserved_evidence"] > 4 / 9 for c in safe_candidates) else "no_existing_scorer_moves_reserved_evidence_safely",
    }
    write_json(SUMMARY_JSON, summary)
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
