#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from collections import Counter
from copy import deepcopy
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = 10018
NAME = "stage10018_current_python_gap_successor_request"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
REQUEST = OUT_DIR / "current_python_gap_successor_request.json"
MANIFEST = OUT_DIR / "edit_localization_manifest.jsonl"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "CURRENT_PYTHON_GAP_SUCCESSOR_REQUEST_STAGE10018.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
BASE = ROOT / "runs/local/artifacts/stage10012_quarantined_blended_weak_language_execution_review/review_manifests/edit_localization.jsonl"
COMPARISON = ROOT / "runs/local/artifacts/stage10017_quarantined_same_manifest_comparison_audit/quarantined_same_manifest_comparison_rows.jsonl"


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def display(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def update_registry(summary: dict[str, Any]) -> None:
    registry = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    rows = [row for row in registry.get("rows", []) if row.get("stage") != STAGE and row.get("stage_name") != NAME]
    rows.append({"stage": STAGE, "stage_name": NAME, "passed": summary["passed"], "path": str(SUMMARY), "next_best_step": summary["next_best_step"]})
    registry["rows"] = sorted(rows, key=lambda row: (int(row.get("stage", -1)), row.get("stage_name", "")))
    registry["passed"] = bool(registry["rows"])
    registry["metrics"] = {
        **(registry.get("metrics") or {}),
        "latest_stage": STAGE,
        "latest_stage_name": NAME,
        "latest_stage_next_best_step": summary["next_best_step"],
        "max_stage": STAGE,
        "registry_rows": len(registry["rows"]),
    }
    REGISTRY.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def replay_reason(row: dict[str, Any]) -> str:
    if (not bool(row.get("hundred_m_correct"))) and bool(row.get("gemma_correct")):
        return "python_gemma_advantage_current"
    return "python_both_wrong_current"


def build_request() -> dict[str, Any]:
    base_rows = load_jsonl(BASE)
    base_index = {str(row.get("row_id") or ""): row for row in base_rows}
    comparison_rows = load_jsonl(COMPARISON)
    python_losses = [
        row for row in comparison_rows
        if str(row.get("language_family") or "") == "python"
        and not bool(row.get("hundred_m_correct"))
    ]
    replay_rows: list[dict[str, Any]] = []
    failures: list[str] = []
    for loss in python_losses:
        row_id = str(loss.get("row_id") or "")
        source = base_index.get(row_id)
        if not isinstance(source, dict):
            failures.append(f"missing_source_row:{row_id}")
            continue
        cloned = deepcopy(source)
        cloned["row_id"] = f"{row_id}::train_gap_replay_current_python"
        cloned["split"] = "train"
        cloned["gap_replay_reason"] = replay_reason(loss)
        replay_rows.append(cloned)
    rows = [*base_rows, *replay_rows]
    write_jsonl(MANIFEST, rows)
    language_counts = Counter(str(row.get("language_family") or "") for row in rows)
    split_counts = Counter(str(row.get("split") or "") for row in rows)
    gap_reason_counts = Counter(str(row.get("gap_replay_reason") or "") for row in rows if row.get("gap_replay_reason"))
    metrics = {
        "rows": len(rows),
        "language_counts": dict(sorted(language_counts.items())),
        "split_counts": dict(sorted(split_counts.items())),
        "gap_replay_rows": len(replay_rows),
        "gap_replay_reason_counts": dict(sorted(gap_reason_counts.items())),
        "python_losses_current": len(python_losses),
    }
    if metrics["rows"] != 119:
        failures.append("rows_not_119")
    if split_counts.get("train") != 47:
        failures.append("train_rows_not_47")
    if language_counts.get("python") != 26:
        failures.append("python_rows_not_26")
    if metrics["gap_replay_rows"] != 7:
        failures.append("gap_replay_rows_not_7")
    if metrics["gap_replay_reason_counts"].get("python_gemma_advantage_current") != 1:
        failures.append("python_gemma_advantage_current_rows_not_1")
    if metrics["gap_replay_reason_counts"].get("python_both_wrong_current") != 6:
        failures.append("python_both_wrong_current_rows_not_6")
    return {"passed": not failures, "failures": failures, "metrics": metrics, "manifest": display(MANIFEST)}


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)
    built = build_request()
    REQUEST.write_text(json.dumps(built, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    next_step = "Run the next direct 100M probe on this 119-row manifest with seven train-side replay copies for the current filtered Python loss set, then rerun the same-manifest Gemma comparison."
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "name": NAME,
        "passed": built["passed"],
        "metrics": {**built["metrics"], "failures": built["failures"]},
        "artifacts": {"request": display(REQUEST), "manifest": display(MANIFEST), "doc": display(DOC)},
        "decision": "Materialized a current Python-gap successor request that adds seven train-side replay copies for the exact Python loss rows from the filtered same-manifest comparison while preserving the quarantined frontier packet.",
        "next_best_step": next_step,
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage10018 Current Python Gap Successor Request",
        "",
        f"Passed: `{summary['passed']}`",
        f"Rows: `{built['metrics']['rows']}`",
        "",
        summary["decision"],
        "",
        f"Next: {next_step}",
        "",
    ]), encoding="utf-8")
    if summary["passed"]:
        update_registry(summary)
    print(json.dumps({"stage": STAGE, "passed": summary["passed"], "metrics": built["metrics"], "failures": built["failures"]}, indent=2, sort_keys=True))
    if built["failures"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
