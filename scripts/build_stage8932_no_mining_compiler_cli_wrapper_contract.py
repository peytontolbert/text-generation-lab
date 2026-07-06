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
STAGE = 8932
NAME = "stage8932_no_mining_compiler_cli_wrapper_contract"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "NO_MINING_COMPILER_CLI_WRAPPER_CONTRACT_STAGE8932.md"
SPINE = ROOT / "docs" / "MODEL_STACK_SPINE.md"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
CONTRACT = OUT_DIR / "no_mining_compiler_cli_wrapper_contract.json"

SOURCE_SUMMARY = ROOT / "runs/summaries/stage8931_orchestrated_compiler_synthetic_dry_run.json"

CLI_NAME = "compile_software_maintenance_curriculum_v1"

ALLOWED_FLAGS = [
    "--input",
    "--output-dir",
    "--mode",
    "--decoder-token-cap",
    "--shortcut-ceiling",
    "--require-recovered-gates",
    "--synthetic-only",
    "--no-decoder-ce",
    "--no-denoise-ce",
    "--no-runtime",
    "--no-mining",
    "--no-model-execution",
]

REQUIRED_MODE_VALUES = [
    "synthetic_dry_run",
    "manifest_no_mining_audit_only",
]

REQUIRED_OUTPUTS = [
    "normalized_input_rows.jsonl",
    "judged_rows.jsonl",
    "ranked_rows.jsonl",
    "shortcut_baseline_card.json",
    "counterfactual_obligation_card.json",
    "compile_card.json",
    "compiler_audit_card.json",
    "dataset_patch_queue.jsonl",
]

FORBIDDEN_FLAGS = [
    "--mine",
    "--train",
    "--allow-runtime",
    "--allow-decoder-ce",
    "--allow-denoise-ce",
    "--load-model",
    "--write-checkpoint",
    "--emit-source-body",
    "--gemma",
    "--harness",
    "--score",
]

FORBIDDEN_OPERATIONS = [
    "data_mining",
    "model_execution",
    "training_step",
    "runtime_execution",
    "decoder_ce_enable",
    "denoise_ce_enable",
    "checkpoint_write",
    "source_body_emission",
    "gemma_execution",
    "harness_execution",
    "scoring",
]


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def build_contract(registry: dict[str, Any]) -> dict[str, Any]:
    source = load_json(SOURCE_SUMMARY)
    checks = {
        "source_stage8931_passed": source.get("passed") is True,
        "allowed_flags_present": len(ALLOWED_FLAGS) >= 10,
        "required_modes_present": set(REQUIRED_MODE_VALUES) == {"synthetic_dry_run", "manifest_no_mining_audit_only"},
        "required_outputs_present": len(REQUIRED_OUTPUTS) >= 8,
        "forbidden_flags_present": len(FORBIDDEN_FLAGS) >= 10,
        "forbidden_operations_present": len(FORBIDDEN_OPERATIONS) >= 10,
        "decoder_ce_forbidden_by_default": "--no-decoder-ce" in ALLOWED_FLAGS and "--allow-decoder-ce" in FORBIDDEN_FLAGS,
        "denoise_ce_forbidden_by_default": "--no-denoise-ce" in ALLOWED_FLAGS and "--allow-denoise-ce" in FORBIDDEN_FLAGS,
        "runtime_forbidden_by_default": "--no-runtime" in ALLOWED_FLAGS and "--allow-runtime" in FORBIDDEN_FLAGS,
        "mining_forbidden_by_default": "--no-mining" in ALLOWED_FLAGS and "--mine" in FORBIDDEN_FLAGS,
        "model_execution_forbidden_by_default": "--no-model-execution" in ALLOWED_FLAGS and "--load-model" in FORBIDDEN_FLAGS,
        "authority_counts_zero": not any(((registry.get("metrics") or {}).get("authority_counts") or {}).get(key, 0) for key in AUTHORITY_CLOSED),
    }
    return {
        "stage": STAGE,
        "stage_name": NAME,
        "contract_status": "NO_EXECUTION_CLI_CONTRACT_ONLY",
        "cli_name": CLI_NAME,
        "allowed_flags": ALLOWED_FLAGS,
        "required_mode_values": REQUIRED_MODE_VALUES,
        "required_outputs": REQUIRED_OUTPUTS,
        "forbidden_flags": FORBIDDEN_FLAGS,
        "forbidden_operations": FORBIDDEN_OPERATIONS,
        "checks": checks,
        "metrics": {
            "allowed_flags": len(ALLOWED_FLAGS),
            "required_mode_values": len(REQUIRED_MODE_VALUES),
            "required_outputs": len(REQUIRED_OUTPUTS),
            "forbidden_flags": len(FORBIDDEN_FLAGS),
            "forbidden_operations": len(FORBIDDEN_OPERATIONS),
            "training_authorized": False,
            "data_mining_authorized": False,
            "runtime_authorized_flag": False,
            "model_execution_authorized_now": False,
            "decoder_ce_authorized": False,
            "denoise_ce_authorized": False,
        },
        "authority": dict(AUTHORITY_CLOSED),
        "decision": {
            "cli_status": "contracted_not_implemented_or_executed",
            "default_mode": "synthetic_dry_run",
            "training_status": "blocked",
            "next_required_artifact": "wrapper skeleton or return to checkpoint/dataset recovery; no execution without a separate authorization card",
        },
    }


