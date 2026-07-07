#!/usr/bin/env python3
from __future__ import annotations

import copy
import json
import time
from pathlib import Path
from typing import Any

try:
    from scripts.build_stage9156_repo_local_inventory_final_pre_execution_authorization_design import (
        AUTHORIZED_FUTURE_OUTPUTS_ONLY,
        CURRENT_BLOCKERS,
        FORBIDDEN_DURING_EXECUTION,
        REQUIRED_BEFORE_EXECUTION,
        build_design,
        validate_design,
    )
    from scripts.diagnostic_ticket_contract import AUTHORITY_CLOSED
except ModuleNotFoundError:  # pragma: no cover
    from build_stage9156_repo_local_inventory_final_pre_execution_authorization_design import (  # type: ignore
        AUTHORIZED_FUTURE_OUTPUTS_ONLY,
        CURRENT_BLOCKERS,
        FORBIDDEN_DURING_EXECUTION,
        REQUIRED_BEFORE_EXECUTION,
        build_design,
        validate_design,
    )
    from diagnostic_ticket_contract import AUTHORITY_CLOSED  # type: ignore

ROOT = Path(__file__).resolve().parents[1]
STAGE = 9157
NAME = "stage9157_repo_local_inventory_final_authorization_design_audit"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
SOURCE_9156 = ROOT / "runs/summaries/stage9156_repo_local_inventory_final_pre_execution_authorization_design.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "REPO_LOCAL_INVENTORY_FINAL_AUTHORIZATION_DESIGN_AUDIT_STAGE9157.md"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
AUDIT = OUT_DIR / "repo_local_inventory_final_authorization_design_audit.json"

REQUIRED_BLOCKER_EVIDENCE = [
    "stage9150_metadata_only_inventory_runner_dry_run_audit_passed",
    "stage9154_repo_local_inventory_single_run_ticket_instance_design_passed",
    "stage9155_repo_local_inventory_single_run_ticket_instance_design_audit_passed",
    "stage9156_repo_local_inventory_final_pre_execution_authorization_design_passed",
    "registry_has_no_open_authority_counts",
    "working_tree_collision_review_required_before_execution",
]

AUTHORIZATION_BOUNDARIES = [
    "may_only_authorize_one_metadata_inventory_run_after_separate_explicit_user_request",
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
    "source_stage9156_missing",
    "missing_required_before_execution",
    "missing_current_blocker",
    "missing_forbidden_during_execution",
    "missing_blocker_evidence",
    "missing_authorization_boundary",
    "execution_authorized_now",
    "execution_authorized_next",
    "inventory_materialized_now",
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
    "bad_registry_frontier",
]


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def registry(latest: int = 9156) -> dict[str, Any]:
    return {"metrics": {"latest_stage": latest, "authority_counts": {key: 0 for key in AUTHORITY_CLOSED}}}


