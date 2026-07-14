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
NAME = "stage11684_counterfactual_identity_semantic_head_postrun_audit"
OUT = ART / NAME
SUMMARY = OUT / "counterfactual_identity_semantic_head_postrun_audit.json"

RUNTIME = ART / "stage11683_counterfactual_identity_semantic_head_probe/runtime_model/runtime_model_bundle.json"
TRAIN_LOG = ART / "stage11683_counterfactual_identity_semantic_head_probe/bounded_decoder_probe/loss_by_step.jsonl"
ROWSETS = {
    "same_role_counterfactual_train": ART / "stage11678_web_remaining_miss_counterfactual_builder/web_same_role_identity_counterfactual_train.jsonl",
    "sealed_remaining_miss_diagnostics": ART / "stage11678_web_remaining_miss_counterfactual_builder/web_remaining_canonical_miss_sealed_diagnostics.jsonl",
    "canonical_heldout": ART / "stage11663_web_canonical_renderer_package/web_canonical_heldout.jsonl",
    "original_web_heldout": ART / "stage11548_web_root_heldout_stage11507_score_audit/web_root_heldout_rows.jsonl",
    "filtered_strict": ART / "stage11442_targeted_residual_role_support_package/agentkernel_lite_encdec_strict_eval.jsonl",
    "old_canary_strict": ART / "stage11429_selected_test_rust_support_package/agentkernel_lite_encdec_strict_eval.jsonl",
    "filtered_validation": ART / "stage11442_targeted_residual_role_support_package/agentkernel_lite_encdec_validation.jsonl",
    "old_canary_validation": ART / "stage11429_selected_test_rust_support_package/agentkernel_lite_encdec_validation.jsonl",
    "residual_bank": ART / "stage11442_targeted_residual_role_support_package/semantic_candidate_residual_bank.jsonl",
}
SEMANTIC_SCORER = "encoder_option_retrieval_semantic_candidate_head"
PROTECTED_SCORER = "encoder_option_retrieval_evidence_judgment_head"
SCORER_BY_ROWSET = {
    "same_role_counterfactual_train": SEMANTIC_SCORER,
    "sealed_remaining_miss_diagnostics": SEMANTIC_SCORER,
    "canonical_heldout": SEMANTIC_SCORER,
    "original_web_heldout": SEMANTIC_SCORER,
    "filtered_strict": PROTECTED_SCORER,
    "old_canary_strict": PROTECTED_SCORER,
    "filtered_validation": PROTECTED_SCORER,
    "old_canary_validation": PROTECTED_SCORER,
    "residual_bank": PROTECTED_SCORER,
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


def training_summary() -> dict[str, Any]:
    rows = [json.loads(line) for line in TRAIN_LOG.read_text(encoding="utf-8").splitlines() if line.strip()] if TRAIN_LOG.exists() else []
    same_app = same_rank = aux_app = aux_rank = verifier_app = verifier_rank = 0
    for row in rows:
        card = row.get("bounded_choice_aux_card") or {}
        aux_app += int(card.get("applicable_rows") or 0)
        aux_rank += int(card.get("target_rank_1_rows") or 0)
        same = row.get("bounded_choice_same_role_listwise_card") or {}
        same_app += int(same.get("applicable_rows") or 0)
        same_rank += int(same.get("target_rank1_rows") or 0)
        verifier = row.get("bounded_choice_verifier_value_listwise_card") or {}
        verifier_app += int(verifier.get("applicable_rows") or 0)
        verifier_rank += int(verifier.get("target_rank1_rows") or 0)
    return {
        "steps": len(rows),
        "aux_rank1": {"applicable": aux_app, "rank1": aux_rank, "rate": (aux_rank / aux_app) if aux_app else None},
        "same_role_rank1": {"applicable": same_app, "rank1": same_rank, "rate": (same_rank / same_app) if same_app else None},
        "verifier_value_rank1": {"applicable": verifier_app, "rank1": verifier_rank, "rate": (verifier_rank / verifier_app) if verifier_app else None},
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
        "counterfactual_train_fit_at_least_70_of_92": (results["same_role_counterfactual_train"]["correct"] or 0) >= 70,
        "counterfactual_train_fit_at_least_85_of_92": (results["same_role_counterfactual_train"]["correct"] or 0) >= 85,
        "sealed_remaining_miss_diagnostics_above_1_of_15": (results["sealed_remaining_miss_diagnostics"]["correct"] or 0) > 1,
        "canonical_heldout_above_stage11680_43_of_66": (results["canonical_heldout"]["correct"] or 0) > 43,
        "canonical_heldout_above_stage11673_51_of_66": (results["canonical_heldout"]["correct"] or 0) > 51,
        "original_web_above_38_of_66": (results["original_web_heldout"]["correct"] or 0) > 38,
        "protected_filtered_strict_22_of_22": results["filtered_strict"]["correct"] == 22 and results["filtered_strict"]["rows"] == 22,
        "protected_old_strict_23_of_23": results["old_canary_strict"]["correct"] == 23 and results["old_canary_strict"]["rows"] == 23,
        "protected_residual_at_least_7_of_10": (results["residual_bank"]["correct"] or 0) >= 7 and results["residual_bank"]["rows"] == 10,
    }
    if not (gates["protected_filtered_strict_22_of_22"] and gates["protected_old_strict_23_of_23"] and gates["protected_residual_at_least_7_of_10"]):
        decision = "semantic_identity_head_rejected_protected_gate_regression"
    elif gates["counterfactual_train_fit_at_least_70_of_92"]:
        decision = "semantic_identity_head_can_fit_counterfactual_slice"
    else:
        decision = "semantic_identity_head_underfits_counterfactual_slice"
    summary = {
        "stage": 11684,
        "stage_name": NAME,
        "created_at_utc": now(),
        "decision": decision,
        "runtime": rel(RUNTIME),
        "runtime_weights_sha256": bundle.get("weights_sha256"),
        "results": results,
        "gates": gates,
        "training_summary": training_summary(),
        "runtime_initialization": init_card,
        "source_artifacts": {name: rel(path) for name, path in ROWSETS.items()},
        "outputs": {"summary": rel(SUMMARY), "audit_dir": rel(OUT)},
    }
    write_json(SUMMARY, summary)
    SUMMARIES.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(SUMMARY, SUMMARIES / f"{NAME}.json")
    print(json.dumps({"decision": decision, "gates": gates, "compact": {k: {"correct": v["correct"], "rows": v["rows"], "scorer": v["scorer"]} for k, v in results.items()}, "training": summary["training_summary"]}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
