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
STAGE = 11656
NAME = "stage11656_same_root_grouped_head_only_postrun_audit"
OUT = ART / NAME
SUMMARY = OUT / "same_root_grouped_head_only_postrun_audit.json"

RUNTIME = ART / "stage11655_same_root_grouped_head_only_probe/runtime_model/runtime_model_bundle.json"
ROWSETS = {
    "grouped_web_gap_train_support": ART / "stage11648_web_gap_grouped_admission_compiler/web_gap_grouped_probe_manifest.jsonl",
    "web_heldout": ART / "stage11548_web_root_heldout_stage11507_score_audit/web_root_heldout_rows.jsonl",
    "web_successor_strict": ART / "stage11597_web_answerable_no_abstain_geometry_audit/web_answerable_no_abstain_successor_strict_rows.jsonl",
    "residual_bank": ART / "stage11442_targeted_residual_role_support_package/semantic_candidate_residual_bank.jsonl",
    "filtered_strict": ART / "stage11442_targeted_residual_role_support_package/agentkernel_lite_encdec_strict_eval.jsonl",
    "old_canary_strict": ART / "stage11429_selected_test_rust_support_package/agentkernel_lite_encdec_strict_eval.jsonl",
    "filtered_validation": ART / "stage11442_targeted_residual_role_support_package/agentkernel_lite_encdec_validation.jsonl",
    "old_canary_validation": ART / "stage11429_selected_test_rust_support_package/agentkernel_lite_encdec_validation.jsonl",
}
SCORER = "encoder_option_retrieval_web_task_candidate_head"

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
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def normalize_row(row: dict[str, Any]) -> dict[str, Any]:
    out = dict(row)
    out.setdefault("prompt_text", out.get("input_text") or out.get("prompt") or "")
    out.setdefault("decoder_text", out.get("target_text") or out.get("bounded_choice_target_label") or "")
    if not isinstance(out.get("loss_mask"), dict):
        out["loss_mask"] = {"decoder_ce": True, "bounded_choice_aux": True}
    source = dict(out.get("standalone_projection_source") or {})
    source.setdefault("opaque_options", out.get("opaque_options") or [])
    out["standalone_projection_source"] = source
    if "target" not in out or not isinstance(out.get("target"), dict):
        out["target"] = {
            "decoder_text": out.get("decoder_text"),
            "bounded_choice_target_label": out.get("bounded_choice_target_label") or out.get("target_text"),
            "semantic_value": out.get("semantic_target_value") or out.get("target_semantic_value"),
        }
    return out


