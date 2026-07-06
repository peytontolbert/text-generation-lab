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
STAGE = 8992
NAME = "stage8992_parquet_footer_metadata_execution_gate_audit"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "PARQUET_FOOTER_METADATA_EXECUTION_GATE_AUDIT_STAGE8992.md"
SPINE = ROOT / "docs" / "MODEL_STACK_SPINE.md"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
AUDIT = OUT_DIR / "parquet_footer_metadata_execution_gate_audit.json"
SOURCE_SUMMARY = ROOT / "runs/summaries/stage8991_parquet_footer_metadata_execution_gate_design.json"
SOURCE_GATE = ROOT / "runs/local/artifacts/stage8991_parquet_footer_metadata_execution_gate_design/parquet_footer_metadata_execution_gate_design_not_granted.json"
SOURCE_TICKET = ROOT / "runs/local/artifacts/stage8984_active_parquet_footer_ticket_instance_design/active_parquet_footer_ticket_instance_pending_audit.json"

REQUIRED_OUTPUTS = {
    "footer_schema_metadata.jsonl",
    "footer_access_audit_card.json",
    "candidate_footer_metadata_card.json",
    "no_row_read_proof.json",
    "next_schema_judge_input.jsonl",
}
FORBIDDEN_OPERATIONS = {
    "DATASET_ROW_SCAN",
    "DATASET_ROW_MATERIALIZATION",
    "PARQUET_BATCH_MATERIALIZATION",
    "PARQUET_DATA_PAGE_READ",
    "REPOSITORY_SOURCE_BODY_READ",
    "ARXIV_WRITE",
    "TRAINING",
    "MINING",
    "MODEL_EXECUTION",
    "RUNTIME_EXECUTION",
    "NETWORK_UPLOAD",
}
REQUIRED_ASSERTIONS = {
    "candidate_ids_match_stage8984_ticket",
    "candidate_count_lte_5",
    "probe_type_exact_parquet_footer_schema_metadata_only",
    "read_footer_metadata_only",
    "no_row_groups_materialized",
    "no_dataset_rows_loaded",
    "no_repository_source_bodies_loaded",
    "output_dir_under_runs_local_artifacts",
    "write_marker_under_output_dir_only",
    "abort_on_any_forbidden_operation",
}
FALSE_GATE_FLAGS = [
    "row_body_reads_allowed",
    "repository_source_body_reads_allowed",
    "arxiv_write_allowed",
    "batch_materialization_allowed",
    "footer_access_authorized_now",
    "execution_authorized",
    "training_authorized",
    "model_execution_authorized",
    "runtime_authorized",
]


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def audit_gate(gate: dict[str, Any], ticket: dict[str, Any]) -> dict[str, Any]:
    selected_ids = [str(item) for item in gate.get("selected_candidate_ids") or []]
    ticket_ids = [str(item) for item in ticket.get("selected_candidate_ids") or []]
    missing_outputs = sorted(REQUIRED_OUTPUTS - set(gate.get("required_outputs") or []))
    missing_forbidden = sorted(FORBIDDEN_OPERATIONS - set(gate.get("forbidden_operations") or []))
    missing_assertions = sorted(REQUIRED_ASSERTIONS - set(gate.get("required_runtime_assertions") or []))
    false_flag_failures = [flag for flag in FALSE_GATE_FLAGS if gate.get(flag) is not False]
    return {
        "selected_candidate_count": len(selected_ids),
        "selected_ids_match_ticket": selected_ids == ticket_ids,
        "duplicate_candidate_ids": len(selected_ids) != len(set(selected_ids)),
        "missing_outputs": missing_outputs,
        "missing_forbidden_operations": missing_forbidden,
        "missing_runtime_assertions": missing_assertions,
        "false_flag_failures": false_flag_failures,
        "output_dir_under_runs_local_artifacts": str(gate.get("output_dir", "")).startswith("runs/local/artifacts/"),
        "allowed_probe_type_exact": gate.get("allowed_probe_type") == "PARQUET_FOOTER_SCHEMA_METADATA_ONLY",
        "gate_state_not_granted": gate.get("gate_state") == "DESIGNED_NOT_GRANTED",
    }


