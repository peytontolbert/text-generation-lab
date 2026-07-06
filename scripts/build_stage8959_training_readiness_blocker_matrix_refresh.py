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
STAGE = 8959
NAME = "stage8959_training_readiness_blocker_matrix_refresh"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "TRAINING_READINESS_BLOCKER_MATRIX_REFRESH_STAGE8959.md"
SPINE = ROOT / "docs" / "MODEL_STACK_SPINE.md"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
MATRIX = OUT_DIR / "training_readiness_blocker_matrix_refresh.json"

SOURCE_SUMMARIES = {
    8953: "stage8953_training_readiness_matrix_refresh_after_converter_contracts",
    8954: "stage8954_bounded_decoder_trainer_loss_mask_readiness_refresh",
    8955: "stage8955_bounded_decoder_no_execution_telemetry_gate",
    8956: "stage8956_bounded_decoder_future_one_run_authorization_schema",
    8957: "stage8957_no_mining_compiler_readiness_refresh_after_decoder_gates",
    8958: "stage8958_real_manifest_audit_only_route_card_readiness",
}

READY_NO_EXECUTION_COMPONENTS = [
    "registry_and_authority_counts",
    "converter_contract_chain",
    "checkpoint_precondition_contracts",
    "bounded_decoder_trainer_command_surface",
    "bounded_decoder_loss_mask_contract",
    "bounded_decoder_telemetry_gate",
    "inactive_future_one_run_ticket_schema",
    "objective_row_judge",
    "dataset_junk_ood_ranker",
    "shortcut_baseline_audit",
    "counterfactual_obligation_audit",
    "curriculum_compiler",
    "loss_mask_card",
    "no_mining_compiler_cli",
    "real_manifest_audit_only_path_validator",
    "route_card_output_contract",
]

TRAINING_BLOCKERS = [
    {
        "id": "no_explicit_live_authorization",
        "severity": "hard_block",
        "required_before_training": "explicit one-run request plus fresh pre-execution audit",
    },
    {
        "id": "converter_not_implemented_or_runnable_tested",
        "severity": "hard_block",
        "required_before_training": "future authority ticket, runnable fixture tests, checkpoint/tensor-safe converter implementation",
    },
    {
        "id": "checkpoint_materialization_closed",
        "severity": "hard_block",
        "required_before_training": "checkpoint preconditions must be promoted from contract to authorized implementation",
    },
    {
        "id": "model_execution_closed",
        "severity": "hard_block",
        "required_before_training": "one-run ticket must authorize exactly one bounded probe command",
    },
    {
        "id": "post_run_diagnostics_absent",
        "severity": "hard_block",
        "required_before_training": "future run must emit real telemetry and pass Stage8902 diagnostics before metrics interpretation",
    },
    {
        "id": "data_mining_closed",
        "severity": "hard_block",
        "required_before_training": "mining requires separate manifest/source authorization; /arxiv remains backup-only unless explicitly opened",
    },
    {
        "id": "runtime_harness_closed",
        "severity": "hard_block",
        "required_before_training": "runtime/harness/gemma/scoring remain closed",
    },
    {
        "id": "no_capability_claim",
        "severity": "interpretation_block",
        "required_before_training": "tiny probe evidence must show bounded loss/output quality before any capability claim or scale-up",
    },
]

NEXT_SAFE_BRANCHES = [
    "continue no-execution module recovery",
    "prepare explicit one-run authorization only if user asks for that exact run",
    "audit current local manifests under real-manifest audit-only mode",
    "refresh central graph gaps against Stage8959",
]


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def summary_path(stage_name: str) -> Path:
    return ROOT / "runs/summaries" / f"{stage_name}.json"


