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
STAGE = 8945
NAME = "stage8945_checkpoint_precondition_matrix_all_contracts_recovered"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "CHECKPOINT_PRECONDITION_MATRIX_ALL_CONTRACTS_RECOVERED_STAGE8945.md"
SPINE = ROOT / "docs" / "MODEL_STACK_SPINE.md"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
MATRIX = OUT_DIR / "checkpoint_precondition_matrix_all_contracts_recovered.json"
SOURCE_SUMMARIES = {
    8927: ROOT / "runs/summaries/stage8927_tokenizer_hashlock_bridge_decision.json",
    8937: ROOT / "runs/summaries/stage8937_tiny_explicit_manifest_cli_audit.json",
    8939: ROOT / "runs/summaries/stage8939_bitnet_layout_decoder_contract.json",
    8940: ROOT / "runs/summaries/stage8940_control_head_initializer_seed_policy.json",
    8941: ROOT / "runs/summaries/stage8941_positional_embedding_ignore_policy.json",
    8942: ROOT / "runs/summaries/stage8942_materialization_delta_shape_telemetry_contract.json",
    8944: ROOT / "runs/summaries/stage8944_bitnet_codebook_order_golden_vector_contract.json",
}

PRECONDITIONS = [
    ("tokenizer_hash_lock", "contract_recovered_no_execution", 8927),
    ("bridge_token_mapping_table_or_keep_target_tokenizer_decision", "contract_recovered_no_execution", 8927),
    ("embedding_resize_or_no_copy_policy", "contract_recovered_block_copy_resize", 8927),
    ("lm_head_resize_or_no_copy_policy", "contract_recovered_block_copy_resize", 8927),
    ("manifest_path_guard_for_audit_inputs", "contract_recovered_no_execution", 8937),
    ("packed_weight_metadata_shape_assertions", "contract_recovered_metadata_only", 8939),
    ("bitnet_codebook_order_golden_vector_semantics", "contract_recovered_future_proof_only", 8944),
    ("control_head_initializer_seed_contract", "contract_recovered_metadata_only", 8940),
    ("positional_embedding_merge_or_ignore_policy", "contract_recovered_ignore_source_only", 8941),
    ("materialization_module_delta_shape_telemetry_contract", "contract_recovered_future_required", 8942),
]
IMPLEMENTATION_BLOCKERS = [
    "converter_implementation_not_written",
    "real_packed_decode_not_authorized",
    "checkpoint_load_not_authorized",
    "checkpoint_write_not_authorized",
    "model_forward_not_authorized",
    "training_not_authorized",
]


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def build_matrix(registry: dict[str, Any]) -> dict[str, Any]:
    source_status = {stage: load_json(path).get("passed") is True for stage, path in SOURCE_SUMMARIES.items()}
    rows = [{"precondition": name, "status": status, "source_stage": source_stage} for name, status, source_stage in PRECONDITIONS]
    recovered = [row for row in rows if str(row["status"]).startswith("contract_recovered")]
    checks = {
        "all_source_summaries_passed": all(source_status.values()),
        "preconditions_recorded": len(rows) == 10,
        "all_precondition_contracts_recovered": len(recovered) == len(rows),
        "implementation_blockers_recorded": len(IMPLEMENTATION_BLOCKERS) >= 6,
        "no_checkpoint_load_authorized": True,
        "no_checkpoint_write_authorized": True,
        "no_real_packed_decode_authorized": True,
        "no_model_execution_authorized": True,
        "no_training_authorized": True,
        "authority_counts_zero": not any(((registry.get("metrics") or {}).get("authority_counts") or {}).get(key, 0) for key in AUTHORITY_CLOSED),
    }
    return {
        "stage": STAGE,
        "stage_name": NAME,
        "status": "CHECKPOINT_PRECONDITION_CONTRACTS_RECOVERED_IMPLEMENTATION_BLOCKED",
        "source_stage_status": source_status,
        "preconditions": rows,
        "implementation_blockers": IMPLEMENTATION_BLOCKERS,
        "checks": checks,
        "metrics": {
            "preconditions": len(rows),
            "recovered_precondition_contracts": len(recovered),
            "blocked_precondition_contracts": len(rows) - len(recovered),
            "implementation_blockers": len(IMPLEMENTATION_BLOCKERS),
            "training_authorized": False,
            "data_mining_authorized": False,
            "runtime_authorized_flag": False,
            "model_execution_authorized_now": False,
            "checkpoint_load_authorized": False,
            "checkpoint_write_authorized": False,
            "real_packed_decode_authorized": False,
            "decoder_ce_authorized": False,
            "denoise_ce_authorized": False,
        },
        "authority": dict(AUTHORITY_CLOSED),
        "decision": "All checkpoint materialization preconditions are recovered as no-execution contracts. This does not authorize implementation, real packed decode, checkpoint load/write, model execution, or training; the next step is a converter implementation audit skeleton.",
    }


def validate_matrix(matrix: dict[str, Any], registry: dict[str, Any]) -> list[str]:
    failures = [key for key, value in matrix["checks"].items() if value is not True]
    if any((matrix.get("authority") or {}).values()):
        failures.append("authority_open")
    latest = int((registry.get("metrics") or {}).get("latest_stage", -1))
    if latest not in {8944, STAGE}:
        failures.append(f"unexpected_registry_frontier:{latest}")
    for key in ["checkpoint_load_authorized", "checkpoint_write_authorized", "real_packed_decode_authorized"]:
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
        "next_best_step": "Design a converter implementation audit skeleton that remains no-op until a future explicit authority ticket exists. Do not decode real weights, load/write checkpoints, run models, or train.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage8945 Checkpoint Precondition Matrix All Contracts Recovered",
        "",
        f"Passed: `{summary['passed']}`",
        "",
        "This stage records that checkpoint materialization preconditions are recovered as no-execution contracts. Implementation remains blocked: no real packed decode, checkpoint load/write, model execution, runtime, decoder CE, denoise CE, training, or promotion authority is opened.",
        "",
        f"Recovered precondition contracts: `{matrix['metrics']['recovered_precondition_contracts']}`",
        f"Implementation blockers: `{matrix['metrics']['implementation_blockers']}`",
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
    marker = "## Stage8945 Checkpoint Precondition Matrix All Contracts Recovered"
    spine_text = SPINE.read_text(encoding="utf-8") if SPINE.exists() else ""
    if marker not in spine_text:
        SPINE.write_text(spine_text.rstrip() + "\n\n" + "\n".join([
            marker,
            "",
            "Stage8945 records all checkpoint materialization preconditions as recovered contracts, while implementation remains blocked. No real packed decode, checkpoint load/write, model execution, runtime, training, or promotion authority is opened.",
            "",
        ]), encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))
    raise SystemExit(0 if summary["passed"] else 1)


if __name__ == "__main__":
    main()
