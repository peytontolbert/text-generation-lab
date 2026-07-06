#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = 8909
NAME = "stage8909_state_dict_shape_migration_design"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "STATE_DICT_SHAPE_MIGRATION_STAGE8909.md"
SPINE = ROOT / "docs" / "MODEL_STACK_SPINE.md"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
AUDIT = OUT_DIR / "state_dict_shape_migration_design.json"

EXPORT_ROOT = Path("/data/repository_library/exports/agent_kernel/models/agentkernel_lite_100m_bitnet_v11")
EXPORT_MANIFEST = EXPORT_ROOT / "manifest.json"
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

TARGET = {
    "vocab_size": 1506,
    "export_vocab_size": 8207,
    "d_model": 640,
    "d_ff": 2048,
    "n_layers": 6,
    "n_heads": 10,
    "retrieval_head_dim": 128,
    "agent_policy_heads": 7,
    "agent_intent_labels": 18,
    "agent_controller_dim": 128,
    "scalar_invariant_rank": 32,
    "structured_head_count": 16,
}


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def expected_recovered_key_families() -> dict[str, list[str]]:
    keys: dict[str, list[str]] = {
        "embedding_and_norm": [
            "enc_embed.weight",
            "dec_embed.weight",
            "enc_norm.weight",
            "enc_norm.bias",
            "dec_norm.weight",
            "dec_norm.bias",
            "lm_head.weight (tied to enc_embed.weight)",
        ],
        "extra_heads": [
            "retrieval_query_head.weight",
            "retrieval_doc_head.weight",
            "agent_policy_heads.*.weight/bias",
            "agent_intent_head.weight/bias",
            "agent_controller.weight/bias",
            "scalar_invariant.weight",
            "structured_heads.*.weight/bias",
        ],
    }
    encoder = []
    decoder = []
    for i in range(TARGET["n_layers"]):
        encoder.extend(
            [
                f"encoder.{i}.self_attn.q_proj.weight",
                f"encoder.{i}.self_attn.k_proj.weight",
                f"encoder.{i}.self_attn.v_proj.weight",
                f"encoder.{i}.self_attn.o_proj.weight",
                f"encoder.{i}.mlp.up_proj.weight",
                f"encoder.{i}.mlp.down_proj.weight",
                f"encoder.{i}.norm1.weight/bias",
                f"encoder.{i}.norm2.weight/bias",
            ]
        )
        decoder.extend(
            [
                f"decoder.{i}.self_attn.q_proj.weight",
                f"decoder.{i}.self_attn.k_proj.weight",
                f"decoder.{i}.self_attn.v_proj.weight",
                f"decoder.{i}.self_attn.o_proj.weight",
                f"decoder.{i}.self_mlp.up_proj.weight",
                f"decoder.{i}.self_mlp.down_proj.weight",
                f"decoder.{i}.cross_attn.q_proj.weight",
                f"decoder.{i}.cross_attn.k_proj.weight",
                f"decoder.{i}.cross_attn.v_proj.weight",
                f"decoder.{i}.cross_attn.o_proj.weight",
                f"decoder.{i}.cross_mlp.up_proj.weight",
                f"decoder.{i}.cross_mlp.down_proj.weight",
                f"decoder.{i}.norm1/2/3/4.weight/bias",
            ]
        )
    keys["encoder"] = encoder
    keys["decoder"] = decoder
    return keys


