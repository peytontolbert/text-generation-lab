#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = 8916
NAME = "stage8916_nonexecuting_converter_shape_report_dry_run"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "NONEXECUTING_CONVERTER_SHAPE_REPORT_DRY_RUN_STAGE8916.md"
SPINE = ROOT / "docs" / "MODEL_STACK_SPINE.md"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
AUDIT = OUT_DIR / "nonexecuting_converter_shape_report_dry_run.json"
ROWS_JSONL = OUT_DIR / "shape_report_rows_metadata_only.jsonl"

EXPORT_ROOT = Path("/data/repository_library/exports/agent_kernel/models/agentkernel_lite_100m_bitnet_v11")
BROWSER_EXPORT = EXPORT_ROOT / "agentkernel_lite_browser_bitnet_export.json"

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
DMODEL = 640
DFF = 2048
EXPORT_VOCAB = 8207
TARGET_VOCAB = 1506
MAX_POS = 4096

FORBIDDEN = [
    "torch_load",
    "state_dict_load",
    "read_binary_tensor_values",
    "decode_packed_bitnet",
    "embedding_resize",
    "checkpoint_write",
    "model_forward",
    "training_step",
]


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def dense_shape_for(name: str, size: int) -> tuple[list[int] | str, str, str]:
    if name in {"enc_embed_weight.f32.bin", "dec_embed_weight.f32.bin"}:
        return [EXPORT_VOCAB, DMODEL], "needs_migration", "resize_embedding_rows"
    if name == "enc_pos_embed_weight.f32.bin":
        return [MAX_POS, DMODEL], "blocked", "merge_or_ignore_positional_embedding"
    if size == DMODEL * FLOAT32_BYTES:
        return [DMODEL], "compatible", "rename_copy"
    return "unknown_dense_shape_from_filename_only", "blocked", "blocked"


def target_key_for_dense(name: str) -> str | None:
    mapping = {
        "enc_embed_weight.f32.bin": "enc_embed.weight",
        "dec_embed_weight.f32.bin": "dec_embed.weight",
        "enc_norm_weight.f32.bin": "enc_norm.weight",
        "enc_norm_bias.f32.bin": "enc_norm.bias",
        "dec_norm_weight.f32.bin": "dec_norm.weight",
        "dec_norm_bias.f32.bin": "dec_norm.bias",
        "enc_pos_embed_weight.f32.bin": None,
    }
    if name in mapping:
        return mapping[name]
    m = re.fullmatch(r"encoder_(\d+)_n([12])_weight\.f32\.bin", name)
    if m:
        return f"encoder.{m.group(1)}.norm{m.group(2)}.weight"
    m = re.fullmatch(r"decoder_(\d+)_(self_attn_block|cross_block)_n([12])_weight\.f32\.bin", name)
    if m:
        layer, block, norm = m.groups()
        # Recovered decoder has norm1/norm2 for self block and norm3/norm4 for cross block.
        idx = int(norm) + (0 if block == "self_attn_block" else 2)
        return f"decoder.{layer}.norm{idx}.weight"
    return None


def pytorch_target_for_module(module: str) -> tuple[str, list[int] | str, str]:
    target = module
    target = target.replace(".attn.w_q", ".self_attn.q_proj.weight")
    target = target.replace(".attn.w_k", ".self_attn.k_proj.weight")
    target = target.replace(".attn.w_v", ".self_attn.v_proj.weight")
    target = target.replace(".attn.w_o", ".self_attn.o_proj.weight")
    target = target.replace(".cross.w_q", ".cross_attn.q_proj.weight")
    target = target.replace(".cross.w_k", ".cross_attn.k_proj.weight")
    target = target.replace(".cross.w_v", ".cross_attn.v_proj.weight")
    target = target.replace(".cross.w_o", ".cross_attn.o_proj.weight")
    target = target.replace(".self_attn_block.mlp.w_in", ".self_mlp.up_proj.weight")
    target = target.replace(".self_attn_block.mlp.w_out", ".self_mlp.down_proj.weight")
    target = target.replace(".cross_block.mlp.w_in", ".cross_mlp.up_proj.weight")
    target = target.replace(".cross_block.mlp.w_out", ".cross_mlp.down_proj.weight")
    target = target.replace(".mlp.w_in", ".mlp.up_proj.weight")
    target = target.replace(".mlp.w_out", ".mlp.down_proj.weight")
    if module.endswith("w_in"):
        shape: list[int] | str = [2 * DFF, DMODEL]
    elif module.endswith("w_out"):
        shape = [DMODEL, DFF]
    elif module == "lm_head":
        shape = [TARGET_VOCAB, DMODEL]
    else:
        shape = [DMODEL, DMODEL]
    return target, shape, "packed_bitnet_layout_header_required"


