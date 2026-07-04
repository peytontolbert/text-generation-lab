#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "runs" / "local" / "artifacts" / "stage8630_external_implementation_recovery_inventory"
SUMMARY_PATH = ROOT / "runs" / "summaries" / "stage8630_reconstructed_external_implementation_recovery_inventory.json"
DOC_PATH = ROOT / "docs" / "EXTERNAL_IMPLEMENTATION_RECOVERY_INVENTORY_STAGE8630.md"
TARGET_CONFIG = ROOT / "configs" / "model" / "agentkernel_100m_seq2seq_recovered_target.json"

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

CANDIDATE_PATHS = [
    "/data/transformer_10/runtime/seq2seq.py",
    "/data/transformer_10/runtime/block_modules.py",
    "/data/transformer_10/runtime/blocks.py",
    "/data/transformer_10/runtime/attention_modules.py",
    "/data/transformer_10/runtime/attention_factory.py",
    "/data/transformer_10/runtime/attention.py",
    "/data/transformer_10/runtime/positional.py",
    "/data/transformer_10/tensor/positional.py",
    "/data/transformer_10/tensor/masking.py",
    "/data/transformer_10/tensor/mlp.py",
    "/data/transformer_10/tensor/norms.py",
    "/data/transformer_10/specs/config.py",
    "/data/agent_kernel_lite/scripts/train_agentkernel_lite_encdec.py",
    "/data/agentkernel/scripts/train_agentkernel_lite_encdec.py",
    "/data/transformer_10/scripts/agent_kernel_lite/train_agentkernel_lite_encdec.py",
    "/data/transformer_10/model/seq2seq.py",
    "/data/transformer_10/model/heads.py",
    "/data/transformer_10/model/encoder.py",
    "/data/transformer_10/model/causal.py",
    "/data/agent_kernel_lite/scripts/build_agentkernel_lite_encdec_dataset.py",
    "/data/transformer_10/scripts/agent_kernel_lite/build_agentkernel_lite_encdec_dataset.py",
    "/data/transformer_10/scripts/agent_kernel_lite/pocketpal_structured_decode.py",
    "/data/transformer_10/scripts/agent_kernel_lite/pocketpal_content_operators.py",
    "/data/transformer_10/scripts/agent_kernel_lite/pocketpal_source_slots.py",
    "/data/transformer_10/scripts/agent_kernel_lite/build_pocketpal_stage50_source_binding_curriculum.py",
    "/data/transformer_10/scripts/agent_kernel_lite/build_pocketpal_stage51_local_agentkernel_trace_curriculum.py",
    "/data/transformer_10/scripts/agent_kernel_lite/build_pocketpal_stage52_counterfactual_slot_transform_curriculum.py",
    "/data/transformer_10/scripts/agent_kernel_lite/build_pocketpal_stage53_operator_distill_curriculum.py",
    "/data/transformer_10/scripts/agent_kernel_lite/build_pocketpal_stage54_world_compression_curriculum.py",
    "/data/transformer_10/scripts/agent_kernel_lite/build_pocketpal_stage55_state_retrieval_curriculum.py",
    "/data/transformer_10/scripts/agent_kernel_lite/build_pocketpal_stage61_slot_operator_curriculum.py",
    "/data/transformer_10/scripts/agent_kernel_lite/build_pocketpal_stage63_routing_boundary_curriculum.py",
    "/data/transformer_10/scripts/agent_kernel_lite/build_pocketpal_v202_hybrid_controller_operator_dataset.py",
    "/data/transformer_10/scripts/agent_kernel_lite/build_pocketpal_v203_decoder_failure_replay.py",
    "/data/transformer_10/scripts/agent_kernel_lite/diagnose_pocketpal_decoder_collapse.py",
    "/data/transformer_10/scripts/agent_kernel_lite/filter_pocketpal_decoder_attractors.py",
]

REQUIRED_STAGE8580_FLAGS = [
    "--cleanup-checkpoints-after-probe",
    "--decoder-ce-weight",
    "--denoise-weight",
    "--manifest",
    "--max-strict-rows",
    "--mode",
    "--no-final-checkpoint-export",
    "--require-loss-mask-enforcement-audit",
    "--structured-aux-weight",
]

