#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = 10032
NAME = "stage10032_python_cpp_fresh_root_builder_workbook"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
WORKBOOK = OUT_DIR / "python_cpp_fresh_root_builder_workbook.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "PYTHON_CPP_FRESH_ROOT_BUILDER_WORKBOOK_STAGE10032.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
REQUEST = ROOT / "runs/local/artifacts/stage10030_python_cpp_fresh_root_replenishment_request/python_cpp_fresh_root_replenishment_request.json"
REVIEW = ROOT / "runs/local/artifacts/stage10031_python_cpp_expert_anti_cheat_review_sheet/python_cpp_expert_anti_cheat_review_sheet.json"


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def display(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def update_registry(summary: dict[str, Any]) -> None:
    registry = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    rows = [row for row in registry.get("rows", []) if row.get("stage") != STAGE and row.get("stage_name") != NAME]
    rows.append(
        {
            "stage": STAGE,
            "stage_name": NAME,
            "passed": summary["passed"],
            "path": str(SUMMARY),
            "next_best_step": summary["next_best_step"],
        }
    )
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


def build_workbook() -> dict[str, Any]:
    request = load_json(REQUEST)
    review = load_json(REVIEW)
    request_rows = request.get("requests") if isinstance(request.get("requests"), list) else []
    review_rows = review.get("review_rows") if isinstance(review.get("review_rows"), list) else []

    review_by_root: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for row in review_rows:
        key = (str(row.get("language_family") or ""), str(row.get("counterfactual_root_row_id") or ""))
        review_by_root.setdefault(key, []).append(row)

    tasks: list[dict[str, Any]] = []
    for request_row in request_rows:
        language = str(request_row.get("language_family") or "")
        root_ids = request_row.get("root_case_ids") if isinstance(request_row.get("root_case_ids"), list) else []
        seed_examples = []
        for root_id in root_ids:
            for row in review_by_root.get((language, str(root_id)), []):
                seed_examples.append(
                    {
                        "row_id": row.get("row_id"),
                        "expected_label": row.get("expected_label"),
                        "review_outcome_bucket": row.get("review_outcome_bucket"),
                        "counterfactual_role": row.get("counterfactual_role"),
                    }
                )
        tasks.append(
            {
                "task_id": f"{language}::{request_row.get('target_label')}::{len(tasks) + 1}",
                "language_family": language,
                "target_label": request_row.get("target_label"),
                "requested_fresh_independent_roots": request_row.get("requested_fresh_independent_roots"),
                "seed_root_case_ids": root_ids,
                "seed_examples": seed_examples,
                "builder_requirements": [
                    "New source root must not appear in any current train or heldout manifest.",
                    "Preserve the visible-evidence edit-localization surface contract.",
                    "Do not copy or lightly mutate the existing root; derive a new independent software-maintenance case.",
                    "Attach expert-maintainer identifiability review before promotion.",
                    "Attach anti-cheat checks for label leakage, decoy handling, and train/eval source independence.",
                ],
                "signoff_checks": [
                    "Root is source-independent from all current training sources.",
                    "Row is answerable from visible evidence alone.",
                    "No target-label literal leakage appears in model-visible fields.",
                    "At least one positive_original heldout row exists for the new root.",
                ],
            }
        )

    failures: list[str] = []
    if len(tasks) != 6:
        failures.append("builder_tasks_not_6")
    workbook = {
        "passed": not failures,
        "failures": failures,
        "metrics": {
            "tasks": len(tasks),
            "languages": sorted({str(task.get("language_family") or "") for task in tasks}),
            "total_requested_fresh_roots": sum(int(task.get("requested_fresh_independent_roots") or 0) for task in tasks),
        },
        "tasks": tasks,
        "inputs": {
            "fresh_root_request": display(REQUEST),
            "expert_anti_cheat_review_sheet": display(REVIEW),
        },
    }
    return workbook


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)
    built = build_workbook()
    WORKBOOK.write_text(json.dumps(built, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    next_step = (
        "Use this workbook to build the six fresh independent Python/C++ root families, then rerun the source-heldout same-manifest comparison on the replenished heldout set."
    )
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "name": NAME,
        "passed": built["passed"],
        "metrics": {**built["metrics"], "failures": built["failures"]},
        "artifacts": {"workbook": display(WORKBOOK), "doc": display(DOC)},
        "decision": "Materialized a builder-facing workbook that turns the unresolved Python/C++ heldout families into six concrete fresh-root construction tasks with explicit source-independence, expert-maintainer, and anti-cheat gates.",
        "next_best_step": next_step,
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text(
        "\n".join(
            [
                "# Stage10032 Python Cpp Fresh Root Builder Workbook",
                "",
                f"Passed: `{summary['passed']}`",
                f"Tasks: `{built['metrics']['tasks']}`",
                "",
                summary["decision"],
                "",
                f"Next: {next_step}",
                "",
            ]
        ),
        encoding="utf-8",
    )
    if summary["passed"]:
        update_registry(summary)
    print(json.dumps({"stage": STAGE, "passed": summary["passed"], "metrics": built["metrics"], "failures": built["failures"]}, indent=2, sort_keys=True))
    if built["failures"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
