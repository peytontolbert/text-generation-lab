#!/usr/bin/env python3
"""Build checkout/probe request for Stage12114 admitted acquisition targets."""
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
STAGE = 12115
NAME = "stage12115_checkout_probe_request"
OUT = ART / NAME
SUMMARY = OUT / "checkout_probe_request.json"
MIRROR = SUM / f"{NAME}.json"
CHECKOUT_QUEUE = OUT / "checkout_targets.jsonl"
LOCAL_PROBE_QUEUE = OUT / "local_probe_targets.jsonl"

STAGE12114_SUMMARY = SUM / "stage12114_fresh_repo_acquisition_intake_audit.json"
STAGE12114_ACQUIRE = ART / "stage12114_fresh_repo_acquisition_intake_audit/admitted_acquisition_targets.jsonl"
STAGE12114_LOCAL = ART / "stage12114_fresh_repo_acquisition_intake_audit/admitted_local_candidates.jsonl"


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        if not line.strip():
            continue
        rows.append(json.loads(line))
    return rows


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


def checkout_dir(repo: str) -> str:
    return f"/data/tmp/stage12115_fresh_repos/{slug(repo)}"


def probe_plan(row: dict[str, Any], checkout_path: str) -> dict[str, Any]:
    language = row.get("language")
    verifier_type = row.get("verifier_type")
    if language == "rust":
        return {
            "manifest_probe": [["test", "-f", "Cargo.toml"], ["rg", "--files", "-g", "*.rs"]],
            "verifier_probe": [["cargo", "test", "--locked"], ["cargo", "test", "--workspace", "--locked"]],
            "not_exercised_probe": [["cargo", "test", "--locked", "stage12115_nonexistent_filter"]],
            "claim_boundary": "May become selected_test_anchor only if cargo discovers/runs real tests and logs are captured.",
        }
    if language == "web_js_ts_html":
        return {
            "manifest_probe": [["test", "-f", "package.json"], ["rg", "--files", "-g", "*.ts", "-g", "*.tsx", "-g", "*.js", "-g", "*.jsx"]],
            "verifier_probe": [["npm", "test"], ["pnpm", "test"], ["yarn", "test"]],
            "not_exercised_probe": [["npm", "test", "--", "stage12115_nonexistent_filter"]],
            "claim_boundary": "May become selected_test_anchor only if package test script and concrete verifier output are captured.",
        }
    if language == "c_cpp":
        return {
            "manifest_probe": [["test", "-f", "CMakeLists.txt"], ["rg", "--files", "-g", "*.c", "-g", "*.cc", "-g", "*.cpp", "-g", "*.h", "-g", "*.hpp"]],
            "verifier_probe": [["cmake", "-S", ".", "-B", f"{checkout_path}/build"], ["cmake", "--build", f"{checkout_path}/build"], ["ctest", "--test-dir", f"{checkout_path}/build", "--output-on-failure"]],
            "not_exercised_probe": [["ctest", "--test-dir", f"{checkout_path}/build", "-R", "stage12115_nonexistent_filter"]],
            "claim_boundary": "Build-only evidence remains static/build scoped unless ctest or another concrete selected verifier is captured.",
        }
    return {
        "manifest_probe": [["rg", "--files"]],
        "verifier_probe": row.get("suggested_commands") or [],
        "not_exercised_probe": [],
        "claim_boundary": f"Verifier scope remains {verifier_type}; do not promote to selected-test without concrete test execution.",
    }


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    stage12114 = read_json(STAGE12114_SUMMARY)
    acquisition_rows = read_jsonl(STAGE12114_ACQUIRE)
    local_rows = read_jsonl(STAGE12114_LOCAL)

    checkout_items = []
    for index, row in enumerate(acquisition_rows, start=1):
        repo = repo_name(row)
        path = checkout_dir(repo)
        item = {
            "stage12115_checkout_probe": True,
            "queue_id": f"stage12115::checkout::{index:03d}::{slug(repo)}",
            "repo_family": row.get("repo_family"),
            "repo_url": row.get("source_path_or_acquisition_target"),
            "checkout_path": path,
            "language": row.get("language"),
            "verifier_type_claimed_by_scout": row.get("verifier_type"),
            "split_status": "needs_acquisition_probe",
            "do_not_train": True,
            "source_row": row,
            "checkout_command": ["git", "clone", "--depth", "1", row.get("source_path_or_acquisition_target"), path],
            "probe_plan": probe_plan(row, path),
            "admission_after_probe_requires": [
                "checkout succeeds",
                "manifest/source markers captured",
                "verifier/build command output captured",
                "root lineage rechecked against protected stages after canonical remote detection",
                "semantic candidate objects built with opaque shuffled non-singleton options",
                "target value not visible before options",
                "selected-test claims only if concrete selected test/verifier exists",
            ],
        }
        checkout_items.append(item)

    local_items = []
    for index, row in enumerate(local_rows, start=1):
        path = str(row.get("source_path_or_acquisition_target"))
        item = {
            "stage12115_local_probe": True,
            "queue_id": f"stage12115::local::{index:03d}::{slug(path)[-72:]}",
            "repo_family": row.get("repo_family"),
            "source_path": path,
            "language": row.get("language"),
            "verifier_type_claimed_by_scout": row.get("verifier_type"),
            "split_status": "local_probe_only",
            "do_not_train": True,
            "source_row": row,
            "probe_plan": probe_plan(row, path),
            "admission_after_probe_requires": [
                "local path still exists",
                "manifest/source markers captured",
                "build/config verifier output captured",
                "root lineage rechecked against protected stages",
                "build/static scope not represented as selected-test evidence",
            ],
        }
        local_items.append(item)

    checkout_counts = Counter(item["language"] for item in checkout_items)
    local_counts = Counter(item["language"] for item in local_items)
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "decision": "checkout_probe_request_ready",
        "do_not_train": True,
        "why": [
            "Stage12114 admitted acquisition targets, not train/eval rows.",
            "Checkout/probe is required to turn leads into source-backed verifier evidence.",
            "Local build/config candidates require the same post-probe row admission gates.",
        ],
        "stage12114_input": {
            "summary": rel(STAGE12114_SUMMARY),
            "admitted_acquisition_targets": stage12114["admitted_acquisition_targets"],
            "admitted_local_candidates": stage12114["admitted_local_candidates"],
            "rejected_candidates": stage12114["rejected_candidates"],
        },
        "checkout_targets": len(checkout_items),
        "checkout_targets_by_language": dict(sorted(checkout_counts.items())),
        "local_probe_targets": len(local_items),
        "local_probe_targets_by_language": dict(sorted(local_counts.items())),
        "strict_claim_boundary": [
            "No Stage12115 item is a training row.",
            "No Stage12115 item is a sealed confirmation row.",
            "GitHub acquisition targets are only leads until checkout and verifier logs exist.",
            "Build/static anchors must not be counted as selected-test anchors unless a concrete selected verifier is discovered and executed.",
        ],
        "next_stage_recommendation": {
            "stage": "stage12116_execute_checkout_probe_batch",
            "action": "Execute checkout/probe in a resource-limited batch, then run a post-probe admission audit before row materialization.",
            "network_required": True,
            "gpu_required": False,
        },
        "outputs": {
            "summary": rel(SUMMARY),
            "summary_mirror": rel(MIRROR),
            "checkout_queue": rel(CHECKOUT_QUEUE),
            "local_probe_queue": rel(LOCAL_PROBE_QUEUE),
        },
    }
    write_jsonl(CHECKOUT_QUEUE, checkout_items)
    write_jsonl(LOCAL_PROBE_QUEUE, local_items)
    write_json(SUMMARY, summary)
    write_json(MIRROR, summary)
    print(json.dumps({
        "decision": summary["decision"],
        "checkout_targets": len(checkout_items),
        "checkout_targets_by_language": summary["checkout_targets_by_language"],
        "local_probe_targets": len(local_items),
        "local_probe_targets_by_language": summary["local_probe_targets_by_language"],
        "next_stage": summary["next_stage_recommendation"],
    }, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
