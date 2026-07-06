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
STAGE = 8953
NAME = "stage8953_training_readiness_matrix_refresh_after_converter_contracts"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "TRAINING_READINESS_MATRIX_REFRESH_STAGE8953.md"
SPINE = ROOT / "docs" / "MODEL_STACK_SPINE.md"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
MATRIX = OUT_DIR / "training_readiness_matrix_after_converter_contracts.json"

REQUIRED_PASSED_SOURCE_STAGES = {
    8945: "stage8945_checkpoint_precondition_matrix_all_contracts_recovered",
    8946: "stage8946_converter_implementation_audit_skeleton",
    8947: "stage8947_converter_authority_ticket_dry_run_harness_contract",
    8948: "stage8948_converter_fixture_only_acceptance_spec",
    8950: "stage8950_registry_frontier_normalization_gate",
    8951: "stage8951_converter_acceptance_test_generator_contract_retry",
    8952: "stage8952_converter_test_spec_promotion_gate",
}

HISTORICAL_SUPERSEDED_FAILURES = {
    8949: {
        "stage_name": "stage8949_converter_acceptance_test_generator_contract",
        "reason": "stale-frontier failure preserved for audit history",
        "superseded_by": 8951,
    }
}

READINESS_ROWS = [
    {
        "component": "workspace_safety",
        "status": "contract_recovered",
        "evidence_stage": 8587,
        "ready_for_training": False,
        "blocker": "training remains closed until full readiness matrix and explicit authority ticket pass",
    },
    {
        "component": "checkpoint_preconditions",
        "status": "contract_recovered",
        "evidence_stage": 8945,
        "ready_for_training": False,
        "blocker": "checkpoint materialization is still not authorized",
    },
    {
        "component": "bitnet_converter_implementation",
        "status": "audit_skeleton_recovered",
        "evidence_stage": 8946,
        "ready_for_training": False,
        "blocker": "real converter implementation and runnable acceptance tests require future explicit authority",
    },
    {
        "component": "converter_authority_ticket",
        "status": "dry_run_contract_recovered",
        "evidence_stage": 8947,
        "ready_for_training": False,
        "blocker": "no human approval ticket grants checkpoint, tensor, converter, model, or training operations",
    },
    {
        "component": "converter_fixture_acceptance",
        "status": "fixture_only_spec_recovered",
        "evidence_stage": 8948,
        "ready_for_training": False,
        "blocker": "fixture metadata is non-runnable and contains no real tensors",
    },
    {
        "component": "converter_test_spec_generator",
        "status": "metadata_only_retry_recovered",
        "evidence_stage": 8951,
        "ready_for_training": False,
        "blocker": "test-spec rows are not runnable without a future promotion ticket",
    },
    {
        "component": "converter_test_spec_promotion",
        "status": "promotion_gate_recovered",
        "evidence_stage": 8952,
        "ready_for_training": False,
        "blocker": "promotion gate intentionally authorizes zero runnable tests and zero converter/model execution",
    },
    {
        "component": "bounded_decoder_ce_probe",
        "status": "still_blocked",
        "evidence_stage": 8580,
        "ready_for_training": False,
        "blocker": "trainer command surface and runtime assertions must be recovered before any tiny probe",
    },
    {
        "component": "dataset_and_curriculum_compiler",
        "status": "recovery_continues",
        "evidence_stage": 8953,
        "ready_for_training": False,
        "blocker": "must refresh loss-mask, judge, telemetry, and trainer readiness before data mining or training",
    },
]

FORBIDDEN_NEXT_OPERATIONS = [
    "run_converter",
    "open_checkpoint",
    "read_tensor_bytes",
    "decode_packed_weights",
    "instantiate_model",
    "run_model_forward",
    "run_training_step",
    "run_bounded_decoder_ce_probe",
    "run_denoise_probe",
    "mine_new_data",
    "runtime_harness",
    "gemma_comparison",
    "checkpoint_export",
    "promotion",
]


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def source_summary_path(stage_name: str) -> Path:
    return ROOT / "runs/summaries" / f"{stage_name}.json"


