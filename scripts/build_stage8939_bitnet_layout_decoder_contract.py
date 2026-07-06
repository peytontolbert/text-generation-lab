#!/usr/bin/env python3
from __future__ import annotations

import json
import math
import time
from collections import Counter
from pathlib import Path
from typing import Any

try:
    from scripts.diagnostic_ticket_contract import AUTHORITY_CLOSED
except ModuleNotFoundError:  # pragma: no cover
    from diagnostic_ticket_contract import AUTHORITY_CLOSED  # type: ignore

ROOT = Path(__file__).resolve().parents[1]
STAGE = 8939
NAME = "stage8939_bitnet_layout_decoder_contract"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "BITNET_LAYOUT_DECODER_CONTRACT_STAGE8939.md"
SPINE = ROOT / "docs" / "MODEL_STACK_SPINE.md"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
CONTRACT = OUT_DIR / "bitnet_layout_decoder_contract.json"
PACKED_ROWS = OUT_DIR / "packed_bitnet_metadata_assertion_rows.jsonl"
SOURCE_ROWS = ROOT / "runs/local/artifacts/stage8916_nonexecuting_converter_shape_report_dry_run/shape_report_rows_metadata_only.jsonl"
SOURCE_SUMMARY = ROOT / "runs/summaries/stage8938_checkpoint_materialization_precondition_matrix.json"

PACKING_VALUES_PER_BYTE = 4
PACKING_BITS_PER_VALUE = 2
FORBIDDEN_OPERATIONS = [
    "read_binary_tensor_values",
    "decode_packed_bitnet",
    "dequantize_weight_values",
    "torch.load",
    "state_dict.load_state_dict",
    "initialize_module_parameters",
    "save_checkpoint",
    "model.forward",
    "train_step",
]
REQUIRED_FUTURE_IMPLEMENTATION_GATES = [
    "explicit_2bit_codebook_semantics",
    "packing_order_and_axis_spec",
    "signed_or_ternary_value_mapping_spec",
    "scale_or_threshold_metadata_policy",
    "golden_tiny_decode_vectors",
    "file_size_to_target_shape_assertions",
    "dtype_output_policy",
    "module_key_mapping_lock",
    "no_inplace_source_mutation",
    "materialization_telemetry_delta_guard",
]


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def load_rows(path: Path = SOURCE_ROWS) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def is_packed_bitnet_row(row: dict[str, Any]) -> bool:
    return row.get("status") == "blocked" and str(row.get("source_artifact") or "").startswith("layers/") and row.get("dtype") == "bitnet_packed_u8_to_converter_output"


def target_weight_count(shape: Any) -> int | None:
    if not isinstance(shape, list) or not shape or not all(isinstance(dim, int) and dim > 0 for dim in shape):
        return None
    total = 1
    for dim in shape:
        total *= dim
    return total


def build_assertion_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for row in rows:
        if not is_packed_bitnet_row(row):
            continue
        count = target_weight_count(row.get("target_shape"))
        expected_bytes = None if count is None else math.ceil(count / PACKING_VALUES_PER_BYTE)
        file_size = row.get("file_size_bytes")
        mismatch_class = None
        if expected_bytes != file_size and row.get("target_key") == "lm_head":
            mismatch_class = "source_vocab_lm_head_blocked_by_tokenizer_policy"
        out.append({
            "source_artifact": row.get("source_artifact"),
            "source_key": row.get("source_key"),
            "target_key": row.get("target_key"),
            "target_shape": row.get("target_shape"),
            "target_weight_count": count,
            "file_size_bytes": file_size,
            "expected_packed_bytes_2bit": expected_bytes,
            "file_size_matches_2bit_shape": expected_bytes == file_size,
            "mismatch_class": mismatch_class,
            "packing_bits_per_value": PACKING_BITS_PER_VALUE,
            "packing_values_per_byte": PACKING_VALUES_PER_BYTE,
            "binary_tensor_values_read": False,
            "decode_authorized": False,
            "checkpoint_write_authorized": False,
            "training_authorized": False,
        })
    return out


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.write_text("\n".join(json.dumps(row, sort_keys=True) for row in rows) + "\n", encoding="utf-8")


