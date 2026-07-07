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
STAGE = 9115
NAME = "stage9115_metadata_only_inventory_runner_contract_design"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
SOURCE_9114 = ROOT / "runs/summaries/stage9114_metadata_only_real_data_inventory_ticket_audit.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "METADATA_ONLY_INVENTORY_RUNNER_CONTRACT_STAGE9115.md"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
CONTRACT = OUT_DIR / "metadata_only_inventory_runner_contract.json"

REQUIRED_CLI_FLAGS = [
    "--datasets-root",
    "--repositories-root",
    "--output-dir",
    "--max-depth",
    "--metadata-only",
    "--no-row-reads",
    "--no-source-body-reads",
    "--no-arxiv-writes",
    "--no-follow-symlinks",
    "--require-ticket-audit",
]

REQUIRED_RUNTIME_ASSERTIONS = [
    "datasets_root_is_arxiv_datasets",
    "repositories_root_is_arxiv_repositories",
    "output_dir_under_runs_local_artifacts",
    "metadata_only_flag_required",
    "row_reads_disabled",
    "source_body_reads_disabled",
    "parquet_group_reads_disabled",
    "arxiv_write_disabled",
    "symlink_follow_disabled",
    "max_depth_enforced",
    "ticket_audit_summary_passed",
]

ALLOWED_METADATA_FIELDS = [
    "path",
    "entry_name",
    "entry_kind",
    "extension",
    "size_bytes",
    "mtime_epoch",
    "depth",
    "parent",
]

FORBIDDEN_RUNTIME_ACTIONS = [
    "open_dataset_row_file_for_content",
    "open_parquet_file_for_row_groups",
    "open_source_file_for_body",
    "hash_file_contents",
    "sample_dataset_rows",
    "parse_repository_source",
    "write_under_arxiv",
    "delete_any_path",
    "invoke_mining",
    "invoke_trainer",
    "model_forward",
    "network_upload",
    "cleanup_execution",
]


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def build_contract(registry: dict[str, Any]) -> dict[str, Any]:
    source = load_json(SOURCE_9114)
    checks = {
        "source_stage9114_passed": source.get("passed") is True,
        "source_stage9114_rejected_negative_cases": (source.get("metrics") or {}).get("negative_cases_rejected") == (source.get("metrics") or {}).get("negative_cases"),
        "required_cli_flags_recorded": len(REQUIRED_CLI_FLAGS) >= 10,
        "runtime_assertions_recorded": len(REQUIRED_RUNTIME_ASSERTIONS) >= 11,
        "allowed_metadata_fields_recorded": len(ALLOWED_METADATA_FIELDS) >= 8,
        "forbidden_runtime_actions_recorded": len(FORBIDDEN_RUNTIME_ACTIONS) >= 13,
        "registry_frontier_stage9114": int((registry.get("metrics") or {}).get("latest_stage", -1)) == 9114,
        "authority_counts_zero": not any(((registry.get("metrics") or {}).get("authority_counts") or {}).get(key, 0) for key in AUTHORITY_CLOSED),
    }
    return {
        "stage": STAGE,
        "stage_name": NAME,
        "status": "METADATA_ONLY_INVENTORY_RUNNER_CONTRACT_DESIGN_NO_RUNNER_EXECUTION",
        "required_cli_flags": list(REQUIRED_CLI_FLAGS),
        "required_runtime_assertions": list(REQUIRED_RUNTIME_ASSERTIONS),
        "allowed_metadata_fields": list(ALLOWED_METADATA_FIELDS),
        "forbidden_runtime_actions": list(FORBIDDEN_RUNTIME_ACTIONS),
        "checks": checks,
        "metrics": {
            "required_cli_flags": len(REQUIRED_CLI_FLAGS),
            "required_runtime_assertions": len(REQUIRED_RUNTIME_ASSERTIONS),
            "allowed_metadata_fields": len(ALLOWED_METADATA_FIELDS),
            "forbidden_runtime_actions": len(FORBIDDEN_RUNTIME_ACTIONS),
            "runner_executed_now": False,
            "arxiv_access_performed": False,
            "arxiv_stat_performed": False,
            "dataset_file_names_read_now": False,
            "repository_root_names_read_now": False,
            "dataset_rows_loaded": False,
            "dataset_parquet_groups_read": False,
            "repository_source_bodies_loaded": False,
            "arxiv_write_authorized": False,
            "data_mining_authorized": False,
            "trainer_executed_now": False,
            "model_forward_attempted": False,
            "training_authorized": False,
            "network_upload_performed": False,
            "cleanup_authorized_now": False,
        },
        "authority": dict(AUTHORITY_CLOSED),
        "decision": "Designed the metadata-only inventory runner contract. This stage does not execute the runner, access/stat /arxiv, read names, read rows, read parquet groups, read source bodies, write to /arxiv, mine data, invoke trainer/model paths, upload, cleanup, or train.",
    }