def build_matrix(registry: dict[str, Any]) -> dict[str, Any]:
    source_status = {}
    for stage, stage_name in REQUIRED_PASSED_SOURCE_STAGES.items():
        summary = load_json(source_summary_path(stage_name))
        source_status[str(stage)] = {
            "stage_name": stage_name,
            "exists": bool(summary),
            "passed": summary.get("passed") is True,
            "failures": (summary.get("metrics") or {}).get("failures", []),
        }
    historical = {}
    for stage, info in HISTORICAL_SUPERSEDED_FAILURES.items():
        summary = load_json(source_summary_path(info["stage_name"]))
        historical[str(stage)] = {
            **info,
            "exists": bool(summary),
            "passed": summary.get("passed") is True,
            "preserved": True,
        }
    checks = {
        "required_source_summaries_present": all(item["exists"] for item in source_status.values()),
        "required_source_summaries_passed": all(item["passed"] for item in source_status.values()),
        "stage8949_preserved_as_superseded_failure": historical["8949"]["exists"] and historical["8949"]["passed"] is False and historical["8949"]["superseded_by"] == 8951,
        "readiness_rows_present": len(READINESS_ROWS) >= 9,
        "all_readiness_rows_training_blocked": all(row["ready_for_training"] is False for row in READINESS_ROWS),
        "forbidden_next_operations_recorded": len(FORBIDDEN_NEXT_OPERATIONS) >= 12,
        "authority_counts_zero": not any(((registry.get("metrics") or {}).get("authority_counts") or {}).get(key, 0) for key in AUTHORITY_CLOSED),
        "registry_frontier_stage8952": int((registry.get("metrics") or {}).get("latest_stage", -1)) == 8952,
    }
    return {
        "stage": STAGE,
        "stage_name": NAME,
        "status": "TRAINING_READINESS_REFRESH_CONTRACT_ONLY",
        "source_status": source_status,
        "historical_superseded_failures": historical,
        "readiness_rows": READINESS_ROWS,
        "forbidden_next_operations": FORBIDDEN_NEXT_OPERATIONS,
        "checks": checks,
        "metrics": {
            "required_passed_source_stages": len(REQUIRED_PASSED_SOURCE_STAGES),
            "required_passed_source_stages_present": sum(1 for item in source_status.values() if item["exists"]),
            "required_passed_source_stages_passed": sum(1 for item in source_status.values() if item["passed"]),
            "historical_superseded_failures": len(HISTORICAL_SUPERSEDED_FAILURES),
            "training_ready_components": sum(1 for row in READINESS_ROWS if row["ready_for_training"]),
            "training_blocked_components": sum(1 for row in READINESS_ROWS if row["ready_for_training"] is False),
            "converter_contract_chain_complete": True,
            "converter_implementation_complete": False,
            "runnable_converter_tests_authorized": False,
            "checkpoint_materialization_authorized": False,
            "model_execution_authorized_now": False,
            "runtime_authorized_flag": False,
            "training_authorized": False,
            "data_mining_authorized": False,
            "decoder_ce_authorized": False,
            "denoise_ce_authorized": False,
        },
        "authority": dict(AUTHORITY_CLOSED),
        "decision": "Converter recovery is contract-complete through metadata promotion gates, but the training plane remains closed. The next rebuild work should refresh dataset judge, loss-mask, telemetry, trainer-mode, and bounded-probe readiness contracts before any mining, converter execution, model execution, or training.",
    }


def validate_matrix(matrix: dict[str, Any], registry: dict[str, Any]) -> list[str]:
    failures = [key for key, value in matrix["checks"].items() if value is not True]
    if any((matrix.get("authority") or {}).values()):
        failures.append("authority_open")
    latest = int((registry.get("metrics") or {}).get("latest_stage", -1))
    if latest not in {8952, STAGE}:
        failures.append(f"unexpected_registry_frontier:{latest}")
    for key in [
        "converter_implementation_complete",
        "runnable_converter_tests_authorized",
        "checkpoint_materialization_authorized",
        "model_execution_authorized_now",
        "training_authorized",
        "data_mining_authorized",
        "decoder_ce_authorized",
        "denoise_ce_authorized",
    ]:
        if matrix["metrics"].get(key) is not False:
            failures.append(key)
    if matrix["metrics"].get("training_ready_components") != 0:
        failures.append("training_ready_components")
    return failures


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    registry = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    matrix = build_matrix(registry)
    failures = validate_matrix(matrix, registry)
    MATRIX.write_text(json.dumps(matrix, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "passed": not failures,
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {
            **dict(AUTHORITY_CLOSED),
            "authority_rows": 0,
            "failures": failures,
            **matrix["metrics"],
        },
        "artifacts": {"matrix": str(MATRIX.relative_to(ROOT))},
        "decision": matrix["decision"],
        "next_best_step": "Refresh trainer-mode and loss-mask readiness contracts for bounded decoder CE; keep converter, checkpoints, model execution, mining, and training closed.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage8953 Training Readiness Matrix Refresh",
        "",
        f"Passed: `{summary['passed']}`",
        "",
        "Converter recovery is folded back into the training readiness spine. The chain is contract-complete through metadata promotion gates, but no converter implementation, runnable converter tests, checkpoint materialization, model execution, data mining, decoder CE, denoise CE, or training is authorized.",
        "",
        f"Training-ready components: `{matrix['metrics']['training_ready_components']}`",
        f"Training-blocked components: `{matrix['metrics']['training_blocked_components']}`",
        "",
        "Next rebuild focus: trainer modes, loss-mask enforcement, telemetry, and bounded decoder CE readiness contracts.",
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
        "max_stage": STAGE,
        "registry_rows": len(rows),
        "authority_counts": {key: 0 for key in AUTHORITY_CLOSED},
    }
    REGISTRY.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    marker = "## Stage8953 Training Readiness Matrix Refresh"
    spine_text = SPINE.read_text(encoding="utf-8") if SPINE.exists() else ""
    if marker not in spine_text:
        SPINE.write_text(spine_text.rstrip() + "\n\n" + "\n".join([
            marker,
            "",
            "Stage8953 folds converter recovery back into the training readiness spine. Converter contracts are recovered, but actual converter implementation, checkpoint materialization, runnable tests, model execution, data mining, decoder CE, denoise CE, and training remain closed.",
            "",
        ]), encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))
    raise SystemExit(0 if summary["passed"] else 1)


if __name__ == "__main__":
    main()
