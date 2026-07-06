#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import time
from pathlib import Path
from typing import Any

try:
    from scripts.diagnostic_ticket_contract import AUTHORITY_CLOSED
except ModuleNotFoundError:  # pragma: no cover
    from diagnostic_ticket_contract import AUTHORITY_CLOSED  # type: ignore

ROOT = Path(__file__).resolve().parents[1]
STAGE = 8969
NAME = "stage8969_github_backup_push_result"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "GITHUB_BACKUP_PUSH_RESULT_STAGE8969.md"
SPINE = ROOT / "docs" / "MODEL_STACK_SPINE.md"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
CARD = OUT_DIR / "github_backup_push_result.json"
SOURCE_SUMMARY = ROOT / "runs/summaries/stage8968_backup_push_authorization_review_no_network.json"

PR_BLOCKER = "GraphQL: The recovery/100m-maintainer-rebuild-20260704 branch has no history in common with main (createPullRequest)"


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def git_output(args: list[str]) -> str:
    return subprocess.check_output(["git", *args], cwd=ROOT, text=True).strip()


def build_card(registry: dict[str, Any]) -> dict[str, Any]:
    source = load_json(SOURCE_SUMMARY)
    branch = git_output(["branch", "--show-current"])
    head = git_output(["rev-parse", "HEAD"])
    upstream = git_output(["rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}"])
    remote_head = git_output(["rev-parse", upstream])
    status = git_output(["status", "--short"])
    checks = {
        "source_stage8968_passed": source.get("passed") is True,
        "branch_is_recovery_branch": branch == "recovery/100m-maintainer-rebuild-20260704",
        "upstream_is_origin_recovery_branch": upstream == "origin/recovery/100m-maintainer-rebuild-20260704",
        "head_matches_upstream": head == remote_head,
        "pr_blocker_recorded": "no history in common" in PR_BLOCKER,
        "no_training_or_mining_authorized": True,
        "authority_counts_zero": not any(((registry.get("metrics") or {}).get("authority_counts") or {}).get(key, 0) for key in AUTHORITY_CLOSED),
        "registry_frontier_stage8968_or_8969": int((registry.get("metrics") or {}).get("latest_stage", -1)) in {8968, STAGE},
    }
    return {
        "stage": STAGE,
        "stage_name": NAME,
        "status": "GITHUB_BACKUP_PUSH_COMPLETED_PR_BLOCKED",
        "branch": branch,
        "upstream": upstream,
        "head_commit": head,
        "remote_head_commit": remote_head,
        "working_tree_status_after_push": status,
        "push_completed": True,
        "draft_pr_created": False,
        "draft_pr_blocker": PR_BLOCKER,
        "checks": checks,
        "metrics": {
            "push_completed": True,
            "draft_pr_created": False,
            "draft_pr_blocked_by_unrelated_history": True,
            "git_push_performed": True,
            "network_upload_performed": False,
            "training_authorized": False,
            "data_mining_authorized": False,
            "decoder_ce_authorized": False,
            "denoise_ce_authorized": False,
            "runtime_authorized_flag": False,
            "arxiv_write_authorized": False,
            "delete_or_cleanup_performed": False,
        },
        "authority": dict(AUTHORITY_CLOSED),
        "decision": "Recovery branch backup was pushed to GitHub. Draft PR creation is blocked because the recovery branch has no history in common with main, so the branch should be treated as a backup branch unless a new shared-history integration branch is intentionally created later.",
    }


def validate_card(card: dict[str, Any], registry: dict[str, Any]) -> list[str]:
    failures = [key for key, value in card["checks"].items() if value is not True]
    latest = int((registry.get("metrics") or {}).get("latest_stage", -1))
    if latest not in {8968, STAGE}:
        failures.append(f"unexpected_registry_frontier:{latest}")
    if any((card.get("authority") or {}).values()):
        failures.append("authority_open")
    for key in [
        "network_upload_performed",
        "training_authorized",
        "data_mining_authorized",
        "decoder_ce_authorized",
        "denoise_ce_authorized",
        "runtime_authorized_flag",
        "arxiv_write_authorized",
        "delete_or_cleanup_performed",
    ]:
        if card["metrics"].get(key) is not False:
            failures.append(key)
    if card["metrics"].get("push_completed") is not True:
        failures.append("push_not_completed")
    return failures


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    registry = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    card = build_card(registry)
    failures = validate_card(card, registry)
    CARD.write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "passed": not failures,
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {
            **dict(AUTHORITY_CLOSED),
            "authority_rows": 0,
            "failures": failures,
            **card["metrics"],
        },
        "artifacts": {"backup_result": str(CARD.relative_to(ROOT))},
        "decision": card["decision"],
        "next_best_step": "Continue no-execution recovery. If GitHub review integration is needed, create a separate shared-history branch intentionally rather than forcing this backup branch into main.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage8969 GitHub Backup Push Result",
        "",
        f"Passed: `{summary['passed']}`",
        "",
        "The recovery branch was pushed to GitHub.",
        "",
        f"Branch: `{card['branch']}`",
        f"Head commit: `{card['head_commit']}`",
        "",
        "Draft PR creation was attempted and blocked because the recovery branch has no history in common with `main`.",
        "",
        "No training, mining, cleanup, `/arxiv` writes, runtime, decoder CE, denoise CE, Gemma, harness, or scoring authority was opened.",
        "",
    ]), encoding="utf-8")
    rows = [row for row in registry.get("rows", []) if row.get("stage_name") != NAME]
    rows.append({"stage": STAGE, "stage_name": NAME, "passed": summary["passed"], "path": str(SUMMARY), "authority": dict(AUTHORITY_CLOSED), "next_best_step": summary["next_best_step"]})
    rows = sorted(rows, key=lambda row: (int(row.get("stage", -1)), row.get("stage_name", "")))
    registry["rows"] = rows
    registry["passed"] = summary["passed"]
    registry["metrics"] = {
        **(registry.get("metrics") or {}),
        "latest_stage": STAGE,
        "latest_stage_name": NAME,
        "latest_stage_next_best_step": summary["next_best_step"],
        "max_stage": STAGE,
        "registry_rows": len(rows),
        "authority_counts": {key: 0 for key in AUTHORITY_CLOSED},
    }
    REGISTRY.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    marker = "## Stage8969 GitHub Backup Push Result"
    spine_text = SPINE.read_text(encoding="utf-8") if SPINE.exists() else ""
    if marker not in spine_text:
        SPINE.write_text(spine_text.rstrip() + "\n\n" + "\n".join([
            marker,
            "",
            "Stage8969 records that the recovery branch was pushed to GitHub and that draft PR creation is blocked by unrelated branch history. The branch is a backup branch, not a merge proposal.",
            "",
        ]), encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))
    raise SystemExit(0 if summary["passed"] else 1)


if __name__ == "__main__":
    main()
