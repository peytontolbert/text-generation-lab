#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

try:
    from scripts.diagnostic_ticket_contract import (
        AUTHORITY_CLOSED,
        apply_diagnostic_gate_fields,
        audit_diagnostic_ticket_fields,
    )
except ModuleNotFoundError:  # pragma: no cover
    from diagnostic_ticket_contract import (  # type: ignore
        AUTHORITY_CLOSED,
        apply_diagnostic_gate_fields,
        audit_diagnostic_ticket_fields,
    )

ROOT = Path(__file__).resolve().parents[1]
STAGE = 9052
NAME = "stage9052_long_context_source_output_ticket_design"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
SOURCE_9051 = ROOT / "runs/summaries/stage9051_long_context_candidate_miner_guard_audit.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "LONG_CONTEXT_SOURCE_OUTPUT_TICKET_DESIGN_STAGE9052.md"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
TICKET = OUT_DIR / "long_context_source_output_ticket_template_inactive.json"
AUDIT = OUT_DIR / "long_context_source_output_ticket_audit.json"

DENIED_OPERATIONS = [
    "scan_arxiv",
    "scan_repository_library",
    "read_repository_bodies",
    "read_dataset_rows",
    "build_corpus_index",
    "read_long_context_index",
    "run_candidate_mining",
    "write_candidates_under_arxiv",
    "write_parquet_under_arxiv",
    "upload_hf",
    "compile_training_manifest",
    "run_model",
    "train_model",
]
REQUIRED_TICKET_FIELDS = [
    "ticket_id",
    "ticket_status",
    "ticket_granted_now",
    "command_materialized",
    "allowed_operations_now",
    "denied_operations",
    "required_source_roots",
    "required_output_paths",
    "required_caps",
    "required_preflight_artifacts",
    "required_postrun_artifacts",
    "authority",
]
REQUIRED_CAPS = {
    "profile": "paper_repo_core",
    "max_files_per_root": 0,
    "max_candidates": 0,
    "max_chars_per_file": 0,
    "rows_per_shard": 0,
    "allow_corpus_scan": False,
    "allow_candidate_mining": False,
    "allow_arxiv_output": False,
    "hf_upload": False,
}
REQUIRED_PREFLIGHT_ARTIFACTS = [
    "source_root_allowlist.json",
    "output_path_allowlist.json",
    "source_license_security_card.json",
    "expected_profile_card.json",
    "no_locked_eval_overlap_card.json",
    "no_destructive_cleanup_card.json",
]
REQUIRED_POSTRUN_ARTIFACTS = [
    "index_summary.json",
    "candidate_summary.json",
    "source_lineage_card.json",
    "route_card.json",
    "shortcut_baseline_audit.json",
    "junk_ranker_card.json",
]


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def build_inactive_ticket() -> dict[str, Any]:
    ticket = {
        "ticket_id": "future_long_context_source_output_ticket__inactive_stage9052",
        "ticket_status": "TEMPLATE_ONLY_INACTIVE",
        "ticket_granted_now": False,
        "requires_explicit_user_authorization": True,
        "requires_fresh_pre_execution_audit": True,
        "command_materialized": False,
        "allowed_operations_now": [],
        "denied_operations": list(DENIED_OPERATIONS),
        "required_source_roots": {
            "papers_root": "explicit_path_required_later",
            "repos_root": "explicit_path_required_later",
            "datasets_root": "optional_explicit_path_required_later",
        },
        "required_output_paths": {
            "index_dir": "explicit_path_required_later",
            "candidate_output": "explicit_path_required_later",
            "summary_output": "explicit_path_required_later",
        },
        "required_caps": dict(REQUIRED_CAPS),
        "required_preflight_artifacts": list(REQUIRED_PREFLIGHT_ARTIFACTS),
        "required_postrun_artifacts": list(REQUIRED_POSTRUN_ARTIFACTS),
        "authority": dict(AUTHORITY_CLOSED),
    }
    return apply_diagnostic_gate_fields(ticket)


