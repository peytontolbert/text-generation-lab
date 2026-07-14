#!/usr/bin/env python3
"""Postrun audit for Stage11887 rendered support probe."""

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
STAGE = 11888
NAME = "stage11888_rendered_support_guarded_postrun_audit"
OUT = ART / NAME
SUMMARY = OUT / "rendered_support_guarded_postrun_audit.json"

RUNTIME = ART / "stage11887_rendered_source_heldout_support_guarded_probe/runtime_model/runtime_model_bundle.json"
PACKAGE = ART / "stage11884_rendered_source_heldout_support_probe_package/rendered_source_heldout_support_probe_package.json"
BASELINE_AUDIT = ART / "stage11885_rendered_support_baseline_delta_audit/rendered_support_baseline_delta_audit.json"
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


def miss_breakdown(rows: list[dict[str, Any]], misses: list[dict[str, Any]]) -> dict[str, Any]:
    by_id = {str(row.get("row_id")): row for row in rows}
    out: dict[str, Any] = {}
    for key in ["language_family", "stage11880_support_source", "task_type", "repo_family"]:
        out[key] = dict(Counter(str(by_id.get(str(m.get("row_id")), {}).get(key)) for m in misses))
    return out


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    package = load_json(PACKAGE)
    baseline = load_json(BASELINE_AUDIT)
    baseline_selected = baseline["results"]["stage11507_selected_frontier"]
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
        "residual_at_least_stage11507_7_of_10": (results["residual_bank"]["correct"] or 0) >= 7 and results["residual_bank"]["rows"] == 10,
        "residual_improves_beyond_stage11507": (results["residual_bank"]["correct"] or 0) > 7 and results["residual_bank"]["rows"] == 10,
        "rendered_support_improves_over_stage11507": (results["rendered_added_support_train"]["correct"] or 0)
        > (baseline_selected["rendered_added_support_train"]["correct"] or 0),
        "rendered_support_at_least_80_of_160": (results["rendered_added_support_train"]["correct"] or 0) >= 80
        and results["rendered_added_support_train"]["rows"] == 160,
        "source_heldout_smoke_not_regressed_6_of_12": (results["verifier_grounded_source_heldout_smoke"]["correct"] or 0)
        >= (baseline_selected["verifier_grounded_source_heldout_smoke"]["correct"] or 0)
        and results["verifier_grounded_source_heldout_smoke"]["rows"] == 12,
        "source_heldout_smoke_improves": (results["verifier_grounded_source_heldout_smoke"]["correct"] or 0)
        > (baseline_selected["verifier_grounded_source_heldout_smoke"]["correct"] or 0)
        and results["verifier_grounded_source_heldout_smoke"]["rows"] == 12,
    }
    preservation = all(
        gates[key]
        for key in [
            "old_canary_strict_23_of_23",
            "filtered_strict_22_of_22",
            "filtered_validation_at_least_20_of_22",
            "old_canary_validation_at_least_21_of_23",
            "residual_at_least_stage11507_7_of_10",
        ]
    )
    if not preservation:
        decision = "reject_stage11887_rendered_support_probe_protected_gate_regression"
    elif gates["residual_improves_beyond_stage11507"] or gates["source_heldout_smoke_improves"]:
        decision = "stage11887_rendered_support_probe_frontier_lift_candidate"
    elif gates["rendered_support_at_least_80_of_160"]:
        decision = "stage11887_rendered_support_fit_without_frontier_lift"
    elif gates["rendered_support_improves_over_stage11507"]:
        decision = "stage11887_partial_rendered_support_fit_diagnostic_only"
    else:
        decision = "stage11887_no_rendered_support_fit_no_frontier_lift"

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
        "baseline_stage11507": {
            name: {
                "correct": metric["correct"],
                "rows": metric["rows"],
                "accuracy": metric["accuracy"],
            }
            for name, metric in baseline_selected.items()
        },
        "rendered_support_miss_breakdown": miss_breakdown(
            rowsets["rendered_added_support_train"], results["rendered_added_support_train"]["misses"]
        ),
        "package": {
            "summary": rel(PACKAGE),
            "renderer_audit": package.get("renderer_audit"),
        },
        "runtime_initialization": init_card,
        "source_artifacts": {name: rel(path) for name, path in ROWSETS.items()},
        "outputs": {"summary": rel(SUMMARY), "audit_dir": rel(OUT)},
        "claim_boundary": [
            "Promotion requires protected gates plus residual/source-heldout improvement; support fit alone is diagnostic.",
            "Rendered support rows are train-support-only and do not establish source-heldout breadth.",
            "Freeform generation is not evaluated here.",
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