def validate_contract(contract: dict[str, Any], registry: dict[str, Any]) -> list[str]:
    failures = [key for key, value in contract["checks"].items() if value is not True]
    if any((contract.get("authority") or {}).values()):
        failures.append("authority_open")
    latest = int((registry.get("metrics") or {}).get("latest_stage", -1))
    if latest not in {9114, STAGE}:
        failures.append(f"unexpected_registry_frontier:{latest}")
    for flag in REQUIRED_CLI_FLAGS:
        if flag not in contract.get("required_cli_flags", []):
            failures.append(f"missing_required_cli_flag:{flag}")
    for assertion in REQUIRED_RUNTIME_ASSERTIONS:
        if assertion not in contract.get("required_runtime_assertions", []):
            failures.append(f"missing_runtime_assertion:{assertion}")
    for action in FORBIDDEN_RUNTIME_ACTIONS:
        if action not in contract.get("forbidden_runtime_actions", []):
            failures.append(f"missing_forbidden_runtime_action:{action}")
    for key in [
        "runner_executed_now",
        "arxiv_access_performed",
        "arxiv_stat_performed",
        "dataset_file_names_read_now",
        "repository_root_names_read_now",
        "dataset_rows_loaded",
        "dataset_parquet_groups_read",
        "repository_source_bodies_loaded",
        "arxiv_write_authorized",
        "data_mining_authorized",
        "trainer_executed_now",
        "model_forward_attempted",
        "training_authorized",
        "network_upload_performed",
        "cleanup_authorized_now",
    ]:
        if contract["metrics"].get(key) is not False:
            failures.append(key)
    return failures


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    registry = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    contract = build_contract(registry)
    failures = validate_contract(contract, registry)
    CONTRACT.write_text(json.dumps(contract, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "passed": not failures,
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {**dict(AUTHORITY_CLOSED), "failures": failures, **contract["metrics"]},
        "artifacts": {"contract": str(CONTRACT.relative_to(ROOT)), "doc": str(DOC.relative_to(ROOT))},
        "decision": contract["decision"] if not failures else "Metadata-only inventory runner contract design failed.",
        "next_best_step": "Audit the metadata-only inventory runner contract with negative cases before implementing or executing it.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage9115 Metadata-Only Inventory Runner Contract",
        "",
        f"Passed: `{summary['passed']}`",
        "",
        "Designs the future runner contract. This stage does not execute the runner or access `/arxiv`.",
        "",
        "Required CLI flags:",
        "",
        *[f"- `{flag}`" for flag in REQUIRED_CLI_FLAGS],
        "",
        "Required runtime assertions:",
        "",
        *[f"- `{item}`" for item in REQUIRED_RUNTIME_ASSERTIONS],
        "",
        f"Next: {summary['next_best_step']}",
    ]) + "\n", encoding="utf-8")
    rows = [row for row in registry.get("rows", []) if row.get("stage_name") != NAME]
    rows.append({"stage": STAGE, "stage_name": NAME, "passed": summary["passed"], "path": str(SUMMARY), "authority": dict(AUTHORITY_CLOSED), "next_best_step": summary["next_best_step"]})
    rows = sorted(rows, key=lambda row: (int(row.get("stage", -1)), row.get("stage_name", "")))
    registry["rows"] = rows
    registry["passed"] = summary["passed"]
    registry["metrics"] = {**(registry.get("metrics") or {}), "latest_stage": STAGE, "latest_stage_name": NAME, "latest_stage_next_best_step": summary["next_best_step"], "max_stage": max(STAGE, int((registry.get("metrics") or {}).get("max_stage", 0))), "registry_rows": len(rows), "authority_counts": {key: 0 for key in AUTHORITY_CLOSED}}
    REGISTRY.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))
    raise SystemExit(0 if summary["passed"] else 1)


if __name__ == "__main__":
    main()
