#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = 10264
NAME = "stage10264_code_assist_web_commit_bundle_candidates"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
BUNDLES_JSON = OUT_DIR / "code_assist_web_commit_bundle_candidates.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"

REPO = Path("/data/code_assist")
MANIFEST = ROOT / "runs/local/artifacts/stage10263_code_assist_web_git_history_candidate_manifest/code_assist_web_git_history_candidate_manifest.json"

SELECTED_COMMITS = [
    "a305b18b7f855b45324e9fceda995e87a3536ef6",
    "b94562d7b7088a75277790b983f2eae74e381897",
]
SELECTED_TESTS = [
    "tests/integration/test_dashboard_api.py",
]
PERSPECTIVES = [
    "symptom_localization",
    "evidence_citation",
    "alternative_hypothesis_elimination",
    "patch_impact",
    "verifier_outcome",
    "minimal_fix_selection",
    "regression_risk",
    "abstention_insufficient_evidence",
]


def _run(*args: str) -> str:
    proc = subprocess.run(list(args), check=True, capture_output=True, text=True)
    return proc.stdout


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="ignore")


def _snippet(text: str, limit: int = 1400) -> str:
    text = str(text).strip()
    return text if len(text) <= limit else text[: limit - 3].rstrip() + "..."


def _git_show_file(commit: str, rel_path: str) -> str:
    try:
        return _run("git", "-C", str(REPO), "show", f"{commit}:{rel_path}")
    except Exception:
        return ""


def _git_diff_for_path(commit: str, rel_path: str) -> str:
    try:
        return _run("git", "-C", str(REPO), "show", "--format=", "--unified=6", commit, "--", rel_path)
    except Exception:
        return ""


def _current_excerpt(rel_path: str, anchor: str | None = None, radius: int = 22) -> str:
    path = REPO / rel_path
    lines = _read(path).splitlines()
    idx = 0
    if anchor:
        for i, line in enumerate(lines):
            if anchor in line:
                idx = i
                break
    start = max(0, idx - radius)
    end = min(len(lines), idx + radius)
    return _snippet("\n".join(lines[start:end]))


def _prompt_task(perspective: str) -> str:
    tasks = {
        "symptom_localization": "Choose the most likely edit target from the visible dashboard behavior and API evidence.",
        "evidence_citation": "Name the visible fact that best supports the chosen edit target.",
        "alternative_hypothesis_elimination": "Explain why a plausible competing UI surface is less justified.",
        "patch_impact": "Compare candidate edits by likely behavior change and blast radius.",
        "verifier_outcome": "Choose the most relevant visible verification target for the proposed fix.",
        "minimal_fix_selection": "Choose the smallest maintainable intervention supported by the evidence.",
        "regression_risk": "Identify the main regression risk if the chosen fix is wrong or too broad.",
        "abstention_insufficient_evidence": "Decide whether the visible evidence supports a singleton answer or whether abstention is more honest.",
    }
    return tasks[perspective]


