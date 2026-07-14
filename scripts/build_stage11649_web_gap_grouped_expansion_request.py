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
STAGE = 11649
NAME = "stage11649_web_gap_grouped_expansion_request"
OUT = ART / NAME
SUMMARY = OUT / "web_gap_grouped_expansion_request.json"
WORK_ITEMS = OUT / "web_gap_grouped_expansion_work_items.jsonl"

STAGE11646_WORK_ITEMS = ART / "stage11646_web_heldout_gap_rollout_mining/web_heldout_gap_materialization_work_items.jsonl"
STAGE11648 = ART / "stage11648_web_gap_grouped_admission_compiler/web_gap_grouped_admission_compiler.json"
STAGE11648_ADMITTED = ART / "stage11648_web_gap_grouped_admission_compiler/web_gap_grouped_admitted_rows.jsonl"

MIN_ROOTS_FOR_PROBE = 20
TARGET_ROOTS_FOR_FIRST_BATCH = 104


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


def root_id(row: dict[str, Any]) -> str:
    return str(row.get("root_id") or row.get("root_lineage_key") or row.get("row_id") or "unknown")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    stage11648 = load_json(STAGE11648)
    gap_items = load_jsonl(STAGE11646_WORK_ITEMS)
    admitted = load_jsonl(STAGE11648_ADMITTED)
    admitted_roots_by_repo: dict[str, set[str]] = collections.defaultdict(set)
    admitted_rows_by_repo_task: dict[tuple[str, str], int] = collections.Counter()
    for row in admitted:
        repo = str(row.get("repo_family") or "unknown")
        task = str(row.get("task_type") or "unknown")
        admitted_roots_by_repo[repo].add(root_id(row))
        admitted_rows_by_repo_task[(repo, task)] += 1

    gap_by_repo_task = {(str(item.get("repo_family")), str(item.get("task_type"))): item for item in gap_items}
    expansion: list[dict[str, Any]] = []
    for (repo, task), item in sorted(gap_by_repo_task.items()):
        admitted_rows = admitted_rows_by_repo_task.get((repo, task), 0)
        admitted_roots = len(admitted_roots_by_repo.get(repo, set()))
        base_needed = int(item.get("recommended_new_disjoint_roots") or 4)
        if admitted_rows > 0 and admitted_roots >= base_needed:
            priority = "satisfied_for_now"
            requested = 0
        else:
            priority = "highest" if repo in {"openhands_openhands_frontend", "llama_stack_ui"} else "high"
            requested = max(base_needed - admitted_roots, 4 if admitted_rows == 0 else 0)
        if requested <= 0:
            continue
        expansion.append(
            {
                "work_item_id": f"stage11649::{repo}::{task}",
                "repo_family": repo,
                "task_type": task,
                "priority": priority,
                "requested_new_disjoint_roots": requested,
                "rollouts_per_root": 16,
                "nominal_rollouts": requested * 16,
                "current_admitted_rows_for_repo_task": admitted_rows,
                "current_admitted_roots_for_repo": admitted_roots,
                "source_gap_row_ids": item.get("source_gap_row_ids") or [],
                "source_gap_root_id": item.get("source_gap_root_id"),
                "materialization_requirements": item.get("materialization_requirements") or [],
                "admission_target": "must pass stage11648 grouped admission compiler",
            }
        )

    current_roots = stage11648.get("metrics", {}).get("admitted_roots", 0)
    roots_needed_min = max(0, MIN_ROOTS_FOR_PROBE - int(current_roots or 0))
    roots_needed_full = max(0, TARGET_ROOTS_FOR_FIRST_BATCH - int(current_roots or 0))
    by_repo = collections.Counter(item["repo_family"] for item in expansion)
    by_task = collections.Counter(item["task_type"] for item in expansion)
    total_requested = sum(int(item["requested_new_disjoint_roots"]) for item in expansion)
    decision = "web_gap_grouped_expansion_request_ready" if expansion else "no_expansion_needed_rerun_stage11648"
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now(),
        "decision": decision,
        "reason": "Stage11648 admitted enough rows but only 11 roots, all from llama_stack_ui; grouped probe requires broader root/repo coverage.",
        "stage11648_status": {
            "decision": stage11648.get("decision"),
            "metrics": stage11648.get("metrics"),
            "gates": stage11648.get("gates"),
        },
        "metrics": {
            "expansion_work_items": len(expansion),
            "requested_new_disjoint_roots": total_requested,
            "nominal_rollouts_at_group16": total_requested * 16,
            "roots_needed_to_unblock_min_probe": roots_needed_min,
            "roots_needed_to_reach_stage11646_first_batch_target": roots_needed_full,
            "current_admitted_roots": current_roots,
            "current_admitted_rows": stage11648.get("metrics", {}).get("admitted_rows", 0),
        },
        "expansion_by_repo": dict(by_repo),
        "expansion_by_task": dict(by_task),
        "mandatory_next_gate": "rerun stage11648 after materialization; do not run stage11649 grouped training until stage11648 emits a non-null command",
        "outputs": {"summary": rel(SUMMARY), "work_items": rel(WORK_ITEMS)},
        "source_artifacts": {
            "stage11646_work_items": rel(STAGE11646_WORK_ITEMS),
            "stage11648_summary": rel(STAGE11648),
            "stage11648_admitted": rel(STAGE11648_ADMITTED),
        },
        "claim_boundary": [
            "This is a data expansion request, not a training request.",
            "Do not lower the Stage11648 admitted-root gate to run on llama_stack_ui-only analogues.",
            "The next trainable package must include OpenHands and other heldout-gap repo families, root-disjoint from the 66 Web heldout rows.",
        ],
    }
    write_jsonl(WORK_ITEMS, expansion)
    write_json(SUMMARY, summary)
    SUMMARIES.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(SUMMARY, SUMMARIES / f"{NAME}.json")
    print(json.dumps({"decision": decision, "metrics": summary["metrics"], "expansion_by_repo": summary["expansion_by_repo"], "expansion_by_task": summary["expansion_by_task"]}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
