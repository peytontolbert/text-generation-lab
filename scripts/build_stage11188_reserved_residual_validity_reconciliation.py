#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "runs/local/artifacts"
OUT_DIR = ARTIFACTS / "stage11188_reserved_residual_validity_reconciliation"
SUMMARY_JSON = OUT_DIR / "reserved_residual_validity_reconciliation.json"
CLEAN_ROWS = OUT_DIR / "clean_reserved_residual_rows.jsonl"
QUARANTINED_ROWS = OUT_DIR / "quarantined_reserved_residual_rows.jsonl"
REPLACEMENT_QUEUE = OUT_DIR / "reserved_residual_replacement_requirements.jsonl"

RESERVED_ROWS = ARTIFACTS / "stage11051_successor_residual_support_plus_priority_evidence/reserved_residual_candidates.jsonl"
QUALITY_CARDS = ARTIFACTS / "stage11174_evidence_gate_and_quality_audit/evidence_quality_row_cards.jsonl"
LATEST_POSTRUN = ARTIFACTS / "stage11187_contract_evidence_ledger_head_postrun_audit/contract_evidence_ledger_head_postrun_audit.json"
QUALITY_SUMMARY = ARTIFACTS / "stage11174_evidence_gate_and_quality_audit/evidence_gate_and_quality_audit.json"


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


def row_gold_value(row: dict[str, Any]) -> str:
    return str((row.get("standalone_projection_source") or {}).get("gold_value") or "")


def replacement_requirement(row: dict[str, Any], reasons: list[str]) -> dict[str, Any]:
    gold = row_gold_value(row)
    role = gold or "same_role_as_quarantined_row"
    return {
        "blocked_row_id": row.get("row_id"),
        "language_family": row.get("language_family"),
        "repo_family": row.get("repo_family"),
        "task_type": row.get("task_type"),
        "target_gold_value": role,
        "quarantine_reasons": reasons,
        "replacement_contract": [
            "Use a root-disjoint source not already present in train/validation/strict/reserved rows.",
            "Expose distinct evidence spans for candidate surface, verifier/test constraint, and symptom/call-path roles.",
            "If verifier_and_test_constraint is gold, include selected test, verifier route, assertion, command, or transition fact.",
            "If symptom_or_call_path_analogue is gold, do not duplicate the candidate changed-file path as the only support.",
            "Do not expose the target label or target role before options.",
            "Require deterministic option shuffle and machine-readable opaque_options/gold_value.",
        ],
        "recommended_source": "stage11177 or newer root-disjoint long-context retrieval source with concrete query_text/support_scores",
    }


def quality_reasons(card: dict[str, Any] | None, unsafe_summary_ids: set[str], row_id: str) -> list[str]:
    if not card:
        if row_id in unsafe_summary_ids:
            return ["listed unsafe in stage11174 summary but missing row card"]
        return []
    reasons: list[str] = []
    if bool(card.get("needs_rewrite_or_quarantine")):
        reasons.append("needs_rewrite_or_quarantine")
    if bool(card.get("duplicated_gold_path")):
        reasons.append("duplicated_gold_path")
    if bool(card.get("role_conflict_candidate_vs_verifier")):
        reasons.append("role_conflict_candidate_vs_verifier")
    if bool(card.get("verifier_gold_with_no_selected_test")):
        reasons.append("verifier_gold_with_no_selected_test")
    if card.get("duplicate_paths"):
        reasons.append("duplicate_role_paths")
    if card.get("verifier_conflict_patterns"):
        patterns = ", ".join(str(item) for item in card.get("verifier_conflict_patterns") or [])
        if patterns:
            reasons.append(f"verifier_conflict_patterns: {patterns}")
    if row_id in unsafe_summary_ids and not reasons:
        reasons.append("listed unsafe in stage11174 summary")
    return reasons


