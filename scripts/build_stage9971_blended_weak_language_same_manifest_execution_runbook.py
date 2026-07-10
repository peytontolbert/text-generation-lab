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
STAGE = 9971
NAME = "stage9971_blended_weak_language_same_manifest_execution_runbook"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
RUNBOOK = OUT_DIR / "blended_weak_language_same_manifest_execution_runbook.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "BLENDED_WEAK_LANGUAGE_SAME_MANIFEST_EXECUTION_RUNBOOK_STAGE9971.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"

HANDOFF = ROOT / "runs/local/artifacts/stage9968_blended_weak_language_same_manifest_handoff_bundle/blended_weak_language_same_manifest_handoff_bundle.json"
ACCEPT_100M = ROOT / "runs/local/artifacts/stage9972_blended_weak_language_output_acceptance_audit/blended_weak_language_output_acceptance_audit.json"
SIGNOFF = ROOT / "runs/local/artifacts/stage9970_blended_weak_language_same_manifest_signoff_workbook/blended_weak_language_same_manifest_signoff_workbook.json"


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


def build_runbook() -> dict[str, Any]:
    handoff = load_json(HANDOFF)
    signoff = load_json(SIGNOFF)
    failures: list[str] = []

    handoff_bundle = handoff.get("handoff_bundle") if isinstance(handoff.get("handoff_bundle"), dict) else {}
    hundred_m = handoff_bundle.get("hundred_m_execution") if isinstance(handoff_bundle.get("hundred_m_execution"), dict) else {}
    gemma = handoff_bundle.get("gemma_execution") if isinstance(handoff_bundle.get("gemma_execution"), dict) else {}
    row_contract = handoff_bundle.get("row_contract") if isinstance(handoff_bundle.get("row_contract"), dict) else {}

    if handoff.get("passed") is not True:
        failures.append("stage9968_not_passed")
    if signoff.get("passed") is not True:
        failures.append("stage9970_not_passed")

    steps = [
        {
            "step_id": "precheck_authorization_and_disk",
            "kind": "precheck",
            "requires": [
                "explicit_stage9965_100m_execution_authorization",
                "explicit_stage9971_gemma_execution_authorization",
                "repo_disk_and_tmp_disk_sufficient",
            ],
            "artifacts": [display(HANDOFF), display(SIGNOFF)],
        },
        {
            "step_id": "run_stage9965_hundred_m",
            "kind": "model_execution",
            "command": list(hundred_m.get("command") or []),
            "expected_output_dir": hundred_m.get("future_output_dir"),
            "expected_run_id": hundred_m.get("future_run_id"),
        },
        {
            "step_id": "audit_stage9965_outputs",
            "kind": "postcheck",
            "artifact": display(ACCEPT_100M),
            "requires": ["stage9965_output_acceptance_ready"],
        },
        {
            "step_id": "run_stage9971_gemma",
            "kind": "gemma_execution",
            "command": list(gemma.get("command") or []),
            "expected_output_stub": gemma.get("future_output_stub"),
        },
        {
            "step_id": "compare_same_manifest_only",
            "kind": "comparison_gate",
            "requires": list((handoff_bundle.get("comparison_rule") or {}).get("claim_permitted_only_after") or []),
            "row_contract": dict(row_contract),
        },
    ]

    metrics = {
        "runbook_steps": len(steps),
        "hundred_m_future_stage": hundred_m.get("future_stage"),
        "gemma_future_stage": gemma.get("future_stage"),
        "same_manifest_compare_rows": row_contract.get("same_manifest_compare_rows"),
        "row_contract_ok": (
            row_contract.get("hundred_m_rows") == 120
            and row_contract.get("gemma_rows") == 120
            and row_contract.get("hundred_m_python_rows") == 24
            and row_contract.get("hundred_m_c_cpp_rows") == 30
            and row_contract.get("hundred_m_web_rows") == 45
            and row_contract.get("same_manifest_compare_rows") == 80
        ),
    }
    if metrics["hundred_m_future_stage"] != 9965:
        failures.append("hundred_m_future_stage_not_9965")
    if metrics["gemma_future_stage"] != 9971:
        failures.append("gemma_future_stage_not_9971")
    if metrics["row_contract_ok"] is not True:
        failures.append("row_contract_not_ok")

    return {
        "passed": not failures,
        "failures": failures,
        "metrics": metrics,
        "steps": steps,
        "claim_rule": (handoff_bundle.get("comparison_rule") or {}),
        "authority": dict(AUTHORITY_CLOSED),
    }


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)
    built = build_runbook()
    RUNBOOK.write_text(json.dumps(built, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    next_step = "If execution is explicitly authorized, follow this runbook in order: run stage9965, audit stage9965 outputs, run the matching Gemma queue, then compare only those outputs on the exact same 120-row manifest."
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "name": NAME,
        "passed": built["passed"],
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {**dict(AUTHORITY_CLOSED), **built["metrics"], "failures": built["failures"]},
        "artifacts": {"runbook": display(RUNBOOK), "doc": display(DOC)},
        "decision": "Materialized the ordered same-manifest execution runbook for the weak-language recovery path so the first authorized 100M-vs-Gemma comparison can be run and audited in a fixed sequence.",
        "next_best_step": next_step,
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage9971 Blended Weak-Language Same-Manifest Execution Runbook",
        "",
        f"Passed: `{summary['passed']}`",
        f"Runbook steps: `{built['metrics']['runbook_steps']}`",
        f"100M future stage: `{built['metrics']['hundred_m_future_stage']}`",
        f"Gemma future stage: `{built['metrics']['gemma_future_stage']}`",
        f"Same-manifest compare rows: `{built['metrics']['same_manifest_compare_rows']}`",
        "",
        summary["decision"],
        "",
        f"Next: {next_step}",
        "",
    ]), encoding="utf-8")
    if summary["passed"]:
        update_registry(summary)
    print(json.dumps({
        "stage": STAGE,
        "passed": summary["passed"],
        "metrics": built["metrics"],
        "failures": built["failures"],
    }, indent=2, sort_keys=True))
    if built["failures"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
