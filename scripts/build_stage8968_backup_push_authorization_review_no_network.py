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
STAGE = 8968
NAME = "stage8968_backup_push_authorization_review_no_network"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "BACKUP_PUSH_AUTHORIZATION_REVIEW_NO_NETWORK_STAGE8968.md"
SPINE = ROOT / "docs" / "MODEL_STACK_SPINE.md"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
CARD_PATH = OUT_DIR / "backup_push_authorization_review_no_network.json"
SOURCE_SUMMARY = ROOT / "runs/summaries/stage8967_backup_commit_scope_plan_no_write.json"

REQUIRED_EXPLICIT_USER_AUTHORIZATION = [
    "push this recovery branch to GitHub now",
    "backup this recovery branch to GitHub now",
]

ALLOWED_FUTURE_COMMAND_SEQUENCE = [
    "git status --short",
    "git add docs runs/summaries runs/local/artifacts runs/local/manifests scripts tests",
    "git commit -m 'rebuild 100m maintainer recovery artifacts'",
    "git push origin recovery/100m-maintainer-rebuild-20260704",
    "git status --short",
]

FORBIDDEN_WITHOUT_NEW_EXPLICIT_AUTHORIZATION = [
    "git push --force",
    "git reset",
    "git clean",
    "delete_any_path",
    "include_arxiv",
    "include_checkpoints",
    "include_runtime_probe_outputs",
    "upload_to_huggingface",
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


def contains_forbidden_command(commands: list[str]) -> bool:
    forbidden_terms = ["--force", " reset", " clean", " rm ", "rm -", "/arxiv", "checkpoints", "huggingface", "python train", "pytest --run"]
    return any(any(term in command for term in forbidden_terms) for command in commands)


def build_card(registry: dict[str, Any]) -> dict[str, Any]:
    source = load_json(SOURCE_SUMMARY)
    branch = git_output(["branch", "--show-current"])
    remotes = git_output(["remote", "-v"])
    status_text = git_output(["status", "--short"])
    paths = status_paths(status_text)
    checks = {
        "source_stage8967_passed": source.get("passed") is True,
        "branch_is_recovery_branch": branch.startswith("recovery/"),
        "remote_origin_present": "origin" in remotes,
        "changed_paths_present": len(paths) > 0,
        "explicit_authorization_phrases_recorded": len(REQUIRED_EXPLICIT_USER_AUTHORIZATION) >= 2,
        "future_sequence_recorded": len(ALLOWED_FUTURE_COMMAND_SEQUENCE) == 5,
        "future_sequence_has_no_forbidden_terms": not contains_forbidden_command(ALLOWED_FUTURE_COMMAND_SEQUENCE),
        "forbidden_without_new_authorization_recorded": len(FORBIDDEN_WITHOUT_NEW_EXPLICIT_AUTHORIZATION) >= 8,
        "no_git_add_performed": True,
        "no_git_commit_performed": True,
        "no_git_push_performed": True,
        "no_network_upload_performed": True,
        "authority_counts_zero": not any(((registry.get("metrics") or {}).get("authority_counts") or {}).get(key, 0) for key in AUTHORITY_CLOSED),
        "registry_frontier_stage8967_or_8968": int((registry.get("metrics") or {}).get("latest_stage", -1)) in {8967, STAGE},
    }
    return {
        "stage": STAGE,
        "stage_name": NAME,
        "status": "BACKUP_PUSH_AUTHORIZATION_REVIEW_NO_NETWORK",
        "branch": branch,
        "changed_paths": len(paths),
        "required_explicit_user_authorization": REQUIRED_EXPLICIT_USER_AUTHORIZATION,
        "allowed_future_command_sequence": ALLOWED_FUTURE_COMMAND_SEQUENCE,
        "forbidden_without_new_explicit_authorization": FORBIDDEN_WITHOUT_NEW_EXPLICIT_AUTHORIZATION,
        "checks": checks,
        "metrics": {
            "changed_paths": len(paths),
            "explicit_authorization_phrases": len(REQUIRED_EXPLICIT_USER_AUTHORIZATION),
            "allowed_future_commands": len(ALLOWED_FUTURE_COMMAND_SEQUENCE),
            "forbidden_without_new_authorization": len(FORBIDDEN_WITHOUT_NEW_EXPLICIT_AUTHORIZATION),
            "git_add_performed": False,
            "git_commit_performed": False,
            "git_push_performed": False,
            "network_upload_performed": False,
            "delete_or_cleanup_performed": False,
            "training_authorized": False,
            "data_mining_authorized": False,
            "decoder_ce_authorized": False,
            "denoise_ce_authorized": False,
            "runtime_authorized_flag": False,
            "arxiv_write_authorized": False,
        },
        "authority": dict(AUTHORITY_CLOSED),
        "decision": "Backup push remains unauthorized. This review card records the exact future scope and requires an explicit user instruction before any git add, commit, push, or network operation.",
    }


def validate_card(card: dict[str, Any], registry: dict[str, Any]) -> list[str]:
    failures = [key for key, value in card["checks"].items() if value is not True]
    if any((card.get("authority") or {}).values()):
        failures.append("authority_open")
    latest = int((registry.get("metrics") or {}).get("latest_stage", -1))
    if latest not in {8967, STAGE}:
        failures.append(f"unexpected_registry_frontier:{latest}")
    for key in [
        "git_add_performed",
        "git_commit_performed",
        "git_push_performed",
        "network_upload_performed",
        "delete_or_cleanup_performed",
        "training_authorized",
        "data_mining_authorized",
        "decoder_ce_authorized",
        "denoise_ce_authorized",
        "runtime_authorized_flag",
        "arxiv_write_authorized",
    ]:
        if card["metrics"].get(key) is not False:
            failures.append(key)
    return failures


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    registry = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    card = build_card(registry)
    failures = validate_card(card, registry)
    CARD_PATH.write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
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
        "artifacts": {"review_card": str(CARD_PATH.relative_to(ROOT))},
        "decision": card["decision"],
        "next_best_step": "Continue no-execution recovery, or if the user explicitly authorizes backup, run the scoped git add/commit/push sequence recorded by Stage8968.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage8968 Backup Push Authorization Review No-Network",
        "",
        f"Passed: `{summary['passed']}`",
        "",
        "This stage does not run git add, commit, push, upload, cleanup, mining, execution, or training.",
        "",
        "Future backup requires an explicit user instruction such as:",
        *[f"- `{phrase}`" for phrase in REQUIRED_EXPLICIT_USER_AUTHORIZATION],
        "",
        "Allowed future command sequence, only after explicit authorization:",
        *[f"- `{command}`" for command in ALLOWED_FUTURE_COMMAND_SEQUENCE],
        "",
        "Forbidden without a new explicit authorization:",
        *[f"- `{item}`" for item in FORBIDDEN_WITHOUT_NEW_EXPLICIT_AUTHORIZATION],
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
    marker = "## Stage8968 Backup Push Authorization Review No-Network"
    spine_text = SPINE.read_text(encoding="utf-8") if SPINE.exists() else ""
    if marker not in spine_text:
        SPINE.write_text(spine_text.rstrip() + "\n\n" + "\n".join([
            marker,
            "",
            "Stage8968 records a no-network backup authorization review card. Git add/commit/push remain closed unless the user explicitly asks for that backup operation.",
            "",
        ]), encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))
    raise SystemExit(0 if summary["passed"] else 1)


if __name__ == "__main__":
    main()
