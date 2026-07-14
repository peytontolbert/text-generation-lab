#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = 10164
NAME = 'stage10164_choice_aux_low_decoder_ce_target100m_execution_request'
OUT_DIR = ROOT / 'runs/local/artifacts' / NAME
REQUEST = OUT_DIR / 'choice_aux_low_decoder_ce_target100m_execution_request.json'
COMMAND_JSON = OUT_DIR / 'choice_aux_low_decoder_ce_target100m_command.json'
MANIFEST = OUT_DIR / 'choice_aux_low_decoder_ce_target100m_manifest.jsonl'
SUMMARY = ROOT / 'runs/summaries' / f'{NAME}.json'
PACKAGE = ROOT / 'runs/local/artifacts/stage10149_v27_standalone_compact_permutation_balanced_package/standalone_compact_permutation_balanced_package.json'
TRAINER = ROOT / 'legacy_src/scripts/train_agentkernel_lite_encdec.py'
MODEL_CONFIG = ROOT / 'configs/model/agentkernel_100m_seq2seq_recovered_target.json'
TOKENIZER_JSON = ROOT / 'configs/tokenizer/agentkernel_bpe_1506/tokenizer.json'
TOKENIZER_CONFIG = ROOT / 'configs/tokenizer/agentkernel_bpe_1506/tokenizer_config.json'
TOKENIZER_HASHLOCK = ROOT / 'configs/tokenizer/agentkernel_bpe_1506_recovered_pointer.json'
TMPDIR = Path('/data/tmp')
RUN_ID = 'stage10165_choice_aux_low_decoder_ce_target100m_probe'
OUTPUT_DIR = 'runs/local/artifacts/stage10165_choice_aux_low_decoder_ce_target100m_probe/bounded_decoder_probe'


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding='utf-8')) if path.exists() else {}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = []
    if not path.exists():
        return rows
    with path.open(encoding='utf-8') as handle:
        for line in handle:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def display(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def now_utc() -> str:
    return time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('w', encoding='utf-8') as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + '\n')


def merged_rows(package: dict[str, Any]) -> list[dict[str, Any]]:
    train = load_jsonl(ROOT / str(package.get('train_dataset_path') or ''))
    strict_eval = load_jsonl(ROOT / str(package.get('eval_dataset_path') or ''))
    return train + strict_eval


def command() -> list[str]:
    return [
        'env', f'TMPDIR={TMPDIR}', f'TEMP={TMPDIR}', f'TMP={TMPDIR}',
        'conda', 'run', '-n', 'trellis', 'python', str(TRAINER),
        '--repo-root', str(ROOT),
        '--manifest', str(MANIFEST),
        '--mode', 'bounded_decoder_ce_probe',
        '--probe-scale', 'target_100m',
        '--implementation', 'transformer',
        '--model-config', str(MODEL_CONFIG),
        '--tokenizer-json', str(TOKENIZER_JSON),
        '--tokenizer-config', str(TOKENIZER_CONFIG),
        '--tokenizer-hashlock', str(TOKENIZER_HASHLOCK),
        '--execution-authorized-for-recovery-probe',
        '--max-train-rows', '143',
        '--max-eval-rows', '0',
        '--max-strict-rows', '127',
        '--max-steps', '192',
        '--batch-size', '2',
        '--learning-rate', '5e-5',
        '--max-encoder-tokens', '768',
        '--max-decoder-tokens', '8',
        '--decoder-ce-weight', '0.25',
        '--bounded-choice-aux-weight', '1.0',
        '--structured-aux-weight', '0.0',
        '--denoise-weight', '0.0',
        '--eos-loss-weight', '4.0',
        '--enable-generation-audit',
        '--max-generation-rows', '16',
        '--max-generation-tokens', '8',
        '--require-loss-mask-enforcement-audit',
        '--no-final-checkpoint-export',
        '--cleanup-checkpoints-after-probe',
        '--skip-final-model-save', '1',
        '--output-dir', str(ROOT / OUTPUT_DIR),
        '--run-id', RUN_ID,
    ]


def build_request() -> dict[str, Any]:
    package = load_json(PACKAGE)
    rows = merged_rows(package)
    write_jsonl(MANIFEST, rows)
    cmd = command()
    split_counts = {'train': 0, 'eval': 0, 'strict_eval': 0, 'other': 0}
    language_counts: dict[str, int] = {}
    label_counts: dict[str, int] = {}
    for row in rows:
        split = str(row.get('split') or '')
        split_counts[split if split in split_counts else 'other'] += 1
        language = str(row.get('language_family') or '')
        language_counts[language] = language_counts.get(language, 0) + 1
        label = str(row.get('target_text') or '')
        label_counts[label] = label_counts.get(label, 0) + 1
    req = {
        'stage': STAGE,
        'stage_name': NAME,
        'created_at_utc': now_utc(),
        'passed': True,
        'source_package': display(PACKAGE),
        'manifest': display(MANIFEST),
        'rows': len(rows),
        'split_counts': split_counts,
        'language_counts': dict(sorted(language_counts.items())),
        'label_counts': dict(sorted(label_counts.items())),
        'command': cmd,
        'output_dir': OUTPUT_DIR,
        'run_id': RUN_ID,
        'request_status': 'execution_ready',
        'required_runtime_artifacts': [
            'execution_result.json',
            'bounded_choice_eval_audit_strict_eval.json',
            'sample_generation_audit.json',
            'failure_bucket_card.json',
            'cleanup_proof.json',
        ],
        'required_honesty_gates': [
            'stage10142 standalone decoder contract audit remains blocking until post-training rerun proves scoreability',
            'permutation-balanced package remains auxiliary and not a primary maintainer leaderboard',
            'bounded-choice eval is diagnostic and does not replace real maintainer bundle adjudication',
        ],
    }
    REQUEST.write_text(json.dumps(req, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    COMMAND_JSON.write_text(
        json.dumps({'command': cmd, 'cwd': str(ROOT), 'env': 'trellis', 'tmpdir': str(TMPDIR)}, indent=2, sort_keys=True) + '\n',
        encoding='utf-8',
    )
    SUMMARY.write_text(
        json.dumps(
            {
                'stage': STAGE,
                'passed': True,
                'request': display(REQUEST),
                'manifest': display(MANIFEST),
                'rows': len(rows),
                'split_counts': split_counts,
                'language_counts': dict(sorted(language_counts.items())),
            },
            indent=2,
            sort_keys=True,
        ) + '\n',
        encoding='utf-8',
    )
    return req


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    request = build_request()
    print(json.dumps({'stage': STAGE, 'passed': True, 'request': display(REQUEST), 'manifest': display(MANIFEST), 'rows': request['rows']}, indent=2, sort_keys=True))


if __name__ == '__main__':
    main()
