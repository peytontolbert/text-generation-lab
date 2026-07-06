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
STAGE = 8942
NAME = "stage8942_materialization_delta_shape_telemetry_contract"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "MATERIALIZATION_DELTA_SHAPE_TELEMETRY_CONTRACT_STAGE8942.md"
SPINE = ROOT / "docs" / "MODEL_STACK_SPINE.md"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
CONTRACT = OUT_DIR / "materialization_delta_shape_telemetry_contract.json"
SOURCE_SUMMARY = ROOT / "runs/summaries/stage8941_positional_embedding_ignore_policy.json"

REQUIRED_FUTURE_ARTIFACTS = [
    "materialization_plan.json",
    "source_target_key_map.jsonl",
    "tensor_shape_assertions.jsonl",
    "packed_decode_manifest.jsonl",
    "embedding_lm_head_policy_report.json",
    "initialized_module_manifest.jsonl",
    "ignored_source_artifacts.jsonl",
    "missing_target_keys.jsonl",
    "unexpected_source_keys.jsonl",
    "module_delta_shape_report.json",
    "materialization_authority_ticket.json",
    "checkpoint_write_proof.json",
]
REQUIRED_DELTA_BUCKETS = [
    "renamed_dense_copy_candidate",
    "packed_bitnet_decode_candidate",
    "target_only_initialized_candidate",
    "ignored_source_only_artifact",
    "blocked_tokenizer_embedding_or_lm_head",
    "blocked_unknown_or_shape_mismatch",
]
FORBIDDEN_OPERATIONS = [
    "read_tensor_values",
    "write_checkpoint",
    "load_checkpoint",
    "decode_packed_bitnet",
    "initialize_parameters",
    "model.forward",
    "train_step",
]


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def is_safe_artifact_name(name: str) -> bool:
    p = Path(name)
    return bool(name) and not p.is_absolute() and ".." not in p.parts and len(p.parts) == 1


def build_contract(registry: dict[str, Any]) -> dict[str, Any]:
    checks = {
        "source_stage8941_passed": load_json(SOURCE_SUMMARY).get("passed") is True,
        "required_future_artifacts_recorded": len(REQUIRED_FUTURE_ARTIFACTS) >= 12,
        "required_delta_buckets_recorded": len(REQUIRED_DELTA_BUCKETS) >= 6,
        "artifact_names_are_safe": all(is_safe_artifact_name(name) for name in REQUIRED_FUTURE_ARTIFACTS),
        "checkpoint_write_proof_is_future_artifact_only": "checkpoint_write_proof.json" in REQUIRED_FUTURE_ARTIFACTS,
        "authority_ticket_required": "materialization_authority_ticket.json" in REQUIRED_FUTURE_ARTIFACTS,
        "no_current_tensor_read": True,
        "no_current_checkpoint_write": True,
        "no_current_checkpoint_load": True,
        "no_current_model_forward": True,
        "no_current_training": True,
        "authority_counts_zero": not any(((registry.get("metrics") or {}).get("authority_counts") or {}).get(key, 0) for key in AUTHORITY_CLOSED),
    }
    return {
        "stage": STAGE,
        "stage_name": NAME,
        "status": "MATERIALIZATION_DELTA_SHAPE_TELEMETRY_CONTRACT_ONLY",
        "required_future_artifacts": REQUIRED_FUTURE_ARTIFACTS,
        "required_delta_buckets": REQUIRED_DELTA_BUCKETS,
        "forbidden_operations": FORBIDDEN_OPERATIONS,
        "telemetry_contract": {
            "must_report_every_source_row_route": True,
            "must_report_every_target_key_status": True,
            "must_report_shape_before_after": True,
            "must_report_dtype_before_after": True,
            "must_report_tokenizer_hashes": True,
            "must_report_initializer_seeds_without_sampling_now": True,
            "must_report_ignored_artifacts": True,
            "must_report_blocked_artifacts": True,
            "must_fail_if_unexplained_key_delta": True,
            "must_fail_if_checkpoint_write_without_ticket": True,
        },
        "checks": checks,
        "metrics": {
            "required_future_artifacts": len(REQUIRED_FUTURE_ARTIFACTS),
            "required_delta_buckets": len(REQUIRED_DELTA_BUCKETS),
            "training_authorized": False,
            "data_mining_authorized": False,
            "runtime_authorized_flag": False,
            "model_execution_authorized_now": False,
            "tensor_read_authorized": False,
            "checkpoint_load_authorized": False,
            "checkpoint_write_authorized": False,
            "decoder_ce_authorized": False,
            "denoise_ce_authorized": False,
        },
        "authority": dict(AUTHORITY_CLOSED),
        "decision": "Materialization delta/shape telemetry contract is recovered. Any future converter must emit complete key-route, shape, dtype, initializer, ignored, blocked, and authority-ticket artifacts before checkpoint write can be considered; no current load/write/decode/init/forward/train authority is opened.",
    }


def validate_contract(contract: dict[str, Any], registry: dict[str, Any]) -> list[str]:
    failures = [key for key, value in contract["checks"].items() if value is not True]
    if any((contract.get("authority") or {}).values()):
        failures.append("authority_open")
    latest = int((registry.get("metrics") or {}).get("latest_stage", -1))
    if latest not in {8941, STAGE}:
        failures.append(f"unexpected_registry_frontier:{latest}")
    for key in ["tensor_read_authorized", "checkpoint_load_authorized", "checkpoint_write_authorized"]:
        if contract["metrics"].get(key) is not False:
            failures.append(key)
    return failures


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    registry = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    contract = build_contract(registry)
    failures = validate_contract(contract, registry)
    CONTRACT.write_text(json.dumps(contract, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    summary = {
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
        "decision": contract["decision"],
        "next_best_step": "Refresh checkpoint materialization precondition matrix. Remaining blocker should be packed BitNet codebook/order/golden-vector semantics before any decode/load/write.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage8942 Materialization Delta Shape Telemetry Contract",
        "",
        f"Passed: `{summary['passed']}`",
        "",
        "This stage records required future telemetry for checkpoint materialization. It does not read tensor values, decode packed weights, initialize parameters, load/write checkpoints, run a model, train, mine data, or execute runtime.",
        "",
        f"Required future artifacts: `{contract['metrics']['required_future_artifacts']}`",
        f"Required delta buckets: `{contract['metrics']['required_delta_buckets']}`",
        "",
    ]), encoding="utf-8")
    rows = [row for row in registry.get("rows", []) if row.get("stage_name") != NAME]
    rows.append({"stage": STAGE, "stage_name": NAME, "passed": summary["passed"], "path": str(SUMMARY), "authority": AUTHORITY_CLOSED, "next_best_step": summary["next_best_step"]})
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
    marker = "## Stage8942 Materialization Delta Shape Telemetry Contract"
    spine_text = SPINE.read_text(encoding="utf-8") if SPINE.exists() else ""
    if marker not in spine_text:
        SPINE.write_text(spine_text.rstrip() + "\n\n" + "\n".join([
            marker,
            "",
            "Stage8942 records future materialization telemetry requirements: every source/target key route, shape/dtype delta, initialized module, ignored artifact, blocked artifact, and authority ticket must be reported before checkpoint write can be considered. No load/write/decode/init/forward/train authority is opened.",
            "",
        ]), encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))
    raise SystemExit(0 if summary["passed"] else 1)


if __name__ == "__main__":
    main()
