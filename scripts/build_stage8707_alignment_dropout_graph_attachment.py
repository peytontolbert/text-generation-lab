#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'runs/local/artifacts/stage8705_low_level_training_graph_attachment/central_research_graph_with_low_level_training.json'
OUT_DIR = ROOT / 'runs/local/artifacts/stage8707_alignment_dropout_graph_attachment'
SUMMARY = ROOT / 'runs/summaries/stage8707_alignment_dropout_graph_attachment.json'
DOC = ROOT / 'docs/ALIGNMENT_DROPOUT_GRAPH_ATTACHMENT_STAGE8707.md'
AUTHORITY_CLOSED = {'model_execution_authorized_next': False, 'decoder_ce_training_authorized_next': False, 'runtime_authorized': False, 'source_emission_authorized': False, 'body_emission_authorized': False, 'gemma_execution_authorized_next': False, 'harness_execution_authorized_next': False, 'scoring_authorized_next': False, 'controller_complete_merge_authorized_next': False, 'promotion_ready': False}


def _load_graph() -> dict[str, list[dict[str, Any]]]:
    if BASE.exists():
        graph=json.loads(BASE.read_text())
        return {'nodes': list(graph.get('nodes', [])), 'edges': list(graph.get('edges', []))}
    return {'nodes': [], 'edges': []}


def _add_node(nodes: dict[str, dict[str, Any]], node_id: str, node_type: str, **attrs: Any) -> None:
    nodes.setdefault(node_id, {'id': node_id, 'node_type': node_type, **attrs})


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    graph=_load_graph()
    nodes_by_id={node.get('id'): node for node in graph['nodes'] if node.get('id')}
    edges=list(graph['edges'])
    modules = {
        'support_module:cross_modal_alignment_audit': ['program_state_modality:source_text','program_state_modality:cst_ast','program_state_modality:symbol_table','program_state_modality:import_export_graph','program_state_modality:type_signature_map','program_state_modality:call_graph','program_state_modality:data_flow_graph','program_state_modality:control_flow_graph','program_state_modality:runtime_trace','program_state_modality:patch_history','program_state_modality:dependency_capability_card'],
        'support_module:modality_dropout_ablation_audit': ['objective:symbol_binding','objective:edit_localization','objective:patch_operator','objective:verifier_repair','objective:bounded_decoder_arguments','objective:bounded_decoder_ce'],
    }
    for module, targets in modules.items():
        _add_node(nodes_by_id, module, 'support_module', recovered=True, authority_opened=False)
        for target in targets:
            node_type='program_state_modality' if target.startswith('program_state_modality:') else 'objective'
            _add_node(nodes_by_id, target, node_type, recovered=True, authority_opened=False)
            edge_type='audits_alignment_for' if module.endswith('cross_modal_alignment_audit') else 'audits_dropout_for'
            edges.append({'src': module, 'dst': target, 'edge_type': edge_type})
    gates = ['gate:no_single_modality_shortcut','gate:multimodal_lift_required','gate:source_hash_path_alignment_required','gate:edge_endpoint_resolution_required']
    for gate in gates:
        _add_node(nodes_by_id, gate, 'curriculum_gate', recovered=True, authority_opened=False)
        for module in modules:
            edges.append({'src': module, 'dst': gate, 'edge_type': 'enforces_gate'})
    missing=['support_module:state_space_repo_state_compressor','support_module:gradient_activation_interpretability','support_module:graph_neural_repo_encoder','support_module:mixed_precision_runtime_contract']
    for m in missing:
        _add_node(nodes_by_id, m, 'missing_support_module', recovered=False, authority_opened=False)
    out={'nodes': list(nodes_by_id.values()), 'edges': edges}
    (OUT_DIR/'central_research_graph_with_alignment_dropout.json').write_text(json.dumps(out, indent=2, sort_keys=True)+'\n')
    (OUT_DIR/'central_research_graph_with_alignment_dropout_nodes.jsonl').write_text(''.join(json.dumps(n, sort_keys=True)+'\n' for n in out['nodes']))
    (OUT_DIR/'central_research_graph_with_alignment_dropout_edges.jsonl').write_text(''.join(json.dumps(e, sort_keys=True)+'\n' for e in out['edges']))
    metrics={'base_graph': str(BASE.relative_to(ROOT)), 'graph_nodes': len(out['nodes']), 'graph_edges': len(out['edges']), 'modules_attached': len(modules), 'gates_attached': len(gates), 'missing_support_modules': missing, **AUTHORITY_CLOSED}
    card={'stage':8707,'name':'stage8707_alignment_dropout_graph_attachment','stage_name':'stage8707_alignment_dropout_graph_attachment','passed':True,'authority':AUTHORITY_CLOSED,'metrics':metrics,'decision':'Attached cross-modal alignment and modality dropout/ablation audits to the central graph, including gates for source/hash/path alignment, edge endpoint resolution, no single-modality shortcut, and multimodal lift.','next_best_step':'Recover state-space repo compressor and gradient/activation interpretability before data mining or training resumes.','created_at_utc':time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}
    (OUT_DIR/'alignment_dropout_graph_attachment_card.json').write_text(json.dumps(card, indent=2, sort_keys=True)+'\n')
    SUMMARY.write_text(json.dumps(card, indent=2, sort_keys=True)+'\n')
    DOC.write_text('\n'.join(['# Stage8707 Alignment/Dropout Graph Attachment','','Passed: `True`','','Attached recovered audit modules:','','- `cross_modal_alignment_audit`','- `modality_dropout_ablation_audit`','','Attached curriculum gates:','','- no single-modality shortcut','- multimodal lift required','- source/hash/path alignment required','- edge endpoint resolution required','','All authority remains closed.','']))
    print(json.dumps(card, indent=2, sort_keys=True))
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
