#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from state_space_repo_state_compressor import selective_scan_compress

STAGE = 8708
NAME = 'stage8708_v27_state_space_repo_state_compressor_readiness'
SUMMARY = ROOT / 'runs/summaries/stage8708_state_space_repo_state_compressor_readiness.json'
OUT_DIR = ROOT / f'runs/local/artifacts/{NAME}'
DOC = ROOT / 'docs/STATE_SPACE_REPO_STATE_COMPRESSOR_READINESS_STAGE8708.md'
REGISTRY = ROOT / 'runs/local/artifacts/reconstructed_stage_registry.json'
AUTHORITY_CLOSED = {'model_execution_authorized_next': False, 'decoder_ce_training_authorized_next': False, 'denoise_ce_training_authorized_next': False, 'runtime_authorized': False, 'source_body_authorized': False, 'gemma_authorized': False, 'promotion_ready': False}


def run(cmd: list[str]) -> dict[str, Any]:
    result = subprocess.run(cmd, cwd=ROOT, text=True, capture_output=True)
    return {'cmd': cmd, 'returncode': result.returncode, 'passed': result.returncode == 0, 'stdout': result.stdout[-4000:], 'stderr': result.stderr[-4000:]}


def write_registry(card: dict[str, Any]) -> None:
    registry = json.loads(REGISTRY.read_text(encoding='utf-8')) if REGISTRY.exists() else {'stages': []}
    stages = [row for row in registry.get('stages', []) if row.get('stage') != STAGE]
    stages.append({'stage': STAGE, 'name': NAME, 'summary_path': str(SUMMARY), 'artifact_dir': str(OUT_DIR), 'passed': card['passed'], 'authority_rows': card['metrics']['authority_rows'], 'created_at': card['created_at']})
    registry['stages'] = sorted(stages, key=lambda row: int(row.get('stage', -1)))
    registry['latest_stage'] = STAGE
    registry['latest_name'] = NAME
    registry['latest_summary_path'] = str(SUMMARY)
    registry['updated_at'] = card['created_at']
    REGISTRY.parent.mkdir(parents=True, exist_ok=True)
    REGISTRY.write_text(json.dumps(registry, indent=2, sort_keys=True) + '\n', encoding='utf-8')


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)
    compile_result = run([sys.executable, '-m', 'py_compile', 'scripts/state_space_repo_state_compressor.py'])
    tests = run([sys.executable, '-m', 'pytest', '-q', 'tests/test_state_space_repo_state_compressor.py'])
    sample = selective_scan_compress([
        {'event_id': 'src', 'event_type': 'source', 'text': 'def repair(value): return value.strip()', 'importance': 0.8, 'retrieval_score': 0.9, 'grounding_score': 1.0, 'token_len': 9},
        {'event_id': 'err', 'event_type': 'error', 'text': 'AttributeError: NoneType has no strip', 'importance': 0.9, 'recency': 0.8, 'token_len': 8},
        {'event_id': 'leak', 'event_type': 'source', 'text': 'oracle target_body expected_answer', 'importance': 1.0, 'token_len': 4},
    ], state_dim=32, token_budget=64)
    passed = compile_result['passed'] and tests['passed'] and sample['passed'] and sample['events_dropped'] == 1 and len(sample['state_vector']) == 32
    card: dict[str, Any] = {
        'stage': STAGE,
        'name': NAME,
        'stage_name': NAME,
        'created_at': datetime.now(timezone.utc).isoformat(),
        'passed': passed,
        'authority': AUTHORITY_CLOSED,
        'checks': {'compile': compile_result, 'tests': tests},
        'sample_compression': sample,
        'metrics': {
            'authority_rows': 0,
            'model_execution_authorized_next': False,
            'decoder_ce_training_authorized_next': False,
            'denoise_ce_training_authorized_next': False,
            'runtime_authorized': False,
            'source_body_authorized': False,
            'gemma_authorized': False,
            'promotion_authorized': False,
            'state_dim': 32,
            'sample_events_seen': sample['events_seen'],
            'sample_events_accepted': sample['events_accepted'],
            'sample_events_dropped': sample['events_dropped'],
        },
        'remaining_missing_modules': ['gradient_activation_interpretability', 'graph_neural_repo_encoder', 'mixed_precision_runtime_contract', 'rubric_llm_judge_calibrator'],
        'decision': 'Deterministic state-space repo-state compressor recovered as ready_partial; actual Mamba/SSM training remains closed.' if passed else 'State-space compressor readiness failed.',
        'next_best_step': 'Attach compressor to central graph, then recover gradient/activation interpretability or judge calibration.',
    }
    (OUT_DIR / 'state_space_repo_state_compressor_readiness_card.json').write_text(json.dumps(card, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    SUMMARY.write_text(json.dumps(card, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    DOC.write_text(f"# Stage {STAGE}: State-Space Repo-State Compressor Readiness\n\nPassed: `{passed}`\n\n- state dim: `32`\n- sample accepted: `{sample['events_accepted']}`\n- sample dropped: `{sample['events_dropped']}`\n- tests passed: `{tests['passed']}`\n\nThis recovers a deterministic selective-scan-style compressor interface. It does not authorize Mamba training, model execution, runtime, decoder CE, denoise CE, source/body emission, Gemma, or promotion.\n", encoding='utf-8')
    write_registry(card)
    print(json.dumps(card, indent=2, sort_keys=True))


if __name__ == '__main__':
    main()
