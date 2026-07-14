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
STAGE = 11657
NAME = "stage11657_same_root_grouped_head_only_routed_audit"
OUT = ART / NAME
SUMMARY = OUT / "same_root_grouped_head_only_routed_audit.json"

WEB_SCORER = "encoder_option_retrieval_web_task_candidate_head"
PROTECTED_SCORER = "encoder_option_retrieval_evidence_judgment_head"
SCORER_BY_ROWSET = {
    "grouped_web_gap_train_support": WEB_SCORER,
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


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    rowsets = {name: [base.normalize_row(row) for row in base.load_jsonl(path)] for name, path in base.ROWSETS.items()}
    model, tokenizer, init_card, bundle = base.load_runtime()
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
        "grouped_train_support_at_least_100_of_113": (results["grouped_web_gap_train_support"]["correct"] or 0) >= 100
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
    preservation_keys = [
        "filtered_strict_22_of_22",
        "old_canary_strict_23_of_23",
        "filtered_validation_at_least_20_of_22",
        "old_canary_validation_at_least_21_of_23",
        "residual_at_least_7_of_10",
    ]
    preservation_ok = all(gates[key] for key in preservation_keys)
    if not preservation_ok:
        decision = "routed_head_only_rejected_protected_gate_regression"
    elif gates["web_heldout_beats_routed_38_of_66"]:
        decision = "routed_head_only_web_improved_but_diagnostic_only"
    elif gates["grouped_train_support_at_least_100_of_113"]:
        decision = "routed_head_only_support_fit_without_web_heldout_gain"
    else:
        decision = "routed_head_only_no_support_or_heldout_gain"

    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now(),
        "decision": decision,
        "runtime": rel(base.RUNTIME),
        "runtime_weights_sha256": bundle.get("weights_sha256"),
        "device": str(base.DEVICE),
        "scorer_by_rowset": SCORER_BY_ROWSET,
        "results": results,
        "gates": gates,
        "baseline_reference": {
            "selected_frontier": "stage11507 + encoder_option_retrieval_evidence_judgment_head",
            "routed_product_web": "38/66",
            "gemma_web": "52/66",
            "selected_residual": "7/10",
        },
        "runtime_initialization": init_card,
        "source_artifacts": {name: rel(path) for name, path in base.ROWSETS.items()},
        "outputs": {"summary": rel(SUMMARY), "audit_dir": rel(OUT)},
        "claim_boundary": [
            "This routed audit uses the Web task candidate head only for Web rowsets.",
            "Protected canary/residual rowsets use the selected evidence-judgment scorer from the Stage11507 frontier.",
            "Stage11655 remains diagnostic because it trained only a bounded-choice Web head and does not prove broad Web generalization.",
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
