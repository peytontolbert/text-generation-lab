#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path

from cross_modal_alignment_audit import audit_alignment_rows
from modality_dropout_ablation_audit import audit_ablation_cards

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / 'runs/local/artifacts/stage8706_alignment_dropout_audit_readiness'
SUMMARY = ROOT / 'runs/summaries/stage8706_alignment_dropout_audit_readiness.json'
DOC = ROOT / 'docs/ALIGNMENT_DROPOUT_AUDIT_READINESS_STAGE8706.md'
AUTHORITY_CLOSED = {'model_execution_authorized_next': False, 'decoder_ce_training_authorized_next': False, 'runtime_authorized': False, 'source_emission_authorized': False, 'body_emission_authorized': False, 'gemma_execution_authorized_next': False, 'harness_execution_authorized_next': False, 'scoring_authorized_next': False, 'controller_complete_merge_authorized_next': False, 'promotion_ready': False}


def sample_alignment_rows() -> list[dict]:
    return [{
        'row_id': 'stage8706_alignment_ok',
        'modalities': {
            'source_text': {'source_hash': 'h1', 'path': 'src/app.py', 'node_id': 'file_1'},
            'cst_ast': {'source_hash': 'h1', 'nodes': [{'node_id': 'n1', 'path': 'src/app.py'}], 'edges': [{'src': 'n1', 'dst': 'n1'}]},
            'symbol_table': {'source_hash': 'h1', 'symbols': [{'symbol_id': 's1', 'path': 'src/app.py'}], 'edges': [{'src': 's1', 'dst': 'dep_x'}]},
            'import_export_graph': {'source_hash': 'h1', 'dependencies': [{'dependency_id': 'dep_x', 'path': 'src/app.py'}]},
            'type_signature_map': {'source_hash': 'h1', 'signatures': [{'signature_id': 't1', 'path': 'src/app.py'}]},
            'call_graph': {'source_hash': 'h1', 'call_nodes': [{'call_node_id': 'call_x', 'path': 'src/app.py'}], 'edges': [{'src': 'call_x', 'dst': 'call_y'}]},
            'data_flow_graph': {'source_hash': 'h1', 'data_nodes': [{'data_node_id': 'd1', 'path': 'src/app.py'}], 'edges': [{'src': 'd1', 'dst': 'd1'}]},
            'control_flow_graph': {'source_hash': 'h1', 'control_nodes': [{'control_node_id': 'c1', 'path': 'src/app.py'}], 'edges': [{'src': 'c1', 'dst': 'c1'}]},
        },
    }]


def sample_ablation_cards() -> list[dict]:
    return [{
        'objective': 'symbol_binding',
        'split': 'strict_eval',
        'full_score': 0.91,
        'majority_baseline': 0.33,
        'modality_scores': {'symbol_table': 0.70, 'call_graph': 0.62, 'runtime_trace': 0.58},
        'combo_scores': {'symbol_plus_call': 0.74},
        'dropout_scores': {'drop_symbol_table': 0.76, 'drop_call_graph': 0.80},
    }]


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    alignment = audit_alignment_rows(sample_alignment_rows())
    dropout = audit_ablation_cards(sample_ablation_cards())
    (OUT_DIR / 'sample_alignment_audit.json').write_text(json.dumps(alignment, indent=2, sort_keys=True) + '\n')
    (OUT_DIR / 'sample_dropout_ablation_audit.json').write_text(json.dumps(dropout, indent=2, sort_keys=True) + '\n')
    metrics = {
        'alignment_rows': alignment['rows'],
        'alignment_failing_rows': alignment['failing_rows'],
        'dropout_cards': dropout['cards'],
        'dropout_failing_cards': dropout['failing_cards'],
        'authority_rows': 0,
        **AUTHORITY_CLOSED,
    }
    passed = alignment['passed'] and dropout['passed']
    card = {'stage': 8706, 'name': 'stage8706_alignment_dropout_audit_readiness', 'stage_name': 'stage8706_alignment_dropout_audit_readiness', 'passed': passed, 'authority': AUTHORITY_CLOSED, 'metrics': metrics, 'decision': 'Recovered cross-modal alignment audit and modality dropout/ablation audit as deterministic no-authority support modules. They catch inconsistent modality packets and one-modality shortcut dominance before training/mining.', 'next_best_step': 'Attach cross-modal alignment and modality dropout audits to the central graph, then recover state-space repo compressor and gradient/activation interpretability.', 'created_at_utc': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}
    (OUT_DIR / 'alignment_dropout_audit_readiness_card.json').write_text(json.dumps(card, indent=2, sort_keys=True) + '\n')
    SUMMARY.write_text(json.dumps(card, indent=2, sort_keys=True) + '\n')
    DOC.write_text('\n'.join(['# Stage8706 Alignment/Dropout Audit Readiness', '', f'Passed: `{passed}`', '', 'Recovered deterministic support modules:', '', '- `cross_modal_alignment_audit`', '- `modality_dropout_ablation_audit`', '', 'These modules do not mine data, execute runtime, or train. They audit candidate manifests/cards before any training or mining can resume.', '', 'All authority remains closed.', '']))
    print(json.dumps(card, indent=2, sort_keys=True))
    return 0 if passed else 1

if __name__ == '__main__':
    raise SystemExit(main())
