#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'runs/local/artifacts/stage8707_alignment_dropout_graph_attachment/central_research_graph_with_alignment_dropout.json'
SOURCE = ROOT / 'runs/summaries/stage8708_state_space_repo_state_compressor_readiness.json'
STAGE = 8709
NAME = 'stage8709_v27_state_space_repo_state_compressor_graph_attachment'
OUT_DIR = ROOT / f'runs/local/artifacts/{NAME}'
SUMMARY = ROOT / 'runs/summaries/stage8709_state_space_repo_state_compressor_graph_attachment.json'
DOC = ROOT / 'docs/STATE_SPACE_REPO_STATE_COMPRESSOR_GRAPH_ATTACHMENT_STAGE8709.md'
REGISTRY = ROOT / 'runs/local/artifacts/reconstructed_stage_registry.json'
AUTHORITY_CLOSED = {'model_execution_authorized_next': False, 'decoder_ce_training_authorized_next': False, 'denoise_ce_training_authorized_next': False, 'runtime_authorized': False, 'source_body_authorized': False, 'gemma_authorized': False, 'promotion_ready': False}


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
    support = 'support_module:state_space_repo_state_compressor'
    exec_node = 'control_execution:stage8708_state_space_repo_state_compressor_readiness'
    added_nodes += int(add_node(nodes, {'id': support, 'kind': 'support_module', 'name': 'state_space_repo_state_compressor', 'role': 'deterministic selective-scan-style compression from repo/log/history stream to compressed_repo_state packet', 'status': 'ready_partial_mamba_training_closed', 'summary': str(SOURCE.relative_to(ROOT)), 'authority': AUTHORITY_CLOSED}))
    added_nodes += int(add_node(nodes, {'id': exec_node, 'kind': 'control_execution', 'name': 'stage8708_state_space_repo_state_compressor_readiness', 'passed': source.get('passed'), 'metrics': source.get('metrics', {}), 'authority': AUTHORITY_CLOSED}))
    links = [
        (exec_node, 'implements_or_audits', support),
        (support, 'uses', 'support_module:context_packer_v1'),
        (support, 'feeds', 'architecture_layer:encoder_decoder_seq2seq'),
        (support, 'future_enables', 'model_family:state_space_mamba'),
        (support, 'supports', 'training_mechanics:state_space_scan'),
        (support, 'protects', 'control_card:leakage:source_lineage_guard'),
        (support, 'outputs', 'data_packet:compressed_repo_state'),
    ]
    for source_id, relation, target in links:
        added_edges += int(add_edge(edges, source_id, relation, target))
    graph['nodes'] = nodes
    graph['edges'] = edges
    graph['version'] = NAME
    graph['generated_at'] = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
    graph['authority'] = AUTHORITY_CLOSED
    full = OUT_DIR / 'central_research_graph_with_state_space_repo_state_compressor.json'
    np = OUT_DIR / 'central_research_graph_with_state_space_repo_state_compressor_nodes.jsonl'
    ep = OUT_DIR / 'central_research_graph_with_state_space_repo_state_compressor_edges.jsonl'
    full.write_text(json.dumps(graph, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    write_jsonl(np, nodes)
    write_jsonl(ep, edges)
    present = {node.get('id') for node in nodes}
    missing = sorted({support, exec_node} - present)
    card = {'stage': STAGE, 'name': NAME, 'stage_name': NAME, 'passed': not missing and bool(source.get('passed')), 'authority': AUTHORITY_CLOSED, 'metrics': {'authority_rows': 0, 'added_nodes': added_nodes, 'added_edges': added_edges, 'graph_nodes': len(nodes), 'graph_edges': len(edges), 'missing_expected_nodes': len(missing), 'model_execution_authorized_next': False, 'decoder_ce_training_authorized_next': False, 'runtime_authorized': False, 'promotion_ready': False}, 'missing_expected_nodes': missing, 'artifacts': {'graph': str(full.relative_to(ROOT)), 'nodes_jsonl': str(np.relative_to(ROOT)), 'edges_jsonl': str(ep.relative_to(ROOT))}, 'decision': 'State-space repo-state compressor attached to central graph; Mamba training remains closed.' if not missing else 'State-space compressor graph attachment incomplete.', 'next_best_step': 'Recover gradient/activation interpretability or rubric judge calibration; keep training closed.', 'created_at_utc': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}
    (OUT_DIR / 'state_space_repo_state_compressor_graph_attachment_card.json').write_text(json.dumps(card, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    SUMMARY.write_text(json.dumps(card, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    DOC.write_text(f"# Stage {STAGE}: State-Space Repo-State Compressor Graph Attachment\n\nPassed: `{card['passed']}`\n\n- added nodes: `{added_nodes}`\n- added edges: `{added_edges}`\n- graph nodes: `{len(nodes)}`\n- graph edges: `{len(edges)}`\n\nAll authority remains closed.\n", encoding='utf-8')
    write_registry(card)
    print(json.dumps(card, indent=2, sort_keys=True))


if __name__ == '__main__':
    main()
