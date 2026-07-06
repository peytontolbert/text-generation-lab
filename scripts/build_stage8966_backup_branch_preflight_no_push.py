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
STAGE = 8966
NAME = "stage8966_backup_branch_preflight_no_push"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "BACKUP_BRANCH_PREFLIGHT_NO_PUSH_STAGE8966.md"
SPINE = ROOT / "docs" / "MODEL_STACK_SPINE.md"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
PREFLIGHT = OUT_DIR / "backup_branch_preflight_no_push.json"
SOURCE_SUMMARY = ROOT / "runs/summaries/stage8965_registry_spine_reconciliation_after_focused_manifest_audit.json"

EXPECTED_REMOTE = "https://github.com/peytontolbert/text-generation-lab.git"

FORBIDDEN_BY_PREFLIGHT = [
    "git_add",
    "git_commit",
    "git_push",
    "network_upload",
    "huggingface_upload",
    "delete_files",
    "cleanup",
    "train_model",
    "mine_data",
]

BACKUP_CATEGORIES = [
    "docs",
    "runs/summaries",
    "runs/local/artifacts",
    "scripts",
    "tests",
    "runs/local/manifests",
]


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def git_output(args: list[str]) -> str:
    return subprocess.check_output(["git", *args], cwd=ROOT, text=True).strip()


def parse_status_lines(lines: list[str]) -> dict[str, Any]:
    status_counts: Counter[str] = Counter()
    category_counts: Counter[str] = Counter()
    total = 0
    for line in lines:
        if not line.strip():
            continue
        total += 1
        status = line[:2]
        path = line[3:] if len(line) > 3 else ""
        status_counts[status] += 1
        category = "other"
        for candidate in BACKUP_CATEGORIES:
            if path == candidate or path.startswith(candidate + "/"):
                category = candidate
                break
        category_counts[category] += 1
    return {
        "total_changed_paths": total,
        "status_counts": dict(sorted(status_counts.items())),
        "category_counts": dict(sorted(category_counts.items())),
    }


def build_preflight(registry: dict[str, Any]) -> dict[str, Any]:
    source = load_json(SOURCE_SUMMARY)
    branch = git_output(["branch", "--show-current"])
    remote_text = git_output(["remote", "-v"])
    status_text = git_output(["status", "--short"])
    status_lines = status_text.splitlines() if status_text else []
    status = parse_status_lines(status_lines)
    checks = {
        "source_stage8965_passed": source.get("passed") is True,
        "current_branch_is_recovery_branch": branch.startswith("recovery/"),
        "origin_remote_points_to_expected_repo": EXPECTED_REMOTE in remote_text,
        "changed_paths_present": status["total_changed_paths"] > 0,
        "recovery_categories_present": all(key in status["category_counts"] for key in ["docs", "runs/summaries", "runs/local/artifacts", "scripts", "tests"]),
        "forbidden_operations_recorded": len(FORBIDDEN_BY_PREFLIGHT) >= 9,
        "no_git_write_performed": True,
        "no_network_upload_performed": True,
        "authority_counts_zero": not any(((registry.get("metrics") or {}).get("authority_counts") or {}).get(key, 0) for key in AUTHORITY_CLOSED),
        "registry_frontier_stage8965": int((registry.get("metrics") or {}).get("latest_stage", -1)) == 8965,
    }
    return {
        "stage": STAGE,
        "stage_name": NAME,
        "status": "BACKUP_PREFLIGHT_NO_PUSH",
        "branch": branch,
        "remote_text": remote_text,
        "expected_remote": EXPECTED_REMOTE,
        "status_summary": status,
        "forbidden_by_preflight": FORBIDDEN_BY_PREFLIGHT,
        "checks": checks,
        "metrics": {
            "changed_paths": status["total_changed_paths"],
            "changed_categories": len(status["category_counts"]),
            "forbidden_operations": len(FORBIDDEN_BY_PREFLIGHT),
            "git_add_performed": False,
            "git_commit_performed": False,
            "git_push_performed": False,
            "network_upload_performed": False,
            "huggingface_upload_performed": False,
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
        "decision": "Backup preflight is ready: recovery changes are on a recovery branch with the expected GitHub remote, but no git add/commit/push or network upload has been performed by this stage.",
    }


def validate_preflight(card: dict[str, Any], registry: dict[str, Any]) -> list[str]:
    failures = [key for key, value in card["checks"].items() if value is not True]
    if any((card.get("authority") or {}).values()):
        failures.append("authority_open")
    latest = int((registry.get("metrics") or {}).get("latest_stage", -1))
    if latest not in {8965, STAGE}:
        failures.append(f"unexpected_registry_frontier:{latest}")
    for key in [
        "git_add_performed",
        "git_commit_performed",
        "git_push_performed",
        "network_upload_performed",
        "huggingface_upload_performed",
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
    card = build_preflight(registry)
    failures = validate_preflight(card, registry)
    PREFLIGHT.write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
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
        "artifacts": {"preflight": str(PREFLIGHT.relative_to(ROOT))},
        "decision": card["decision"],
        "next_best_step": "If the user explicitly wants backup, run intentional git add/commit/push on the recovery branch. Otherwise continue no-execution recovery.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage8966 Backup Branch Preflight No-Push",
        "",
        f"Passed: `{summary['passed']}`",
        "",
        "This stage records backup readiness only. It does not run `git add`, commit, push, or any network upload.",
        "",
        f"Branch: `{card['branch']}`",
        f"Changed paths: `{card['metrics']['changed_paths']}`",
        f"Git push performed: `{card['metrics']['git_push_performed']}`",
        "",
        "No mining, model execution, decoder CE, denoise CE, runtime, checkpoint export, or training is authorized.",
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
    marker = "## Stage8966 Backup Branch Preflight No-Push"
    spine_text = SPINE.read_text(encoding="utf-8") if SPINE.exists() else ""
    if marker not in spine_text:
        SPINE.write_text(spine_text.rstrip() + "\n\n" + "\n".join([
            marker,
            "",
            "Stage8966 records backup readiness for the recovery branch. It does not stage, commit, push, upload, mine, execute models, or train.",
            "",
        ]), encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))
    raise SystemExit(0 if summary["passed"] else 1)


if __name__ == "__main__":
    main()
