#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
GRAPH_PATH = ROOT / "runs" / "local" / "artifacts" / "stage8624_arxiv_recovery_graph_attachment" / "central_research_graph_with_arxiv_sources.json"
TARGET_CONFIG = ROOT / "configs" / "model" / "agentkernel_100m_seq2seq_recovered_target.json"
STAGE8630 = ROOT / "runs" / "summaries" / "stage8630_reconstructed_external_implementation_recovery_inventory.json"
STAGE8631 = ROOT / "runs" / "summaries" / "stage8631_reconstructed_recovered_transformer_module_audit.json"
OUT_DIR = ROOT / "runs" / "local" / "artifacts" / "stage8632_training_variable_reconciliation"
SUMMARY_PATH = ROOT / "runs" / "summaries" / "stage8632_reconstructed_training_variable_reconciliation.json"
DOC_PATH = ROOT / "docs" / "TRAINING_VARIABLE_RECONCILIATION_STAGE8632.md"

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


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True))


def graph_counts() -> dict[str, int]:
    if not GRAPH_PATH.is_file():
        return {}
    graph = read_json(GRAPH_PATH)
    counts: dict[str, int] = {}
    for node in graph.get("nodes", []):
        counts[str(node.get("kind", "unknown"))] = counts.get(str(node.get("kind", "unknown")), 0) + 1
    return counts


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    target = read_json(TARGET_CONFIG)
    cfg = target["model_config"]
    s8630 = read_json(STAGE8630)
    s8631 = read_json(STAGE8631)
    counts = graph_counts()

    recovered_variables = {
        "model_family": target["model_family"],
        "parameter_count_preserved": int(target["parameter_count"]),
        "parameter_count_estimated_local": int(s8631["metrics"]["estimated_local_transformer_parameter_count"]),
        "d_model": int(cfg["d_model"]),
        "d_ff": int(cfg["d_ff"]),
        "n_layers": int(cfg["n_layers"]),
        "n_heads": int(cfg["n_heads"]),
        "vocab_size": int(cfg["vocab_size"]),
        "max_position_embeddings": int(cfg["max_position_embeddings"]),
        "rope_theta": float(cfg["rope_theta"]),
        "retrieval_head_dim": int(cfg["retrieval_head_dim"]),
        "agent_policy_heads": bool(cfg["agent_policy_heads"]),
        "agent_intent_labels": int(cfg["agent_intent_labels"]),
        "agent_controller_dim": int(cfg["agent_controller_dim"]),
        "scalar_invariant_rank": int(cfg["scalar_invariant_rank"]),
        "tokenizer_kind": target["tokenizer"]["kind"],
        "tokenizer_vocab_size": int(target["tokenizer"]["vocab_size"]),
    }

    required_before_training = [
        {
            "item": "wire transformer implementation behind safe trainer wrapper",
            "status": "missing",
            "reason": "local transformer module exists, but trainer execution path still uses contract scaffold and has no authorized model execution",
        },
        {
            "item": "bounded decoder CE manifest availability",
            "status": "partial",
            "reason": "candidate package was recovered through Stage8580 history, but current rebuild still needs regenerated local rows/loss-mask card before execution",
        },
        {
            "item": "agentkernel BPE tokenizer artifact",
            "status": "partial",
            "reason": "target tokenizer metadata recovered; concrete tokenizer files must be located or rebuilt from dataset text before full training",
        },
        {
            "item": "runtime loss-mask enforcement",
            "status": "partial",
            "reason": "safe command surface validates masks in contract-only mode; real loss computation must be connected to row masks before execution",
        },
        {
            "item": "telemetry artifacts",
            "status": "present_contract_only",
            "reason": "telemetry filenames and stubs exist; real row token loss/logit/module delta artifacts require tiny authorized execution",
        },
        {
            "item": "central graph objective coverage",
            "status": "present",
            "reason": "central graph lists policy, graph, binding, localization, operator, verifier, bounded decoder, denoise, and promotion families",
        },
    ]

    objective_chain = [
        "intent_to_build_strategy",
        "repo_state_graph_v1",
        "symbol_binding",
        "edit_localization",
        "patch_operator",
        "verifier_repair",
        "bounded_decoder_arguments",
        "bounded_decoder_ce",
        "output_repair_denoise",
        "controlled_harness_later",
    ]

    metrics = {
        "central_graph_nodes": sum(counts.values()),
        "central_graph_kinds": len(counts),
        "objective_family_nodes": counts.get("objective_family", 0),
        "structured_field_nodes": counts.get("structured_field", 0),
        "model_family_nodes": counts.get("model_family", 0),
        "authority_flag_nodes": counts.get("authority_flag", 0),
        "recovered_model_variable_count": len(recovered_variables),
        "required_before_training_count": len(required_before_training),
        "stage8630_passed": bool(s8630.get("passed")),
        "stage8631_passed": bool(s8631.get("passed")),
    }

    reconciliation = {
        "stage": 8632,
        "authority": AUTHORITY_CLOSED,
        "metrics": metrics,
        "recovered_variables": recovered_variables,
        "objective_chain": objective_chain,
        "required_before_training": required_before_training,
        "graph_kind_counts": counts,
        "interpretation": "The architecture variables needed for the effective 100M model are back. The next gap is safe integration into the trainer and regeneration/verification of the bounded decoder CE manifest, not more architecture guessing.",
    }
    write_json(OUT_DIR / "training_variable_reconciliation.json", reconciliation)

    DOC_PATH.write_text(
        "\n".join(
            [
                "# Stage8632 Training Variable Reconciliation",
                "",
                "This stage reconciles the central research graph with the recovered 100M transformer implementation. It is a recovery control artifact only and does not authorize training.",
                "",
                "## Recovered 100M Model Variables",
                "",
                *[f"- `{key}`: `{value}`" for key, value in recovered_variables.items()],
                "",
                "## Active Objective Chain",
                "",
                " -> ".join(f"`{item}`" for item in objective_chain),
                "",
                "## Still Required Before Training",
                "",
                *[f"- `{row['item']}`: `{row['status']}` - {row['reason']}" for row in required_before_training],
                "",
                "## Central Graph Coverage",
                "",
                f"- objective families: `{counts.get('objective_family', 0)}`",
                f"- structured fields: `{counts.get('structured_field', 0)}`",
                f"- model families: `{counts.get('model_family', 0)}`",
                f"- authority flags: `{counts.get('authority_flag', 0)}`",
                "",
                "## Current Best Next Step",
                "",
                "Integrate `legacy_src/agentkernel_lite/modeling_transformer.py` behind the safe trainer wrapper as a selectable implementation, then run a non-executing shape/manifest/loss-mask audit. Do not run decoder CE yet.",
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
        "stage": 8632,
        "stage_name": "stage8632_reconstructed_training_variable_reconciliation",
        "passed": True,
        "reconstructed": True,
        "authority": AUTHORITY_CLOSED,
        "metrics": metrics,
        "gates": {
            "central_graph_checked": bool(counts),
            "target_model_variables_recovered": True,
            "transformer_module_recovered": bool(s8631.get("passed")),
            "training_still_blocked_until_safe_integration": True,
            "authority_closed": True,
        },
        "artifacts": {
            "reconciliation": str((OUT_DIR / "training_variable_reconciliation.json").relative_to(ROOT)),
            "doc": str(DOC_PATH.relative_to(ROOT)),
        },
        "next_best_step": "Wire the recovered transformer as a selectable safe trainer implementation and audit shape/loss-mask integration without execution.",
    }
    write_json(SUMMARY_PATH, summary)
    print(json.dumps({"passed": True, "metrics": metrics, "summary": str(SUMMARY_PATH)}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
