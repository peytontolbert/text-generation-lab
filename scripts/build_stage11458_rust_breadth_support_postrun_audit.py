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

ARTIFACTS = ROOT / "runs/local/artifacts"
SUMMARIES = ROOT / "runs/summaries"
STAGE = 11458
NAME = "stage11458_rust_breadth_support_postrun_audit"
OUT_DIR = ARTIFACTS / NAME
SUMMARY_JSON = OUT_DIR / "rust_breadth_support_postrun_audit.json"
RUNTIME = ARTIFACTS / "stage11457_rust_breadth_support_probe/runtime_model/runtime_model_bundle.json"
REQUEST = ARTIFACTS / "stage11456_rust_breadth_support_probe_request/rust_breadth_support_probe_request.json"
PACKAGE = ARTIFACTS / "stage11454_rust_breadth_support_package_v2/rust_breadth_support_package_v2.json"
FILTERED_VALIDATION = ARTIFACTS / "stage11454_rust_breadth_support_package_v2/agentkernel_lite_encdec_validation.jsonl"
FILTERED_STRICT = ARTIFACTS / "stage11454_rust_breadth_support_package_v2/agentkernel_lite_encdec_strict_eval.jsonl"
RESIDUAL = ARTIFACTS / "stage11454_rust_breadth_support_package_v2/semantic_candidate_residual_bank.jsonl"
OLD_VALIDATION = ARTIFACTS / "stage11429_selected_test_rust_support_package/agentkernel_lite_encdec_validation.jsonl"
OLD_STRICT = ARTIFACTS / "stage11429_selected_test_rust_support_package/agentkernel_lite_encdec_strict_eval.jsonl"
SCORERS = ["encoder_option_retrieval", "encoder_option_retrieval_semantic_candidate_head", "decoder_first_step"]
PRODUCT_SCORER = "encoder_option_retrieval"

torch.set_num_threads(max(1, int(os.environ.get("AGENTKERNEL_EVAL_THREADS", "8"))))
try:
    torch.set_num_interop_threads(max(1, min(4, int(os.environ.get("AGENTKERNEL_EVAL_THREADS", "8")))))
except RuntimeError:
    pass
DEVICE = torch.device(os.environ.get("AGENTKERNEL_EVAL_DEVICE", "cuda" if torch.cuda.is_available() else "cpu"))


def now_utc() -> str:
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
        OUT_DIR,
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
    request = load_json(REQUEST)
    package = load_json(PACKAGE)
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
    promotion_gates = {
        "product_filtered_strict_22_of_22": product["filtered_strict"]["correct"] == 22,
        "product_filtered_validation_at_least_20_of_22": (product["filtered_validation"]["correct"] or 0) >= 20,
        "product_residual_above_base_5_of_10": (product["residual_bank"]["correct"] or 0) > 5,
        "old_canary_strict_preserves_23_of_23": product["old_canary_strict"]["correct"] == 23,
        "coverage_full_for_product_residual": product["residual_bank"].get("coverage") == 1.0,
    }
    promoted = all(promotion_gates.values())
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": True,
        "decision": "rust_breadth_support_probe_promoted" if promoted else "rust_breadth_support_probe_rejected_or_diagnostic_only",
        "runtime_initialization": init_card,
        "runtime_weights_sha256": init_card.get("weights_sha256"),
        "request_metrics": request.get("metrics"),
        "package_counts": package.get("counts"),
        "scored": scored,
        "promotion_gates": promotion_gates,
        "decision_basis": [
            "Stage11457 trained on the Rust breadth support package initialized from the selected Stage11444 runtime.",
            "Promotion requires no filtered strict regression, no old-canary regression, and residual bank improvement beyond 5/10.",
            "A strict regression or flat residual keeps the runtime diagnostic-only even if some Rust support rows were materialized correctly.",
        ],
        "source_artifacts": {
            "runtime_bundle": rel(RUNTIME),
            "request": rel(REQUEST),
            "package": rel(PACKAGE),
            "filtered_validation": rel(FILTERED_VALIDATION),
            "filtered_strict": rel(FILTERED_STRICT),
            "residual_bank": rel(RESIDUAL),
            "old_canary_validation": rel(OLD_VALIDATION),
            "old_canary_strict": rel(OLD_STRICT),
        },
        "outputs": {"summary_json": rel(SUMMARY_JSON)},
    }
    write_json(SUMMARY_JSON, summary)
    SUMMARIES.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(SUMMARY_JSON, SUMMARIES / f"{NAME}.json")
    print(json.dumps({"decision": summary["decision"], "promotion_gates": promotion_gates, "product": product}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
