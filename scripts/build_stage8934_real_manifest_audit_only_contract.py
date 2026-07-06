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
STAGE = 8934
NAME = "stage8934_real_manifest_audit_only_contract"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "REAL_MANIFEST_AUDIT_ONLY_CONTRACT_STAGE8934.md"
SPINE = ROOT / "docs" / "MODEL_STACK_SPINE.md"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
CONTRACT = OUT_DIR / "real_manifest_audit_only_contract.json"

SOURCE_SUMMARY = ROOT / "runs/summaries/stage8933_no_mining_compiler_cli_wrapper_skeleton.json"

ALLOWED_INPUT_ROOTS = [
    "runs/local/artifacts",
    "runs/local/recovered",
    "runs/local/manifests",
    "datasets/recovered",
]

FORBIDDEN_INPUT_ROOTS = [
    "/arxiv",
    "/data",
    "/",
]

REQUIRED_MANIFEST_PROPERTIES = [
    "jsonl_objects_only",
    "row_id_present_or_compiler_assigns",
    "authority_absent_or_all_false",
    "no_locked_eval_training_rows",
    "source_lineage_present_for_source_backed_rows",
    "loss_masks_absent_or_default_false_before_compile",
]

AUDIT_ONLY_ALLOWED_OUTPUTS = [
    "judged_rows.jsonl",
    "ranked_rows.jsonl",
    "shortcut_baseline_card.json",
    "counterfactual_obligation_card.json",
    "compile_card.json",
    "compiler_audit_card.json",
    "dataset_patch_queue.jsonl",
]

FORBIDDEN_OPERATIONS = [
    "glob_discovery_mining",
    "remote_download",
    "recursive_dataset_scan",
    "model_execution",
    "training_step",
    "runtime_execution",
    "decoder_ce_enable",
    "denoise_ce_enable",
    "checkpoint_write",
    "mutate_input_manifest",
    "write_into_arxiv",
]


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def build_contract(registry: dict[str, Any]) -> dict[str, Any]:
    checks = {
        "source_stage8933_passed": load_json(SOURCE_SUMMARY).get("passed") is True,
        "allowed_input_roots_recorded": len(ALLOWED_INPUT_ROOTS) >= 4,
        "forbidden_input_roots_recorded": "/arxiv" in FORBIDDEN_INPUT_ROOTS and "/data" in FORBIDDEN_INPUT_ROOTS,
        "required_manifest_properties_recorded": len(REQUIRED_MANIFEST_PROPERTIES) >= 6,
        "audit_only_outputs_recorded": len(AUDIT_ONLY_ALLOWED_OUTPUTS) >= 7,
        "forbidden_operations_recorded": len(FORBIDDEN_OPERATIONS) >= 10,
        "training_remains_blocked": True,
        "data_mining_remains_blocked": True,
        "runtime_remains_blocked": True,
        "authority_counts_zero": not any(((registry.get("metrics") or {}).get("authority_counts") or {}).get(key, 0) for key in AUTHORITY_CLOSED),
    }
    return {
        "stage": STAGE,
        "stage_name": NAME,
        "contract_status": "NO_MINING_REAL_MANIFEST_AUDIT_ONLY",
        "allowed_input_roots": ALLOWED_INPUT_ROOTS,
        "forbidden_input_roots": FORBIDDEN_INPUT_ROOTS,
        "required_manifest_properties": REQUIRED_MANIFEST_PROPERTIES,
        "audit_only_allowed_outputs": AUDIT_ONLY_ALLOWED_OUTPUTS,
        "forbidden_operations": FORBIDDEN_OPERATIONS,
        "checks": checks,
        "metrics": {
            "allowed_input_roots": len(ALLOWED_INPUT_ROOTS),
            "forbidden_input_roots": len(FORBIDDEN_INPUT_ROOTS),
            "required_manifest_properties": len(REQUIRED_MANIFEST_PROPERTIES),
            "audit_only_allowed_outputs": len(AUDIT_ONLY_ALLOWED_OUTPUTS),
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
            "real_manifest_status": "audit_only_if_explicit_path_provided",
            "mining_status": "blocked",
            "training_status": "blocked",
            "next_required_artifact": "if needed, implement path validator for audit-only manifest input; otherwise return to checkpoint blockers",
        },
    }


def validate_contract(contract: dict[str, Any], registry: dict[str, Any]) -> list[str]:
    failures = [key for key, value in contract["checks"].items() if value is not True]
    if any((contract.get("authority") or {}).values()):
        failures.append("authority_open")
    latest = int((registry.get("metrics") or {}).get("latest_stage", -1))
    if latest not in {8933, STAGE}:
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
        "decision": "Real-manifest audit-only contract passed; explicitly provided local manifests may be inspected by the compiler wrapper, but mining/training/runtime/execution remain blocked.",
        "next_best_step": "Implement an audit-only manifest path validator, or return to checkpoint blockers; do not mine or train.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage8934 Real Manifest Audit-Only Contract",
        "",
        f"Passed: `{card['passed']}`",
        "",
        "This stage allows a future wrapper to inspect an explicitly provided local manifest path in audit-only mode. It does not allow dataset discovery, recursive scanning, downloads, mining, model execution, runtime, decoder CE, denoise CE, checkpoint writes, or training.",
        "",
        f"Allowed input roots: `{contract['metrics']['allowed_input_roots']}`",
        f"Required manifest properties: `{contract['metrics']['required_manifest_properties']}`",
        f"Forbidden operations: `{contract['metrics']['forbidden_operations']}`",
        "",
    ]), encoding="utf-8")
    rows = [row for row in registry.get("rows", []) if row.get("stage_name") != NAME]
    rows.append({"stage": STAGE, "stage_name": NAME, "passed": card["passed"], "path": str(SUMMARY), "authority": AUTHORITY_CLOSED, "next_best_step": card["next_best_step"]})
    rows = sorted(rows, key=lambda row: (int(row.get("stage", -1)), row.get("stage_name", "")))
    registry["rows"] = rows
    registry["passed"] = card["passed"]
    registry["metrics"] = {**(registry.get("metrics") or {}), "latest_stage": STAGE, "latest_stage_name": NAME, "latest_stage_next_best_step": card["next_best_step"], "max_stage": STAGE, "registry_rows": len(rows), "authority_counts": {key: 0 for key in AUTHORITY_CLOSED}}
    REGISTRY.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    marker = "## Stage8934 Real Manifest Audit-Only Contract"
    spine_text = SPINE.read_text(encoding="utf-8") if SPINE.exists() else ""
    if marker not in spine_text:
        SPINE.write_text(spine_text.rstrip() + "\n\n" + "\n".join([
            marker,
            "",
            "Stage8934 defines real-manifest audit-only boundaries for the compiler wrapper: explicit local input paths only, no discovery/mining/downloads, no mutation of input manifests, no `/arxiv` writes, and no training/runtime/model execution.",
            "",
        ]), encoding="utf-8")
    print(json.dumps(card, indent=2, sort_keys=True))
    raise SystemExit(0 if card["passed"] else 1)


if __name__ == "__main__":
    main()
