#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = 10135
NAME = "stage10135_true_source_backed_high_risk_review_sheet"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
SHEET = OUT_DIR / "true_source_backed_high_risk_review_sheet.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "TRUE_SOURCE_BACKED_HIGH_RISK_REVIEW_SHEET_STAGE10135.md"
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


def _review_focus(row: dict[str, Any]) -> list[str]:
    focus: list[str] = []
    watch = row.get("eval_hacking_watchlist") or {}
    if watch.get("high_shortcut_risk"):
        focus.append("check whether candidate-count or path-name priors can solve localization without real reasoning")
    if watch.get("few_candidate_paths"):
        focus.append("verify that the tiny candidate set does not trivialize the answer")
    if watch.get("no_selected_tests"):
        focus.append("review verifier-related perspectives strictly because no selected tests are attached")
    if watch.get("abstention_requires_honesty_review"):
        focus.append("prefer abstention whenever the visible evidence does not honestly isolate one answer")
    return focus


def build_sheet(*, readiness_path: Path = READINESS) -> dict[str, Any]:
    readiness = load_json(readiness_path)
    failures: list[str] = []
    if readiness.get("passed") is not True:
        failures.append("stage10132_not_passed")

    rows = list(readiness.get("rows") or [])
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
    selected = ranked[:4]

    review_rows = []
    for idx, row in enumerate(selected, start=1):
        review_rows.append(
            {
                "review_rank": idx,
                "bundle_id": row.get("bundle_id"),
                "language_family": row.get("language_family"),
                "repo_id": row.get("repo_id"),
                "priority_tier": row.get("priority_tier"),
                "priority_score": row.get("priority_score"),
                "shortcut_risk_score": row.get("shortcut_risk_score"),
                "selected_tests_count": row.get("selected_tests_count"),
                "candidate_paths_count": row.get("candidate_paths_count"),
                "blocked_reason_heads": list(((row.get("adjudication_state") or {}).get("blocked_reason_heads")) or []),
                "review_focus": _review_focus(row),
                "review_files": dict(row.get("review_files") or {}),
            }
        )

    metrics = {
        "high_risk_rows": len(review_rows),
        "web_rows_included": sum(1 for row in review_rows if row["language_family"] == "web_js_ts_html"),
        "rows_without_selected_tests": sum(1 for row in review_rows if int(row["selected_tests_count"] or 0) == 0),
        "highest_shortcut_risk": max((int(row["shortcut_risk_score"] or 0) for row in review_rows), default=0),
    }
    if metrics["high_risk_rows"] != 4:
        failures.append("high_risk_rows_not_4")
    if metrics["web_rows_included"] != 2:
        failures.append("web_rows_included_not_2")

    return {
        "stage": STAGE,
        "name": NAME,
        "passed": not failures,
        "decision": (
            "Collapse the first-wave human bottleneck into a targeted high-risk review sheet so reviewers can clear the bundles most exposed to shortcut risk and weak verifier evidence before spending time on lower-risk bundles."
        ),
        "rows": review_rows,
        "metrics": metrics,
        "failures": failures,
        "next_best_step": (
            "Work these four review rows first in order, then return to the remaining lower-risk bundles before rerunning Stage10129 and Stage10130."
        ),
    }


def main() -> None:
    built = build_sheet()
    write_json(SHEET, built)
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "name": NAME,
        "passed": built["passed"],
        "metrics": built["metrics"],
        "artifacts": {
            "sheet": display(SHEET),
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
                "# Stage10135 True Source-Backed High Risk Review Sheet",
                "",
                f"Passed: `{summary['passed']}`",
                f"High-risk rows: `{built['metrics']['high_risk_rows']}`",
                f"Web rows included: `{built['metrics']['web_rows_included']}`",
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
