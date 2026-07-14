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
STAGE = 11667
NAME = "stage11667_web_canonical_active_contrast_postrun_audit"
OUT = ART / NAME
SUMMARY = OUT / "web_canonical_active_contrast_postrun_audit.json"

RUNTIME = ART / "stage11666_web_canonical_active_contrast_probe/runtime_model/runtime_model_bundle.json"
TRAIN_LOG = ART / "stage11666_web_canonical_active_contrast_probe/bounded_decoder_probe/loss_by_step.jsonl"
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


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


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


def training_contrast_summary() -> dict[str, Any]:
    if not TRAIN_LOG.exists():
        return {"train_log_exists": False}
    rows = []
    for line in TRAIN_LOG.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    applicable = 0
    skipped = 0
    steps_with_applicable = 0
    for row in rows:
        card = row.get("bounded_choice_contrast_card") or {}
        app = int(card.get("applicable_rows") or 0)
        skip = int(card.get("skipped_rows") or 0)
        applicable += app
        skipped += skip
        if app:
            steps_with_applicable += 1
    return {
        "train_log_exists": True,
        "steps": len(rows),
        "contrast_applicable_rows_total": applicable,
        "contrast_skipped_rows_total": skipped,
        "steps_with_contrast_applicable": steps_with_applicable,
        "contrast_inactive": applicable == 0 and skipped > 0,
        "latest_step": rows[-1].get("step") if rows else None,
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
        "canonical_heldout_beats_routed_38_of_66": (results["canonical_heldout"]["correct"] or 0) > 38
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
        decision = "web_canonical_active_contrast_rejected_protected_gate_regression"
    elif gates["original_web_heldout_beats_gemma_52_of_66"]:
        decision = "web_canonical_active_contrast_beats_original_web_gemma_but_requires_external_validation"
    elif gates["original_web_heldout_beats_routed_38_of_66"]:
        decision = "web_canonical_active_contrast_improves_original_web_heldout"
    elif gates["canonical_heldout_beats_routed_38_of_66"]:
        decision = "web_canonical_active_contrast_improves_canonical_heldout_only"
    elif gates["canonical_train_support_at_least_300_of_334"]:
        decision = "web_canonical_active_contrast_support_fit_without_frontier_gain"
    else:
        decision = "web_canonical_active_contrast_no_support_or_heldout_gain"

    contrast = training_contrast_summary()
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
        "training_contrast_summary": contrast,
        "baseline_reference": {
            "selected_frontier": "stage11507 + encoder_option_retrieval_evidence_judgment_head",
            "routed_product_web": "38/66",
            "gemma_web": "52/66",
            "stage11657_old_schema_head_only_web": "4/66",
            "stage11661_schema_aligned_bridge_web": "17/66",
            "stage11665_canonical_no_active_contrast_canonical_heldout": "50/66",
            "stage11665_canonical_no_active_contrast_original_web": "28/66",
            "selected_residual": "7/10",
        },
        "runtime_initialization": init_card,
        "source_artifacts": {name: rel(path) for name, path in ROWSETS.items()},
        "outputs": {"summary": rel(SUMMARY), "audit_dir": rel(OUT)},
        "claim_boundary": [
            "Stage11666 is a head-only diagnostic on canonical-rendered Web rows with active canonical contrast.",
            "Canonical heldout improvement alone proves same-renderer learning, not old Web-surface transfer.",
            "Original Web heldout must beat 38/66 before this is Web frontier progress.",
            "Protected gates are routed through the selected Stage11507 evidence-judgment scorer.",
            "If contrast_inactive is true, the contrast knobs did not actually train canonical candidate-role margins.",
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
                "contrast": contrast,
                "compact": {key: {"correct": value["correct"], "rows": value["rows"], "scorer": value["scorer"]} for key, value in results.items()},
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