def main() -> None:
    reserved = load_jsonl(RESERVED_ROWS)
    quality_cards = load_jsonl(QUALITY_CARDS)
    postrun = load_json(LATEST_POSTRUN) if LATEST_POSTRUN.exists() else {}
    quality_summary = load_json(QUALITY_SUMMARY) if QUALITY_SUMMARY.exists() else {}
    unsafe_summary_ids = set(
        str(row_id)
        for row_id in ((quality_summary.get("quality_audit") or {}).get("unsafe_row_ids") or [])
    )
    quality_by_id = {str(card.get("row_id") or ""): card for card in quality_cards}

    clean: list[dict[str, Any]] = []
    quarantined: list[dict[str, Any]] = []
    replacements: list[dict[str, Any]] = []
    for row in reserved:
        if row.get("task_type") != "evidence_citation":
            clean.append(row)
            continue
        row_id = str(row.get("row_id") or "")
        card = quality_by_id.get(row_id)
        reasons = quality_reasons(card, unsafe_summary_ids, row_id)
        if reasons:
            enriched = dict(row)
            enriched["quarantine_card"] = {
                "source_stage": 11174,
                "reasons": reasons,
                "quality_card": card,
            }
            quarantined.append(enriched)
            replacements.append(replacement_requirement(row, reasons))
        else:
            clean.append(row)

    clean_evidence = [row for row in clean if row.get("task_type") == "evidence_citation"]
    quarantined_evidence = [row for row in quarantined if row.get("task_type") == "evidence_citation"]
    latest_product = postrun.get("productized_scorer_result") or {}
    latest_reserved = latest_product.get("reserved_residual") or {}
    latest_evidence = latest_product.get("reserved_evidence") or {}

    summary = {
        "stage": 11188,
        "created_at_utc": now_utc(),
        "decision": "reserved_bank_needs_replacement_before_more_training"
        if quarantined_evidence
        else "reserved_bank_clean",
        "source_artifacts": {
            "reserved_rows": rel(RESERVED_ROWS),
            "quality_cards": rel(QUALITY_CARDS),
            "latest_postrun": rel(LATEST_POSTRUN) if LATEST_POSTRUN.exists() else None,
        },
        "counts": {
            "reserved_rows_total": len(reserved),
            "clean_reserved_rows": len(clean),
            "quarantined_reserved_rows": len(quarantined),
            "reserved_evidence_rows_total": sum(1 for row in reserved if row.get("task_type") == "evidence_citation"),
            "clean_reserved_evidence_rows": len(clean_evidence),
            "quarantined_reserved_evidence_rows": len(quarantined_evidence),
        },
        "quarantined_by_language": dict(sorted(Counter(str(row.get("language_family") or "missing") for row in quarantined).items())),
        "quarantined_by_repo": dict(sorted(Counter(str(row.get("repo_family") or "missing") for row in quarantined).items())),
        "quarantined_by_gold_value": dict(sorted(Counter(row_gold_value(row) or "missing" for row in quarantined).items())),
        "latest_reserved_scores_are_not_promotable": {
            "latest_reserved_residual_accuracy": latest_reserved.get("exact_accuracy"),
            "latest_reserved_evidence_accuracy": latest_evidence.get("exact_accuracy"),
            "reason": "The evidence residual denominator includes rows quarantined by the stage11174 quality audit.",
        },
        "next_required_work": [
            "Retire quarantined evidence rows from the residual promotion gate.",
            "Materialize replacement rows from fresh root-disjoint evidence sources before any new evidence-training claim.",
            "Keep clean strict 22/22 as the standalone canary, but do not use the old reserved evidence 4/9 as a capability target without this quarantine note.",
        ],
        "outputs": {
            "summary_json": rel(SUMMARY_JSON),
            "clean_rows": rel(CLEAN_ROWS),
            "quarantined_rows": rel(QUARANTINED_ROWS),
            "replacement_queue": rel(REPLACEMENT_QUEUE),
        },
    }
    write_jsonl(CLEAN_ROWS, clean)
    write_jsonl(QUARANTINED_ROWS, quarantined)
    write_jsonl(REPLACEMENT_QUEUE, replacements)
    write_json(SUMMARY_JSON, summary)
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
