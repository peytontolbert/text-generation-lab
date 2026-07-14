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
STAGE = 11661
NAME = "stage11661_web_schema_aligned_bridge_postrun_audit"
OUT = ART / NAME
SUMMARY = OUT / "web_schema_aligned_bridge_postrun_audit.json"

RUNTIME = ART / "stage11660_web_schema_aligned_bridge_head_only_probe/runtime_model/runtime_model_bundle.json"
ROWSETS = {
    "schema_aligned_bridge_train_support": ART / "stage11659_web_schema_aligned_bridge_package/web_schema_aligned_bridge_manifest.jsonl",
    "web_heldout": ART / "stage11548_web_root_heldout_stage11507_score_audit/web_root_heldout_rows.jsonl",
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
    "schema_aligned_bridge_train_support": WEB_SCORER,
    "web_heldout": WEB_SCORER,
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
        "schema_aligned_train_support_at_least_80_of_113": (results["schema_aligned_bridge_train_support"]["correct"] or 0) >= 80
        and results["schema_aligned_bridge_train_support"]["rows"] == 113,
        "schema_aligned_train_support_at_least_100_of_113": (results["schema_aligned_bridge_train_support"]["correct"] or 0) >= 100
        and results["schema_aligned_bridge_train_support"]["rows"] == 113,
        "filtered_strict_22_of_22": results["filtered_strict"]["correct"] == 22 and results["filtered_strict"]["rows"] == 22,
        "old_canary_strict_23_of_23": results["old_canary_strict"]["correct"] == 23 and results["old_canary_strict"]["rows"] == 23,
        "filtered_validation_at_least_20_of_22": (results["filtered_validation"]["correct"] or 0) >= 20
        and results["filtered_validation"]["rows"] == 22,
        "old_canary_validation_at_least_21_of_23": (results["old_canary_validation"]["correct"] or 0) >= 21
        and results["old_canary_validation"]["rows"] == 23,
        "residual_at_least_7_of_10": (results["residual_bank"]["correct"] or 0) >= 7 and results["residual_bank"]["rows"] == 10,
        "web_heldout_beats_stage11657_4_of_66": (results["web_heldout"]["correct"] or 0) > 4 and results["web_heldout"]["rows"] == 66,
        "web_heldout_beats_routed_38_of_66": (results["web_heldout"]["correct"] or 0) > 38 and results["web_heldout"]["rows"] == 66,
        "web_heldout_beats_gemma_52_of_66": (results["web_heldout"]["correct"] or 0) > 52 and results["web_heldout"]["rows"] == 66,
        "web_successor_at_least_30_of_36": (results["web_successor_strict"]["correct"] or 0) >= 30
        and results["web_successor_strict"]["rows"] == 36,
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
        decision = "schema_aligned_bridge_rejected_protected_gate_regression"
    elif gates["web_heldout_beats_routed_38_of_66"]:
        decision = "schema_aligned_bridge_improves_web_but_remains_diagnostic"
    elif gates["web_heldout_beats_stage11657_4_of_66"]:
        decision = "schema_aligned_bridge_improves_over_bad_head_only_baseline_but_not_frontier"
    elif gates["schema_aligned_train_support_at_least_80_of_113"]:
        decision = "schema_aligned_bridge_support_fit_without_heldout_gain"
    else:
        decision = "schema_aligned_bridge_no_support_or_heldout_gain"

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
        "baseline_reference": {
            "selected_frontier": "stage11507 + encoder_option_retrieval_evidence_judgment_head",
            "routed_product_web": "38/66",
            "gemma_web": "52/66",
            "stage11657_old_schema_head_only_web": "4/66",
            "selected_residual": "7/10",
        },
        "runtime_initialization": init_card,
        "source_artifacts": {name: rel(path) for name, path in ROWSETS.items()},
        "outputs": {"summary": rel(SUMMARY), "audit_dir": rel(OUT)},
        "claim_boundary": [
            "Stage11660 is a head-only diagnostic on schema-aligned bridge support rows.",
            "A Web heldout score below 39/66 is not frontier progress.",
            "Protected gates are routed through the selected Stage11507 evidence-judgment scorer.",
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
                "compact": {key: {"correct": value["correct"], "rows": value["rows"], "scorer": value["scorer"]} for key, value in results.items()},
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
