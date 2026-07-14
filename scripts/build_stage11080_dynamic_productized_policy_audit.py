#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import torch

from legacy_src.agentkernel_lite.modeling_transformer import AgentKernelLiteTransformerConfig, AgentKernelLiteTransformerSeq2Seq
from legacy_src.agentkernel_lite.training_data import AgentKernelBPETokenizer
from legacy_src.agentkernel_lite.training_loop import _load_runtime_model_bundle, _write_bounded_choice_eval_audit


ARTIFACTS = ROOT / "runs" / "local" / "artifacts"
STAGE = 11080
NAME = "stage11080_dynamic_productized_policy_audit"
OUT_DIR = ARTIFACTS / NAME
SUMMARY_JSON = OUT_DIR / "dynamic_productized_policy_audit.json"

RUNTIME_BUNDLE = ARTIFACTS / "stage11071_a_prior_and_python_verifier_diagnostic_probe" / "runtime_model" / "runtime_model_bundle.json"
CLEAN_VALIDATION = ARTIFACTS / "stage11065_singleton_eval_quarantine_package" / "agentkernel_lite_encdec_validation.jsonl"
CLEAN_STRICT = ARTIFACTS / "stage11065_singleton_eval_quarantine_package" / "agentkernel_lite_encdec_strict_eval.jsonl"
RESERVED_ROWS = ARTIFACTS / "stage11051_successor_residual_support_plus_priority_evidence" / "reserved_residual_candidates.jsonl"

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


def load_runtime():
    bundle = load_json(RUNTIME_BUNDLE)
    metadata = bundle["metadata"]
    config = AgentKernelLiteTransformerConfig.from_recovered_target_json(load_json(Path(str(metadata["model_config"]))))
    model = AgentKernelLiteTransformerSeq2Seq(config)
    init_card = _load_runtime_model_bundle(RUNTIME_BUNDLE, model=model)
    tokenizer = AgentKernelBPETokenizer(Path(str(metadata["tokenizer_json"])), Path(str(metadata["tokenizer_config"])))
    model.to(EVAL_DEVICE)
    model.eval()
    return model, tokenizer, init_card


def summarize(card: dict[str, Any]) -> dict[str, Any]:
    return {
        "rows": int(card.get("rows") or 0),
        "exact_accuracy": card.get("constrained_choice_top1_accuracy"),
        "full_vocab_top1_accuracy": card.get("full_vocab_top1_accuracy"),
        "rows_with_target_rank_1": card.get("rows_with_target_rank_1"),
        "miss_rows": [row.get("row_id") for row in card.get("row_cards", []) if row.get("constrained_choice_match") is False],
    }


