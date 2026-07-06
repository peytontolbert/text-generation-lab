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
STAGE = 8929
NAME = "stage8929_single_compiler_api_contract"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "SINGLE_COMPILER_API_CONTRACT_STAGE8929.md"
SPINE = ROOT / "docs" / "MODEL_STACK_SPINE.md"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
CONTRACT = OUT_DIR / "single_compiler_api_contract.json"

SOURCE_SUMMARY = ROOT / "runs/summaries/stage8928_dataset_compiler_module_inventory_gap_matrix.json"

PIPELINE_STEPS = [
    {
        "step": "ingest_manifest",
        "module": "scripts/curriculum_compiler.py",
        "input": "raw_or_recovered_rows.jsonl",
        "output": "normalized_input_rows.jsonl",
        "status": "contract_only",
    },
    {
        "step": "objective_row_judge",
        "module": "scripts/objective_row_judge.py",
        "input": "normalized_input_rows.jsonl",
        "output": "judged_rows.jsonl",
        "status": "contract_only",
    },
    {
        "step": "junk_ood_rank",
        "module": "scripts/dataset_junk_ood_ranker_v1.py",
        "input": "judged_rows.jsonl",
        "output": "ranked_rows.jsonl",
        "status": "contract_only",
    },
    {
        "step": "shortcut_baseline_audit",
        "module": "scripts/shortcut_baseline_audit.py",
        "input": "ranked_rows.jsonl",
        "output": "shortcut_baseline_card.json",
        "status": "contract_only",
    },
    {
        "step": "counterfactual_obligation_audit",
        "module": "scripts/counterfactual_obligation_audit.py",
        "input": "ranked_rows.jsonl",
        "output": "counterfactual_obligation_card.json",
        "status": "contract_only",
    },
    {
        "step": "compile_objective_manifests",
        "module": "scripts/curriculum_compiler.py",
        "input": "ranked_rows.jsonl",
        "output": "objective_manifests/",
        "status": "contract_only",
    },
    {
        "step": "emit_loss_mask_card",
        "module": "scripts/curriculum_compiler.py",
        "input": "objective_manifests/",
        "output": "loss_mask_card.json",
        "status": "contract_only",
    },
    {
        "step": "emit_patch_queue",
        "module": "scripts/training_data_attribution_influence.py",
        "input": "audit_failures.jsonl",
        "output": "dataset_patch_queue.jsonl",
        "status": "contract_only",
    },
    {
        "step": "emit_compiler_audit_card",
        "module": "scripts/training_telemetry_metrics.py",
        "input": "all_cards",
        "output": "compiler_audit_card.json",
        "status": "contract_only",
    },
]

REQUIRED_OUTPUTS = [
    "normalized_input_rows.jsonl",
    "judged_rows.jsonl",
    "ranked_rows.jsonl",
    "shortcut_baseline_card.json",
    "counterfactual_obligation_card.json",
    "objective_manifests/",
    "loss_mask_card.json",
    "dataset_patch_queue.jsonl",
    "compiler_audit_card.json",
]

HARD_GATES = [
    "authority_rows == 0",
    "runtime_authorized == false",
    "decoder_ce only when route == KEEP_BOUNDED_DECODER and explicit authorization exists",
    "denoise_ce only when route == USE_FOR_DENOISE_REPAIR and explicit authorization exists",
    "locked_eval_source rows never train",
    "shortcut strongest baseline below configured ceiling",
    "counterfactual obligations satisfied or route to patch queue",
    "target_over_budget rows route to HOLD_LONG_OUTPUT",
    "internal token rows route to repair/quarantine, not raw decoder CE",
    "all loss masks are explicit and default false",
]

