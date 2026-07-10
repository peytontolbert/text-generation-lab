#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import json
import time
from pathlib import Path
from typing import Any

def _load_symbol(module_name: str, path: Path, symbol: str):
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return getattr(module, symbol)

ROOT = Path(__file__).resolve().parents[1]
AUTHORITY_CLOSED = _load_symbol('stage10005_contract', ROOT / 'scripts/diagnostic_ticket_contract.py', 'AUTHORITY_CLOSED')
STAGE = 10005
NAME = "stage10005_v27_current_blocker_ledger_after_heldout_win"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
LEDGER = OUT_DIR / "v27_current_blocker_ledger_after_heldout_win.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "V27_CURRENT_BLOCKER_LEDGER_AFTER_HELDOUT_WIN_STAGE10005.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"

COMPARISON = ROOT / "runs/summaries/stage10001_source_heldout_same_manifest_comparison_audit.json"
WORKBOOK = ROOT / "runs/local/artifacts/stage10004_heldout_multilingual_winner_signoff_workbook/heldout_multilingual_winner_signoff_workbook.json"
HANDOFF = ROOT / "runs/local/artifacts/stage9931_weighted_harness_backend_handoff_bundle/weighted_harness_backend_handoff_bundle.json"


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


def build_ledger() -> dict[str, Any]:
    comparison = load_json(COMPARISON)
    workbook = load_json(WORKBOOK)
    if not workbook:
        build_workbook = _load_symbol(
            'stage10005_stage10004_builder',
            ROOT / 'scripts/build_stage10004_heldout_multilingual_winner_signoff_workbook.py',
            'build_workbook',
        )
        workbook = build_workbook()
    handoff = load_json(HANDOFF)
    per_language = ((comparison.get("metrics") or {}).get("per_language") or {})
    signoff_rows = [row for row in (workbook.get("rows") or []) if isinstance(row, dict)]
    handoff_rows = [row for row in (handoff.get("handoff_cells") or []) if isinstance(row, dict)]
    metrics = {
        **dict(AUTHORITY_CLOSED),
        "objective_complete": False,
        "languages_required": 4,
        "languages_with_standalone_win": sum(1 for row in per_language.values() if isinstance(row, dict) and row.get("verdict") == "100m_better"),
        "languages_with_harness_handoff_ready": sum(1 for row in handoff_rows if row.get("handoff_status") == "ready_for_external_backend_adapter"),
        "languages_with_harness_acceptance_ready": 0,
        "total_pending_human_signoff_tasks": len(signoff_rows),
        "heldout_standalone_path_fully_packaged_locally": True,
    }
    failures: list[str] = []
    if metrics["languages_with_standalone_win"] != 4:
        failures.append("languages_with_standalone_win_not_4")
    if metrics["languages_with_harness_handoff_ready"] != 4:
        failures.append("languages_with_harness_handoff_ready_not_4")
    if metrics["total_pending_human_signoff_tasks"] != 8:
        failures.append("total_pending_human_signoff_tasks_not_8")
    payload = {
        "passed": not failures,
        "failures": failures,
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": metrics,
        "frontier_paths": {
            "source_heldout_same_manifest_comparison": display(COMPARISON),
            "heldout_signoff_workbook": display(WORKBOOK),
            "external_harness_handoff_bundle": display(HANDOFF),
        },
        "remaining_blockers": [
            "8_human_signoff_tasks_on_current_heldout_winner_packets",
            "4_external_full_product_harness_backend_executions",
            "future_reruns_should_use_stage10003_deduped_manifest",
        ],
    }
    return payload


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)
    built = build_ledger()
    LEDGER.write_text(json.dumps(built, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    next_step = "Complete the 8 human signoff tasks on the current heldout winner packets and hand the 4 external harness bundles to the runtime owner; future reruns should use the stage10003 deduped manifest."
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "name": NAME,
        "passed": built["passed"],
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {**built["metrics"], "failures": built["failures"]},
        "artifacts": {"ledger": display(LEDGER), "doc": display(DOC)},
        "decision": "Refreshed the v2.7 blocker ledger after the heldout multilingual standalone win so the repo now distinguishes the achieved 4-language standalone result from the still-open human signoff and external harness runtime work.",
        "next_best_step": next_step,
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage10005 V27 Current Blocker Ledger After Heldout Win",
        "",
        f"Passed: `{summary['passed']}`",
        f"Languages with standalone win: `{built['metrics']['languages_with_standalone_win']}`",
        f"Pending human signoff tasks: `{built['metrics']['total_pending_human_signoff_tasks']}`",
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
    if built["failures"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
