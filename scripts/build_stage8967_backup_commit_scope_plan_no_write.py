#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import time
from collections import Counter
from pathlib import Path
from typing import Any

try:
    from scripts.diagnostic_ticket_contract import AUTHORITY_CLOSED
except ModuleNotFoundError:  # pragma: no cover
    from diagnostic_ticket_contract import AUTHORITY_CLOSED  # type: ignore

ROOT = Path(__file__).resolve().parents[1]
STAGE = 8967
NAME = "stage8967_backup_commit_scope_plan_no_write"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "BACKUP_COMMIT_SCOPE_PLAN_NO_WRITE_STAGE8967.md"
SPINE = ROOT / "docs" / "MODEL_STACK_SPINE.md"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
PLAN = OUT_DIR / "backup_commit_scope_plan_no_write.json"
SOURCE_SUMMARY = ROOT / "runs/summaries/stage8966_backup_branch_preflight_no_push.json"

INCLUDE_PREFIXES = [
    "docs/",
    "runs/summaries/",
    "runs/local/artifacts/",
    "runs/local/manifests/",
    "scripts/",
    "tests/",
]

EXCLUDE_PREFIXES = [
    "/arxiv",
    "arxiv/",
    "checkpoints/",
    "runs/local/probes/",
    "runs/local/checkpoints/",
    "wandb/",
    ".venv/",
    "__pycache__/",
]

COMMIT_PLAN_STEPS = [
    "review_scope",
    "stage_recovery_files_only",
    "commit_recovery_snapshot",
    "push_current_recovery_branch",
    "verify_remote_branch",
]

FORBIDDEN_BY_PLAN = [
    "git_add_now",
    "git_commit_now",
    "git_push_now",
    "network_upload",
    "force_push",
    "delete_or_cleanup",
    "include_arxiv",
    "include_checkpoints",
    "include_probe_outputs_from_execution",
    "train_or_mine",
]


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def git_output(args: list[str]) -> str:
    return subprocess.check_output(["git", *args], cwd=ROOT, text=True).strip()


def status_paths(status_text: str) -> list[str]:
    paths = []
    for line in status_text.splitlines():
        if not line.strip():
            continue
        path = line[3:] if len(line) > 2 and line[2] == " " else line[2:]
        if " -> " in path:
            path = path.split(" -> ", 1)[1]
        paths.append(path)
    return paths


def classify_path(path: str) -> str:
    for prefix in EXCLUDE_PREFIXES:
        if path == prefix.rstrip("/") or path.startswith(prefix):
            return "exclude"
    for prefix in INCLUDE_PREFIXES:
        if path.startswith(prefix):
            return prefix.rstrip("/")
    return "review"


