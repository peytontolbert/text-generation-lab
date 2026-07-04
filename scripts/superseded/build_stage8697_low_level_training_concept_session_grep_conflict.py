#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SESSIONS = Path('/home/peyton/.codex/sessions')
STAGE = 8697
NAME = 'stage8697_v27_low_level_training_concept_session_grep'
OUT_DIR = ROOT / f'runs/local/artifacts/{NAME}'
SUMMARY = ROOT / 'runs/summaries/stage8697_low_level_training_concept_session_grep.json'
DOC = ROOT / 'docs/LOW_LEVEL_TRAINING_CONCEPT_SESSION_GREP_STAGE8697.md'
REGISTRY = ROOT / 'runs/local/artifacts/reconstructed_stage_registry.json'
AUTHORITY_CLOSED = {
    'model_execution_authorized_next': False,
    'decoder_ce_training_authorized_next': False,
    'denoise_ce_training_authorized_next': False,
    'runtime_authorized': False,
    'source_body_authorized': False,
    'gemma_authorized': False,
    'promotion_ready': False,
}

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


def iter_session_files() -> list[Path]:
    if not SESSIONS.exists():
        return []
    return sorted(SESSIONS.rglob('*.jsonl'))


def safe_line_text(line: str) -> str:
    try:
        payload = json.loads(line)
        return json.dumps(payload, sort_keys=True)[:3000]
    except Exception:
        return line[:3000]


def scan_group(files: list[Path], terms: list[str], *, max_hits: int = 60) -> dict[str, Any]:
    patterns = [re.compile(re.escape(term), re.IGNORECASE) for term in terms]
    hits: list[dict[str, Any]] = []
    files_hit: set[str] = set()
    for path in files:
        try:
            with path.open('r', encoding='utf-8', errors='ignore') as handle:
                for lineno, line in enumerate(handle, start=1):
                    matched = [term for term, pat in zip(terms, patterns) if pat.search(line)]
                    if not matched:
                        continue
                    files_hit.add(str(path))
                    if len(hits) < max_hits:
                        hits.append({'file': str(path), 'line': lineno, 'terms': matched, 'text': safe_line_text(line)})
                    break
        except OSError:
            continue
    return {'files_hit_count': len(files_hit), 'sample_files': sorted(files_hit)[:20], 'sample_hits': hits}


def current_docs_coverage(group: str, terms: list[str]) -> dict[str, Any]:
    search_roots = [ROOT / 'docs', ROOT / 'scripts', ROOT / 'legacy_src', ROOT / 'tests']
    files = []
    for base in search_roots:
        if base.exists():
            files.extend([p for p in base.rglob('*') if p.is_file() and p.suffix in {'.md', '.py', '.json', '.yaml', '.yml'}])
    term_hits = {term: 0 for term in terms}
    file_hits: set[str] = set()
    for path in files:
        try:
            text = path.read_text(encoding='utf-8', errors='ignore')
        except Exception:
            continue
        low = text.lower()
        any_hit = False
        for term in terms:
            count = low.count(term.lower())
            if count:
                term_hits[term] += count
                any_hit = True
        if any_hit:
            file_hits.add(str(path.relative_to(ROOT)))
    return {'term_hits': term_hits, 'files_hit_count': len(file_hits), 'sample_files': sorted(file_hits)[:30]}


def readiness_status(group: str, session_hits: dict[str, Any], docs_hits: dict[str, Any]) -> str:
    files_hit = docs_hits['files_hit_count']
    has_script = any(path.startswith('scripts/') or path.startswith('legacy_src/') for path in docs_hits['sample_files'])
    if files_hit == 0 and session_hits['files_hit_count'] > 0:
        return 'session_recovered_not_indexed'
    if files_hit > 0 and not has_script:
        return 'documented_not_executable'
    if has_script:
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
    files = iter_session_files()
    groups: dict[str, Any] = {}
    missing_index = []
    documented_not_executable = []
    for group, terms in CONCEPT_GROUPS.items():
        session = scan_group(files, terms)
        docs = current_docs_coverage(group, terms)
        status = readiness_status(group, session, docs)
        groups[group] = {'terms': terms, 'session': session, 'current_recovery': docs, 'status': status}
        (OUT_DIR / f'{group}.json').write_text(json.dumps(groups[group], indent=2, sort_keys=True) + '\n', encoding='utf-8')
        if status == 'session_recovered_not_indexed':
            missing_index.append(group)
        if status == 'documented_not_executable':
            documented_not_executable.append(group)
    card = {
        'stage': STAGE,
        'stage_name': NAME,
        'passed': True,
        'authority': AUTHORITY_CLOSED,
        'session_files_scanned': len(files),
        'groups': groups,
        'metrics': {
            'authority_rows': 0,
            'groups': len(groups),
            'session_recovered_not_indexed': len(missing_index),
            'documented_not_executable': len(documented_not_executable),
            'model_execution_authorized_next': False,
            'decoder_ce_training_authorized_next': False,
            'runtime_authorized': False,
            'promotion_ready': False,
        },
        'missing_index_groups': missing_index,
        'documented_not_executable_groups': documented_not_executable,
        'decision': 'Low-level tensor/training concept grep completed; use missing/documented groups to update model-stack spine and support-module recovery queue.',
        'next_best_step': 'Build a low-level training mechanics spine patch and attach it to central graph; prioritize executable modules only for telemetry, context, runtime verifier, and state-space compressor.',
        'created_at_utc': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
    }
    (OUT_DIR / 'low_level_training_concept_session_grep_card.json').write_text(json.dumps(card, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    SUMMARY.write_text(json.dumps(card, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    lines = [f'# Stage {STAGE}: Low-Level Training Concept Session Grep', '', f'Passed: `{card["passed"]}`', '', f'Session files scanned: `{len(files)}`', '', '## Status By Group', '']
    for group, data in groups.items():
        lines.append(f'- `{group}`: `{data["status"]}`; session files `{data["session"]["files_hit_count"]}`; recovered files `{data["current_recovery"]["files_hit_count"]}`')
    lines.extend(['', '## Missing Index Groups', '', *(f'- `{g}`' for g in missing_index), '', '## Documented But Not Executable', '', *(f'- `{g}`' for g in documented_not_executable), '', 'All authority remains closed.', ''])
    DOC.write_text('\n'.join(lines), encoding='utf-8')
    write_registry(card)
    print(json.dumps(card, indent=2, sort_keys=True))


if __name__ == '__main__':
    main()
