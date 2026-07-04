#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'runs/local/artifacts/stage8702_runtime_verifier_loop_graph_attachment/central_research_graph_with_runtime_verifier_loop.json'
OUT_DIR = ROOT / 'runs/local/artifacts/stage8705_low_level_training_graph_attachment'
SUMMARY = ROOT / 'runs/summaries/stage8705_low_level_training_graph_attachment.json'
DOC = ROOT / 'docs/LOW_LEVEL_TRAINING_GRAPH_ATTACHMENT_STAGE8705.md'
AUTHORITY_CLOSED = {'model_execution_authorized_next': False, 'decoder_ce_training_authorized_next': False, 'runtime_authorized': False, 'source_emission_authorized': False, 'body_emission_authorized': False, 'gemma_execution_authorized_next': False, 'harness_execution_authorized_next': False, 'scoring_authorized_next': False, 'controller_complete_merge_authorized_next': False, 'promotion_ready': False}
MECHANICS = ['tensor_shapes_dtype_device','matmul_linear_projection','embedding_tokenization','attention_qkv','positional_encoding_rope','mlp_activation_norm','loss_logits_ce','autograd_backward_gradients','optimizer_scheduler','dataloader_batching','checkpoint_reproducibility','mixed_precision_memory','calibration_entropy_confidence','activation_interpretability','state_space_scan','graph_gnn','denoise_diffusion','dataset_cartography_attribution']


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
    layer='architecture_layer:low_level_training_mechanics'
    _add_node(nodes_by_id, layer, 'architecture_layer', recovered=True, authority_opened=False)
    for mech in MECHANICS:
        mech_id=f'training_mechanic:{mech}'
        _add_node(nodes_by_id, mech_id, 'training_mechanic', recovered=True, authority_opened=False)
        edges.append({'src': layer, 'dst': mech_id, 'edge_type': 'contains_mechanic'})
    for support in ['support_module:training_telemetry_metrics','support_module:runtime_verifier_loop_contract','support_module:context_packer_v1','support_module:target_implementation_guard']:
        _add_node(nodes_by_id, support, 'support_module', recovered=True, authority_opened=False)
        edges.append({'src': layer, 'dst': support, 'edge_type': 'constrains_or_audits'})
    missing=['support_module:gradient_activation_interpretability','support_module:state_space_repo_state_compressor','support_module:graph_neural_repo_encoder','support_module:mixed_precision_runtime_contract']
    for m in missing:
        _add_node(nodes_by_id, m, 'missing_support_module', recovered=False, authority_opened=False)
    out={'nodes': list(nodes_by_id.values()), 'edges': edges}
    (OUT_DIR/'central_research_graph_with_low_level_training.json').write_text(json.dumps(out, indent=2, sort_keys=True)+'\n')
    (OUT_DIR/'central_research_graph_with_low_level_training_nodes.jsonl').write_text(''.join(json.dumps(n, sort_keys=True)+'\n' for n in out['nodes']))
    (OUT_DIR/'central_research_graph_with_low_level_training_edges.jsonl').write_text(''.join(json.dumps(e, sort_keys=True)+'\n' for e in out['edges']))
    metrics={'base_graph': str(BASE.relative_to(ROOT)), 'graph_nodes': len(out['nodes']), 'graph_edges': len(out['edges']), 'mechanics_attached': len(MECHANICS), 'missing_support_modules': missing, **AUTHORITY_CLOSED}
    card={'stage':8705,'name':'stage8705_low_level_training_graph_attachment','stage_name':'stage8705_low_level_training_graph_attachment','passed':True,'authority':AUTHORITY_CLOSED,'metrics':metrics,'decision':'Attached low-level training mechanics to the central graph so tensors, logits, losses, gradients, optimizer behavior, telemetry, and missing interpretability modules remain explicit recovery variables.','next_best_step':'Recover cross-modal alignment audit and modality dropout/ablation audit, then state-space repo compressor and gradient/activation interpretability.','created_at_utc':time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}
    (OUT_DIR/'low_level_training_graph_attachment_card.json').write_text(json.dumps(card, indent=2, sort_keys=True)+'\n')
    SUMMARY.write_text(json.dumps(card, indent=2, sort_keys=True)+'\n')
    DOC.write_text('\n'.join(['# Stage8705 Low-Level Training Graph Attachment','','Passed: `True`','','Attached low-level training mechanics to the central graph. This keeps tensor/matmul/embedding/attention/loss/autograd/optimizer/dataloader/checkpoint/calibration/interpretability/state-space/GNN/denoise/cartography variables visible as first-class recovery nodes.','','All authority remains closed.','']))
    print(json.dumps(card, indent=2, sort_keys=True))
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