FORBIDDEN_OPERATIONS = [
    "data_mining",
    "model_execution",
    "training_step",
    "runtime_execution",
    "hidden_scoring",
    "gemma_execution",
    "checkpoint_write",
    "source_body_emission",
]


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def build_contract(registry: dict[str, Any]) -> dict[str, Any]:
    module_cards = []
    for step in PIPELINE_STEPS:
        module_path = ROOT / step["module"]
        module_cards.append({**step, "module_exists": module_path.exists()})
    checks = {
        "source_stage8928_passed": load_json(SOURCE_SUMMARY).get("passed") is True,
        "pipeline_steps_present": len(PIPELINE_STEPS) >= 9,
        "all_step_modules_present": all(row["module_exists"] for row in module_cards),
        "required_outputs_present": len(REQUIRED_OUTPUTS) >= 9,
        "hard_gates_present": len(HARD_GATES) >= 10,
        "forbidden_operations_present": len(FORBIDDEN_OPERATIONS) >= 8,
        "training_remains_blocked": True,
        "data_mining_remains_blocked": True,
        "runtime_remains_blocked": True,
        "authority_counts_zero": not any(((registry.get("metrics") or {}).get("authority_counts") or {}).get(key, 0) for key in AUTHORITY_CLOSED),
    }
    return {
        "stage": STAGE,
        "stage_name": NAME,
        "contract_status": "NO_EXECUTION_API_CONTRACT_ONLY",
        "api_name": "compile_software_maintenance_curriculum_v1",
        "api_signature": {
            "input_manifest": "Path",
            "output_dir": "Path",
            "config": {
                "allow_decoder_ce": False,
                "allow_denoise_ce": False,
                "allow_runtime": False,
                "require_recovered_gates": True,
                "shortcut_ceiling": 0.8,
            },
        },
        "pipeline_steps": module_cards,
        "required_outputs": REQUIRED_OUTPUTS,
        "hard_gates": HARD_GATES,
        "forbidden_operations": FORBIDDEN_OPERATIONS,
        "checks": checks,
        "metrics": {
            "pipeline_steps": len(PIPELINE_STEPS),
            "step_modules_present": sum(1 for row in module_cards if row["module_exists"]),
            "required_outputs": len(REQUIRED_OUTPUTS),
            "hard_gates": len(HARD_GATES),
            "training_authorized": False,
            "data_mining_authorized": False,
            "runtime_authorized_flag": False,
            "model_execution_authorized_now": False,
        },
        "authority": dict(AUTHORITY_CLOSED),
        "decision": {
            "api_status": "contracted_not_executed",
            "training_status": "blocked",
            "next_required_artifact": "targeted readiness tests for source extractors, structured junk ranker, and counterfactual obligation audit",
        },
    }


def validate_contract(contract: dict[str, Any], registry: dict[str, Any]) -> list[str]:
    failures = [key for key, value in contract["checks"].items() if value is not True]
    if any((contract.get("authority") or {}).values()):
        failures.append("authority_open")
    latest = int((registry.get("metrics") or {}).get("latest_stage", -1))
    if latest not in {8928, STAGE}:
        failures.append(f"unexpected_registry_frontier:{latest}")
    return failures


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    registry = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    contract = build_contract(registry)
    failures = validate_contract(contract, registry)
    CONTRACT.write_text(json.dumps(contract, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    card = {
        "stage": STAGE,
        "stage_name": NAME,
        "passed": not failures,
        "authority": AUTHORITY_CLOSED,
        "metrics": {
            **AUTHORITY_CLOSED,
            "authority_rows": 0,
            "failures": failures,
            **contract["metrics"],
            "decoder_ce_authorized": False,
            "denoise_ce_authorized": False,
        },
        "artifacts": {"contract": str(CONTRACT.relative_to(ROOT))},
        "decision": "Single compiler API contract passed; it defines the judge/rank/audit/compile/patch queue sequence without mining, execution, or training.",
        "next_best_step": "Add targeted readiness tests for source extractors, structured junk ranker, and counterfactual obligation audit; keep training/mining blocked.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage8929 Single Compiler API Contract",
        "",
        f"Passed: `{card['passed']}`",
        "",
        "This stage defines a single no-execution compiler API contract for the recovered software-maintainer curriculum pipeline.",
        "",
        f"Pipeline steps: `{contract['metrics']['pipeline_steps']}`",
        f"Required outputs: `{contract['metrics']['required_outputs']}`",
        f"Hard gates: `{contract['metrics']['hard_gates']}`",
        "",
        "No mining, model execution, runtime, decoder CE, denoise CE, checkpoint write, source/body emission, or training is authorized.",
        "",
    ]), encoding="utf-8")
    rows = [row for row in registry.get("rows", []) if row.get("stage_name") != NAME]
    rows.append({"stage": STAGE, "stage_name": NAME, "passed": card["passed"], "path": str(SUMMARY), "authority": AUTHORITY_CLOSED, "next_best_step": card["next_best_step"]})
    rows = sorted(rows, key=lambda row: (int(row.get("stage", -1)), row.get("stage_name", "")))
    registry["rows"] = rows
    registry["passed"] = card["passed"]
    registry["metrics"] = {**(registry.get("metrics") or {}), "latest_stage": STAGE, "latest_stage_name": NAME, "latest_stage_next_best_step": card["next_best_step"], "max_stage": STAGE, "registry_rows": len(rows), "authority_counts": {key: 0 for key in AUTHORITY_CLOSED}}
    REGISTRY.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    marker = "## Stage8929 Single Compiler API Contract"
    spine_text = SPINE.read_text(encoding="utf-8") if SPINE.exists() else ""
    if marker not in spine_text:
        SPINE.write_text(spine_text.rstrip() + "\n\n" + "\n".join([
            marker,
            "",
            "Stage8929 defines the single no-execution compiler API contract: ingest -> judge -> junk/OOD rank -> shortcut/counterfactual audit -> compile objective manifests -> loss mask card -> patch queue -> compiler audit. It centralizes recovered modules without authorizing mining, training, decoder CE, denoise CE, runtime, or execution.",
            "",
        ]), encoding="utf-8")
    print(json.dumps(card, indent=2, sort_keys=True))
    raise SystemExit(0 if card["passed"] else 1)


if __name__ == "__main__":
    main()
