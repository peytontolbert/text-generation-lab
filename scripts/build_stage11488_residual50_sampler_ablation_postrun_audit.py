#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import shutil
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


ART = ROOT / "runs/local/artifacts"
SUMMARIES = ROOT / "runs/summaries"
STAGE = 11488
NAME = "stage11488_residual50_sampler_ablation_postrun_audit"
OUT = ART / NAME
SUMMARY = OUT / "residual50_sampler_ablation_postrun_audit.json"

RUNTIME = ART / "stage11487_residual50_sampler_ablation_probe/runtime_model/runtime_model_bundle.json"
REQUEST = ART / "stage11486_residual50_sampler_ablation_probe_request/residual50_sampler_ablation_probe_request.json"
PACKAGE = ART / "stage11481_residual50_ready_package_with_rust_counters/residual50_ready_package_with_rust_counters.json"
FILTERED_VALIDATION = ART / "stage11442_targeted_residual_role_support_package/agentkernel_lite_encdec_validation.jsonl"
FILTERED_STRICT = ART / "stage11442_targeted_residual_role_support_package/agentkernel_lite_encdec_strict_eval.jsonl"
RESIDUAL = ART / "stage11442_targeted_residual_role_support_package/semantic_candidate_residual_bank.jsonl"
OLD_VALIDATION = ART / "stage11429_selected_test_rust_support_package/agentkernel_lite_encdec_validation.jsonl"
OLD_STRICT = ART / "stage11429_selected_test_rust_support_package/agentkernel_lite_encdec_strict_eval.jsonl"
REJECTED_REFERENCE = ART / "stage11484_residual50_controlled_probe_postrun_audit/residual50_controlled_probe_postrun_audit.json"

SCORERS = ["encoder_option_retrieval", "encoder_option_retrieval_semantic_candidate_head", "decoder_first_step"]
PRODUCT_SCORER = "encoder_option_retrieval"

torch.set_num_threads(max(1, int(os.environ.get("AGENTKERNEL_EVAL_THREADS", "8"))))
try:
    torch.set_num_interop_threads(max(1, min(4, int(os.environ.get("AGENTKERNEL_EVAL_THREADS", "8")))))
except RuntimeError:
    pass
DEVICE = torch.device(os.environ.get("AGENTKERNEL_EVAL_DEVICE", "cuda" if torch.cuda.is_available() else "cpu"))


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


def load_runtime() -> tuple[Any, Any, dict[str, Any]]:
    bundle = load_json(RUNTIME)
    metadata = bundle["metadata"]
    config = AgentKernelLiteTransformerConfig.from_recovered_target_json(load_json(Path(str(metadata["model_config"]))))
    model = AgentKernelLiteTransformerSeq2Seq(config)
    init_card = _load_runtime_model_bundle(RUNTIME, model=model)
    model.to(DEVICE)
    model.eval()
    tokenizer = AgentKernelBPETokenizer(Path(str(metadata["tokenizer_json"])), Path(str(metadata["tokenizer_config"])))
    return model, tokenizer, init_card


def metric_from_card(card: dict[str, Any]) -> dict[str, Any]:
    misses = []
    for row in card.get("row_cards") or []:
        if row.get("constrained_choice_match") is not True:
            misses.append(
                {
                    "row_id": row.get("row_id"),
                    "target": row.get("bounded_choice_target_label"),
                    "predicted": row.get("constrained_choice_top1_label"),
                    "full_vocab_top1_text": row.get("full_vocab_top1_text"),
                    "target_rank_full_vocab": row.get("target_rank_full_vocab"),
                    "scored": isinstance(row.get("constrained_choice_match"), bool),
                }
            )
    return {
        "rows": card.get("rows"),
        "correct": card.get("constrained_choice_correct"),
        "scored_rows": card.get("constrained_choice_rows"),
        "unscored_rows": card.get("constrained_choice_unscored_rows"),
        "coverage": card.get("constrained_choice_coverage"),
        "reported_accuracy_on_scored_rows": card.get("constrained_choice_top1_accuracy"),
        "coverage_corrected_accuracy": card.get("constrained_choice_coverage_corrected_top1_accuracy"),
        "misses": misses,
    }


