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
STAGE = 9151
NAME = "stage9151_route_card_candidate_quality_gate_contract"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "ROUTE_CARD_CANDIDATE_QUALITY_GATE_CONTRACT_STAGE9151.md"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
CONTRACT = OUT_DIR / "route_card_candidate_quality_gate_contract.json"

FUTURE_INPUTS = [
    "audited_metadata_only_inventory_runner_dry_run",
    "metadata_only_repo_local_path_inventory_manifest",
    "real_route_card_input_ticket_instance",
    "route_card_schema_recovery_contract",
    "route_to_loss_translation_contract",
]

REQUIRED_CANDIDATE_FIELDS = [
    "candidate_id",
    "source_inventory_ref",
    "source_inventory_lineage",
    "source_provenance",
    "route_card_schema_version",
    "route_family",
    "task_family",
    "language_family",
    "operator_category",
    "evidence_refs",
    "gate_status",
    "loss_mask_policy",
    "authority",
]

QUALITY_GATE_RULES = [
    "metadata_only_source_refs",
    "repo_local_paths_only",
    "no_file_content_or_body_fields",
    "no_hidden_or_locked_eval_sources",
    "no_arxiv_reads_in_candidate_gate",
    "schema_version_pinned",
    "known_route_family_required",
    "evidence_refs_nonempty",
    "gate_status_all_recovered_support_modules_explicit",
    "loss_mask_policy_defaults_closed",
    "compiler_handoff_requires_separate_audit",
    "training_requires_separate_dry_run_ticket",
]

ACTIVE_BLOCKERS = [
    "stage9150_or_later_inventory_runner_audit_not_consumed_here",
    "no_metadata_path_inventory_manifest_loaded",
    "no_route_card_candidates_materialized",
    "no_loss_mask_cards_materialized",
    "no_compiler_handoff",
    "no_trainer_dry_run",
]

NEGATIVE_CASES = [
    "missing_future_input",
    "missing_required_candidate_field",
    "missing_quality_gate_rule",
    "inventory_executed_now",
    "path_inventory_loaded_now",
    "file_content_read",
    "hidden_eval_allowed",
    "route_cards_materialized",
    "loss_masks_materialized",
    "compiler_handoff_ready",
    "training_authorized",
    "decoder_ce_authorized",
    "denoise_ce_authorized",
    "authority_open",
]


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def build_contract() -> dict[str, Any]:
    return {
        "stage": STAGE,
        "stage_name": NAME,
        "contract_type": "route_card_candidate_quality_gate_v1",
        "purpose": (
            "Define the no-execution quality gate a future metadata-inventory-derived "
            "route-card candidate must pass before route-card materialization or "
            "route-to-loss translation can be considered."
        ),
        "future_inputs": list(FUTURE_INPUTS),
        "required_candidate_fields": list(REQUIRED_CANDIDATE_FIELDS),
        "quality_gate_rules": list(QUALITY_GATE_RULES),
        "active_blockers": list(ACTIVE_BLOCKERS),
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {
            "contract_only": True,
            "inventory_runner_executed_now": False,
            "metadata_path_inventory_loaded_now": False,
            "path_inventory_rows_loaded": 0,
            "candidate_rows_loaded": 0,
            "file_content_read": False,
            "dataset_rows_loaded": False,
            "arxiv_accessed": False,
            "hidden_eval_allowed": False,
            "locked_eval_allowed": False,
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
            "network_upload_performed": False,
            "cleanup_authorized_now": False,
        },
        "decision": (
            "This is a downstream contract only. It does not consume Stage9150 worker "
            "outputs, execute an inventory runner, open repo artifacts, materialize "
            "route cards, compile loss masks, hand off to the compiler, or authorize "
            "training."
        ),
    }


