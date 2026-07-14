#!/usr/bin/env python3
from __future__ import annotations

import collections
import json
import shutil
import time
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "runs/local/artifacts"
SUMMARIES = ROOT / "runs/summaries"
STAGE = 11646
NAME = "stage11646_web_heldout_gap_rollout_mining"
OUT = ART / NAME
SUMMARY = OUT / "web_heldout_gap_rollout_mining.json"
GROUPS = OUT / "web_heldout_gap_rollout_groups.jsonl"
WORK_ITEMS = OUT / "web_heldout_gap_materialization_work_items.jsonl"

HELDOUT_ROWS = ART / "stage11548_web_root_heldout_stage11507_score_audit/web_root_heldout_rows.jsonl"
ROUTED_AUDIT = ART / "stage11631_web_head_only_transfer_audit/bounded_choice_eval_audit_web_heldout.json"
GEMMA_ROWS = ART / "stage11549_web_root_heldout_same_manifest_gemma_comparison/web_root_heldout_gemma_rows.jsonl"
SUPPORT_ROWS = ART / "stage11638_web_support_schema_normalization/web_support_normalized_admitted_train_rows.jsonl"
STAGE11645 = ART / "stage11645_web_head_only_fit_decision/web_head_only_fit_decision.json"

TASKS = [
    "symptom_localization",
    "evidence_citation",
    "verifier_outcome",
    "minimal_fix_selection",
    "patch_impact",
    "alternative_hypothesis_elimination",
    "abstention_insufficient_evidence",
]


def now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


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
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def counter(rows: list[dict[str, Any]], key: str) -> dict[str, int]:
    return dict(collections.Counter(str(row.get(key) or "unknown") for row in rows))


def row_card_map(path: Path) -> dict[str, dict[str, Any]]:
    card = load_json(path)
    return {str(row["row_id"]): row for row in card.get("row_cards") or []}


def option_roles(row: dict[str, Any]) -> dict[str, str]:
    roles: dict[str, str] = {}
    for option in row.get("opaque_options") or []:
        label = str(option.get("label") or "")
        role = str(option.get("semantic_role") or option.get("value") or option.get("text") or "unknown")
        if label:
            roles[label] = role
    return roles


def support_index(rows: list[dict[str, Any]]) -> dict[tuple[str, str], list[dict[str, Any]]]:
    out: dict[tuple[str, str], list[dict[str, Any]]] = collections.defaultdict(list)
    for row in rows:
        repo = str(row.get("repo_family") or row.get("git_repo_family") or "unknown")
        task = str(row.get("task_type") or "unknown")
        out[(repo, task)].append(row)
    return out


def selected_option(row: dict[str, Any], label: str | None) -> dict[str, Any] | None:
    if not label:
        return None
    for option in row.get("opaque_options") or []:
        if option.get("label") == label:
            return option
    return None


