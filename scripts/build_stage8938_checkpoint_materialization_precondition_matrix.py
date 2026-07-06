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
STAGE = 8938
NAME = "stage8938_checkpoint_materialization_precondition_matrix"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "CHECKPOINT_MATERIALIZATION_PRECONDITION_MATRIX_STAGE8938.md"
SPINE = ROOT / "docs" / "MODEL_STACK_SPINE.md"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
MATRIX = OUT_DIR / "checkpoint_materialization_precondition_matrix.json"
SOURCE_SUMMARIES = {
    8918: ROOT / "runs/summaries/stage8918_converter_key_mapping_init_policy_contract.json",
    8919: ROOT / "runs/summaries/stage8919_tokenizer_embedding_migration_policy_design.json",
    8920: ROOT / "runs/summaries/stage8920_checkpoint_materialization_noop_skeleton_design.json",
    8921: ROOT / "runs/summaries/stage8921_future_probe_artifact_path_policy.json",
    8922: ROOT / "runs/summaries/stage8922_cleanup_proof_no_overwrite_finalization.json",
    8927: ROOT / "runs/summaries/stage8927_tokenizer_hashlock_bridge_decision.json",
    8937: ROOT / "runs/summaries/stage8937_tiny_explicit_manifest_cli_audit.json",
}

PRECONDITIONS = [
    {
        "precondition": "tokenizer_hash_lock",
        "status": "resolved_no_execution",
        "source_stage": 8927,
        "reason": "Source tokenizer hashes and keep-target bridge decision are recorded; tokenizer swap and embedding copy remain blocked.",
    },
    {
        "precondition": "bridge_token_mapping_table_or_keep_target_tokenizer_decision",
        "status": "resolved_keep_target_no_execution",
        "source_stage": 8927,
        "reason": "Current decision keeps recovered target tokenizer 1506; bridge rows are metadata-only.",
    },
    {
        "precondition": "embedding_resize_or_no_copy_policy",
        "status": "resolved_block_copy_resize",
        "source_stage": 8919,
        "reason": "Embedding copy/resize is explicitly blocked under keep-target policy.",
    },
    {
        "precondition": "lm_head_resize_or_no_copy_policy",
        "status": "resolved_block_copy_resize",
        "source_stage": 8919,
        "reason": "LM-head copy/resize is explicitly blocked under keep-target policy.",
    },
    {
        "precondition": "bitnet_layout_decoder_contract",
        "status": "blocked_missing_contract",
        "source_stage": None,
        "reason": "Packed browser BitNet rows still require layout/dequantization spec before tensor materialization.",
    },
    {
        "precondition": "packed_weight_shape_assertions",
        "status": "blocked_missing_contract",
        "source_stage": None,
        "reason": "Packed-weight file-size/dtype/shape assertions are not yet implemented for materialization.",
    },
    {
        "precondition": "control_head_initializer_seed_contract",
        "status": "blocked_missing_contract",
        "source_stage": None,
        "reason": "Recovered target-only heads need deterministic initializer and seed policy before any initialization.",
    },
    {
        "precondition": "positional_embedding_merge_or_ignore_policy",
        "status": "blocked_missing_contract",
        "source_stage": None,
        "reason": "Source-only encoder positional embedding artifact requires explicit ignore/merge policy.",
    },
    {
        "precondition": "output_checkpoint_safe_path_contract",
        "status": "resolved_no_execution",
        "source_stage": 8921,
        "reason": "Future outputs are scoped to fresh probe directories with forbidden write classes denied.",
    },
    {
        "precondition": "cleanup_proof_no_overwrite_contract",
        "status": "resolved_no_execution",
        "source_stage": 8922,
        "reason": "Cleanup is scoped to checkpoint children only under a marked fresh probe output.",
    },
    {
        "precondition": "module_delta_and_shape_telemetry_contract",
        "status": "blocked_missing_materialization_specific_contract",
        "source_stage": None,
        "reason": "Training telemetry exists elsewhere, but checkpoint materialization needs its own before/after module-shape and delta guard.",
    },
    {
        "precondition": "manifest_path_guard_for_audit_inputs",
        "status": "resolved_no_execution",
        "source_stage": 8937,
        "reason": "Explicit repo-local manifests are path-guarded and compiler-auditable without mining.",
    },
]

