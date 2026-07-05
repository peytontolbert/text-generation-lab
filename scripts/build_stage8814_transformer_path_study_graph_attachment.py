#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = 8814
NAME = "stage8814_transformer_path_study_graph_attachment"
BASES = [
    ROOT / "runs/local/artifacts/stage8808_source_backed_decoder_target_materialization_graph_attachment/central_research_graph_with_source_backed_decoder_target_materialization.json",
    ROOT / "runs/local/artifacts/stage8812_output_repair_denoise_controls_graph_attachment/central_research_graph_with_output_repair_denoise_controls.json",
]
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "TRANSFORMER_PATH_STUDY_GRAPH_ATTACHMENT_STAGE8814.md"
SPINE = ROOT / "docs" / "MODEL_STACK_SPINE.md"
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
REQUIRED_FILES = [
    "legacy_src/agentkernel_lite/modeling_transformer.py",
    "legacy_src/agentkernel_lite/training_loop.py",
    "tests/test_transformer_recovery.py",
    "docs/LOW_LEVEL_TRAINING_CONCEPT_SESSION_GREP_STAGE8703.md",
]


def add_node(nodes: dict[str, dict[str, Any]], node: dict[str, Any]) -> bool:
    node_id = node["id"]
    if node_id in nodes:
        nodes[node_id].update(node)
        return False
    nodes[node_id] = node
    return True


def add_edge(edges: list[dict[str, Any]], src: str, relation: str, dst: str) -> None:
    edge = {"src": src, "edge_type": relation, "dst": dst, "source": src, "relation": relation, "target": dst, "evidence_source": NAME}
    if edge not in edges:
        edges.append(edge)


