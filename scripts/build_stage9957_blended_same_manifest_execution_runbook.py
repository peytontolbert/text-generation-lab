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
STAGE = 9957
NAME = "stage9957_blended_same_manifest_execution_runbook"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
RUNBOOK = OUT_DIR / "blended_same_manifest_execution_runbook.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "BLENDED_SAME_MANIFEST_EXECUTION_RUNBOOK_STAGE9957.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
HANDOFF = ROOT / "runs/local/artifacts/stage9955_blended_same_manifest_execution_handoff_bundle/blended_same_manifest_execution_handoff_bundle.json"
BLOCKERS = ROOT / "runs/local/artifacts/stage9956_v27_current_blocker_ledger/v27_current_blocker_ledger.json"
ACCEPT_100M = ROOT / "runs/local/artifacts/stage9951_blended_edit_localization_output_acceptance_audit/blended_edit_localization_output_acceptance_audit.json"
COMPARE_GATE = ROOT / "runs/local/artifacts/stage9954_blended_edit_localization_same_manifest_comparison_gate/blended_edit_localization_same_manifest_comparison_gate.json"


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
    blockers = load_json(BLOCKERS)
    accept_100m = load_json(ACCEPT_100M)
    compare_gate = load_json(COMPARE_GATE)
    failures: list[str] = []

    bundle = handoff.get("handoff_bundle") if isinstance(handoff.get("handoff_bundle"), dict) else {}
    if handoff.get("passed") is not True:
        failures.append("stage9955_not_passed")
    if blockers.get("passed") is not True:
        failures.append("stage9956_not_passed")
    if compare_gate.get("passed") is not True:
        failures.append("stage9954_not_passed")

    hundred_m = bundle.get("hundred_m_execution") if isinstance(bundle.get("hundred_m_execution"), dict) else {}
    gemma = bundle.get("gemma_execution") if isinstance(bundle.get("gemma_execution"), dict) else {}
    row_contract = bundle.get("row_contract") if isinstance(bundle.get("row_contract"), dict) else {}
    completion_boundary = blockers.get("completion_boundary") if isinstance(blockers.get("completion_boundary"), dict) else {}

    steps = [
        {
            "step_id": "precheck_authorization_and_disk",
            "kind": "precheck",
            "requires": [
                "explicit_stage9950_100m_execution_authorization",
                "explicit_stage9953_gemma_execution_authorization",
                "repo_disk_and_tmp_disk_sufficient",
            ],
            "artifacts": [
                display(HANDOFF),
                display(BLOCKERS),
            ],
        },
        {
            "step_id": "run_stage9950_hundred_m",
            "kind": "model_execution",
            "command": list(hundred_m.get("command") or []),
            "expected_output_dir": hundred_m.get("future_output_dir"),
            "expected_run_id": hundred_m.get("future_run_id"),
        },
        {
            "step_id": "audit_stage9950_outputs",
            "kind": "postcheck",
            "artifact": display(ACCEPT_100M),
            "requires": ["stage9950_output_acceptance_ready"],
        },
        {
            "step_id": "run_stage9953_gemma",
            "kind": "gemma_execution",
            "command": list(gemma.get("command") or []),
            "expected_output_stub": gemma.get("future_output_stub"),
        },
        {
            "step_id": "compare_same_manifest_only",
            "kind": "comparison_gate",
            "artifact": display(COMPARE_GATE),
            "requires": list((compare_gate.get("gate_rows") or {}).get("same_manifest_claim_permitted_only_after") or []),
        },
    ]

    metrics = {
        "runbook_steps": len(steps),
        "hundred_m_future_stage": hundred_m.get("future_stage"),
        "gemma_future_stage": gemma.get("future_stage"),
        "row_contract_ok": row_contract.get("hundred_m_rows") == 72 and row_contract.get("gemma_rows") == 72 and row_contract.get("hundred_m_web_rows") == 27 and row_contract.get("gemma_web_rows") == 27,
        "claim_rule_present": "claim_rule" in completion_boundary,
    }
    if metrics["hundred_m_future_stage"] != 9950:
        failures.append("hundred_m_future_stage_not_9950")
    if metrics["gemma_future_stage"] != 9953:
        failures.append("gemma_future_stage_not_9953")
    if metrics["row_contract_ok"] is not True:
        failures.append("row_contract_not_ok")
    if metrics["claim_rule_present"] is not True:
        failures.append("claim_rule_missing")

    return {
        "passed": not failures,
        "failures": failures,
        "metrics": metrics,
        "steps": steps,
        "claim_rule": completion_boundary.get("claim_rule"),
        "still_requires_real_execution_or_external_input": list(completion_boundary.get("still_requires_real_execution_or_external_input") or []),
        "authority": dict(AUTHORITY_CLOSED),
    }


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)
    built = build_runbook()
    RUNBOOK.write_text(json.dumps(built, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    next_step = "If execution is explicitly authorized, follow this runbook in order: run stage9950, audit stage9950 outputs, run the matching Gemma queue, then apply the stage9954 same-manifest comparison gate before making any narrow blended claim."
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "name": NAME,
        "passed": built["passed"],
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {**dict(AUTHORITY_CLOSED), **built["metrics"], "failures": built["failures"]},
        "artifacts": {"runbook": display(RUNBOOK), "doc": display(DOC)},
        "decision": "Materialized an ordered execution runbook for the narrow blended same-manifest path so the first authorized 100M-vs-Gemma comparison can be run and audited in a fixed sequence.",
        "next_best_step": next_step,
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage9957 Blended Same-Manifest Execution Runbook",
        "",
        f"Passed: `{summary['passed']}`",
        f"Runbook steps: `{built['metrics']['runbook_steps']}`",
        f"100M future stage: `{built['metrics']['hundred_m_future_stage']}`",
        f"Gemma future stage: `{built['metrics']['gemma_future_stage']}`",
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
        "next_best_step": next_step,
    }, indent=2, sort_keys=True))
    if built["failures"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
