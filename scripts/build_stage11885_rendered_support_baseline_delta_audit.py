#!/usr/bin/env python3
"""Score Stage11507 and Stage11882 on rendered support/protected rowsets."""

from __future__ import annotations

import json
import os
import shutil
import sys
import time
from collections import Counter
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
STAGE = 11885
NAME = "stage11885_rendered_support_baseline_delta_audit"
OUT = ART / NAME
SUMMARY = OUT / "rendered_support_baseline_delta_audit.json"

RUNTIMES = {
    "stage11507_selected_frontier": ART / "stage11507_preservation_strengthened_evidence_judgment_probe/runtime_model/runtime_model_bundle.json",
    "stage11882_rejected_unrendered_probe": ART / "stage11882_source_heldout_support_guarded_probe/runtime_model/runtime_model_bundle.json",
}
ROWSETS = {
    "rendered_added_support_train": ART / "stage11884_rendered_source_heldout_support_probe_package/rendered_source_heldout_support_added_train_rows.jsonl",
    "residual_bank": ART / "stage11442_targeted_residual_role_support_package/semantic_candidate_residual_bank.jsonl",
    "filtered_strict": ART / "stage11442_targeted_residual_role_support_package/agentkernel_lite_encdec_strict_eval.jsonl",
    "old_canary_strict": ART / "stage11429_selected_test_rust_support_package/agentkernel_lite_encdec_strict_eval.jsonl",
    "filtered_validation": ART / "stage11442_targeted_residual_role_support_package/agentkernel_lite_encdec_validation.jsonl",
    "old_canary_validation": ART / "stage11429_selected_test_rust_support_package/agentkernel_lite_encdec_validation.jsonl",
    "verifier_grounded_source_heldout_smoke": ART / "stage11740_verifier_grounded_source_heldout_successor_score/verifier_grounded_successor_rows.jsonl",
}
SCORER = "encoder_option_retrieval_evidence_judgment_head"

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


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_jsonl(path: Path) -> list[dict[str, Any]]:
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
        out["target"] = {
            "decoder_text": out.get("decoder_text") or label,
            "bounded_choice_target_label": label,
            "semantic_value": out.get("semantic_target_value") or out.get("target_value"),
        }
    if not isinstance(out.get("loss_mask"), dict):
        out["loss_mask"] = {"decoder_ce": True, "bounded_choice_aux": True}
    return out


def load_runtime(path: Path) -> tuple[Any, Any, dict[str, Any]]:
    bundle = load_json(path)
    metadata = bundle["metadata"]
    config = AgentKernelLiteTransformerConfig.from_recovered_target_json(load_json(Path(str(metadata["model_config"]))))
    model = AgentKernelLiteTransformerSeq2Seq(config)
    init_card = _load_runtime_model_bundle(path, model=model)
    model.to(DEVICE)
    model.eval()
    tokenizer = AgentKernelBPETokenizer(Path(str(metadata["tokenizer_json"])), Path(str(metadata["tokenizer_config"])))
    return model, tokenizer, init_card


def metric(card: dict[str, Any]) -> dict[str, Any]:
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
        "coverage": card.get("constrained_choice_coverage"),
        "accuracy": card.get("constrained_choice_top1_accuracy"),
        "misses": misses,
    }


def miss_breakdown(rows: list[dict[str, Any]], misses: list[dict[str, Any]]) -> dict[str, Any]:
    by_id = {str(row.get("row_id")): row for row in rows}
    out: dict[str, Any] = {}
    for key in ["language_family", "stage11880_support_source", "task_type", "repo_family"]:
        out[key] = dict(Counter(str(by_id.get(str(m.get("row_id")), {}).get(key)) for m in misses))
    return out


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    rowsets = {name: [normalize_row(row) for row in load_jsonl(path)] for name, path in ROWSETS.items()}
    results: dict[str, Any] = {}
    init_cards: dict[str, Any] = {}
    for runtime_name, runtime_path in RUNTIMES.items():
        model, tokenizer, init_card = load_runtime(runtime_path)
        init_cards[runtime_name] = init_card
        runtime_results: dict[str, Any] = {}
        for rowset_name, rows in rowsets.items():
            split_name = f"{runtime_name}__{rowset_name}"
            card = _write_bounded_choice_eval_audit(
                OUT,
                model=model,
                rows=rows,
                tokenizer=tokenizer,
                max_encoder_tokens=768,
                max_decoder_tokens=16,
                split_name=split_name,
                bounded_choice_aux_source=SCORER,
                eval_batch_size=8,
            )
            runtime_results[rowset_name] = metric(card)
        results[runtime_name] = runtime_results
        del model
        if torch.cuda.is_available():
            torch.cuda.empty_cache()

    support_rows = rowsets["rendered_added_support_train"]
    support_deltas = {
        name: results[name]["rendered_added_support_train"]["correct"] for name in RUNTIMES
    }
    residual_deltas = {name: results[name]["residual_bank"]["correct"] for name in RUNTIMES}
    stage11882_learned_rendered_support = support_deltas["stage11882_rejected_unrendered_probe"] > support_deltas["stage11507_selected_frontier"]
    stage11882_preserved_residual = residual_deltas["stage11882_rejected_unrendered_probe"] >= residual_deltas["stage11507_selected_frontier"]
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now(),
        "decision": (
            "rendered_support_train_fit_requires_retraining"
            if not stage11882_learned_rendered_support
            else "rejected_probe_has_some_rendered_support_transfer"
        ),
        "device": str(DEVICE),
        "scorer": SCORER,
        "results": results,
        "support_delta_correct": support_deltas,
        "residual_delta_correct": residual_deltas,
        "stage11882_learned_rendered_support": stage11882_learned_rendered_support,
        "stage11882_preserved_residual": stage11882_preserved_residual,
        "rendered_support_miss_breakdown": {
            name: miss_breakdown(support_rows, results[name]["rendered_added_support_train"]["misses"])
            for name in RUNTIMES
        },
        "runtime_initialization": init_cards,
        "source_artifacts": {name: rel(path) for name, path in ROWSETS.items()},
        "outputs": {"summary": rel(SUMMARY), "audit_dir": rel(OUT)},
        "claim_boundary": [
            "This is a diagnostic score audit only; no model is promoted here.",
            "Stage11882 trained on unrendered support inputs, so poor rendered support transfer implies retraining is required.",
        ],
    }
    write_json(SUMMARY, summary)
    SUMMARIES.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(SUMMARY, SUMMARIES / f"{NAME}.json")
    print(
        json.dumps(
            {
                "decision": summary["decision"],
                "support_delta_correct": support_deltas,
                "residual_delta_correct": residual_deltas,
                "protected": {
                    runtime: {
                        "old_strict": results[runtime]["old_canary_strict"]["correct"],
                        "filtered_strict": results[runtime]["filtered_strict"]["correct"],
                        "old_val": results[runtime]["old_canary_validation"]["correct"],
                        "filtered_val": results[runtime]["filtered_validation"]["correct"],
                    }
                    for runtime in RUNTIMES
                },
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
