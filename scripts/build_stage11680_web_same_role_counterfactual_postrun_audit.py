#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import json
import shutil
import time
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
BASE_PATH = ROOT / "scripts/build_stage11656_same_root_grouped_head_only_postrun_audit.py"
spec = importlib.util.spec_from_file_location("stage11656_base", BASE_PATH)
if spec is None or spec.loader is None:
    raise RuntimeError(f"failed to load base audit helpers: {BASE_PATH}")
base = importlib.util.module_from_spec(spec)
spec.loader.exec_module(base)

ART = ROOT / "runs/local/artifacts"
SUMMARIES = ROOT / "runs/summaries"
NAME = "stage11680_web_same_role_counterfactual_postrun_audit"
OUT = ART / NAME
SUMMARY = OUT / "web_same_role_counterfactual_postrun_audit.json"

RUNTIME = ART / "stage11679_web_same_role_counterfactual_probe/runtime_model/runtime_model_bundle.json"
TRAIN_LOG = ART / "stage11679_web_same_role_counterfactual_probe/bounded_decoder_probe/loss_by_step.jsonl"
ROWSETS = {
    "canonical_train_support": ART / "stage11663_web_canonical_renderer_package/web_canonical_train_support.jsonl",
    "same_role_counterfactual_train": ART / "stage11678_web_remaining_miss_counterfactual_builder/web_same_role_identity_counterfactual_train.jsonl",
    "sealed_remaining_miss_diagnostics": ART / "stage11678_web_remaining_miss_counterfactual_builder/web_remaining_canonical_miss_sealed_diagnostics.jsonl",
    "canonical_heldout": ART / "stage11663_web_canonical_renderer_package/web_canonical_heldout.jsonl",
    "original_web_heldout": ART / "stage11548_web_root_heldout_stage11507_score_audit/web_root_heldout_rows.jsonl",
    "web_successor_strict": ART / "stage11597_web_answerable_no_abstain_geometry_audit/web_answerable_no_abstain_successor_strict_rows.jsonl",
    "residual_bank": ART / "stage11442_targeted_residual_role_support_package/semantic_candidate_residual_bank.jsonl",
    "filtered_strict": ART / "stage11442_targeted_residual_role_support_package/agentkernel_lite_encdec_strict_eval.jsonl",
    "old_canary_strict": ART / "stage11429_selected_test_rust_support_package/agentkernel_lite_encdec_strict_eval.jsonl",
    "filtered_validation": ART / "stage11442_targeted_residual_role_support_package/agentkernel_lite_encdec_validation.jsonl",
    "old_canary_validation": ART / "stage11429_selected_test_rust_support_package/agentkernel_lite_encdec_validation.jsonl",
}
WEB_SCORER = "encoder_option_retrieval_web_task_candidate_head"
PROTECTED_SCORER = "encoder_option_retrieval_evidence_judgment_head"
SCORER_BY_ROWSET = {
    "canonical_train_support": WEB_SCORER,
    "same_role_counterfactual_train": WEB_SCORER,
    "sealed_remaining_miss_diagnostics": WEB_SCORER,
    "canonical_heldout": WEB_SCORER,
    "original_web_heldout": WEB_SCORER,
    "web_successor_strict": WEB_SCORER,
    "residual_bank": PROTECTED_SCORER,
    "filtered_strict": PROTECTED_SCORER,
    "old_canary_strict": PROTECTED_SCORER,
    "filtered_validation": PROTECTED_SCORER,
    "old_canary_validation": PROTECTED_SCORER,
}


def now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def load_runtime() -> tuple[Any, Any, dict[str, Any], dict[str, Any]]:
    old_runtime = base.RUNTIME
    try:
        base.RUNTIME = RUNTIME
        return base.load_runtime()
    finally:
        base.RUNTIME = old_runtime


def _merge_counts(dst: dict[str, int], src: dict[str, Any]) -> None:
    for key, value in src.items():
        dst[str(key)] = dst.get(str(key), 0) + int(value)


def _summarize_card(rows: list[dict[str, Any]], card_key: str) -> dict[str, Any]:
    applicable = 0
    skipped = 0
    steps_with_applicable = 0
    target_rank1 = 0
    target_values: dict[str, int] = {}
    families: dict[str, int] = {}
    candidate_set_sizes: dict[str, int] = {}
    for row in rows:
        card = row.get(card_key) or {}
        app = int(card.get("applicable_rows") or 0)
        skip = int(card.get("skipped_rows") or 0)
        applicable += app
        skipped += skip
        if app:
            steps_with_applicable += 1
        target_rank1 += int(card.get("target_rank1_rows") or 0)
        _merge_counts(target_values, card.get("target_values") or {})
        _merge_counts(families, card.get("families") or {})
        _merge_counts(candidate_set_sizes, card.get("candidate_set_sizes") or {})
    return {
        "applicable_rows_total": applicable,
        "skipped_rows_total": skipped,
        "steps_with_applicable": steps_with_applicable,
        "target_rank1_rows_total": target_rank1,
        "target_rank1_rate": (target_rank1 / applicable) if applicable else None,
        "target_values": target_values,
        "families": families,
        "candidate_set_sizes": candidate_set_sizes,
    }