MARKERS = {
    "config_class": [r"class\s+AgentKernelLiteConfig"],
    "model_class": [r"class\s+AgentKernelLiteSeq2Seq", r"class\s+.*Seq2Seq"],
    "transformer_attention": [
        r"MultiheadAttention",
        r"scaled_dot_product_attention",
        r"\bq_proj\b",
        r"\bk_proj\b",
        r"\bv_proj\b",
        r"attention_scores",
    ],
    "rotary_or_rope": [r"apply_rotary", r"rotary", r"rope", r"rope_theta"],
    "agent_policy_heads": [r"agent_policy", r"policy_head", r"intent_head"],
    "retrieval_heads": [r"retrieval", r"retrieve"],
    "scalar_invariant": [r"scalar_invariant", r"scalar"],
    "safe_softmax": [r"safe_softmax"],
    "causal_mask": [r"causal_mask", r"build_causal_mask"],
    "loss_mask": [r"loss_mask", r"losses_enabled", r"decoder_ce"],
    "structured_aux": [r"structured_aux", r"structured_head", r"field_targets"],
    "bpe_tokenizer": [r"agentkernel-bpe", r"tokenizer", r"vocab_size"],
    "stage8580_flags": [re.escape(flag) for flag in REQUIRED_STAGE8580_FLAGS],
}


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest()


def read_text(path: Path) -> str | None:
    try:
        return path.read_text(errors="replace")
    except (FileNotFoundError, PermissionError, OSError):
        return None


def line_numbers_for_patterns(text: str, patterns: list[str], limit: int = 12) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    lines = text.splitlines()
    for i, line in enumerate(lines, start=1):
        for pattern in patterns:
            if re.search(pattern, line, flags=re.IGNORECASE):
                out.append({"line": i, "text": line.strip()[:220]})
                break
        if len(out) >= limit:
            break
    return out


