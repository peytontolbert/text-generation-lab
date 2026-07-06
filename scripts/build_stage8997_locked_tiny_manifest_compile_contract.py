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
STAGE = 8997
NAME = "stage8997_locked_tiny_manifest_compile_contract"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "LOCKED_TINY_MANIFEST_COMPILE_CONTRACT_STAGE8997.md"
SPINE = ROOT / "docs" / "MODEL_STACK_SPINE.md"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
CONTRACT = OUT_DIR / "locked_tiny_manifest_compile_contract.json"

SOURCE_SUMMARY = ROOT / "runs/summaries/stage8996_tiny_row_sample_dataset_judge_contract.json"
SOURCE_CONTRACT = ROOT / "runs/local/artifacts/stage8996_tiny_row_sample_dataset_judge_contract/tiny_row_sample_dataset_judge_contract.json"

REQUIRED_INPUTS = [
    "row_sample_dataset_judge_report.json",
    "accepted_row_ids_pending_manifest_compile.jsonl",
    "candidate_row_quality_scores.jsonl",
    "judge_to_compiler_gate_status.json",
]

REQUIRED_OUTPUTS = [
    "locked_tiny_training_manifest.jsonl",
    "loss_mask_card.json",
    "manifest_schema_lock.json",
    "split_cell_card.json",
    "contamination_and_leakage_proof.json",
    "trainer_contract_dry_run_input.json",
]

LOSS_MASK_FIELDS = [
    "train_structured_aux",
    "train_decoder_ce",
    "train_denoise_ce",
    "train_retrieval",
    "train_runtime_reward",
    "train_gemma_distill",
    "train_source_body",
]

REQUIRED_MANIFEST_FIELDS = [
    "row_id",
    "source_candidate_id",
    "split",
    "route",
    "task_family",
    "language_family",
    "input_packet_ref",
    "target_ref",
    "losses_enabled",
    "authority",
    "lineage",
    "judge_score_ref",
]

FORBIDDEN_OPERATIONS = [
    "MANIFEST_COMPILE_EXECUTION_NOW",
    "ADD_UNJUDGED_ROWS",
    "USE_LOCKED_EVAL_FOR_TRAINING",
    "ENABLE_DECODER_CE_BY_DEFAULT",
    "ENABLE_DENOISE_CE_BY_DEFAULT",
    "READ_REPOSITORY_SOURCE_BODY",
    "WRITE_TO_ARXIV",
    "START_TRAINING",
    "RUN_MODEL",
    "RUN_RUNTIME",
]


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def build_contract(registry: dict[str, Any]) -> dict[str, Any]:
    source_summary = load_json(SOURCE_SUMMARY)
    source_contract = load_json(SOURCE_CONTRACT)
    checks = {
        "source_stage8996_present": SOURCE_SUMMARY.exists() and SOURCE_CONTRACT.exists(),
        "source_stage8996_passed": source_summary.get("passed") is True,
        "source_stage8996_keeps_judge_closed": (source_summary.get("metrics") or {}).get("dataset_judge_executed_now") is False,
        "source_stage8996_requires_gate_status": "judge_to_compiler_gate_status.json" in (source_contract.get("judge_outputs") or []),
        "required_inputs_recorded": len(REQUIRED_INPUTS) >= 4,
        "required_outputs_recorded": len(REQUIRED_OUTPUTS) >= 6,
        "loss_mask_fields_recorded": len(LOSS_MASK_FIELDS) >= 7,
        "manifest_fields_recorded": len(REQUIRED_MANIFEST_FIELDS) >= 12,
        "forbidden_operations_recorded": len(FORBIDDEN_OPERATIONS) >= 10,
        "authority_counts_zero": not any(((registry.get("metrics") or {}).get("authority_counts") or {}).get(key, 0) for key in AUTHORITY_CLOSED),
    }
    return {
        "stage": STAGE,
        "stage_name": NAME,
        "status": "LOCKED_TINY_MANIFEST_COMPILE_CONTRACT_NO_EXECUTION",
        "required_inputs": REQUIRED_INPUTS,
        "required_outputs": REQUIRED_OUTPUTS,
        "loss_mask_fields": LOSS_MASK_FIELDS,
        "required_manifest_fields": REQUIRED_MANIFEST_FIELDS,
        "forbidden_operations": FORBIDDEN_OPERATIONS,
        "loss_mask_defaults": {field: False for field in LOSS_MASK_FIELDS},
        "allowed_after_future_judge_pass": {
            "train_structured_aux": True,
            "train_decoder_ce": False,
            "train_denoise_ce": False,
            "train_retrieval": False,
            "train_runtime_reward": False,
            "train_gemma_distill": False,
            "train_source_body": False,
        },
        "checks": checks,
        "metrics": {
            "required_inputs": len(REQUIRED_INPUTS),
            "required_outputs": len(REQUIRED_OUTPUTS),
            "loss_mask_fields": len(LOSS_MASK_FIELDS),
            "required_manifest_fields": len(REQUIRED_MANIFEST_FIELDS),
            "forbidden_operations": len(FORBIDDEN_OPERATIONS),
            "manifest_compile_authorized_now": False,
            "manifest_emitted_now": False,
            "unjugded_rows_allowed": False,
            "unjudged_rows_allowed": False,
            "decoder_ce_default_enabled": False,
            "denoise_ce_default_enabled": False,
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
        "decision": "Locked tiny manifest compilation is specified as a future contract only. It requires a passed row-sample dataset judge and explicit loss masks before any trainer dry run or training ticket.",
    }


def validate_contract(card: dict[str, Any]) -> list[str]:
    failures = [key for key, value in card["checks"].items() if value is not True]
    if any((card.get("authority") or {}).values()):
        failures.append("authority_open")
    defaults = card.get("loss_mask_defaults") or {}
    if any(defaults.get(field) is not False for field in LOSS_MASK_FIELDS):
        failures.append("loss_mask_defaults_not_false")
    for required in ["locked_tiny_training_manifest.jsonl", "loss_mask_card.json", "trainer_contract_dry_run_input.json"]:
        if required not in card.get("required_outputs", []):
            failures.append(f"missing_output:{required}")
    for key in [
        "manifest_compile_authorized_now",
        "manifest_emitted_now",
        "unjudged_rows_allowed",
        "decoder_ce_default_enabled",
        "denoise_ce_default_enabled",
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
        "next_best_step": "After a future row-sample judge passes, design a locked manifest compile ticket. Until then, keep manifest compile and training closed.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage8997 Locked Tiny Manifest Compile Contract",
        "",
        f"Passed: `{summary['passed']}`",
        "",
        "This stage defines the future locked tiny training-manifest compile contract. It does not compile a manifest, load rows, emit training data, train, execute models, or authorize decoder/denoise CE.",
        "",
        f"Loss mask fields: `{summary['metrics']['loss_mask_fields']}`",
        f"Manifest compile authorized now: `{summary['metrics']['manifest_compile_authorized_now']}`",
        f"Manifest emitted now: `{summary['metrics']['manifest_emitted_now']}`",
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
    marker = "## Stage8997 Locked Tiny Manifest Compile Contract"
    spine_text = SPINE.read_text(encoding="utf-8") if SPINE.exists() else ""
    if marker not in spine_text:
        SPINE.write_text(spine_text.rstrip() + "\n\n" + "\n".join([
            marker,
            "",
            "Stage8997 defines the future locked tiny manifest compile contract. Loss masks default false, unjudged rows are forbidden, and manifest compile/training remain closed.",
            "",
        ]), encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))
    raise SystemExit(0 if summary["passed"] else 1)


if __name__ == "__main__":
    main()