def audit_ticket(ticket: dict[str, Any], registry: dict[str, Any]) -> dict[str, Any]:
    failures = audit_diagnostic_ticket_fields(ticket)
    for field in REQUIRED_TICKET_FIELDS:
        if field not in ticket:
            failures.append(f"missing:{field}")
    if ticket.get("ticket_status") != "TEMPLATE_ONLY_INACTIVE":
        failures.append("ticket_not_template_only_inactive")
    if ticket.get("ticket_granted_now") is not False:
        failures.append("ticket_granted_now_not_false")
    if ticket.get("command_materialized") is not False:
        failures.append("command_materialized_not_false")
    if ticket.get("allowed_operations_now") != []:
        failures.append("allowed_operations_now_not_empty")
    denied = set(ticket.get("denied_operations") or [])
    missing_denials = sorted(set(DENIED_OPERATIONS) - denied)
    failures.extend([f"missing_denial:{item}" for item in missing_denials])
    caps = ticket.get("required_caps") or {}
    for key, expected in REQUIRED_CAPS.items():
        if caps.get(key) != expected:
            failures.append(f"cap_mismatch:{key}")
    metrics = registry.get("metrics") or {}
    if any(int((metrics.get("authority_counts") or {}).get(key, 0)) != 0 for key in AUTHORITY_CLOSED):
        failures.append("registry_authority_counts_nonzero")
    source_9051 = load_json(SOURCE_9051)
    if source_9051.get("passed") is not True:
        failures.append("source_stage9051_not_passed")
    return {
        "passed": not failures,
        "failures": failures,
        "ticket_contract_failures": audit_diagnostic_ticket_fields(ticket),
        "denied_operations": len(denied),
        "required_preflight_artifacts": len(ticket.get("required_preflight_artifacts") or []),
        "required_postrun_artifacts": len(ticket.get("required_postrun_artifacts") or []),
    }


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    registry = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    ticket = build_inactive_ticket()
    audit = audit_ticket(ticket, registry)
    TICKET.write_text(json.dumps(ticket, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    AUDIT.write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "passed": audit["passed"],
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {
            **dict(AUTHORITY_CLOSED),
            "authority_rows": 0,
            "failures": audit["failures"],
            "ticket_contract_failures": len(audit["ticket_contract_failures"]),
            "denied_operations": audit["denied_operations"],
            "required_preflight_artifacts": audit["required_preflight_artifacts"],
            "required_postrun_artifacts": audit["required_postrun_artifacts"],
            "ticket_granted_now": False,
            "command_materialized": False,
            "corpus_scan_authorized_now": False,
            "candidate_mining_authorized_now": False,
            "arxiv_write_authorized": False,
            "hf_upload_authorized_now": False,
            "training_authorized": False,
            "model_execution_attempted": False,
        },
        "artifacts": {"ticket": str(TICKET.relative_to(ROOT)), "audit": str(AUDIT.relative_to(ROOT))},
        "decision": "Inactive long-context source/output ticket schema is defined but not granted. Real corpus indexing/candidate mining remains closed.",
        "next_best_step": "Audit this inactive ticket schema, then continue no-data pipeline recovery unless the user explicitly authorizes a tiny source/output ticket instance later.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage9052 Long Context Source/Output Ticket Design",
        "",
        f"Passed: `{summary['passed']}`",
        "",
        "This stage designs an inactive future ticket only. It grants no source reads, index reads, candidate mining, `/arxiv` writes, Hugging Face upload, model execution, or training.",
        "",
        "Required preflight artifacts:",
        "",
        *[f"- `{item}`" for item in REQUIRED_PREFLIGHT_ARTIFACTS],
        "",
        "Required postrun artifacts for any future granted ticket:",
        "",
        *[f"- `{item}`" for item in REQUIRED_POSTRUN_ARTIFACTS],
        "",
        f"Next: {summary['next_best_step']}",
        "",
    ]) + "\n", encoding="utf-8")
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
    print(json.dumps(summary, indent=2, sort_keys=True))
    raise SystemExit(0 if summary["passed"] else 1)


if __name__ == "__main__":
    main()
