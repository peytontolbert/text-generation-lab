#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "runs" / "local" / "artifacts"
STAGE = 11051
NAME = "stage11051_successor_residual_support_plus_priority_evidence"
OUT_DIR = ARTIFACTS / NAME
SUMMARY_JSON = OUT_DIR / "successor_residual_support_plus_priority_evidence.json"
TRAIN_JSONL = OUT_DIR / "agentkernel_lite_encdec_train.jsonl"
VALIDATION_JSONL = OUT_DIR / "agentkernel_lite_encdec_validation.jsonl"
STRICT_JSONL = OUT_DIR / "agentkernel_lite_encdec_strict_eval.jsonl"
STRESS_JSONL = OUT_DIR / "agentkernel_lite_encdec_stress_eval.jsonl"
ADDED_PRIORITY_ROWS_JSONL = OUT_DIR / "added_priority_evidence_support_rows.jsonl"
RESERVED_CANDIDATES_JSONL = OUT_DIR / "reserved_residual_candidates.jsonl"

BASE_DIR = ARTIFACTS / "stage11035_successor_residual_support_package"
BASE_SUMMARY = BASE_DIR / "successor_residual_support_package.json"
BASE_TRAIN = BASE_DIR / "agentkernel_lite_encdec_train.jsonl"
BASE_VALIDATION = BASE_DIR / "agentkernel_lite_encdec_validation.jsonl"
BASE_STRICT = BASE_DIR / "agentkernel_lite_encdec_strict_eval.jsonl"
BASE_STRESS = BASE_DIR / "agentkernel_lite_encdec_stress_eval.jsonl"
BASE_RESERVED = BASE_DIR / "reserved_residual_candidates.jsonl"

PRIORITY_DIR = ARTIFACTS / "stage11045_priority_evidence_bounded_candidate_conversion"
PRIORITY_SUMMARY = PRIORITY_DIR / "priority_evidence_bounded_candidate_conversion.json"
PRIORITY_ROWS = PRIORITY_DIR / "bounded_candidate_rows.jsonl"

PRIORITY_AUDIT = ARTIFACTS / "stage11046_priority_evidence_bounded_candidate_audit" / "priority_evidence_bounded_candidate_audit.json"
PRIORITY_RUNTIME_AUDIT = ARTIFACTS / "stage11047_priority_evidence_candidate_runtime_audit" / "priority_evidence_candidate_runtime_audit.json"
PRIORITY_POLICY = ARTIFACTS / "stage11050_priority_evidence_policy_decision" / "priority_evidence_policy_decision.json"


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
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


def count_by(rows: list[dict[str, Any]], key: str) -> dict[str, int]:
    return dict(sorted(Counter(str(row.get(key) or "missing") for row in rows).items()))


def normalize_train_support_row(row: dict[str, Any]) -> dict[str, Any]:
    updated = dict(row)
    updated["split"] = "train"
    updated["train_support_only"] = True
    updated["strict_eval_eligible"] = False
    updated["disable_losses"] = []
    updated["loss_mask"] = {"decoder_ce": True}
    updated["successor_residual_stage"] = STAGE
    updated["successor_residual_branch"] = True
    updated["priority_evidence_support"] = True
    anti_cheat = dict(updated.get("anti_cheat") or {})
    anti_cheat["successor_residual_branch"] = True
    anti_cheat["priority_evidence_support"] = True
    anti_cheat["same_surface_eval_admissible"] = False
    updated["anti_cheat"] = anti_cheat
    return updated


