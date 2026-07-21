#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12342_openclaw_access_verifier_executor"
OUT = ROOT / "runs/local/artifacts" / STAGE
SUMMARY = ROOT / "runs/summaries" / f"{STAGE}.json"
REPO = Path("/data/repositories/openclaw__clawhub")
STDOUT = OUT / "logs/openclaw_access_test_stdout.log"
STDERR = OUT / "logs/openclaw_access_test_stderr.log"
COMMAND = "./node_modules/.bin/vitest run convex/lib/access.test.ts"
SOURCE_FILES = ["convex/lib/access.ts", "convex/schema.ts", "package.json"]
TEST_FILES = ["convex/lib/access.test.ts"]


def sha_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def sha_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def git_output(args: list[str]) -> str:
    try:
        return subprocess.check_output(["git", "-C", str(REPO), *args], text=True, stderr=subprocess.DEVNULL).strip()
    except Exception:
        return ""


def parse_counts(stdout: str) -> dict[str, int | None]:
    file_match = re.search(r"Test Files\s+(\d+)\s+passed", stdout)
    test_match = re.search(r"Tests\s+(\d+)\s+passed", stdout)
    return {
        "test_files_passed": int(file_match.group(1)) if file_match else None,
        "tests_passed": int(test_match.group(1)) if test_match else None,
    }


def refs(paths: list[str], full: bool = False) -> list[str]:
    out = []
    for rel in paths:
        path = REPO / rel
        if path.exists() and "node_modules" not in rel:
            digest = sha_file(path)
            out.append(f"{rel}@{digest if full else digest[:12]}")
    return out


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    stdout = STDOUT.read_text(encoding="utf-8", errors="replace") if STDOUT.exists() else ""
    stderr = STDERR.read_text(encoding="utf-8", errors="replace") if STDERR.exists() else ""
    counts = parse_counts(stdout)
    passed = bool(counts.get("test_files_passed") and counts.get("tests_passed") and not stderr.strip())
    summary = {
        "stage": STAGE,
        "decision": "openclaw_access_focused_verifier_passed" if passed else "openclaw_access_focused_verifier_not_admissible",
        "training_allowed": False,
        "claim_boundary": "Verifier execution evidence only. No row admitted by this stage.",
        "repo_family": "openclaw/clawhub",
        "language_family": "web_js_ts_html",
        "repo_path": str(REPO),
        "commit_sha": git_output(["rev-parse", "HEAD"]),
        "git_status_short_sha256": sha_text(git_output(["status", "--short"])),
        "focused_verifier_command": COMMAND,
        "focused_verifier_cwd": str(REPO),
        "focused_verifier_exit_code": 0 if passed else 1,
        "focused_verifier_passed": passed,
        "verifier_result_summary": counts,
        "stdout_log": str(STDOUT),
        "stderr_log": str(STDERR),
        "stdout_sha256": sha_text(stdout) if stdout else None,
        "stderr_sha256": sha_text(stderr) if stderr else None,
        "source_hash_refs": refs(SOURCE_FILES),
        "test_hash_refs": refs(TEST_FILES, full=True),
        "blocked_reasons_before_row_admission": [
            "needs_gold_perspective_answers",
            "needs_selected_changed_path",
            "needs_selected_symptom_or_call_path_evidence",
            "needs_anti_cheat_renderer",
            "needs_lineage_audit",
        ],
    }
    if not passed:
        summary["blocked_reasons_before_row_admission"].insert(0, "focused_verifier_nonzero_or_not_run")
    (OUT / "openclaw_access_verifier_execution.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
