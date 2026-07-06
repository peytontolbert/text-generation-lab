#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = 8912
NAME = "stage8912_shape_report_schema_conversion_map_audit"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "SHAPE_REPORT_SCHEMA_CONVERSION_MAP_STAGE8912.md"
SPINE = ROOT / "docs" / "MODEL_STACK_SPINE.md"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
AUDIT = OUT_DIR / "shape_report_schema_conversion_map_audit.json"
SCHEMA = OUT_DIR / "shape_report_schema_v1.json"
CONVERSION_MAP = OUT_DIR / "conversion_map_draft_v1.jsonl"

EXPORT_ROOT = Path("/data/repository_library/exports/agent_kernel/models/agentkernel_lite_100m_bitnet_v11")

AUTHORITY_CLOSED = {
    "model_execution_authorized_next": False,
    "decoder_ce_training_authorized_next": False,
    "denoise_ce_training_authorized_next": False,
    "runtime_authorized": False,
    "source_emission_authorized": False,
    "body_emission_authorized": False,
    "gemma_execution_authorized_next": False,
    "harness_execution_authorized_next": False,
    "scoring_authorized_next": False,
    "controller_complete_merge_authorized_next": False,
    "promotion_ready": False,
}

FLOAT32_BYTES = 4
EXPORT_VOCAB = 8207
TARGET_VOCAB = 1506
DMODEL = 640
MAX_POS = 4096

SHAPE_REPORT_SCHEMA = {
    "schema_name": "agentkernel_lite_state_dict_shape_report_v1",
    "required_fields": [
        "source_key",
        "target_key",
        "source_artifact",
        "source_shape",
        "target_shape",
        "dtype",
        "action",
        "status",
        "provenance",
        "notes",
    ],
    "allowed_actions": [
        "copy_exact",
        "rename_copy",
        "transpose_copy",
        "split_gated_mlp",
        "merge_or_ignore_positional_embedding",
        "resize_embedding_rows",
        "new_init",
        "skip",
        "blocked",
    ],
    "required_statuses": ["compatible", "needs_migration", "new_init_required", "blocked"],
    "forbidden_in_this_stage": [
        "torch_load",
        "state_dict_load",
        "read_binary_tensor_values",
        "embedding_resize",
        "checkpoint_write",
        "model_forward",
        "training_step",
    ],
}


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def file_size(rel: str) -> int | None:
    path = EXPORT_ROOT / rel
    return path.stat().st_size if path.exists() else None


def infer_float32_shape(rel: str, expected: list[int]) -> dict[str, Any]:
    size = file_size(rel)
    expected_bytes = FLOAT32_BYTES
    for dim in expected:
        expected_bytes *= int(dim)
    return {
        "artifact": rel,
        "exists": size is not None,
        "file_size_bytes": size,
        "expected_shape": expected,
        "expected_bytes": expected_bytes,
        "matches_expected_bytes": size == expected_bytes,
    }