def load_graph(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    graphs = [load_graph(path) for path in BASES]
    nodes: dict[str, dict[str, Any]] = {}
    edges: list[dict[str, Any]] = []
    for graph in graphs:
        for node in graph.get("nodes", []):
            if node.get("id"):
                add_node(nodes, node)
        for edge in graph.get("edges", []):
            if edge not in edges:
                edges.append(edge)

    missing_files = [path for path in REQUIRED_FILES if not (ROOT / path).exists()]
    added_nodes = 0
    concept = "study_path:transformer_tiny_model_intelligence"
    added_nodes += int(add_node(nodes, {
        "id": concept,
        "kind": "study_path",
        "node_type": "study_path",
        "name": "transformer_tiny_model_intelligence",
        "status": "indexed_no_authority_study_path",
        "purpose": "Keep the lab focused on the recovered transformer implementation, not the GRU fallback, when reasoning about tiny model intelligence and training mechanics.",
        "ordered_topics": [
            "tensor_shapes_input_embed_heads_logits",
            "matmul_linear_projection_heads",
            "multi_head_attention_qkv_rope_masks_sdpa",
            "encoder_memory_decoder_state",
            "decoder_ce_autograd_optimizer_loop",
        ],
        "primary_files": REQUIRED_FILES,
        "authority": AUTHORITY_CLOSED,
    }))
    file_nodes = {
        "file:legacy_src/agentkernel_lite/modeling_transformer.py": "implementation_transformer_shapes_attention_heads_rope_structured_heads",
        "file:legacy_src/agentkernel_lite/training_loop.py": "implementation_training_loop_forward_loss_backward_clip_step",
        "file:tests/test_transformer_recovery.py": "test_transformer_forward_shapes_and_contract",
        "file:docs/LOW_LEVEL_TRAINING_CONCEPT_SESSION_GREP_STAGE8703.md": "concept_checklist_tensor_matmul_attention_rope_ce_autograd",
    }
    for node_id, desc in file_nodes.items():
        path = node_id.removeprefix("file:")
        added_nodes += int(add_node(nodes, {
            "id": node_id,
            "kind": "file",
            "node_type": "file",
            "path": path,
            "status": "present" if (ROOT / path).exists() else "missing",
            "role": desc,
            "authority": AUTHORITY_CLOSED,
        }))
        add_edge(edges, concept, "uses_primary_file", node_id)

    concept_nodes = {
        "concept:tensor_shapes_dtype_device": "input_ids [batch, seq] -> embeddings [batch, seq, d_model] -> logits [batch, seq, vocab]",
        "concept:matmul_linear_projection": "nn.Linear projections for q/k/v/o, MLP up/down, lm_head, retrieval heads, structured heads",
        "concept:attention_qkv_rope": "MultiHeadAttention projects q/k/v, splits heads, applies RoPE where configured, masks, scaled-dot-product attention, merges heads",
        "concept:encoder_memory_decoder_state": "encoder hidden memory is the maintained representation the decoder cross-attends to",
        "concept:loss_logits_ce_autograd": "training loop computes logits/loss, backward gradients, clipping, optimizer step",
        "concept:structured_heads_retrieval_heads": "auxiliary heads are learned projections over pooled/hidden transformer state",
        "concept:gru_scaffold_fallback_not_primary": "legacy GRU scaffold is fallback only, not the primary mental model for this lab",
    }
    for node_id, desc in concept_nodes.items():
        added_nodes += int(add_node(nodes, {
            "id": node_id,
            "kind": "concept",
            "node_type": "concept",
            "description": desc,
            "status": "indexed",
            "authority": AUTHORITY_CLOSED,
        }))
        add_edge(edges, concept, "requires_understanding", node_id)

    for downstream in [
        "support_module:gradient_activation_interpretability",
        "support_module:training_telemetry_metrics",
        "support_module:fusion_logits_forward_pass_contract",
        "objective:bounded_decoder_ce",
        "objective:denoise_repair",
        "objective:source_backed_decoder_target_materialization",
        "objective:output_repair_denoise_controls",
    ]:
        add_node(nodes, {"id": downstream, "kind": "support_or_objective", "node_type": "support_or_objective", "authority": AUTHORITY_CLOSED})
        add_edge(edges, concept, "grounds_debugging_for", downstream)

    out = {"version": NAME, "nodes": list(nodes.values()), "edges": edges}
    graph_path = OUT_DIR / "central_research_graph_with_transformer_path_study.json"
    nodes_path = OUT_DIR / "central_research_graph_with_transformer_path_study_nodes.jsonl"
    edges_path = OUT_DIR / "central_research_graph_with_transformer_path_study_edges.jsonl"
    graph_path.write_text(json.dumps(out, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    nodes_path.write_text("".join(json.dumps(node, sort_keys=True) + "\n" for node in out["nodes"]), encoding="utf-8")
    edges_path.write_text("".join(json.dumps(edge, sort_keys=True) + "\n" for edge in out["edges"]), encoding="utf-8")
    failures = []
    if missing_files:
        failures.append("missing_required_files")
    metrics = {
        **AUTHORITY_CLOSED,
        "authority_rows": 0,
        "source_failures": [],
        "missing_required_files": missing_files,
        "graph_nodes": len(out["nodes"]),
        "graph_edges": len(out["edges"]),
        "added_nodes": added_nodes,
        "base_graphs_merged": len(BASES),
        "required_files_present": len(REQUIRED_FILES) - len(missing_files),
        "required_files_total": len(REQUIRED_FILES),
    }
    card = {
        "stage": STAGE,
        "stage_name": NAME,
        "passed": not failures,
        "authority": AUTHORITY_CLOSED,
        "metrics": metrics,
        "artifacts": {
            "graph": str(graph_path.relative_to(ROOT)),
            "nodes_jsonl": str(nodes_path.relative_to(ROOT)),
            "edges_jsonl": str(edges_path.relative_to(ROOT)),
        },
        "decision": "Attached transformer-path study node to the central graph and merged the target-materialization and denoise-control graph branches." if not failures else "Transformer-path study graph attachment failed.",
        "next_best_step": "Use this study path to debug future CE/denoise probes by tensor shapes, attention projections, logits/loss, gradients, and structured heads; keep execution/training closed until gates authorize it.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    (OUT_DIR / "transformer_path_study_graph_attachment_card.json").write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    SUMMARY.write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage8814 Transformer Path Study Graph Attachment",
        "",
        f"Passed: `{card['passed']}`",
        "",
        "This indexes the transformer-specific mental model for this lab:",
        "",
        "1. Tensor shapes: `[batch, seq] -> [batch, seq, d_model] -> [batch, heads, seq, head_dim] -> [batch, seq, vocab]`.",
        "2. Matmul/projections: `nn.Linear` as learned projections for Q/K/V/O, MLP up/down, LM head, retrieval heads, and structured heads.",
        "3. Attention: QKV projection, head split/merge, RoPE, masks, scaled dot-product attention.",
        "4. State: encoder memory plus decoder causal/cross-attention hidden state, not generic SSM theory first.",
        "5. Learning: decoder CE/logits/autograd/backward/clip/optimizer step in the recovered training loop.",
        "",
        "Primary files:",
        "",
        *[f"- `{path}`" for path in REQUIRED_FILES],
        "",
        "The GRU scaffold is fallback, not the main intelligence path for this repo.",
        "",
        "No training, runtime, decoder CE, denoise CE, source/body emission, scoring, Gemma, controller merge, or promotion is authorized by this stage.",
        "",
    ]), encoding="utf-8")

    marker = "## Stage8814 Transformer Path Study Index"
    spine_text = SPINE.read_text(encoding="utf-8") if SPINE.exists() else ""
    if marker not in spine_text:
        SPINE.write_text(spine_text.rstrip() + "\n\n" + "\n".join([
            marker,
            "",
            "The lab's primary tiny-model intelligence path is the recovered transformer, not the GRU scaffold. The graph now indexes `legacy_src/agentkernel_lite/modeling_transformer.py`, `legacy_src/agentkernel_lite/training_loop.py`, `tests/test_transformer_recovery.py`, and the Stage8703 low-level concept checklist as the required study/debug path.",
            "",
            "Study/debug order:",
            "",
            "1. Tensor shapes through config, embedding, head split/merge, encoder/decoder, and logits.",
            "2. `nn.Linear` as matmul/projection for Q/K/V/O, MLP, LM head, retrieval heads, and structured heads.",
            "3. Multi-head attention mechanics: QKV, RoPE, causal/padding masks, scaled-dot-product attention, merge/project out.",
            "4. State as evolving hidden tensor plus encoder memory read by decoder cross-attention.",
            "5. Loss/learning through decoder CE, autograd, gradient clipping, and optimizer step.",
            "",
            "This node should be used when debugging future bounded decoder CE, denoise repair, fusion/logit contracts, activation telemetry, and structured heads. It opens no training/runtime authority.",
            "",
        ]), encoding="utf-8")

    print(json.dumps(card, indent=2, sort_keys=True))
    raise SystemExit(0 if card["passed"] else 1)

if __name__ == "__main__":
    main()