def same_root_task_coverage(rows: list[dict[str, Any]]) -> dict[str, list[str]]:
    by_root: dict[str, set[str]] = collections.defaultdict(set)
    for row in rows:
        by_root[str(row.get("root_id") or "unknown")].add(str(row.get("task_type") or "unknown"))
    return {root: sorted(tasks) for root, tasks in by_root.items()}


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    heldout = load_jsonl(HELDOUT_ROWS)
    gemma = {str(row["row_id"]): row for row in load_jsonl(GEMMA_ROWS)}
    routed = row_card_map(ROUTED_AUDIT)
    support = load_jsonl(SUPPORT_ROWS)
    support_by_repo_task = support_index(support)

    gap_rows: list[dict[str, Any]] = []
    routed_recovered: list[dict[str, Any]] = []
    gemma_missed_routed_correct: list[dict[str, Any]] = []
    both_wrong: list[dict[str, Any]] = []
    for row in heldout:
        row_id = str(row["row_id"])
        gemma_card = gemma.get(row_id, {})
        routed_card = routed.get(row_id, {})
        gemma_correct = gemma_card.get("gemma12b_correct") is True
        routed_correct = routed_card.get("constrained_choice_match") is True
        enriched = {
            "row_id": row_id,
            "root_id": row.get("root_id"),
            "root_lineage_key": row.get("root_lineage_key"),
            "repo_family": row.get("repo_family"),
            "task_type": row.get("task_type"),
            "target_label": row.get("bounded_choice_target_label") or row.get("target_text"),
            "target_semantic_value": row.get("semantic_target_value"),
            "routed_predicted_label": routed_card.get("constrained_choice_top1_label"),
            "routed_predicted_value": (selected_option(row, routed_card.get("constrained_choice_top1_label")) or {}).get("value"),
            "routed_full_vocab_top1_text": routed_card.get("full_vocab_top1_text"),
            "routed_target_rank_full_vocab": routed_card.get("target_rank_full_vocab"),
            "gemma_predicted_label": gemma_card.get("gemma12b_predicted_label"),
            "gemma_raw_output": gemma_card.get("gemma12b_raw_output"),
            "gemma_correct": gemma_correct,
            "routed_correct": routed_correct,
            "option_roles_by_label": option_roles(row),
            "options": row.get("opaque_options") or [],
            "selected_verifier_path": (row.get("standalone_projection_source") or {}).get("bundle", {}).get("selected_test_path")
            or row.get("selected_verifier_path"),
            "verifier_transition": row.get("verifier_transition")
            or row.get("observed_verifier_transition")
            or ((row.get("standalone_projection_source") or {}).get("bundle", {}).get("verifier_execution_evidence") or {}).get("status"),
            "existing_support_rows_for_repo_task": len(
                support_by_repo_task.get((str(row.get("repo_family") or "unknown"), str(row.get("task_type") or "unknown")), [])
            ),
            "split_instruction": "sealed_heldout_do_not_train",
        }
        if gemma_correct and not routed_correct:
            gap_rows.append(enriched)
        elif routed_correct and not gemma_correct:
            routed_recovered.append(enriched)
        elif not routed_correct and not gemma_correct:
            both_wrong.append(enriched)
        else:
            pass
    # Keep a separate list of Gemma misses that the routed product gets right for contrastive counterfamilies.
    gemma_missed_routed_correct = routed_recovered

    by_root: dict[str, list[dict[str, Any]]] = collections.defaultdict(list)
    for row in gap_rows:
        by_root[str(row.get("root_id") or row["row_id"])].append(row)

    groups: list[dict[str, Any]] = []
    work_items: list[dict[str, Any]] = []
    for root_id, rows in sorted(by_root.items()):
        repo = str(rows[0].get("repo_family") or "unknown")
        tasks = sorted({str(row.get("task_type") or "unknown") for row in rows})
        support_counts = {task: len(support_by_repo_task.get((repo, task), [])) for task in tasks}
        missing_tasks = [task for task in TASKS if task not in tasks]
        group = {
            "group_id": f"stage11646::{repo}::{root_id}",
            "root_id": root_id,
            "root_lineage_key": rows[0].get("root_lineage_key"),
            "repo_family": repo,
            "blocked_rows": len(rows),
            "blocked_task_types": tasks,
            "missing_task_types_in_gap": missing_tasks,
            "existing_support_rows_by_blocked_task": support_counts,
            "heldout_rows": rows,
            "required_disjoint_analogue_roots": max(4, len(rows) * 4),
            "rollout_group_size": 16,
            "training_design": {
                "unit": "root_local_candidate_group",
                "do_not_train_on": "these sealed heldout row_ids",
                "generate": [
                    "16 candidate decisions per analogue root",
                    "same-root listwise scores over opaque options",
                    "pairwise margins against hardest wrong option",
                    "verifier-grounded outcome labels for selected tests",
                ],
                "loss_recommendation": [
                    "listwise_softmax_over_same_root_candidates",
                    "pairwise_margin_correct_vs_hardest_wrong",
                    "protected_replay_gate_against_stage11507 compact canary",
                    "repo_family/task_family balanced sampling",
                ],
            },
            "quality_gates": [
                "root-disjoint from web_root_heldout_66",
                "not from any protected compact canary/residual root",
                "selected verifier/test path present",
                "observed verifier transition present",
                "opaque deterministic options",
                "no target label or gold semantic value visible before choices except legitimate code/test evidence",
                "candidate_change_surface, verifier_and_test_constraint, symptom_or_call_path_analogue, and abstain competitors where task-appropriate",
                "include at least one counterfamily where candidate_change_surface is genuinely correct",
            ],
        }
        groups.append(group)
        for task in tasks:
            work_items.append(
                {
                    "work_item_id": f"stage11646::{repo}::{task}::{root_id}",
                    "repo_family": repo,
                    "task_type": task,
                    "source_gap_root_id": root_id,
                    "source_gap_row_ids": [row["row_id"] for row in rows if row.get("task_type") == task],
                    "recommended_new_disjoint_roots": max(4, 4 * sum(1 for row in rows if row.get("task_type") == task)),
                    "rollouts_per_root": 16,
                    "existing_support_rows_for_repo_task": len(support_by_repo_task.get((repo, task), [])),
                    "materialization_requirements": group["quality_gates"],
                    "priority": "highest" if repo in {"openhands_openhands_frontend", "llama_stack_ui"} else "high",
                }
            )

    support_task_coverage = same_root_task_coverage(support)
    complete_support_roots = sum(1 for tasks in support_task_coverage.values() if set(TASKS[:6]).issubset(set(tasks)))
    stage11645 = load_json(STAGE11645)
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now(),
        "decision": "web_heldout_gap_rollout_groups_ready",
        "inputs": {
            "heldout_rows": rel(HELDOUT_ROWS),
            "routed_audit": rel(ROUTED_AUDIT),
            "gemma_rows": rel(GEMMA_ROWS),
            "normalized_support_rows": rel(SUPPORT_ROWS),
            "stage11645_decision": rel(STAGE11645),
        },
        "metrics": {
            "heldout_rows": len(heldout),
            "gemma_correct_routed_wrong_rows": len(gap_rows),
            "routed_correct_gemma_wrong_rows": len(routed_recovered),
            "both_wrong_rows": len(both_wrong),
            "gap_root_groups": len(groups),
            "work_items": len(work_items),
            "support_rows": len(support),
            "support_roots": len(support_task_coverage),
            "complete_six_task_support_roots": complete_support_roots,
        },
        "gap_by_repo": counter(gap_rows, "repo_family"),
        "gap_by_task": counter(gap_rows, "task_type"),
        "gap_by_target_semantic_value": counter(gap_rows, "target_semantic_value"),
        "gap_by_routed_predicted_label": counter(gap_rows, "routed_predicted_label"),
        "routed_recovered_by_repo": counter(routed_recovered, "repo_family"),
        "routed_recovered_by_task": counter(routed_recovered, "task_type"),
        "stage11645_read": {
            "decision": stage11645.get("decision"),
            "normalized_web_train_support": stage11645.get("key_results", {}).get("normalized_web_train_support"),
            "web_heldout": stage11645.get("key_results", {}).get("web_heldout"),
            "protected_strict": {
                "filtered_strict": stage11645.get("key_results", {}).get("filtered_strict"),
                "old_canary_strict": stage11645.get("key_results", {}).get("old_canary_strict"),
            },
        },
        "next_training_design": {
            "do_not_run_next": [
                "head_only support fit against the same 206 rows",
                "full-model generic Web support probe without grouped heldout analogues",
                "training directly on the 66 heldout rows",
            ],
            "run_next": [
                "materialize disjoint analogue roots for these exact gap groups",
                "train with grouped/root-local listwise or pairwise candidate ranking",
                "use protected Stage11507 replay gates during model selection, not only after training",
                "evaluate against Web heldout 66, Web successor 36, compact canary, residual, and same-manifest Gemma",
            ],
            "rl_scale_translation": {
                "meaningful_step": "one update over grouped root-local candidate rollouts with verifier grades",
                "suggested_group_size": 16,
                "first_batch_target_roots": sum(item["recommended_new_disjoint_roots"] for item in work_items),
                "first_batch_nominal_rollouts": 16 * sum(item["recommended_new_disjoint_roots"] for item in work_items),
                "note": "This mirrors the useful part of RL-style coding training: many graded attempts per root before one update, not merely more optimizer steps.",
            },
        },
        "outputs": {"groups": rel(GROUPS), "work_items": rel(WORK_ITEMS), "summary": rel(SUMMARY)},
        "claim_boundary": [
            "These are mining/materialization instructions, not train rows.",
            "The 66 Web heldout rows remain sealed evaluation rows.",
            "A future run is promotable only if it beats routed 38/66 Web heldout while preserving Stage11507 protected gates.",
        ],
    }
    write_jsonl(GROUPS, groups)
    write_jsonl(WORK_ITEMS, work_items)
    write_json(SUMMARY, summary)
    SUMMARIES.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(SUMMARY, SUMMARIES / f"{NAME}.json")
    print(
        json.dumps(
            {
                "decision": summary["decision"],
                "metrics": summary["metrics"],
                "gap_by_repo": summary["gap_by_repo"],
                "gap_by_task": summary["gap_by_task"],
                "first_batch_nominal_rollouts": summary["next_training_design"]["rl_scale_translation"][
                    "first_batch_nominal_rollouts"
                ],
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