def conversion_rows() -> list[dict[str, Any]]:
    return [
        {
            "source_key": "enc_embed_weight",
            "target_key": "enc_embed.weight",
            "source_artifact": "dense/enc_embed_weight.f32.bin",
            "source_shape": [EXPORT_VOCAB, DMODEL],
            "target_shape": [TARGET_VOCAB, DMODEL],
            "dtype": "float32",
            "action": "resize_embedding_rows",
            "status": "needs_migration",
            "provenance": "local_agentkernel_lite_browser_bitnet_export",
            "notes": "Export vocab 8207 differs from recovered target vocab 1506; do not copy without tokenizer decision.",
        },
        {
            "source_key": "dec_embed_weight",
            "target_key": "dec_embed.weight",
            "source_artifact": "dense/dec_embed_weight.f32.bin",
            "source_shape": [EXPORT_VOCAB, DMODEL],
            "target_shape": [TARGET_VOCAB, DMODEL],
            "dtype": "float32",
            "action": "resize_embedding_rows",
            "status": "needs_migration",
            "provenance": "local_agentkernel_lite_browser_bitnet_export",
            "notes": "Decoder embedding rows require the same tokenizer/vocab decision as encoder embedding.",
        },
        {
            "source_key": "enc_norm_weight",
            "target_key": "enc_norm.weight",
            "source_artifact": "dense/enc_norm_weight.f32.bin",
            "source_shape": [DMODEL],
            "target_shape": [DMODEL],
            "dtype": "float32",
            "action": "rename_copy",
            "status": "compatible",
            "provenance": "local_agentkernel_lite_browser_bitnet_export",
            "notes": "Shape-compatible metadata only; binary values are not read in this stage.",
        },
        {
            "source_key": "dec_norm_weight",
            "target_key": "dec_norm.weight",
            "source_artifact": "dense/dec_norm_weight.f32.bin",
            "source_shape": [DMODEL],
            "target_shape": [DMODEL],
            "dtype": "float32",
            "action": "rename_copy",
            "status": "compatible",
            "provenance": "local_agentkernel_lite_browser_bitnet_export",
            "notes": "Shape-compatible metadata only; binary values are not read in this stage.",
        },
        {
            "source_key": "enc_pos_embed_weight",
            "target_key": None,
            "source_artifact": "dense/enc_pos_embed_weight.f32.bin",
            "source_shape": [MAX_POS, DMODEL],
            "target_shape": None,
            "dtype": "float32",
            "action": "merge_or_ignore_positional_embedding",
            "status": "blocked",
            "provenance": "local_agentkernel_lite_browser_bitnet_export",
            "notes": "Recovered PyTorch module currently uses decoder RoPE and encoder has no learned positional embedding parameter.",
        },
        {
            "source_key": "encoder.0.attn.w_q",
            "target_key": "encoder.0.self_attn.q_proj.weight",
            "source_artifact": "layers/encoder_0_attn_w_q.packed_weight.u8.bin",
            "source_shape": "packed_bitnet_layout_header_required",
            "target_shape": [DMODEL, DMODEL],
            "dtype": "bitnet_packed_u8_to_float_or_quantized_tensor",
            "action": "rename_copy",
            "status": "blocked",
            "provenance": "local_agentkernel_lite_browser_bitnet_export",
            "notes": "Packed runtime layout requires a converter spec; no binary tensor decoding is authorized here.",
        },
        {
            "source_key": None,
            "target_key": "retrieval_query_head.weight",
            "source_artifact": None,
            "source_shape": None,
            "target_shape": [128, DMODEL],
            "dtype": "float32_or_training_dtype",
            "action": "new_init",
            "status": "new_init_required",
            "provenance": "recovered_target_control_head",
            "notes": "Missing from export metadata; must be newly initialized or recovered from a different checkpoint.",
        },
        {
            "source_key": None,
            "target_key": "structured_heads.*.weight/bias",
            "source_artifact": None,
            "source_shape": None,
            "target_shape": "per_structured_field_vocab",
            "dtype": "float32_or_training_dtype",
            "action": "new_init",
            "status": "new_init_required",
            "provenance": "recovered_software_maintainer_control_surface",
            "notes": "Structured software-maintainer heads are current-project control heads and cannot be assumed from export.",
        },
    ]


def validate_rows(rows: list[dict[str, Any]]) -> list[str]:
    failures: list[str] = []
    required = set(SHAPE_REPORT_SCHEMA["required_fields"])
    allowed_actions = set(SHAPE_REPORT_SCHEMA["allowed_actions"])
    statuses = set(SHAPE_REPORT_SCHEMA["required_statuses"])
    for index, row in enumerate(rows):
        missing = required - set(row)
        if missing:
            failures.append(f"row_{index}_missing_fields:{sorted(missing)}")
        if row.get("action") not in allowed_actions:
            failures.append(f"row_{index}_bad_action:{row.get('action')}")
        if row.get("status") not in statuses:
            failures.append(f"row_{index}_bad_status:{row.get('status')}")
    return failures


