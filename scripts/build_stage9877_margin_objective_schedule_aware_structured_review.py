#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import subprocess
import time
from pathlib import Path
from typing import Any

try:
    from diagnostic_ticket_contract import AUTHORITY_CLOSED
except ModuleNotFoundError:
    from scripts.diagnostic_ticket_contract import AUTHORITY_CLOSED  # type: ignore

ROOT = Path(__file__).resolve().parents[1]
STAGE = 9877
NAME = 'stage9877_margin_objective_schedule_aware_structured_review'
SOURCE_SUMMARY = ROOT / 'runs/summaries/stage9875_margin_objective_target_100m_contract_only_preflight.json'
SOURCE_MANIFEST_DIR = ROOT / 'runs/local/artifacts/stage9875_margin_objective_target_100m_contract_only_preflight/manifests'
OUT_DIR = ROOT / 'runs/local/artifacts' / NAME
RUNS_DIR = OUT_DIR / 'surface_runs'
AUDIT = OUT_DIR / 'margin_objective_schedule_aware_structured_review_audit.json'
SUMMARY = ROOT / 'runs/summaries' / f'{NAME}.json'
DOC = ROOT / 'docs' / 'MARGIN_OBJECTIVE_SCHEDULE_AWARE_STRUCTURED_REVIEW_STAGE9877.md'
REGISTRY = ROOT / 'runs/local/artifacts/reconstructed_stage_registry.json'
TRAINER = ROOT / 'legacy_src/scripts/train_agentkernel_lite_encdec.py'
MODEL_CONFIG = ROOT / 'configs/model/agentkernel_100m_seq2seq_recovered_target.json'
TOKENIZER_JSON = ROOT / 'configs/tokenizer/agentkernel_bpe_1506/tokenizer.json'
TOKENIZER_CONFIG = ROOT / 'configs/tokenizer/agentkernel_bpe_1506/tokenizer_config.json'
TOKENIZER_HASHLOCK = ROOT / 'configs/tokenizer/agentkernel_bpe_1506_recovered_pointer.json'
TMPDIR = Path('/data/tmp')
SURFACES = {
    'symbol_binding': {
        'mode': 'symbol_binding_probe',
        'field': 'symbol_binding',
        'max_steps': 8,
        'eval_interval': 0,
        'restore_best': False,
    },
    'edit_localization': {
        'mode': 'edit_localization_probe',
        'field': 'edit_localization',
        'max_steps': 32,
        'eval_interval': 1,
        'restore_best': True,
    },
    'patch_operator_selection': {
        'mode': 'patch_operator_probe',
        'field': 'patch_operator',
        'max_steps': 8,
        'eval_interval': 0,
        'restore_best': False,
    },
    'verifier_failure_repair_or_abstain': {
        'mode': 'verifier_repair_probe',
        'field': 'verifier_repair',
        'max_steps': 8,
        'eval_interval': 0,
        'restore_best': False,
    },
}


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding='utf-8')) if path.exists() else {}


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines() if line.strip()]


def update_registry(summary: dict[str, Any]) -> None:
    registry = load_json(REGISTRY) or {'rows': [], 'metrics': {}}
    rows = [row for row in registry.get('rows', []) if row.get('stage') != STAGE and row.get('stage_name') != NAME]
    rows.append(
        {
            'stage': STAGE,
            'stage_name': NAME,
            'passed': summary['passed'],
            'path': str(SUMMARY),
            'authority': dict(AUTHORITY_CLOSED),
            'next_best_step': summary['next_best_step'],
        }
    )
    registry['rows'] = sorted(rows, key=lambda row: (int(row.get('stage', -1)), row.get('stage_name', '')))
    registry['passed'] = bool(registry['rows'])
    registry['metrics'] = {
        **(registry.get('metrics') or {}),
        'latest_stage': STAGE,
        'latest_stage_name': NAME,
        'latest_stage_next_best_step': summary['next_best_step'],
        'max_stage': STAGE,
        'registry_rows': len(registry['rows']),
    }
    REGISTRY.write_text(json.dumps(registry, indent=2, sort_keys=True) + '\n', encoding='utf-8')


def split_counts(rows: list[dict[str, Any]]) -> dict[str, int]:
    out = {'train': 0, 'eval': 0, 'strict_eval': 0}
    for row in rows:
        split = str(row.get('split') or 'other')
        if split in out:
            out[split] += 1
    return out


