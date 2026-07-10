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
STAGE = 10078
NAME = "stage10078_canonical_v27_completion_boundary"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
BOUNDARY = OUT_DIR / "canonical_v27_completion_boundary.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "CANONICAL_V27_COMPLETION_BOUNDARY_STAGE10078.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"

FINISH_GATE = ROOT / "runs/local/artifacts/stage10076_canonical_v27_finish_gate/canonical_v27_finish_gate.json"
ACCEPTANCE = ROOT / "runs/local/artifacts/stage9938_weighted_harness_output_acceptance_audit/weighted_harness_output_acceptance_audit.json"
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
    rows.append({"stage": STAGE, "stage_name": NAME, "passed": summary["passed"], "path": str(SUMMARY), "authority": dict(AUTHORITY_CLOSED), "next_best_step": summary["next_best_step"]})
    registry["rows"] = sorted(rows, key=lambda row: (int(row.get("stage", -1)), row.get("stage_name", "")))
    registry["passed"] = bool(registry["rows"])
    registry["metrics"] = {**(registry.get("metrics") or {}), "latest_stage": STAGE, "latest_stage_name": NAME, "latest_stage_next_best_step": summary["next_best_step"], "max_stage": STAGE, "registry_rows": len(registry["rows"])}
    REGISTRY.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def build_boundary() -> dict[str, Any]:
    finish = load_json(FINISH_GATE)
    acceptance = load_json(ACCEPTANCE)
    failures: list[str] = []

    finish_rows = {str(row.get("language_family") or ""): row for row in (finish.get("language_rows") or []) if isinstance(row, dict)}
    acceptance_rows = {str(row.get("language_family") or ""): row for row in (acceptance.get("records") or []) if isinstance(row, dict)}

    boundary_rows: list[dict[str, Any]] = []
    for lang in LANGS:
        finish_row = finish_rows.get(lang)
        acceptance_row = acceptance_rows.get(lang)
        if not isinstance(finish_row, dict):
            failures.append(f"missing_finish_row:{lang}")
            continue
        if not isinstance(acceptance_row, dict):
            failures.append(f"missing_acceptance_row:{lang}")
            continue
        pending_artifacts = list(acceptance_row.get("pending_artifacts") or [])
        acceptance_ready = bool(acceptance_row.get("acceptance_ready"))
        boundary_rows.append({
            "language_family": lang,
            "standalone_same_surface_win": finish_row.get("standalone_same_surface_win"),
            "standalone_exact_100m": finish_row.get("standalone_exact_100m"),
            "standalone_exact_gemma": finish_row.get("standalone_exact_gemma"),
            "standalone_human_signoff_tasks_remaining": finish_row.get("standalone_human_signoff_tasks_remaining"),
            "harness_backend_handoff_ready": finish_row.get("harness_backend_handoff_ready"),
            "harness_acceptance_ready": acceptance_ready,
            "harness_stub_only": not acceptance_ready,
            "harness_pending_artifacts": pending_artifacts,
            "harness_pending_artifact_count": len(pending_artifacts),
            "objective_language_complete": False,
            "completion_state": "complete" if acceptance_ready and int(finish_row.get("standalone_human_signoff_tasks_remaining") or 0) == 0 else "standalone_win_plus_handoff_ready_waiting_for_real_harness_outputs",
            "remaining_blockers": [*list(finish_row.get("remaining_blockers") or []), *( [] if acceptance_ready else ["real_harness_outputs_still_missing"])],
        })

    metrics = {
        "languages_required": len(LANGS),
        "languages_with_standalone_win": sum(1 for row in boundary_rows if row["standalone_same_surface_win"]),
        "standalone_human_signoff_tasks_remaining": sum(int(row["standalone_human_signoff_tasks_remaining"] or 0) for row in boundary_rows),
        "languages_with_harness_handoff_ready": sum(1 for row in boundary_rows if row["harness_backend_handoff_ready"]),
        "languages_with_harness_acceptance_ready": sum(1 for row in boundary_rows if row["harness_acceptance_ready"]),
        "languages_still_stub_only": sum(1 for row in boundary_rows if row["harness_stub_only"]),
        "total_pending_harness_artifacts": sum(int(row["harness_pending_artifact_count"]) for row in boundary_rows),
        "objective_complete": False,
    }
    if metrics["languages_with_standalone_win"] != 4:
        failures.append("languages_with_standalone_win_not_4")
    if metrics["standalone_human_signoff_tasks_remaining"] != 8:
        failures.append("standalone_human_signoff_tasks_remaining_not_8")
    if metrics["languages_with_harness_handoff_ready"] != 4:
        failures.append("languages_with_harness_handoff_ready_not_4")
    if metrics["languages_with_harness_acceptance_ready"] != 0:
        failures.append("languages_with_harness_acceptance_ready_not_0")
    if metrics["languages_still_stub_only"] != 4:
        failures.append("languages_still_stub_only_not_4")
    if metrics["total_pending_harness_artifacts"] != 28:
        failures.append("total_pending_harness_artifacts_not_28")
    return {
        "passed": not failures,
        "failures": failures,
        "metrics": metrics,
        "language_rows": boundary_rows,
        "completion_rule": {
            "standalone_requirement": "all 4 language families retain 100m_better same-manifest verdict and receive signed expert rubric plus anti-cheat review",
            "harness_requirement": "all 4 language families replace reserved stub harness artifacts with real backend outputs on the same locked task pack",
            "expert_eval_requirement": "expert maintainer review and anti-cheat review must remain attached after real harness outputs land",
        },
        "authority": dict(AUTHORITY_CLOSED),
    }


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)
    built = build_boundary()
    BOUNDARY.write_text(json.dumps(built, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    next_step = "Complete the 8 remaining standalone human signoff tasks, then execute the 4 harness backend handoff bundles until the 28 reserved stub artifacts are replaced by real same-task-pack runtime outputs."
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "name": NAME,
        "passed": built["passed"],
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {**dict(AUTHORITY_CLOSED), **built["metrics"], "failures": built["failures"]},
        "artifacts": {"boundary": display(BOUNDARY), "doc": display(DOC)},
        "decision": "Materialized the live canonical v2.7 completion boundary by joining the refreshed standalone finish gate to the existing harness acceptance audit, proving that harness packaging is handoff-ready but still entirely stub-backed.",
        "next_best_step": next_step,
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage10078 Canonical V27 Completion Boundary",
        "",
        f"Passed: `{summary['passed']}`",
        f"Languages with standalone win: `{built['metrics']['languages_with_standalone_win']}`",
        f"Standalone human signoff tasks remaining: `{built['metrics']['standalone_human_signoff_tasks_remaining']}`",
        f"Languages with harness handoff ready: `{built['metrics']['languages_with_harness_handoff_ready']}`",
        f"Languages with harness acceptance ready: `{built['metrics']['languages_with_harness_acceptance_ready']}`",
        f"Languages still stub only: `{built['metrics']['languages_still_stub_only']}`",
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
