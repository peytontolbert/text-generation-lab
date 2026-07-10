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
NAME = "stage9156_metadata_inventory_final_authorization_blocker_contract"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "METADATA_INVENTORY_FINAL_AUTHORIZATION_BLOCKER_CONTRACT_STAGE9156.md"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
CONTRACT = OUT_DIR / "metadata_inventory_final_authorization_blocker_contract.json"

REQUIRED_PREAUTH_EVIDENCE = [
    "stage9150_metadata_only_inventory_runner_dry_run_audit_passed",
    "stage9154_repo_local_inventory_single_run_ticket_instance_design_passed",
    "stage9155_repo_local_inventory_single_run_ticket_instance_design_audit_passed",
    "single_run_ticket_instance_has_unique_ticket_id",
    "ticket_allowed_roots_are_repo_local_only",
    "ticket_forbidden_roots_include_arxiv_data_home_tmp_and_root",
    "ticket_output_dir_under_runs_local_artifacts",
    "ticket_lists_paths_only",
    "ticket_forbids_file_content_reads",
    "ticket_forbids_json_parse_and_jsonl_row_count",
    "ticket_forbids_dataset_row_load",
    "ticket_forbids_route_card_and_loss_mask_materialization",
    "ticket_forbids_compiler_handoff_and_trainer_execution",
    "registry_has_no_open_authority_counts",
    "working_tree_collision_review_complete",
]

AUTHORIZATION_BOUNDARIES = [
    "may_only_authorize_one_metadata_inventory_run_after_separate_human_approval",
    "must_not_authorize_route_card_materialization",
    "must_not_authorize_loss_mask_materialization",
    "must_not_authorize_compiler_handoff",
    "must_not_authorize_trainer_dry_run",
    "must_not_authorize_model_forward",
    "must_not_authorize_decoder_or_denoise_ce",
    "must_not_authorize_runtime_or_harness",
    "must_not_read_file_contents",
    "must_not_access_arxiv_or_external_roots",
]

NEGATIVE_CASES = [
    "missing_preauth_evidence",
    "missing_authorization_boundary",
    "execution_authorized_now",
    "route_card_materialization_authorized",
    "loss_mask_materialization_authorized",
    "compiler_handoff_authorized",
    "trainer_authorized",
    "model_forward_authorized",
    "decoder_ce_authorized",
    "denoise_ce_authorized",
    "file_content_read_allowed",
    "arxiv_access_allowed",
    "authority_open",
]


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def build_contract() -> dict[str, Any]:
    return {
        "stage": STAGE,
        "stage_name": NAME,
        "contract_type": "metadata_inventory_final_authorization_blocker_v1",
        "purpose": (
            "Capture the remaining blocker conditions before a future one-run "
            "metadata-only repo-local inventory can be explicitly authorized. This "
            "stage does not authorize that run."
        ),
        "required_preauth_evidence": list(REQUIRED_PREAUTH_EVIDENCE),
        "authorization_boundaries": list(AUTHORIZATION_BOUNDARIES),
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {
            "contract_only": True,
            "metadata_inventory_execution_authorized_now": False,
            "metadata_inventory_execution_authorized_next": False,
            "single_run_ticket_instantiated_now": False,
            "inventory_runner_executed_now": False,
            "metadata_path_inventory_loaded_now": False,
            "path_inventory_rows_loaded": 0,
            "candidate_rows_loaded": 0,
            "file_content_read": False,
            "json_parsed": False,
            "jsonl_rows_counted": False,
            "dataset_rows_loaded": False,
            "arxiv_accessed": False,
            "external_root_accessed": False,
            "route_cards_materialized_now": False,
            "loss_mask_cards_materialized_now": False,
            "compiler_handoff_ready_now": False,
            "trainer_dry_run_passed_now": False,
            "trainer_executed_now": False,
            "model_forward_attempted": False,
            "training_authorized": False,
            "decoder_ce_authorized": False,
            "denoise_ce_authorized": False,
            "runtime_authorized_flag": False,
            "harness_authorized_flag": False,
            "network_upload_performed": False,
            "cleanup_authorized_now": False,
        },
        "decision": (
            "Final metadata-inventory authorization remains blocked until the listed "
            "preauthorization evidence exists and a separate explicit approval opens "
            "exactly one metadata-only path-listing run. All downstream route-card, "
            "loss-mask, compiler, trainer, decoder, denoise, runtime, and harness "
            "paths remain closed."
        ),
    }


