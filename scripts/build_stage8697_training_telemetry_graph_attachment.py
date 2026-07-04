#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "runs/local/artifacts/stage8695_context_packer_graph_attachment/central_research_graph_with_context_packer.json"
OUT_DIR = ROOT / "runs/local/artifacts/stage8697_training_telemetry_graph_attachment"
SUMMARY = ROOT / "runs/summaries/stage8697_training_telemetry_graph_attachment.json"
DOC = ROOT / "docs/TRAINING_TELEMETRY_GRAPH_ATTACHMENT_STAGE8697.md"
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


def _load_graph() -> dict[str, list[dict[str, Any]]]:
    if BASE.exists():
        graph = json.loads(BASE.read_text())
        return {"nodes": list(graph.get("nodes", [])), "edges": list(graph.get("edges", []))}
    return {"nodes": [], "edges": []}


def _add_node(nodes: dict[str, dict[str, Any]], node_id: str, node_type: str, **attrs: Any) -> None:
    nodes.setdefault(node_id, {"id": node_id, "node_type": node_type, **attrs})


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    graph = _load_graph()
    nodes_by_id = {node.get("id"): node for node in graph["nodes"] if node.get("id")}
    edges = list(graph["edges"])
    module = "support_module:training_telemetry_metrics"
    metrics = [
        "telemetry:row_field_margin_confidence_entropy",
        "telemetry:high_confidence_wrong_rows",
        "telemetry:token_loss_map",
        "telemetry:failure_bucket_summary",
    ]
    _add_node(nodes_by_id, module, "support_module", recovered=True, authority_opened=False)
    for metric in metrics:
        _add_node(nodes_by_id, metric, "telemetry_metric", recovered=True, authority_opened=False)
        edges.append({"src": module, "dst": metric, "edge_type": "emits_metric"})
    for objective in ["objective:intent_to_build_strategy", "objective:symbol_binding", "objective:edit_localization", "objective:patch_operator", "objective:verifier_repair", "objective:bounded_decoder_ce"]:
        _add_node(nodes_by_id, objective, "objective", recovered=True, authority_opened=False)
        edges.append({"src": module, "dst": objective, "edge_type": "audits_probe"})
    missing = [
        "support_module:runtime_stack_trace_normalizer",
        "support_module:patch_history_modality_builder",
        "support_module:dependency_capability_card_builder",
        "support_module:cross_modal_alignment_audit",
        "support_module:modality_dropout_ablation_audit",
        "support_module:state_space_repo_state_compressor",
        "support_module:runtime_verifier_loop",
        "support_module:gradient_activation_interpretability",
    ]
    for node_id in missing:
        _add_node(nodes_by_id, node_id, "missing_support_module", recovered=False, authority_opened=False)
    out_graph = {"nodes": list(nodes_by_id.values()), "edges": edges}
    (OUT_DIR / "central_research_graph_with_training_telemetry.json").write_text(json.dumps(out_graph, indent=2, sort_keys=True) + "\n")
    (OUT_DIR / "central_research_graph_with_training_telemetry_nodes.jsonl").write_text("".join(json.dumps(node, sort_keys=True) + "\n" for node in out_graph["nodes"]))
    (OUT_DIR / "central_research_graph_with_training_telemetry_edges.jsonl").write_text("".join(json.dumps(edge, sort_keys=True) + "\n" for edge in out_graph["edges"]))
    card_metrics = {
        "base_graph": str(BASE.relative_to(ROOT)),
        "graph_nodes": len(out_graph["nodes"]),
        "graph_edges": len(out_graph["edges"]),
        "telemetry_metrics_attached": len(metrics),
        "missing_support_modules": missing,
        **AUTHORITY_CLOSED,
    }
    card = {
        "stage": 8697,
        "name": "stage8697_training_telemetry_graph_attachment",
        "stage_name": "stage8697_training_telemetry_graph_attachment",
        "passed": True,
        "authority": AUTHORITY_CLOSED,
        "metrics": card_metrics,
        "decision": "Attached training_telemetry_metrics to the central graph as the non-executing telemetry substrate for native probes and bounded decoder audits.",
        "next_best_step": "Recover runtime stack trace normalizer, patch-history modality builder, dependency capability cards, and runtime verifier loop before data mining or training resumes.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    (OUT_DIR / "training_telemetry_graph_attachment_card.json").write_text(json.dumps(card, indent=2, sort_keys=True) + "\n")
    SUMMARY.write_text(json.dumps(card, indent=2, sort_keys=True) + "\n")
    DOC.write_text("\n".join([
        "# Stage8697 Training Telemetry Graph Attachment",
        "",
        "Passed: `True`",
        "",
        "Attached telemetry metrics:",
        "",
        "- row-field margin/confidence/entropy",
        "- high-confidence wrong row filter",
        "- token loss map",
        "- failure bucket summary",
        "",
        "These metrics support native structured probes and bounded decoder audits. This stage does not authorize training or runtime execution.",
        "",
        "## Next",
        "",
        card["next_best_step"],
        "",
    ]))
    print(json.dumps(card, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