def build_audit() -> dict[str, Any]:
    rows = conversion_rows()
    inferred = {
        "enc_embed": infer_float32_shape("dense/enc_embed_weight.f32.bin", [EXPORT_VOCAB, DMODEL]),
        "dec_embed": infer_float32_shape("dense/dec_embed_weight.f32.bin", [EXPORT_VOCAB, DMODEL]),
        "enc_norm": infer_float32_shape("dense/enc_norm_weight.f32.bin", [DMODEL]),
        "dec_norm": infer_float32_shape("dense/dec_norm_weight.f32.bin", [DMODEL]),
        "enc_pos_embed": infer_float32_shape("dense/enc_pos_embed_weight.f32.bin", [MAX_POS, DMODEL]),
    }
    row_failures = validate_rows(rows)
    checks = {
        "schema_has_required_fields": bool(SHAPE_REPORT_SCHEMA["required_fields"]),
        "conversion_rows_present": len(rows) >= 8,
        "compatible_rows": sum(row["status"] == "compatible" for row in rows),
        "blocked_rows": sum(row["status"] == "blocked" for row in rows),
        "new_init_rows": sum(row["status"] == "new_init_required" for row in rows),
        "needs_migration_rows": sum(row["status"] == "needs_migration" for row in rows),
        "embedding_file_sizes_match_export_vocab": inferred["enc_embed"]["matches_expected_bytes"] and inferred["dec_embed"]["matches_expected_bytes"],
        "positional_embedding_file_matches_export_shape": inferred["enc_pos_embed"]["matches_expected_bytes"],
        "direct_load_allowed": False,
        "binary_tensor_values_read": False,
    }
    blockers = [
        "shape_report_schema_only_no_weight_loading",
        "embedding_rows_require_tokenizer_migration",
        "packed_bitnet_layers_require_converter_spec",
        "learned_encoder_positional_embedding_has_no_current_target_key",
        "retrieval_policy_structured_heads_require_new_init_or_external_checkpoint",
    ]
    return {
        "stage": STAGE,
        "stage_name": NAME,
        "schema": SHAPE_REPORT_SCHEMA,
        "inferred_file_shapes": inferred,
        "conversion_rows": rows,
        "checks": checks,
        "row_validation_failures": row_failures,
        "blockers": blockers,
        "decision": {
            "conversion_map_status": "draft_schema_only",
            "direct_load_status": "blocked",
            "next_required_artifact": "non_executing_converter_shape_report_generator",
        },
        "authority": AUTHORITY_CLOSED,
    }


