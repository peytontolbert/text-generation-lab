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
STAGE = 11676
NAME = "stage11676_web_canonical_same_role_listwise_postrun_audit"
OUT = ART / NAME
SUMMARY = OUT / "web_canonical_same_role_listwise_postrun_audit.json"

RUNTIME = ART / "stage11675_web_canonical_same_role_listwise_probe/runtime_model/runtime_model_bundle.json"
TRAIN_LOG = ART / "stage11675_web_canonical_same_role_listwise_probe/bounded_decoder_probe/loss_by_step.jsonl"
ROWSETS = {
    "canonical_train_support": ART / "stage11663_web_canonical_renderer_package/web_canonical_train_support.jsonl",
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
    if not TRAIN_LOG.exists():
        return {"train_log_exists": False}
    rows = [json.loads(line) for line in TRAIN_LOG.read_text(encoding="utf-8").splitlines() if line.strip()]
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
    verifier_value = _summarize_card(rows, "bounded_choice_verifier_value_listwise_card")
    same_role = _summarize_card(rows, "bounded_choice_same_role_listwise_card")
    return {
        "train_log_exists": True,
        "steps": len(rows),
        "latest_step": rows[-1].get("step") if rows else None,
        "contrast": {
            "applicable_rows_total": contrast_applicable,
            "skipped_rows_total": contrast_skipped,
            "steps_with_applicable": contrast_steps,
            "inactive": contrast_applicable == 0 and contrast_skipped > 0,
        },
        "verifier_value_listwise": verifier_value,
        "same_role_listwise": same_role,
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
        "canonical_train_support_at_least_300_of_334": (results["canonical_train_support"]["correct"] or 0) >= 300
        and results["canonical_train_support"]["rows"] == 334,
        "canonical_train_support_at_least_320_of_334": (results["canonical_train_support"]["correct"] or 0) >= 320
        and results["canonical_train_support"]["rows"] == 334,
        "canonical_heldout_beats_stage11673_51_of_66": (results["canonical_heldout"]["correct"] or 0) > 51
        and results["canonical_heldout"]["rows"] == 66,
        "canonical_heldout_beats_gemma_52_of_66": (results["canonical_heldout"]["correct"] or 0) > 52
        and results["canonical_heldout"]["rows"] == 66,
        "original_web_heldout_beats_routed_38_of_66": (results["original_web_heldout"]["correct"] or 0) > 38
        and results["original_web_heldout"]["rows"] == 66,
        "original_web_heldout_beats_gemma_52_of_66": (results["original_web_heldout"]["correct"] or 0) > 52
        and results["original_web_heldout"]["rows"] == 66,
        "web_successor_at_least_30_of_36": (results["web_successor_strict"]["correct"] or 0) >= 30
        and results["web_successor_strict"]["rows"] == 36,
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
        decision = "web_canonical_same_role_listwise_rejected_protected_gate_regression"
    elif gates["original_web_heldout_beats_gemma_52_of_66"]:
        decision = "web_canonical_same_role_listwise_beats_original_web_gemma_but_requires_external_validation"
    elif gates["original_web_heldout_beats_routed_38_of_66"]:
        decision = "web_canonical_same_role_listwise_improves_original_web_heldout"
    elif gates["canonical_heldout_beats_gemma_52_of_66"]:
        decision = "web_canonical_same_role_listwise_beats_canonical_gemma_threshold"
    elif gates["canonical_heldout_beats_stage11673_51_of_66"]:
        decision = "web_canonical_same_role_listwise_improves_canonical_heldout_only"
    elif gates["canonical_train_support_at_least_300_of_334"]:
        decision = "web_canonical_same_role_listwise_support_fit_without_frontier_gain"
    else:
        decision = "web_canonical_same_role_listwise_no_support_or_heldout_gain"

    training = training_objective_summary()
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now(),
        "decision": decision,
        "runtime": rel(RUNTIME),
        "runtime_weights_sha256": bundle.get("weights_sha256"),
        "device": str(base.DEVICE),
        "scorer_by_rowset": SCORER_BY_ROWSET,
        "results": results,
        "gates": gates,
        "preservation_ok": preservation_ok,
        "training_objective_summary": training,
        "baseline_reference": {
            "selected_frontier": "stage11507 + encoder_option_retrieval_evidence_judgment_head",
            "routed_product_web": "38/66",
            "gemma_web": "52/66",
            "stage11665_canonical_no_active_contrast_canonical_heldout": "50/66",
            "stage11665_canonical_no_active_contrast_original_web": "28/66",
            "stage11673_verifier_value_listwise_canonical_heldout": "51/66",
            "stage11673_verifier_value_listwise_original_web": "27/66",
            "selected_residual": "7/10",
        },
        "runtime_initialization": init_card,
        "source_artifacts": {name: rel(path) for name, path in ROWSETS.items()},
        "outputs": {"summary": rel(SUMMARY), "audit_dir": rel(OUT)},
        "claim_boundary": [
            "Stage11675 is a head-only diagnostic on canonical-rendered Web rows with verifier-value and generic same-role listwise losses.",
            "Canonical heldout improvement alone proves same-renderer learning, not old Web-surface transfer.",
            "Original Web heldout must beat 38/66 before this is Web frontier progress.",
            "Protected gates are routed through the selected Stage11507 evidence-judgment scorer.",
            "If same_role_listwise has low applicable coverage, the same-role candidate identity objective is still underexercised by the sampler.",
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
                "training": training,
                "compact": {key: {"correct": value["correct"], "rows": value["rows"], "scorer": value["scorer"]} for key, value in results.items()},
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
