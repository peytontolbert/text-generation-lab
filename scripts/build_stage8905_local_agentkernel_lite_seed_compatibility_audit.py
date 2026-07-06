#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = 8905
NAME = "stage8905_local_agentkernel_lite_seed_compatibility_audit"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "LOCAL_AGENTKERNEL_LITE_SEED_COMPATIBILITY_STAGE8905.md"
SPINE = ROOT / "docs" / "MODEL_STACK_SPINE.md"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
AUDIT = OUT_DIR / "local_agentkernel_lite_seed_compatibility_audit.json"

LOCAL_EXPORT = Path("/data/repository_library/exports/agent_kernel/models/agentkernel_lite_100m_bitnet_v11")
EXPORT_MANIFEST = LOCAL_EXPORT / "agentkernel_lite_browser_bitnet_export.json"

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

RECOVERED_TARGET = {
    "model_family": "recovered_agentkernel_lite_transformer",
    "trainable_surface": "legacy_src/agentkernel_lite/modeling_transformer.py",
    "trainer_surface": "legacy_src/scripts/train_agentkernel_lite_encdec.py",
    "vocab_size": 1506,
    "d_model": 640,
    "d_ff": 2048,
    "n_layers": 6,
    "n_heads": 10,
    "pad_token_id": 0,
    "max_position_embeddings": 4096,
    "rope_theta": 1_000_000.0,
    "retrieval_head_dim": 128,
    "agent_policy_heads": True,
    "structured_heads_required": [
        "surface_role",
        "repair_surface",
        "action_label",
        "evidence_state",
        "decoder_budget_ok",
        "decode_allowed",
        "build_mode",
        "allowed_import_policy",
        "blocked_import_policy",
        "repo_dependency_policy",
        "action_sequence",
        "file_plan",
        "symbol_binding",
        "edit_localization",
        "patch_operator",
        "verifier_repair",
    ],
}


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def summarize_export(manifest: dict[str, Any]) -> dict[str, Any]:
    model = manifest.get("model") if isinstance(manifest.get("model"), dict) else {}
    tokenizer = manifest.get("tokenizer") if isinstance(manifest.get("tokenizer"), dict) else {}
    quant = manifest.get("quantization") if isinstance(manifest.get("quantization"), dict) else {}
    return {
        "path": str(LOCAL_EXPORT),
        "manifest_path": str(EXPORT_MANIFEST),
        "exists": LOCAL_EXPORT.exists(),
        "manifest_exists": EXPORT_MANIFEST.exists(),
        "artifact_kind": manifest.get("artifact_kind"),
        "format": manifest.get("format"),
        "size_bytes": manifest.get("size_bytes"),
        "layer_count": manifest.get("layer_count"),
        "source_bundle_manifest_path": manifest.get("source_bundle_manifest_path"),
        "source_model_dir": manifest.get("source_model_dir"),
        "source_tokenizer_dir": manifest.get("source_tokenizer_dir"),
        "webapp_model_dir": manifest.get("webapp_model_dir"),
        "model": {
            "vocab_size": model.get("vocab_size"),
            "d_model": model.get("d_model"),
            "d_ff": model.get("d_ff"),
            "n_layers": model.get("n_layers"),
            "n_heads": model.get("n_heads"),
            "pad_token_id": model.get("pad_token_id"),
            "max_position_embeddings": model.get("max_position_embeddings"),
            "rope_theta": model.get("rope_theta"),
            "positional": model.get("positional"),
            "retrieval_head_dim": model.get("retrieval_head_dim"),
            "agent_policy_heads": model.get("agent_policy_heads"),
        },
        "tokenizer": {
            "kind": tokenizer.get("kind"),
            "source_kind": tokenizer.get("source_kind"),
            "vocab_size": tokenizer.get("vocab_size"),
            "pad_token_id": tokenizer.get("pad_token_id"),
            "bos_token_id": tokenizer.get("bos_token_id"),
            "eos_token_id": tokenizer.get("eos_token_id"),
            "unk_token_id": tokenizer.get("unk_token_id"),
        },
        "quantization": {
            "scheme": quant.get("scheme"),
            "num": quant.get("num"),
            "activation_quant": quant.get("activation_quant"),
        },
    }