def validate_contract(contract: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    for item in REQUIRED_PREAUTH_EVIDENCE:
        if item not in contract.get("required_preauth_evidence", []):
            failures.append(f"missing_preauth_evidence:{item}")
    for item in AUTHORIZATION_BOUNDARIES:
        if item not in contract.get("authorization_boundaries", []):
            failures.append(f"missing_authorization_boundary:{item}")
    metrics = contract.get("metrics") or {}
    if metrics.get("contract_only") is not True:
        failures.append("contract_not_marked_contract_only")
    false_keys = [
        "metadata_inventory_execution_authorized_now",
        "metadata_inventory_execution_authorized_next",
        "single_run_ticket_instantiated_now",
        "inventory_runner_executed_now",
        "metadata_path_inventory_loaded_now",
        "file_content_read",
        "json_parsed",
        "jsonl_rows_counted",
        "dataset_rows_loaded",
        "arxiv_accessed",
        "external_root_accessed",
        "route_cards_materialized_now",
        "loss_mask_cards_materialized_now",
        "compiler_handoff_ready_now",
        "trainer_dry_run_passed_now",
        "trainer_executed_now",
        "model_forward_attempted",
        "training_authorized",
        "decoder_ce_authorized",
        "denoise_ce_authorized",
        "runtime_authorized_flag",
        "harness_authorized_flag",
        "network_upload_performed",
        "cleanup_authorized_now",
    ]
    for key in false_keys:
        if metrics.get(key) is not False:
            failures.append(key)
    for key in ["path_inventory_rows_loaded", "candidate_rows_loaded"]:
        if metrics.get(key) != 0:
            failures.append(key)
    if any((contract.get("authority") or {}).values()):
        failures.append("authority_open")
    return failures


def run_negative_cases() -> dict[str, Any]:
    base = build_contract()
    cases: dict[str, dict[str, Any]] = {}
    for name in NEGATIVE_CASES:
        candidate = copy.deepcopy(base)
        if name == "missing_preauth_evidence":
            candidate["required_preauth_evidence"].remove("stage9155_repo_local_inventory_single_run_ticket_instance_design_audit_passed")
        elif name == "missing_authorization_boundary":
            candidate["authorization_boundaries"].remove("must_not_authorize_route_card_materialization")
        elif name == "execution_authorized_now":
            candidate["metrics"]["metadata_inventory_execution_authorized_now"] = True
        elif name == "route_card_materialization_authorized":
            candidate["metrics"]["route_cards_materialized_now"] = True
        elif name == "loss_mask_materialization_authorized":
            candidate["metrics"]["loss_mask_cards_materialized_now"] = True
        elif name == "compiler_handoff_authorized":
            candidate["metrics"]["compiler_handoff_ready_now"] = True
        elif name == "trainer_authorized":
            candidate["metrics"]["trainer_executed_now"] = True
        elif name == "model_forward_authorized":
            candidate["metrics"]["model_forward_attempted"] = True
        elif name == "decoder_ce_authorized":
            candidate["metrics"]["decoder_ce_authorized"] = True
        elif name == "denoise_ce_authorized":
            candidate["metrics"]["denoise_ce_authorized"] = True
        elif name == "file_content_read_allowed":
            candidate["metrics"]["file_content_read"] = True
        elif name == "arxiv_access_allowed":
            candidate["metrics"]["arxiv_accessed"] = True
        elif name == "authority_open":
            candidate["authority"]["model_execution_authorized_next"] = True
        cases[name] = candidate
    return {
        name: {"failures": validate_contract(candidate), "rejected": bool(validate_contract(candidate))}
        for name, candidate in cases.items()
    }


def build_summary() -> dict[str, Any]:
    contract = build_contract()
    failures = validate_contract(contract)
    negatives = run_negative_cases()
    checks = {
        "contract_passes": failures == [],
        "negative_cases_rejected": all(item["rejected"] for item in negatives.values()),
        "preauth_evidence_complete": set(REQUIRED_PREAUTH_EVIDENCE).issubset(set(contract["required_preauth_evidence"])),
        "authorization_boundaries_complete": set(AUTHORIZATION_BOUNDARIES).issubset(set(contract["authorization_boundaries"])),
        "authority_closed": not any(contract["authority"].values()),
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
        "contract": contract,
        "negative_cases": negatives,
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {
            **contract["metrics"],
            "required_preauth_evidence": len(REQUIRED_PREAUTH_EVIDENCE),
            "authorization_boundaries": len(AUTHORIZATION_BOUNDARIES),
            "negative_cases": len(negatives),
            "negative_cases_rejected": sum(1 for item in negatives.values() if item["rejected"]),
        },
        "decision": contract["decision"] if passed else "Metadata-inventory final authorization blocker contract failed validation.",
        "next_best_step": (
            "Finish and audit the Stage9155 ticket-instance design audit, reconcile the "
            "registry, then request a separate explicit approval before any one-run "
            "metadata inventory execution."
        ),
    }


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    summary = build_summary()
    CONTRACT.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    public_summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "passed": summary["passed"],
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {**dict(AUTHORITY_CLOSED), **summary["metrics"], "failures": summary["failures"]},
        "artifacts": {"contract": str(CONTRACT.relative_to(ROOT)), "doc": str(DOC.relative_to(ROOT))},
        "decision": summary["decision"],
        "next_best_step": summary["next_best_step"],
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(public_summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage9156 Metadata Inventory Final Authorization Blocker Contract",
        "",
        f"Passed: `{public_summary['passed']}`",
        "",
        "This is a no-execution blocker contract. It does not authorize metadata inventory execution.",
        "",
        f"Required preauthorization evidence: `{summary['metrics']['required_preauth_evidence']}`",
        f"Authorization boundaries: `{summary['metrics']['authorization_boundaries']}`",
        f"Negative cases rejected: `{summary['metrics']['negative_cases_rejected']}/{summary['metrics']['negative_cases']}`",
        "",
        f"Next: {public_summary['next_best_step']}",
    ]) + "\n", encoding="utf-8")

    registry_json = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    rows = [row for row in registry_json.get("rows", []) if row.get("stage_name") != NAME and row.get("stage") != STAGE]
    rows.append({
        "stage": STAGE,
        "stage_name": NAME,
        "passed": public_summary["passed"],
        "path": str(SUMMARY),
        "authority": dict(AUTHORITY_CLOSED),
        "next_best_step": public_summary["next_best_step"],
    })
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
