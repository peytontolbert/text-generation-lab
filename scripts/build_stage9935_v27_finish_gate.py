#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

try:
    from diagnostic_ticket_contract import AUTHORITY_CLOSED
except ModuleNotFoundError:
    from scripts.diagnostic_ticket_contract import AUTHORITY_CLOSED  # type: ignore

ROOT = Path(__file__).resolve().parents[1]
STAGE = 9935
NAME = "stage9935_v27_finish_gate"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
GATE = OUT_DIR / "v27_finish_gate.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "V27_FINISH_GATE_STAGE9935.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"

FRONTIER = ROOT / "runs/local/artifacts/stage9922_current_weighted_hardened_multilingual_frontier_bridge/current_weighted_hardened_multilingual_frontier_bridge.json"
SIGNOFF = ROOT / "runs/local/artifacts/stage9934_active_weighted_winner_signoff_workbook/active_weighted_winner_signoff_workbook.json"
HANDOFF = ROOT / "runs/local/artifacts/stage9931_weighted_harness_backend_handoff_bundle/weighted_harness_backend_handoff_bundle.json"

LANGS = ["python", "rust", "c_cpp", "web_js_ts_html"]


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
    rows.append({
        "stage": STAGE,
        "stage_name": NAME,
        "passed": summary["passed"],
        "path": str(SUMMARY),
        "authority": dict(AUTHORITY_CLOSED),
        "next_best_step": summary["next_best_step"],
    })
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


def build_gate() -> dict[str, Any]:
    frontier = load_json(FRONTIER)
    signoff = load_json(SIGNOFF)
    handoff = load_json(HANDOFF)
    failures: list[str] = []

    frontier_records = {str(row.get("language_family") or ""): row for row in (frontier.get("records") or []) if isinstance(row, dict)}
    signoff_rows = [row for row in (signoff.get("rows") or []) if isinstance(row, dict)]
    handoff_rows = {str(row.get("language_family") or ""): row for row in (handoff.get("handoff_cells") or []) if isinstance(row, dict)}

    gate_rows: list[dict[str, Any]] = []
    for lang in LANGS:
        frontier_row = frontier_records.get(lang)
        if not isinstance(frontier_row, dict):
            failures.append(f"missing_frontier_record:{lang}")
            continue
        lang_signoff = [row for row in signoff_rows if str(row.get("language_family") or "") == lang]
        handoff_row = handoff_rows.get(lang)
        if not isinstance(handoff_row, dict):
            failures.append(f"missing_handoff_row:{lang}")
            continue
        gate_rows.append({
            "language_family": lang,
            "standalone_same_surface_win": bool(frontier_row.get("strict_verdict") == "100m_better"),
            "standalone_strict_exact_100m": frontier_row.get("strict_exact_100m"),
            "standalone_strict_exact_gemma": frontier_row.get("strict_exact_gemma"),
            "standalone_human_signoff_tasks_remaining": len(lang_signoff),
            "standalone_review_statuses": [row.get("review_status") for row in lang_signoff],
            "standalone_top_signoff_files": [row.get("review_file") for row in lang_signoff],
            "harness_backend_handoff_ready": bool(handoff_row.get("handoff_status") == "ready_for_external_backend_adapter"),
            "harness_external_backend_required": True,
            "harness_handoff_bundle": handoff_row.get("handoff_bundle_path"),
            "objective_language_ready_now": bool(frontier_row.get("strict_verdict") == "100m_better"),
            "objective_language_complete": False,
            "remaining_blockers": [
                "human_standalone_rubric_signoff",
                "human_standalone_anti_cheat_signoff",
                "external_full_product_harness_backend_execution",
            ],
        })

    metrics = {
        "languages_required": len(LANGS),
        "languages_with_standalone_win": sum(1 for row in gate_rows if row["standalone_same_surface_win"]),
        "standalone_human_signoff_tasks_remaining": sum(int(row["standalone_human_signoff_tasks_remaining"]) for row in gate_rows),
        "languages_with_harness_handoff_ready": sum(1 for row in gate_rows if row["harness_backend_handoff_ready"]),
        "objective_complete": False,
    }

    if metrics["languages_required"] != 4:
        failures.append("languages_required_not_4")
    if metrics["languages_with_standalone_win"] != 4:
        failures.append("languages_with_standalone_win_not_4")
    if metrics["standalone_human_signoff_tasks_remaining"] != 8:
        failures.append("standalone_human_signoff_tasks_remaining_not_8")
    if metrics["languages_with_harness_handoff_ready"] != 4:
        failures.append("languages_with_harness_handoff_ready_not_4")

    return {
        "passed": not failures,
        "failures": failures,
        "metrics": metrics,
        "language_rows": gate_rows,
        "completion_rule": {
            "standalone_requirement": "all 4 language families retain 100m_better strict verdict and receive human rubric plus anti-cheat signoff",
            "harness_requirement": "all 4 language families execute through external full-product backend and write back required artifacts",
            "anti_cheat_requirement": "no anti-cheat failure in any signed winner cell",
        },
        "authority": dict(AUTHORITY_CLOSED),
    }


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)
    built = build_gate()
    GATE.write_text(json.dumps(built, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    next_step = "Complete the 8 human signoff tasks in the Stage9934 workbook, then hand the 4 Stage9931 backend bundles to the external full-product runtime to satisfy the remaining harness requirement."
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "name": NAME,
        "passed": built["passed"],
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {**dict(AUTHORITY_CLOSED), **built["metrics"], "failures": built["failures"]},
        "artifacts": {"gate": display(GATE), "doc": display(DOC)},
        "decision": "Materialized a single v2.7 finish gate that proves the four-language standalone win is present, the active signoff queue is exactly 8 human tasks, and the harness side is packaged through external-backend handoff but not complete.",
        "next_best_step": next_step,
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage9935 V27 Finish Gate",
        "",
        f"Passed: `{summary['passed']}`",
        f"Languages with standalone win: `{built['metrics']['languages_with_standalone_win']}`",
        f"Standalone human signoff tasks remaining: `{built['metrics']['standalone_human_signoff_tasks_remaining']}`",
        f"Languages with harness handoff ready: `{built['metrics']['languages_with_harness_handoff_ready']}`",
        "",
        summary["decision"],
        "",
        f"Next: {next_step}",
        "",
    ]), encoding="utf-8")
    if summary["passed"]:
        update_registry(summary)
    print(json.dumps({"stage": STAGE, "passed": summary["passed"], "metrics": built["metrics"], "failures": built["failures"]}, indent=2, sort_keys=True))
    if not summary["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
