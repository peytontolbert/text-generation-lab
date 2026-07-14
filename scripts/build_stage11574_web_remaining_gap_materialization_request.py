#!/usr/bin/env python3
from __future__ import annotations

import json
import shutil
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "runs/local/artifacts"
SUMMARIES = ROOT / "runs/summaries"
STAGE = 11574
NAME = "stage11574_web_remaining_gap_materialization_request"
OUT = ART / NAME
SUMMARY = OUT / "web_remaining_gap_materialization_request.json"
WORK_ITEMS = OUT / "web_remaining_gap_work_items.jsonl"

STAGE11573_SUMMARY = SUMMARIES / "stage11573_web_remaining_miss_materialization_audit.json"
STAGE11573_CARDS = ART / "stage11573_web_remaining_miss_materialization_audit/remaining_web_miss_cards.jsonl"
STAGE11573_QUEUE = ART / "stage11573_web_remaining_miss_materialization_audit/web_materialization_queue.jsonl"


def now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def priority_for(action: str) -> int:
    if "openhands" in action:
        return 1
    if "llama_stack" in action:
        return 2
    return 3


def required_artifacts(action: str) -> list[str]:
    base = [
        "root_record_with_repo_snapshot_commit_and_lineage_key",
        "task_observation_and_acceptance_condition",
        "visible_source_snippet_for_each_candidate_surface",
        "deterministically_shuffled_opaque_options",
        "prompt_target_leak_audit",
        "root_split_overlap_audit",
        "anti_cheat_review_card",
    ]
    if "openhands" in action or "llama_stack" in action:
        return base + [
            "selected_test_or_verifier_command",
            "verifier_transition_label_fail_to_pass_pass_to_pass_not_exercised_or_insufficient",
            "test_id_and_changed_path_candidate_pairs",
            "non_evidence_perspective_gold_answers",
        ]
    return base + [
        "evidence_ledger_with_decisive_supporting_distractor_and_contradictory_roles",
        "candidate_change_surface_vs_verifier_constraint_hard_negatives",
        "evidence_item_gold_role_answer",
    ]


def admission_gates(action: str) -> dict[str, Any]:
    common = {
        "train_on_source_miss_rows": False,
        "same_root_as_current_heldout_allowed": False,
        "singleton_options_allowed": False,
        "gold_value_visible_before_options_allowed": False,
        "deterministic_option_shuffle_required": True,
        "opaque_labels_required": True,
        "minimum_options": 4,
    }
    if "openhands" in action:
        common.update(
            {
                "minimum_train_roots": 10,
                "minimum_heldout_roots": 3,
                "minimum_repo_families": 2,
                "must_include_task_types": [
                    "symptom_localization",
                    "verifier_outcome",
                    "minimal_fix_selection",
                    "alternative_hypothesis_elimination",
                    "abstention_insufficient_evidence",
                ],
            }
        )
    elif "llama_stack" in action:
        common.update(
            {
                "minimum_train_roots": 10,
                "minimum_heldout_roots": 3,
                "minimum_repo_families": 1,
                "must_include_task_types": [
                    "symptom_localization",
                    "evidence_citation",
                    "verifier_outcome",
                    "minimal_fix_selection",
                    "alternative_hypothesis_elimination",
                    "abstention_insufficient_evidence",
                ],
            }
        )
    else:
        common.update(
            {
                "minimum_train_roots": 5,
                "minimum_heldout_roots": 2,
                "minimum_repo_families": 1,
                "must_include_task_types": ["evidence_citation"],
                "must_balance_roles": [
                    "candidate_change_surface",
                    "verifier_and_test_constraint",
                    "symptom_or_call_path_analogue",
                    "insufficient_evidence",
                ],
            }
        )
    return common


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    summary11573 = load_json(STAGE11573_SUMMARY)
    cards = load_jsonl(STAGE11573_CARDS)
    queue = load_jsonl(STAGE11573_QUEUE)
    cards_by_action: dict[str, list[dict[str, Any]]] = {}
    for card in cards:
        cards_by_action.setdefault(str(card.get("recommended_materialization_action")), []).append(card)

    work_items: list[dict[str, Any]] = []
    for item in queue:
        action = str(item["action"])
        source_cards = cards_by_action.get(action, [])
        work_items.append(
            {
                "priority": priority_for(action),
                "action": action,
                "status": "requested_not_materialized",
                "source_miss_rows": item.get("source_miss_row_ids") or [],
                "source_miss_count": item.get("miss_rows"),
                "source_repo_buckets": item.get("repo_buckets"),
                "source_task_types": item.get("task_types"),
                "minimum_next_supply": item.get("minimum_next_supply"),
                "admission_gates": admission_gates(action),
                "required_artifacts": required_artifacts(action),
                "example_target_confusions": [
                    {
                        "row_id": card.get("row_id"),
                        "task_type": card.get("task_type"),
                        "target_value": (card.get("target_option") or {}).get("value"),
                        "predicted_value": (card.get("predicted_option") or {}).get("value"),
                    }
                    for card in source_cards[:5]
                ],
                "negative_result_context": [
                    "stage11550_web_support_probe_did_not_improve_web_heldout",
                    "stage11563_conservative_openhands_probe_preserved_strict_but_only_reached_42_of_66_web",
                    "stage11567_balanced_non_evidence_support_preserved_no_frontier_gain",
                    "stage11570_semantic_candidate_metadata_support_preserved_no_frontier_gain",
                ],
                "next_allowed_step": "materialize_and_audit_fresh_roots_only",
            }
        )

    work_items.sort(key=lambda row: (row["priority"], row["action"]))
    metrics = {
        "work_items": len(work_items),
        "source_remaining_misses": summary11573["miss_summary"]["remaining_misses"],
        "gemma_correct_on_100m_misses": summary11573["miss_summary"]["gemma_correct_on_100m_misses"],
        "requested_minimum_train_roots": sum((item.get("minimum_next_supply") or {}).get("train_roots", 0) for item in queue),
        "requested_minimum_heldout_roots": sum((item.get("minimum_next_supply") or {}).get("heldout_roots", 0) for item in queue),
    }
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now(),
        "passed": True,
        "decision": "fresh_web_gap_materialization_requested_no_training",
        "metrics": metrics,
        "work_items": work_items,
        "promotion_blockers": [
            "stage11571 Web remains 42/66 while Gemma is 52/66",
            "all 24 remaining 100M misses are Gemma-correct on the same manifest",
            "prior support probes did not transfer to Llama Stack or OpenHands non-evidence tasks",
            "remaining MCP/SEP evidence misses need evidence-item judgment rows, not global scorer reroutes",
        ],
        "next_stage_recommendation": "stage11575_web_remaining_gap_fresh_root_materializer",
        "claim_boundary": [
            "This is not a training package and must not be used as train support directly.",
            "The current selected frontier remains stage11507/stage11509.",
            "Progress on Web now requires fresh root materialization and admission, not another probe over existing miss rows.",
        ],
        "source_artifacts": {
            "stage11573_summary": rel(STAGE11573_SUMMARY),
            "stage11573_cards": rel(STAGE11573_CARDS),
            "stage11573_queue": rel(STAGE11573_QUEUE),
        },
        "outputs": {"summary": rel(SUMMARY), "work_items": rel(WORK_ITEMS)},
    }
    write_jsonl(WORK_ITEMS, work_items)
    write_json(SUMMARY, summary)
    SUMMARIES.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(SUMMARY, SUMMARIES / f"{NAME}.json")
    print(json.dumps({"decision": summary["decision"], "metrics": metrics, "top_work_items": work_items[:3]}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
