#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'runs/local/artifacts/stage8711_gradient_activation_interpretability_graph_attachment/central_research_graph_with_gradient_activation_interpretability.json'
SOURCE = ROOT / 'runs/summaries/stage8712_mixed_precision_runtime_contract_readiness.json'
STAGE = 8713
NAME = 'stage8713_mixed_precision_runtime_contract_graph_attachment'
OUT_DIR = ROOT / f'runs/local/artifacts/{NAME}'
SUMMARY = ROOT / 'runs/summaries/stage8713_mixed_precision_runtime_contract_graph_attachment.json'
DOC = ROOT / 'docs/MIXED_PRECISION_RUNTIME_CONTRACT_GRAPH_ATTACHMENT_STAGE8713.md'
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
    support = 'support_module:mixed_precision_runtime_contract'
    exec_node = 'control_execution:stage8712_mixed_precision_runtime_contract_readiness'
    added_nodes = 0
    added_edges = 0
    added_nodes += int(add_node(nodes, {'id': support, 'kind': 'support_module', 'name': 'mixed_precision_runtime_contract', 'role': 'contract-only fp32/bf16/fp16 precision and memory policy with autocast/GradScaler validation', 'status': 'ready_partial_contract_only', 'summary': str(SOURCE.relative_to(ROOT)), 'authority': AUTHORITY_CLOSED}))
    added_nodes += int(add_node(nodes, {'id': exec_node, 'kind': 'control_execution', 'name': 'stage8712_mixed_precision_runtime_contract_readiness', 'passed': source.get('passed'), 'metrics': source.get('metrics', {}), 'authority': AUTHORITY_CLOSED}))
    for src, rel, dst in [
        (exec_node, 'implements_or_audits', support),
        (support, 'supports', 'training_mechanics:mixed_precision_memory'),
        (support, 'constrains', 'training_mechanics:optimizer_scheduler'),
        (support, 'constrains', 'training_mechanics:checkpoint_reproducibility'),
        (support, 'precedes', 'control_execution:future_authorized_training_probe'),
        (support, 'does_not_authorize', 'authority:model_execution'),
        (support, 'does_not_authorize', 'authority:training'),
    ]:
        added_edges += int(add_edge(edges, src, rel, dst))
    graph['nodes'] = nodes
    graph['edges'] = edges
    graph['version'] = NAME
    graph['generated_at'] = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
    graph['authority'] = AUTHORITY_CLOSED
    full = OUT_DIR / 'central_research_graph_with_mixed_precision_runtime_contract.json'
    np = OUT_DIR / 'central_research_graph_with_mixed_precision_runtime_contract_nodes.jsonl'
    ep = OUT_DIR / 'central_research_graph_with_mixed_precision_runtime_contract_edges.jsonl'
    full.write_text(json.dumps(graph, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    write_jsonl(np, nodes)
    write_jsonl(ep, edges)
    present = {node.get('id') for node in nodes}
    missing = sorted({support, exec_node} - present)
    card = {'stage': STAGE, 'stage_name': NAME, 'passed': not missing and bool(source.get('passed')), 'authority': AUTHORITY_CLOSED, 'metrics': {'authority_rows': 0, 'added_nodes': added_nodes, 'added_edges': added_edges, 'graph_nodes': len(nodes), 'graph_edges': len(edges), 'missing_expected_nodes': len(missing), 'model_execution_authorized_next': False, 'decoder_ce_training_authorized_next': False, 'runtime_authorized': False, 'promotion_ready': False}, 'missing_expected_nodes': missing, 'artifacts': {'graph': str(full.relative_to(ROOT)), 'nodes_jsonl': str(np.relative_to(ROOT)), 'edges_jsonl': str(ep.relative_to(ROOT))}, 'decision': 'Mixed-precision runtime contract attached to central graph; execution/training remains closed.' if not missing else 'Mixed-precision graph attachment incomplete.', 'next_best_step': 'Recover graph neural repo encoder or rubric judge calibration; keep training closed.', 'created_at_utc': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}
    (OUT_DIR / 'mixed_precision_runtime_contract_graph_attachment_card.json').write_text(json.dumps(card, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    SUMMARY.write_text(json.dumps(card, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    DOC.write_text(f"# Stage {STAGE}: Mixed-Precision Runtime Contract Graph Attachment\n\nPassed: `{card['passed']}`\n\n- added nodes: `{added_nodes}`\n- added edges: `{added_edges}`\n- graph nodes: `{len(nodes)}`\n- graph edges: `{len(edges)}`\n\nAll authority remains closed.\n", encoding='utf-8')
    write_registry(card)
    print(json.dumps(card, indent=2, sort_keys=True))


if __name__ == '__main__':
    main()