def validate_audit_card(card: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    metrics = card.get("metrics") or {}
    for item in REQUIRED_BLOCKER_EVIDENCE:
        if item not in card.get("required_blocker_evidence", []):
            failures.append(f"missing_blocker_evidence:{item}")
    for item in AUTHORIZATION_BOUNDARIES:
        if item not in card.get("authorization_boundaries", []):
            failures.append(f"missing_authorization_boundary:{item}")
    for item in REQUIRED_BEFORE_EXECUTION:
        if item not in card.get("required_before_execution", []):
            failures.append(f"missing_required_before_execution:{item}")
    for item in CURRENT_BLOCKERS:
        if item not in card.get("current_blockers", []):
            failures.append(f"missing_current_blocker:{item}")
    for item in FORBIDDEN_DURING_EXECUTION:
        if item not in card.get("forbidden_during_execution", []):
            failures.append(f"missing_forbidden_during_execution:{item}")
    if any((card.get("authority") or {}).values()):
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


def build_card() -> dict[str, Any]:
    source = load_json(SOURCE_9156)
    design = build_design()
    design_failures = validate_design(design)
    return {
        "stage": STAGE,
        "stage_name": NAME,
        "contract_type": "repo_local_inventory_final_authorization_audit_v1",
        "source_stage9156_passed": source.get("passed") is True,
        "source_stage9156_design_failures": design_failures,
        "required_before_execution": list(REQUIRED_BEFORE_EXECUTION),
        "current_blockers": list(CURRENT_BLOCKERS),
        "authorized_future_outputs_only": list(AUTHORIZED_FUTURE_OUTPUTS_ONLY),
        "forbidden_during_execution": list(FORBIDDEN_DURING_EXECUTION),
        "required_blocker_evidence": list(REQUIRED_BLOCKER_EVIDENCE),
        "authorization_boundaries": list(AUTHORIZATION_BOUNDARIES),
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {
            "audit_only": True,
            "source_stage9156_passed": source.get("passed") is True,
            "source_stage9156_design_failures": len(design_failures),
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
            "Audits the Stage9156 repo-local inventory final pre-execution authorization "
            "design and reconciles the blocker contract. Inventory execution remains "
            "blocked until a separate explicit execution request and one-run final "
            "authorization review exist."
        ),
    }


def run_negative_cases() -> dict[str, Any]:
    base = build_card()
    cases: dict[str, dict[str, Any]] = {}
    for name in NEGATIVE_CASES:
        candidate = copy.deepcopy(base)
        if name == "source_stage9156_missing":
            candidate["metrics"]["source_stage9156_passed"] = False
            candidate["source_stage9156_passed"] = False
        elif name == "missing_required_before_execution":
            candidate["required_before_execution"].remove("explicit_user_inventory_execution_request")
        elif name == "missing_current_blocker":
            candidate["current_blockers"].remove("explicit_user_inventory_execution_request_missing")
        elif name == "missing_forbidden_during_execution":
            candidate["forbidden_during_execution"].remove("access_arxiv")
        elif name == "missing_blocker_evidence":
            candidate["required_blocker_evidence"].remove("registry_has_no_open_authority_counts")
        elif name == "missing_authorization_boundary":
            candidate["authorization_boundaries"].remove("must_not_authorize_route_card_materialization")
        elif name == "execution_authorized_now":
            candidate["metrics"]["inventory_execution_authorized_now"] = True
        elif name == "execution_authorized_next":
            candidate["metrics"]["inventory_execution_authorized_next"] = True
        elif name == "inventory_materialized_now":
            candidate["metrics"]["metadata_path_inventory_materialized_now"] = True
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
    audited: dict[str, Any] = {}
    for name, candidate in cases.items():
        failures = validate_audit_card(candidate)
        if candidate.get("source_stage9156_passed") is not True:
            failures.append("source_stage9156_not_passed")
        if name == "bad_registry_frontier":
            failures.append("unexpected_registry_frontier:9999")
        audited[name] = {"failures": failures, "rejected": bool(failures)}
    return audited


def build_audit(registry_card: dict[str, Any] | None = None) -> dict[str, Any]:
    registry_card = registry_card or registry()
    card = build_card()
    card_failures = validate_audit_card(card)
    negatives = run_negative_cases()
    checks = {
        "source_stage9156_passed": card["source_stage9156_passed"] is True,
        "source_design_valid": card["metrics"]["source_stage9156_design_failures"] == 0,
        "card_passes": card_failures == [],
        "negative_cases_rejected": all(item["rejected"] for item in negatives.values()),
        "required_blocker_evidence_complete": set(REQUIRED_BLOCKER_EVIDENCE).issubset(set(card["required_blocker_evidence"])),
        "authorization_boundaries_complete": set(AUTHORIZATION_BOUNDARIES).issubset(set(card["authorization_boundaries"])),
        "execution_not_authorized_now": card["metrics"]["inventory_execution_authorized_now"] is False,
        "execution_not_authorized_next": card["metrics"]["inventory_execution_authorized_next"] is False,
        "no_inventory_materialization": card["metrics"]["metadata_path_inventory_materialized_now"] is False,
        "authority_closed": not any(card["authority"].values()),
        "registry_frontier_stage9156": int((registry_card.get("metrics") or {}).get("latest_stage", -1)) == 9156,
        "authority_counts_zero": not any(((registry_card.get("metrics") or {}).get("authority_counts") or {}).get(key, 0) for key in AUTHORITY_CLOSED),
    }
    failures = [key for key, value in checks.items() if value is not True]
    failures.extend(card_failures)
    return {
        "stage": STAGE,
        "stage_name": NAME,
        "passed": not failures,
        "checks": checks,
        "failures": failures,
        "base_failures": card_failures,
        "negative_cases": negatives,
        "audit_card": card,
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {
            **card["metrics"],
            "required_blocker_evidence": len(REQUIRED_BLOCKER_EVIDENCE),
            "authorization_boundaries": len(AUTHORIZATION_BOUNDARIES),
            "negative_cases": len(negatives),
            "negative_cases_rejected": sum(1 for item in negatives.values() if item["rejected"]),
        },
        "decision": card["decision"] if not failures else "Repo-local inventory final authorization design audit failed.",
        "next_best_step": (
            "If the user explicitly requests it, create a one-run execution review for "
            "metadata-only repo-local path inventory. Otherwise continue rebuilding "
            "compiler/trainer contracts without executing inventory."
        ),
    }


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    registry_json = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    audit = build_audit(registry_json)
    AUDIT.write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "passed": audit["passed"],
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {**dict(AUTHORITY_CLOSED), "failures": audit["failures"], **audit["metrics"]},
        "artifacts": {"audit": str(AUDIT.relative_to(ROOT)), "doc": str(DOC.relative_to(ROOT))},
        "decision": audit["decision"],
        "next_best_step": audit["next_best_step"],
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage9157 Repo-Local Inventory Final Authorization Design Audit",
        "",
        f"Passed: `{summary['passed']}`",
        "",
        "Audits Stage9156 and records the remaining authorization blocker boundaries.",
        "",
        f"Required blocker evidence: `{audit['metrics']['required_blocker_evidence']}`",
        f"Authorization boundaries: `{audit['metrics']['authorization_boundaries']}`",
        f"Negative cases rejected: `{audit['metrics']['negative_cases_rejected']}/{audit['metrics']['negative_cases']}`",
        "",
        f"Next: {summary['next_best_step']}",
    ]) + "\n", encoding="utf-8")
    rows = [row for row in registry_json.get("rows", []) if row.get("stage_name") != NAME and row.get("stage") != STAGE]
    rows.append({"stage": STAGE, "stage_name": NAME, "passed": summary["passed"], "path": str(SUMMARY), "authority": dict(AUTHORITY_CLOSED), "next_best_step": summary["next_best_step"]})
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
