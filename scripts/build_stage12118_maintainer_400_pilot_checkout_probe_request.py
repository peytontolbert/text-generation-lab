#!/usr/bin/env python3
"""Build a capped checkout/probe request for the Maintainer-400 pilot."""
from __future__ import annotations

import json
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "runs/local/artifacts"
SUM = ROOT / "runs/summaries"
STAGE = 12118
NAME = "stage12118_maintainer_400_pilot_checkout_probe_request"
OUT = ART / NAME
SUMMARY = OUT / "maintainer_400_pilot_checkout_probe_request.json"
MIRROR = SUM / f"{NAME}.json"
QUEUE = OUT / "pilot_checkout_probe_targets.jsonl"
OVERFLOW = OUT / "pilot_checkout_probe_overflow.jsonl"

STAGE12117_SUMMARY = SUM / "stage12117_maintainer_400_pilot_candidate_intake_audit.json"
STAGE12117_ADMITTED = ART / "stage12117_maintainer_400_pilot_candidate_intake_audit/admitted_pilot_acquisition_targets.jsonl"

TARGET_PER_LANGUAGE = 50


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, sort_keys=True) + "\n")


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def slug(value: Any) -> str:
    return re.sub(r"[^a-zA-Z0-9]+", "_", str(value or "")).strip("_")


def repo_name(row: dict[str, Any]) -> str:
    target = str(row.get("source_path_or_acquisition_target") or "")
    if target.startswith("https://github.com/"):
        return target.removeprefix("https://github.com/").strip("/")
    return str(row.get("repo_family") or target).strip("/")


def checkout_path(repo: str) -> str:
    return f"/data/tmp/stage12118_maintainer_400_repos/{slug(repo)}"


def probe_plan(language: str, path: str) -> dict[str, Any]:
    if language == "python":
        return {
            "manifest_probe": [["test", "-f", "pyproject.toml"], ["rg", "--files", "-g", "*.py"]],
            "verifier_probe": [["python", "-m", "pytest", "--collect-only", "-q", "-o", "addopts="], ["python", "-m", "pytest", "-q", "-o", "addopts="]],
            "not_exercised_probe": [["python", "-m", "pytest", "-q", "-o", "addopts=", "-k", "stage121_python_nonexistent_filter"]],
            "claim_boundary": "May become selected_test_anchor only if pytest collection/execution logs identify concrete selected tests.",
        }
    if language == "rust":
        return {
            "manifest_probe": [["test", "-f", "Cargo.toml"], ["rg", "--files", "-g", "*.rs"]],
            "verifier_probe": [["cargo", "test", "--locked"], ["cargo", "test", "--workspace", "--locked"]],
            "not_exercised_probe": [["cargo", "test", "--locked", "stage12118_nonexistent_filter"]],
            "claim_boundary": "May become selected_test_anchor only if cargo discovers/runs real tests and logs are captured.",
        }
    if language == "c_cpp":
        return {
            "manifest_probe": [["test", "-f", "CMakeLists.txt"], ["rg", "--files", "-g", "*.c", "-g", "*.cc", "-g", "*.cpp", "-g", "*.h", "-g", "*.hpp"]],
            "verifier_probe": [["cmake", "-S", ".", "-B", f"{path}/build"], ["cmake", "--build", f"{path}/build", "--parallel", "2"], ["ctest", "--test-dir", f"{path}/build", "--output-on-failure"]],
            "not_exercised_probe": [["ctest", "--test-dir", f"{path}/build", "-R", "stage12118_nonexistent_filter"]],
            "claim_boundary": "Build-only evidence remains build/static scoped unless ctest or another concrete selected verifier is captured.",
        }
    return {
        "manifest_probe": [["test", "-f", "package.json"], ["rg", "--files", "-g", "*.ts", "-g", "*.tsx", "-g", "*.js", "-g", "*.jsx"]],
        "verifier_probe": [["npm", "test"], ["pnpm", "test"], ["yarn", "test"]],
        "not_exercised_probe": [["npm", "test", "--", "stage12118_nonexistent_filter"]],
        "claim_boundary": "May become selected_test_anchor only if package test script and concrete verifier output are captured.",
    }


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    stage12117 = read_json(STAGE12117_SUMMARY)
    rows = read_jsonl(STAGE12117_ADMITTED)
    selected = []
    overflow = []
    counts = Counter()

    for row in sorted(rows, key=lambda r: (str(r.get("language")), str(r.get("repo_family")))):
        language = str(row.get("language"))
        repo = repo_name(row)
        path = checkout_path(repo)
        item = {
            "stage12118_pilot_checkout_probe": True,
            "queue_id": f"stage12118::{language}::{counts[language] + 1:03d}::{slug(repo)}",
            "language": language,
            "repo_family": row.get("repo_family"),
            "repo_url": row.get("source_path_or_acquisition_target"),
            "checkout_path": path,
            "checkout_command": ["git", "clone", "--depth", "1", row.get("source_path_or_acquisition_target"), path],
            "probe_plan": probe_plan(language, path),
            "source_row": row,
            "do_not_train": True,
            "split_status": "pilot_checkout_probe_only",
            "admission_after_probe_requires": [
                "checkout succeeds",
                "canonical remote and commit SHA captured",
                "manifest/source markers captured",
                "verifier/build command output captured",
                "selected-test claims only if concrete test/verifier exists",
                "semantic candidate objects built with opaque shuffled non-singleton options",
                "target value not visible before options",
                "root lineage rechecked against protected stages",
            ],
        }
        if counts[language] < TARGET_PER_LANGUAGE:
            selected.append(item)
            counts[language] += 1
        else:
            overflow.append({**item, "overflow_reason": "language_target_cap_reached"})

    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "decision": "maintainer_400_pilot_checkout_probe_request_ready",
        "do_not_train": True,
        "stage12117_input": {
            "summary": rel(STAGE12117_SUMMARY),
            "admitted_candidates": stage12117["admitted_candidates"],
            "admitted_by_language": stage12117["admitted_by_language"],
        },
        "target_per_language": TARGET_PER_LANGUAGE,
        "selected_targets": len(selected),
        "selected_by_language": dict(sorted(counts.items())),
        "overflow_targets": len(overflow),
        "claim_boundary": [
            "Stage12118 items are checkout/probe work only, not task rows.",
            "No selected-test row can be admitted without concrete executed verifier evidence.",
            "Overflow remains acquisition buffer and must not bypass audit/cap controls.",
        ],
        "next_stage_recommendation": {
            "stage": "stage12119_execute_maintainer_400_pilot_checkout_probe_batch",
            "action": "Execute selected checkout/probe targets in resource-limited batches, then run post-probe admission and row materialization.",
            "network_required": True,
            "gpu_required": False,
        },
        "outputs": {
            "summary": rel(SUMMARY),
            "summary_mirror": rel(MIRROR),
            "checkout_probe_queue": rel(QUEUE),
            "overflow": rel(OVERFLOW),
        },
    }
    write_jsonl(QUEUE, selected)
    write_jsonl(OVERFLOW, overflow)
    write_json(SUMMARY, summary)
    write_json(MIRROR, summary)
    print(json.dumps({
        "decision": summary["decision"],
        "selected_targets": len(selected),
        "selected_by_language": summary["selected_by_language"],
        "overflow_targets": len(overflow),
    }, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