def trainer_command(surface: str, manifest: Path, rows: list[dict[str, Any]]) -> list[str]:
    counts = split_counts(rows)
    spec = SURFACES[surface]
    out_dir = RUNS_DIR / surface
    cmd = [
        'conda', 'run', '-n', 'trellis', 'python', str(TRAINER),
        '--repo-root', str(ROOT),
        '--manifest', str(manifest.relative_to(ROOT)),
        '--mode', spec['mode'],
        '--probe-scale', 'target_100m',
        '--implementation', 'transformer',
        '--model-config', str(MODEL_CONFIG.relative_to(ROOT)),
        '--tokenizer-json', str(TOKENIZER_JSON.relative_to(ROOT)),
        '--tokenizer-config', str(TOKENIZER_CONFIG.relative_to(ROOT)),
        '--tokenizer-hashlock', str(TOKENIZER_HASHLOCK.relative_to(ROOT)),
        '--max-train-rows', str(counts['train']),
        '--max-eval-rows', str(counts['eval']),
        '--max-strict-rows', str(counts['strict_eval']),
        '--max-steps', str(spec['max_steps']),
        '--batch-size', '2',
        '--learning-rate', '5e-5',
        '--max-encoder-tokens', '512',
        '--max-decoder-tokens', '8',
        '--decoder-ce-weight', '0.0',
        '--structured-aux-weight', '1.0',
        '--denoise-weight', '0.0',
        '--require-loss-mask-enforcement-audit',
        '--no-final-checkpoint-export',
        '--cleanup-checkpoints-after-probe',
        '--skip-final-model-save', '1',
        '--output-dir', str(out_dir.relative_to(ROOT)),
        '--run-id', f'{NAME}_{surface}',
        '--execution-authorized-for-recovery-probe',
    ]
    if spec['eval_interval']:
        cmd.extend(['--eval-interval', str(spec['eval_interval'])])
    if spec['restore_best']:
        cmd.append('--restore-best-structured-state')
    return cmd


def extract_metrics(surface: str, result: dict[str, Any]) -> dict[str, Any]:
    eval_card = result.get('eval') if isinstance(result.get('eval'), dict) else {}
    field = SURFACES[surface]['field']
    out: dict[str, Any] = {}
    for split in ('eval', 'strict_eval'):
        split_card = eval_card.get(split) if isinstance(eval_card.get(split), dict) else {}
        out[f'{split}_exact'] = ((((split_card.get('field_exact') or {}).get(field)) or {}).get('exact'))
    out['best_state_selection'] = result.get('best_state_selection')
    return out


def run_surface(surface: str) -> dict[str, Any]:
    manifest = SOURCE_MANIFEST_DIR / f'{surface}.jsonl'
    rows = read_jsonl(manifest)
    env = dict(os.environ)
    env.update({'TMPDIR': str(TMPDIR), 'TEMP': str(TMPDIR), 'TMP': str(TMPDIR)})
    run = subprocess.run(trainer_command(surface, manifest, rows), cwd=ROOT, env=env, text=True, capture_output=True, check=False)
    out_dir = RUNS_DIR / surface
    result = load_json(out_dir / 'execution_result.json')
    metrics = extract_metrics(surface, result)
    return {
        'surface': surface,
        'rows': len(rows),
        'trainer_returncode': run.returncode,
        'passed': run.returncode == 0 and bool(result.get('required_artifacts_written')),
        'schedule': {k: SURFACES[surface][k] for k in ('max_steps', 'eval_interval', 'restore_best')},
        **metrics,
        'stdout_tail': run.stdout[-2000:],
        'stderr_tail': run.stderr[-2000:],
    }


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    RUNS_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)
    source = load_json(SOURCE_SUMMARY)
    failures: list[str] = []
    if source.get('passed') is not True:
        failures.append('stage9875_not_passed')
    surface_results = []
    if not failures:
        for surface in SURFACES:
            res = run_surface(surface)
            surface_results.append(res)
            if not res['passed']:
                failures.append(f'surface_execution_failed:{surface}')
    compact_results = [{k: v for k, v in row.items() if k not in {'stdout_tail', 'stderr_tail'}} for row in surface_results]
    audit = {'passed': not failures, 'failures': failures, 'surface_results': compact_results, 'authority': dict(AUTHORITY_CLOSED)}
    AUDIT.write_text(json.dumps(audit, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    next_step = 'Use this schedule-aware broader review to decide whether edit localization is now strong enough to rerun the broader standalone Gemma ledger, and whether symbol binding needs its own objective upgrade.'
    summary = {
        'stage': STAGE,
        'stage_name': NAME,
        'name': NAME,
        'passed': not failures,
        'authority': dict(AUTHORITY_CLOSED),
        'metrics': {**dict(AUTHORITY_CLOSED), 'failures': failures, 'surface_results': compact_results},
        'artifacts': {'audit': str(AUDIT.relative_to(ROOT)), 'run_dir': str(RUNS_DIR.relative_to(ROOT)), 'doc': str(DOC.relative_to(ROOT))},
        'decision': 'Executed a schedule-aware target-100M structured review on the refreshed Stage9874 mix, giving edit localization the longer best-state schedule from the winning Stage9872 path while keeping the guardrail surfaces on short probes.',
        'next_best_step': next_step,
        'created_at_utc': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    DOC.write_text(
        '\n'.join(
            [
                '# Stage9877 Margin Objective Schedule-Aware Structured Review',
                '',
                f'Passed: `{summary["passed"]}`',
                f'Failures: `{failures}`',
                f'Surfaces: `{compact_results}`',
                '',
                'This stage reuses the refreshed Stage9874/9875 chain but stops undertraining edit localization by applying the longer best-state schedule that produced the Stage9872 same-surface multilingual win.',
                '',
                'No runtime, source/body emission, hidden scoring, final checkpoint export, or promotion is authorized.',
                '',
                f'Next: {next_step}',
                '',
            ]
        ) + '\n',
        encoding='utf-8',
    )
    if summary['passed']:
        update_registry(summary)
    print(json.dumps({'stage': STAGE, 'passed': summary['passed'], 'failures': failures, 'surface_results': compact_results}, indent=2, sort_keys=True))
    if failures:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
