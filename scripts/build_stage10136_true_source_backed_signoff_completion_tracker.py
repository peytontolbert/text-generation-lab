#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import json
import time
from pathlib import Path
from typing import Any, Callable

ROOT = Path(__file__).resolve().parents[1]
STAGE = 10136
NAME = "stage10136_true_source_backed_signoff_completion_tracker"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
TRACKER = OUT_DIR / "true_source_backed_signoff_completion_tracker.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "TRUE_SOURCE_BACKED_SIGNOFF_COMPLETION_TRACKER_STAGE10136.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"

READINESS = ROOT / "runs/local/artifacts/stage10132_true_source_backed_first_wave_adjudication_readiness_ledger/true_source_backed_first_wave_adjudication_readiness_ledger.json"


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


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
        "max_stage": max(STAGE, int((registry.get("metrics") or {}).get("max_stage", 0) or 0)),
        "registry_rows": len(registry["rows"]),
    }
    REGISTRY.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _load_stage10122_helpers() -> tuple[Callable[[dict[str, Any]], list[str]], Callable[[dict[str, Any]], list[str]], Callable[[dict[str, Any], int], list[str]]]:
    path = ROOT / "scripts" / "build_stage10122_true_source_backed_root_bundle_adjudicated_manifest_compiler.py"
    spec = importlib.util.spec_from_file_location("stage10122_helpers_for_10136", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module._require_completed_rubric, module._require_completed_anti_cheat, module._require_completed_gold


def _split_gold_failures(failures: list[str]) -> tuple[list[str], list[dict[str, Any]]]:
    bundle_level: list[str] = []
    perspective_index: dict[int, list[str]] = {}
    for failure in failures:
        if "::" not in failure:
            bundle_level.append(failure)
            continue
        head, idx_str = failure.split("::", 1)
        try:
            idx = int(idx_str)
        except ValueError:
            bundle_level.append(failure)
            continue
        perspective_index.setdefault(idx, []).append(head)
    perspective_rows = [
        {
            "perspective_index": idx,
            "missing_fields": sorted(values),
        }
        for idx, values in sorted(perspective_index.items())
    ]
    return sorted(bundle_level), perspective_rows


def build_tracker(*, readiness_path: Path = READINESS, root: Path = ROOT) -> dict[str, Any]:
    readiness = load_json(readiness_path)
    failures: list[str] = []
    if readiness.get("passed") is not True:
        failures.append("stage10132_not_passed")

    require_rubric, require_anti, require_gold = _load_stage10122_helpers()
    rows = list(readiness.get("rows") or [])
    tracker_rows: list[dict[str, Any]] = []
    total_missing_gold_fields = 0

    ranked = sorted(
        rows,
        key=lambda row: (
            -int((row.get("shortcut_risk_score") or 0)),
            int((row.get("selected_tests_count") or 0)),
            int((row.get("candidate_paths_count") or 0)),
            -int((row.get("claim_priority_score") or 0)),
            int((row.get("queue_position") or 0)),
        ),
    )

    for rank, row in enumerate(ranked, start=1):
        review_files = row.get("review_files") if isinstance(row.get("review_files"), dict) else {}
        rubric = load_json(root / str(review_files.get("rubric_review") or ""))
        anti = load_json(root / str(review_files.get("anti_cheat_review") or ""))
        gold = load_json(root / str(review_files.get("gold_adjudication") or ""))

        rubric_missing = require_rubric(rubric) if rubric else ["rubric_review_missing"]
        anti_missing = require_anti(anti) if anti else ["anti_cheat_review_missing"]
        expected_perspectives = int(((row.get("task_status") or {}).get("gold_answers_expected", 0) or 0))
        gold_missing_all = require_gold(gold, expected_perspectives=expected_perspectives) if gold else ["perspective_gold_missing"]
        gold_bundle_missing, gold_perspectives = _split_gold_failures(gold_missing_all)
        total_missing_gold_fields += sum(len(p["missing_fields"]) for p in gold_perspectives)

        tracker_rows.append(
            {
                "completion_rank": rank,
                "bundle_id": row.get("bundle_id"),
                "language_family": row.get("language_family"),
                "repo_id": row.get("repo_id"),
                "shortcut_risk_score": row.get("shortcut_risk_score"),
                "selected_tests_count": row.get("selected_tests_count"),
                "candidate_paths_count": row.get("candidate_paths_count"),
                "rubric_missing_fields": rubric_missing,
                "anti_cheat_missing_fields": anti_missing,
                "gold_bundle_missing_fields": gold_bundle_missing,
                "gold_perspective_missing_fields": gold_perspectives,
                "review_files": review_files,
            }
        )

    metrics = {
        "bundle_count": len(tracker_rows),
        "bundles_with_pending_rubric": sum(1 for row in tracker_rows if row["rubric_missing_fields"]),
        "bundles_with_pending_anti_cheat": sum(1 for row in tracker_rows if row["anti_cheat_missing_fields"]),
        "bundles_with_pending_gold": sum(1 for row in tracker_rows if row["gold_bundle_missing_fields"] or row["gold_perspective_missing_fields"]),
        "total_missing_gold_perspective_fields": total_missing_gold_fields,
    }
    if metrics["bundle_count"] != 8:
        failures.append("bundle_count_not_8")
    if metrics["bundles_with_pending_rubric"] != 8:
        failures.append("bundles_with_pending_rubric_not_8")
    if metrics["bundles_with_pending_anti_cheat"] != 8:
        failures.append("bundles_with_pending_anti_cheat_not_8")
    if metrics["bundles_with_pending_gold"] != 8:
        failures.append("bundles_with_pending_gold_not_8")

    return {
        "stage": STAGE,
        "name": NAME,
        "passed": not failures,
        "decision": (
            "Turn the blocked first-wave bundles into a field-by-field signoff tracker so reviewers can see the exact missing rubric, anti-cheat, and gold-adjudication entries required by the real adjudication compiler."
        ),
        "rows": tracker_rows,
        "metrics": metrics,
        "failures": failures,
        "next_best_step": (
            "Fill the missing rubric reviewer_id and decision_rationale, the anti-cheat reviewer_id and decision_rationale, and all eight gold answer kind/value/rationale fields per bundle, then rerun Stage10129."
        ),
    }


def main() -> None:
    built = build_tracker()
    write_json(TRACKER, built)
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "name": NAME,
        "passed": built["passed"],
        "metrics": built["metrics"],
        "artifacts": {
            "tracker": display(TRACKER),
            "doc": display(DOC),
        },
        "decision": built["decision"],
        "next_best_step": built["next_best_step"],
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    write_json(SUMMARY, summary)
    DOC.write_text(
        "\n".join(
            [
                "# Stage10136 True Source-Backed Signoff Completion Tracker",
                "",
                f"Passed: `{summary['passed']}`",
                f"Bundles tracked: `{built['metrics']['bundle_count']}`",
                f"Bundles with pending gold: `{built['metrics']['bundles_with_pending_gold']}`",
                "",
                summary["decision"],
                "",
                f"Next: {built['next_best_step']}",
                "",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    if summary["passed"]:
        update_registry(summary)
    print(json.dumps({"stage": STAGE, "passed": built["passed"], "metrics": built["metrics"], "failures": built["failures"]}, indent=2, sort_keys=True))
    if built["failures"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