def build_rows() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for path in sorted((EXPORT_ROOT / "dense").glob("*.bin")):
        rel = str(path.relative_to(EXPORT_ROOT))
        shape, status, action = dense_shape_for(path.name, path.stat().st_size)
        rows.append(
            {
                "source_key": path.stem.replace(".f32", ""),
                "target_key": target_key_for_dense(path.name),
                "source_artifact": rel,
                "source_shape": shape,
                "target_shape": [TARGET_VOCAB, DMODEL] if path.name in {"enc_embed_weight.f32.bin", "dec_embed_weight.f32.bin"} else ([DMODEL] if status == "compatible" else None),
                "dtype": "float32",
                "action": action,
                "status": status,
                "provenance": "dense_file_metadata",
                "file_size_bytes": path.stat().st_size,
                "binary_tensor_values_read": False,
                "notes": "metadata-only dense file row; file size inspected but tensor values were not read",
            }
        )
    modules = ((load_json(BROWSER_EXPORT).get("quantization") or {}).get("modules") or [])
    for module in modules:
        target, target_shape, source_shape = pytorch_target_for_module(str(module))
        artifact_prefix = str(module).replace(".", "_")
        rows.append(
            {
                "source_key": module,
                "target_key": target,
                "source_artifact": f"layers/{artifact_prefix}.packed_weight.u8.bin",
                "source_shape": source_shape,
                "target_shape": target_shape,
                "dtype": "bitnet_packed_u8_to_converter_output",
                "action": "blocked",
                "status": "blocked",
                "provenance": "browser_bitnet_manifest_metadata",
                "file_size_bytes": (EXPORT_ROOT / "layers" / f"{artifact_prefix}.packed_weight.u8.bin").stat().st_size if (EXPORT_ROOT / "layers" / f"{artifact_prefix}.packed_weight.u8.bin").exists() else None,
                "binary_tensor_values_read": False,
                "notes": "packed BitNet row requires converter implementation and layout audit before any tensor materialization",
            }
        )
    for target_key, target_shape in [
        ("retrieval_query_head.weight", [128, DMODEL]),
        ("retrieval_doc_head.weight", [128, DMODEL]),
        ("agent_policy_heads.*.weight/bias", "per_policy_head"),
        ("agent_intent_head.weight/bias", [18, DMODEL]),
        ("agent_controller.weight/bias", [128, DMODEL]),
        ("scalar_invariant.weight", [32, DMODEL]),
        ("structured_heads.*.weight/bias", "per_structured_field_vocab"),
    ]:
        rows.append(
            {
                "source_key": None,
                "target_key": target_key,
                "source_artifact": None,
                "source_shape": None,
                "target_shape": target_shape,
                "dtype": "float32_or_training_dtype",
                "action": "new_init",
                "status": "new_init_required",
                "provenance": "recovered_target_control_surface",
                "file_size_bytes": None,
                "binary_tensor_values_read": False,
                "notes": "target-only recovered control head requires initialization policy or another checkpoint",
            }
        )
    return rows


def validate_rows(rows: list[dict[str, Any]]) -> list[str]:
    failures: list[str] = []
    required = {"source_key", "target_key", "source_artifact", "source_shape", "target_shape", "dtype", "action", "status", "provenance", "binary_tensor_values_read"}
    for idx, row in enumerate(rows):
        missing = required - set(row)
        if missing:
            failures.append(f"row_{idx}_missing:{sorted(missing)}")
        if row.get("binary_tensor_values_read") is not False:
            failures.append(f"row_{idx}_read_binary_values")
    return failures


def build_audit() -> dict[str, Any]:
    rows = build_rows()
    row_failures = validate_rows(rows)
    dense_rows = [r for r in rows if str(r.get("source_artifact") or "").startswith("dense/")]
    packed_rows = [r for r in rows if str(r.get("source_artifact") or "").startswith("layers/")]
    checks = {
        "rows_present": len(rows) > 0,
        "dense_rows": len(dense_rows),
        "packed_manifest_rows": len(packed_rows),
        "new_init_rows": sum(r["status"] == "new_init_required" for r in rows),
        "needs_migration_rows": sum(r["status"] == "needs_migration" for r in rows),
        "blocked_rows": sum(r["status"] == "blocked" for r in rows),
        "compatible_rows": sum(r["status"] == "compatible" for r in rows),
        "binary_tensor_values_read": any(r["binary_tensor_values_read"] for r in rows),
        "direct_load_allowed": False,
        "converter_emits_full_metadata_rows": len(dense_rows) >= 43 and len(packed_rows) >= 109,
    }
    return {
        "stage": STAGE,
        "stage_name": NAME,
        "checks": checks,
        "row_validation_failures": row_failures,
        "forbidden_operations": FORBIDDEN,
        "shape_rows": rows,
        "decision": {
            "dry_run_status": "metadata_only_complete_enough_for_next_audit",
            "direct_load_status": "blocked",
            "next_required_artifact": "converter_row_completeness_and_collision_audit",
        },
        "authority": AUTHORITY_CLOSED,
    }