def compatibility_checks(export: dict[str, Any]) -> dict[str, Any]:
    model = export["model"]
    tokenizer = export["tokenizer"]
    return {
        "local_export_present": export["exists"] and export["manifest_exists"],
        "same_d_model": model.get("d_model") == RECOVERED_TARGET["d_model"],
        "same_d_ff": model.get("d_ff") == RECOVERED_TARGET["d_ff"],
        "same_layer_count": model.get("n_layers") == RECOVERED_TARGET["n_layers"],
        "same_attention_heads": model.get("n_heads") == RECOVERED_TARGET["n_heads"],
        "same_position_limit": model.get("max_position_embeddings") == RECOVERED_TARGET["max_position_embeddings"],
        "same_rope_theta": float(model.get("rope_theta") or 0.0) == RECOVERED_TARGET["rope_theta"],
        "same_pad_token": tokenizer.get("pad_token_id") == RECOVERED_TARGET["pad_token_id"],
        "vocab_matches_recovered_target": tokenizer.get("vocab_size") == RECOVERED_TARGET["vocab_size"],
        "export_has_retrieval_head": model.get("retrieval_head_dim") == RECOVERED_TARGET["retrieval_head_dim"],
        "export_has_agent_policy_heads": model.get("agent_policy_heads") is True,
        "is_browser_bitnet_export": export.get("format") == "model-stack-browser-bitnet",
        "has_pytorch_state_dict": False,
        "safe_to_directly_initialize_training": False,
    }


def build_audit() -> dict[str, Any]:
    manifest = load_json(EXPORT_MANIFEST)
    export = summarize_export(manifest)
    checks = compatibility_checks(export)
    blockers = []
    if not checks["local_export_present"]:
        blockers.append("local_export_or_manifest_missing")
    if not checks["vocab_matches_recovered_target"]:
        blockers.append("tokenizer_vocab_mismatch_requires_explicit_vocab_resize_or_matching_tokenizer")
    if not checks["export_has_retrieval_head"]:
        blockers.append("retrieval_head_missing_for_current_100m_control_surface")
    if not checks["export_has_agent_policy_heads"]:
        blockers.append("agent_policy_heads_missing_for_current_control_surface")
    if checks["is_browser_bitnet_export"]:
        blockers.append("browser_bitnet_runtime_export_not_direct_pytorch_training_checkpoint")
    if not checks["has_pytorch_state_dict"]:
        blockers.append("no_verified_pytorch_state_dict_for_trainer_loading")
    return {
        "stage": STAGE,
        "stage_name": NAME,
        "recovered_target": RECOVERED_TARGET,
        "local_export": export,
        "checks": checks,
        "blockers": blockers,
        "decision": {
            "direct_training_seed_status": "blocked_pending_conversion_plan",
            "allowed_use_now": [
                "architecture_lineage_reference",
                "tokenizer_special_token_lineage_reference",
                "browser_runtime_export_reference",
                "teacher/tool candidate only after separate no-execution registration",
            ],
            "required_before_seed_loading": [
                "match tokenizer/vocab or define audited resize mapping",
                "recover or convert a PyTorch-compatible state dict",
                "decide whether retrieval and policy heads are newly initialized or recovered",
                "run state-dict key/shape audit without training",
                "run tokenizer special-token compatibility audit",
                "keep decoder CE/training/runtime closed until explicit one-run authorization",
            ],
        },
        "authority": AUTHORITY_CLOSED,
    }


