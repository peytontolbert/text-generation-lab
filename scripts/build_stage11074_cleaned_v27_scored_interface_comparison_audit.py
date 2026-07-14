#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
import time
from collections import defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.bounded_choice_policy import choose_bounded_choice_label, policy_correct, policy_for_row


ARTIFACTS = ROOT / "runs" / "local" / "artifacts"
STAGE = 11074
NAME = "stage11074_cleaned_v27_scored_interface_comparison_audit"
OUT_DIR = ARTIFACTS / NAME
OUT_JSON = OUT_DIR / "cleaned_v27_scored_interface_comparison_audit.json"
OUT_ROWS = OUT_DIR / "cleaned_v27_scored_interface_rows.jsonl"

SCORING_CONTRACT = ARTIFACTS / "stage11073_cleaned_v27_scored_interface_contract_refresh" / "cleaned_v27_scored_interface_contract_refresh.json"
CLEANED_STRICT_ROWS = ARTIFACTS / "stage11065_singleton_eval_quarantine_package" / "agentkernel_lite_encdec_strict_eval.jsonl"
CURRENT_STRICT_AUDIT = ARTIFACTS / "stage11071_a_prior_and_python_verifier_diagnostic_probe" / "bounded_decoder_probe" / "bounded_choice_eval_audit_strict_eval.json"
COMBINED_SUCCESSOR_ROWS = ARTIFACTS / "stage10898_python_verifier_transition_successor_same_manifest_comparison" / "combined_strict_rows.jsonl"
POSTRUN_AUDIT = ARTIFACTS / "stage11072_a_prior_and_python_verifier_diagnostic_postrun_audit" / "a_prior_and_python_verifier_diagnostic_postrun_audit.json"


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def now_utc() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def metric(correct: int, rows: int) -> dict[str, Any]:
    return {
        "correct": correct,
        "rows": rows,
        "exact_accuracy": (correct / rows) if rows else None,
    }


def verdict(hundred_correct: int, gemma_correct: int, rows: int) -> str:
    if rows == 0:
        return "no_rows"
    if hundred_correct > gemma_correct:
        return "100m_better"
    if hundred_correct < gemma_correct:
        return "gemma_better"
    return "tie"


def by_group(rows: list[dict[str, Any]], key: str, result_key: str) -> dict[str, Any]:
    buckets: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        buckets[str(row.get(key) or "unknown")].append(row)
    out = {}
    for bucket_key, bucket_rows in sorted(buckets.items()):
        hundred_correct = sum(1 for row in bucket_rows if bool(row.get(result_key)))
        gemma_correct = sum(1 for row in bucket_rows if bool(row.get("gemma12b_correct")))
        out[bucket_key] = metric(hundred_correct, len(bucket_rows))
        out[bucket_key]["verdict"] = verdict(hundred_correct, gemma_correct, len(bucket_rows))
    return out