def main() -> None:
    base_summary = load_json(BASE_SUMMARY)
    priority_summary = load_json(PRIORITY_SUMMARY)
    priority_audit = load_json(PRIORITY_AUDIT)
    priority_runtime_audit = load_json(PRIORITY_RUNTIME_AUDIT)
    priority_policy = load_json(PRIORITY_POLICY)

    base_train = load_jsonl(BASE_TRAIN)
    validation_rows = load_jsonl(BASE_VALIDATION)
    strict_rows = load_jsonl(BASE_STRICT)
    stress_rows = load_jsonl(BASE_STRESS)
    reserved_candidates = load_jsonl(BASE_RESERVED)
    priority_rows = load_jsonl(PRIORITY_ROWS)

    base_ids = {str(row.get("row_id") or "") for row in base_train}
    added_priority_rows: list[dict[str, Any]] = []
    for row in priority_rows:
        row_id = str(row.get("row_id") or "")
        if row_id in base_ids:
            continue
        added_priority_rows.append(normalize_train_support_row(row))

    train_rows = [*base_train, *added_priority_rows]

    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": True,
        "decision": "successor_residual_support_plus_priority_evidence_ready",
        "claim_scope": [
            "Extend the stage11035 successor residual package with the five anti-cheat-clean stage11045 bounded evidence rows as train support only.",
            "Keep the 23-row successor validation/strict overlay and the current global scoring source unchanged.",
            "Preserve the older reserved residual bank as heldout candidate material while moving the new priority evidence slice into explicit support status.",
        ],
        "source_artifacts": {
            "base_support_package": rel(BASE_SUMMARY),
            "priority_evidence_rows": rel(PRIORITY_ROWS),
            "priority_evidence_summary": rel(PRIORITY_SUMMARY),
            "priority_evidence_audit": rel(PRIORITY_AUDIT),
            "priority_runtime_audit": rel(PRIORITY_RUNTIME_AUDIT),
            "priority_policy_decision": rel(PRIORITY_POLICY),
        },
        "metrics": {
            "train_rows_before": len(base_train),
            "train_rows_after": len(train_rows),
            "added_priority_evidence_rows": len(added_priority_rows),
            "added_priority_rows_by_language": count_by(added_priority_rows, "language_family"),
            "added_priority_rows_by_repo_family": count_by(added_priority_rows, "repo_family"),
            "added_priority_rows_by_target": count_by(added_priority_rows, "decoder_text"),
            "added_priority_rows_by_task": count_by(added_priority_rows, "task_type"),
            "validation_rows": len(validation_rows),
            "strict_rows": len(strict_rows),
            "stress_rows": len(stress_rows),
            "reserved_candidates_retained": len(reserved_candidates),
            "priority_slice_runtime_accuracy": priority_runtime_audit.get("metrics", {}).get("overall", {}).get("exact_accuracy"),
            "priority_slice_rows_with_target_rank_1": priority_runtime_audit.get("metrics", {}).get("rows_with_target_rank_1"),
            "base_train_rows_after_stage11035": base_summary.get("metrics", {}).get("train_rows_after"),
        },
        "findings": [
            "The five stage11045 rows are now explicit support rows, not candidate-only limbo.",
            "The row geometry directly attacks the evidence-role failure where verifier-and-test constraint should beat candidate-change-surface.",
            "This keeps the safer encoder_option_retrieval overlay scorer while giving the model a clean training path for the new slice.",
        ],
        "limits": [
            "These five rows are no longer usable as an independent heldout slice after training on them.",
            "The package still does not add fresh Rust replenishment or promotable web roots.",
            "This branch remains residual diagnostic work unless the reserved bank or successor overlay materially improve.",
        ],
        "required_honesty_gates": [
            "Keep the 23-row successor overlay scored with encoder_option_retrieval.",
            "Do not report postrun gains on the five added stage11045 rows as heldout generalization; they are train support.",
            "Reserved candidate reporting must stay separate from the successor overlay and from the newly added priority evidence support rows.",
        ],
        "next_best_step": "Run one bounded probe from the stage11037 runtime using this package, then report successor validation/strict and the still-untrained reserved candidate bank separately.",
        "outputs": {
            "summary_json": rel(SUMMARY_JSON),
            "train_rows_jsonl": rel(TRAIN_JSONL),
            "validation_rows_jsonl": rel(VALIDATION_JSONL),
            "strict_rows_jsonl": rel(STRICT_JSONL),
            "stress_rows_jsonl": rel(STRESS_JSONL),
            "added_priority_rows_jsonl": rel(ADDED_PRIORITY_ROWS_JSONL),
            "reserved_candidates_jsonl": rel(RESERVED_CANDIDATES_JSONL),
        },
    }

    write_json(SUMMARY_JSON, summary)
    write_jsonl(TRAIN_JSONL, train_rows)
    write_jsonl(VALIDATION_JSONL, validation_rows)
    write_jsonl(STRICT_JSONL, strict_rows)
    write_jsonl(STRESS_JSONL, stress_rows)
    write_jsonl(ADDED_PRIORITY_ROWS_JSONL, added_priority_rows)
    write_jsonl(RESERVED_CANDIDATES_JSONL, reserved_candidates)
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
