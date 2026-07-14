#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "runs/local/artifacts"
STAGE = 11346
NAME = "stage11346_web_source_verifier_review_queue"
OUT = ART / NAME
SUMMARY = OUT / "web_source_verifier_review_queue.json"
OUT_QUEUE = OUT / "web_source_verifier_first_wave_review_queue.jsonl"
SOURCE = ART / "stage11345_local_rust_web_source_acquisition_atlas/local_rust_web_source_candidates.jsonl"


def now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, sort_keys=True) + "\n")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows))


def test_strength(paths: list[str]) -> int:
    score = 0
    for path in paths:
        lower = path.lower()
        if ".test." in lower or ".spec." in lower or lower.endswith(".test.ts") or lower.endswith(".spec.ts"):
            score += 5
        elif "test" in lower or "spec" in lower:
            score += 3
        elif "vitest" in lower or "playwright" in lower or "jest" in lower:
            score += 2
        else:
            score += 1
    return score


def candidate_score(row: dict[str, Any]) -> tuple[int, int, str]:
    tests = row.get("verifier_and_test_constraint_paths") or []
    sources = row.get("candidate_change_surface_paths") or []
    return (test_strength(tests), len(sources), str(row.get("candidate_id")))


def make_review_item(row: dict[str, Any], rank: int) -> dict[str, Any]:
    snippets = row.get("snippets") or {}
    item = {
        "review_item_id": f"stage11346::web_review::{rank:02d}::{row.get('repo_family')}",
        "source_candidate_id": row.get("candidate_id"),
        "language_family": "web_js_ts_html",
        "repo_family": row.get("repo_family"),
        "git_repo_family": row.get("git_repo_family"),
        "repo_path": row.get("repo_path"),
        "git_repo_root": row.get("git_repo_root"),
        "git_head": row.get("git_head"),
        "candidate_change_surface_paths": row.get("candidate_change_surface_paths") or [],
        "verifier_and_test_constraint_paths": row.get("verifier_and_test_constraint_paths") or [],
        "source_snippet_preview": (snippets.get("candidate_change_surface") or {}),
        "verifier_snippet_preview": (snippets.get("verifier_and_test_constraint") or {}),
        "admission_status": "needs_maintainer_gold_and_verifier_transition",
        "train_rows_emitted": 0,
        "strict_eval_eligible": False,
        "review_required_fields": {
            "root_task_or_bug_description": None,
            "selected_changed_path": None,
            "selected_verifier_path": None,
            "selected_symptom_or_call_path_evidence": None,
            "observed_verifier_transition": None,
            "gold_perspective_answers": None,
            "anti_cheat_decision": None,
            "root_split_assignment": None,
        },
        "anti_cheat_precheck": {
            "protected_overlap": row.get("protected_overlap") or {},
            "candidate_has_locked_commit": bool(row.get("git_head")),
            "candidate_has_source_path": bool(row.get("candidate_change_surface_paths")),
            "candidate_has_verifier_or_test_path": bool(row.get("verifier_and_test_constraint_paths")),
            "no_gold_label_present": True,
        },
        "recommended_materialization": {
            "perspectives": [
                "symptom_localization",
                "evidence_citation",
                "verifier_outcome",
                "patch_impact",
                "minimal_fix_selection",
                "abstention_insufficient_evidence",
            ],
            "minimum_before_train": [
                "human_or_ai_maintainer_gold",
                "executed_or_recovered_verifier_output",
                "distinct symptom/call-path evidence",
                "root-disjoint split assignment",
                "prompt-target leak audit",
            ],
        },
    }
    return item


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    rows = [r for r in read_jsonl(SOURCE) if r.get("language_family") == "web_js_ts_html" and not r.get("blockers")]
    by_git_family: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        family = str(row.get("git_repo_family") or row.get("repo_family"))
        by_git_family.setdefault(family, []).append(row)
    selected = []
    for family, family_rows in sorted(by_git_family.items()):
        selected.append(sorted(family_rows, key=candidate_score, reverse=True)[0])
    selected = sorted(selected, key=candidate_score, reverse=True)[:12]
    queue = [make_review_item(row, idx + 1) for idx, row in enumerate(selected)]
    write_jsonl(OUT_QUEUE, queue)
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now(),
        "passed": bool(queue),
        "decision": "web_source_verifier_first_wave_review_queue_ready" if queue else "web_source_verifier_review_queue_empty",
        "counts": {
            "source_candidates": len(rows),
            "git_repo_families": len(by_git_family),
            "review_queue_items": len(queue),
            "by_git_repo_family": dict(sorted(Counter(q["git_repo_family"] for q in queue).items())),
            "train_rows_emitted": 0,
        },
        "admissibility": {
            "scoreable_now": False,
            "trainable_now": False,
            "why": "This is a first-wave review queue. It has locked commits and source/test snippets, but no adjudicated root task, gold answers, or verifier transition yet.",
        },
        "source_artifacts": {"stage11345_candidates": rel(SOURCE)},
        "outputs": {"summary": rel(SUMMARY), "review_queue": rel(OUT_QUEUE)},
        "recommended_next_action": "Complete review_required_fields for 4-8 queue items, then project multi-perspective Web rows with root-level split isolation.",
    }
    write_json(SUMMARY, summary)
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
