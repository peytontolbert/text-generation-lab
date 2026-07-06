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
STAGE = 8944
NAME = "stage8944_bitnet_codebook_order_golden_vector_contract"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "BITNET_CODEBOOK_ORDER_GOLDEN_VECTOR_CONTRACT_STAGE8944.md"
SPINE = ROOT / "docs" / "MODEL_STACK_SPINE.md"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
CONTRACT = OUT_DIR / "bitnet_codebook_order_golden_vector_contract.json"
GOLDEN_ROWS = OUT_DIR / "bitnet_synthetic_golden_vector_contract_rows.jsonl"
SOURCE_SUMMARY = ROOT / "runs/summaries/stage8943_checkpoint_precondition_matrix_refresh.json"

CODEBOOK_CANDIDATES = [
    {
        "codebook_id": "ternary_symmetric_zero_centered",
        "codes": {"0b00": -1.0, "0b01": 0.0, "0b10": 1.0, "0b11": "reserved_or_zero"},
        "status": "candidate_requires_export_evidence",
    },
    {
        "codebook_id": "quaternary_symmetric",
        "codes": {"0b00": -1.0, "0b01": -0.3333333333, "0b10": 0.3333333333, "0b11": 1.0},
        "status": "candidate_requires_export_evidence",
    },
    {
        "codebook_id": "unsigned_affine_quantized",
        "codes": {"0b00": 0, "0b01": 1, "0b10": 2, "0b11": 3},
        "status": "candidate_requires_scale_zero_point_metadata",
    },
]
PACKING_ORDER_CANDIDATES = [
    "least_significant_bits_first",
    "most_significant_bits_first",
]
AXIS_ORDER_CANDIDATES = [
    "row_major_flattened_target_shape",
    "column_major_flattened_target_shape",
    "blocked_tile_order_requires_header",
]
SYNTHETIC_GOLDEN_ROWS = [
    {
        "golden_id": "alternating_codes_lsb",
        "packed_bytes_hex": ["e4", "1b"],
        "packing_order": "least_significant_bits_first",
        "two_bit_codes": [0, 1, 2, 3, 3, 2, 1, 0],
        "shape": [2, 4],
        "axis_order": "row_major_flattened_target_shape",
        "purpose": "distinguish byte bit order and row-major flattening",
    },
    {
        "golden_id": "alternating_codes_msb",
        "packed_bytes_hex": ["1b", "e4"],
        "packing_order": "most_significant_bits_first",
        "two_bit_codes": [0, 1, 2, 3, 3, 2, 1, 0],
        "shape": [2, 4],
        "axis_order": "row_major_flattened_target_shape",
        "purpose": "distinguish opposite byte bit order",
    },
    {
        "golden_id": "axis_order_probe",
        "packed_bytes_hex": ["24", "e4"],
        "packing_order": "least_significant_bits_first",
        "two_bit_codes": [0, 1, 2, 0, 0, 1, 2, 3],
        "shape": [4, 2],
        "axis_order": "row_major_flattened_target_shape",
        "purpose": "distinguish flattening axis from codebook values",
    },
]
REQUIRED_FUTURE_GATES = [
    "select_exact_codebook_from_export_docs_or_known_converter",
    "select_exact_byte_bit_order",
    "select_exact_axis_order",
    "define_scale_threshold_or_zero_point_policy",
    "pass_synthetic_golden_vectors",
    "pass_real_metadata_file_size_shape_assertions",
    "emit_decode_telemetry_without_checkpoint_write",
    "fail_closed_on_reserved_or_unknown_codes",
    "lm_head_vocab_projection_policy_applied",
    "materialization_delta_shape_telemetry_attached",
]
FORBIDDEN_OPERATIONS = [
    "read_real_packed_weight_values",
    "decode_real_packed_bitnet",
    "dequantize_real_weight_values",
    "load_checkpoint",
    "write_checkpoint",
    "model.forward",
    "train_step",
]


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.write_text("\n".join(json.dumps(row, sort_keys=True) for row in rows) + "\n", encoding="utf-8")