def export_inventory() -> dict[str, Any]:
    browser = load_json(BROWSER_EXPORT)
    manifest = load_json(EXPORT_MANIFEST)
    quant_modules = ((browser.get("quantization") or {}).get("modules") or []) if isinstance(browser.get("quantization"), dict) else []
    dense_files = sorted(p.name for p in (EXPORT_ROOT / "dense").glob("*") if p.is_file())
    layer_files = sorted(p.name for p in (EXPORT_ROOT / "layers").glob("*") if p.is_file())
    return {
        "export_root": str(EXPORT_ROOT),
        "manifest_exists": EXPORT_MANIFEST.exists(),
        "browser_export_exists": BROWSER_EXPORT.exists(),
        "format": browser.get("format") or manifest.get("format"),
        "parameter_count": ((manifest.get("agentkernel_lite") or {}).get("parameter_count")),
        "source_bundle_manifest_path": ((manifest.get("agentkernel_lite") or {}).get("source_bundle_manifest_path")),
        "source_model_dir": ((manifest.get("agentkernel_lite") or {}).get("source_model_dir")),
        "source_tokenizer_dir": ((manifest.get("agentkernel_lite") or {}).get("source_tokenizer_dir")),
        "quant_module_count": len(quant_modules),
        "dense_file_count": len(dense_files),
        "layer_file_count": len(layer_files),
        "dense_files": dense_files,
        "quant_modules_sample": quant_modules[:24],
        "has_learned_encoder_pos_embed": "enc_pos_embed_weight.f32.bin" in dense_files,
        "has_source_pytorch_checkpoint_path": False,
    }


def build_design() -> dict[str, Any]:
    inv = export_inventory()
    key_families = expected_recovered_key_families()
    blockers = [
        "browser_bitnet_export_has_packed_runtime_files_not_verified_pytorch_state_dict",
        "export_key_names_do_not_match_recovered_pytorch_module_names",
        "embedding_shapes_differ_due_to_vocab_8207_vs_target_1506",
        "export_contains_encoder_position_embedding_not_present_in_recovered_module",
        "current_recovered_control_heads_missing_from_export",
        "state_dict_loading_would_require_explicit_conversion_map_and_shape_report",
    ]
    migration_plan = [
        {
            "step": "inventory_source_checkpoint",
            "status": "required_before_loading",
            "detail": "Locate a real PyTorch state_dict/safetensors source, or write a no-execution converter spec for browser BitNet files.",
        },
        {
            "step": "tokenizer_decision",
            "status": "blocked_by_stage8908",
            "detail": "Either update recovered target vocab to 8207 with audited embedding/lm_head shapes, or keep vocab 1506 and do not reuse export embeddings.",
        },
        {
            "step": "key_mapping_table",
            "status": "required",
            "detail": "Map export names like encoder.0.attn.w_q to PyTorch names like encoder.0.self_attn.q_proj.weight.",
        },
        {
            "step": "head_policy",
            "status": "required",
            "detail": "Declare retrieval, policy, intent, controller, scalar, and structured heads as recovered, newly initialized, frozen, or disabled.",
        },
        {
            "step": "shape_report",
            "status": "required",
            "detail": "Emit per-key source shape, target shape, action, and initialization provenance before any model load.",
        },
    ]
    checks = {
        "export_inventory_present": inv["manifest_exists"] and inv["browser_export_exists"],
        "dimensionally_relevant": inv["parameter_count"] == 113507328,
        "has_quant_runtime_modules": inv["quant_module_count"] == 109,
        "has_dense_runtime_files": inv["dense_file_count"] >= 40,
        "has_pytorch_state_dict": inv["has_source_pytorch_checkpoint_path"],
        "direct_state_dict_load_safe": False,
        "requires_conversion_map": True,
        "requires_tokenizer_migration": True,
        "requires_new_head_policy": True,
    }
    return {
        "stage": STAGE,
        "stage_name": NAME,
        "target": TARGET,
        "export_inventory": inv,
        "expected_recovered_key_families": key_families,
        "checks": checks,
        "blockers": blockers,
        "migration_plan": migration_plan,
        "decision": {
            "direct_load_status": "blocked",
            "allowed_now": ["metadata_inventory", "conversion_plan_design", "shape_report_schema_design"],
            "forbidden_now": ["torch.load_export", "state_dict_load", "embedding_resize", "checkpoint_write", "training", "model_execution"],
        },
        "authority": AUTHORITY_CLOSED,
    }


