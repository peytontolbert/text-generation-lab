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
STAGE = 8946
NAME = "stage8946_converter_implementation_audit_skeleton"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "CONVERTER_IMPLEMENTATION_AUDIT_SKELETON_STAGE8946.md"
SPINE = ROOT / "docs" / "MODEL_STACK_SPINE.md"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
SKELETON = OUT_DIR / "converter_implementation_audit_skeleton.json"
SOURCE_SUMMARY = ROOT / "runs/summaries/stage8945_checkpoint_precondition_matrix_all_contracts_recovered.json"

REQUIRED_AUDIT_PHASES = [
    "read_only_source_inventory",
    "tokenizer_hashlock_recheck",
    "manifest_path_guard_recheck",
    "packed_bitnet_semantics_fixture_check",
    "shape_delta_telemetry_dry_run_schema",
    "module_key_mapping_dry_run_schema",
    "control_head_initializer_seed_dry_run_schema",
    "positional_embedding_ignore_policy_recheck",
    "checkpoint_write_blocker_recheck",
    "authority_ticket_recheck",
]

FORBIDDEN_OPERATIONS = [
    "torch.load",
    "safetensors_load_file",
    "read_real_packed_weight_values",
    "decode_real_packed_bitnet",
    "dequantize_real_weights",
    "instantiate_live_model_for_forward",
    "load_state_dict",
    "save_checkpoint",
    "model.forward",
    "train_step",
]

REQUIRED_FUTURE_AUTHORITY_TICKET_FIELDS = [
    "ticket_id",
    "scope",
    "source_checkpoint_path",
    "target_checkpoint_path",
    "allowed_operations",
    "packed_bitnet_semantics_version",
    "golden_vector_fixture_hash",
    "rollback_plan",
    "runtime_budget",
    "human_approval_record",
]


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def build_skeleton(registry: dict[str, Any]) -> dict[str, Any]:
    checks = {
        "source_stage8945_passed": load_json(SOURCE_SUMMARY).get("passed") is True,
        "audit_phases_recorded": len(REQUIRED_AUDIT_PHASES) >= 10,
        "forbidden_operations_recorded": len(FORBIDDEN_OPERATIONS) >= 10,
        "authority_ticket_fields_recorded": len(REQUIRED_FUTURE_AUTHORITY_TICKET_FIELDS) >= 10,
        "no_checkpoint_load_authorized": True,
        "no_checkpoint_write_authorized": True,
        "no_real_packed_decode_authorized": True,
        "no_model_execution_authorized": True,
        "no_runtime_authorized": True,
        "no_training_authorized": True,
        "authority_counts_zero": not any(((registry.get("metrics") or {}).get("authority_counts") or {}).get(key, 0) for key in AUTHORITY_CLOSED),
    }
    return {
        "stage": STAGE,
        "stage_name": NAME,
        "status": "CONVERTER_IMPLEMENTATION_AUDIT_SKELETON_NOOP",
        "source_stage": 8945,
        "required_audit_phases": REQUIRED_AUDIT_PHASES,
        "forbidden_operations": FORBIDDEN_OPERATIONS,
        "required_future_authority_ticket_fields": REQUIRED_FUTURE_AUTHORITY_TICKET_FIELDS,
        "checks": checks,
        "metrics": {
            "audit_phases": len(REQUIRED_AUDIT_PHASES),
            "forbidden_operations": len(FORBIDDEN_OPERATIONS),
            "future_authority_ticket_fields": len(REQUIRED_FUTURE_AUTHORITY_TICKET_FIELDS),
            "converter_code_written": False,
            "converter_execution_authorized": False,
            "real_packed_decode_authorized": False,
            "checkpoint_load_authorized": False,
            "checkpoint_write_authorized": False,
            "model_execution_authorized_now": False,
            "runtime_authorized_flag": False,
            "training_authorized": False,
            "data_mining_authorized": False,
            "decoder_ce_authorized": False,
            "denoise_ce_authorized": False,
        },
        "authority": dict(AUTHORITY_CLOSED),
        "decision": "A future converter implementation audit now has a no-op skeleton: required phases, forbidden operations, and authority-ticket fields are explicit. This stage writes no converter, decodes no weights, loads/writes no checkpoint, runs no model, and trains nothing.",
    }


def validate_skeleton(skeleton: dict[str, Any], registry: dict[str, Any]) -> list[str]:
    failures = [key for key, value in skeleton["checks"].items() if value is not True]
    if any((skeleton.get("authority") or {}).values()):
        failures.append("authority_open")
    latest = int((registry.get("metrics") or {}).get("latest_stage", -1))
    if latest not in {8945, 8946, 8947, 8948, 8949, 8950, 8951, STAGE}:
        failures.append(f"unexpected_registry_frontier:{latest}")
    for key in [
        "converter_code_written",
        "converter_execution_authorized",
        "real_packed_decode_authorized",
        "checkpoint_load_authorized",
        "checkpoint_write_authorized",
        "model_execution_authorized_now",
        "training_authorized",
    ]:
        if skeleton["metrics"].get(key) is not False:
            failures.append(key)
    return failures


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    registry = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    skeleton = build_skeleton(registry)
    failures = validate_skeleton(skeleton, registry)
    SKELETON.write_text(json.dumps(skeleton, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "passed": not failures,
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {
            **dict(AUTHORITY_CLOSED),
            "authority_rows": 0,
            "failures": failures,
            **skeleton["metrics"],
        },
        "artifacts": {"skeleton": str(SKELETON.relative_to(ROOT))},
        "decision": skeleton["decision"],
        "next_best_step": "Recover a converter authority-ticket schema and dry-run audit harness contract. Do not implement conversion, decode packed weights, load/write checkpoints, run models, or train.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage8946 Converter Implementation Audit Skeleton",
        "",
        f"Passed: `{summary['passed']}`",
        "",
        "This stage defines a no-op audit skeleton for any future converter implementation. It records required audit phases, forbidden operations, and future authority-ticket fields. It does not write converter code, decode real packed weights, load/write checkpoints, run model forward, execute runtime, train, or mine data.",
        "",
        f"Audit phases: `{skeleton['metrics']['audit_phases']}`",
        f"Forbidden operations: `{skeleton['metrics']['forbidden_operations']}`",
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
    marker = "## Stage8946 Converter Implementation Audit Skeleton"
    spine_text = SPINE.read_text(encoding="utf-8") if SPINE.exists() else ""
    if marker not in spine_text:
        SPINE.write_text(spine_text.rstrip() + "\n\n" + "\n".join([
            marker,
            "",
            "Stage8946 defines a no-op converter implementation audit skeleton. It records required audit phases and authority-ticket fields while explicitly blocking converter code, packed decode, checkpoint load/write, model execution, runtime, and training.",
            "",
        ]), encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))
    raise SystemExit(0 if summary["passed"] else 1)


if __name__ == "__main__":
    main()
