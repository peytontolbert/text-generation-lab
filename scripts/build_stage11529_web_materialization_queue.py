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
STAGE = 11529
NAME = "stage11529_web_materialization_queue"
OUT = ART / NAME
SUMMARY = OUT / "web_materialization_queue.json"
QUEUE = OUT / "web_materialization_work_items.jsonl"

STAGE11346 = ART / "stage11346_web_source_verifier_review_queue/web_source_verifier_first_wave_review_queue.jsonl"
STAGE11353 = ART / "stage11353_web_verifier_execution_evidence/web_verifier_execution_evidence.json"
STAGE11528 = SUMMARIES / "stage11528_web_verifier_root_supply_audit.json"


PROTECTED_HELDOUT_FAMILIES = {"llama_stack", "llama_stack_ui", "openhands_openhands", "openhands_openhands_frontend"}
ALREADY_EXECUTED_TRAIN_FAMILIES = {
    "modelcontextprotocol_typescript_sdk",
    "modelcontextprotocol_modelcontextprotocol",
    "sourcebot",
    "openhands_openhands",
}


def now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()] if path.exists() else []


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def split_recommendation(item: dict[str, Any]) -> str:
    family = str(item.get("git_repo_family") or item.get("repo_family") or "")
    repo_family = str(item.get("repo_family") or "")
    if family in PROTECTED_HELDOUT_FAMILIES or repo_family in PROTECTED_HELDOUT_FAMILIES:
        return "sealed_heldout_only"
    if family in ALREADY_EXECUTED_TRAIN_FAMILIES:
        return "train_support_or_additional_diagnostic"
    if family in {"openclaw_clawhub", "dspy", "ai_town"}:
        return "preferred_new_heldout_or_train_family"
    if repo_family == "qa_lab":
        return "train_support_after_dependency_repair"
    return "train_support_candidate"


def blocker_context(item: dict[str, Any], stage11353: dict[str, Any]) -> list[str]:
    review_required = item.get("review_required_fields") or {}
    blockers = [key for key, value in review_required.items() if value is None]
    repo_family = item.get("repo_family")
    if repo_family == "qa_lab":
        qa = ((stage11353.get("by_root") or {}).get("qa_model_switch_continuity") or {})
        if qa.get("execution_status") != "verifier_executed_passed":
            blockers.append("qa_lab_dependency_setup_blocked")
    return sorted(set(blockers))


def main() -> None:
    items = load_jsonl(STAGE11346)
    stage11353 = load_json(STAGE11353)
    stage11528 = load_json(STAGE11528)
    work_items: list[dict[str, Any]] = []
    for item in items:
        rec = split_recommendation(item)
        blockers = blocker_context(item, stage11353)
        priority = 10
        if item.get("git_repo_family") in {"openclaw_clawhub", "dspy", "ai_town"}:
            priority = 1
        elif item.get("repo_family") == "qa_lab":
            priority = 2
        elif rec == "train_support_candidate":
            priority = 3
        elif rec == "train_support_or_additional_diagnostic":
            priority = 4
        elif rec == "sealed_heldout_only":
            priority = 5
        work_items.append(
            {
                "priority": priority,
                "review_item_id": item.get("review_item_id"),
                "source_candidate_id": item.get("source_candidate_id"),
                "repo_family": item.get("repo_family"),
                "git_repo_family": item.get("git_repo_family"),
                "repo_path": item.get("repo_path"),
                "git_head": item.get("git_head"),
                "recommended_split": rec,
                "strict_eval_eligible_current": item.get("strict_eval_eligible"),
                "candidate_change_surface_paths": item.get("candidate_change_surface_paths") or [],
                "verifier_and_test_constraint_paths": item.get("verifier_and_test_constraint_paths") or [],
                "materialization_blockers": blockers,
                "required_actions": [
                    "select maintainer-grade root task/bug description",
                    "choose one changed/source path and one selected verifier/test path",
                    "execute or recover focused verifier output",
                    "fill gold perspective answers for six maintainer perspectives",
                    "emit deterministic shuffled opaque options",
                    "run prompt-target leak and root-overlap audit",
                ],
            }
        )
    work_items.sort(key=lambda row: (row["priority"], str(row.get("git_repo_family")), str(row.get("repo_family"))))
    preferred_new = [row for row in work_items if row["priority"] == 1]
    qa_blocked = [row for row in work_items if row.get("repo_family") == "qa_lab"]
    protected = [row for row in work_items if row["recommended_split"] == "sealed_heldout_only"]
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now(),
        "passed": True,
        "decision": "web_materialization_queue_ready_supply_gap_remains",
        "metrics": {
            "stage11528_train_roots_available": ((stage11528.get("stage11527_gate") or {}).get("train_roots_available")),
            "stage11528_train_roots_required": ((stage11528.get("stage11527_gate") or {}).get("train_roots_required")),
            "stage11528_heldout_roots_available": ((stage11528.get("stage11527_gate") or {}).get("heldout_roots_available")),
            "stage11528_heldout_roots_required": ((stage11528.get("stage11527_gate") or {}).get("heldout_roots_required")),
            "queue_items": len(work_items),
            "preferred_new_family_items": len(preferred_new),
            "qa_dependency_blocked_items": len(qa_blocked),
            "protected_existing_heldout_family_items": len(protected),
        },
        "recommended_order": [
            "Materialize openclaw_clawhub, dspy, and ai_town first because they add new repo families.",
            "Use at least some of those new families as sealed heldout to close the heldout-root shortfall.",
            "Repair qa_lab dependency setup only after the new-family queue is underway.",
            "Do not train on existing Llama Stack or OpenHands heldout roots.",
        ],
        "work_items": work_items,
        "claim_boundary": [
            "This is a queue for Web root materialization, not a training package.",
            "Stage11527 minimum gate is still unmet until enough queued roots are materialized and audited.",
            "Existing OpenHands-only support probes regressed canaries, so the next package must be multi-family.",
        ],
        "source_artifacts": {
            "stage11346_queue": rel(STAGE11346),
            "stage11353_execution": rel(STAGE11353),
            "stage11528_supply_audit": rel(STAGE11528),
        },
        "outputs": {"summary": rel(SUMMARY), "queue": rel(QUEUE)},
    }
    write_jsonl(QUEUE, work_items)
    write_json(SUMMARY, summary)
    SUMMARIES.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(SUMMARY, SUMMARIES / f"{NAME}.json")
    print(json.dumps({"decision": summary["decision"], "metrics": summary["metrics"], "recommended_order": summary["recommended_order"], "top_work_items": work_items[:5]}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