def build_plan(registry: dict[str, Any]) -> dict[str, Any]:
    source = load_json(SOURCE_SUMMARY)
    branch = git_output(["branch", "--show-current"])
    remote_text = git_output(["remote", "-v"])
    paths = status_paths(git_output(["status", "--short"]))
    classifications = Counter(classify_path(path) for path in paths)
    include_paths = [path for path in paths if classify_path(path) not in {"exclude", "review"}]
    review_paths = [path for path in paths if classify_path(path) == "review"]
    exclude_paths = [path for path in paths if classify_path(path) == "exclude"]
    checks = {
        "source_stage8966_passed": source.get("passed") is True,
        "branch_is_recovery_branch": branch.startswith("recovery/"),
        "remote_present": "origin" in remote_text,
        "changed_paths_present": len(paths) > 0,
        "include_paths_present": len(include_paths) > 0,
        "exclude_paths_absent": len(exclude_paths) == 0,
        "review_paths_absent": len(review_paths) == 0,
        "commit_plan_steps_recorded": len(COMMIT_PLAN_STEPS) >= 5,
        "forbidden_by_plan_recorded": len(FORBIDDEN_BY_PLAN) >= 9,
        "no_git_write_performed": True,
        "authority_counts_zero": not any(((registry.get("metrics") or {}).get("authority_counts") or {}).get(key, 0) for key in AUTHORITY_CLOSED),
        "registry_frontier_stage8966_or_8967": int((registry.get("metrics") or {}).get("latest_stage", -1)) in {8966, STAGE},
    }
    return {
        "stage": STAGE,
        "stage_name": NAME,
        "status": "BACKUP_COMMIT_SCOPE_PLAN_NO_WRITE",
        "branch": branch,
        "remote_text": remote_text,
        "include_prefixes": INCLUDE_PREFIXES,
        "exclude_prefixes": EXCLUDE_PREFIXES,
        "commit_plan_steps": COMMIT_PLAN_STEPS,
        "forbidden_by_plan": FORBIDDEN_BY_PLAN,
        "path_classification_counts": dict(sorted(classifications.items())),
        "review_paths": review_paths[:100],
        "exclude_paths": exclude_paths[:100],
        "checks": checks,
        "metrics": {
            "changed_paths": len(paths),
            "include_paths": len(include_paths),
            "review_paths": len(review_paths),
            "exclude_paths": len(exclude_paths),
            "commit_plan_steps": len(COMMIT_PLAN_STEPS),
            "forbidden_operations": len(FORBIDDEN_BY_PLAN),
            "git_add_performed": False,
            "git_commit_performed": False,
            "git_push_performed": False,
            "network_upload_performed": False,
            "actual_execution_authorized_next": False,
            "model_execution_attempted": False,
            "runtime_authorized_flag": False,
            "training_authorized": False,
            "data_mining_authorized": False,
            "decoder_ce_authorized": False,
            "denoise_ce_authorized": False,
            "arxiv_read_authorized_for_compiler": False,
            "arxiv_write_authorized": False,
        },
        "authority": dict(AUTHORITY_CLOSED),
        "decision": "Backup commit scope is planned but not executed. All changed paths fall under recovery include prefixes, with no excluded or review paths detected. A future backup step may intentionally stage/commit/push this recovery branch if explicitly requested.",
    }


def validate_plan(card: dict[str, Any], registry: dict[str, Any]) -> list[str]:
    failures = [key for key, value in card["checks"].items() if value is not True]
    if any((card.get("authority") or {}).values()):
        failures.append("authority_open")
    latest = int((registry.get("metrics") or {}).get("latest_stage", -1))
    if latest not in {8966, STAGE}:
        failures.append(f"unexpected_registry_frontier:{latest}")
    for key in [
        "git_add_performed",
        "git_commit_performed",
        "git_push_performed",
        "network_upload_performed",
        "actual_execution_authorized_next",
        "model_execution_attempted",
        "runtime_authorized_flag",
        "training_authorized",
        "data_mining_authorized",
        "decoder_ce_authorized",
        "denoise_ce_authorized",
        "arxiv_read_authorized_for_compiler",
        "arxiv_write_authorized",
    ]:
        if card["metrics"].get(key) is not False:
            failures.append(key)
    return failures


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    registry = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    card = build_plan(registry)
    failures = validate_plan(card, registry)
    PLAN.write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
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
        "artifacts": {"plan": str(PLAN.relative_to(ROOT))},
        "decision": card["decision"],
        "next_best_step": "If the user explicitly requests backup, intentionally run git add/commit/push for this recovery branch. Otherwise continue no-execution recovery.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage8967 Backup Commit Scope Plan No-Write",
        "",
        f"Passed: `{summary['passed']}`",
        "",
        "This stage plans a backup commit scope only. It does not stage, commit, push, upload, delete, mine, execute, or train.",
        "",
        f"Changed paths: `{card['metrics']['changed_paths']}`",
        f"Include paths: `{card['metrics']['include_paths']}`",
        f"Review paths: `{card['metrics']['review_paths']}`",
        f"Git push performed: `{card['metrics']['git_push_performed']}`",
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
    marker = "## Stage8967 Backup Commit Scope Plan No-Write"
    spine_text = SPINE.read_text(encoding="utf-8") if SPINE.exists() else ""
    if marker not in spine_text:
        SPINE.write_text(spine_text.rstrip() + "\n\n" + "\n".join([
            marker,
            "",
            "Stage8967 plans backup commit scope for the recovery branch. It performs no git add, commit, push, upload, cleanup, mining, execution, or training.",
            "",
        ]), encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))
    raise SystemExit(0 if summary["passed"] else 1)


if __name__ == "__main__":
    main()