FORBIDDEN_OPERATIONS = [
    "torch.load",
    "state_dict.load_state_dict",
    "read_tensor_values",
    "decode_packed_bitnet",
    "resize_token_embeddings",
    "initialize_module_parameters",
    "save_checkpoint",
    "model.forward",
    "train_step",
]


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def build_matrix(registry: dict[str, Any]) -> dict[str, Any]:
    source_status = {stage: load_json(path).get("passed") is True for stage, path in SOURCE_SUMMARIES.items()}
    resolved = [row for row in PRECONDITIONS if str(row["status"]).startswith("resolved")]
    blocked = [row for row in PRECONDITIONS if str(row["status"]).startswith("blocked")]
    checks = {
        "source_stage8918_passed": source_status.get(8918) is True,
        "source_stage8919_passed": source_status.get(8919) is True,
        "source_stage8920_passed": source_status.get(8920) is True,
        "source_stage8921_passed": source_status.get(8921) is True,
        "source_stage8922_passed": source_status.get(8922) is True,
        "source_stage8927_passed": source_status.get(8927) is True,
        "source_stage8937_passed": source_status.get(8937) is True,
        "preconditions_recorded": len(PRECONDITIONS) >= 12,
        "blocked_preconditions_remain": len(blocked) >= 5,
        "tokenizer_hash_lock_resolved": any(row["precondition"] == "tokenizer_hash_lock" and str(row["status"]).startswith("resolved") for row in PRECONDITIONS),
        "bitnet_decoder_still_blocked": any(row["precondition"] == "bitnet_layout_decoder_contract" and str(row["status"]).startswith("blocked") for row in PRECONDITIONS),
        "control_head_init_still_blocked": any(row["precondition"] == "control_head_initializer_seed_contract" and str(row["status"]).startswith("blocked") for row in PRECONDITIONS),
        "no_load_or_write_authority": True,
        "authority_counts_zero": not any(((registry.get("metrics") or {}).get("authority_counts") or {}).get(key, 0) for key in AUTHORITY_CLOSED),
    }
    return {
        "stage": STAGE,
        "stage_name": NAME,
        "status": "CHECKPOINT_MATERIALIZATION_PRECONDITION_MATRIX",
        "source_stage_status": source_status,
        "preconditions": PRECONDITIONS,
        "forbidden_operations": FORBIDDEN_OPERATIONS,
        "checks": checks,
        "metrics": {
            "preconditions": len(PRECONDITIONS),
            "resolved_preconditions": len(resolved),
            "blocked_preconditions": len(blocked),
            "training_authorized": False,
            "data_mining_authorized": False,
            "runtime_authorized_flag": False,
            "model_execution_authorized_now": False,
            "checkpoint_load_authorized": False,
            "checkpoint_write_authorized": False,
            "decoder_ce_authorized": False,
            "denoise_ce_authorized": False,
        },
        "authority": dict(AUTHORITY_CLOSED),
        "decision": "Checkpoint materialization remains blocked. Tokenizer/hash/path cleanup guards are recovered, but BitNet layout decoding, packed shape assertions, control-head initializer seed policy, positional embedding policy, and materialization-specific telemetry are still missing.",
    }


def validate_matrix(matrix: dict[str, Any], registry: dict[str, Any]) -> list[str]:
    failures = [key for key, value in matrix["checks"].items() if value is not True]
    if any((matrix.get("authority") or {}).values()):
        failures.append("authority_open")
    latest = int((registry.get("metrics") or {}).get("latest_stage", -1))
    if latest not in {8937, STAGE}:
        failures.append(f"unexpected_registry_frontier:{latest}")
    if matrix["metrics"].get("checkpoint_load_authorized") is not False:
        failures.append("checkpoint_load_authorized")
    if matrix["metrics"].get("checkpoint_write_authorized") is not False:
        failures.append("checkpoint_write_authorized")
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
        "authority": AUTHORITY_CLOSED,
        "metrics": {
            **AUTHORITY_CLOSED,
            "authority_rows": 0,
            "failures": failures,
            **matrix["metrics"],
        },
        "artifacts": {"matrix": str(MATRIX.relative_to(ROOT))},
        "decision": matrix["decision"],
        "next_best_step": "Recover materialization-specific contracts for BitNet layout decoding, packed shape assertions, control-head initializer seed policy, positional embedding policy, and module delta/shape telemetry. Do not load or write checkpoints.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage8938 Checkpoint Materialization Precondition Matrix",
        "",
        f"Passed: `{summary['passed']}`",
        "",
        "This stage reconciles checkpoint materialization preconditions after the compiler/path recovery. It does not load tensors, decode packed weights, resize embeddings, initialize heads, write checkpoints, run a forward pass, train, mine, or execute runtime.",
        "",
        f"Resolved preconditions: `{matrix['metrics']['resolved_preconditions']}`",
        f"Blocked preconditions: `{matrix['metrics']['blocked_preconditions']}`",
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
    marker = "## Stage8938 Checkpoint Materialization Precondition Matrix"
    spine_text = SPINE.read_text(encoding="utf-8") if SPINE.exists() else ""
    if marker not in spine_text:
        SPINE.write_text(spine_text.rstrip() + "\n\n" + "\n".join([
            marker,
            "",
            "Stage8938 records checkpoint materialization preconditions after path-guard recovery. Tokenizer/hash/path cleanup guards are recovered, but packed BitNet layout, shape assertions, control-head initializer seed policy, positional embedding policy, and materialization telemetry remain blockers. No checkpoint load/write or model execution is authorized.",
            "",
        ]), encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))
    raise SystemExit(0 if summary["passed"] else 1)


if __name__ == "__main__":
    main()
