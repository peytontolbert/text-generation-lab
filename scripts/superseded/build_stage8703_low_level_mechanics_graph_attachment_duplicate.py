#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'runs/local/artifacts/stage8702_runtime_verifier_loop_graph_attachment/central_research_graph_with_runtime_verifier_loop.json'
SOURCE = ROOT / 'runs/summaries/stage8700_low_level_training_mechanics_spine_patch.json'
STAGE = 8703
NAME = 'stage8703_v27_low_level_training_mechanics_graph_attachment'
OUT_DIR = ROOT / f'runs/local/artifacts/{NAME}'
SUMMARY = ROOT / 'runs/summaries/stage8701_low_level_training_mechanics_graph_attachment.json'
DOC = ROOT / 'docs/LOW_LEVEL_TRAINING_MECHANICS_GRAPH_ATTACHMENT_STAGE8701.md'
REGISTRY = ROOT / 'runs/local/artifacts/reconstructed_stage_registry.json'
AUTHORITY_CLOSED = {'model_execution_authorized_next': False, 'decoder_ce_training_authorized_next': False, 'denoise_ce_training_authorized_next': False, 'runtime_authorized': False, 'source_body_authorized': False, 'gemma_authorized': False, 'promotion_ready': False}
MECHANICS = {
    'tensor_shapes_dtype_device': 'shape/dtype/device and batch compatibility substrate',
    'matmul_linear_projection': 'weighted mixing primitive for projections, heads, attention and MLPs',
    'embedding_tokenization': 'token/vector vocabulary compatibility substrate',
    'attention_qkv': 'token/evidence routing mechanism',
    'positional_encoding_rope': 'position/order/location encoding for code and context packets',
    'mlp_activation_norm': 'feature transformation and stabilization mechanism',
    'loss_logits_ce': 'supervised logits/loss/loss-mask substrate',
    'autograd_backward_gradients': 'gradient production and training attribution substrate',
    'optimizer_scheduler': 'parameter update and learning-rate control substrate',
    'dataloader_batching': 'batch/split/collate/dataflow substrate',
    'checkpoint_reproducibility': 'repeatability and rollback substrate',
    'mixed_precision_memory': 'future efficient memory/precision substrate, documented-not-executable',
    'calibration_entropy_confidence': 'abstain/confidence/OOD threshold substrate',
    'activation_interpretability': 'future activation/logit/patching substrate, documented-not-executable',
    'graph_gnn': 'future learned graph message-passing substrate, documented-not-executable',
    'state_space_scan': 'future selective-scan repo-state compression substrate',
    'denoise_diffusion': 'repair/infill iterative denoising substrate',
    'dataset_cartography_attribution': 'future data dynamics/influence substrate',
}


def add_node(nodes: list[dict[str, Any]], node: dict[str, Any]) -> bool:
    if any(existing.get('id') == node['id'] for existing in nodes):
        return False
    nodes.append(node)
    return True


def add_edge(edges: list[dict[str, Any]], source: str, relation: str, target: str) -> bool:
    edge = {'source': source, 'relation': relation, 'target': target, 'evidence_source': NAME}
    if any(e.get('source') == source and e.get('relation') == relation and e.get('target') == target for e in edges):
        return False
    edges.append(edge)
    return True


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.write_text(''.join(json.dumps(row, sort_keys=True) + '\n' for row in rows), encoding='utf-8')


