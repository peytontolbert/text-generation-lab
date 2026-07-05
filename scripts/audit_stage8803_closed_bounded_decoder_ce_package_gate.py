#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STAGE = 8803
NAME = "stage8803_closed_bounded_decoder_ce_package_gate_audit"
MANIFEST = ROOT / "runs/local/artifacts/stage8802_closed_bounded_decoder_ce_package_gate/closed_bounded_decoder_ce_package_gate_manifest.jsonl"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "CLOSED_BOUNDED_DECODER_CE_PACKAGE_GATE_AUDIT_STAGE8803.md"
AUTHORITY_CLOSED = {
    "model_execution_authorized_next": False,
    "decoder_ce_training_authorized_next": False,
    "denoise_ce_training_authorized_next": False,
    "runtime_authorized": False,
    "source_emission_authorized": False,
    "body_emission_authorized": False,
    "gemma_execution_authorized_next": False,
    "harness_execution_authorized_next": False,
    "scoring_authorized_next": False,
    "controller_complete_merge_authorized_next": False,
    "promotion_ready": False,
}
REQUIRED_GATES = [
    "source_inventory_lineage", "source_provenance", "contamination_leakage_detector",
    "golden_locked_eval_suite", "drift_canary_regression_monitor",
    "cluster_slice_near_duplicate_detector", "dataset_junk_ood_ranker_v1", "schema_drift_detector",
]


def rows() -> list[dict]:
    return [json.loads(line) for line in MANIFEST.read_text(encoding="utf-8").splitlines() if line.strip()]


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    data = rows()
    gate_counts = Counter(row["clean_state"]["ce_gate_decision"] for row in data)
    split_counts = Counter(row.get("split") for row in data)
    authority_rows = [row["row_id"] for row in data if any((row.get("authority") or {}).values())]
    loss_rows = [row["row_id"] for row in data if any((row.get("loss_mask") or {}).values())]
    incomplete_gates = [row["row_id"] for row in data if not all((row.get("gate_status") or {}).get(k) is True for k in REQUIRED_GATES)]
    raw_rows = [row["row_id"] for row in data if any((row.get("anti_cheat") or {}).get(k) for k in ["raw_source_included", "raw_decoder_text_included", "raw_patch_body_included", "target_text_in_encoder", "target_label_in_id", "source_row_id_in_model_input"])]
    eligible_now = [row["row_id"] for row in data if row["clean_state"].get("decoder_ce_eligible_now") is True]
    arg_candidate_without_materialization_block = [row["row_id"] for row in data if row["clean_state"]["ce_gate_decision"] == "CE_CANDIDATE_NEEDS_SOURCE_BACKED_TARGET_TEXT" and "target_text_not_materialized" not in row.get("hard_blockers", [])]
    failures = []
    expected = {
        "CE_CANDIDATE_NEEDS_SOURCE_BACKED_TARGET_TEXT": 360,
        "CE_BLOCK_LONG_OUTPUT_UNDER_CURRENT_DECODER_BUDGET": 72,
        "CE_BLOCK_RETRIEVE_MORE_BEFORE_DECODING": 72,
    }
    if len(data) != 504:
        failures.append("row_count_changed")
    for key, value in expected.items():
        if gate_counts.get(key) != value:
            failures.append(f"gate_count_mismatch:{key}")
    if split_counts != Counter({"train": 168, "eval": 168, "strict": 168}):
        failures.append("split_balance_changed")
    if authority_rows:
        failures.append("authority_rows_nonzero")
    if loss_rows:
        failures.append("loss_mask_rows_nonzero")
    if incomplete_gates:
        failures.append("incomplete_gate_rows")
    if raw_rows:
        failures.append("raw_or_target_visible_rows")
    if eligible_now:
        failures.append("eligible_now_rows_nonzero")
    if arg_candidate_without_materialization_block:
        failures.append("candidate_missing_materialization_block")
    metrics = {
        **AUTHORITY_CLOSED,
        "rows": len(data),
        "gate_decision_counts": dict(sorted(gate_counts.items())),
        "split_counts": dict(sorted(split_counts.items())),
        "authority_rows": len(authority_rows),
        "loss_mask_rows": len(loss_rows),
        "incomplete_gate_rows": len(incomplete_gates),
        "raw_or_target_visible_rows": len(raw_rows),
        "decoder_ce_eligible_now_rows": len(eligible_now),
        "candidate_missing_materialization_block_rows": len(arg_candidate_without_materialization_block),
        "failures": failures,
    }
    card = {
        "stage": STAGE,
        "stage_name": NAME,
        "passed": not failures,
        "authority": AUTHORITY_CLOSED,
        "metrics": metrics,
        "artifacts": {
            "audited_manifest": str(MANIFEST.relative_to(ROOT)),
            "audit_card": str((OUT_DIR / "closed_bounded_decoder_ce_package_gate_audit_card.json").relative_to(ROOT)),
            "audit_script": "scripts/audit_stage8803_closed_bounded_decoder_ce_package_gate.py",
        },
        "decision": "Closed bounded decoder CE package gate passed; CE remains blocked pending source-backed target materialization and explicit authorization." if not failures else "Closed bounded decoder CE package gate audit failed.",
        "next_best_step": "Attach the closed CE gate to the central graph, then recover source-backed target materialization controls before any CE reopen discussion.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    (OUT_DIR / "closed_bounded_decoder_ce_package_gate_audit_card.json").write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    SUMMARY.write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage8803 Closed Bounded Decoder CE Package Gate Audit",
        "",
        f"Passed: `{card['passed']}`",
        "",
        f"Rows: `{metrics['rows']}`",
        f"Authority rows: `{metrics['authority_rows']}`",
        f"Loss-mask rows: `{metrics['loss_mask_rows']}`",
        f"Incomplete gate rows: `{metrics['incomplete_gate_rows']}`",
        f"Decoder CE eligible now rows: `{metrics['decoder_ce_eligible_now_rows']}`",
        "",
        "CE remains blocked pending source-backed target materialization and an explicit future authorization stage.",
        "",
    ]), encoding="utf-8")
    print(json.dumps(card, indent=2, sort_keys=True))
    raise SystemExit(0 if card["passed"] else 1)

if __name__ == "__main__":
    main()
