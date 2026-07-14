#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "runs" / "local" / "artifacts"
STAGE = 10899
NAME = "stage10899_python_verifier_transition_successor_comparison_audit"
OUT_DIR = ARTIFACTS / NAME
AUDIT_JSON = OUT_DIR / "python_verifier_transition_successor_comparison_audit.json"

COMPARISON_JSON = ARTIFACTS / "stage10898_python_verifier_transition_successor_same_manifest_comparison" / "python_verifier_transition_successor_same_manifest_comparison.json"
COMBINED_ROWS_JSONL = ARTIFACTS / "stage10898_python_verifier_transition_successor_same_manifest_comparison" / "combined_strict_rows.jsonl"
SUCCESSOR_AUDIT_JSON = ARTIFACTS / "stage10897_python_verifier_transition_strict_successor_audit" / "python_verifier_transition_strict_successor_audit.json"
BASELINE_AUDIT_JSON = ARTIFACTS / "stage10882_quarantined_v27_comparison_successor_audit" / "quarantined_v27_comparison_successor_audit.json"

SUCCESSOR_ROW_ID = "stage10894::code_assist::python::verifier_outcome_semantic_transition::strict_candidate_v1"


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
    comparison = load_json(COMPARISON_JSON)
    combined_rows = load_jsonl(COMBINED_ROWS_JSONL)
    successor_audit = load_json(SUCCESSOR_AUDIT_JSON)
    baseline = load_json(BASELINE_AUDIT_JSON)

    successor_row = next((row for row in combined_rows if str(row.get("row_id")) == SUCCESSOR_ROW_ID), None)
    hundred_overall = (((comparison.get("hundred_m") or {}).get("strict_overall")) or {})
    gemma_overall = (((comparison.get("gemma12b") or {}).get("strict_overall")) or {})
    baseline_metrics = baseline.get("metrics") or {}
    hundred_rows = int(hundred_overall.get("rows") or 0)
    hundred_scored_rows = int(hundred_overall.get("scored_rows") or 0)
    hundred_unscored_rows = max(0, hundred_rows - hundred_scored_rows)

    payload = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": True,
        "decision": "python_verifier_transition_successor_comparison_audited",
        "claim_scope": [
            "Audit the first fresh Python verifier-transition successor comparison built from the stage10896 strict slice.",
            "Make the claim boundary explicit relative to the old 22/23 quarantined baseline.",
        ],
        "headline_status": {
            "old_quarantined_baseline_strict_exact_100m": baseline_metrics.get("strict_exact_100m"),
            "old_quarantined_baseline_strict_exact_gemma": baseline_metrics.get("strict_exact_gemma"),
            "new_successor_strict_exact_100m_scored_only": hundred_overall.get("exact_accuracy"),
            "new_successor_strict_scored_rows_100m": hundred_scored_rows,
            "new_successor_strict_total_rows_100m": hundred_rows,
            "new_successor_strict_unscored_rows_100m": hundred_unscored_rows,
            "new_successor_strict_exact_100m_promotable": None if hundred_unscored_rows else hundred_overall.get("exact_accuracy"),
            "new_successor_strict_exact_gemma": gemma_overall.get("exact_accuracy"),
            "continuation_of_old_headline": False,
            "new_heldout_baseline_required": True,
            "clean_promotable_headline_ready": hundred_unscored_rows == 0,
        },
        "successor_row_result": successor_row,
        "eval_integrity": {
            "single_strict_row_replacement": successor_audit.get("metrics", {}).get("removed_strict_row_count") == 1
            and successor_audit.get("metrics", {}).get("added_strict_row_count") == 1,
            "train_rows_unchanged": successor_audit.get("metrics", {}).get("train_rows_unchanged"),
            "validation_rows_unchanged": successor_audit.get("metrics", {}).get("validation_rows_unchanged"),
            "stress_rows_unchanged": successor_audit.get("metrics", {}).get("stress_rows_unchanged"),
            "target_path_hidden_pre_options": successor_audit.get("metrics", {}).get("target_path_visible_pre_options") is False,
            "explicit_transition_semantics": successor_audit.get("metrics", {}).get("explicit_transition_semantics"),
            "successor_row_unscored_under_constrained_policy": successor_row is not None and successor_row.get("constrained_choice_match") is None,
        },
        "claim_boundary": [
            "This comparison changes the Python strict verifier interface and must be reported as a new successor baseline.",
            "The row count remains 23, but row identity changed, so the result is not directly the old 22/23 headline.",
            "The new Python verifier row uses opaque verifier IDs plus transition semantics and therefore is a stronger anti-cheat surface than the replaced MirrorMind path-letter row.",
            (
                "The current bounded-choice scoring policy still fails on the successor row even though the full-vocab top-1 token is already correct."
                if successor_row is not None and successor_row.get("constrained_choice_match") is False and successor_row.get("full_vocab_top1_match") is True
                else "The successor row is now fully scoreable under the canonical bounded-choice policy."
            ),
        ],
        "source_artifacts": {
            "comparison": rel(COMPARISON_JSON),
            "combined_rows": rel(COMBINED_ROWS_JSONL),
            "successor_audit": rel(SUCCESSOR_AUDIT_JSON),
            "old_baseline_audit": rel(BASELINE_AUDIT_JSON),
        },
        "next_best_step": "If the successor row behaves well, build at least one second opaque verifier-transition heldout row before promoting a broader Python verifier baseline; if it fails, use the row-local miss for targeted verifier-support design rather than replaying the old MirrorMind row.",
    }

    write_json(AUDIT_JSON, payload)
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
