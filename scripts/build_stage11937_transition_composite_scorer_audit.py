#!/usr/bin/env python3
"""Audit Stage11935 semantic-plus-transition composite scorer runtime."""

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
STAGE = 11937
NAME = "stage11937_transition_composite_scorer_audit"
OUT = ART / NAME
SUMMARY = OUT / "transition_composite_scorer_audit.json"

TRANSITION_ROWS = ART / "stage11897_transition_record_projection_rows/transition_projection_rows.jsonl"
RUNTIMES = {
    "stage11507_selected_frontier": ART / "stage11507_preservation_strengthened_evidence_judgment_probe/runtime_model/runtime_model_bundle.json",
    "stage11924_transition_listwise_head_only": ART / "stage11924_transition_listwise_head_only_probe/runtime_model/runtime_model_bundle.json",
    "stage11935_transition_candidate_head": ART / "stage11935_transition_candidate_head_probe/runtime_model/runtime_model_bundle.json",
}
PROTECTED_ROWSETS = {
    "residual_bank": ART / "stage11442_targeted_residual_role_support_package/semantic_candidate_residual_bank.jsonl",
    "filtered_strict": ART / "stage11442_targeted_residual_role_support_package/agentkernel_lite_encdec_strict_eval.jsonl",
    "old_canary_strict": ART / "stage11429_selected_test_rust_support_package/agentkernel_lite_encdec_strict_eval.jsonl",
    "filtered_validation": ART / "stage11442_targeted_residual_role_support_package/agentkernel_lite_encdec_validation.jsonl",
    "old_canary_validation": ART / "stage11429_selected_test_rust_support_package/agentkernel_lite_encdec_validation.jsonl",
    "verifier_grounded_source_heldout_smoke": ART / "stage11740_verifier_grounded_source_heldout_successor_score/verifier_grounded_successor_rows.jsonl",
}
TRANSITION_SCORERS = {
    "stage11507_selected_frontier": "encoder_option_retrieval_evidence_judgment_head",
    "stage11924_transition_listwise_head_only": "encoder_option_retrieval_semantic_candidate_head",
    "stage11935_transition_candidate_head": "encoder_option_retrieval_semantic_plus_transition_candidate_head",
}
COMPACT_SCORER = "encoder_option_retrieval_evidence_judgment_head"

torch.set_num_threads(max(1, int(os.environ.get("AGENTKERNEL_EVAL_THREADS", "8"))))
try:
    torch.set_num_interop_threads(max(1, min(4, int(os.environ.get("AGENTKERNEL_EVAL_THREADS", "8")))))
except RuntimeError:
    pass
DEVICE = torch.device(os.environ.get("AGENTKERNEL_EVAL_DEVICE", "cuda" if torch.cuda.is_available() else "cpu"))


