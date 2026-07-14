#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "runs" / "local" / "artifacts"
STAGE = 11057
NAME = "stage11057_explicit_ledger_conflict_replenishment_request"
OUT_DIR = ARTIFACTS / NAME
SUMMARY_JSON = OUT_DIR / "explicit_ledger_conflict_replenishment_request.json"
WORK_ITEMS_JSONL = OUT_DIR / "work_items.jsonl"

AUDIT_11054 = ARTIFACTS / "stage11054_successor_residual_support_plus_priority_postrun_audit" / "successor_residual_support_plus_priority_postrun_audit.json"
AUDIT_11056 = ARTIFACTS / "stage11056_explicit_ledger_gated_scorer_policy_audit" / "explicit_ledger_gated_scorer_policy_audit.json"


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


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


def main() -> None:
    audit11054 = load_json(AUDIT_11054)
    audit11056 = load_json(AUDIT_11056)

    reserved_mismatches = (((audit11054.get("reserved_candidate_result") or {}).get("mismatches")) or [])
    strict_misses = (((audit11054.get("successor_surface_result") or {}).get("strict_miss_rows")) or [])
    validation_misses = (((audit11054.get("successor_surface_result") or {}).get("validation_miss_rows")) or [])

    work_items = [
        {
            "priority": 1,
            "lane": "python_verifier_transition",
            "objective": "Expand verifier-transition roots beyond the single strict successor row.",
            "target_family": "code_assist_hf_local",
            "required_new_roots": 8,
            "required_new_rows": 30,
            "why_now": "The only remaining strict overlay miss is still the Python verifier-transition successor row.",
            "evidence": strict_misses,
            "acceptance_requirements": [
                "Opaque verifier target IDs preserved",
                "No singleton verifier options",
                "Rows represent test_id plus transition semantics",
                "At least two plausible competing FAIL_TO_PASS targets per root",
            ],
        },
        {
            "priority": 2,
            "lane": "evidence_citation_conflict",
            "objective": "Replenish the agentkernel counterfamily evidence rows that role-map still mis-scores.",
            "target_family": "cpp_agentkernel_counterfamily",
            "required_new_roots": 4,
            "required_new_rows": 16,
            "why_now": "This family remains wrong under the explicit-ledger gate and distinguishes a true counterexample to the current evidence scorer.",
            "evidence": [
                row["row_id"] for row in reserved_mismatches
                if str(row.get("repo_family")) == "agentkernel"
            ],
            "acceptance_requirements": [
                "Explicit selected-test ledger preserved",
                "Evidence gold must be supported by packet-visible verifier anchors",
                "Counterfamily examples where candidate_change_surface is tempting but wrong",
            ],
        },
        {
            "priority": 3,
            "lane": "evidence_citation_conflict",
            "objective": "Replenish Python reviewed-next evidence rows where explicit-ledger routing still fails.",
            "target_family": "python_repository_library_reviewed_next",
            "required_new_roots": 4,
            "required_new_rows": 16,
            "why_now": "The explicit-ledger gate fixes the replenishment row but not the reviewed-next Python evidence successor.",
            "evidence": [
                row["row_id"] for row in reserved_mismatches
                if str(row.get("language_family")) == "python"
            ] + [
                row_id for row_id in validation_misses if "::python::evidence_citation::" in row_id
            ],
            "acceptance_requirements": [
                "Fresh roots, not same-row paraphrases",
                "Visible evidence must separate verifier constraint from candidate surface cleanly",
                "Selected tests remain explicit and anti-cheat-clean",
            ],
        },
        {
            "priority": 4,
            "lane": "rust_evidence_citation",
            "objective": "Replace weak Rust explicit-ledger evidence families with fresh non-aliased roots.",
            "target_family": "rust_non_tokenizers_non_alias",
            "required_new_roots": 6,
            "required_new_rows": 24,
            "why_now": "Rust reserved evidence remains weak across tokenizers and candle-flash-attn under both base and role-mapped scorers.",
            "evidence": [
                row["row_id"] for row in reserved_mismatches
                if str(row.get("language_family")) == "rust"
            ],
            "acceptance_requirements": [
                "No aliased visible evidence spans",
                "At least one fresh non-tokenizers family",
                "Selected-test or verifier anchors present",
                "Explicit-ledger candidate packet with six evidence roles when possible",
            ],
        },
        {
            "priority": 5,
            "lane": "c_cpp_validation_gap",
            "objective": "Replenish C/C++ verifier-outcome roots behind the unchanged validation miss.",
            "target_family": "parametergolf_verifier_transition",
            "required_new_roots": 4,
            "required_new_rows": 12,
            "why_now": "Successor eval still misses parametergolf verifier_outcome even after the support branch.",
            "evidence": [
                row_id for row_id in validation_misses if "::c_cpp::verifier_outcome::" in row_id
            ],
            "acceptance_requirements": [
                "Verifier target semantics visible in packet",
                "At least two plausible targets per row",
                "Not derived from the current eval row verbatim",
            ],
        },
    ]

    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": True,
        "decision": "explicit_ledger_conflict_replenishment_requested",
        "claim_scope": [
            "Turn the stage11054 and stage11056 audit results into the next concrete replenishment queue.",
            "Prioritize the row families that remain wrong even after the stricter explicit-ledger scorer gate.",
        ],
        "source_artifacts": {
            "postrun_audit": rel(AUDIT_11054),
            "explicit_ledger_gate_audit": rel(AUDIT_11056),
        },
        "metrics": {
            "strict_miss_count": len(strict_misses),
            "validation_miss_count": len(validation_misses),
            "reserved_mismatch_count": len(reserved_mismatches),
            "requested_work_items": len(work_items),
            "requested_new_roots_total": sum(int(item["required_new_roots"]) for item in work_items),
            "requested_new_rows_total": sum(int(item["required_new_rows"]) for item in work_items),
        },
        "headline_findings": [
            "Inference routing is no longer the main uncertainty: the explicit-ledger gate preserves the overlay but leaves the reserved bank flat.",
            "The next honest gain path is fresh root supply for the remaining conflict families plus deeper Python verifier-transition support.",
        ],
        "next_best_step": "Materialize the five requested replenishment families, then train a new branch or scorer-head objective only after those fresh roots exist.",
        "outputs": {
            "summary_json": rel(SUMMARY_JSON),
            "work_items_jsonl": rel(WORK_ITEMS_JSONL),
        },
    }
    write_json(SUMMARY_JSON, summary)
    write_jsonl(WORK_ITEMS_JSONL, work_items)
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