def training_objective_summary() -> dict[str, Any]:
    rows = [json.loads(line) for line in TRAIN_LOG.read_text(encoding="utf-8").splitlines() if line.strip()] if TRAIN_LOG.exists() else []
    contrast_applicable = 0
    contrast_skipped = 0
    contrast_steps = 0
    for row in rows:
        card = row.get("bounded_choice_contrast_card") or {}
        app = int(card.get("applicable_rows") or 0)
        contrast_applicable += app
        contrast_skipped += int(card.get("skipped_rows") or 0)
        if app:
            contrast_steps += 1
    return {
        "train_log_exists": TRAIN_LOG.exists(),
        "steps": len(rows),
        "latest_step": rows[-1].get("step") if rows else None,
        "contrast": {
            "applicable_rows_total": contrast_applicable,
            "skipped_rows_total": contrast_skipped,
            "steps_with_applicable": contrast_steps,
            "inactive": contrast_applicable == 0 and contrast_skipped > 0,
        },
        "verifier_value_listwise": _summarize_card(rows, "bounded_choice_verifier_value_listwise_card"),
        "same_role_listwise": _summarize_card(rows, "bounded_choice_same_role_listwise_card"),
    }


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    rowsets = {name: [base.normalize_row(row) for row in base.load_jsonl(path)] for name, path in ROWSETS.items()}
    model, tokenizer, init_card, bundle = load_runtime()
    results: dict[str, Any] = {}
    for name, rows in rowsets.items():
        scorer = SCORER_BY_ROWSET[name]
        card = base._write_bounded_choice_eval_audit(
            OUT,
            model=model,
            rows=rows,
            tokenizer=tokenizer,
            max_encoder_tokens=768,
            max_decoder_tokens=16,
            split_name=f"{name}__{scorer}",
            bounded_choice_aux_source=scorer,
            eval_batch_size=8,
        )
        results[name] = {**base.metric(card), "scorer": scorer}

    gates = {
        "canonical_heldout_beats_stage11673_51_of_66": (results["canonical_heldout"]["correct"] or 0) > 51
        and results["canonical_heldout"]["rows"] == 66,
        "canonical_heldout_beats_gemma_52_of_66": (results["canonical_heldout"]["correct"] or 0) > 52
        and results["canonical_heldout"]["rows"] == 66,
        "original_web_heldout_beats_routed_38_of_66": (results["original_web_heldout"]["correct"] or 0) > 38
        and results["original_web_heldout"]["rows"] == 66,
        "original_web_heldout_beats_gemma_52_of_66": (results["original_web_heldout"]["correct"] or 0) > 52
        and results["original_web_heldout"]["rows"] == 66,
        "sealed_remaining_miss_diagnostics_above_stage11676_0_of_15": (results["sealed_remaining_miss_diagnostics"]["correct"] or 0) > 0
        and results["sealed_remaining_miss_diagnostics"]["rows"] == 15,
        "filtered_strict_22_of_22": results["filtered_strict"]["correct"] == 22 and results["filtered_strict"]["rows"] == 22,
        "old_canary_strict_23_of_23": results["old_canary_strict"]["correct"] == 23 and results["old_canary_strict"]["rows"] == 23,
        "filtered_validation_at_least_20_of_22": (results["filtered_validation"]["correct"] or 0) >= 20
        and results["filtered_validation"]["rows"] == 22,
        "old_canary_validation_at_least_21_of_23": (results["old_canary_validation"]["correct"] or 0) >= 21
        and results["old_canary_validation"]["rows"] == 23,
        "residual_at_least_7_of_10": (results["residual_bank"]["correct"] or 0) >= 7 and results["residual_bank"]["rows"] == 10,
    }
    preservation_keys = [
        "filtered_strict_22_of_22",
        "old_canary_strict_23_of_23",
        "filtered_validation_at_least_20_of_22",
        "old_canary_validation_at_least_21_of_23",
        "residual_at_least_7_of_10",
    ]
    preservation_ok = all(gates[key] for key in preservation_keys)
    if not preservation_ok:
        decision = "same_role_counterfactual_rejected_protected_gate_regression"
    elif gates["original_web_heldout_beats_routed_38_of_66"]:
        decision = "same_role_counterfactual_candidate_web_frontier_gain"
    elif gates["canonical_heldout_beats_stage11673_51_of_66"]:
        decision = "same_role_counterfactual_canonical_gain_only"
    elif gates["sealed_remaining_miss_diagnostics_above_stage11676_0_of_15"]:
        decision = "same_role_counterfactual_moves_sealed_misses_only"
    else:
        decision = "same_role_counterfactual_no_frontier_gain"
    summary = {
        "stage": 11680,
        "stage_name": NAME,
        "created_at_utc": now(),
        "decision": decision,
        "runtime": rel(RUNTIME),
        "runtime_weights_sha256": bundle.get("weights_sha256"),
        "device": str(base.DEVICE),
        "results": results,
        "gates": gates,
        "preservation_ok": preservation_ok,
        "training_objective_summary": training_objective_summary(),
        "baseline_reference": {
            "stage11673_canonical_heldout": "51/66",
            "stage11676_canonical_heldout": "51/66",
            "stage11676_original_web_heldout": "28/66",
            "routed_product_web_gate": ">38/66",
            "gemma_web": "52/66",
            "selected_residual": "7/10",
        },
        "runtime_initialization": init_card,
        "source_artifacts": {name: rel(path) for name, path in ROWSETS.items()},
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
                "compact": {key: {"correct": value["correct"], "rows": value["rows"], "scorer": value["scorer"]} for key, value in results.items()},
                "training": summary["training_objective_summary"],
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
