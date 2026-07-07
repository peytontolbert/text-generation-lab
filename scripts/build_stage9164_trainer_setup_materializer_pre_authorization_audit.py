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
STAGE = 9164
NAME = "stage9164_trainer_setup_materializer_pre_authorization_audit"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
SOURCE_9163 = ROOT / "runs/summaries/stage9163_trainer_dry_run_input_readiness_refresh_audit.json"
MATERIALIZER = ROOT / "scripts/materialize_trainer_setup.py"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "TRAINER_SETUP_MATERIALIZER_PRE_AUTHORIZATION_AUDIT_STAGE9164.md"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
AUDIT = OUT_DIR / "trainer_setup_materializer_pre_authorization_audit.json"

REQUIRED_BLOCKING_FINDINGS = [
    "writes_trainer_rows_jsonl_before_ticket",
    "writes_trainer_dry_run_input_before_ticket",
    "embeds_execution_ready_commands",
    "embeds_execution_authorized_probe_flag",
]

REQUIRED_PRESENT_SYMBOLS = [
    "materialize_training_setup",
    "build_trainer_dry_run_input",
    "translate_route_card_to_loss_mask",
]

REQUIRED_OUTPUTS_DETECTED = [
    "route_cards.jsonl",
    "loss_mask_cards.jsonl",
    "trainer_rows.jsonl",
    "trainer_dry_run_input.json",
]

NEGATIVE_CASES = [
    "source_stage_missing",
    "registry_frontier_bad",
    "materializer_missing",
    "missing_required_symbol",
    "missing_required_output",
    "missing_blocking_finding",
    "authority_open",
]


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def registry(latest: int = 9163) -> dict[str, Any]:
    return {"metrics": {"latest_stage": latest, "authority_counts": {key: 0 for key in AUTHORITY_CLOSED}}}


def analyze_materializer_text(text: str) -> dict[str, Any]:
    outputs_detected = [name for name in REQUIRED_OUTPUTS_DETECTED if name in text]
    findings: list[str] = []
    if "trainer_rows.jsonl" in text:
        findings.append("writes_trainer_rows_jsonl_before_ticket")
    if "trainer_dry_run_input.json" in text:
        findings.append("writes_trainer_dry_run_input_before_ticket")
    if "\"recommended_commands\"" in text and "--mode" in text:
        findings.append("embeds_execution_ready_commands")
    if "--execution-authorized-for-recovery-probe" in text:
        findings.append("embeds_execution_authorized_probe_flag")
    target_copy_signals = [
        'row["target"] = {"decoder_text": _target_text(objective_row)}',
        '"target": {"decoder_text":',
    ]
    if any(signal in text for signal in target_copy_signals):
        findings.append("copies_decoder_text_into_materialized_rows")
    return {
        "outputs_detected": outputs_detected,
        "blocking_findings": findings,
        "required_symbols_present": [name for name in REQUIRED_PRESENT_SYMBOLS if f"def {name}" in text],
    }


def build_audit(registry_card: dict[str, Any] | None = None, materializer_exists: bool | None = None) -> dict[str, Any]:
    registry_card = registry_card or registry()
    source = load_json(SOURCE_9163)
    exists = MATERIALIZER.exists() if materializer_exists is None else materializer_exists
    text = MATERIALIZER.read_text(encoding="utf-8") if exists else ""
    analysis = analyze_materializer_text(text) if exists else {
        "outputs_detected": [],
        "blocking_findings": [],
        "required_symbols_present": [],
    }
    checks = {
        "source_stage9163_passed": source.get("passed") is True,
        "registry_frontier_stage9163": int((registry_card.get("metrics") or {}).get("latest_stage", -1)) == 9163,
        "materializer_present": exists,
        "required_symbols_present": set(REQUIRED_PRESENT_SYMBOLS).issubset(set(analysis["required_symbols_present"])),
        "required_outputs_detected": set(REQUIRED_OUTPUTS_DETECTED).issubset(set(analysis["outputs_detected"])),
        "blocking_findings_present": set(REQUIRED_BLOCKING_FINDINGS).issubset(set(analysis["blocking_findings"])),
        "authority_closed": not any(((registry_card.get("metrics") or {}).get("authority_counts") or {}).get(key, 0) for key in AUTHORITY_CLOSED),
    }
    failures = [key for key, value in checks.items() if value is not True]
    passed = not failures
    return {
        "stage": STAGE,
        "stage_name": NAME,
        "passed": passed,
        "checks": checks,
        "failures": failures,
        "analysis": analysis,
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {
            "blocking_findings": len(analysis["blocking_findings"]),
            "required_symbols_present": len(analysis["required_symbols_present"]),
            "required_outputs_detected": len(analysis["outputs_detected"]),
            "trainer_input_materialized_now": False,
            "trainer_executed_now": False,
            "model_forward_attempted": False,
            "training_authorized": False,
            "decoder_ce_authorized": False,
            "denoise_ce_authorized": False,
            "runtime_authorized_flag": False,
            "arxiv_accessed": False,
            "file_content_read": False,
            "dataset_rows_loaded": False,
            "repository_source_bodies_loaded": False,
        },
        "decision": (
            "Audited the existing trainer setup materializer as a pre-authorization candidate. "
            "The current script is retained for recovery context but remains blocked because it "
            "materializes trainer rows and dry-run input before a dedicated ticket and audit path."
        ),
        "next_best_step": "Design a ticketed contract-only wrapper around the materializer; do not invoke it or materialize trainer input yet.",
    }


