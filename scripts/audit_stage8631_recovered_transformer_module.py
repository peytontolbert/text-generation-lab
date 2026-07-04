#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "legacy_src" / "agentkernel_lite" / "modeling_transformer.py"
TARGET_CONFIG = ROOT / "configs" / "model" / "agentkernel_100m_seq2seq_recovered_target.json"
OUT_DIR = ROOT / "runs" / "local" / "artifacts" / "stage8631_recovered_transformer_module_audit"
SUMMARY_PATH = ROOT / "runs" / "summaries" / "stage8631_reconstructed_recovered_transformer_module_audit.json"
DOC_PATH = ROOT / "docs" / "RECOVERED_TRANSFORMER_MODULE_STAGE8631.md"

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

REQUIRED_MARKERS = {
    "transformer_config": "class AgentKernelLiteTransformerConfig",
    "transformer_model": "class AgentKernelLiteTransformerSeq2Seq",
    "rotary_embedding": "class RotaryEmbedding",
    "apply_rotary": "def apply_rotary",
    "scaled_dot_product_attention": "scaled_dot_product_attention",
    "encoder_layer": "class EncoderLayer",
    "decoder_layer": "class DecoderLayer",
    "cross_attention": "self.cross_attn",
    "retrieval_query_head": "retrieval_query_head",
    "retrieval_doc_head": "retrieval_doc_head",
    "agent_policy_heads": "agent_policy_heads",
    "agent_intent_head": "agent_intent_head",
    "structured_heads": "structured_heads",
    "decoder_ce_loss": "def decoder_ce_loss",
    "parameter_estimator": "def estimate_transformer_parameter_count",
}


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True))