def validate_contract(contract: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    for item in FUTURE_INPUTS:
        if item not in contract.get("future_inputs", []):
            failures.append(f"missing_future_input:{item}")
    for item in REQUIRED_CANDIDATE_FIELDS:
        if item not in contract.get("required_candidate_fields", []):
            failures.append(f"missing_required_candidate_field:{item}")
    for item in QUALITY_GATE_RULES:
        if item not in contract.get("quality_gate_rules", []):
            failures.append(f"missing_quality_gate_rule:{item}")
    for item in ACTIVE_BLOCKERS:
        if item not in contract.get("active_blockers", []):
            failures.append(f"missing_active_blocker:{item}")

    metrics = contract.get("metrics") or {}
    if metrics.get("contract_only") is not True:
        failures.append("contract_not_marked_contract_only")
    closed_false = [
        "inventory_runner_executed_now",
        "metadata_path_inventory_loaded_now",
        "file_content_read",
        "dataset_rows_loaded",
        "arxiv_accessed",
        "hidden_eval_allowed",
        "locked_eval_allowed",
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
        "network_upload_performed",
        "cleanup_authorized_now",
    ]
    for key in closed_false:
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
        if name == "missing_future_input":
            candidate["future_inputs"].remove("metadata_only_repo_local_path_inventory_manifest")
        elif name == "missing_required_candidate_field":
            candidate["required_candidate_fields"].remove("source_provenance")
        elif name == "missing_quality_gate_rule":
            candidate["quality_gate_rules"].remove("no_file_content_or_body_fields")
        elif name == "inventory_executed_now":
            candidate["metrics"]["inventory_runner_executed_now"] = True
        elif name == "path_inventory_loaded_now":
            candidate["metrics"]["metadata_path_inventory_loaded_now"] = True
            candidate["metrics"]["path_inventory_rows_loaded"] = 1
        elif name == "file_content_read":
            candidate["metrics"]["file_content_read"] = True
        elif name == "hidden_eval_allowed":
            candidate["metrics"]["hidden_eval_allowed"] = True
        elif name == "route_cards_materialized":
            candidate["metrics"]["route_cards_materialized_now"] = True
            candidate["metrics"]["candidate_rows_loaded"] = 1
        elif name == "loss_masks_materialized":
            candidate["metrics"]["loss_mask_cards_materialized_now"] = True
        elif name == "compiler_handoff_ready":
            candidate["metrics"]["compiler_handoff_ready_now"] = True
        elif name == "training_authorized":
            candidate["metrics"]["training_authorized"] = True
        elif name == "decoder_ce_authorized":
            candidate["metrics"]["decoder_ce_authorized"] = True
        elif name == "denoise_ce_authorized":
            candidate["metrics"]["denoise_ce_authorized"] = True
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
        "future_inputs_declared": set(FUTURE_INPUTS).issubset(set(contract["future_inputs"])),
        "required_candidate_fields_declared": set(REQUIRED_CANDIDATE_FIELDS).issubset(set(contract["required_candidate_fields"])),
        "quality_gate_rules_declared": set(QUALITY_GATE_RULES).issubset(set(contract["quality_gate_rules"])),
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
            "negative_cases": len(negatives),
            "negative_cases_rejected": sum(1 for item in negatives.values() if item["rejected"]),
            "future_inputs": len(FUTURE_INPUTS),
            "required_candidate_fields": len(REQUIRED_CANDIDATE_FIELDS),
            "quality_gate_rules": len(QUALITY_GATE_RULES),
            "active_blockers": len(ACTIVE_BLOCKERS),
        },
        "decision": contract["decision"] if passed else "Route-card candidate quality gate contract failed validation.",
        "next_best_step": (
            "After the inventory-runner dry-run audit is committed, attach this candidate "
            "quality gate to the route-card materialization preflight; still do not "
            "materialize route cards or train."
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
        "# Stage9151 Route-Card Candidate Quality Gate Contract",
        "",
        f"Passed: `{public_summary['passed']}`",
        "",
        "This is a downstream no-execution contract for future inventory-derived route-card candidates.",
        "",
        f"Future inputs declared: `{summary['metrics']['future_inputs']}`",
        f"Required candidate fields: `{summary['metrics']['required_candidate_fields']}`",
        f"Quality gate rules: `{summary['metrics']['quality_gate_rules']}`",
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
