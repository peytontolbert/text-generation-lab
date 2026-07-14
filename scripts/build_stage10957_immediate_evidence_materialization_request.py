#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "runs" / "local" / "artifacts"
STAGE = 10957
NAME = "stage10957_immediate_evidence_materialization_request"
OUT_DIR = ARTIFACTS / NAME
OUT_JSON = OUT_DIR / "immediate_evidence_materialization_request.json"
OUT_JSONL = OUT_DIR / "materialization_work_items.jsonl"

NEXT_BATCH_JSON = ARTIFACTS / "stage10956_multilingual_evidence_next_batch_package" / "multilingual_evidence_next_batch_package.json"
NEXT_BATCH_ROWS = ARTIFACTS / "stage10956_multilingual_evidence_next_batch_package" / "next_batch_rows.jsonl"


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


def main() -> None:
    package = load_json(NEXT_BATCH_JSON)
    rows = load_jsonl(NEXT_BATCH_ROWS)

    immediate = [row for row in rows if str(row.get("lane") or "") == "immediate_materialization"]
    rust_supply = [row for row in rows if str(row.get("lane") or "") == "rust_reviewed_supply"]
    web_rows = [row for row in rows if str(row.get("lane") or "") == "web_supply_or_stress"]

    work_items: list[dict[str, Any]] = []

    priority = 1
    for row in immediate:
        work_items.append(
            {
                "priority": priority,
                "workstream": "fresh_evidence_successor_materialization",
                "language_family": row.get("language_family"),
                "repo_id": row.get("repo_id"),
                "queue_or_bundle_id": row.get("queue_id"),
                "goal": "Build fresh explicit-ledger evidence rows with preserved anti-cheat constraints.",
                "why_now": "Direct scorer calibration is exhausted, and these are the only ready materialization candidates that directly attack the current B-vs-F blocker.",
                "required_inputs": {
                    "selected_tests": row.get("selected_tests"),
                    "candidate_paths": row.get("candidate_paths"),
                    "gold_answer_value": row.get("gold_answer_value"),
                    "competition_family": row.get("competition_family"),
                    "anti_cheat_challenge_families": row.get("anti_cheat_challenge_families"),
                    "materialization_requirements": row.get("materialization_requirements"),
                },
                "success_criteria": [
                    "materialized rows preserve selected-test anchors",
                    "no visible gold target path before options",
                    "candidate_change_surface remains plausible but not determinative",
                    "explicit-ledger evidence roles are human-judgeable from visible evidence",
                ],
                "promotable_if": [
                    "prompt_target_leak_rows == 0",
                    "same-surface comparison remains admissible",
                    "new rows are root-disjoint from the strict overlay",
                ],
            }
        )
        priority += 1

    for row in rust_supply:
        work_items.append(
            {
                "priority": priority,
                "workstream": "rust_evidence_replenishment",
                "language_family": "rust",
                "repo_id": row.get("repo_id"),
                "queue_or_bundle_id": row.get("bundle_id"),
                "goal": "Convert reviewed Rust supply into fresh E-vs-F evidence rows or explicitly classify it as support-only.",
                "why_now": "Rust still lacks a clean non-aliased heldout evidence successor after the tokenizers alias quarantine.",
                "required_inputs": {
                    "selected_tests": row.get("selected_tests"),
                    "visible_evidence_keys": row.get("visible_evidence_keys"),
                    "status": row.get("status"),
                    "decision_rationale": row.get("decision_rationale"),
                },
                "success_criteria": [
                    "at least one non-aliased Rust E-vs-F materialized row exists",
                    "selected-test or verifier anchors are persisted when available",
                    "abstention-heavy packets are not mislabeled as singleton-localization evidence",
                ],
                "promotable_if": [
                    "row is fresh and non-tokenizers when used as headline replenishment",
                    "candidate_change_surface does not duplicate the gold evidence span",
                ],
            }
        )
        priority += 1

    for row in web_rows:
        work_items.append(
            {
                "priority": priority,
                "workstream": "web_supply_governance",
                "language_family": row.get("language_family"),
                "repo_id": row.get("repo_id"),
                "queue_or_bundle_id": row.get("queue_id"),
                "goal": row.get("task"),
                "why_now": "Web remains the only language lane with a supply blocker rather than a ready replenishment candidate.",
                "required_inputs": {
                    "selected_tests": row.get("selected_tests"),
                    "candidate_paths": row.get("candidate_paths"),
                    "anti_cheat_requirements": row.get("anti_cheat_requirements"),
                    "status": row.get("status"),
                },
                "success_criteria": [
                    "pure-web headline path remains blocked until a new selected-test family exists"
                    if row.get("status") == "blocked_on_source_supply"
                    else "overlap web rows are clearly marked stress/train-support only"
                ],
                "promotable_if": [
                    "never for overlap stress rows",
                    "only after new pure-web selected-test family is source-heldout admissible",
                ],
            }
        )
        priority += 1

    payload = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": True,
        "decision": "advance_to_materialization_not_more_scorer_tuning",
        "claim_scope": [
            "Turn the stage10956 next-batch package into an ordered set of concrete materialization work items.",
            "Make the immediate Python/C++ replenishment path explicit while preserving the Rust replenishment and web supply-governance branches.",
        ],
        "source_package": rel(NEXT_BATCH_JSON),
        "headline": {
            "immediate_materialization_count": len(immediate),
            "rust_supply_items": len(rust_supply),
            "web_governance_items": len(web_rows),
            "next_priority_lane": (immediate[0].get("queue_id") if immediate else None),
        },
        "findings": [
            "The next honest step is materialization, not another scorer tweak or generic support probe.",
            "Python repository_library and C/C++ parametergolf are the direct replenishment lanes for the current B-vs-F blocker.",
            "The C/C++ agentkernel counterfamily remains necessary as a positive control against over-correcting all evidence rows toward verifier_and_test_constraint.",
            "Rust and web should be handled explicitly as replenishment and supply-governance branches, not quietly mixed into the same promotion claim.",
        ],
        "recommended_execution_order": [
            "Materialize python_repository_library_evidence_b_vs_f_replenishment.",
            "Materialize cpp_parametergolf_evidence_b_vs_f_replenishment.",
            "Materialize cpp_agentkernel_counterfamily_evidence_replenishment as the counterfamily control.",
            "Then convert one Rust reviewed supply bundle into a fresh non-aliased E-vs-F row family.",
            "Keep web on a blocked/stress branch until a pure-web selected-test family exists.",
        ],
        "outputs": {
            "request_json": rel(OUT_JSON),
            "work_items_jsonl": rel(OUT_JSONL),
        },
    }

    write_json(OUT_JSON, payload)
    write_jsonl(OUT_JSONL, work_items)
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
