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
AUTHORITY_CLOSED = _load_symbol("stage10008_contract", ROOT / "scripts/diagnostic_ticket_contract.py", "AUTHORITY_CLOSED")
STAGE = 10008
NAME = "stage10008_heldout_winner_signoff_sheets"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
MANIFEST = OUT_DIR / "heldout_winner_signoff_sheets.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "HELDOUT_WINNER_SIGNOFF_SHEETS_STAGE10008.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
CLOSEOUT = ROOT / "runs/local/artifacts/stage10006_v27_heldout_closeout_packet/v27_heldout_closeout_packet.json"
BASE = ROOT / "runs/local/artifacts/stage9752_supported_standalone_review_packets/review_packets"


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


def _sheet_text(row: dict[str, Any]) -> str:
    lang = str(row.get("language_family") or "")
    standalone = row.get("standalone_win_summary") if isinstance(row.get("standalone_win_summary"), dict) else {}
    human = row.get("human_signoff") if isinstance(row.get("human_signoff"), dict) else {}
    harness = row.get("external_harness") if isinstance(row.get("external_harness"), dict) else {}
    tasks = human.get("tasks") if isinstance(human.get("tasks"), list) else []
    lines = [
        f"# {lang} Heldout Winner Signoff Sheet",
        "",
        f"Standalone heldout same-manifest result: `100M {standalone.get('same_surface_eval_exact_100m')} vs Gemma {standalone.get('same_surface_eval_exact_gemma')}`",
        f"Rows in heldout comparison: `{standalone.get('same_surface_rows')}`",
        f"Standalone win present: `{standalone.get('standalone_same_surface_win')}`",
        "",
        "## Human Signoff Tasks",
        "",
    ]
    for task in tasks:
        lines.extend([
            f"### {task.get('task')}",
            f"Status: `{task.get('review_status')}`",
            f"Review file: `{task.get('review_file')}`",
            f"Recommendation source: `{task.get('recommendation_source_path')}`",
            f"Required action: {task.get('required_human_action')}",
            "",
        ])
    lines.extend([
        "## External Harness",
        "",
        f"Handoff status: `{harness.get('handoff_status')}`",
        f"Handoff bundle: `{harness.get('handoff_bundle_path')}`",
        "Backend must supply:",
    ])
    for item in harness.get("backend_must_supply") or []:
        lines.append(f"- {item}")
    lines.extend([
        "",
        "## Completion Blockers",
        "",
    ])
    for item in row.get("completion_blockers") or []:
        lines.append(f"- {item}")
    lines.append("")
    return "\n".join(lines)


def build_sheets() -> dict[str, Any]:
    closeout = load_json(CLOSEOUT)
    rows = [row for row in (closeout.get("language_packets") or []) if isinstance(row, dict)]
    failures: list[str] = []
    manifest_rows: list[dict[str, Any]] = []
    for row in rows:
        lang = str(row.get("language_family") or "")
        sheet_path = BASE / f"standalone_100m_weights__{lang}__edit_localization" / "signoff_sheet.md"
        sheet_path.parent.mkdir(parents=True, exist_ok=True)
        sheet_path.write_text(_sheet_text(row), encoding="utf-8")
        manifest_rows.append({
            "language_family": lang,
            "sheet": display(sheet_path),
            "review_files": [task.get("review_file") for task in (row.get("human_signoff") or {}).get("tasks", [])],
            "handoff_bundle": (row.get("external_harness") or {}).get("handoff_bundle_path"),
        })
    metrics = {
        "signoff_sheets_written": len(manifest_rows),
        "languages": len({row['language_family'] for row in manifest_rows}),
    }
    if metrics["signoff_sheets_written"] != 4:
        failures.append("signoff_sheets_written_not_4")
    return {"passed": not failures, "failures": failures, "metrics": metrics, "rows": manifest_rows, "authority": dict(AUTHORITY_CLOSED)}


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)
    built = build_sheets()
    MANIFEST.write_text(json.dumps(built, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    next_step = "Use the four heldout signoff_sheet.md files to complete the remaining 8 human review tasks, then pass the referenced harness handoff bundles to the external runtime owner."
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "name": NAME,
        "passed": built["passed"],
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {**dict(AUTHORITY_CLOSED), **built["metrics"], "failures": built["failures"]},
        "artifacts": {"manifest": display(MANIFEST), "doc": display(DOC)},
        "decision": "Materialized four plain-language heldout signoff sheets, one per required language, so the remaining human review and external handoff work can be executed from local packet dirs without navigating raw JSON artifacts.",
        "next_best_step": next_step,
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage10008 Heldout Winner Signoff Sheets",
        "",
        f"Passed: `{summary['passed']}`",
        f"Signoff sheets written: `{built['metrics']['signoff_sheets_written']}`",
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