def _bundle_from_commit(meta: dict[str, Any]) -> dict[str, Any]:
    commit = str(meta["commit"])
    ui_paths = list(meta["ui_paths"])
    primary_path = ui_paths[0]
    diff_blocks = []
    for rel_path in ui_paths[:4]:
        diff_text = _git_diff_for_path(commit, rel_path)
        if diff_text.strip():
            diff_blocks.append(
                {
                    "path": rel_path,
                    "source_type": "git_commit",
                    "retrieval_reason": "commit_diff",
                    "distance_from_seed": 0,
                    "text": _snippet(diff_text, 1500),
                }
            )

    nearby = []
    for rel_path in ui_paths[:4]:
        current_text = _current_excerpt(rel_path)
        if current_text.strip():
            nearby.append(
                {
                    "path": rel_path,
                    "source_type": "local_repo",
                    "retrieval_reason": "current_file_context",
                    "distance_from_seed": 1,
                    "text": current_text,
                }
            )

    verifier = []
    for rel_path in SELECTED_TESTS:
        verifier.append(
            {
                "path": rel_path,
                "source_type": "local_repo",
                "retrieval_reason": "dashboard_verifier_anchor",
                "distance_from_seed": 1,
                "text": _current_excerpt(rel_path, anchor="def test_dashboard_add_project_then_list", radius=36),
            }
        )

    candidate_paths = ui_paths[:]
    evidence = {
        "candidate_change_surface": diff_blocks,
        "nearby_definition_or_usage_context": nearby[:2],
        "symptom_or_call_path_analogue": nearby[2:4] if len(nearby) > 2 else nearby[:1],
        "verifier_and_test_constraint": verifier,
        "algorithmic_background_reference": [],
        "external_analogue_reference": [],
    }
    visible_keys = sorted(key for key, value in evidence.items() if value)
    bundle_id = f"stage10264::code_assist_git_commit::{commit[:12]}::web_js_ts_html"
    perspective_rows = []
    for perspective in PERSPECTIVES:
        perspective_rows.append(
            {
                "bundle_id": bundle_id,
                "language_family": "web_js_ts_html",
                "perspective": perspective,
                "prompt_contract": {
                    "task": _prompt_task(perspective),
                    "candidate_paths": candidate_paths,
                    "selected_tests": list(SELECTED_TESTS),
                    "visible_evidence_keys": visible_keys,
                    "abstention_option_required": perspective == "abstention_insufficient_evidence",
                },
                "gold_answer_status": "pending_ai_adjudication",
                "eligible_for_training_or_scoring_now": False,
            }
        )

    return {
        "bundle_id": bundle_id,
        "root_example_id": f"code_assist_web_commit_{commit[:12]}",
        "repo_id": "code_assist",
        "language_family": "web_js_ts_html",
        "source_route": "GIT_HISTORY_COMMIT_LEVEL_WEB_BUNDLE",
        "commit": commit,
        "commit_subject": meta["subject"],
        "commit_author_date": meta["author_date"],
        "seed_paths": candidate_paths,
        "candidate_paths": candidate_paths,
        "selected_tests": list(SELECTED_TESTS),
        "claim_boundary": {
            "source_heldout_headline_admissible": False,
            "same_repo_overlap_risk": True,
            "train_support_candidate": True,
            "repo_overlap_stress_eval_candidate": True,
            "supports_training_or_scoring_now": False,
            "requires_bundle_specific_anti_cheat_review": True,
            "requires_ai_maintainer_gold_adjudication": True,
            "reason_not_source_heldout": "same_repo_family_as_consumed_web_frontier",
        },
        "maintainer_visible_evidence": evidence,
        "perspective_rows": perspective_rows,
    }


def build() -> dict[str, Any]:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    by_commit = {str(row["commit"]): row for row in manifest.get("candidate_commits") or []}
    bundles = []
    missing = []
    for commit in SELECTED_COMMITS:
        meta = by_commit.get(commit)
        if not meta:
            missing.append(commit)
            continue
        bundles.append(_bundle_from_commit(meta))
    payload = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "passed": len(missing) == 0,
        "inputs": {
            "commit_manifest": str(MANIFEST.relative_to(ROOT)),
            "repo": str(REPO),
        },
        "metrics": {
            "requested_commits": len(SELECTED_COMMITS),
            "bundles_emitted": len(bundles),
            "missing_commits": len(missing),
        },
        "missing_commits": missing,
        "bundle_candidates": bundles,
        "decision": (
            "Compiled two code_assist UI commits into maintainer-grade web bundle candidates with real commit diffs, "
            "current file context, and dashboard API verifier anchors. These are repo-overlap support candidates, not source-heldout headline evidence."
        ),
        "next_best_step": (
            "Run AI maintainer rubric, anti-cheat, and gold adjudication on these two commit-level bundles, then use admitted rows for standalone web support "
            "and harness stress-eval while keeping source-heldout claim boundaries strict."
        ),
    }
    return payload


def main() -> None:
    payload = build()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    BUNDLES_JSON.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    SUMMARY.write_text(
        json.dumps(
            {
                "stage": STAGE,
                "stage_name": NAME,
                "passed": payload["passed"],
                "artifact": str(BUNDLES_JSON.relative_to(ROOT)),
                "decision": payload["decision"],
                "next_best_step": payload["next_best_step"],
                "metrics": payload["metrics"],
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    print(json.dumps({"stage": STAGE, "passed": payload["passed"], "artifact": str(BUNDLES_JSON.relative_to(ROOT)), "metrics": payload["metrics"]}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
