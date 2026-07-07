#!/usr/bin/env python3
from __future__ import annotations

import copy
import json
import time
from pathlib import Path
from typing import Any

try:
    from scripts.diagnostic_ticket_contract import AUTHORITY_CLOSED
except ModuleNotFoundError:  # pragma: no cover
    from diagnostic_ticket_contract import AUTHORITY_CLOSED  # type: ignore

ROOT = Path(__file__).resolve().parents[1]
STAGE = 9156
NAME = "stage9156_repo_local_inventory_final_pre_execution_authorization_design"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
SOURCE_9155 = ROOT / "runs/summaries/stage9155_repo_local_inventory_single_run_ticket_instance_design_audit.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "REPO_LOCAL_INVENTORY_FINAL_PRE_EXECUTION_AUTHORIZATION_DESIGN_STAGE9156.md"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
DESIGN = OUT_DIR / "repo_local_inventory_final_pre_execution_authorization_design.json"

REQUIRED_BEFORE_EXECUTION = [
    "stage9155_ticket_design_audit_passed",
    "explicit_user_inventory_execution_request",
    "single_run_ticket_instance_materialized",
    "ticket_output_dir_under_runs_local_artifacts",
    "allowed_roots_exact_runs_local_artifacts_and_runs_summaries",
    "forbidden_roots_include_arxiv_data_home_tmp_root",
    "list_paths_only_true",
    "no_file_content_reads_true",
    "no_json_parse_true",
    "no_jsonl_row_count_true",
    "no_dataset_row_load_true",
    "no_route_card_materialization_true",
    "no_loss_mask_materialization_true",
    "no_compiler_handoff_true",
    "no_trainer_execution_true",
    "final_negative_case_audit_passed",
]

CURRENT_BLOCKERS = [
    "explicit_user_inventory_execution_request_missing",
    "executable_ticket_instance_missing",
    "final_negative_case_audit_missing",
    "no_current_execution_window",
]

AUTHORIZED_FUTURE_OUTPUTS_ONLY = [
    "metadata_only_path_inventory.json",
    "metadata_only_path_inventory_summary.json",
    "inventory_scope_card.json",
    "inventory_execution_proof.json",
]

FORBIDDEN_DURING_EXECUTION = [
    "open_file_contents",
    "parse_json_payloads",
    "count_jsonl_rows",
    "load_dataset_rows",
    "access_arxiv",
    "follow_symlink_outside_allowed_roots",
    "materialize_route_cards",
    "materialize_loss_masks",
    "invoke_compiler",
    "invoke_trainer",
    "model_forward",
    "runtime_execution",
    "cleanup_execution",
]

NEGATIVE_CASES = [
    "source_stage_missing",
    "missing_required_before_execution",
    "missing_current_blocker",
    "missing_authorized_future_output",
    "missing_forbidden_during_execution",
    "execution_authorized_now",
    "execution_authorized_next",
    "file_content_read",
    "json_parsed",
    "jsonl_rows_counted",
    "dataset_rows_loaded",
    "arxiv_accessed",
    "route_cards_materialized",
    "loss_masks_materialized",
    "compiler_handoff_ready",
    "trainer_executed",
    "training_authorized",
    "runtime_authorized",
    "authority_open",
]


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def build_design(source_9155: dict[str, Any] | None = None) -> dict[str, Any]:
    source_9155 = source_9155 if source_9155 is not None else load_json(SOURCE_9155)
    return {
        "stage": STAGE,
        "stage_name": NAME,
        "contract_type": "repo_local_inventory_final_pre_execution_authorization_design_v1",
        "purpose": (
            "Define the final pre-execution authorization gate for a future single-run "
            "repo-local metadata-only path inventory. This stage does not authorize or "
            "execute the inventory."
        ),
        "required_before_execution": list(REQUIRED_BEFORE_EXECUTION),
        "current_blockers": list(CURRENT_BLOCKERS),
        "authorized_future_outputs_only": list(AUTHORIZED_FUTURE_OUTPUTS_ONLY),
        "forbidden_during_execution": list(FORBIDDEN_DURING_EXECUTION),
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {
            "design_only": True,
            "source_stage9155_passed": source_9155.get("passed") is True,
            "inventory_execution_authorized_now": False,
            "inventory_execution_authorized_next": False,
            "inventory_runner_executed_now": False,
            "metadata_path_inventory_loaded_now": False,
            "metadata_path_inventory_materialized_now": False,
            "path_inventory_rows_loaded": 0,
            "candidate_rows_loaded": 0,
            "file_content_read": False,
            "json_parsed": False,
            "jsonl_rows_counted": False,
            "dataset_rows_loaded": False,
            "arxiv_accessed": False,
            "route_cards_materialized_now": False,
            "loss_mask_cards_materialized_now": False,
            "compiler_handoff_ready_now": False,
            "trainer_executed_now": False,
            "model_forward_attempted": False,
            "training_authorized": False,
            "decoder_ce_authorized": False,
            "denoise_ce_authorized": False,
            "runtime_authorized_flag": False,
            "network_upload_performed": False,
            "cleanup_authorized_now": False,
        },
        "decision": (
            "Designed the final pre-execution authorization gate for future repo-local "
            "metadata-only inventory. The current stage does not authorize execution "
            "now or next and does not materialize inventory outputs."
        ),
    }