def build_contract(registry: dict[str, Any]) -> dict[str, Any]:
    source_rows = load_rows()
    packed = build_assertion_rows(source_rows)
    target_shapes = Counter(str(row.get("target_shape")) for row in packed)
    mismatch_rows = [row for row in packed if not row["file_size_matches_2bit_shape"]]
    non_vocab_mismatch_rows = [row for row in mismatch_rows if row.get("mismatch_class") != "source_vocab_lm_head_blocked_by_tokenizer_policy"]
    checks = {
        "source_stage8938_passed": load_json(SOURCE_SUMMARY).get("passed") is True,
        "source_shape_rows_exist": len(source_rows) >= 150,
        "packed_rows_present": len(packed) >= 100,
        "non_vocab_file_sizes_match_2bit_shape": len(non_vocab_mismatch_rows) == 0,
        "lm_head_vocab_projection_isolated": len(mismatch_rows) == 1 and mismatch_rows[0].get("mismatch_class") == "source_vocab_lm_head_blocked_by_tokenizer_policy",
        "all_binary_values_unread": all(row["binary_tensor_values_read"] is False for row in packed),
        "all_decode_blocked": all(row["decode_authorized"] is False for row in packed),
        "all_checkpoint_write_blocked": all(row["checkpoint_write_authorized"] is False for row in packed),
        "all_training_blocked": all(row["training_authorized"] is False for row in packed),
        "future_gates_recorded": len(REQUIRED_FUTURE_IMPLEMENTATION_GATES) >= 10,
        "authority_counts_zero": not any(((registry.get("metrics") or {}).get("authority_counts") or {}).get(key, 0) for key in AUTHORITY_CLOSED),
    }
    return {
        "stage": STAGE,
        "stage_name": NAME,
        "status": "BITNET_LAYOUT_CONTRACT_METADATA_ONLY",
        "layout_contract": {
            "container": "u8_packed_weight_bin",
            "inferred_bits_per_value_from_file_size": PACKING_BITS_PER_VALUE,
            "inferred_values_per_byte_from_file_size": PACKING_VALUES_PER_BYTE,
            "decode_status": "blocked_pending_codebook_and_order_spec",
            "metadata_shape_assertion_status": "passed_if_checks_pass",
            "tensor_value_read_authorized": False,
            "dequantization_authorized": False,
        },
        "future_implementation_gates": REQUIRED_FUTURE_IMPLEMENTATION_GATES,
        "forbidden_operations": FORBIDDEN_OPERATIONS,
        "checks": checks,
        "metrics": {
            "source_rows": len(source_rows),
            "packed_rows": len(packed),
            "target_shape_classes": len(target_shapes),
            "shape_assertion_failures": len(mismatch_rows),
            "non_vocab_shape_assertion_failures": len(non_vocab_mismatch_rows),
            "lm_head_vocab_projection_mismatch_rows": sum(1 for row in mismatch_rows if row.get("mismatch_class") == "source_vocab_lm_head_blocked_by_tokenizer_policy"),
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
        "packed_rows": packed,
        "authority": dict(AUTHORITY_CLOSED),
        "decision": "Packed BitNet metadata shape assertions pass for non-vocab packed rows under an inferred 2-bit/four-values-per-byte layout. The lm_head packed row is isolated as a source-vocab projection mismatch covered by tokenizer/LM-head policy. Actual layout decoding/dequantization remains blocked until codebook/order/golden-vector gates exist.",
    }


def validate_contract(contract: dict[str, Any], registry: dict[str, Any]) -> list[str]:
    failures = [key for key, value in contract["checks"].items() if value is not True]
    if any((contract.get("authority") or {}).values()):
        failures.append("authority_open")
    latest = int((registry.get("metrics") or {}).get("latest_stage", -1))
    if latest not in {8938, STAGE}:
        failures.append(f"unexpected_registry_frontier:{latest}")
    for key in ["checkpoint_load_authorized", "checkpoint_write_authorized", "decode_packed_bitnet_authorized"]:
        if contract["metrics"].get(key) is not False:
            failures.append(key)
    return failures


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    registry = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    contract = build_contract(registry)
    failures = validate_contract(contract, registry)
    packed_rows = contract.pop("packed_rows")
    CONTRACT.write_text(json.dumps(contract, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    write_jsonl(PACKED_ROWS, packed_rows)
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
        "artifacts": {"contract": str(CONTRACT.relative_to(ROOT)), "packed_rows": str(PACKED_ROWS.relative_to(ROOT))},
        "decision": contract["decision"],
        "next_best_step": "Recover packed BitNet codebook/order/golden-vector contract or move to control-head initializer seed policy. Do not decode packed weights or load checkpoints.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage8939 BitNet Layout Decoder Contract",
        "",
        f"Passed: `{summary['passed']}`",
        "",
        "This stage defines metadata-only packed BitNet layout assertions. It infers a 2-bit/four-values-per-byte packing from file sizes and target shapes for non-vocab packed rows, isolates the lm_head source-vocab mismatch, and does not read tensor values, decode packed weights, dequantize, load a checkpoint, write a checkpoint, run a model, train, or execute runtime.",
        "",
        f"Packed rows: `{contract['metrics']['packed_rows']}`",
        f"Shape assertion failures: `{contract['metrics']['shape_assertion_failures']}`",
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
    marker = "## Stage8939 BitNet Layout Decoder Contract"
    spine_text = SPINE.read_text(encoding="utf-8") if SPINE.exists() else ""
    if marker not in spine_text:
        SPINE.write_text(spine_text.rstrip() + "\n\n" + "\n".join([
            marker,
            "",
            "Stage8939 records metadata-only packed BitNet layout assertions. File sizes match an inferred 2-bit/four-values-per-byte shape contract, but actual codebook/order semantics, decode, dequantization, checkpoint load/write, model execution, and training remain blocked.",
            "",
        ]), encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))
    raise SystemExit(0 if summary["passed"] else 1)


if __name__ == "__main__":
    main()
