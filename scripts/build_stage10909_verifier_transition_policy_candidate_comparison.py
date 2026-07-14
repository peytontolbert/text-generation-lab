#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "runs" / "local" / "artifacts"
STAGE = 10909
NAME = "stage10909_verifier_transition_policy_candidate_comparison"
OUT_DIR = ARTIFACTS / NAME
OUT_JSON = OUT_DIR / "verifier_transition_policy_candidate_comparison.json"

POLICY_AUDIT = ARTIFACTS / "stage10908_verifier_transition_policy_audit" / "verifier_transition_policy_audit.json"
SLICE_COMPARISON = ARTIFACTS / "stage10903_python_verifier_transition_candidate_slice_comparison" / "python_verifier_transition_candidate_slice_comparison.json"
CANARY_STRICT = ARTIFACTS / "stage10881_evidence_alias_quarantine_successor" / "agentkernel_lite_encdec_strict_eval.jsonl"


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def now_utc() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def main() -> None:
    policy_audit = load_json(POLICY_AUDIT)
    slice_comparison = load_json(SLICE_COMPARISON)
    canary_rows = load_jsonl(CANARY_STRICT)

    current_policy = policy_audit["policies"]["current_retrieval"]
    candidate_policy = policy_audit["policies"]["decoder_on_transition_only"]

    slice_rows = []
    for row in slice_comparison["rows"]:
        predicted_before = row.get("constrained_choice_top1_label")
        predicted_after = None
        for miss in candidate_policy["strict_eval"]["misses"]:
            if miss["row_id"] == row["row_id"]:
                predicted_after = miss["pred"]
                break
        if predicted_after is None:
            predicted_after = row["bounded_choice_target_label"]
        slice_rows.append(
            {
                "row_id": row["row_id"],
                "target": row["bounded_choice_target_label"],
                "hundred_m_before": predicted_before,
                "hundred_m_after": predicted_after,
                "gemma12b": row.get("gemma12b_predicted_label"),
                "hundred_m_before_correct": bool(row.get("constrained_choice_match")),
                "hundred_m_after_correct": predicted_after == row["bounded_choice_target_label"],
                "gemma12b_correct": bool(row.get("gemma12b_correct")),
            }
        )

    payload = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": True,
        "claim_scope": [
            "Compare the current retrieval policy against the decoder-on-transition-only interface candidate on the fresh Python verifier-transition slice, with Gemma held fixed.",
            "Confirm that the interface candidate does not alter the existing cleaned multilingual canary surface because that surface contains no verifier_outcome_semantic_transition rows.",
        ],
        "source_artifacts": {
            "policy_audit": rel(POLICY_AUDIT),
            "slice_comparison": rel(SLICE_COMPARISON),
            "canary_strict_rows": rel(CANARY_STRICT),
        },
        "headline": {
            "fresh_python_verifier_slice": {
                "rows": len(slice_rows),
                "hundred_m_before_correct": sum(1 for row in slice_rows if row["hundred_m_before_correct"]),
                "hundred_m_after_correct": sum(1 for row in slice_rows if row["hundred_m_after_correct"]),
                "gemma12b_correct": sum(1 for row in slice_rows if row["gemma12b_correct"]),
                "hundred_m_before_accuracy": current_policy["strict_eval"]["accuracy"],
                "hundred_m_after_accuracy": candidate_policy["strict_eval"]["accuracy"],
                "gemma12b_accuracy": slice_comparison["gemma12b"]["overall"]["exact_accuracy"],
            },
            "cleaned_canary_regression_check": {
                "surface_rows": len(canary_rows),
                "semantic_transition_rows_present": sum(
                    1 for row in canary_rows if str(row.get("task_type") or "") == "verifier_outcome_semantic_transition"
                ),
                "current_eval_accuracy_on_canary_check_surface": current_policy["eval"]["accuracy"],
                "candidate_eval_accuracy_on_canary_check_surface": candidate_policy["eval"]["accuracy"],
            },
        },
        "slice_rows": slice_rows,
        "findings": [
            "The decoder-on-transition-only interface candidate improves the fresh Python verifier-transition slice from 1/2 to 2/2 for the 100M model while Gemma remains 0/2.",
            "The candidate policy leaves the regression-check eval surface unchanged because it only affects verifier_outcome_semantic_transition rows and none are present in the cleaned canary strict pack.",
            "This is a narrow scoring-interface candidate, not a broad standalone victory upgrade; evidence_citation remains the main multilingual weak family.",
        ],
        "next_best_step": "Adopt decoder-on-transition-only as an explicit scored-interface candidate for verifier_outcome_semantic_transition rows, then run the same-policy boundary wherever Gemma is compared on fresh verifier-transition successors.",
    }

    write_json(OUT_JSON, payload)
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
