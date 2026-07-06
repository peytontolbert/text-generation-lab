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
STAGE = 8990
NAME = "stage8990_training_return_path_after_footer_gate_contract"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "TRAINING_RETURN_PATH_AFTER_FOOTER_GATE_CONTRACT_STAGE8990.md"
SPINE = ROOT / "docs" / "MODEL_STACK_SPINE.md"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
CONTRACT = OUT_DIR / "training_return_path_after_footer_gate_contract.json"

SOURCE_SUMMARIES = {
    8970: ROOT / "runs/summaries/stage8970_training_pipeline_module_gap_matrix.json",
    8971: ROOT / "runs/summaries/stage8971_trainer_contract_reconciliation_no_execution.json",
    8983: ROOT / "runs/summaries/stage8983_active_parquet_footer_ticket_schema_audit.json",
}

RETURN_PATH_GATES = [
    {
        "gate_id": "active_parquet_footer_ticket_instance",
        "purpose": "select a small parquet candidate subset and grant only metadata footer access",
        "requires_previous": "stage8983_active_parquet_footer_ticket_schema_audit",
        "authorizes_training": False,
    },
    {
        "gate_id": "parquet_footer_metadata_access_execution",
        "purpose": "read footer/schema metadata only for selected parquet candidates",
        "requires_previous": "active ticket instance audit pass",
        "authorizes_training": False,
    },
    {
        "gate_id": "schema_compatibility_judge",
        "purpose": "classify candidate datasets against maintainer/curriculum schemas without row bodies",
        "requires_previous": "footer metadata artifacts",
        "authorizes_training": False,
    },
    {
        "gate_id": "tiny_row_sample_ticket",
        "purpose": "allow bounded row samples from selected compatible datasets",
        "requires_previous": "schema compatibility pass",
        "authorizes_training": False,
    },
    {
        "gate_id": "row_sample_dataset_judge",
        "purpose": "run junk/OOD/leakage/contamination/schema/task-label checks on tiny row samples",
        "requires_previous": "tiny row sample artifacts",
        "authorizes_training": False,
    },
    {
        "gate_id": "locked_tiny_training_manifest_compile",
        "purpose": "compile judged rows into explicit loss-mask training manifest",
        "requires_previous": "dataset judge pass and contamination pass",
        "authorizes_training": False,
    },
    {
        "gate_id": "trainer_contract_only_dry_run",
        "purpose": "validate trainer flags, loss masks, telemetry outputs, and no-write paths without training",
        "requires_previous": "locked tiny training manifest",
        "authorizes_training": False,
    },
    {
        "gate_id": "one_run_bounded_training_ticket",
        "purpose": "authorize exactly one bounded training/probe command with post-run diagnostics",
        "requires_previous": "trainer contract-only dry run pass",
        "authorizes_training": True,
    },
]

