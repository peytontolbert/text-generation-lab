#!/usr/bin/env python3
"""Postrun audit for Stage11882 guarded support probe."""

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
STAGE = 11883
NAME = "stage11883_source_heldout_support_guarded_postrun_audit"
OUT = ART / NAME
SUMMARY = OUT / "source_heldout_support_guarded_postrun_audit.json"

RUNTIME = ART / "stage11882_source_heldout_support_guarded_probe/runtime_model/runtime_model_bundle.json"
PACKAGE = ART / "stage11880_source_heldout_support_guarded_probe_package/source_heldout_support_guarded_probe_package.json"
ROWSETS = {
    "added_support_train": ART / "stage11880_source_heldout_support_guarded_probe_package/source_heldout_support_added_train_rows.jsonl",
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
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def normalize_row(row: dict[str, Any]) -> dict[str, Any]:
    out = dict(row)
    out.setdefault("prompt_text", out.get("input_text") or out.get("prompt") or "")
    out.setdefault("decoder_text", out.get("target_text") or out.get("bounded_choice_target_label") or out.get("target_label") or "")
    if not isinstance(out.get("loss_mask"), dict):
        out["loss_mask"] = {"decoder_ce": True, "bounded_choice_aux": True}
    source = dict(out.get("standalone_projection_source") or {})
    source.setdefault("opaque_options", out.get("opaque_options") or [])
    out["standalone_projection_source"] = source
    if "target" not in out or not isinstance(out.get("target"), dict):
        out["target"] = {
            "decoder_text": out.get("decoder_text"),
            "bounded_choice_target_label": out.get("bounded_choice_target_label") or out.get("target_text") or out.get("target_label"),
            "semantic_value": out.get("semantic_target_value") or out.get("target_value") or out.get("target_semantic_value"),
        }
    return out


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
    package = load_json(PACKAGE)
    rowsets = {name: [normalize_row(row) for row in load_jsonl(path)] for name, path in ROWSETS.items()}
    model, tokenizer, init_card = load_runtime()
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
        "old_canary_strict_23_of_23": results["old_canary_strict"]["correct"] == 23 and results["old_canary_strict"]["rows"] == 23,
        "filtered_strict_22_of_22": results["filtered_strict"]["correct"] == 22 and results["filtered_strict"]["rows"] == 22,
        "filtered_validation_at_least_20_of_22": (results["filtered_validation"]["correct"] or 0) >= 20
        and results["filtered_validation"]["rows"] == 22,
        "old_canary_validation_at_least_21_of_23": (results["old_canary_validation"]["correct"] or 0) >= 21
        and results["old_canary_validation"]["rows"] == 23,
        "residual_at_least_7_of_10": (results["residual_bank"]["correct"] or 0) >= 7 and results["residual_bank"]["rows"] == 10,
        "residual_improves_beyond_stage11507": (results["residual_bank"]["correct"] or 0) > 7 and results["residual_bank"]["rows"] == 10,
        "support_train_at_least_140_of_160": (results["added_support_train"]["correct"] or 0) >= 140
        and results["added_support_train"]["rows"] == 160,
        "source_heldout_smoke_not_regressed": (results["verifier_grounded_source_heldout_smoke"]["correct"] or 0) >= 2
        and results["verifier_grounded_source_heldout_smoke"]["rows"] == 3,
        "source_heldout_smoke_improves": (results["verifier_grounded_source_heldout_smoke"]["correct"] or 0) > 2
        and results["verifier_grounded_source_heldout_smoke"]["rows"] == 3,
    }
    preservation_gates = {
        key: gates[key]
        for key in [
            "old_canary_strict_23_of_23",
            "filtered_strict_22_of_22",
            "filtered_validation_at_least_20_of_22",
            "old_canary_validation_at_least_21_of_23",
            "residual_at_least_7_of_10",
        ]
    }
    if not all(preservation_gates.values()):
        decision = "reject_stage11882_guarded_support_probe_protected_gate_regression"
    elif gates["residual_improves_beyond_stage11507"] or gates["source_heldout_smoke_improves"]:
        decision = "stage11882_guarded_support_probe_frontier_lift_candidate"
    elif gates["support_train_at_least_140_of_160"]:
        decision = "stage11882_support_fit_without_frontier_lift"
    else:
        decision = "stage11882_no_support_fit_no_frontier_lift"

    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now(),
        "decision": decision,
        "runtime": rel(RUNTIME),
        "device": str(DEVICE),
        "scorer": SCORER,
        "results": results,
        "gates": gates,
        "preservation_gates": preservation_gates,
        "package": {
            "summary": rel(PACKAGE),
            "same_repo_family_warning": package.get("same_repo_family_warning"),
        },
        "baseline_reference": {
            "selected_frontier": "stage11507 + encoder_option_retrieval_evidence_judgment_head",
            "selected_residual": "7/10",
            "selected_old_canary_strict": "23/23",
            "selected_filtered_strict": "22/22",
            "verifier_grounded_source_heldout_smoke": "2/3 before support expansion",
        },
        "runtime_initialization": init_card,
        "source_artifacts": {name: rel(path) for name, path in ROWSETS.items()},
        "outputs": {"summary": rel(SUMMARY), "audit_dir": rel(OUT)},
        "claim_boundary": [
            "Stage11882 is not broad source-heldout proof unless source-heldout smoke/heldout gates improve and same-manifest Gemma is attached.",
            "C/C++ support includes same-repo-family google_benchmark roots and cannot be used as source-heldout breadth evidence.",
            "Freeform generation remains outside this bounded-choice scorer audit.",
        ],
    }
    write_json(SUMMARY, summary)
    SUMMARIES.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(SUMMARY, SUMMARIES / f"{NAME}.json")
    print(
        json.dumps(
            {
                "decision": decision,
                "results": {k: {"correct": v["correct"], "rows": v["rows"]} for k, v in results.items()},
                "gates": gates,
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
