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
AUTHORITY_CLOSED = _load_symbol('stage10006_contract', ROOT / 'scripts/diagnostic_ticket_contract.py', 'AUTHORITY_CLOSED')
STAGE = 10006
NAME = "stage10006_v27_heldout_closeout_packet"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
PACKET = OUT_DIR / "v27_heldout_closeout_packet.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "V27_HELDOUT_CLOSEOUT_PACKET_STAGE10006.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"

BLOCKERS = ROOT / "runs/local/artifacts/stage10005_v27_current_blocker_ledger_after_heldout_win/v27_current_blocker_ledger_after_heldout_win.json"
WORKBOOK = ROOT / "runs/local/artifacts/stage10004_heldout_multilingual_winner_signoff_workbook/heldout_multilingual_winner_signoff_workbook.json"
HANDOFF = ROOT / "runs/local/artifacts/stage9931_weighted_harness_backend_handoff_bundle/weighted_harness_backend_handoff_bundle.json"
COMPARISON = ROOT / "runs/summaries/stage10001_source_heldout_same_manifest_comparison_audit.json"
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


def build_packet() -> dict[str, Any]:
    blockers = load_json(BLOCKERS)
    workbook = load_json(WORKBOOK)
    if not workbook:
        build_workbook = _load_symbol(
            'stage10006_stage10004_builder',
            ROOT / 'scripts/build_stage10004_heldout_multilingual_winner_signoff_workbook.py',
            'build_workbook',
        )
        workbook = build_workbook()
    handoff = load_json(HANDOFF)
    comparison = load_json(COMPARISON)
    signoff_rows = [row for row in (workbook.get("rows") or []) if isinstance(row, dict)]
    handoff_rows = {str(row.get("language_family") or ""): row for row in (handoff.get("handoff_cells") or []) if isinstance(row, dict)}
    per_language = ((comparison.get("metrics") or {}).get("per_language") or {})
    failures: list[str] = []
    packet_rows: list[dict[str, Any]] = []
    for lang in LANGS:
        metrics = per_language.get(lang)
        handoff_row = handoff_rows.get(lang)
        if not isinstance(metrics, dict):
            failures.append(f"missing_language_metrics:{lang}")
            continue
        if not isinstance(handoff_row, dict):
            failures.append(f"missing_handoff_row:{lang}")
            continue
        lang_signoff = [row for row in signoff_rows if str(row.get("language_family") or "") == lang]
        if len(lang_signoff) != 2:
            failures.append(f"unexpected_signoff_row_count:{lang}:{len(lang_signoff)}")
        packet_rows.append({
            "language_family": lang,
            "standalone_win_summary": {
                "same_surface_eval_exact_100m": metrics.get("hundred_m_exact"),
                "same_surface_eval_exact_gemma": metrics.get("gemma_exact"),
                "same_surface_rows": metrics.get("rows"),
                "standalone_same_surface_win": metrics.get("verdict") == "100m_better",
            },
            "human_signoff": {
                "tasks_remaining": len(lang_signoff),
                "tasks": [
                    {
                        "task": row.get("task"),
                        "review_status": row.get("review_status"),
                        "required_human_action": row.get("required_human_action"),
                        "review_file": row.get("review_file"),
                        "recommendation_source_path": row.get("recommendation_source_path"),
                    }
                    for row in lang_signoff
                ],
            },
            "external_harness": {
                "handoff_status": handoff_row.get("handoff_status"),
                "handoff_bundle_path": handoff_row.get("handoff_bundle_path"),
                "backend_must_supply": handoff_row.get("backend_must_supply"),
                "artifact_paths": handoff_row.get("artifact_paths"),
            },
            "completion_blockers": list((blockers.get("remaining_blockers") or [])),
        })
    metrics = {
        "language_packets": len(packet_rows),
        "total_human_tasks_remaining": sum(int(row["human_signoff"]["tasks_remaining"]) for row in packet_rows),
        "languages_with_external_harness_handoff": sum(1 for row in packet_rows if row["external_harness"].get("handoff_status") == "ready_for_external_backend_adapter"),
        "languages_with_standalone_win": sum(1 for row in packet_rows if row["standalone_win_summary"].get("standalone_same_surface_win") is True),
    }
    if metrics["language_packets"] != 4:
        failures.append("language_packets_not_4")
    if metrics["total_human_tasks_remaining"] != 8:
        failures.append("total_human_tasks_remaining_not_8")
    if metrics["languages_with_external_harness_handoff"] != 4:
        failures.append("languages_with_external_harness_handoff_not_4")
    if metrics["languages_with_standalone_win"] != 4:
        failures.append("languages_with_standalone_win_not_4")
    return {
        "passed": not failures,
        "failures": failures,
        "metrics": metrics,
        "language_packets": packet_rows,
        "authority": dict(AUTHORITY_CLOSED),
    }


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)
    built = build_packet()
    PACKET.write_text(json.dumps(built, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    next_step = "Use this heldout closeout packet to complete the 8 human standalone signoff tasks and hand off the 4 per-language harness bundles to the external runtime owner."
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "name": NAME,
        "passed": built["passed"],
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {**dict(AUTHORITY_CLOSED), **built["metrics"], "failures": built["failures"]},
        "artifacts": {"packet": display(PACKET), "doc": display(DOC)},
        "decision": "Materialized one language-by-language closeout packet that combines the heldout standalone win evidence, the live human signoff tasks, and the external harness handoff bundle for each required language family.",
        "next_best_step": next_step,
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage10006 V27 Heldout Closeout Packet",
        "",
        f"Passed: `{summary['passed']}`",
        f"Language packets: `{built['metrics']['language_packets']}`",
        f"Total human tasks remaining: `{built['metrics']['total_human_tasks_remaining']}`",
        f"Languages with external harness handoff: `{built['metrics']['languages_with_external_harness_handoff']}`",
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