def validate_contract(contract: dict[str, Any], registry: dict[str, Any]) -> list[str]:
    failures = [key for key, value in contract["checks"].items() if value is not True]
    if any((contract.get("authority") or {}).values()):
        failures.append("authority_open")
    latest = int((registry.get("metrics") or {}).get("latest_stage", -1))
    if latest not in {8931, STAGE}:
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
        },
        "artifacts": {"contract": str(CONTRACT.relative_to(ROOT))},
        "decision": "No-mining compiler CLI wrapper contract passed; allowed flags, required outputs, forbidden flags, and closed authority are recorded without implementation or execution.",
        "next_best_step": "Implement a no-execution wrapper skeleton for the compiler contract, or return to checkpoint/dataset recovery; no mining/training/runtime remains authorized.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage8932 No-Mining Compiler CLI Wrapper Contract",
        "",
        f"Passed: `{card['passed']}`",
        "",
        "This stage defines the CLI surface for the recovered compiler orchestration without implementing or executing it.",
        "",
        f"Allowed flags: `{contract['metrics']['allowed_flags']}`",
        f"Forbidden flags: `{contract['metrics']['forbidden_flags']}`",
        f"Required outputs: `{contract['metrics']['required_outputs']}`",
        "",
        "Mining, model execution, runtime, decoder CE, denoise CE, checkpoint writes, source/body emission, Gemma, harness, scoring, and training remain blocked.",
        "",
    ]), encoding="utf-8")
    rows = [row for row in registry.get("rows", []) if row.get("stage_name") != NAME]
    rows.append({"stage": STAGE, "stage_name": NAME, "passed": card["passed"], "path": str(SUMMARY), "authority": AUTHORITY_CLOSED, "next_best_step": card["next_best_step"]})
    rows = sorted(rows, key=lambda row: (int(row.get("stage", -1)), row.get("stage_name", "")))
    registry["rows"] = rows
    registry["passed"] = card["passed"]
    registry["metrics"] = {**(registry.get("metrics") or {}), "latest_stage": STAGE, "latest_stage_name": NAME, "latest_stage_next_best_step": card["next_best_step"], "max_stage": STAGE, "registry_rows": len(rows), "authority_counts": {key: 0 for key in AUTHORITY_CLOSED}}
    REGISTRY.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    marker = "## Stage8932 No-Mining Compiler CLI Wrapper Contract"
    spine_text = SPINE.read_text(encoding="utf-8") if SPINE.exists() else ""
    if marker not in spine_text:
        SPINE.write_text(spine_text.rstrip() + "\n\n" + "\n".join([
            marker,
            "",
            "Stage8932 defines the no-mining compiler CLI wrapper contract for the recovered orchestration. It records allowed flags, forbidden flags, required outputs, and closed defaults for decoder CE, denoise CE, runtime, mining, model execution, checkpoint writes, and training.",
            "",
        ]), encoding="utf-8")
    print(json.dumps(card, indent=2, sort_keys=True))
    raise SystemExit(0 if card["passed"] else 1)


if __name__ == "__main__":
    main()
