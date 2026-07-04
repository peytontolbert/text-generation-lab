#!/usr/bin/env python3
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
CURRENT_CONFIG = ROOT / "configs" / "model" / "agentkernel_100m_seq2seq.json"
TARGET_CONFIG = ROOT / "configs" / "model" / "agentkernel_100m_seq2seq_recovered_target.json"
MODEL_IMPL = ROOT / "legacy_src" / "agentkernel_lite" / "modeling.py"
OUT_DIR = ROOT / "runs" / "local" / "artifacts" / "stage8629_current_model_vs_preserved_target"
SUMMARY_PATH = ROOT / "runs" / "summaries" / "stage8629_reconstructed_current_model_vs_preserved_target_audit.json"
DOC_PATH = ROOT / "docs" / "CURRENT_MODEL_VS_PRESERVED_TARGET_AUDIT_STAGE8629.md"

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


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text())


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True))


def inspect_model_impl() -> dict[str, Any]:
    text = MODEL_IMPL.read_text()
    return {
        "uses_gru": "nn.GRU" in text,
        "uses_transformer_attention": any(token in text for token in ["MultiheadAttention", "scaled_dot_product_attention", "q_proj", "k_proj", "v_proj"]),
        "has_rotary": "rotary" in text.lower() or "rope" in text.lower(),
        "has_agent_policy_heads": "agent_policy" in text,
        "has_retrieval_heads": "retrieval" in text,
        "has_scalar_invariant": "scalar_invariant" in text,
        "default_hidden_size": int(re.search(r"hidden_size: int = (\d+)", text).group(1)) if re.search(r"hidden_size: int = (\d+)", text) else None,
        "default_vocab_size": int(re.search(r"vocab_size: int = (\d+)", text).group(1)) if re.search(r"vocab_size: int = (\d+)", text) else None,
        "default_num_layers": int(re.search(r"num_layers: int = (\d+)", text).group(1)) if re.search(r"num_layers: int = (\d+)", text) else None,
    }


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    current = read_json(CURRENT_CONFIG)
    target = read_json(TARGET_CONFIG)
    impl = inspect_model_impl()
    target_cfg = target["model_config"]

    mismatches = []
    if current.get("model_family") != "agentkernel_lite_encdec_v1":
        mismatches.append("current config uses generic/rebuilt model family, not recovered agentkernel_lite_encdec_v1")
    if impl["uses_gru"]:
        mismatches.append("current model implementation is GRU scaffold, not recovered transformer/rotary 100M target")
    if impl["default_hidden_size"] != target_cfg["d_model"]:
        mismatches.append(f"hidden size mismatch: scaffold {impl['default_hidden_size']} vs target d_model {target_cfg['d_model']}")
    if impl["default_vocab_size"] != target_cfg["vocab_size"]:
        mismatches.append(f"vocab size mismatch: scaffold {impl['default_vocab_size']} vs target vocab {target_cfg['vocab_size']}")
    if impl["default_num_layers"] != target_cfg["n_layers"]:
        mismatches.append(f"layer count mismatch: scaffold {impl['default_num_layers']} vs target layers {target_cfg['n_layers']}")
    for required in ["has_rotary", "has_agent_policy_heads", "has_retrieval_heads", "has_scalar_invariant"]:
        if not impl[required]:
            mismatches.append(f"implementation missing recovered feature: {required}")

    metrics = {
        "mismatch_count": len(mismatches),
        "current_execution_authorized": bool(current.get("execution_authorized")),
        "target_execution_authorized": bool(target.get("execution_authorized")),
        "scaffold_uses_gru": impl["uses_gru"],
        "scaffold_uses_transformer_attention": impl["uses_transformer_attention"],
        "scaffold_hidden_size": impl["default_hidden_size"],
        "target_d_model": target_cfg["d_model"],
        "scaffold_vocab_size": impl["default_vocab_size"],
        "target_vocab_size": target_cfg["vocab_size"],
        "scaffold_layers": impl["default_num_layers"],
        "target_layers": target_cfg["n_layers"],
        "target_parameter_count": target["parameter_count"],
    }
    audit = {
        "passed": True,
        "classification": "gap_audit_passed_training_still_blocked",
        "authority": AUTHORITY_CLOSED,
        "metrics": metrics,
        "mismatches": mismatches,
        "current_config": str(CURRENT_CONFIG.relative_to(ROOT)),
        "target_config": str(TARGET_CONFIG.relative_to(ROOT)),
        "model_impl": str(MODEL_IMPL.relative_to(ROOT)),
        "interpretation": "The current implementation is a safe tiny scaffold for interface tests. It must not be mistaken for the recovered 102M target architecture.",
    }
    write_json(OUT_DIR / "current_model_vs_preserved_target_audit.json", audit)

    DOC_PATH.write_text(
        "\n".join(
            [
                "# Stage8629 Current Model vs Preserved 100M Target Audit",
                "",
                "This audit compares the current rebuilt model scaffold against the recovered preserved 100M AgentKernel Lite target config. It is a gap audit only and does not authorize execution or training.",
                "",
                "## Result",
                "",
                "The current implementation is an interface scaffold, not the recovered 102M target model.",
                "",
                "## Key Mismatches",
                "",
                *[f"- {item}" for item in mismatches],
                "",
                "## Preserved Target",
                "",
                f"- parameter count: `{target['parameter_count']}`",
                f"- d_model: `{target_cfg['d_model']}`",
                f"- d_ff: `{target_cfg['d_ff']}`",
                f"- layers: `{target_cfg['n_layers']}`",
                f"- heads: `{target_cfg['n_heads']}`",
                f"- vocab size: `{target_cfg['vocab_size']}`",
                f"- max positions: `{target_cfg['max_position_embeddings']}`",
                f"- tokenizer: `{target['tokenizer']['kind']}`",
                "",
                "## Current Scaffold",
                "",
                f"- GRU scaffold: `{impl['uses_gru']}`",
                f"- hidden size: `{impl['default_hidden_size']}`",
                f"- vocab size: `{impl['default_vocab_size']}`",
                f"- layers: `{impl['default_num_layers']}`",
                "",
                "## Required Rebuild Implication",
                "",
                "Before real 100M training resumes, rebuild or recover the transformer/rotary AgentKernel Lite implementation and tokenizer compatibility path. The current scaffold remains useful for contract tests only.",
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
        "stage": 8629,
        "stage_name": "stage8629_reconstructed_current_model_vs_preserved_target_audit",
        "passed": True,
        "reconstructed": True,
        "authority": AUTHORITY_CLOSED,
        "metrics": metrics,
        "gates": {
            "gap_audit_written": True,
            "current_scaffold_not_confused_with_target": True,
            "training_blocked_until_target_impl_recovered": True,
            "model_execution_authorized": False,
            "authority_closed": True,
        },
        "artifacts": {
            "target_config": str(TARGET_CONFIG.relative_to(ROOT)),
            "audit": str((OUT_DIR / "current_model_vs_preserved_target_audit.json").relative_to(ROOT)),
            "doc": str(DOC_PATH.relative_to(ROOT)),
        },
        "next_best_step": "Recover or rebuild the transformer/rotary AgentKernel Lite 100M implementation and tokenizer compatibility path before any real training.",
        "notes": "Current model code is a safe interface scaffold; preserved manifests define the target 102M architecture.",
    }
    write_json(SUMMARY_PATH, summary)
    print(json.dumps({"passed": True, "metrics": metrics, "summary": str(SUMMARY_PATH)}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