def validate_design(design: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    metrics = design.get("metrics") or {}
    if metrics.get("source_stage9155_passed") is not True:
        failures.append("source_stage9155_not_passed")
    for item in REQUIRED_BEFORE_EXECUTION:
        if item not in design.get("required_before_execution", []):
            failures.append(f"missing_required_before_execution:{item}")
    for item in CURRENT_BLOCKERS:
        if item not in design.get("current_blockers", []):
            failures.append(f"missing_current_blocker:{item}")
    for item in AUTHORIZED_FUTURE_OUTPUTS_ONLY:
        if item not in design.get("authorized_future_outputs_only", []):
            failures.append(f"missing_authorized_future_output:{item}")
    for item in FORBIDDEN_DURING_EXECUTION:
        if item not in design.get("forbidden_during_execution", []):
            failures.append(f"missing_forbidden_during_execution:{item}")
    if any((design.get("authority") or {}).values()):
        failures.append("authority_open")
    closed_false = [
        "inventory_execution_authorized_now",
        "inventory_execution_authorized_next",
        "inventory_runner_executed_now",
        "metadata_path_inventory_loaded_now",
        "metadata_path_inventory_materialized_now",
        "file_content_read",
        "json_parsed",
        "jsonl_rows_counted",
        "dataset_rows_loaded",
        "arxiv_accessed",
        "route_cards_materialized_now",
        "loss_mask_cards_materialized_now",
        "compiler_handoff_ready_now",
        "trainer_executed_now",
        "model_forward_attempted",
        "training_authorized",
        "decoder_ce_authorized",
        "denoise_ce_authorized",
        "runtime_authorized_flag",
        "network_upload_performed",
        "cleanup_authorized_now",
    ]
    for key in closed_false:
        if metrics.get(key) is not False:
            failures.append(key)
    for key in ["path_inventory_rows_loaded", "candidate_rows_loaded"]:
        if metrics.get(key) != 0:
            failures.append(key)
    return failures


def run_negative_cases() -> dict[str, Any]:
    base = build_design()
    cases: dict[str, dict[str, Any]] = {}
    for name in NEGATIVE_CASES:
        candidate = copy.deepcopy(base)
        if name == "source_stage_missing":
            candidate["metrics"]["source_stage9155_passed"] = False
        elif name == "missing_required_before_execution":
            candidate["required_before_execution"].remove("explicit_user_inventory_execution_request")
        elif name == "missing_current_blocker":
            candidate["current_blockers"].remove("explicit_user_inventory_execution_request_missing")
        elif name == "missing_authorized_future_output":
            candidate["authorized_future_outputs_only"].remove("metadata_only_path_inventory.json")
        elif name == "missing_forbidden_during_execution":
            candidate["forbidden_during_execution"].remove("access_arxiv")
        elif name == "execution_authorized_now":
            candidate["metrics"]["inventory_execution_authorized_now"] = True
        elif name == "execution_authorized_next":
            candidate["metrics"]["inventory_execution_authorized_next"] = True
        elif name == "file_content_read":
            candidate["metrics"]["file_content_read"] = True
        elif name == "json_parsed":
            candidate["metrics"]["json_parsed"] = True
        elif name == "jsonl_rows_counted":
            candidate["metrics"]["jsonl_rows_counted"] = True
        elif name == "dataset_rows_loaded":
            candidate["metrics"]["dataset_rows_loaded"] = True
        elif name == "arxiv_accessed":
            candidate["metrics"]["arxiv_accessed"] = True
        elif name == "route_cards_materialized":
            candidate["metrics"]["route_cards_materialized_now"] = True
        elif name == "loss_masks_materialized":
            candidate["metrics"]["loss_mask_cards_materialized_now"] = True
        elif name == "compiler_handoff_ready":
            candidate["metrics"]["compiler_handoff_ready_now"] = True
        elif name == "trainer_executed":
            candidate["metrics"]["trainer_executed_now"] = True
        elif name == "training_authorized":
            candidate["metrics"]["training_authorized"] = True
        elif name == "runtime_authorized":
            candidate["metrics"]["runtime_authorized_flag"] = True
        elif name == "authority_open":
            candidate["authority"]["model_execution_authorized_next"] = True
        cases[name] = candidate
    return {
        name: {"failures": validate_design(candidate), "rejected": bool(validate_design(candidate))}
        for name, candidate in cases.items()
    }


def build_summary() -> dict[str, Any]:
    design = build_design()
    failures = validate_design(design)
    negatives = run_negative_cases()
    checks = {
        "design_passes": failures == [],
        "negative_cases_rejected": all(item["rejected"] for item in negatives.values()),
        "execution_not_authorized_now": design["metrics"]["inventory_execution_authorized_now"] is False,
        "execution_not_authorized_next": design["metrics"]["inventory_execution_authorized_next"] is False,
        "arxiv_forbidden_during_execution": "access_arxiv" in design["forbidden_during_execution"],
        "authority_closed": not any(design["authority"].values()),
    }
    all_failures = [key for key, value in checks.items() if value is not True]
    all_failures.extend(failures)
    passed = not all_failures
    return {
        "stage": STAGE,
        "stage_name": NAME,
        "passed": passed,
        "checks": checks,
        "failures": all_failures,
        "design": design,
        "negative_cases": negatives,
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {
            **design["metrics"],
            "required_before_execution": len(REQUIRED_BEFORE_EXECUTION),
            "current_blockers": len(CURRENT_BLOCKERS),
            "authorized_future_outputs_only": len(AUTHORIZED_FUTURE_OUTPUTS_ONLY),
            "forbidden_during_execution": len(FORBIDDEN_DURING_EXECUTION),
            "negative_cases": len(negatives),
            "negative_cases_rejected": sum(1 for item in negatives.values() if item["rejected"]),
        },
        "decision": design["decision"] if passed else "Repo-local inventory final pre-execution authorization design failed validation.",
        "next_best_step": "Audit the Stage9156 authorization design; do not run inventory until a separate explicit execution request exists.",
    }


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    summary = build_summary()
    DESIGN.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    public_summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "passed": summary["passed"],
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {**dict(AUTHORITY_CLOSED), **summary["metrics"], "failures": summary["failures"]},
        "artifacts": {"design": str(DESIGN.relative_to(ROOT)), "doc": str(DOC.relative_to(ROOT))},
        "decision": summary["decision"],
        "next_best_step": summary["next_best_step"],
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(public_summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage9156 Repo-Local Inventory Final Pre-Execution Authorization Design",
        "",
        f"Passed: `{public_summary['passed']}`",
        "",
        "Defines the future final pre-execution authorization gate. It does not authorize or execute inventory.",
        "",
        f"Current blockers: `{summary['metrics']['current_blockers']}`",
        f"Forbidden during execution: `{summary['metrics']['forbidden_during_execution']}`",
        f"Negative cases rejected: `{summary['metrics']['negative_cases_rejected']}/{summary['metrics']['negative_cases']}`",
        "",
        f"Next: {public_summary['next_best_step']}",
    ]) + "\n", encoding="utf-8")
    registry_json = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    rows = [row for row in registry_json.get("rows", []) if row.get("stage_name") != NAME and row.get("stage") != STAGE]
    rows.append({"stage": STAGE, "stage_name": NAME, "passed": public_summary["passed"], "path": str(SUMMARY), "authority": dict(AUTHORITY_CLOSED), "next_best_step": public_summary["next_best_step"]})
    rows = sorted(rows, key=lambda row: (int(row.get("stage", -1)), row.get("stage_name", "")))
    registry_json["rows"] = rows
    registry_json["passed"] = public_summary["passed"]
    registry_json["metrics"] = {
        **(registry_json.get("metrics") or {}),
        "latest_stage": STAGE,
        "latest_stage_name": NAME,
        "latest_stage_next_best_step": public_summary["next_best_step"],
        "max_stage": max(STAGE, int((registry_json.get("metrics") or {}).get("max_stage", 0))),
        "registry_rows": len(rows),
        "authority_counts": {key: 0 for key in AUTHORITY_CLOSED},
    }
    REGISTRY.write_text(json.dumps(registry_json, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(public_summary, indent=2, sort_keys=True))
    raise SystemExit(0 if public_summary["passed"] else 1)


if __name__ == "__main__":
    main()
