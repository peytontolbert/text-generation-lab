#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = 10606
NAME = "stage10606_semantic_output_probe_prefix_inflation_audit"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
SUMMARY_JSON = OUT_DIR / "semantic_output_probe_prefix_inflation_audit.json"
RUN_SUMMARY_JSON = ROOT / "runs/summaries" / f"{NAME}.json"

EXECUTION_RESULT = ROOT / "runs/local/artifacts/stage10605_fresh_python_cpp_mixed_contract_semantic_output_probe/bounded_decoder_probe/execution_result.json"
INTERFACE_AUDIT = ROOT / "runs/local/artifacts/stage10603_fresh_python_cpp_mixed_contract_semantic_output_audit/fresh_python_cpp_mixed_contract_semantic_output_audit.json"
BASELINE_OLD = ROOT / "runs/local/artifacts/stage10594_fresh_python_cpp_mixed_contract_probe/bounded_decoder_probe/execution_result.json"
BASELINE_DIAGNOSTIC = ROOT / "runs/local/artifacts/stage10599_mixed_contract_non_a_diagnostic_probe/bounded_decoder_probe/execution_result.json"


def now_utc() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def display(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def subtype_for_row_id(row_id: str) -> str:
    if "decisive_evidence" in row_id:
        return "decisive_evidence_top1"
    if "retrieve_answer_abstain" in row_id:
        return "retrieve_answer_abstain"
    if "verifier_outcome" in row_id:
        return "verifier_outcome_masked"
    return "unknown"


def main() -> None:
    execution = load_json(EXECUTION_RESULT)
    interface_audit = load_json(INTERFACE_AUDIT)
    baseline_old = load_json(BASELINE_OLD)
    baseline_diag = load_json(BASELINE_DIAGNOSTIC)
    strict = ((execution.get("bounded_choice_eval") or {}).get("strict_eval") or {})
    rows = strict.get("row_cards") or []
    pred_counter = Counter(str(row.get("full_vocab_top1_text") or "") for row in rows)
    constrained_counter = Counter(str(row.get("constrained_choice_top1_label") or "") for row in rows)
    by_subtype: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        by_subtype[subtype_for_row_id(str(row.get("row_id") or ""))].append(row)

    per_subtype = {}
    for subtype, bucket in sorted(by_subtype.items()):
        rows_n = len(bucket)
        full_acc = sum(1 for row in bucket if row.get("full_vocab_top1_match")) / rows_n if rows_n else None
        constrained_acc = sum(1 for row in bucket if row.get("constrained_choice_match")) / rows_n if rows_n else None
        top1_pred = Counter(str(row.get("full_vocab_top1_text") or "") for row in bucket).most_common(1)
        per_subtype[subtype] = {
            "rows": rows_n,
            "full_vocab_top1_accuracy": full_acc,
            "constrained_choice_top1_accuracy": constrained_acc,
            "dominant_full_vocab_prediction": top1_pred[0][0] if top1_pred else None,
            "dominant_full_vocab_prediction_fraction": (top1_pred[0][1] / rows_n) if top1_pred and rows_n else None,
        }

    payload = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": True,
        "inputs": {
            "execution_result": display(EXECUTION_RESULT),
            "interface_audit": display(INTERFACE_AUDIT),
            "baseline_old": display(BASELINE_OLD),
            "baseline_diagnostic": display(BASELINE_DIAGNOSTIC),
        },
        "claim_scope": [
            "Audits whether the stage10605 semantic-output probe created a genuine sequence-generation improvement or only a first-token metric illusion.",
            "Compares full-vocab first-token accuracy with constrained-choice accuracy and dominant predicted token patterns.",
            "This is an anti-cheat metric audit, not a benchmark promotion artifact.",
        ],
        "current_state": {
            "stage10605_full_vocab_top1_accuracy": strict.get("full_vocab_top1_accuracy"),
            "stage10605_constrained_choice_top1_accuracy": strict.get("constrained_choice_top1_accuracy"),
            "stage10605_rows_with_target_rank_1": strict.get("rows_with_target_rank_1"),
            "stage10605_rows": strict.get("rows"),
            "stage10594_full_vocab_top1_accuracy": (((baseline_old.get("bounded_choice_eval") or {}).get("strict_eval") or {}).get("full_vocab_top1_accuracy")),
            "stage10599_full_vocab_top1_accuracy": (((baseline_diag.get("bounded_choice_eval") or {}).get("strict_eval") or {}).get("full_vocab_top1_accuracy")),
            "semantic_decoder_equals_label_rows": ((interface_audit.get("strict_eval") or {}).get("decoder_equals_label_rows")),
        },
        "dominant_predictions": {
            "full_vocab": pred_counter.most_common(10),
            "constrained_choice": constrained_counter.most_common(10),
        },
        "per_subtype": per_subtype,
        "anti_cheat_findings": [
            "If full_vocab predicts one token for nearly every row while constrained_choice remains much lower, the semantic-output headline is inflated by first-token overlap rather than true sequence generation.",
            "Retrieve rows beginning with ANSWER_WITH_RETRIEVED_EVIDENCE are especially vulnerable because a constant token A can count as a full-vocab top1 match under first-token scoring.",
            "Promotion should rely on constrained-choice accuracy plus exact sequence generation, not first-token full-vocab accuracy, for multi-token semantic outputs.",
        ],
        "truthful_read": [
            "Stage10605 materially changed the metric surface, but it did not solve the fresh mixed-contract task in a trustworthy way.",
            "The model predicted the same first token for every strict row, so the apparent full-vocab gain over stage10594/stage10599 is not a real maintainer capability gain.",
            "The correct next metric change is exact semantic-output sequence scoring or semantic constrained scoring, not promotion of the current first-token result.",
        ],
        "outputs": {
            "audit_json": display(SUMMARY_JSON),
        },
    }
    write_json(SUMMARY_JSON, payload)
    write_json(RUN_SUMMARY_JSON, payload)
    print(json.dumps({
        "stage": STAGE,
        "full_vocab_top1_accuracy": payload["current_state"]["stage10605_full_vocab_top1_accuracy"],
        "constrained_choice_top1_accuracy": payload["current_state"]["stage10605_constrained_choice_top1_accuracy"],
        "dominant_full_vocab_prediction": payload["dominant_predictions"]["full_vocab"][0] if payload["dominant_predictions"]["full_vocab"] else None,
    }, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
