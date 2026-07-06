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
STAGE = 8991
NAME = "stage8991_parquet_footer_metadata_execution_gate_design"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "PARQUET_FOOTER_METADATA_EXECUTION_GATE_DESIGN_STAGE8991.md"
SPINE = ROOT / "docs" / "MODEL_STACK_SPINE.md"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
GATE = OUT_DIR / "parquet_footer_metadata_execution_gate_design_not_granted.json"
SOURCE_SUMMARY = ROOT / "runs/summaries/stage8985_active_parquet_footer_ticket_instance_audit.json"
SOURCE_TICKET = ROOT / "runs/local/artifacts/stage8984_active_parquet_footer_ticket_instance_design/active_parquet_footer_ticket_instance_pending_audit.json"
SELECTED_IDS = ROOT / "runs/local/artifacts/stage8984_active_parquet_footer_ticket_instance_design/selected_candidate_ids_pending_audit.jsonl"

ALLOWED_PROBE_TYPE = "PARQUET_FOOTER_SCHEMA_METADATA_ONLY"
GATE_STATE = "DESIGNED_NOT_GRANTED"
MAX_CANDIDATES = 5
REQUIRED_OUTPUTS = [
    "footer_schema_metadata.jsonl",
    "footer_access_audit_card.json",
    "candidate_footer_metadata_card.json",
    "no_row_read_proof.json",
    "next_schema_judge_input.jsonl",
]
FORBIDDEN_OPERATIONS = [
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
]
REQUIRED_RUNTIME_ASSERTIONS = [
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
]


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def selected_ids(rows: list[dict[str, Any]]) -> list[str]:
    return [str(row.get("candidate_id")) for row in rows if row.get("candidate_id") is not None]


def build_gate(ticket: dict[str, Any], selected: list[dict[str, Any]]) -> dict[str, Any]:
    ids = selected_ids(selected)
    return {
        "gate_id": "stage8991_future_parquet_footer_metadata_execution_gate",
        "gate_state": GATE_STATE,
        "source_ticket_id": ticket.get("ticket_id"),
        "allowed_probe_type": ALLOWED_PROBE_TYPE,
        "selected_candidate_ids": ids,
        "selected_candidate_count": len(ids),
        "max_candidates": MAX_CANDIDATES,
        "output_dir": "runs/local/artifacts/future_stage899x_parquet_footer_metadata_only_access",
        "required_outputs": list(REQUIRED_OUTPUTS),
        "forbidden_operations": list(FORBIDDEN_OPERATIONS),
        "required_runtime_assertions": list(REQUIRED_RUNTIME_ASSERTIONS),
        "grant_requires_stage8985_passed": True,
        "grant_requires_manual_execution_authorization": True,
        "grant_requires_clean_worktree_or_explicit_dirty_card": True,
        "grant_requires_no_arxiv_write": True,
        "row_body_reads_allowed": False,
        "repository_source_body_reads_allowed": False,
        "arxiv_write_allowed": False,
        "batch_materialization_allowed": False,
        "footer_access_authorized_now": False,
        "execution_authorized": False,
        "training_authorized": False,
        "model_execution_authorized": False,
        "runtime_authorized": False,
    }


def validate_gate(gate: dict[str, Any], ticket: dict[str, Any], selected: list[dict[str, Any]]) -> list[str]:
    failures: list[str] = []
    ids = selected_ids(selected)
    if gate.get("gate_state") != GATE_STATE:
        failures.append("gate_state")
    if gate.get("allowed_probe_type") != ALLOWED_PROBE_TYPE:
        failures.append("allowed_probe_type")
    if gate.get("selected_candidate_ids") != ids:
        failures.append("selected_candidate_ids")
    if gate.get("selected_candidate_ids") != (ticket.get("selected_candidate_ids") or []):
        failures.append("ticket_candidate_ids")
    if len(ids) == 0 or len(ids) > MAX_CANDIDATES:
        failures.append("candidate_count")
    if len(ids) != len(set(ids)):
        failures.append("duplicate_candidate_ids")
    if not str(gate.get("output_dir", "")).startswith("runs/local/artifacts/"):
        failures.append("output_dir")
    for item in REQUIRED_OUTPUTS:
        if item not in set(gate.get("required_outputs") or []):
            failures.append(f"missing_output:{item}")
    for item in FORBIDDEN_OPERATIONS:
        if item not in set(gate.get("forbidden_operations") or []):
            failures.append(f"missing_forbidden:{item}")
    for item in REQUIRED_RUNTIME_ASSERTIONS:
        if item not in set(gate.get("required_runtime_assertions") or []):
            failures.append(f"missing_runtime_assertion:{item}")
    for flag in [
        "row_body_reads_allowed",
        "repository_source_body_reads_allowed",
        "arxiv_write_allowed",
        "batch_materialization_allowed",
        "footer_access_authorized_now",
        "execution_authorized",
        "training_authorized",
        "model_execution_authorized",
        "runtime_authorized",
    ]:
        if gate.get(flag) is not False:
            failures.append(flag)
    return failures