def build_audit(registry: dict[str, Any]) -> dict[str, Any]:
    source = load_json(SOURCE_SUMMARY)
    gate = load_json(SOURCE_GATE)
    ticket = load_json(SOURCE_TICKET)
    audit = audit_gate(gate, ticket)
    checks = {
        "source_stage8991_passed": source.get("passed") is True,
        "source_gate_present": SOURCE_GATE.exists(),
        "source_ticket_present": SOURCE_TICKET.exists(),
        "gate_state_not_granted": audit["gate_state_not_granted"] is True,
        "allowed_probe_type_exact": audit["allowed_probe_type_exact"] is True,
        "selected_ids_match_ticket": audit["selected_ids_match_ticket"] is True,
        "candidate_count_lte_5": 0 < audit["selected_candidate_count"] <= 5,
        "no_duplicate_candidate_ids": audit["duplicate_candidate_ids"] is False,
        "required_outputs_complete": not audit["missing_outputs"],
        "forbidden_operations_complete": not audit["missing_forbidden_operations"],
        "runtime_assertions_complete": not audit["missing_runtime_assertions"],
        "false_flags_preserved": not audit["false_flag_failures"],
        "output_dir_under_runs_local_artifacts": audit["output_dir_under_runs_local_artifacts"] is True,
        "authority_counts_zero": not any(((registry.get("metrics") or {}).get("authority_counts") or {}).get(key, 0) for key in AUTHORITY_CLOSED),
    }
    return {
        "stage": STAGE,
        "stage_name": NAME,
        "status": "PARQUET_FOOTER_METADATA_EXECUTION_GATE_AUDIT_NO_GRANT",
        "gate_audit": audit,
        "checks": checks,
        "metrics": {
            "selected_candidate_count": audit["selected_candidate_count"],
            "missing_outputs": len(audit["missing_outputs"]),
            "missing_forbidden_operations": len(audit["missing_forbidden_operations"]),
            "missing_runtime_assertions": len(audit["missing_runtime_assertions"]),
            "false_flag_failures": len(audit["false_flag_failures"]),
            "gate_audit_passed": all(checks.values()),
            "gate_granted": False,
            "footer_access_authorized_now": False,
            "execution_authorized": False,
            "parquet_footer_access_performed": False,
            "candidate_file_opened": False,
            "schema_or_header_read_performed": False,
            "dataset_rows_loaded": False,
            "repository_source_bodies_loaded": False,
            "arxiv_write_authorized": False,
            "training_authorized": False,
            "data_mining_authorized": False,
            "model_execution_attempted": False,
            "decoder_ce_authorized": False,
            "denoise_ce_authorized": False,
            "runtime_authorized_flag": False,
            "network_upload_performed": False,
        },
        "authority": dict(AUTHORITY_CLOSED),
        "decision": "Parquet-footer metadata execution-gate design audit passed, but the gate is still not granted. Footer access remains closed until a separate one-command grant stage exists.",
    }


def validate_audit(card: dict[str, Any]) -> list[str]:
    failures = [key for key, value in card["checks"].items() if value is not True]
    if any((card.get("authority") or {}).values()):
        failures.append("authority_open")
    for key in ["missing_outputs", "missing_forbidden_operations", "missing_runtime_assertions", "false_flag_failures"]:
        if card["metrics"].get(key) != 0:
            failures.append(key)
    for key in [
        "gate_granted",
        "footer_access_authorized_now",
        "execution_authorized",
        "parquet_footer_access_performed",
        "candidate_file_opened",
        "schema_or_header_read_performed",
        "dataset_rows_loaded",
        "repository_source_bodies_loaded",
        "arxiv_write_authorized",
        "training_authorized",
        "data_mining_authorized",
        "model_execution_attempted",
        "decoder_ce_authorized",
        "denoise_ce_authorized",
        "runtime_authorized_flag",
        "network_upload_performed",
    ]:
        if card["metrics"].get(key) is not False:
            failures.append(key)
    return failures


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    registry = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    card = build_audit(registry)
    failures = validate_audit(card)
    AUDIT.write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "passed": not failures,
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {**dict(AUTHORITY_CLOSED), "authority_rows": 0, "failures": failures, **card["metrics"]},
        "artifacts": {"audit": str(AUDIT.relative_to(ROOT))},
        "decision": card["decision"],
        "next_best_step": "If approved later, design a one-command footer metadata grant stage with exact command, output dir, and no-row-read proof. Do not run it yet.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage8992 Parquet Footer Metadata Execution Gate Audit",
        "",
        f"Passed: `{summary['passed']}`",
        "",
        "This stage audits the Stage8991 future execution-gate design. It still does not grant footer access, open files, read footers, read rows, write `/arxiv`, mine, train, or execute models.",
        "",
        f"Missing outputs: `{summary['metrics']['missing_outputs']}`",
        f"Missing forbidden operations: `{summary['metrics']['missing_forbidden_operations']}`",
        f"Missing runtime assertions: `{summary['metrics']['missing_runtime_assertions']}`",
        f"Gate granted: `{summary['metrics']['gate_granted']}`",
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
        "max_stage": max(STAGE, int((registry.get("metrics") or {}).get("max_stage", 0))),
        "registry_rows": len(rows),
        "authority_counts": {key: 0 for key in AUTHORITY_CLOSED},
    }
    REGISTRY.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    marker = "## Stage8992 Parquet Footer Metadata Execution Gate Audit"
    spine_text = SPINE.read_text(encoding="utf-8") if SPINE.exists() else ""
    if marker not in spine_text:
        SPINE.write_text(spine_text.rstrip() + "\n\n" + "\n".join([
            marker,
            "",
            "Stage8992 audits the future parquet-footer metadata execution-gate design but still grants no footer access. A later one-command grant stage is required before any metadata access can run.",
            "",
        ]), encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))
    raise SystemExit(0 if summary["passed"] else 1)


if __name__ == "__main__":
    main()