def now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def rel(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def normalize_row(row: dict[str, Any]) -> dict[str, Any]:
    out = dict(row)
    source = dict(out.get("standalone_projection_source") or {})
    source.setdefault("opaque_options", out.get("opaque_options") or [])
    out["standalone_projection_source"] = source
    if not isinstance(out.get("target"), dict):
        label = out.get("bounded_choice_target_label") or out.get("target_label") or out.get("target_text")
        out["target"] = {"decoder_text": out.get("decoder_text") or label, "bounded_choice_target_label": label}
    out.setdefault("loss_mask", {"decoder_ce": True, "bounded_choice_aux": True})
    return out


def load_runtime(path: Path) -> tuple[Any, Any, dict[str, Any]]:
    bundle = read_json(path)
    metadata = bundle["metadata"]
    config = AgentKernelLiteTransformerConfig.from_recovered_target_json(read_json(Path(str(metadata["model_config"]))))
    model = AgentKernelLiteTransformerSeq2Seq(config)
    init_card = _load_runtime_model_bundle(path, model=model)
    model.to(DEVICE)
    model.eval()
    tokenizer = AgentKernelBPETokenizer(Path(str(metadata["tokenizer_json"])), Path(str(metadata["tokenizer_config"])))
    return model, tokenizer, init_card


def metric(card: dict[str, Any]) -> dict[str, Any]:
    return {
        "rows": card.get("rows"),
        "correct": card.get("constrained_choice_correct"),
        "accuracy": card.get("constrained_choice_top1_accuracy"),
        "coverage": card.get("constrained_choice_coverage"),
        "miss_count": sum(1 for row in card.get("row_cards") or [] if row.get("constrained_choice_match") is not True),
    }


def grouped(card: dict[str, Any], key: str) -> dict[str, Any]:
    buckets: dict[str, list[dict[str, Any]]] = {}
    for row in card.get("row_cards") or []:
        buckets.setdefault(str(row.get(key)), []).append(row)
    out = {}
    for name, rows in sorted(buckets.items()):
        correct = sum(1 for row in rows if row.get("constrained_choice_match") is True)
        out[name] = {"rows": len(rows), "correct": correct, "accuracy": correct / len(rows) if rows else None}
    return out


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    transition_rows = [normalize_row(row) for row in read_jsonl(TRANSITION_ROWS)]
    protected = {name: [normalize_row(row) for row in read_jsonl(path)] for name, path in PROTECTED_ROWSETS.items()}
    results: dict[str, Any] = {}
    init_cards: dict[str, Any] = {}
    for runtime_name, runtime_path in RUNTIMES.items():
        model, tokenizer, init_card = load_runtime(runtime_path)
        init_cards[runtime_name] = init_card
        transition_source = TRANSITION_SCORERS[runtime_name]
        card = _write_bounded_choice_eval_audit(
            OUT / runtime_name,
            model=model,
            rows=transition_rows,
            tokenizer=tokenizer,
            max_encoder_tokens=768,
            max_decoder_tokens=16,
            split_name=f"transition_projection__{transition_source}",
            bounded_choice_aux_source=transition_source,
            eval_batch_size=8,
        )
        runtime_results: dict[str, Any] = {
            "transition_projection_routed": metric(card),
            "transition_by_language": grouped(card, "language_family"),
            "transition_by_task": grouped(card, "task_type"),
        }
        for name, rows in protected.items():
            pcard = _write_bounded_choice_eval_audit(
                OUT / runtime_name,
                model=model,
                rows=rows,
                tokenizer=tokenizer,
                max_encoder_tokens=768,
                max_decoder_tokens=16,
                split_name=f"protected__{name}__evidence_judgment_head",
                bounded_choice_aux_source=COMPACT_SCORER,
                eval_batch_size=8,
            )
            runtime_results[f"protected::{name}"] = metric(pcard)
        results[runtime_name] = runtime_results
        del model
        if torch.cuda.is_available():
            torch.cuda.empty_cache()

    selected = results["stage11507_selected_frontier"]
    previous = results["stage11924_transition_listwise_head_only"]
    postrun = results["stage11935_transition_candidate_head"]
    gates = {
        "transition_projection_improved_vs_selected": (postrun["transition_projection_routed"].get("correct") or 0) > (selected["transition_projection_routed"].get("correct") or 0),
        "transition_projection_improved_vs_stage11924": (postrun["transition_projection_routed"].get("correct") or 0) > (previous["transition_projection_routed"].get("correct") or 0),
        "transition_projection_above_364_of_640": (postrun["transition_projection_routed"].get("correct") or 0) > 364,
        "transition_projection_at_least_gemma_386_of_640": (postrun["transition_projection_routed"].get("correct") or 0) >= 386,
        "filtered_strict_preserved": postrun["protected::filtered_strict"].get("correct") == 22,
        "old_canary_strict_preserved": postrun["protected::old_canary_strict"].get("correct") == 23,
        "filtered_validation_preserved": (postrun["protected::filtered_validation"].get("correct") or 0) >= 20,
        "old_canary_validation_preserved": (postrun["protected::old_canary_validation"].get("correct") or 0) >= 21,
        "residual_preserved": (postrun["protected::residual_bank"].get("correct") or 0) >= 7,
        "smoke_preserved": (postrun["protected::verifier_grounded_source_heldout_smoke"].get("correct") or 0) >= 6,
    }
    protected_ok = all(
        gates[key]
        for key in (
            "filtered_strict_preserved",
            "old_canary_strict_preserved",
            "filtered_validation_preserved",
            "old_canary_validation_preserved",
            "residual_preserved",
            "smoke_preserved",
        )
    )
    if protected_ok and gates["transition_projection_at_least_gemma_386_of_640"]:
        decision = "transition_composite_scorer_promotable_pending_same_manifest_gemma_attachment"
    elif protected_ok and gates["transition_projection_improved_vs_stage11924"]:
        decision = "transition_composite_scorer_improved_but_not_gemma_beating"
    elif protected_ok:
        decision = "transition_composite_scorer_preserved_but_no_frontier_gain"
    else:
        decision = "transition_composite_scorer_rejected_protected_regression"
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now(),
        "decision": decision,
        "device": str(DEVICE),
        "route_policy": {"transition_projection_rows": TRANSITION_SCORERS, "compact_protected_rows": COMPACT_SCORER},
        "gates": gates,
        "results": results,
        "runtime_initialization": init_cards,
        "source_artifacts": {
            "transition_rows": rel(TRANSITION_ROWS),
            "runtimes": {name: rel(path) for name, path in RUNTIMES.items()},
            "protected_rowsets": {name: rel(path) for name, path in PROTECTED_ROWSETS.items()},
        },
        "outputs": {"summary": rel(SUMMARY), "audit_dir": rel(OUT)},
    }
    write_json(SUMMARY, summary)
    SUMMARIES.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(SUMMARY, SUMMARIES / f"{NAME}.json")
    print(
        json.dumps(
            {
                "decision": decision,
                "gates": gates,
                "previous_transition": previous["transition_projection_routed"],
                "postrun_transition": postrun["transition_projection_routed"],
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
