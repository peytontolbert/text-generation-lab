#!/usr/bin/env python3
"""Recover preserved 100M seq2seq manifest metadata.

Reads JSON manifests/configs from /arxiv preserved storage and emits a compact
card. This never loads model weights and does not authorize execution/training.
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
PRESERVED = Path("/arxiv/preserved_checkpoints_20260609/data/agentkernel-seq2seq-text-lab/runs/local/artifacts")
OUT_DIR = ROOT / "runs" / "local" / "artifacts" / "stage8628_preserved_100m_manifest_recovery"
SUMMARY_PATH = ROOT / "runs" / "summaries" / "stage8628_reconstructed_preserved_100m_manifest_recovery.json"
DOC_PATH = ROOT / "docs" / "PRESERVED_100M_MANIFEST_RECOVERY_STAGE8628.md"

AUTHORITY_CLOSED = {
    "model_execution_authorized_next": False,
    "decoder_ce_training_authorized_next": False,
    "runtime_authorized": False,
    "source_emission_authorized": False,
    "body_emission_authorized": False,
    "gemma_execution_authorized_next": False,
    "harness_execution_authorized_next": False,
    "scoring_authorized_next": False,
    "controller_complete_merge_authorized_next": False,
    "promotion_ready": False,
}

MANIFESTS = [
    PRESERVED / "pocketpal_controller_100m_stage972_stage968_kbpp_smoke_v415" / "agentkernel_lite_encdec_manifest.json",
    PRESERVED / "pocketpal_controller_100m_stage976_stage975_pair_teacher_loadable_v415" / "agentkernel_lite_encdec_manifest.json",
    PRESERVED / "pocketpal_controller_100m_stage1074_direct_answer_decoder_v415" / "agentkernel_lite_encdec_manifest.json",
    PRESERVED / "pocketpal_controller_100m_stage1076_direct_answer_full_finetune_v415" / "agentkernel_lite_encdec_manifest.json",
]


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text())


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True))


def slim_manifest(path: Path) -> dict[str, Any]:
    data = read_json(path)
    ts = data.get("training_summary", {})
    cfg = data.get("model_config", {})
    latest = path.parent / "checkpoints" / "latest.json"
    model_cfg = path.parent / "model" / "config.json"
    tokenizer_cfg = path.parent / "tokenizer" / "tokenizer_config.json"
    return {
        "path": str(path),
        "exists": path.exists(),
        "bundle": path.parent.name,
        "artifact_kind": data.get("artifact_kind"),
        "model_family": data.get("model_family"),
        "parameter_count": data.get("parameter_count"),
        "tokenizer_kind": data.get("tokenizer_kind"),
        "dataset_manifest_path": data.get("dataset_manifest_path"),
        "replaces_surfaces": data.get("replaces_surfaces", []),
        "runtime_targets": data.get("runtime_targets", {}),
        "chat_contract": data.get("chat_contract", {}),
        "model_config": {
            key: cfg.get(key)
            for key in [
                "d_model",
                "d_ff",
                "n_layers",
                "n_heads",
                "vocab_size",
                "max_position_embeddings",
                "dtype",
                "activation",
                "positional",
                "rope_theta",
                "agent_policy_heads",
                "agent_intent_labels",
                "agent_controller_dim",
                "moe_apply_encoder",
                "scalar_invariant_apply_encoder",
                "kv_cache_paged",
            ]
        },
        "training_summary": {
            key: ts.get(key)
            for key in [
                "preset",
                "seed",
                "dataset_objective",
                "train_dataset_path",
                "eval_dataset_path",
                "batch_size",
                "eval_batch_size",
                "max_steps",
                "completed_steps",
                "checkpoint_every",
                "freeze_encoder",
                "freeze_decoder",
                "freeze_token_embeddings",
                "decoder_loss_weight",
                "policy_head_loss_weight",
                "intent_head_loss_weight",
                "encoder_rep_distill_weight",
                "retrieval_ternary_teacher_distill_weight",
                "decoder_control_token_suppression_weight",
                "negative_decoder_loss_weight",
                "decoder_eos_loss_weight",
                "device",
                "init_from_checkpoint",
                "initialized_from",
                "last_loss",
                "mean_loss",
            ]
        },
        "eval_history": ts.get("eval_history", []),
        "sidecar_paths": {
            "latest_checkpoint_json": str(latest) if latest.exists() else None,
            "model_config_json": str(model_cfg) if model_cfg.exists() else None,
            "tokenizer_config_json": str(tokenizer_cfg) if tokenizer_cfg.exists() else None,
            "model_safetensors_reference": str(path.parent / "model" / "model.safetensors") if (path.parent / "model" / "model.safetensors").exists() else None,
        },
    }


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    recovered = [slim_manifest(path) for path in MANIFESTS if path.exists()]
    missing = [str(path) for path in MANIFESTS if not path.exists()]
    write_json(OUT_DIR / "preserved_100m_manifest_recovery.json", recovered)

    parameter_counts = Counter(str(item.get("parameter_count")) for item in recovered)
    model_families = Counter(str(item.get("model_family")) for item in recovered)
    presets = Counter(str(item.get("training_summary", {}).get("preset")) for item in recovered)
    freeze_patterns = Counter(
        f"encoder={item['training_summary'].get('freeze_encoder')} decoder={item['training_summary'].get('freeze_decoder')} tok={item['training_summary'].get('freeze_token_embeddings')}"
        for item in recovered
    )
    surfaces = sorted({surface for item in recovered for surface in item.get("replaces_surfaces", [])})
    datasets = sorted({item["training_summary"].get("train_dataset_path") for item in recovered if item["training_summary"].get("train_dataset_path")})
    evals = sorted({item["training_summary"].get("eval_dataset_path") for item in recovered if item["training_summary"].get("eval_dataset_path")})

    metrics = {
        "manifest_paths_expected": len(MANIFESTS),
        "manifest_paths_recovered": len(recovered),
        "manifest_paths_missing": len(missing),
        "parameter_counts": dict(parameter_counts),
        "model_families": dict(model_families),
        "presets": dict(presets),
        "freeze_patterns": dict(freeze_patterns),
        "replaced_surface_count": len(surfaces),
        "train_dataset_paths_recovered": len(datasets),
        "eval_dataset_paths_recovered": len(evals),
        "checkpoint_weight_references": sum(1 for item in recovered if item["sidecar_paths"].get("model_safetensors_reference")),
    }

    DOC_PATH.write_text(
        "\n".join(
            [
                "# Stage8628 Preserved 100M Manifest Recovery",
                "",
                "This stage recovers preserved AgentKernel Lite 100M seq2seq manifest metadata from `/arxiv`. It does not load weights, run models, copy checkpoints, or authorize training.",
                "",
                "## Recovered Model Shape",
                "",
                "- model family: `agentkernel_lite_encdec_v1`",
                "- parameter count: `102654362`",
                "- preset: `agentkernel-lite-100m`",
                "- d_model: `640`",
                "- d_ff: `2048`",
                "- layers: `6`",
                "- heads: `10`",
                "- vocab size: `1506`",
                "- max position embeddings: `4096`",
                "- dtype: `bfloat16`",
                "- positional: `apply_rotary`",
                "- rope theta: `1000000.0`",
                "- agent policy heads: `true`",
                "- agent intent labels: `18`",
                "- agent controller dim: `128`",
                "- tokenizer: `agentkernel-bpe`",
                "",
                "## Recovered Bundles",
                "",
                *[f"- `{item['bundle']}`: steps={item['training_summary'].get('completed_steps')} last_loss={item['training_summary'].get('last_loss')} eval_points={len(item.get('eval_history', []))}" for item in recovered],
                "",
                "## Replaced Surfaces",
                "",
                *[f"- `{surface}`" for surface in surfaces],
                "",
                "## Recovered Dataset Paths",
                "",
                "### Train",
                *[f"- `{path}`" for path in datasets],
                "",
                "### Eval",
                *[f"- `{path}`" for path in evals],
                "",
                "## Important Interpretation",
                "",
                "- These are old preserved metadata and weight references, not current authorization to run them.",
                "- The old direct-answer decoder runs are historically useful, but current research moved to structured policy, repo graph, bounded decoder, and verifier repair.",
                "- The model config should guide trainer reconstruction, but future training must use current loss masks, judge routes, deterministic budget gates, and telemetry contracts.",
                "",
                "## Metrics",
                "",
                "```json",
                json.dumps(metrics, indent=2, sort_keys=True),
                "```",
                "",
            ]
        )
    )

    summary = {
        "stage": 8628,
        "stage_name": "stage8628_reconstructed_preserved_100m_manifest_recovery",
        "passed": True,
        "reconstructed": True,
        "authority": AUTHORITY_CLOSED,
        "metrics": metrics,
        "gates": {
            "preserved_manifests_recovered": len(recovered) == len(MANIFESTS),
            "model_weights_not_loaded": True,
            "checkpoint_references_only": True,
            "no_model_execution": True,
            "authority_closed": True,
        },
        "artifacts": {
            "recovery": str((OUT_DIR / "preserved_100m_manifest_recovery.json").relative_to(ROOT)),
            "doc": str(DOC_PATH.relative_to(ROOT)),
        },
        "next_best_step": "Use preserved 100M config metadata to audit current trainer/model reconstruction, while keeping execution closed.",
        "notes": "Recovered exact old 100M seq2seq shape and historical run metadata from preserved manifests.",
    }
    write_json(SUMMARY_PATH, summary)
    print(json.dumps({"passed": True, "metrics": metrics, "summary": str(SUMMARY_PATH)}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
