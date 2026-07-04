#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path

from program_state_call_graph_extractor import extract_python_call_graph
from program_state_data_control_flow_extractor import extract_python_data_control_flow
from program_state_type_signature_extractor import extract_python_type_signatures

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "runs/local/artifacts/stage8691_semantic_flow_extractor_readiness"
SUMMARY = ROOT / "runs/summaries/stage8691_semantic_flow_extractor_readiness.json"
DOC = ROOT / "docs/SEMANTIC_FLOW_EXTRACTOR_READINESS_STAGE8691.md"
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
SAMPLE = """
from pathlib import Path

class Greeter:
    def hello(self, name: str) -> str:
        message = "hi " + name
        if name:
            return message
        return "hi"

def main(path: Path) -> str:
    greeter = Greeter()
    return greeter.hello(str(path))
"""


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    type_packet = extract_python_type_signatures(SAMPLE, row_id="stage8691_sample", path="sample.py").to_dict()
    call_packet = extract_python_call_graph(SAMPLE, row_id="stage8691_sample", path="sample.py").to_dict()
    flow_packet = extract_python_data_control_flow(SAMPLE, row_id="stage8691_sample", path="sample.py").to_dict()
    (OUT_DIR / "sample_type_signature_packet.json").write_text(json.dumps(type_packet, indent=2, sort_keys=True) + "\n")
    (OUT_DIR / "sample_call_graph_packet.json").write_text(json.dumps(call_packet, indent=2, sort_keys=True) + "\n")
    (OUT_DIR / "sample_data_control_flow_packet.json").write_text(json.dumps(flow_packet, indent=2, sort_keys=True) + "\n")
    covered = ["type_signature_map", "call_graph", "data_flow_graph", "control_flow_graph"]
    still_missing = [
        "runtime_stack_trace_normalizer",
        "patch_history_modality_builder",
        "dependency_capability_card_builder",
        "cross_modal_alignment_audit",
        "modality_dropout_ablation_audit",
        "context_packer_lost_in_middle_memory_retrieval",
        "state_space_repo_state_compressor",
        "training_telemetry",
    ]
    metrics = {
        "type_signature_records": len(type_packet["signatures"]),
        "type_signature_edges": len(type_packet["edges"]),
        "call_graph_nodes": len(call_packet["call_nodes"]),
        "call_graph_edges": len(call_packet["edges"]),
        "data_flow_nodes": len(flow_packet["data_nodes"]),
        "control_flow_nodes": len(flow_packet["control_nodes"]),
        "data_control_edges": len(flow_packet["edges"]),
        "covered_modalities": covered,
        "still_missing_modules": still_missing,
        "authority_rows": 0,
        **AUTHORITY_CLOSED,
    }
    passed = all(not packet["failures"] for packet in [type_packet, call_packet, flow_packet]) and metrics["type_signature_records"] > 0 and metrics["call_graph_edges"] > 0 and metrics["data_control_edges"] > 0
    card = {
        "stage": 8691,
        "name": "stage8691_semantic_flow_extractor_readiness",
        "stage_name": "stage8691_semantic_flow_extractor_readiness",
        "passed": passed,
        "authority": AUTHORITY_CLOSED,
        "metrics": metrics,
        "decision": "Recovered sample-only type/signature, call-graph, data-flow, and control-flow extractors for the program-state multimodality spine. These are modality extractors only and do not authorize mining, model execution, runtime, or training.",
        "next_best_step": "Attach semantic-flow extractors to the central graph, then recover runtime trace normalizer and patch-history modality builder.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    (OUT_DIR / "semantic_flow_extractor_readiness_card.json").write_text(json.dumps(card, indent=2, sort_keys=True) + "\n")
    SUMMARY.write_text(json.dumps(card, indent=2, sort_keys=True) + "\n")
    DOC.write_text("\n".join([
        "# Stage8691 Semantic Flow Extractor Readiness",
        "",
        f"Passed: `{passed}`",
        "",
        "Recovered no-authority modality extractors:",
        "",
        "- type/signature map",
        "- call graph",
        "- data-flow graph",
        "- control-flow graph",
        "",
        "These are sample-only readiness modules. They do not mine `/arxiv`, do not run code, do not train, and do not open decoder CE.",
        "",
        "## Metrics",
        "",
        f"- type signatures: `{metrics['type_signature_records']}`",
        f"- call graph edges: `{metrics['call_graph_edges']}`",
        f"- data/control edges: `{metrics['data_control_edges']}`",
        "",
        "## Still Missing",
        "",
        *[f"- `{item}`" for item in still_missing],
        "",
        "All authority remains closed.",
        "",
    ]))
    print(json.dumps(card, indent=2, sort_keys=True))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
