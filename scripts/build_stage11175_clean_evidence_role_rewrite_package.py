#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "runs" / "local" / "artifacts"
STAGE = 11175
NAME = "stage11175_clean_evidence_role_rewrite_package"
OUT_DIR = ARTIFACTS / NAME
SUMMARY_JSON = OUT_DIR / "clean_evidence_role_rewrite_package.json"
SAFE_ROWS_JSONL = OUT_DIR / "safe_evidence_rows.jsonl"
BLOCKED_ROWS_JSONL = OUT_DIR / "blocked_evidence_rewrite_queue.jsonl"
CONTRACT_JSON = OUT_DIR / "evidence_role_admission_contract.json"

QUALITY_AUDIT = ARTIFACTS / "stage11174_evidence_gate_and_quality_audit" / "evidence_gate_and_quality_audit.json"
QUALITY_CARDS = ARTIFACTS / "stage11174_evidence_gate_and_quality_audit" / "evidence_quality_row_cards.jsonl"
ROW_SOURCES = {
    "clean_strict": ARTIFACTS / "stage11146_singleton_strict_quarantine_successor" / "agentkernel_lite_encdec_strict_eval.jsonl",
    "clean_validation": ARTIFACTS / "stage11146_singleton_strict_quarantine_successor" / "agentkernel_lite_encdec_validation.jsonl",
    "reserved_residual": ARTIFACTS / "stage11051_successor_residual_support_plus_priority_evidence" / "reserved_residual_candidates.jsonl",
}


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()] if path.exists() else []


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


def row_by_id() -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for split, path in ROW_SOURCES.items():
        for row in load_jsonl(path):
            row_id = str(row.get("row_id") or "")
            if row_id:
                enriched = dict(row)
                enriched["_source_split"] = split
                out[row_id] = enriched
    return out


def rewrite_actions(card: dict[str, Any]) -> list[str]:
    actions: list[str] = []
    if card.get("role_conflict_candidate_vs_verifier"):
        actions.append(
            "Rewrite verifier_and_test_constraint so it contains independent selected-test/verifier evidence, not prose that says the candidate surface directly exposes/includes the answer."
        )
        actions.append(
            "Keep candidate_change_surface positive controls, but make the verifier option a true competing verifier fact rather than another argument for the same candidate surface."
        )
    if card.get("duplicated_gold_path"):
        actions.append(
            "Replace duplicated role spans: candidate_change_surface, symptom_or_call_path_analogue, and background roles must not reuse the same path/text span when the task requires role discrimination."
        )
        actions.append(
            "If only one real source span is available, mark the row ambiguous/abstain or quarantine instead of forcing a singleton evidence-role label."
        )
    if card.get("verifier_gold_with_no_selected_test"):
        actions.append(
            "Do not use verifier_and_test_constraint as gold when the verifier block says no selected test is recorded or evidence is insufficient."
        )
    if not actions:
        actions.append("No rewrite required by stage11174 quality gates.")
    return actions


