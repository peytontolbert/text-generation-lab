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
STAGE = 9158
NAME = "stage9158_compiler_trainer_no_data_readiness_matrix"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
SOURCE_9157 = ROOT / "runs/summaries/stage9157_repo_local_inventory_final_authorization_design_audit.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "COMPILER_TRAINER_NO_DATA_READINESS_MATRIX_STAGE9158.md"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
MATRIX = OUT_DIR / "compiler_trainer_no_data_readiness_matrix.json"

PIPELINE_GATES = [
    {
        "gate": "metadata_inventory",
        "status": "blocked_without_explicit_execution_request",
        "requires": ["stage9157_passed", "one_run_execution_review"],
        "opens": [],
    },
    {
        "gate": "route_card_materialization",
        "status": "blocked_without_inventory_and_quality_gate",
        "requires": ["metadata_inventory_output", "stage9151_candidate_quality_gate", "stage9153_preflight_audit"],
        "opens": [],
    },
    {
        "gate": "route_to_loss_translation",
        "status": "blocked_without_route_cards",
        "requires": ["route_cards.jsonl", "route_card_materialization_audit.json", "stage9127_route_to_loss_contract_audit"],
        "opens": [],
    },
    {
        "gate": "loss_mask_materialization",
        "status": "blocked_without_route_to_loss_translation",
        "requires": ["route_to_loss_translation_audit", "stage9129_loss_mask_schema_audit"],
        "opens": [],
    },
    {
        "gate": "trainer_contract_dry_run",
        "status": "blocked_without_loss_mask_cards_and_explicit_ticket",
        "requires": ["loss_mask_cards", "trainer_input_completeness_audit", "explicit_contract_only_ticket"],
        "opens": [],
    },
    {
        "gate": "model_training",
        "status": "blocked_without_tiny_probe_execution_authorization",
        "requires": ["trainer_contract_dry_run_passed", "telemetry_contract", "execution_authorization_review"],
        "opens": [],
    },
]

CURRENT_BLOCKERS = [
    "metadata_inventory_not_executed",
    "route_cards_not_materialized",
    "route_to_loss_not_translated",
    "loss_masks_not_materialized",
    "trainer_contract_dry_run_not_authorized",
    "model_training_not_authorized",
    "decoder_ce_not_authorized",
    "denoise_ce_not_authorized",
    "runtime_not_authorized",
]

REQUIRED_NEXT_NON_EXECUTING_STAGES = [
    "route_card_materialization_preflight_instance_audit_after_inventory_ticket",
    "route_to_loss_readiness_refresh_after_route_card_gate",
    "loss_mask_materialization_preflight_design",
    "trainer_contract_dry_run_input_readiness_refresh",
]

NEGATIVE_CASES = [
    "source_stage_missing",
    "missing_pipeline_gate",
    "missing_current_blocker",
    "missing_next_stage",
    "metadata_inventory_executed",
    "route_cards_materialized",
    "loss_masks_materialized",
    "trainer_dry_run_authorized",
    "training_authorized",
    "decoder_ce_authorized",
    "denoise_ce_authorized",
    "runtime_authorized",
    "authority_open",
]


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def build_matrix(source_9157: dict[str, Any] | None = None) -> dict[str, Any]:
    source_9157 = source_9157 if source_9157 is not None else load_json(SOURCE_9157)
    return {
        "stage": STAGE,
        "stage_name": NAME,
        "matrix_type": "compiler_trainer_no_data_readiness_matrix_v1",
        "source_stage9157_passed": source_9157.get("passed") is True,
        "pipeline_gates": copy.deepcopy(PIPELINE_GATES),
        "current_blockers": list(CURRENT_BLOCKERS),
        "required_next_non_executing_stages": list(REQUIRED_NEXT_NON_EXECUTING_STAGES),
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {
            "matrix_only": True,
            "source_stage9157_passed": source_9157.get("passed") is True,
            "pipeline_gates": len(PIPELINE_GATES),
            "current_blockers": len(CURRENT_BLOCKERS),
            "required_next_non_executing_stages": len(REQUIRED_NEXT_NON_EXECUTING_STAGES),
            "metadata_inventory_executed_now": False,
            "metadata_path_inventory_materialized_now": False,
            "route_cards_materialized_now": False,
            "route_to_loss_translation_ready_now": False,
            "loss_mask_cards_materialized_now": False,
            "compiler_handoff_ready_now": False,
            "trainer_dry_run_authorized_now": False,
            "trainer_executed_now": False,
            "model_forward_attempted": False,
            "training_authorized": False,
            "decoder_ce_authorized": False,
            "denoise_ce_authorized": False,
            "runtime_authorized_flag": False,
            "arxiv_accessed": False,
            "file_content_read": False,
            "dataset_rows_loaded": False,
            "cleanup_authorized_now": False,
        },
        "decision": (
            "Compiler/trainer readiness remains blocked at the data handoff boundary. "
            "The next work is non-executing preflight refresh, not inventory execution, "
            "route-card materialization, loss-mask materialization, trainer dry run, or training."
        ),
    }