NON_NEGOTIABLE_CONTROLS = [
    "locked_eval_never_train",
    "contamination_leakage_detector_pass",
    "dataset_junk_ood_ranker_pass",
    "loss_masks_explicit_default_false",
    "post_run_diagnostics_required",
    "high_confidence_wrong_rows_reported",
    "per_field_metrics_required",
    "authority_ticket_scope_single_run",
    "runtime_outputs_under_runs_local_artifacts",
]


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def build_contract(registry: dict[str, Any]) -> dict[str, Any]:
    sources = {stage: load_json(path) for stage, path in SOURCE_SUMMARIES.items()}
    source_passed = {stage: data.get("passed") is True for stage, data in sources.items()}
    training_authorizing_gates = [gate for gate in RETURN_PATH_GATES if gate["authorizes_training"]]
    checks = {
        "source_summaries_present": all(path.exists() for path in SOURCE_SUMMARIES.values()),
        "source_summaries_passed": all(source_passed.values()),
        "return_path_gates_recorded": len(RETURN_PATH_GATES) >= 8,
        "only_final_gate_authorizes_training": len(training_authorizing_gates) == 1 and training_authorizing_gates[0]["gate_id"] == "one_run_bounded_training_ticket",
        "non_negotiable_controls_recorded": len(NON_NEGOTIABLE_CONTROLS) >= 9,
        "current_footer_ticket_inactive": (sources[8983].get("metrics") or {}).get("ticket_active") is False,
        "current_training_closed": (sources[8971].get("metrics") or {}).get("training_authorized") is False,
        "module_stack_complete": (sources[8970].get("metrics") or {}).get("incomplete_component_families") == 0,
        "authority_counts_zero": not any(((registry.get("metrics") or {}).get("authority_counts") or {}).get(key, 0) for key in AUTHORITY_CLOSED),
    }
    return {
        "stage": STAGE,
        "stage_name": NAME,
        "status": "TRAINING_RETURN_PATH_CONTRACT_NO_EXECUTION",
        "source_stage_status": source_passed,
        "return_path_gates": RETURN_PATH_GATES,
        "non_negotiable_controls": NON_NEGOTIABLE_CONTROLS,
        "checks": checks,
        "metrics": {
            "return_path_gates": len(RETURN_PATH_GATES),
            "training_authorizing_gates": len(training_authorizing_gates),
            "non_negotiable_controls": len(NON_NEGOTIABLE_CONTROLS),
            "footer_access_authorized_now": False,
            "dataset_rows_loaded": False,
            "repository_source_bodies_loaded": False,
            "arxiv_write_authorized": False,
            "training_authorized": False,
            "data_mining_authorized": False,
            "model_execution_attempted": False,
            "decoder_ce_authorized": False,
            "denoise_ce_authorized": False,
            "runtime_authorized_flag": False,
        },
        "authority": dict(AUTHORITY_CLOSED),
        "decision": "The path back to training is explicit: footer metadata, schema judging, tiny row sampling, dataset judging, locked manifest compile, trainer contract-only dry run, then a one-run bounded training ticket. This stage authorizes none of those executions.",
    }


def validate_contract(card: dict[str, Any]) -> list[str]:
    failures = [key for key, value in card["checks"].items() if value is not True]
    if any((card.get("authority") or {}).values()):
        failures.append("authority_open")
    for key in [
        "footer_access_authorized_now",
        "dataset_rows_loaded",
        "repository_source_bodies_loaded",
        "arxiv_write_authorized",
        "training_authorized",
        "data_mining_authorized",
        "model_execution_attempted",
        "decoder_ce_authorized",
        "denoise_ce_authorized",
        "runtime_authorized_flag",
    ]:
        if card["metrics"].get(key) is not False:
            failures.append(key)
    return failures


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    registry = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    card = build_contract(registry)
    failures = validate_contract(card)
    CONTRACT.write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "passed": not failures,
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {**dict(AUTHORITY_CLOSED), "authority_rows": 0, "failures": failures, **card["metrics"]},
        "artifacts": {"contract": str(CONTRACT.relative_to(ROOT))},
        "decision": card["decision"],
        "next_best_step": "Let Stage8984 continue. In parallel, keep this return-path contract as the checklist for when to request a tiny bounded training ticket.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage8990 Training Return Path After Footer Gate Contract",
        "",
        f"Passed: `{summary['passed']}`",
        "",
        "This stage records the gated path from parquet-footer metadata preflight back to tiny bounded training. It is no-execution and does not authorize footer access, row reads, mining, training, model execution, runtime, decoder CE, or denoise CE.",
        "",
        f"Return path gates: `{summary['metrics']['return_path_gates']}`",
        f"Training-authorizing gates: `{summary['metrics']['training_authorizing_gates']}`",
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
    marker = "## Stage8990 Training Return Path After Footer Gate Contract"
    spine_text = SPINE.read_text(encoding="utf-8") if SPINE.exists() else ""
    if marker not in spine_text:
        SPINE.write_text(spine_text.rstrip() + "\n\n" + "\n".join([
            marker,
            "",
            "Stage8990 records the gated path from footer metadata preflight to tiny bounded training: footer ticket, schema judge, tiny row sample ticket, dataset judge, locked manifest, trainer contract dry run, and one-run bounded training ticket. Execution remains closed.",
            "",
        ]), encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))
    raise SystemExit(0 if summary["passed"] else 1)


if __name__ == "__main__":
    main()
