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
STAGE = 11637
NAME = "stage11637_web_gap_root_materialization_request"
OUT = ART / NAME
SUMMARY = OUT / "web_gap_root_materialization_request.json"
WORK_ITEMS = OUT / "web_gap_root_materialization_work_items.jsonl"

STAGE11636 = ART / "stage11636_web_gap_targeted_supply_audit/web_gap_targeted_supply_audit.json"
STAGE11636_WORKLIST = ART / "stage11636_web_gap_targeted_supply_audit/web_gap_targeted_worklist.jsonl"

HIGH_PRIORITY_REPOS = {"openhands_openhands_frontend", "llama_stack_ui"}
TASK_TO_ANALOGUE_REQUIREMENT = {
    "evidence_citation": [
        "include at least three evidence items: candidate surface, selected verifier/test constraint, and symptom/call-path analogue",
        "gold must be the minimal sufficient evidence item or set, not a role name shortcut",
        "include a hard negative where candidate_change_surface is plausible but not decisive",
    ],
    "verifier_outcome": [
        "include selected verifier path, observed transition, and one plausible non-exercising verifier distractor",
        "target must be represented as verifier_id plus transition, not just an option letter",
        "include PASS_TO_PASS and FAIL_TO_PASS/FAIL_TO_FAIL contrasts when executable",
    ],
    "minimal_fix_selection": [
        "include two plausible fix surfaces with only one minimal under the visible verifier constraint",
        "include source snippet and verifier snippet sufficient for a maintainer to adjudicate",
    ],
    "symptom_localization": [
        "include symptom text, call-site/source snippet, and at least one sibling distractor surface",
        "avoid direct filename giveaway before options",
    ],
    "abstention_insufficient_evidence": [
        "include answerable and genuinely underdetermined siblings from separate roots",
        "target answer_with_visible_evidence only when the visible evidence uniquely supports one option",
    ],
    "alternative_hypothesis_elimination": [
        "include explicit plausible wrong hypothesis plus visible fact that rules it out",
        "avoid generic 'not config/test' template shortcuts",
    ],
}


def now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


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


