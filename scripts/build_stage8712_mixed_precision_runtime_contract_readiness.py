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
from mixed_precision_runtime_contract import MixedPrecisionRequest, build_precision_policy_card, safe_default_policy

STAGE = 8712
NAME = 'stage8712_mixed_precision_runtime_contract_readiness'
SUMMARY = ROOT / 'runs/summaries/stage8712_mixed_precision_runtime_contract_readiness.json'
OUT_DIR = ROOT / f'runs/local/artifacts/{NAME}'
DOC = ROOT / 'docs/MIXED_PRECISION_RUNTIME_CONTRACT_READINESS_STAGE8712.md'
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
    compile_result = run([sys.executable, '-m', 'py_compile', 'scripts/mixed_precision_runtime_contract.py'])
    tests = run([sys.executable, '-m', 'pytest', '-q', 'tests/test_mixed_precision_runtime_contract.py'])
    safe = safe_default_policy()
    bf16_contract = build_precision_policy_card(
        MixedPrecisionRequest(precision='bf16', device='cuda', use_autocast=True, model_execution_authorized=False, training_authorized=False, max_memory_mb=1024),
        parameter_count=102_654_362,
        sequence_tokens=2048,
        hidden_dim=640,
        batch_size=1,
    )
    invalid_fp16 = build_precision_policy_card(
        MixedPrecisionRequest(precision='fp16', device='cuda', use_autocast=True, training_authorized=True, use_grad_scaler=False),
        parameter_count=102_654_362,
        sequence_tokens=2048,
        hidden_dim=640,
        batch_size=1,
    )
    passed = compile_result['passed'] and tests['passed'] and safe['passed'] and bf16_contract['passed'] and not invalid_fp16['passed']
    card: dict[str, Any] = {
        'stage': STAGE,
        'name': NAME,
        'created_at': datetime.now(timezone.utc).isoformat(),
        'passed': passed,
        'authority': AUTHORITY_CLOSED,
        'checks': {'compile': compile_result, 'tests': tests},
        'sample_policies': {'safe_default_fp32': safe, 'bf16_contract_only': bf16_contract, 'invalid_fp16_training_without_scaler': invalid_fp16},
        'metrics': {
            'authority_rows': 0,
            'model_execution_authorized_next': False,
            'decoder_ce_training_authorized_next': False,
            'denoise_ce_training_authorized_next': False,
            'runtime_authorized': False,
            'source_body_authorized': False,
            'gemma_authorized': False,
            'promotion_authorized': False,
            'safe_default_total_mb': safe['memory_estimate']['total_estimated_mb'],
            'bf16_contract_total_mb': bf16_contract['memory_estimate']['total_estimated_mb'],
        },
        'remaining_missing_modules': ['graph_neural_repo_encoder', 'rubric_llm_judge_calibrator'],
        'decision': 'Mixed-precision runtime contract recovered as ready_partial contract-only; no execution/training authority opened.' if passed else 'Mixed-precision runtime contract readiness failed.',
        'next_best_step': 'Attach mixed-precision contract to central graph, then recover graph neural repo encoder or judge calibration.',
    }
    (OUT_DIR / 'mixed_precision_runtime_contract_readiness_card.json').write_text(json.dumps(card, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    SUMMARY.write_text(json.dumps(card, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    DOC.write_text(f"# Stage {STAGE}: Mixed-Precision Runtime Contract Readiness\n\nPassed: `{passed}`\n\n- safe default total MB: `{safe['memory_estimate']['total_estimated_mb']:.2f}`\n- bf16 contract total MB: `{bf16_contract['memory_estimate']['total_estimated_mb']:.2f}`\n- invalid fp16 training rejected: `{not invalid_fp16['passed']}`\n- tests passed: `{tests['passed']}`\n\nThis is contract-only. It does not authorize model execution, training, runtime, decoder CE, denoise CE, source/body emission, Gemma, or promotion.\n", encoding='utf-8')
    write_registry(card)
    print(json.dumps(card, indent=2, sort_keys=True))


if __name__ == '__main__':
    main()