def index_cards(card: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {str(row.get("row_id") or ""): row for row in (card.get("row_cards") or []) if isinstance(row, dict)}


def composite_eval(*, rows: list[dict[str, Any]], base_card: dict[str, Any], dynamic_card: dict[str, Any]) -> dict[str, Any]:
    base_index = index_cards(base_card)
    dynamic_index = index_cards(dynamic_card)
    row_cards = []
    correct = 0
    changed = 0
    for row in rows:
        row_id = str(row.get("row_id") or "")
        task_type = str(row.get("task_type") or "")
        target = str(row.get("target_text") or "")
        base = base_index.get(row_id, {})
        dynamic = dynamic_index.get(row_id, {})
        selected_policy = "base"
        predicted = base.get("constrained_choice_top1_label")
        if task_type == "verifier_outcome_semantic_transition":
            predicted = base.get("full_vocab_top1_text")
            selected_policy = "decoder_transition"
        elif task_type == "evidence_citation":
            predicted = dynamic.get("constrained_choice_top1_label")
            selected_policy = "dynamic_productized_evidence"
        match = predicted == target
        if match:
            correct += 1
        if predicted != base.get("constrained_choice_top1_label"):
            changed += 1
        row_cards.append(
            {
                "row_id": row_id,
                "task_type": task_type,
                "language_family": str(row.get("language_family") or ""),
                "target_text": target,
                "base_label": base.get("constrained_choice_top1_label"),
                "dynamic_label": dynamic.get("constrained_choice_top1_label"),
                "decoder_label": base.get("full_vocab_top1_text"),
                "selected_policy": selected_policy,
                "selected_label": predicted,
                "selected_correct": match,
            }
        )
    return {
        "rows": len(rows),
        "correct": correct,
        "exact_accuracy": (correct / len(rows)) if rows else None,
        "changed_rows": changed,
        "row_cards": row_cards,
        "miss_rows": [row["row_id"] for row in row_cards if not row["selected_correct"]],
    }


def main() -> None:
    model, tokenizer, init_card = load_runtime()

    clean_validation_rows = load_jsonl(CLEAN_VALIDATION)
    clean_strict_rows = load_jsonl(CLEAN_STRICT)
    reserved_rows = load_jsonl(RESERVED_ROWS)

    eval_sets = [
        ("clean_validation_base", clean_validation_rows, "encoder_option_retrieval"),
        ("clean_validation_dynamic", clean_validation_rows, "encoder_option_retrieval_dynamic_productized"),
        ("clean_strict_base", clean_strict_rows, "encoder_option_retrieval"),
        ("clean_strict_dynamic", clean_strict_rows, "encoder_option_retrieval_dynamic_productized"),
        ("reserved_base", reserved_rows, "encoder_option_retrieval"),
        ("reserved_dynamic", reserved_rows, "encoder_option_retrieval_dynamic_productized"),
    ]
    cards: dict[str, dict[str, Any]] = {}
    for split_name, rows, source in eval_sets:
        cards[split_name] = _write_bounded_choice_eval_audit(
            OUT_DIR,
            model=model,
            rows=rows,
            tokenizer=tokenizer,
            max_encoder_tokens=768,
            max_decoder_tokens=8,
            split_name=split_name,
            bounded_choice_aux_source=source,
            eval_batch_size=8,
        )

    composite_validation = composite_eval(
        rows=clean_validation_rows,
        base_card=cards["clean_validation_base"],
        dynamic_card=cards["clean_validation_dynamic"],
    )
    composite_strict = composite_eval(
        rows=clean_strict_rows,
        base_card=cards["clean_strict_base"],
        dynamic_card=cards["clean_strict_dynamic"],
    )
    composite_reserved = composite_eval(
        rows=reserved_rows,
        base_card=cards["reserved_base"],
        dynamic_card=cards["reserved_dynamic"],
    )

    payload = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": True,
        "claim_scope": [
            "Audit whether task-conditioned dynamic productized retrieval can improve evidence-citation behavior on the current runtime without regressing the cleaned canary.",
            "Compare base retrieval, dynamic productized retrieval, and a narrow composite policy that preserves the existing verifier-transition decoder override.",
        ],
        "runtime_bundle": rel(RUNTIME_BUNDLE),
        "runtime_initialization": init_card,
        "base_policy": {
            "clean_validation": summarize(cards["clean_validation_base"]),
            "clean_strict": summarize(cards["clean_strict_base"]),
            "reserved_residual": summarize(cards["reserved_base"]),
        },
        "dynamic_productized_policy": {
            "clean_validation": summarize(cards["clean_validation_dynamic"]),
            "clean_strict": summarize(cards["clean_strict_dynamic"]),
            "reserved_residual": summarize(cards["reserved_dynamic"]),
        },
        "composite_policy": {
            "definition": [
                "verifier_outcome_semantic_transition -> decoder full-vocab top1",
                "evidence_citation -> encoder_option_retrieval_dynamic_productized",
                "all other task types -> encoder_option_retrieval",
            ],
            "clean_validation": {
                "rows": composite_validation["rows"],
                "exact_accuracy": composite_validation["exact_accuracy"],
                "changed_rows": composite_validation["changed_rows"],
                "miss_rows": composite_validation["miss_rows"],
            },
            "clean_strict": {
                "rows": composite_strict["rows"],
                "exact_accuracy": composite_strict["exact_accuracy"],
                "changed_rows": composite_strict["changed_rows"],
                "miss_rows": composite_strict["miss_rows"],
            },
            "reserved_residual": {
                "rows": composite_reserved["rows"],
                "exact_accuracy": composite_reserved["exact_accuracy"],
                "changed_rows": composite_reserved["changed_rows"],
                "miss_rows": composite_reserved["miss_rows"],
            },
        },
        "delta_vs_base": {
            "clean_validation": None if composite_validation["exact_accuracy"] is None or cards["clean_validation_base"].get("constrained_choice_top1_accuracy") is None else composite_validation["exact_accuracy"] - float(cards["clean_validation_base"]["constrained_choice_top1_accuracy"]),
            "clean_strict": None if composite_strict["exact_accuracy"] is None or cards["clean_strict_base"].get("constrained_choice_top1_accuracy") is None else composite_strict["exact_accuracy"] - float(cards["clean_strict_base"]["constrained_choice_top1_accuracy"]),
            "reserved_residual": None if composite_reserved["exact_accuracy"] is None or cards["reserved_base"].get("constrained_choice_top1_accuracy") is None else composite_reserved["exact_accuracy"] - float(cards["reserved_base"]["constrained_choice_top1_accuracy"]),
        },
        "findings": [
            "This isolates the remaining interface question without retraining: whether task-conditioned option text helps evidence rows on the current frontier runtime.",
            "Any gain here is an inference-policy/interface gain, not a new model-capability result.",
            "If the composite policy helps reserved evidence rows while preserving the cleaned canary, it is a plausible next productized scorer boundary.",
        ],
        "next_best_step": "If the composite policy is strictly better on the cleaned canary or reserved residual bank without regressions, freeze it as the new standalone scored-interface candidate; otherwise keep the current verifier-only contract and continue with data/scorer-head work.",
    }
    write_json(SUMMARY_JSON, payload)
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
