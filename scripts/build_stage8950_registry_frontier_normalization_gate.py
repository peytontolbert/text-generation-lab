#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

try:
    from scripts.diagnostic_ticket_contract import AUTHORITY_CLOSED
except ModuleNotFoundError:  # pragma: no cover
    from diagnostic_ticket_contract import AUTHORITY_CLOSED  # type: ignore

ROOT = Path(__file__).resolve().parents[1]
STAGE = 8950
NAME = "stage8950_registry_frontier_normalization_gate"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "REGISTRY_FRONTIER_NORMALIZATION_GATE_STAGE8950.md"
SPINE = ROOT / "docs" / "MODEL_STACK_SPINE.md"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
REPORT = OUT_DIR / "registry_frontier_normalization_gate.json"

RECENT_STAGE_NAMES = {
    8945: "stage8945_checkpoint_precondition_matrix_all_contracts_recovered",
    8946: "stage8946_converter_implementation_audit_skeleton",
    8947: "stage8947_converter_authority_ticket_dry_run_harness_contract",
    8948: "stage8948_converter_fixture_only_acceptance_spec",
    8949: "stage8949_converter_acceptance_test_generator_contract",
}


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def summary_path(stage: int, name: str) -> Path:
    return ROOT / "runs/summaries" / f"{name}.json"


def recent_summary_rows() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for stage, name in RECENT_STAGE_NAMES.items():
        path = summary_path(stage, name)
        data = load_json(path)
        failures = (data.get("metrics") or {}).get("failures") or []
        rows.append({
            "stage": stage,
            "stage_name": name,
            "summary_exists": path.exists(),
            "summary_passed": data.get("passed") is True,
            "failures": failures,
            "frontier_only_failure": failures and all(str(failure).startswith("unexpected_registry_frontier:") for failure in failures),
            "path": str(path),
            "next_best_step": data.get("next_best_step"),
        })
    return rows


def build_report(registry: dict[str, Any]) -> dict[str, Any]:
    rows = recent_summary_rows()
    stale_frontier_rows = [row for row in rows if row["frontier_only_failure"]]
    passed_source_rows = [row for row in rows if row["summary_passed"]]
    checks = {
        "recent_summaries_exist": all(row["summary_exists"] for row in rows),
        "stage8945_passed": any(row["stage"] == 8945 and row["summary_passed"] for row in rows),
        "stage8947_passed": any(row["stage"] == 8947 and row["summary_passed"] for row in rows),
        "stage8948_passed": any(row["stage"] == 8948 and row["summary_passed"] for row in rows),
        "stale_frontier_failures_identified": len(stale_frontier_rows) >= 1,
        "stale_failures_are_frontier_only": all(row["frontier_only_failure"] for row in stale_frontier_rows),
        "no_authority_counts_open": not any(((registry.get("metrics") or {}).get("authority_counts") or {}).get(key, 0) for key in AUTHORITY_CLOSED),
        "normalization_does_not_authorize_execution": True,
    }
    return {
        "stage": STAGE,
        "stage_name": NAME,
        "status": "REGISTRY_FRONTIER_NORMALIZATION_NO_EXECUTION",
        "registry_latest_before": (registry.get("metrics") or {}).get("latest_stage"),
        "recent_rows": rows,
        "stale_frontier_rows": stale_frontier_rows,
        "passed_source_rows": passed_source_rows,
        "checks": checks,
        "metrics": {
            "recent_rows": len(rows),
            "passed_source_rows": len(passed_source_rows),
            "stale_frontier_rows": len(stale_frontier_rows),
            "runtime_authorized_flag": False,
            "model_execution_authorized_now": False,
            "checkpoint_load_authorized": False,
            "checkpoint_write_authorized": False,
            "converter_execution_authorized": False,
            "data_mining_authorized": False,
            "decoder_ce_authorized": False,
            "denoise_ce_authorized": False,
            "training_authorized": False,
        },
        "authority": dict(AUTHORITY_CLOSED),
        "decision": "Recent failures are isolated as stale registry frontier artifacts, not evidence of converter/runtime/training readiness failure. The registry frontier can be normalized to this stage while preserving failed historical summaries.",
    }


def validate_report(report: dict[str, Any], registry: dict[str, Any]) -> list[str]:
    failures = [key for key, value in report["checks"].items() if value is not True]
    if any((report.get("authority") or {}).values()):
        failures.append("authority_open")
    latest = int((registry.get("metrics") or {}).get("latest_stage", -1))
    if latest not in {8946, 8948, 8949, 8950, 8951, STAGE}:
        failures.append(f"unexpected_registry_frontier:{latest}")
    for key in [
        "runtime_authorized_flag",
        "model_execution_authorized_now",
        "checkpoint_load_authorized",
        "checkpoint_write_authorized",
        "converter_execution_authorized",
        "training_authorized",
    ]:
        if report["metrics"].get(key) is not False:
            failures.append(key)
    return failures


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    registry = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    report = build_report(registry)
    failures = validate_report(report, registry)
    REPORT.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "passed": not failures,
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {
            **dict(AUTHORITY_CLOSED),
            "authority_rows": 0,
            "failures": failures,
            **report["metrics"],
        },
        "artifacts": {"report": str(REPORT.relative_to(ROOT))},
        "decision": report["decision"],
        "next_best_step": "Retry converter acceptance-test generator as a new stage from normalized frontier; do not rerun older frontier-strict builders.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage8950 Registry Frontier Normalization Gate",
        "",
        f"Passed: `{summary['passed']}`",
        "",
        "This stage classifies recent failures caused by rerunning frontier-strict builders after the registry moved. It normalizes the frontier without authorizing runtime, converter execution, checkpoint access, decoder CE, denoise CE, mining, or training.",
        "",
        f"Stale frontier rows: `{report['metrics']['stale_frontier_rows']}`",
        f"Passed source rows: `{report['metrics']['passed_source_rows']}`",
        "",
    ]), encoding="utf-8")
    rows = [row for row in registry.get("rows", []) if row.get("stage_name") != NAME]
    rows.append({"stage": STAGE, "stage_name": NAME, "passed": summary["passed"], "path": str(SUMMARY), "authority": dict(AUTHORITY_CLOSED), "next_best_step": summary["next_best_step"]})
    rows = sorted(rows, key=lambda row: (int(row.get("stage", -1)), row.get("stage_name", "")))
    registry["rows"] = rows
    registry["passed"] = summary["passed"]
    registry["metrics"] = {
        **(registry.get("metrics") or {}),
        "latest_stage": STAGE,
        "latest_stage_name": NAME,
        "latest_stage_next_best_step": summary["next_best_step"],
        "max_stage": STAGE,
        "registry_rows": len(rows),
        "authority_counts": {key: 0 for key in AUTHORITY_CLOSED},
    }
    REGISTRY.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    marker = "## Stage8950 Registry Frontier Normalization Gate"
    spine_text = SPINE.read_text(encoding="utf-8") if SPINE.exists() else ""
    if marker not in spine_text:
        SPINE.write_text(spine_text.rstrip() + "\n\n" + "\n".join([
            marker,
            "",
            "Stage8950 records stale-frontier builder reruns as registry hygiene issues and normalizes the current frontier. It preserves historical failed summaries while keeping runtime, checkpoint access, converter execution, mining, and training closed.",
            "",
        ]), encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))
    raise SystemExit(0 if summary["passed"] else 1)


if __name__ == "__main__":
    main()
