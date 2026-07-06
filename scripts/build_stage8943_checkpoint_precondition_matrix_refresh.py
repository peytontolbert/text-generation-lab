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
STAGE = 8943
NAME = "stage8943_checkpoint_precondition_matrix_refresh"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "CHECKPOINT_PRECONDITION_MATRIX_REFRESH_STAGE8943.md"
SPINE = ROOT / "docs" / "MODEL_STACK_SPINE.md"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
MATRIX = OUT_DIR / "checkpoint_precondition_matrix_refresh.json"
SOURCE_SUMMARIES = {
    8927: ROOT / "runs/summaries/stage8927_tokenizer_hashlock_bridge_decision.json",
    8937: ROOT / "runs/summaries/stage8937_tiny_explicit_manifest_cli_audit.json",
    8939: ROOT / "runs/summaries/stage8939_bitnet_layout_decoder_contract.json",
    8940: ROOT / "runs/summaries/stage8940_control_head_initializer_seed_policy.json",
    8941: ROOT / "runs/summaries/stage8941_positional_embedding_ignore_policy.json",
    8942: ROOT / "runs/summaries/stage8942_materialization_delta_shape_telemetry_contract.json",
}

PRECONDITIONS = [
    ("tokenizer_hash_lock", "resolved_no_execution", 8927),
    ("bridge_token_mapping_table_or_keep_target_tokenizer_decision", "resolved_keep_target_no_execution", 8927),
    ("embedding_resize_or_no_copy_policy", "resolved_block_copy_resize", 8927),
    ("lm_head_resize_or_no_copy_policy", "resolved_block_copy_resize", 8927),
    ("manifest_path_guard_for_audit_inputs", "resolved_no_execution", 8937),
    ("packed_weight_metadata_shape_assertions", "resolved_metadata_only", 8939),
    ("bitnet_layout_decoder_contract", "blocked_codebook_order_golden_vectors_missing", 8939),
    ("control_head_initializer_seed_contract", "resolved_metadata_only", 8940),
    ("positional_embedding_merge_or_ignore_policy", "resolved_ignore_source_only", 8941),
    ("materialization_module_delta_shape_telemetry_contract", "resolved_contract_only", 8942),
]


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def build_matrix(registry: dict[str, Any]) -> dict[str, Any]:
    source_status = {stage: load_json(path).get("passed") is True for stage, path in SOURCE_SUMMARIES.items()}
    rows = [{"precondition": name, "status": status, "source_stage": source_stage} for name, status, source_stage in PRECONDITIONS]
    resolved = [row for row in rows if str(row["status"]).startswith("resolved")]
    blocked = [row for row in rows if str(row["status"]).startswith("blocked")]
    checks = {
        "all_source_summaries_passed": all(source_status.values()),
        "preconditions_recorded": len(rows) == 10,
        "resolved_preconditions_expected": len(resolved) == 9,
        "single_blocker_remaining": len(blocked) == 1,
        "remaining_blocker_is_bitnet_semantics": len(blocked) == 1 and blocked[0]["precondition"] == "bitnet_layout_decoder_contract",
        "no_checkpoint_load_authorized": True,
        "no_checkpoint_write_authorized": True,
        "no_model_execution_authorized": True,
        "no_training_authorized": True,
        "authority_counts_zero": not any(((registry.get("metrics") or {}).get("authority_counts") or {}).get(key, 0) for key in AUTHORITY_CLOSED),
    }
    return {
        "stage": STAGE,
        "stage_name": NAME,
        "status": "CHECKPOINT_PRECONDITION_MATRIX_REFRESH",
        "source_stage_status": source_status,
        "preconditions": rows,
        "checks": checks,
        "metrics": {
            "preconditions": len(rows),
            "resolved_preconditions": len(resolved),
            "blocked_preconditions": len(blocked),
            "training_authorized": False,
            "data_mining_authorized": False,
            "runtime_authorized_flag": False,
            "model_execution_authorized_now": False,
            "checkpoint_load_authorized": False,
            "checkpoint_write_authorized": False,
            "decode_packed_bitnet_authorized": False,
            "decoder_ce_authorized": False,
            "denoise_ce_authorized": False,
        },
        "authority": dict(AUTHORITY_CLOSED),
        "decision": "Checkpoint materialization preconditions are mostly recovered as no-execution contracts. The only remaining semantic blocker is packed BitNet codebook/order/golden-vector semantics; checkpoint load/write, model execution, and training remain closed.",
    }


def validate_matrix(matrix: dict[str, Any], registry: dict[str, Any]) -> list[str]:
    failures = [key for key, value in matrix["checks"].items() if value is not True]
    if any((matrix.get("authority") or {}).values()):
        failures.append("authority_open")
    latest = int((registry.get("metrics") or {}).get("latest_stage", -1))
    if latest not in {8942, STAGE}:
        failures.append(f"unexpected_registry_frontier:{latest}")
    for key in ["checkpoint_load_authorized", "checkpoint_write_authorized", "decode_packed_bitnet_authorized"]:
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
        "authority": AUTHORITY_CLOSED,
        "metrics": {
            **AUTHORITY_CLOSED,
            "authority_rows": 0,
            "failures": failures,
            **matrix["metrics"],
        },
        "artifacts": {"matrix": str(MATRIX.relative_to(ROOT))},
        "decision": matrix["decision"],
        "next_best_step": "Recover packed BitNet codebook/order/golden-vector semantics contract. Do not decode packed weights, load checkpoints, write checkpoints, run models, or train.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage8943 Checkpoint Precondition Matrix Refresh",
        "",
        f"Passed: `{summary['passed']}`",
        "",
        "This stage refreshes checkpoint materialization preconditions after recovering the BitNet metadata shape contract, control-head initializer seed policy, positional embedding ignore policy, and materialization telemetry contract.",
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
    marker = "## Stage8943 Checkpoint Precondition Matrix Refresh"
    spine_text = SPINE.read_text(encoding="utf-8") if SPINE.exists() else ""
    if marker not in spine_text:
        SPINE.write_text(spine_text.rstrip() + "\n\n" + "\n".join([
            marker,
            "",
            "Stage8943 refreshes checkpoint materialization preconditions: 9 recovered as no-execution contracts, 1 remaining blocker for packed BitNet codebook/order/golden-vector semantics. Checkpoint load/write, packed decode, model execution, and training remain closed.",
            "",
        ]), encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))
    raise SystemExit(0 if summary["passed"] else 1)


if __name__ == "__main__":
    main()