def build_contract(registry: dict[str, Any]) -> dict[str, Any]:
    checks = {
        "source_stage8943_passed": load_json(SOURCE_SUMMARY).get("passed") is True,
        "codebook_candidates_recorded": len(CODEBOOK_CANDIDATES) >= 3,
        "packing_order_candidates_recorded": len(PACKING_ORDER_CANDIDATES) >= 2,
        "axis_order_candidates_recorded": len(AXIS_ORDER_CANDIDATES) >= 3,
        "synthetic_golden_rows_recorded": len(SYNTHETIC_GOLDEN_ROWS) >= 3,
        "golden_rows_are_synthetic_only": all("real" not in row["golden_id"] for row in SYNTHETIC_GOLDEN_ROWS),
        "future_gates_recorded": len(REQUIRED_FUTURE_GATES) >= 10,
        "no_real_weight_read_authorized": True,
        "no_real_decode_authorized": True,
        "no_checkpoint_load_authorized": True,
        "no_checkpoint_write_authorized": True,
        "no_model_execution_authorized": True,
        "no_training_authorized": True,
        "authority_counts_zero": not any(((registry.get("metrics") or {}).get("authority_counts") or {}).get(key, 0) for key in AUTHORITY_CLOSED),
    }
    return {
        "stage": STAGE,
        "stage_name": NAME,
        "status": "BITNET_CODEBOOK_ORDER_GOLDEN_VECTOR_CONTRACT_ONLY",
        "codebook_candidates": CODEBOOK_CANDIDATES,
        "packing_order_candidates": PACKING_ORDER_CANDIDATES,
        "axis_order_candidates": AXIS_ORDER_CANDIDATES,
        "synthetic_golden_rows": SYNTHETIC_GOLDEN_ROWS,
        "required_future_gates": REQUIRED_FUTURE_GATES,
        "forbidden_operations": FORBIDDEN_OPERATIONS,
        "checks": checks,
        "metrics": {
            "codebook_candidates": len(CODEBOOK_CANDIDATES),
            "packing_order_candidates": len(PACKING_ORDER_CANDIDATES),
            "axis_order_candidates": len(AXIS_ORDER_CANDIDATES),
            "synthetic_golden_rows": len(SYNTHETIC_GOLDEN_ROWS),
            "required_future_gates": len(REQUIRED_FUTURE_GATES),
            "real_weight_read_authorized": False,
            "real_packed_decode_authorized": False,
            "checkpoint_load_authorized": False,
            "checkpoint_write_authorized": False,
            "training_authorized": False,
            "model_execution_authorized_now": False,
            "runtime_authorized_flag": False,
            "data_mining_authorized": False,
            "decoder_ce_authorized": False,
            "denoise_ce_authorized": False,
        },
        "authority": dict(AUTHORITY_CLOSED),
        "decision": "BitNet codebook/order/golden-vector semantics are recovered as a future proof contract only. The contract records candidate codebooks, byte order, axis order, synthetic golden vectors, and required future gates, but still forbids reading or decoding real packed weights and forbids checkpoint load/write, model execution, and training.",
    }


def validate_contract(contract: dict[str, Any], registry: dict[str, Any]) -> list[str]:
    failures = [key for key, value in contract["checks"].items() if value is not True]
    if any((contract.get("authority") or {}).values()):
        failures.append("authority_open")
    latest = int((registry.get("metrics") or {}).get("latest_stage", -1))
    if latest not in {8943, STAGE}:
        failures.append(f"unexpected_registry_frontier:{latest}")
    for key in ["real_weight_read_authorized", "real_packed_decode_authorized", "checkpoint_load_authorized", "checkpoint_write_authorized"]:
        if contract["metrics"].get(key) is not False:
            failures.append(key)
    return failures


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    registry = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    contract = build_contract(registry)
    failures = validate_contract(contract, registry)
    golden_rows = contract["synthetic_golden_rows"]
    CONTRACT.write_text(json.dumps({k: v for k, v in contract.items() if k != "synthetic_golden_rows"}, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    write_jsonl(GOLDEN_ROWS, golden_rows)
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
        "artifacts": {"contract": str(CONTRACT.relative_to(ROOT)), "golden_rows": str(GOLDEN_ROWS.relative_to(ROOT))},
        "decision": contract["decision"],
        "next_best_step": "Refresh checkpoint precondition matrix; if this resolves all no-execution contracts, design a converter implementation audit skeleton. Do not decode real weights or write checkpoints.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage8944 BitNet Codebook Order Golden Vector Contract",
        "",
        f"Passed: `{summary['passed']}`",
        "",
        "This stage records future proof obligations for packed BitNet semantics: candidate codebooks, byte bit order, axis order, synthetic golden-vector rows, and required future gates. It does not read or decode real packed weights, dequantize tensors, load/write checkpoints, run a model, train, mine data, or execute runtime.",
        "",
        f"Codebook candidates: `{contract['metrics']['codebook_candidates']}`",
        f"Synthetic golden rows: `{contract['metrics']['synthetic_golden_rows']}`",
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
    marker = "## Stage8944 BitNet Codebook Order Golden Vector Contract"
    spine_text = SPINE.read_text(encoding="utf-8") if SPINE.exists() else ""
    if marker not in spine_text:
        SPINE.write_text(spine_text.rstrip() + "\n\n" + "\n".join([
            marker,
            "",
            "Stage8944 records packed BitNet semantic proof obligations: candidate codebooks, byte bit order, axis order, synthetic golden vectors, and required future gates. It still forbids reading or decoding real packed weights, checkpoint load/write, model execution, and training.",
            "",
        ]), encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))
    raise SystemExit(0 if summary["passed"] else 1)


if __name__ == "__main__":
    main()