def estimate_parameter_count(cfg: dict[str, Any], structured_dims: dict[str, int]) -> int:
    d_model = int(cfg["d_model"])
    d_ff = int(cfg["d_ff"])
    n_layers = int(cfg["n_layers"])
    vocab = int(cfg["vocab_size"])
    retrieval_dim = int(cfg.get("retrieval_head_dim") or 0)
    agent_intent_labels = int(cfg.get("agent_intent_labels") or 0)
    agent_controller_dim = int(cfg.get("agent_controller_dim") or 0)
    scalar_rank = int(cfg.get("scalar_invariant_rank") or 0)
    embed = vocab * d_model * 2
    encoder_layer = (4 * d_model * d_model) + (3 * d_model * d_ff) + (4 * d_model)
    decoder_layer = (8 * d_model * d_model) + (6 * d_model * d_ff) + (8 * d_model)
    norms = 4 * d_model
    retrieval = 2 * d_model * retrieval_dim if retrieval_dim else 0
    policy = 7 * (d_model + 1) if cfg.get("agent_policy_heads") else 0
    intent = (d_model + 1) * agent_intent_labels if agent_intent_labels else 0
    controller = (d_model + 1) * agent_controller_dim if agent_controller_dim else 0
    scalar = d_model * scalar_rank if scalar_rank else 0
    structured = sum((d_model + 1) * int(dim) for dim in structured_dims.values())
    return int(embed + n_layers * (encoder_layer + decoder_layer) + norms + retrieval + policy + intent + controller + scalar + structured)


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    text = MODULE.read_text()
    target = json.loads(TARGET_CONFIG.read_text())
    cfg = target["model_config"]
    marker_hits = {name: marker in text for name, marker in REQUIRED_MARKERS.items()}
    structured_dims = {
        "surface_role": 8,
        "repair_surface": 8,
        "action_label": 12,
        "evidence_state": 6,
        "decoder_budget_ok": 2,
        "decode_allowed": 2,
        "build_mode": 3,
        "allowed_import_policy": 4,
        "blocked_import_policy": 4,
        "repo_dependency_policy": 4,
        "action_sequence": 16,
        "file_plan": 8,
        "symbol_binding": 6,
        "edit_localization": 7,
        "patch_operator": 12,
        "verifier_repair": 9,
    }
    estimate = estimate_parameter_count(cfg, structured_dims)
    target_count = int(target["parameter_count"])
    ratio = estimate / target_count
    metrics = {
        "required_marker_count": len(REQUIRED_MARKERS),
        "required_marker_hits": sum(int(v) for v in marker_hits.values()),
        "missing_marker_count": sum(int(not v) for v in marker_hits.values()),
        "target_parameter_count": target_count,
        "estimated_local_transformer_parameter_count": estimate,
        "estimate_to_preserved_ratio": ratio,
        "target_d_model": int(cfg["d_model"]),
        "target_layers": int(cfg["n_layers"]),
        "target_heads": int(cfg["n_heads"]),
        "target_vocab_size": int(cfg["vocab_size"]),
    }
    missing = [name for name, ok in marker_hits.items() if not ok]
    audit = {
        "passed": not missing and 0.75 <= ratio <= 1.40,
        "authority": AUTHORITY_CLOSED,
        "metrics": metrics,
        "marker_hits": marker_hits,
        "missing_markers": missing,
        "module": str(MODULE.relative_to(ROOT)),
        "target_config": str(TARGET_CONFIG.relative_to(ROOT)),
        "interpretation": "Recovered local transformer/rotary module is now present for shape/interface audits. It remains non-executing until a later explicit probe authorization.",
    }
    write_json(OUT_DIR / "recovered_transformer_module_audit.json", audit)
    DOC_PATH.write_text(
        "\n".join(
            [
                "# Stage8631 Recovered Transformer Module Audit",
                "",
                "This stage records the local recovery of the transformer/rotary implementation needed for the 100M software-maintainer path. It does not authorize training or model execution.",
                "",
                "## What Was Recovered",
                "",
                "- local module: `legacy_src/agentkernel_lite/modeling_transformer.py`",
                "- transformer encoder/decoder stack with RoPE decoder self-attention",
                "- cross-attention decoder layers",
                "- structured-state heads for the recovered curriculum objectives",
                "- retrieval query/doc embedding heads",
                "- agent policy and intent heads",
                "- decoder CE loss helper with row mask support",
                "- target-config parameter-count estimator",
                "",
                "## Why This Matters",
                "",
                "Stage8629 proved the active model was only a GRU scaffold. Stage8630 found the preserved architecture boundary in `/data/transformer_10/runtime/seq2seq.py` plus transformer/rotary runtime modules. Stage8631 restores a local, auditable transformer module so the next step can be a non-executing shape and parameter-count audit.",
                "",
                "## Metrics",
                "",
                "```json",
                json.dumps(metrics, indent=2, sort_keys=True),
                "```",
                "",
                "## Still Closed",
                "",
                "Decoder CE, runtime, source/body emission, Gemma, harness/scoring, controller merge, and promotion remain closed.",
                "",
            ]
        )
    )
    summary = {
        "stage": 8631,
        "stage_name": "stage8631_reconstructed_recovered_transformer_module_audit",
        "passed": bool(audit["passed"]),
        "reconstructed": True,
        "authority": AUTHORITY_CLOSED,
        "metrics": metrics,
        "gates": {
            "transformer_module_present": True,
            "required_markers_present": not missing,
            "parameter_estimate_reasonable": 0.75 <= ratio <= 1.40,
            "model_execution_authorized": False,
            "decoder_ce_training_authorized": False,
            "authority_closed": True,
        },
        "artifacts": {
            "audit": str((OUT_DIR / "recovered_transformer_module_audit.json").relative_to(ROOT)),
            "doc": str(DOC_PATH.relative_to(ROOT)),
            "module": str(MODULE.relative_to(ROOT)),
        },
        "next_best_step": "Run a non-executing transformer shape/parameter-count audit with tiny instantiated dimensions and target-config static estimates, then integrate the module behind the safe trainer wrapper.",
    }
    write_json(SUMMARY_PATH, summary)
    print(json.dumps({"passed": audit["passed"], "metrics": metrics, "summary": str(SUMMARY_PATH)}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
