#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import subprocess
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SESSIONS = Path('/home/peyton/.codex/sessions')
STAGE = 8703
NAME = 'stage8703_v27_low_level_training_concept_session_grep'
OUT_DIR = ROOT / f'runs/local/artifacts/{NAME}'
SUMMARY = ROOT / 'runs/summaries/stage8703_low_level_training_concept_session_grep.json'
DOC = ROOT / 'docs/LOW_LEVEL_TRAINING_CONCEPT_SESSION_GREP_STAGE8703.md'
REGISTRY = ROOT / 'runs/local/artifacts/reconstructed_stage_registry.json'
AUTHORITY_CLOSED = {'model_execution_authorized_next': False, 'decoder_ce_training_authorized_next': False, 'denoise_ce_training_authorized_next': False, 'runtime_authorized': False, 'source_body_authorized': False, 'gemma_authorized': False, 'promotion_ready': False}
CONCEPT_GROUPS: dict[str, list[str]] = {
    'tensor_shapes_dtype_device': ['tensor', 'shape', 'dtype', 'device', 'broadcast', 'contiguous'],
    'matmul_linear_projection': ['matmul', 'matrix multiplication', 'dot product', 'linear layer', 'projection'],
    'embedding_tokenization': ['embedding', 'token embedding', 'tied embedding', 'tokenizer', 'vocab'],
    'attention_qkv': ['attention', 'qkv', 'query key value', 'causal mask', 'cross attention'],
    'positional_encoding_rope': ['positional encoding', 'position encoding', 'rotary', 'rope', 'sinusoidal'],
    'mlp_activation_norm': ['mlp', 'feed forward', 'gelu', 'silu', 'layernorm', 'rmsnorm', 'normalization'],
    'loss_logits_ce': ['logits', 'cross entropy', 'ce loss', 'loss mask', 'per token loss'],
    'autograd_backward_gradients': ['autograd', 'backward', 'gradient', 'grad norm', 'clip_grad', 'gradient clipping'],
    'optimizer_scheduler': ['optimizer', 'adamw', 'scheduler', 'warmup', 'cosine', 'weight decay'],
    'dataloader_batching': ['dataloader', 'dataset', 'batch', 'shuffle', 'collate'],
    'checkpoint_reproducibility': ['checkpoint', 'seed', 'reproducibility', 'state_dict', 'resume'],
    'mixed_precision_memory': ['mixed precision', 'fp16', 'bf16', 'grad scaler', 'activation checkpoint'],
    'calibration_entropy_confidence': ['calibration', 'entropy', 'confidence', 'margin', 'ood'],
    'activation_interpretability': ['activation', 'logit lens', 'activation patch', 'sae', 'sparse autoencoder'],
    'state_space_scan': ['state space', 'selective scan', 'mamba', 'ssm'],
    'graph_gnn': ['gnn', 'graph neural', 'message passing', 'call graph', 'dependency graph'],
    'denoise_diffusion': ['denoise', 'diffusion', 'masked diffusion', 'mask token', 'iterative repair'],
    'dataset_cartography_attribution': ['dataset cartography', 'forgetting event', 'data attribution', 'influence', 'trac', 'grand', 'el2n'],
}


def rg_group(root: Path, terms: list[str], *, max_count: int = 80, timeout: int = 25) -> dict[str, Any]:
    pattern = '|'.join(re.escape(term) for term in terms)
    if not root.exists():
        return {'available': False, 'returncode': None, 'line_count': 0, 'sample_files': [], 'sample_lines': [], 'timeout': False}
    cmd = ['rg', '-i', '-n', '--no-heading', '-m', str(max_count), '-e', pattern, str(root)]
    try:
        res = subprocess.run(cmd, text=True, capture_output=True, timeout=timeout)
    except subprocess.TimeoutExpired as exc:
        text = (exc.stdout or '') if isinstance(exc.stdout, str) else ''
        lines = text.splitlines()[:max_count]
        return {'available': True, 'returncode': 'timeout', 'line_count': len(lines), 'sample_files': sorted({line.split(':', 1)[0] for line in lines})[:20], 'sample_lines': lines[:40], 'timeout': True}
    lines = res.stdout.splitlines()[:max_count]
    return {'available': True, 'returncode': res.returncode, 'line_count': len(lines), 'sample_files': sorted({line.split(':', 1)[0] for line in lines})[:20], 'sample_lines': lines[:40], 'timeout': False}


def coverage_status(session: dict[str, Any], recovered: dict[str, Any]) -> str:
    if recovered['line_count'] == 0 and session['line_count'] > 0:
        return 'session_recovered_not_indexed'
    if recovered['line_count'] > 0 and not any('/scripts/' in f or '/legacy_src/' in f or f.startswith('scripts/') or f.startswith('legacy_src/') for f in recovered['sample_files']):
        return 'documented_not_executable'
    if recovered['line_count'] > 0:
        return 'indexed_or_partially_executable'
    return 'not_recovered'


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
    recovered_root = ROOT
    groups: dict[str, Any] = {}
    missing_index = []
    documented_not_executable = []
    for group, terms in CONCEPT_GROUPS.items():
        session = rg_group(SESSIONS, terms)
        recovered = rg_group(recovered_root, terms)
        status = coverage_status(session, recovered)
        groups[group] = {'terms': terms, 'session': session, 'current_recovery': recovered, 'status': status}
        (OUT_DIR / f'{group}.json').write_text(json.dumps(groups[group], indent=2, sort_keys=True) + '\n', encoding='utf-8')
        if status == 'session_recovered_not_indexed':
            missing_index.append(group)
        if status == 'documented_not_executable':
            documented_not_executable.append(group)
    card = {'stage': STAGE, 'stage_name': NAME, 'passed': True, 'authority': AUTHORITY_CLOSED, 'groups': groups, 'metrics': {'authority_rows': 0, 'groups': len(groups), 'session_recovered_not_indexed': len(missing_index), 'documented_not_executable': len(documented_not_executable), 'model_execution_authorized_next': False, 'decoder_ce_training_authorized_next': False, 'runtime_authorized': False, 'promotion_ready': False}, 'missing_index_groups': missing_index, 'documented_not_executable_groups': documented_not_executable, 'decision': 'rg-based low-level tensor/training concept recovery grep completed.', 'next_best_step': 'Patch low-level training mechanics spine, then attach to graph. Prioritize executable recovery for state-space compressor, runtime verifier, and judge calibration.', 'created_at_utc': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}
    (OUT_DIR / 'low_level_training_concept_session_grep_card.json').write_text(json.dumps(card, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    SUMMARY.write_text(json.dumps(card, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    lines = [f'# Stage {STAGE}: Low-Level Training Concept Session Grep', '', f'Passed: `{card["passed"]}`', '', '## Status By Group', '']
    for group, data in groups.items():
        lines.append(f'- `{group}`: `{data["status"]}`; session lines `{data["session"]["line_count"]}`; recovered lines `{data["current_recovery"]["line_count"]}`')
    lines.extend(['', '## Missing Index Groups', '', *(f'- `{g}`' for g in missing_index), '', '## Documented But Not Executable', '', *(f'- `{g}`' for g in documented_not_executable), '', 'All authority remains closed.', ''])
    DOC.write_text('\n'.join(lines), encoding='utf-8')
    write_registry(card)
    print(json.dumps(card, indent=2, sort_keys=True))


if __name__ == '__main__':
    main()