def write_registry(card: dict[str, Any]) -> None:
    registry = json.loads(REGISTRY.read_text(encoding='utf-8')) if REGISTRY.exists() else {'stages': []}
    stages = [row for row in registry.get('stages', []) if row.get('stage') != STAGE]
    stages.append({'stage': STAGE, 'name': NAME, 'summary_path': str(SUMMARY), 'artifact_dir': str(OUT_DIR), 'passed': card['passed'], 'authority_rows': card['metrics']['authority_rows'], 'created_at': card['created_at_utc']})
    registry['stages'] = sorted(stages, key=lambda row: int(row.get('stage', -1)))
    registry['latest_stage'] = STAGE
    registry['latest_name'] = NAME
    registry['latest_summary_path'] = str(SUMMARY)
    registry['updated_at'] = card['created_at_utc']
    REGISTRY.parent.mkdir(parents=True, exist_ok=True)
    REGISTRY.write_text(json.dumps(registry, indent=2, sort_keys=True) + '\n', encoding='utf-8')


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)
    graph = json.loads(BASE.read_text(encoding='utf-8'))
    source = json.loads(SOURCE.read_text(encoding='utf-8'))
    nodes = list(graph.get('nodes', []))
    edges = list(graph.get('edges', []))
    added_nodes = 0
    added_edges = 0
    root_id = 'training_mechanics:low_level_training_substrate'
    added_nodes += int(add_node(nodes, {'id': root_id, 'kind': 'training_mechanics', 'name': 'low_level_training_substrate', 'role': 'tensor/matmul/autograd/loss/optimizer substrate for recovered 100M maintainer training', 'status': 'indexed', 'summary': str(SOURCE.relative_to(ROOT)), 'authority': AUTHORITY_CLOSED}))
    for key, role in MECHANICS.items():
        node_id = f'training_mechanics:{key}'
        status = 'documented_not_executable' if key in set(source.get('documented_not_executable_groups', [])) else 'indexed_or_partially_executable'
        added_nodes += int(add_node(nodes, {'id': node_id, 'kind': 'training_mechanics', 'name': key, 'role': role, 'status': status, 'authority': AUTHORITY_CLOSED}))
        added_edges += int(add_edge(edges, root_id, 'contains_mechanic', node_id))
        if key in {'loss_logits_ce', 'autograd_backward_gradients', 'calibration_entropy_confidence'}:
            added_edges += int(add_edge(edges, node_id, 'supports', 'support_module:training_telemetry_metrics'))
        if key == 'positional_encoding_rope':
            added_edges += int(add_edge(edges, node_id, 'supports', 'model_component:rotary_position_encoding'))
        if key == 'graph_gnn':
            added_edges += int(add_edge(edges, node_id, 'future_supports', 'objective_family:repo_state_graph_v1'))
        if key == 'state_space_scan':
            added_edges += int(add_edge(edges, node_id, 'future_supports', 'support_module:context_packer_v1'))
    graph['nodes'] = nodes
    graph['edges'] = edges
    graph['version'] = NAME
    graph['generated_at'] = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
    graph['authority'] = AUTHORITY_CLOSED
    full = OUT_DIR / 'central_research_graph_with_low_level_training_mechanics.json'
    np = OUT_DIR / 'central_research_graph_with_low_level_training_mechanics_nodes.jsonl'
    ep = OUT_DIR / 'central_research_graph_with_low_level_training_mechanics_edges.jsonl'
    full.write_text(json.dumps(graph, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    write_jsonl(np, nodes)
    write_jsonl(ep, edges)
    expected = {f'training_mechanics:{key}' for key in MECHANICS} | {root_id}
    present = {node.get('id') for node in nodes}
    missing = sorted(expected - present)
    card = {'stage': STAGE, 'stage_name': NAME, 'passed': not missing and bool(source.get('passed')), 'authority': AUTHORITY_CLOSED, 'metrics': {'authority_rows': 0, 'added_nodes': added_nodes, 'added_edges': added_edges, 'graph_nodes': len(nodes), 'graph_edges': len(edges), 'missing_expected_nodes': len(missing), 'model_execution_authorized_next': False, 'decoder_ce_training_authorized_next': False, 'runtime_authorized': False, 'promotion_ready': False}, 'missing_expected_nodes': missing, 'artifacts': {'graph': str(full.relative_to(ROOT)), 'nodes_jsonl': str(np.relative_to(ROOT)), 'edges_jsonl': str(ep.relative_to(ROOT))}, 'decision': 'Low-level training mechanics attached to central graph.' if not missing else 'Low-level training mechanics graph attachment incomplete.', 'next_best_step': 'Recover runtime verifier loop or state-space repo-state compressor; keep training closed.', 'created_at_utc': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}
    (OUT_DIR / 'low_level_training_mechanics_graph_attachment_card.json').write_text(json.dumps(card, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    SUMMARY.write_text(json.dumps(card, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    DOC.write_text(f"# Stage {STAGE}: Low-Level Training Mechanics Graph Attachment\n\nPassed: `{card['passed']}`\n\n- added nodes: `{added_nodes}`\n- added edges: `{added_edges}`\n- graph nodes: `{len(nodes)}`\n- graph edges: `{len(edges)}`\n\nAll authority remains closed.\n", encoding='utf-8')
    write_registry(card)
    print(json.dumps(card, indent=2, sort_keys=True))


if __name__ == '__main__':
    main()
