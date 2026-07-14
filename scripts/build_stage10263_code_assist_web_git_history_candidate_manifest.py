#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = 10263
NAME = "stage10263_code_assist_web_git_history_candidate_manifest"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
MANIFEST = OUT_DIR / "code_assist_web_git_history_candidate_manifest.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"

REPO = Path("/data/code_assist")
WEB_PATHS = ["src/code_assist/ui", "src/code_assist/ui/dashboard_assets"]
VERIFIER_ANCHORS = [
    "tests/integration/test_dashboard_api.py",
    "tests/e2e/test_orchestrator_e2e.py",
    "tests/e2e/test_orchestrator_agent_driven.py",
    "tests/integration/test_domain_knowledge_context_pack.py",
]
CONSUMED_FAMILY_AUDIT = ROOT / "runs/summaries" / "stage10261_raw_web_source_rescue_audit.json"


def _run(*args: str) -> str:
    proc = subprocess.run(list(args), check=True, capture_output=True, text=True)
    return proc.stdout


def _git_log() -> list[str]:
    out = _run("git", "-C", str(REPO), "log", "--format=%H", "--", *WEB_PATHS)
    return [line.strip() for line in out.splitlines() if line.strip()]


def _git_show_meta(commit: str) -> dict[str, Any]:
    meta = _run("git", "-C", str(REPO), "show", "--quiet", "--format=%H%n%ad%n%s", "--date=iso-strict", commit)
    lines = [line for line in meta.splitlines()]
    return {
        "commit": lines[0] if len(lines) > 0 else commit,
        "author_date": lines[1] if len(lines) > 1 else "",
        "subject": lines[2] if len(lines) > 2 else "",
    }


def _git_changed_paths(commit: str) -> list[str]:
    out = _run("git", "-C", str(REPO), "show", "--pretty=", "--name-only", commit, "--", *WEB_PATHS)
    return [line.strip() for line in out.splitlines() if line.strip()]


def _git_stat(commit: str) -> str:
    return _run("git", "-C", str(REPO), "show", "--stat", "--summary", "--format=", commit, "--", *WEB_PATHS).strip()


def build() -> dict[str, Any]:
    consumed = json.loads(CONSUMED_FAMILY_AUDIT.read_text(encoding="utf-8")) if CONSUMED_FAMILY_AUDIT.exists() else {}
    consumed_repos = set((consumed.get("raw_inventory_findings") or {}).get("distinct_repo_families") or [])

    commits = _git_log()
    candidates: list[dict[str, Any]] = []
    for commit in commits[:8]:
        meta = _git_show_meta(commit)
        changed_paths = _git_changed_paths(commit)
        ui_paths = [path for path in changed_paths if path.startswith("src/code_assist/ui/")]
        if not ui_paths:
            continue
        candidate = {
            "repo_id": "code_assist",
            "commit": meta["commit"],
            "author_date": meta["author_date"],
            "subject": meta["subject"],
            "changed_paths": changed_paths,
            "ui_paths": ui_paths,
            "verifier_anchors": VERIFIER_ANCHORS,
            "git_stat_excerpt": _git_stat(commit),
            "claim_boundary": {
                "source_heldout_headline_admissible": False,
                "same_repo_overlap_risk": True,
                "train_support_candidate": True,
                "repo_overlap_stress_eval_candidate": True,
                "requires_commit_level_split": True,
                "requires_bundle_specific_anti_cheat_review": True
            },
        }
        if "code_assist" in consumed_repos:
            candidate["claim_boundary"]["reason_not_source_heldout"] = (
                "same_repo_family_as_consumed_web_frontier; treat as fresh commit-level root only, not source-heldout repo-family evidence"
            )
        candidates.append(candidate)

    manifest = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "passed": True,
        "inputs": {
            "repo": str(REPO),
            "consumed_family_audit": str(CONSUMED_FAMILY_AUDIT),
        },
        "decision": (
            "code_assist git history contains multiple distinct UI commits that can serve as fresh commit-level web roots. "
            "Because they share the code_assist repo family with the consumed frontier, they should be used first as train-support "
            "or repo-overlap stress-eval candidates, not as source-heldout headline evidence."
        ),
        "metrics": {
            "candidate_commits": len(candidates),
            "repo_family_overlap": True,
        },
        "verifier_anchor_tests": VERIFIER_ANCHORS,
        "candidate_commits": candidates,
        "next_best_step": (
            "Compile 1-2 of these commits into maintainer-grade web root bundles with explicit commit hashes, realistic snippets, "
            "and anti-cheat review; keep them out of source-heldout headline claims until a non-overlapping repo family exists."
        ),
    }
    return manifest


def main() -> None:
    payload = build()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    MANIFEST.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    SUMMARY.write_text(
        json.dumps(
            {
                "stage": STAGE,
                "stage_name": NAME,
                "passed": payload["passed"],
                "artifact": str(MANIFEST.relative_to(ROOT)),
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
    print(json.dumps({"stage": STAGE, "passed": payload["passed"], "artifact": str(MANIFEST.relative_to(ROOT)), "metrics": payload["metrics"]}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