def validate_audit(audit: dict[str, Any], registry: dict[str, Any]) -> list[str]:
    failures = list(audit["row_validation_failures"])
    checks = audit["checks"]
    if checks["converter_emits_full_metadata_rows"] is not True:
        failures.append("insufficient_metadata_rows")
    if checks["binary_tensor_values_read"] is True:
        failures.append("binary_tensor_values_were_read")
    if checks["direct_load_allowed"] is True:
        failures.append("direct_load_was_incorrectly_allowed")
    if checks["new_init_rows"] < 7:
        failures.append("missing_control_head_new_init_rows")
    authority_counts = (registry.get("metrics") or {}).get("authority_counts") or {}
    if any(authority_counts.get(key, 0) != 0 for key in AUTHORITY_CLOSED):
        failures.append("registry_authority_counts_nonzero")
    latest = (registry.get("metrics") or {}).get("latest_stage")
    if latest not in {8915, STAGE}:
        failures.append(f"unexpected_registry_frontier:{latest}")
    return failures


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.write_text("\n".join(json.dumps(row, sort_keys=True) for row in rows) + "\n", encoding="utf-8")


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    registry = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    audit = build_audit()
    failures = validate_audit(audit, registry)
    AUDIT.write_text(json.dumps({k: v for k, v in audit.items() if k != "shape_rows"}, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    write_jsonl(ROWS_JSONL, audit["shape_rows"])
    card = {
        "stage": STAGE,
        "stage_name": NAME,
        "passed": not failures,
        "authority": AUTHORITY_CLOSED,
        "metrics": {
            **AUTHORITY_CLOSED,
            "authority_rows": 0,
            "failures": failures,
            **audit["checks"],
            "shape_rows": len(audit["shape_rows"]),
            "model_execution_authorized_now": False,
            "training_authorized": False,
            "decoder_ce_authorized": False,
            "denoise_ce_authorized": False,
            "runtime_authorized_flag": False,
            "data_mining_authorized": False,
            "download_authorized": False,
        },
        "artifacts": {"audit": str(AUDIT.relative_to(ROOT)), "shape_rows": str(ROWS_JSONL.relative_to(ROOT))},
        "decision": "Non-executing converter dry-run emitted metadata-only shape rows and kept direct loading blocked." if not failures else "Non-executing converter dry-run failed.",
        "next_best_step": "Audit converter row completeness/collisions, especially target-key collisions and unknown dense rows; still do not decode weights, load state dicts, execute, or train.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage8916 Non-Executing Converter Shape Report Dry Run",
        "",
        f"Passed: `{card['passed']}`",
        "",
        "This stage emits metadata-only shape rows for dense export files, manifest-listed packed BitNet modules, and target-only recovered control heads.",
        "",
        "No binary tensor values were read. Direct loading remains blocked.",
        "",
        "Next: audit row completeness and target-key collisions before any converter implementation.",
        "",
    ]), encoding="utf-8")
    rows = [row for row in registry.get("rows", []) if row.get("stage_name") != NAME]
    rows.append({"stage": STAGE, "stage_name": NAME, "passed": card["passed"], "path": str(SUMMARY), "authority": AUTHORITY_CLOSED, "next_best_step": card["next_best_step"]})
    rows = sorted(rows, key=lambda row: (int(row.get("stage", -1)), row.get("stage_name", "")))
    registry["rows"] = rows
    registry["passed"] = card["passed"]
    registry["metrics"] = {**registry.get("metrics", {}), "latest_stage": STAGE, "latest_stage_name": NAME, "latest_stage_next_best_step": card["next_best_step"], "max_stage": STAGE, "registry_rows": len(rows), "authority_counts": {key: 0 for key in AUTHORITY_CLOSED}}
    REGISTRY.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    marker = "## Stage8916 Non-Executing Converter Shape Report Dry Run"
    spine_text = SPINE.read_text(encoding="utf-8") if SPINE.exists() else ""
    if marker not in spine_text:
        SPINE.write_text(spine_text.rstrip() + "\n\n" + marker + "\n\nStage8916 emits metadata-only shape rows for the AgentKernel Lite export. It does not decode packed BitNet weights, load a state dict, resize embeddings, execute, or train. Direct loading stays blocked pending row completeness and target-key collision audits.\n", encoding="utf-8")
    print(json.dumps(card, indent=2, sort_keys=True))
    raise SystemExit(0 if card["passed"] else 1)


if __name__ == "__main__":
    main()
