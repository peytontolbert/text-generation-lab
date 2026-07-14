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
STAGE = 11526
NAME = "stage11526_openhands_non_evidence_from_stage11507_postrun_audit"
OUT = ART / NAME
SUMMARY = OUT / "openhands_non_evidence_from_stage11507_postrun_audit.json"

RUNTIME = ART / "stage11525_openhands_non_evidence_from_stage11507_probe/runtime_model/runtime_model_bundle.json"
REQUEST = ART / "stage11525_openhands_non_evidence_from_stage11507_probe_request/openhands_non_evidence_from_stage11507_probe_request.json"
FILTERED_VALIDATION = ART / "stage11442_targeted_residual_role_support_package/agentkernel_lite_encdec_validation.jsonl"
FILTERED_STRICT = ART / "stage11442_targeted_residual_role_support_package/agentkernel_lite_encdec_strict_eval.jsonl"
OLD_VALIDATION = ART / "stage11429_selected_test_rust_support_package/agentkernel_lite_encdec_validation.jsonl"
OLD_STRICT = ART / "stage11429_selected_test_rust_support_package/agentkernel_lite_encdec_strict_eval.jsonl"
OPENHANDS_TRAIN = ART / "stage11394_openhands_support_unit_verifier_train_rows/openhands_support_unit_verifier_train_rows.jsonl"
OPENHANDS_HELDOUT = ART / "stage11390_openhands_unit_verifier_heldout_candidate_rows/openhands_unit_verifier_heldout_candidate_rows.jsonl"
LLAMA_HELDOUT = ART / "stage11361_web_llama_stack_executed_heldout_rows/web_llama_stack_executed_heldout_rows.jsonl"
OPENHANDS_GEMMA = ART / "stage11392_openhands_web_same_manifest_gemma_comparison/openhands_web_gemma_rows.jsonl"
LLAMA_GEMMA = ART / "stage11363_web_llama_stack_same_manifest_gemma_comparison/web_llama_stack_gemma_rows.jsonl"
STAGE11521 = SUMMARIES / "stage11521_web_llama_stack_stage11507_same_manifest_comparison.json"
STAGE11522 = SUMMARIES / "stage11522_openhands_web_stage11507_same_manifest_comparison.json"

SCORERS = [
    "encoder_option_retrieval_evidence_judgment_head",
    "encoder_option_retrieval",
    "encoder_option_retrieval_semantic_candidate_head",
    "decoder_first_step",
]
PRODUCT_SCORER = "encoder_option_retrieval_evidence_judgment_head"

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