def build_design(registry: dict[str, Any]) -> dict[str, Any]:
    source = load_json(SOURCE_SUMMARY)
    ticket = load_json(SOURCE_TICKET)
    selected = read_jsonl(SELECTED_IDS)
    gate = build_gate(ticket, selected)
    gate_failures = validate_gate(gate, ticket, selected)
    checks = {
        "source_stage8985_passed": source.get("passed") is True,
        "source_ticket_present": SOURCE_TICKET.exists(),
        "selected_ids_present": SELECTED_IDS.exists() and len(selected) > 0,
        "gate_valid_not_granted": not gate_failures,
        "gate_state_not_granted": gate.get("gate_state") == GATE_STATE,
        "footer_access_not_authorized": gate.get("footer_access_authorized_now") is False,
        "execution_not_authorized": gate.get("execution_authorized") is False,
        "required_outputs_recorded": len(gate.get("required_outputs") or []) >= len(REQUIRED_OUTPUTS),
        "forbidden_operations_recorded": len(gate.get("forbidden_operations") or []) >= len(FORBIDDEN_OPERATIONS),
        "runtime_assertions_recorded": len(gate.get("required_runtime_assertions") or []) >= len(REQUIRED_RUNTIME_ASSERTIONS),
        "authority_counts_zero": not any(((registry.get("metrics") or {}).get("authority_counts") or {}).get(key, 0) for key in AUTHORITY_CLOSED),
    }
    return {
        "stage": STAGE,
        "stage_name": NAME,
        "status": "PARQUET_FOOTER_METADATA_EXECUTION_GATE_DESIGN_NOT_GRANTED",
        "gate": gate,
        "gate_failures": gate_failures,
        "checks": checks,
        "metrics": {
            "selected_candidate_count": len(selected),
            "required_outputs": len(REQUIRED_OUTPUTS),
            "forbidden_operations": len(FORBIDDEN_OPERATIONS),
            "required_runtime_assertions": len(REQUIRED_RUNTIME_ASSERTIONS),
            "gate_failures": len(gate_failures),
            "gate_designed": True,
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
        "decision": "Parquet-footer metadata execution gate is designed but not granted. It specifies the only future allowed footer-metadata access shape and keeps execution closed.",
    }


def validate_design(card: dict[str, Any]) -> list[str]:
    failures = [key for key, value in card["checks"].items() if value is not True]
    if any((card.get("authority") or {}).values()):
        failures.append("authority_open")
    if card["metrics"].get("gate_failures") != 0:
        failures.append("gate_failures")
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
    card = build_design(registry)
    failures = validate_design(card)
    GATE.write_text(json.dumps(card["gate"], indent=2, sort_keys=True) + "\n", encoding="utf-8")
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "passed": not failures,
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {**dict(AUTHORITY_CLOSED), "authority_rows": 0, "failures": failures, **card["metrics"]},
        "artifacts": {"gate": str(GATE.relative_to(ROOT))},
        "decision": card["decision"],
        "next_best_step": "Audit this execution-gate design. Do not perform parquet footer access until an explicit later gate grants exactly one metadata-only command.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage8991 Parquet Footer Metadata Execution Gate Design",
        "",
        f"Passed: `{summary['passed']}`",
        "",
        "This stage designs the future execution gate for parquet-footer schema metadata access. It is not granted and does not open files, read footers, read rows, write `/arxiv`, mine, train, or execute models.",
        "",
        f"Selected candidate count: `{summary['metrics']['selected_candidate_count']}`",
        f"Gate granted: `{summary['metrics']['gate_granted']}`",
        f"Execution authorized: `{summary['metrics']['execution_authorized']}`",
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
    marker = "## Stage8991 Parquet Footer Metadata Execution Gate Design"
    spine_text = SPINE.read_text(encoding="utf-8") if SPINE.exists() else ""
    if marker not in spine_text:
        SPINE.write_text(spine_text.rstrip() + "\n\n" + "\n".join([
            marker,
            "",
            "Stage8991 designs but does not grant the future parquet-footer metadata execution gate. Footer access, row/source-body reads, `/arxiv` writes, mining, training, model execution, and runtime remain closed.",
            "",
        ]), encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))
    raise SystemExit(0 if summary["passed"] else 1)


if __name__ == "__main__":
    main()