def build_matrix(registry: dict[str, Any]) -> dict[str, Any]:
    sources: dict[str, dict[str, Any]] = {}
    for stage, stage_name in SOURCE_SUMMARIES.items():
        summary = load_json(summary_path(stage_name))
        sources[str(stage)] = {
            "stage_name": stage_name,
            "exists": bool(summary),
            "passed": summary.get("passed") is True,
            "metrics": summary.get("metrics") or {},
        }
    checks = {
        "source_summaries_present": all(item["exists"] for item in sources.values()),
        "source_summaries_passed": all(item["passed"] for item in sources.values()),
        "ready_no_execution_components_recorded": len(READY_NO_EXECUTION_COMPONENTS) >= 16,
        "training_blockers_recorded": len(TRAINING_BLOCKERS) >= 8,
        "all_blockers_are_blocks_or_interpretation_blocks": all(row["severity"] in {"hard_block", "interpretation_block"} for row in TRAINING_BLOCKERS),
        "next_safe_branches_recorded": len(NEXT_SAFE_BRANCHES) >= 4,
        "bounded_decoder_ticket_inactive": sources["8956"]["metrics"].get("execution_authorized_now") is False,
        "manifest_audit_keeps_arxiv_closed": sources["8958"]["metrics"].get("arxiv_read_authorized_for_compiler") is False and sources["8958"]["metrics"].get("arxiv_write_authorized") is False,
        "compiler_keeps_mining_closed": sources["8957"]["metrics"].get("data_mining_authorized") is False,
        "authority_counts_zero": not any(((registry.get("metrics") or {}).get("authority_counts") or {}).get(key, 0) for key in AUTHORITY_CLOSED),
        "registry_frontier_stage8958": int((registry.get("metrics") or {}).get("latest_stage", -1)) == 8958,
    }
    return {
        "stage": STAGE,
        "stage_name": NAME,
        "status": "TRAINING_READINESS_BLOCKED_BUT_RECOVERY_SPINE_CURRENT",
        "source_status": sources,
        "ready_no_execution_components": READY_NO_EXECUTION_COMPONENTS,
        "training_blockers": TRAINING_BLOCKERS,
        "next_safe_branches": NEXT_SAFE_BRANCHES,
        "checks": checks,
        "metrics": {
            "source_summaries": len(SOURCE_SUMMARIES),
            "source_summaries_passed": sum(1 for item in sources.values() if item["passed"]),
            "ready_no_execution_components": len(READY_NO_EXECUTION_COMPONENTS),
            "training_blockers": len(TRAINING_BLOCKERS),
            "hard_blockers": sum(1 for row in TRAINING_BLOCKERS if row["severity"] == "hard_block"),
            "interpretation_blockers": sum(1 for row in TRAINING_BLOCKERS if row["severity"] == "interpretation_block"),
            "training_ready": False,
            "actual_execution_authorized_next": False,
            "model_execution_attempted": False,
            "runtime_authorized_flag": False,
            "training_authorized": False,
            "data_mining_authorized": False,
            "decoder_ce_authorized": False,
            "denoise_ce_authorized": False,
            "arxiv_read_authorized_for_compiler": False,
            "arxiv_write_authorized": False,
        },
        "authority": dict(AUTHORITY_CLOSED),
        "decision": "The recovered pipeline is current for no-execution readiness, but actual model training remains hard-blocked. Converter, checkpoint materialization, execution, post-run diagnostics, mining, runtime/harness, and capability interpretation all require explicit future gates.",
    }


def validate_matrix(matrix: dict[str, Any], registry: dict[str, Any]) -> list[str]:
    failures = [key for key, value in matrix["checks"].items() if value is not True]
    if any((matrix.get("authority") or {}).values()):
        failures.append("authority_open")
    latest = int((registry.get("metrics") or {}).get("latest_stage", -1))
    if latest not in {8958, STAGE}:
        failures.append(f"unexpected_registry_frontier:{latest}")
    for key in ["training_ready", "actual_execution_authorized_next", "model_execution_attempted", "runtime_authorized_flag", "training_authorized", "data_mining_authorized", "decoder_ce_authorized", "denoise_ce_authorized", "arxiv_read_authorized_for_compiler", "arxiv_write_authorized"]:
        if matrix["metrics"].get(key) is not False:
            failures.append(key)
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
        "next_best_step": "Either continue no-execution recovery/central-graph reconciliation or explicitly request a future one-run bounded probe ticket; do not train or mine directly.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage8959 Training Readiness Blocker Matrix Refresh",
        "",
        f"Passed: `{summary['passed']}`",
        "",
        "The no-execution recovery spine is current, but actual training is still hard-blocked.",
        "",
        f"No-execution ready components: `{matrix['metrics']['ready_no_execution_components']}`",
        f"Training blockers: `{matrix['metrics']['training_blockers']}`",
        f"Training ready: `{matrix['metrics']['training_ready']}`",
        f"Data mining authorized: `{matrix['metrics']['data_mining_authorized']}`",
        "",
        "No mining, model execution, decoder CE, denoise CE, runtime, checkpoint export, or training is authorized.",
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
    marker = "## Stage8959 Training Readiness Blocker Matrix Refresh"
    spine_text = SPINE.read_text(encoding="utf-8") if SPINE.exists() else ""
    if marker not in spine_text:
        SPINE.write_text(spine_text.rstrip() + "\n\n" + "\n".join([
            marker,
            "",
            "Stage8959 refreshes the full training-readiness blocker matrix after converter, bounded decoder, compiler, and real-manifest audit recovery. The no-execution spine is current, but training remains hard-blocked.",
            "",
        ]), encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))
    raise SystemExit(0 if summary["passed"] else 1)


if __name__ == "__main__":
    main()