def inspect_candidate(path_str: str) -> dict[str, Any]:
    path = Path(path_str)
    text = read_text(path)
    if text is None:
        return {
            "path": path_str,
            "exists": False,
            "readable": False,
            "line_count": 0,
            "sha256": None,
            "marker_hits": {},
            "marker_hit_count": 0,
            "required_stage8580_flags_present": [],
            "required_stage8580_flags_missing": REQUIRED_STAGE8580_FLAGS,
            "score": 0,
        }

    marker_hits: dict[str, bool] = {}
    marker_lines: dict[str, list[dict[str, Any]]] = {}
    for name, patterns in MARKERS.items():
        hit = any(re.search(pattern, text, flags=re.IGNORECASE) for pattern in patterns)
        marker_hits[name] = hit
        if hit:
            marker_lines[name] = line_numbers_for_patterns(text, patterns)

    present_flags = [flag for flag in REQUIRED_STAGE8580_FLAGS if flag in text]
    missing_flags = [flag for flag in REQUIRED_STAGE8580_FLAGS if flag not in text]

    architecture_score = sum(
        int(marker_hits[name])
        for name in [
            "config_class",
            "model_class",
            "transformer_attention",
            "rotary_or_rope",
            "agent_policy_heads",
            "retrieval_heads",
            "scalar_invariant",
            "safe_softmax",
            "causal_mask",
        ]
    )
    trainer_score = len(present_flags) + sum(int(marker_hits[name]) for name in ["loss_mask", "structured_aux"])
    curriculum_score = sum(
        int(token in text.lower())
        for token in [
            "counterfactual",
            "source_binding",
            "operator",
            "retrieval",
            "structured_decode",
            "failure_replay",
            "world_compression",
            "slot",
        ]
    )

    return {
        "path": path_str,
        "exists": True,
        "readable": True,
        "line_count": text.count("\n") + 1,
        "sha256": sha256_text(text),
        "marker_hits": marker_hits,
        "marker_lines": marker_lines,
        "marker_hit_count": sum(int(v) for v in marker_hits.values()),
        "required_stage8580_flags_present": present_flags,
        "required_stage8580_flags_missing": missing_flags,
        "architecture_score": architecture_score,
        "trainer_score": trainer_score,
        "curriculum_score": curriculum_score,
        "score": architecture_score * 4 + trainer_score * 3 + curriculum_score,
    }


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True))


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    candidates = [inspect_candidate(path) for path in CANDIDATE_PATHS]
    candidates_sorted = sorted(candidates, key=lambda row: row["score"], reverse=True)

    target = json.loads(TARGET_CONFIG.read_text())
    target_config = target.get("model_config", {})

    top_architecture = [
        row
        for row in candidates_sorted
        if row.get("marker_hits", {}).get("transformer_attention") or row.get("marker_hits", {}).get("rotary_or_rope")
    ][:5]
    top_trainer = [row for row in candidates_sorted if row.get("required_stage8580_flags_present")][:5]
    top_curriculum = [row for row in candidates_sorted if row.get("curriculum_score", 0) > 0][:8]

    metrics = {
        "candidate_paths": len(CANDIDATE_PATHS),
        "readable_candidates": sum(int(row["readable"]) for row in candidates),
        "architecture_candidates": len(top_architecture),
        "trainer_flag_candidates": len(top_trainer),
        "curriculum_candidates": len(top_curriculum),
        "target_parameter_count": target.get("parameter_count"),
        "target_d_model": target_config.get("d_model"),
        "target_layers": target_config.get("n_layers"),
        "target_heads": target_config.get("n_heads"),
        "target_vocab_size": target_config.get("vocab_size"),
    }

    inventory = {
        "stage": 8630,
        "purpose": "Recover exact implementation sources for the preserved 100M transformer/rotary model, safe trainer command surface, and curriculum builders.",
        "authority": AUTHORITY_CLOSED,
        "metrics": metrics,
        "target_config": str(TARGET_CONFIG.relative_to(ROOT)),
        "candidates": candidates_sorted,
        "top_architecture_candidates": [row["path"] for row in top_architecture],
        "top_trainer_candidates": [row["path"] for row in top_trainer],
        "top_curriculum_candidates": [row["path"] for row in top_curriculum],
        "interpretation": "This stage is recovery inventory only. It does not copy code, instantiate the model, run training, or authorize decoder CE.",
    }
    write_json(OUT_DIR / "implementation_candidates.json", inventory)

    def candidate_line(row: dict[str, Any]) -> str:
        missing = len(row.get("required_stage8580_flags_missing", []))
        return (
            f"- `{row['path']}` | score `{row['score']}` | lines `{row['line_count']}` | "
            f"arch `{row.get('architecture_score', 0)}` | trainer `{row.get('trainer_score', 0)}` | "
            f"curriculum `{row.get('curriculum_score', 0)}` | missing Stage8580 flags `{missing}`"
        )

    DOC_PATH.write_text(
        "\n".join(
            [
                "# Stage8630 External Implementation Recovery Inventory",
                "",
                "This stage inventories preserved implementation candidates for rebuilding the real 100M AgentKernel Lite software-maintainer model path. It is read-only recovery work: no code is copied, no model is instantiated, no training is run, and all authority gates remain closed.",
                "",
                "## Why This Stage Exists",
                "",
                "Stage8629 proved that the local `legacy_src/agentkernel_lite/modeling.py` file is only a GRU scaffold. The preserved target is a 102,654,362 parameter transformer/rotary encoder-decoder with agent policy, retrieval, and scalar invariant components. We need to recover implementation sources before touching training.",
                "",
                "## Preserved 100M Target",
                "",
                f"- parameter count: `{target.get('parameter_count')}`",
                f"- d_model: `{target_config.get('d_model')}`",
                f"- d_ff: `{target_config.get('d_ff')}`",
                f"- layers: `{target_config.get('n_layers')}`",
                f"- heads: `{target_config.get('n_heads')}`",
                f"- vocab size: `{target_config.get('vocab_size')}`",
                f"- max positions: `{target_config.get('max_position_embeddings')}`",
                f"- rope theta: `{target_config.get('rope_theta')}`",
                "",
                "## Best Architecture Candidates",
                "",
                *[candidate_line(row) for row in top_architecture],
                "",
                "## Best Trainer Command-Surface Candidates",
                "",
                *[candidate_line(row) for row in top_trainer],
                "",
                "## Best Curriculum/Compiler Candidates",
                "",
                *[candidate_line(row) for row in top_curriculum],
                "",
                "## Required Recovery Decision",
                "",
                "The next stage should inspect the highest-scoring trainer/model candidate in detail and decide whether to adapt it directly or reconstruct a clean `legacy_src/agentkernel_lite/modeling_transformer.py` from the recovered implementation. The safer path is to add a new transformer module and keep the GRU scaffold only for interface tests until shape and parameter-count audits pass.",
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
        "stage": 8630,
        "stage_name": "stage8630_reconstructed_external_implementation_recovery_inventory",
        "passed": True,
        "reconstructed": True,
        "authority": AUTHORITY_CLOSED,
        "metrics": metrics,
        "gates": {
            "inventory_written": True,
            "model_execution_authorized": False,
            "decoder_ce_training_authorized": False,
            "runtime_authorized": False,
            "source_body_emission_authorized": False,
            "safe_read_only_recovery": True,
        },
        "artifacts": {
            "inventory": str((OUT_DIR / "implementation_candidates.json").relative_to(ROOT)),
            "doc": str(DOC_PATH.relative_to(ROOT)),
        },
        "next_best_step": "Inspect the top implementation candidate in detail and recover the transformer/rotary module behind a non-executing shape/parameter-count audit.",
    }
    write_json(SUMMARY_PATH, summary)
    print(json.dumps({"passed": True, "metrics": metrics, "summary": str(SUMMARY_PATH)}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