def load_json_opt(path: Path) -> Any:
    return load_json(path) if path.exists() else {}


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
                }
            )
    return {
        "rows": card.get("rows"),
        "correct": card.get("constrained_choice_correct"),
        "scored_rows": card.get("constrained_choice_rows"),
        "unscored_rows": card.get("constrained_choice_unscored_rows"),
        "coverage": card.get("constrained_choice_coverage"),
        "accuracy": card.get("constrained_choice_top1_accuracy"),
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


def gemma_metric(rows: list[dict[str, Any]]) -> dict[str, Any]:
    correct = sum(1 for row in rows if row.get("gemma12b_correct") is True)
    return {"rows": len(rows), "correct": correct, "accuracy": correct / len(rows) if rows else 0.0}


def baseline_correct(path: Path, key: str) -> Any:
    obj = load_json_opt(path)
    return (((obj.get("scorer_results") or {}).get(PRODUCT_SCORER) or {}).get("correct")) if key == "product" else None


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    rowsets = {
        "filtered_validation": load_jsonl(FILTERED_VALIDATION),
        "filtered_strict": load_jsonl(FILTERED_STRICT),
        "old_canary_validation": load_jsonl(OLD_VALIDATION),
        "old_canary_strict": load_jsonl(OLD_STRICT),
        "openhands_train_support": load_jsonl(OPENHANDS_TRAIN),
        "openhands_heldout": load_jsonl(OPENHANDS_HELDOUT),
        "llama_stack_heldout": load_jsonl(LLAMA_HELDOUT),
    }
    model, tokenizer, init_card = load_runtime()
    scored = {
        scorer: {name: score(model, tokenizer, rows, name, scorer) for name, rows in rowsets.items()}
        for scorer in SCORERS
    }
    product = scored[PRODUCT_SCORER]
    openhands_gemma = gemma_metric(load_jsonl(OPENHANDS_GEMMA))
    llama_gemma = gemma_metric(load_jsonl(LLAMA_GEMMA))
    gates = {
        "filtered_strict_preserved_22_of_22": product["filtered_strict"]["correct"] == 22,
        "old_canary_strict_preserved_23_of_23": product["old_canary_strict"]["correct"] == 23,
        "filtered_validation_at_least_stage11507_20_of_22": (product["filtered_validation"]["correct"] or 0) >= 20,
        "old_validation_at_least_stage11507_21_of_23": (product["old_canary_validation"]["correct"] or 0) >= 21,
        "openhands_heldout_improves_over_stage11507_zero": (product["openhands_heldout"]["correct"] or 0) > 0,
        "llama_stack_heldout_improves_over_stage11507_zero": (product["llama_stack_heldout"]["correct"] or 0) > 0,
        "openhands_beats_gemma": (product["openhands_heldout"]["correct"] or 0) > openhands_gemma["correct"],
        "llama_stack_beats_gemma": (product["llama_stack_heldout"]["correct"] or 0) > llama_gemma["correct"],
    }
    promoted = (
        gates["filtered_strict_preserved_22_of_22"]
        and gates["old_canary_strict_preserved_23_of_23"]
        and gates["openhands_beats_gemma"]
        and gates["llama_stack_beats_gemma"]
    )
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now(),
        "passed": True,
        "decision": "openhands_non_evidence_stage11507_support_promoted" if promoted else "openhands_non_evidence_stage11507_support_diagnostic_only",
        "runtime_initialization": init_card,
        "runtime_weights_sha256": init_card.get("weights_sha256"),
        "request": load_json_opt(REQUEST),
        "product_scorer": PRODUCT_SCORER,
        "scored": scored,
        "gemma_existing_artifacts": {"openhands": openhands_gemma, "llama_stack": llama_gemma},
        "comparison_to_stage11507_web_smokes": {
            "stage11521_llama_product_correct": baseline_correct(STAGE11521, "product"),
            "stage11526_llama_product_correct": product["llama_stack_heldout"]["correct"],
            "stage11522_openhands_product_correct": baseline_correct(STAGE11522, "product"),
            "stage11526_openhands_product_correct": product["openhands_heldout"]["correct"],
        },
        "gates": gates,
        "claim_boundary": [
            "Diagnostic non-evidence Web adaptation probe only.",
            "OpenHands train support shares repo family with OpenHands heldout; OpenHands heldout improvement alone is not promotable.",
            "Promotion would require preserving canaries and beating Gemma on heldout Web packets, which this audit checks explicitly.",
        ],
        "source_artifacts": {
            "runtime_bundle": rel(RUNTIME),
            "request": rel(REQUEST),
            "filtered_validation": rel(FILTERED_VALIDATION),
            "filtered_strict": rel(FILTERED_STRICT),
            "old_validation": rel(OLD_VALIDATION),
            "old_strict": rel(OLD_STRICT),
            "openhands_train": rel(OPENHANDS_TRAIN),
            "openhands_heldout": rel(OPENHANDS_HELDOUT),
            "llama_heldout": rel(LLAMA_HELDOUT),
            "openhands_gemma": rel(OPENHANDS_GEMMA),
            "llama_gemma": rel(LLAMA_GEMMA),
        },
        "outputs": {"summary": rel(SUMMARY), "audit_dir": rel(OUT)},
    }
    write_json(SUMMARY, summary)
    SUMMARIES.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(SUMMARY, SUMMARIES / f"{NAME}.json")
    print(
        json.dumps(
            {
                "decision": summary["decision"],
                "product": {
                    key: {
                        "correct": value["correct"],
                        "rows": value["rows"],
                        "accuracy": value["accuracy"],
                    }
                    for key, value in product.items()
                },
                "gemma": summary["gemma_existing_artifacts"],
                "gates": gates,
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