def main() -> None:
    contract = load_json(SCORING_CONTRACT)
    cleaned_rows = load_jsonl(CLEANED_STRICT_ROWS)
    current_strict = load_json(CURRENT_STRICT_AUDIT)
    combined_rows = load_jsonl(COMBINED_SUCCESSOR_ROWS)
    postrun = load_json(POSTRUN_AUDIT)

    default_policy = ((contract.get("approved_scoring_contract") or {}).get("default_policy")) or "current_retrieval"
    overrides = ((contract.get("approved_scoring_contract") or {}).get("task_policy_overrides")) or {}

    allowed_ids = {str(row.get("row_id") or "") for row in cleaned_rows}
    current_by_id = {
        str(row.get("row_id") or ""): row
        for row in list(current_strict.get("row_cards") or [])
        if str(row.get("row_id") or "") in allowed_ids
    }

    scored_rows = []
    changed_rows = []
    raw_rows = []

    for combined in combined_rows:
        row_id = str(combined.get("row_id") or "")
        if row_id not in allowed_ids:
            continue
        current = current_by_id.get(row_id)
        if current is None:
            continue
        merged = dict(combined)
        merged.update(
            {
                "split": "strict_eval_cleaned",
                "bounded_choice_target_label": current.get("bounded_choice_target_label"),
                "constrained_choice_match": current.get("constrained_choice_match"),
                "constrained_choice_top1_label": current.get("constrained_choice_top1_label"),
                "full_vocab_top1_match": current.get("full_vocab_top1_match"),
                "full_vocab_top1_text": current.get("full_vocab_top1_text"),
                "full_vocab_top1_token_id": current.get("full_vocab_top1_token_id"),
                "target_rank_full_vocab": current.get("target_rank_full_vocab"),
                "target_text": current.get("target_text"),
                "target_token_id": current.get("target_token_id"),
            }
        )
        raw_correct = bool(current.get("constrained_choice_match"))
        merged["raw_constrained_correct"] = raw_correct

        policy_name = policy_for_row(row=merged, default_policy=default_policy, override_by_task=overrides)
        contract_pred = choose_bounded_choice_label(
            row=merged,
            constrained_label=str(merged.get("constrained_choice_top1_label") or "") or None,
            decoder_label=str(merged.get("full_vocab_top1_text") or "") or None,
            policy=policy_name,
        )
        contract_correct = policy_correct(target_label=str(merged.get("target_text") or ""), predicted_label=contract_pred)
        merged["contract_policy"] = policy_name
        merged["contract_predicted_label"] = contract_pred
        merged["contract_correct"] = contract_correct
        scored_rows.append(merged)
        raw_rows.append(merged)
        if contract_pred != merged.get("constrained_choice_top1_label"):
            changed_rows.append(
                {
                    "row_id": row_id,
                    "task_type": merged.get("task_type"),
                    "language_family": merged.get("language_family"),
                    "before": merged.get("constrained_choice_top1_label"),
                    "after": contract_pred,
                    "target": merged.get("target_text"),
                    "decoder_top1": merged.get("full_vocab_top1_text"),
                }
            )

    write_jsonl(OUT_ROWS, scored_rows)

    rows = len(scored_rows)
    raw_correct = sum(1 for row in raw_rows if bool(row.get("raw_constrained_correct")))
    contract_correct_total = sum(1 for row in scored_rows if bool(row.get("contract_correct")))
    gemma_correct = sum(1 for row in scored_rows if bool(row.get("gemma12b_correct")))

    payload = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": True,
        "decision": "cleaned_v27_scored_interface_comparison_audited",
        "claim_scope": [
            "Audit the cleaned 22-row reviewed-v2.7 strict canary under the refreshed scored-interface contract.",
            "Report raw constrained-retrieval and policy-assisted results separately on the same cleaned same-manifest standalone surface.",
        ],
        "source_artifacts": {
            "scoring_contract": rel(SCORING_CONTRACT),
            "cleaned_strict_rows": rel(CLEANED_STRICT_ROWS),
            "current_strict_audit": rel(CURRENT_STRICT_AUDIT),
            "combined_successor_rows": rel(COMBINED_SUCCESSOR_ROWS),
            "current_postrun_audit": rel(POSTRUN_AUDIT),
        },
        "headline": {
            "raw_cleaned_strict_exact_100m": raw_correct / rows if rows else None,
            "policy_cleaned_strict_exact_100m": contract_correct_total / rows if rows else None,
            "strict_exact_gemma": gemma_correct / rows if rows else None,
            "raw_delta_100m_minus_gemma": (raw_correct - gemma_correct) / rows if rows else None,
            "policy_delta_100m_minus_gemma": (contract_correct_total - gemma_correct) / rows if rows else None,
            "rows": rows,
            "language_wins_100m_under_policy": sum(1 for block in by_group(scored_rows, "language_family", "contract_correct").values() if block["verdict"] == "100m_better"),
            "language_wins_gemma_under_policy": sum(1 for block in by_group(scored_rows, "language_family", "contract_correct").values() if block["verdict"] == "gemma_better"),
            "language_ties_under_policy": sum(1 for block in by_group(scored_rows, "language_family", "contract_correct").values() if block["verdict"] == "tie"),
        },
        "comparison": {
            "hundred_m_raw_constrained": metric(raw_correct, rows),
            "hundred_m_under_contract": metric(contract_correct_total, rows),
            "gemma12b": metric(gemma_correct, rows),
            "by_language": by_group(scored_rows, "language_family", "contract_correct"),
            "by_task_type": by_group(scored_rows, "task_type", "contract_correct"),
            "by_selected_test_anchor": by_group(scored_rows, "selected_test_anchor", "contract_correct"),
            "by_verifier_anchor": by_group(scored_rows, "verifier_anchor", "contract_correct"),
        },
        "contract_effect": {
            "default_policy": default_policy,
            "task_policy_overrides": overrides,
            "rows_changed_by_contract": len(changed_rows),
            "changed_rows": changed_rows,
            "raw_cleaned_strict_miss_rows": ((postrun.get("cleaned_canary_result") or {}).get("strict_miss_rows")),
        },
        "claim_boundaries": [
            "The policy-assisted score uses the frozen verifier-transition override and must not be reported as raw constrained retrieval.",
            "This remains a standalone same-manifest comparison on the cleaned 22-row canary.",
            "No evidence-role scorer override or explicit-ledger A-prior relief is included here.",
        ],
        "findings": [
            "The cleaned surface now isolates the single surviving strict miss to a semantic-transition verifier row with correct decoder top-1 token.",
            "If the policy-assisted score improves, that gain comes from inference-side scored-interface alignment rather than a new training breakthrough.",
            "The cleaned canary remains the honest regression surface while broader evidence-row and web-source problems stay outside this contract.",
        ],
        "outputs": {
            "rows_jsonl": rel(OUT_ROWS),
            "summary_json": rel(OUT_JSON),
        },
    }
    write_json(OUT_JSON, payload)
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