def main() -> None:
    quality = load_json(QUALITY_AUDIT)
    cards = load_jsonl(QUALITY_CARDS)
    rows = row_by_id()
    safe_cards = [card for card in cards if not card.get("needs_rewrite_or_quarantine")]
    blocked_cards = [card for card in cards if card.get("needs_rewrite_or_quarantine")]

    safe_rows: list[dict[str, Any]] = []
    for card in safe_cards:
        row = dict(rows.get(card["row_id"], {}))
        row["stage11175_evidence_quality"] = {
            "status": "safe_for_reference_only",
            "source_split": card["split"],
            "gold_value": card["gold_value"],
            "note": "These rows passed the evidence-role quality gate, but existing heldout/reserved rows must not be recycled into train support.",
        }
        safe_rows.append(row)

    blocked_rows: list[dict[str, Any]] = []
    for card in blocked_cards:
        row = dict(rows.get(card["row_id"], {}))
        blocked_rows.append(
            {
                "row_id": card["row_id"],
                "language_family": card["language_family"],
                "repo_family": card["repo_family"],
                "source_split": card["split"],
                "gold_value": card["gold_value"],
                "blocked_reasons": {
                    "role_conflict_candidate_vs_verifier": bool(card.get("role_conflict_candidate_vs_verifier")),
                    "duplicated_gold_path": bool(card.get("duplicated_gold_path")),
                    "verifier_gold_with_no_selected_test": bool(card.get("verifier_gold_with_no_selected_test")),
                },
                "duplicate_paths": card.get("duplicate_paths") or {},
                "verifier_conflict_patterns": card.get("verifier_conflict_patterns") or [],
                "rewrite_actions": rewrite_actions(card),
                "original_row_available": bool(row),
                "original_source_root_id": row.get("source_root_id"),
                "original_selected_test_anchor": row.get("selected_test_anchor"),
                "original_verifier_anchor": row.get("verifier_anchor"),
                "target_text": row.get("target_text"),
                "target_option_value": card.get("gold_value"),
            }
        )

    contract = {
        "stage": STAGE,
        "contract_name": "evidence_role_admission_contract_v1",
        "required_for_train_or_eval": [
            "Every evidence role option must correspond to a distinct visible fact, span, or ledger entry.",
            "candidate_change_surface and symptom_or_call_path_analogue may share a file only if their text spans/facts are materially different and the row asks for that distinction explicitly.",
            "verifier_and_test_constraint must expose an actual selected test, verifier result, assertion, command, or transition fact; it must not merely restate that the candidate surface is visible.",
            "Rows with no selected test or insufficient verifier evidence must not force verifier_and_test_constraint as singleton gold.",
            "Rows where multiple roles are equally supported must become abstain/set-valued rows or remain quarantined.",
            "Heldout/reserved rows that fail this gate cannot be used as train support; replacements must come from root-disjoint source material."
        ],
        "reject_if": [
            "same_path_same_text_under_multiple_roles",
            "verifier_text_argues_for_candidate_surface_when_candidate_surface_is_gold",
            "gold_role_absent_from_visible_evidence",
            "gold_verifier_role_without_selected_test_or_verifier_anchor",
            "option_label_or_order_is_needed_to_solve_the_row",
        ],
    }

    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": True,
        "decision": "evidence_role_rewrite_package_ready_no_training_yet",
        "source_artifacts": {
            "quality_audit": rel(QUALITY_AUDIT),
            "quality_cards": rel(QUALITY_CARDS),
            "row_sources": {split: rel(path) for split, path in ROW_SOURCES.items()},
        },
        "counts": {
            "audited_evidence_rows": len(cards),
            "safe_reference_rows": len(safe_rows),
            "blocked_rewrite_rows": len(blocked_rows),
            "trainable_now": 0,
            "why_trainable_now_zero": "All audited rows are strict/validation/reserved heldout surfaces or blocked rewrite rows; they should guide materialization but not be recycled into train support.",
        },
        "blocked_by_language": dict(sorted(__import__("collections").Counter(row["language_family"] for row in blocked_rows).items())),
        "blocked_by_reason": {
            "role_conflict_candidate_vs_verifier": sum(1 for row in blocked_rows if row["blocked_reasons"]["role_conflict_candidate_vs_verifier"]),
            "duplicated_gold_path": sum(1 for row in blocked_rows if row["blocked_reasons"]["duplicated_gold_path"]),
            "verifier_gold_with_no_selected_test": sum(1 for row in blocked_rows if row["blocked_reasons"]["verifier_gold_with_no_selected_test"]),
        },
        "contract": contract,
        "next_best_step": "Materialize fresh root-disjoint evidence-role rows satisfying evidence_role_admission_contract_v1, with balanced candidate_change_surface, verifier_and_test_constraint, and symptom_or_call_path_analogue positives; then train/evaluate a semantic evidence scorer objective.",
        "outputs": {
            "summary_json": rel(SUMMARY_JSON),
            "safe_rows_jsonl": rel(SAFE_ROWS_JSONL),
            "blocked_rows_jsonl": rel(BLOCKED_ROWS_JSONL),
            "contract_json": rel(CONTRACT_JSON),
        },
    }
    write_json(SUMMARY_JSON, summary)
    write_json(CONTRACT_JSON, contract)
    write_jsonl(SAFE_ROWS_JSONL, safe_rows)
    write_jsonl(BLOCKED_ROWS_JSONL, blocked_rows)
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