def validate_audit(audit: dict[str, Any], registry: dict[str, Any]) -> list[str]:
    failures = list(audit["row_validation_failures"])
    checks = audit["checks"]
    if checks["conversion_rows_present"] is not True:
        failures.append("conversion_rows_missing")
    if checks["embedding_file_sizes_match_export_vocab"] is not True:
        failures.append("embedding_file_size_mismatch")
    if checks["direct_load_allowed"] is True:
        failures.append("direct_load_was_incorrectly_allowed")
    if checks["binary_tensor_values_read"] is True:
        failures.append("binary_tensor_values_were_read")
    if checks["blocked_rows"] < 2:
        failures.append("insufficient_blocked_rows")
    if checks["new_init_rows"] < 2:
        failures.append("missing_new_init_head_rows")
    authority_counts = (registry.get("metrics") or {}).get("authority_counts") or {}
    if any(authority_counts.get(key, 0) != 0 for key in AUTHORITY_CLOSED):
        failures.append("registry_authority_counts_nonzero")
    latest = (registry.get("metrics") or {}).get("latest_stage")
    if latest not in {8911, STAGE}:
        failures.append(f"unexpected_registry_frontier:{latest}")
    return failures


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.write_text("\n".join(json.dumps(row, sort_keys=True) for row in rows) + "\n", encoding="utf-8")


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    registry = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    audit = build_audit()
    failures = validate_audit(audit, registry)
    AUDIT.write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    SCHEMA.write_text(json.dumps(SHAPE_REPORT_SCHEMA, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    write_jsonl(CONVERSION_MAP, audit["conversion_rows"])
    card = {
        "stage": STAGE,
        "stage_name": NAME,
        "passed": not failures,
        "authority": AUTHORITY_CLOSED,
        "metrics": {
            **AUTHORITY_CLOSED,
            "authority_rows": 0,
            "failures": failures,
            "conversion_rows": len(audit["conversion_rows"]),
            "compatible_rows": audit["checks"]["compatible_rows"],
            "blocked_rows": audit["checks"]["blocked_rows"],
            "new_init_rows": audit["checks"]["new_init_rows"],
            "needs_migration_rows": audit["checks"]["needs_migration_rows"],
            "embedding_file_sizes_match_export_vocab": audit["checks"]["embedding_file_sizes_match_export_vocab"],
            "direct_load_allowed": audit["checks"]["direct_load_allowed"],
            "binary_tensor_values_read": audit["checks"]["binary_tensor_values_read"],
            "model_execution_authorized_now": False,
            "training_authorized": False,
            "decoder_ce_authorized": False,
            "denoise_ce_authorized": False,
            "runtime_authorized_flag": False,
            "data_mining_authorized": False,
            "download_authorized": False,
        },
        "artifacts": {
            "audit": str(AUDIT.relative_to(ROOT)),
            "schema": str(SCHEMA.relative_to(ROOT)),
            "conversion_map": str(CONVERSION_MAP.relative_to(ROOT)),
        },
        "decision": "Shape-report schema and draft conversion map are ready as metadata-only artifacts; direct loading remains blocked." if not failures else "Shape-report schema conversion-map audit failed.",
        "next_best_step": "Build a non-executing converter dry-run that emits full shape rows from metadata only; still do not decode weights, load state dicts, resize embeddings, execute, or train.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage8912 Shape Report Schema And Conversion Map Audit",
        "",
        f"Passed: `{card['passed']}`",
        "",
        "This stage defines the metadata-only shape report schema required before any future AgentKernel Lite export conversion.",
        "",
        "It records draft conversion rows for embeddings, norms, one packed attention tensor, the extra encoder positional embedding, and missing recovered control heads.",
        "",
        "Important decisions:",
        "",
        "- direct load remains blocked",
        "- embedding rows need tokenizer migration",
        "- packed BitNet layers need a converter spec",
        "- recovered retrieval/policy/structured heads need new-init or another checkpoint",
        "- no binary tensor values were read",
        "",
        "Authority remains closed for model execution, training, decoder CE, denoise CE, runtime, source/body emission, Gemma, harness, scoring, controller merge, and promotion.",
        "",
    ]), encoding="utf-8")
    rows = [row for row in registry.get("rows", []) if row.get("stage_name") != NAME]
    rows.append({"stage": STAGE, "stage_name": NAME, "passed": card["passed"], "path": str(SUMMARY), "authority": AUTHORITY_CLOSED, "next_best_step": card["next_best_step"]})
    rows = sorted(rows, key=lambda row: (int(row.get("stage", -1)), row.get("stage_name", "")))
    registry["rows"] = rows
    registry["passed"] = card["passed"]
    registry["metrics"] = {**registry.get("metrics", {}), "latest_stage": STAGE, "latest_stage_name": NAME, "latest_stage_next_best_step": card["next_best_step"], "max_stage": STAGE, "registry_rows": len(rows), "authority_counts": {key: 0 for key in AUTHORITY_CLOSED}}
    REGISTRY.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    marker = "## Stage8912 Shape Report Schema And Conversion Map"
    spine_text = SPINE.read_text(encoding="utf-8") if SPINE.exists() else ""
    if marker not in spine_text:
        SPINE.write_text(spine_text.rstrip() + "\n\n" + "\n".join([
            marker,
            "",
            "Stage8912 adds a metadata-only shape report schema and draft conversion map for the local AgentKernel Lite export. It preserves the direct-load block: embedding rows require tokenizer migration, packed BitNet layers require a converter spec, and recovered control heads require new initialization or another checkpoint.",
            "",
        ]), encoding="utf-8")
    print(json.dumps(card, indent=2, sort_keys=True))
    raise SystemExit(0 if card["passed"] else 1)


if __name__ == "__main__":
    main()