def score(model: Any, tokenizer: Any, rows: list[dict[str, Any]], split: str, scorer: str) -> dict[str, Any]:
    card = _write_bounded_choice_eval_audit(
        OUT,
        model=model,
        rows=rows,
        tokenizer=tokenizer,
        max_encoder_tokens=768,
        max_decoder_tokens=16,
        split_name=f"{split}_{scorer}",
        bounded_choice_aux_source=scorer,
        eval_batch_size=8,
    )
    return metric_from_card(card)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    request = load_json(REQUEST)
    package = load_json(PACKAGE)
    rejected_reference = load_json(REJECTED_REFERENCE) if REJECTED_REFERENCE.exists() else {}
    rows = {
        "filtered_validation": load_jsonl(FILTERED_VALIDATION),
        "filtered_strict": load_jsonl(FILTERED_STRICT),
        "residual_bank": load_jsonl(RESIDUAL),
        "old_canary_validation": load_jsonl(OLD_VALIDATION),
        "old_canary_strict": load_jsonl(OLD_STRICT),
    }
    model, tokenizer, init_card = load_runtime()
    scored: dict[str, Any] = {}
    for scorer in SCORERS:
        scored[scorer] = {name: score(model, tokenizer, split_rows, name, scorer) for name, split_rows in rows.items()}
    product = scored[PRODUCT_SCORER]
    gates = {
        "product_old_canary_strict_23_of_23": product["old_canary_strict"]["correct"] == 23,
        "product_filtered_strict_22_of_22": product["filtered_strict"]["correct"] == 22,
        "product_filtered_validation_at_least_20_of_22": (product["filtered_validation"]["correct"] or 0) >= 20,
        "product_old_canary_validation_at_least_21_of_23": (product["old_canary_validation"]["correct"] or 0) >= 21,
        "product_residual_above_base_5_of_10": (product["residual_bank"]["correct"] or 0) > 5,
        "coverage_full_for_product_residual": product["residual_bank"].get("coverage") == 1.0,
    }
    promoted = all(gates.values())
    reference_product = ((rejected_reference.get("scored") or {}).get(PRODUCT_SCORER) or {})
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now(),
        "passed": True,
        "decision": "residual50_sampler_ablation_promoted" if promoted else "residual50_sampler_ablation_rejected_or_diagnostic_only",
        "runtime_initialization": init_card,
        "runtime_weights_sha256": init_card.get("weights_sha256"),
        "request_metrics": request.get("metrics"),
        "package_metrics": package.get("metrics"),
        "scored": scored,
        "promotion_gates": gates,
        "comparison_to_stage11483": {
            "stage11483_product_filtered_strict": (reference_product.get("filtered_strict") or {}).get("correct"),
            "stage11487_product_filtered_strict": product["filtered_strict"]["correct"],
            "stage11483_product_old_canary_strict": (reference_product.get("old_canary_strict") or {}).get("correct"),
            "stage11487_product_old_canary_strict": product["old_canary_strict"]["correct"],
            "stage11483_product_residual_bank": (reference_product.get("residual_bank") or {}).get("correct"),
            "stage11487_product_residual_bank": product["residual_bank"]["correct"],
        },
        "decision_basis": [
            "Stage11487 held data, init runtime, product scorer, loss weights, and protected splits fixed.",
            "Only bounded_decoder_train_sampler changed from residual_family_balanced to cyclic.",
            "Promotion still requires product scorer encoder_option_retrieval to preserve old/filtered strict and validation while improving residual bank above 5/10.",
        ],
        "source_artifacts": {
            "runtime_bundle": rel(RUNTIME),
            "request": rel(REQUEST),
            "package": rel(PACKAGE),
            "rejected_reference": rel(REJECTED_REFERENCE),
            "filtered_validation": rel(FILTERED_VALIDATION),
            "filtered_strict": rel(FILTERED_STRICT),
            "residual_bank": rel(RESIDUAL),
            "old_canary_validation": rel(OLD_VALIDATION),
            "old_canary_strict": rel(OLD_STRICT),
        },
        "outputs": {"summary": rel(SUMMARY)},
    }
    write_json(SUMMARY, summary)
    SUMMARIES.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(SUMMARY, SUMMARIES / f"{NAME}.json")
    print(json.dumps({"decision": summary["decision"], "promotion_gates": gates, "comparison_to_stage11483": summary["comparison_to_stage11483"], "product": product}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