def validate_audit(audit: dict[str, Any], registry: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    checks = audit["checks"]
    if not checks["local_export_present"]:
        failures.append("local_export_missing")
    for key in ["same_d_model", "same_d_ff", "same_layer_count", "same_attention_heads", "same_position_limit", "same_rope_theta", "same_pad_token"]:
        if checks.get(key) is not True:
            failures.append(f"expected_compatible_{key}_false")
    if checks["safe_to_directly_initialize_training"] is True:
        failures.append("direct_training_seed_was_incorrectly_allowed")
    if not audit["blockers"]:
        failures.append("missing_direct_seed_blockers")
    authority_counts = (registry.get("metrics") or {}).get("authority_counts") or {}
    if any(authority_counts.get(key, 0) != 0 for key in AUTHORITY_CLOSED):
        failures.append("registry_authority_counts_nonzero")
    latest = (registry.get("metrics") or {}).get("latest_stage")
    if latest not in {8904, STAGE}:
        failures.append(f"unexpected_registry_frontier:{latest}")
    return failures


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    registry = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    audit = build_audit()
    failures = validate_audit(audit, registry)
    AUDIT.write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    card = {
        "stage": STAGE,
        "stage_name": NAME,
        "passed": not failures,
        "authority": AUTHORITY_CLOSED,
        "metrics": {
            **AUTHORITY_CLOSED,
            "authority_rows": 0,
            "failures": failures,
            "local_export_present": audit["checks"]["local_export_present"],
            "dimension_compatible_core": all(audit["checks"][key] for key in ["same_d_model", "same_d_ff", "same_layer_count", "same_attention_heads"]),
            "vocab_matches_recovered_target": audit["checks"]["vocab_matches_recovered_target"],
            "safe_to_directly_initialize_training": audit["checks"]["safe_to_directly_initialize_training"],
            "blocker_count": len(audit["blockers"]),
            "model_execution_authorized_now": False,
            "training_authorized": False,
            "decoder_ce_authorized": False,
            "denoise_ce_authorized": False,
            "runtime_authorized_flag": False,
            "data_mining_authorized": False,
            "download_authorized": False,
        },
        "artifacts": {"audit": str(AUDIT.relative_to(ROOT))},
        "decision": "Local AgentKernel Lite export is dimensionally useful but blocked as a direct training seed until tokenizer/state-dict/head compatibility is explicitly solved." if not failures else "Local AgentKernel Lite seed compatibility audit failed.",
        "next_best_step": "Build tokenizer/special-token compatibility and state-dict shape audit plans before any seed loading. Keep model execution and training closed.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage8905 Local AgentKernel Lite Seed Compatibility Audit",
        "",
        f"Passed: `{card['passed']}`",
        "",
        "This is a no-execution compatibility audit over the local AgentKernel Lite browser BitNet export.",
        "",
        "Finding: the export matches the recovered target on major dimensions (`d_model=640`, `d_ff=2048`, 6 layers, 10 heads, 4096 positions, RoPE theta 1e6), but it is not directly trainable in the recovered PyTorch trainer as-is.",
        "",
        "Primary blockers:",
        "",
        "- tokenizer/vocab mismatch: local export vocab is 8207 while the recovered target default is 1506",
        "- retrieval and agent policy heads are absent in the export metadata but expected in the current recovered control surface",
        "- the artifact is a browser BitNet runtime export, not a verified PyTorch training checkpoint",
        "- no state-dict key/shape mapping has been audited",
        "",
        "Allowed use now: lineage/reference only. Do not load, train, resize, convert, or execute it until the next audits are built and passed.",
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
    marker = "## Stage8905 Local AgentKernel Lite Seed Compatibility"
    spine_text = SPINE.read_text(encoding="utf-8") if SPINE.exists() else ""
    if marker not in spine_text:
        SPINE.write_text(spine_text.rstrip() + "\n\n" + "\n".join([
            marker,
            "",
            "Stage8905 audits the local AgentKernel Lite browser BitNet export as a possible 100M seed. It is dimensionally relevant, but blocked as a direct training seed because tokenizer/vocab, state-dict, and missing control-head compatibility are not solved. Treat it as lineage/reference until tokenizer and state-dict shape audits pass.",
            "",
        ]), encoding="utf-8")
    print(json.dumps(card, indent=2, sort_keys=True))
    raise SystemExit(0 if card["passed"] else 1)


if __name__ == "__main__":
    main()