def validate_matrix(matrix: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    metrics = matrix.get("metrics") or {}
    if matrix.get("source_stage9157_passed") is not True or metrics.get("source_stage9157_passed") is not True:
        failures.append("source_stage9157_not_passed")
    gate_names = {row.get("gate") for row in matrix.get("pipeline_gates", [])}
    for gate in [row["gate"] for row in PIPELINE_GATES]:
        if gate not in gate_names:
            failures.append(f"missing_pipeline_gate:{gate}")
    for blocker in CURRENT_BLOCKERS:
        if blocker not in matrix.get("current_blockers", []):
            failures.append(f"missing_current_blocker:{blocker}")
    for stage in REQUIRED_NEXT_NON_EXECUTING_STAGES:
        if stage not in matrix.get("required_next_non_executing_stages", []):
            failures.append(f"missing_next_stage:{stage}")
    if any((matrix.get("authority") or {}).values()):
        failures.append("authority_open")
    false_keys = [
        "metadata_inventory_executed_now",
        "metadata_path_inventory_materialized_now",
        "route_cards_materialized_now",
        "route_to_loss_translation_ready_now",
        "loss_mask_cards_materialized_now",
        "compiler_handoff_ready_now",
        "trainer_dry_run_authorized_now",
        "trainer_executed_now",
        "model_forward_attempted",
        "training_authorized",
        "decoder_ce_authorized",
        "denoise_ce_authorized",
        "runtime_authorized_flag",
        "arxiv_accessed",
        "file_content_read",
        "dataset_rows_loaded",
        "cleanup_authorized_now",
    ]
    for key in false_keys:
        if metrics.get(key) is not False:
            failures.append(key)
    return failures


def run_negative_cases() -> dict[str, Any]:
    base = build_matrix()
    cases: dict[str, dict[str, Any]] = {}
    for name in NEGATIVE_CASES:
        candidate = copy.deepcopy(base)
        if name == "source_stage_missing":
            candidate["source_stage9157_passed"] = False
            candidate["metrics"]["source_stage9157_passed"] = False
        elif name == "missing_pipeline_gate":
            candidate["pipeline_gates"] = [row for row in candidate["pipeline_gates"] if row["gate"] != "route_to_loss_translation"]
        elif name == "missing_current_blocker":
            candidate["current_blockers"].remove("route_cards_not_materialized")
        elif name == "missing_next_stage":
            candidate["required_next_non_executing_stages"].remove("loss_mask_materialization_preflight_design")
        elif name == "metadata_inventory_executed":
            candidate["metrics"]["metadata_inventory_executed_now"] = True
        elif name == "route_cards_materialized":
            candidate["metrics"]["route_cards_materialized_now"] = True
        elif name == "loss_masks_materialized":
            candidate["metrics"]["loss_mask_cards_materialized_now"] = True
        elif name == "trainer_dry_run_authorized":
            candidate["metrics"]["trainer_dry_run_authorized_now"] = True
        elif name == "training_authorized":
            candidate["metrics"]["training_authorized"] = True
        elif name == "decoder_ce_authorized":
            candidate["metrics"]["decoder_ce_authorized"] = True
        elif name == "denoise_ce_authorized":
            candidate["metrics"]["denoise_ce_authorized"] = True
        elif name == "runtime_authorized":
            candidate["metrics"]["runtime_authorized_flag"] = True
        elif name == "authority_open":
            candidate["authority"]["model_execution_authorized_next"] = True
        cases[name] = candidate
    return {
        name: {"failures": validate_matrix(candidate), "rejected": bool(validate_matrix(candidate))}
        for name, candidate in cases.items()
    }


def build_summary() -> dict[str, Any]:
    matrix = build_matrix()
    failures = validate_matrix(matrix)
    negatives = run_negative_cases()
    checks = {
        "matrix_passes": failures == [],
        "negative_cases_rejected": all(item["rejected"] for item in negatives.values()),
        "all_pipeline_gates_blocked": all(not row.get("opens") for row in matrix["pipeline_gates"]),
        "authority_closed": not any(matrix["authority"].values()),
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
        "matrix": matrix,
        "negative_cases": negatives,
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {
            **matrix["metrics"],
            "negative_cases": len(negatives),
            "negative_cases_rejected": sum(1 for item in negatives.values() if item["rejected"]),
        },
        "decision": matrix["decision"] if passed else "Compiler/trainer no-data readiness matrix failed validation.",
        "next_best_step": "Refresh route-to-loss readiness against the new route-card quality and inventory gates; still do not materialize route cards or train.",
    }


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    summary = build_summary()
    MATRIX.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    public_summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "passed": summary["passed"],
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {**dict(AUTHORITY_CLOSED), **summary["metrics"], "failures": summary["failures"]},
        "artifacts": {"matrix": str(MATRIX.relative_to(ROOT)), "doc": str(DOC.relative_to(ROOT))},
        "decision": summary["decision"],
        "next_best_step": summary["next_best_step"],
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(public_summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage9158 Compiler/Trainer No-Data Readiness Matrix",
        "",
        f"Passed: `{public_summary['passed']}`",
        "",
        "Records the blocked compiler/trainer handoff state after the repo-local inventory authorization gates.",
        "",
        f"Pipeline gates: `{summary['metrics']['pipeline_gates']}`",
        f"Current blockers: `{summary['metrics']['current_blockers']}`",
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