def load_runtime() -> tuple[Any, Any, dict[str, Any], dict[str, Any]]:
    bundle = load_json(RUNTIME)
    metadata = bundle["metadata"]
    config = AgentKernelLiteTransformerConfig.from_recovered_target_json(load_json(Path(str(metadata["model_config"]))))
    model = AgentKernelLiteTransformerSeq2Seq(config)
    init_card = _load_runtime_model_bundle(RUNTIME, model=model)
    model.to(DEVICE)
    model.eval()
    tokenizer = AgentKernelBPETokenizer(Path(str(metadata["tokenizer_json"])), Path(str(metadata["tokenizer_config"])))
    return model, tokenizer, init_card, bundle


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


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    rowsets = {name: [normalize_row(row) for row in load_jsonl(path)] for name, path in ROWSETS.items()}
    model, tokenizer, init_card, bundle = load_runtime()
    results: dict[str, Any] = {}
    for name, rows in rowsets.items():
        card = _write_bounded_choice_eval_audit(
            OUT,
            model=model,
            rows=rows,
            tokenizer=tokenizer,
            max_encoder_tokens=768,
            max_decoder_tokens=16,
            split_name=name,
            bounded_choice_aux_source=SCORER,
            eval_batch_size=8,
        )
        results[name] = metric(card)

    gates = {
        "grouped_train_support_at_least_80_of_113": (results["grouped_web_gap_train_support"]["correct"] or 0) >= 80
        and results["grouped_web_gap_train_support"]["rows"] == 113,
        "grouped_train_support_at_least_100_of_113": (results["grouped_web_gap_train_support"]["correct"] or 0) >= 100
        and results["grouped_web_gap_train_support"]["rows"] == 113,
        "grouped_train_support_full_coverage": results["grouped_web_gap_train_support"]["coverage"] == 1.0
        and results["grouped_web_gap_train_support"]["rows"] == 113,
        "filtered_strict_22_of_22": results["filtered_strict"]["correct"] == 22 and results["filtered_strict"]["rows"] == 22,
        "old_canary_strict_23_of_23": results["old_canary_strict"]["correct"] == 23 and results["old_canary_strict"]["rows"] == 23,
        "filtered_validation_at_least_20_of_22": (results["filtered_validation"]["correct"] or 0) >= 20
        and results["filtered_validation"]["rows"] == 22,
        "old_canary_validation_at_least_21_of_23": (results["old_canary_validation"]["correct"] or 0) >= 21
        and results["old_canary_validation"]["rows"] == 23,
        "residual_at_least_7_of_10": (results["residual_bank"]["correct"] or 0) >= 7 and results["residual_bank"]["rows"] == 10,
        "web_heldout_beats_routed_38_of_66": (results["web_heldout"]["correct"] or 0) > 38 and results["web_heldout"]["rows"] == 66,
        "web_heldout_beats_gemma_52_of_66": (results["web_heldout"]["correct"] or 0) > 52 and results["web_heldout"]["rows"] == 66,
        "web_successor_at_least_30_of_36": (results["web_successor_strict"]["correct"] or 0) >= 30
        and results["web_successor_strict"]["rows"] == 36,
    }
    preservation_gates = {
        key: gates[key]
        for key in [
            "filtered_strict_22_of_22",
            "old_canary_strict_23_of_23",
            "filtered_validation_at_least_20_of_22",
            "old_canary_validation_at_least_21_of_23",
            "residual_at_least_7_of_10",
        ]
    }

    if not all(preservation_gates.values()):
        decision = "same_root_grouped_head_only_rejected_protected_gate_regression"
    elif gates["web_heldout_beats_gemma_52_of_66"]:
        decision = "same_root_grouped_head_only_beats_web_gemma_but_remains_diagnostic"
    elif gates["web_heldout_beats_routed_38_of_66"]:
        decision = "same_root_grouped_head_only_improves_web_but_remains_diagnostic"
    elif gates["grouped_train_support_at_least_80_of_113"]:
        decision = "same_root_grouped_head_only_support_fit_without_heldout_gain"
    else:
        decision = "same_root_grouped_head_only_no_support_or_heldout_gain"

    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now(),
        "decision": decision,
        "runtime": rel(RUNTIME),
        "runtime_weights_sha256": bundle.get("weights_sha256"),
        "device": str(DEVICE),
        "scorer": SCORER,
        "results": results,
        "gates": gates,
        "preservation_gates": preservation_gates,
        "baseline_reference": {
            "selected_frontier": "stage11507 + encoder_option_retrieval_evidence_judgment_head",
            "routed_product_web": "38/66",
            "gemma_web": "52/66",
            "selected_residual": "7/10",
            "stage11651b_full_model_web": "3/66",
            "stage11651b_full_model_residual": "3/10",
        },
        "runtime_initialization": init_card,
        "source_artifacts": {name: rel(path) for name, path in ROWSETS.items()},
        "outputs": {"summary": rel(SUMMARY), "audit_dir": rel(OUT)},
        "claim_boundary": [
            "Stage11655 is a head-only diagnostic probe, not a promotion candidate by itself.",
            "The run tests whether same-root grouped Web-gap rows are learnable without updating the shared encoder.",
            "Any Web improvement must still preserve filtered strict, old canary strict, validation, and residual gates.",
            "Grouped train-support fit is diagnostic only and does not establish Web heldout generalization.",
        ],
    }
    write_json(SUMMARY, summary)
    SUMMARIES.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(SUMMARY, SUMMARIES / f"{NAME}.json")
    print(
        json.dumps(
            {
                "decision": decision,
                "gates": gates,
                "compact": {key: {"correct": value["correct"], "rows": value["rows"]} for key, value in results.items()},
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
