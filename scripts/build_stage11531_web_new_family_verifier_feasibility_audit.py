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
STAGE = 11531
NAME = "stage11531_web_new_family_verifier_feasibility_audit"
OUT = ART / NAME
SUMMARY = OUT / "web_new_family_verifier_feasibility_audit.json"
ROWS = OUT / "web_new_family_verifier_feasibility_rows.jsonl"

PACKETS = ART / "stage11530_web_new_family_materialization_packets/web_new_family_root_packets.jsonl"


def now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


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


def package_root(repo_path: Path) -> Path:
    cur = repo_path
    while cur != cur.parent:
        if (cur / "package.json").exists():
            return cur
        cur = cur.parent
    return repo_path


def load_package_json(path: Path) -> dict[str, Any]:
    pkg = path / "package.json"
    if not pkg.exists():
        return {}
    return json.loads(pkg.read_text(encoding="utf-8", errors="replace"))


def command_for(packet: dict[str, Any], root: Path, pkg: dict[str, Any]) -> str | None:
    family = packet["git_repo_family"]
    verifier_path = packet.get("selected_verifier_path_proposal")
    scripts = pkg.get("scripts") or {}
    if family == "dspy" and scripts.get("test"):
        return f"CI=true npm test -- --watchAll=false {verifier_path}"
    if family == "openclaw_clawhub":
        if "test" in scripts:
            return f"bun run test -- {verifier_path}"
    if family == "ai_town":
        if "build" in scripts:
            return "npm run build"
    return None


def feasibility(packet: dict[str, Any]) -> dict[str, Any]:
    repo_path = Path(str(packet["repo_path"]))
    root = package_root(repo_path)
    pkg = load_package_json(root)
    node_modules = root / "node_modules"
    lockfiles = [name for name in ("package-lock.json", "pnpm-lock.yaml", "yarn.lock", "bun.lock", "bun.lockb") if (root / name).exists()]
    command = command_for(packet, root, pkg)
    blockers = []
    if not pkg:
        blockers.append("missing_package_json")
    if not node_modules.exists():
        blockers.append("dependencies_not_hydrated")
    if not command:
        blockers.append("no_focused_verifier_command_selected")
    if packet.get("git_repo_family") == "ai_town" and packet.get("selected_verifier_path_proposal") == "testing.ts":
        blockers.append("selected_verifier_is_helper_not_test")
    return {
        "root_id": packet["root_id"],
        "git_repo_family": packet["git_repo_family"],
        "repo_family": packet["repo_family"],
        "repo_path": packet["repo_path"],
        "package_root": str(root),
        "package_name": pkg.get("name"),
        "lockfiles_present": lockfiles,
        "node_modules_present": node_modules.exists(),
        "selected_verifier_path": packet.get("selected_verifier_path_proposal"),
        "proposed_verifier_command": command,
        "execution_ready_now": not blockers,
        "blockers": blockers,
        "recommended_next_action": (
            "execute focused verifier"
            if not blockers
            else "hydrate dependencies or choose a stronger selected test before verifier execution"
        ),
    }


def main() -> None:
    packets = load_jsonl(PACKETS)
    rows = [feasibility(packet) for packet in packets]
    ready = [row for row in rows if row["execution_ready_now"]]
    dependency_blocked = [row for row in rows if "dependencies_not_hydrated" in row["blockers"]]
    weak_verifier = [row for row in rows if "selected_verifier_is_helper_not_test" in row["blockers"]]
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now(),
        "passed": bool(rows),
        "decision": "new_web_family_verifier_execution_blocked_by_dependency_hydration"
        if not ready
        else "new_web_family_verifier_execution_ready_for_some_roots",
        "counts": {
            "root_packets": len(rows),
            "execution_ready_now": len(ready),
            "dependency_blocked": len(dependency_blocked),
            "weak_selected_verifier": len(weak_verifier),
        },
        "rows": rows,
        "admission": {
            "trainable_now": False,
            "strict_eval_eligible_now": False,
            "why": "Verifier execution evidence is still absent for all new-family packets.",
        },
        "next_actions": [
            "Hydrate dependencies in a controlled environment for dspy and openclaw_clawhub, then run the proposed focused verifier commands.",
            "Replace ai_town/testing.ts with a real selected test or keep ai_town as source-only diagnostic material.",
            "Do not add Stage11530 row shells to train/eval until a later stage attaches verifier output and gold answers.",
        ],
        "source_artifacts": {"stage11530_packets": rel(PACKETS)},
        "outputs": {"summary": rel(SUMMARY), "rows": rel(ROWS)},
    }
    write_jsonl(ROWS, rows)
    write_json(SUMMARY, summary)
    SUMMARIES.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(SUMMARY, SUMMARIES / f"{NAME}.json")
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