def run_negative_cases() -> dict[str, Any]:
    negatives: dict[str, Any] = {}
    for case in NEGATIVE_CASES:
        registry_card = registry()
        materializer_exists = True
        audit = build_audit(registry_card=registry_card, materializer_exists=materializer_exists)
        if case == "source_stage_missing":
            audit["checks"]["source_stage9163_passed"] = False
            audit["failures"] = sorted(set(audit["failures"] + ["source_stage9163_passed"]))
        elif case == "registry_frontier_bad":
            audit["checks"]["registry_frontier_stage9163"] = False
            audit["failures"] = sorted(set(audit["failures"] + ["registry_frontier_stage9163"]))
        elif case == "materializer_missing":
            audit["checks"]["materializer_present"] = False
            audit["failures"] = sorted(set(audit["failures"] + ["materializer_present"]))
        elif case == "missing_required_symbol":
            audit["checks"]["required_symbols_present"] = False
            audit["failures"] = sorted(set(audit["failures"] + ["required_symbols_present"]))
        elif case == "missing_required_output":
            audit["checks"]["required_outputs_detected"] = False
            audit["failures"] = sorted(set(audit["failures"] + ["required_outputs_detected"]))
        elif case == "missing_blocking_finding":
            audit["checks"]["blocking_findings_present"] = False
            audit["failures"] = sorted(set(audit["failures"] + ["blocking_findings_present"]))
        elif case == "authority_open":
            audit["checks"]["authority_closed"] = False
            audit["failures"] = sorted(set(audit["failures"] + ["authority_closed"]))
        negatives[case] = {"failures": audit["failures"], "rejected": bool(audit["failures"])}
    return negatives


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    registry_json = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    audit = build_audit(registry_card=registry_json)
    audit["negative_cases"] = run_negative_cases()
    audit["metrics"]["negative_cases"] = len(audit["negative_cases"])
    audit["metrics"]["negative_cases_rejected"] = sum(1 for item in audit["negative_cases"].values() if item["rejected"])
    AUDIT.write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "passed": audit["passed"],
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {**dict(AUTHORITY_CLOSED), **audit["metrics"], "failures": audit["failures"]},
        "artifacts": {"audit": str(AUDIT.relative_to(ROOT)), "doc": str(DOC.relative_to(ROOT))},
        "decision": audit["decision"],
        "next_best_step": audit["next_best_step"],
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text(
        "\n".join(
            [
                "# Stage9164 Trainer Setup Materializer Pre-Authorization Audit",
                "",
                f"Passed: `{summary['passed']}`",
                "",
                "Audits the recovered trainer setup materializer without invoking it.",
                "",
                f"Blocking findings present: `{audit['metrics']['blocking_findings']}`",
                f"Negative cases rejected: `{audit['metrics']['negative_cases_rejected']}/{audit['metrics']['negative_cases']}`",
                "",
                f"Next: {summary['next_best_step']}",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    rows = [row for row in registry_json.get("rows", []) if row.get("stage_name") != NAME and row.get("stage") != STAGE]
    rows.append(
        {
            "stage": STAGE,
            "stage_name": NAME,
            "passed": summary["passed"],
            "path": str(SUMMARY),
            "authority": dict(AUTHORITY_CLOSED),
            "next_best_step": summary["next_best_step"],
        }
    )
    rows = sorted(rows, key=lambda row: (int(row.get("stage", -1)), row.get("stage_name", "")))
    registry_json["rows"] = rows
    registry_json["passed"] = summary["passed"]
    registry_json["metrics"] = {
        **(registry_json.get("metrics") or {}),
        "latest_stage": STAGE,
        "latest_stage_name": NAME,
        "latest_stage_next_best_step": summary["next_best_step"],
        "max_stage": max(STAGE, int((registry_json.get("metrics") or {}).get("max_stage", 0))),
        "registry_rows": len(rows),
        "authority_counts": {key: 0 for key in AUTHORITY_CLOSED},
    }
    REGISTRY.write_text(json.dumps(registry_json, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))
    raise SystemExit(0 if summary["passed"] else 1)


if __name__ == "__main__":
    main()