def validate_design(design: dict[str, Any], registry: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    checks = design["checks"]
    if checks["export_inventory_present"] is not True:
        failures.append("export_inventory_missing")
    if checks["direct_state_dict_load_safe"] is True:
        failures.append("direct_state_dict_load_was_incorrectly_allowed")
    if checks["requires_conversion_map"] is not True:
        failures.append("missing_conversion_map_requirement")
    if checks["requires_tokenizer_migration"] is not True:
        failures.append("missing_tokenizer_migration_requirement")
    if checks["requires_new_head_policy"] is not True:
        failures.append("missing_new_head_policy_requirement")
    if len(design["blockers"]) < 5:
        failures.append("insufficient_direct_load_blockers")
    authority_counts = (registry.get("metrics") or {}).get("authority_counts") or {}
    if any(authority_counts.get(key, 0) != 0 for key in AUTHORITY_CLOSED):
        failures.append("registry_authority_counts_nonzero")
    latest = (registry.get("metrics") or {}).get("latest_stage")
    if latest not in {8908, STAGE}:
        failures.append(f"unexpected_registry_frontier:{latest}")
    return failures


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    registry = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    design = build_design()
    failures = validate_design(design, registry)
    AUDIT.write_text(json.dumps(design, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    card = {
        "stage": STAGE,
        "stage_name": NAME,
        "passed": not failures,
        "authority": AUTHORITY_CLOSED,
        "metrics": {
            **AUTHORITY_CLOSED,
            "authority_rows": 0,
            "failures": failures,
            "export_inventory_present": design["checks"]["export_inventory_present"],
            "quant_module_count": design["export_inventory"]["quant_module_count"],
            "dense_file_count": design["export_inventory"]["dense_file_count"],
            "direct_state_dict_load_safe": design["checks"]["direct_state_dict_load_safe"],
            "requires_conversion_map": design["checks"]["requires_conversion_map"],
            "requires_tokenizer_migration": design["checks"]["requires_tokenizer_migration"],
            "requires_new_head_policy": design["checks"]["requires_new_head_policy"],
            "blocker_count": len(design["blockers"]),
            "model_execution_authorized_now": False,
            "training_authorized": False,
            "decoder_ce_authorized": False,
            "denoise_ce_authorized": False,
            "runtime_authorized_flag": False,
            "data_mining_authorized": False,
            "download_authorized": False,
        },
        "artifacts": {"design": str(AUDIT.relative_to(ROOT))},
        "decision": "State-dict loading is blocked; the local export needs an explicit conversion map, tokenizer migration, and control-head policy before any seed loading." if not failures else "State-dict shape migration design failed.",
        "next_best_step": "Build a no-execution shape-report schema and conversion-map audit; still do not load weights, resize embeddings, execute models, or train.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage8909 State-Dict Shape Migration Design",
        "",
        f"Passed: `{card['passed']}`",
        "",
        "The local AgentKernel Lite artifact is a browser BitNet runtime export, not a verified PyTorch training checkpoint.",
        "",
        "Direct loading is blocked because export key names, tokenizer vocab, learned positional embedding presence, and recovered control heads do not match the recovered PyTorch target directly.",
        "",
        "Required before seed loading:",
        "",
        "- source checkpoint or converter inventory",
        "- explicit tokenizer/vocab migration decision",
        "- export-to-PyTorch key mapping table",
        "- per-key shape report",
        "- head policy for retrieval, policy, intent, controller, scalar, and structured heads",
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
    marker = "## Stage8909 State-Dict Shape Migration"
    spine_text = SPINE.read_text(encoding="utf-8") if SPINE.exists() else ""
    if marker not in spine_text:
        SPINE.write_text(spine_text.rstrip() + "\n\n" + "\n".join([
            marker,
            "",
            "Stage8909 blocks direct state-dict loading from the local AgentKernel Lite browser BitNet export. The export is dimensionally useful but needs tokenizer migration, export-to-PyTorch key mapping, per-key shape reporting, and explicit new-head initialization policy before any seed loading.",
            "",
        ]), encoding="utf-8")
    print(json.dumps(card, indent=2, sort_keys=True))
    raise SystemExit(0 if card["passed"] else 1)


if __name__ == "__main__":
    main()