def main() -> None:
    audit = load_json(STAGE11636)
    worklist = load_jsonl(STAGE11636_WORKLIST)
    support_task_counts = ((audit.get("support_inventory") or {}).get("gap_repo_task_counts") or {})
    blocker_by_repo = audit.get("gemma_correct_routed_wrong_by_repo_family") or {}
    blocker_by_task = audit.get("gemma_correct_routed_wrong_by_task_type") or {}

    items: list[dict[str, Any]] = []
    for row in worklist:
        repo = str(row.get("repo_family") or "unknown")
        task = str(row.get("task_type") or "unknown")
        existing = int(row.get("existing_train_support_rows_for_repo_task") or 0)
        if repo in HIGH_PRIORITY_REPOS:
            root_target = 12
            reason = "high_priority_web_transfer_family"
        elif task in {"evidence_citation", "verifier_outcome"}:
            root_target = 6
            reason = "high_frequency_task_blocker"
        else:
            root_target = 4
            reason = "secondary_web_blocker"
        if existing >= row.get("recommended_new_root_target", 0):
            request_kind = "quality_rebuild_disjoint_analogues"
            supply_note = "Existing support rows are present, but Stage11633/11635 show they did not transfer to heldout."
        else:
            request_kind = "supply_gap_plus_quality_rebuild"
            supply_note = "Existing support rows are below target for this blocker bucket."
        items.append(
            {
                "work_item_id": f"{NAME}::{repo}::{task}",
                "repo_family": repo,
                "task_type": task,
                "request_kind": request_kind,
                "priority": row.get("priority"),
                "reason": reason,
                "blocking_rows": row.get("blocking_rows"),
                "example_blocking_row_ids": row.get("example_blocking_row_ids"),
                "existing_train_support_rows_for_repo_task": existing,
                "new_disjoint_root_target": root_target,
                "required_projection_rows_per_root": [
                    "symptom_localization",
                    "evidence_citation",
                    "verifier_outcome",
                    "minimal_fix_selection",
                    "patch_impact",
                    "abstention_insufficient_evidence",
                ],
                "task_specific_requirements": TASK_TO_ANALOGUE_REQUIREMENT.get(task, []),
                "global_admission_requirements": [
                    "root_id and root_lineage_key must be disjoint from web_root_heldout_66",
                    "repo-family overlap may be used only as transfer-support, never as source-heldout claim evidence",
                    "selected verifier path or executed transition is required",
                    "opaque deterministic option shuffle must be declared",
                    "no target semantic value may appear before options",
                    "candidate hard negatives must be root-local and maintainer-plausible",
                    "review packet must expose snippets/test/verifier evidence sufficient for AI-maintainer adjudication",
                ],
                "supply_note": supply_note,
            }
        )

    total_requested_roots = sum(int(item["new_disjoint_root_target"]) for item in items)
    high_priority_requested_roots = sum(
        int(item["new_disjoint_root_target"]) for item in items if item["repo_family"] in HIGH_PRIORITY_REPOS
    )
    gates = {
        "stage11636_confirms_routed_web_still_loses_to_gemma": not ((audit.get("gates") or {}).get("routed_beats_gemma")),
        "stage11636_has_complete_same_row_inputs": (audit.get("gates") or {}).get("same_row_inputs_complete") is True,
        "request_targets_openhands_or_llama": any(item["repo_family"] in HIGH_PRIORITY_REPOS for item in items),
        "request_includes_evidence_or_verifier_tasks": any(item["task_type"] in {"evidence_citation", "verifier_outcome"} for item in items),
        "request_distinguishes_quality_rebuild_from_raw_supply": any(item["request_kind"] == "quality_rebuild_disjoint_analogues" for item in items),
    }
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now(),
        "decision": "web_gap_materialization_request_ready" if all(gates.values()) else "web_gap_materialization_request_blocked",
        "gates": gates,
        "requested_work_items": len(items),
        "total_requested_disjoint_roots": total_requested_roots,
        "high_priority_openhands_llama_requested_roots": high_priority_requested_roots,
        "blocker_context": {
            "gemma_correct_routed_wrong_by_repo_family": blocker_by_repo,
            "gemma_correct_routed_wrong_by_task_type": blocker_by_task,
            "support_task_counts_for_gap_repos": support_task_counts,
            "interpretation": "The current issue is not raw row absence. Existing OpenHands/Llama support exists, but its geometry did not transfer to heldout.",
        },
        "training_policy_after_materialization": {
            "do_not_train_until": [
                "new roots pass anti-cheat admission",
                "root overlap with web_root_heldout_66 is zero",
                "all requested task buckets have at least one admitted root",
                "protected canary/residual replay rows are included",
            ],
            "first_probe_should_be": {
                "sampler": "web_task_family_balanced_or_root_balanced",
                "contrast": "task-aware hard-negative contrast enabled",
                "preservation_kl": ">=4.0",
                "device_constraint": "CUDA_VISIBLE_DEVICES=2 only",
            },
            "promotion_gate": {
                "protected_filtered_strict": "22/22",
                "protected_old_canary_strict": "23/23",
                "protected_residual_bank": ">=7/10",
                "web_heldout": ">38/66 first; >52/66 for Gemma Web win",
                "same_manifest_gemma_comparison": "attached",
            },
        },
        "rl_scale_note": {
            "interpretation": "Do not count optimizer steps as experience. A serious RL stage should count complete scored rollouts per update.",
            "minimum_before_rl": [
                "hundreds of executable Web roots, not 66 heldout rows",
                "root-disjoint train/eval split",
                "automated verifier scoring",
                "parallel rollout infrastructure pinned away from GPUs 0 and 1",
            ],
        },
        "source_artifacts": {
            "stage11636_summary": rel(STAGE11636),
            "stage11636_worklist": rel(STAGE11636_WORKLIST),
        },
        "outputs": {"summary": rel(SUMMARY), "work_items": rel(WORK_ITEMS)},
    }

    OUT.mkdir(parents=True, exist_ok=True)
    write_json(SUMMARY, summary)
    write_jsonl(WORK_ITEMS, items)
    SUMMARIES.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(SUMMARY, SUMMARIES / f"{NAME}.json")
    print(
        json.dumps(
            {
                "decision": summary["decision"],
                "requested_work_items": len(items),
                "total_requested_disjoint_roots": total_requested_roots,
                "high_priority_openhands_llama_requested_roots": high_priority_requested_roots,
                "gates": gates,
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
