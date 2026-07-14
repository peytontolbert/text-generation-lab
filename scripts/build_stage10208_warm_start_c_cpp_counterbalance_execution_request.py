#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = 10208
NAME = "stage10208_warm_start_c_cpp_counterbalance_execution_request"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
REQUEST = OUT_DIR / "warm_start_c_cpp_counterbalance_execution_request.json"
COMMAND_JSON = OUT_DIR / "warm_start_c_cpp_counterbalance_command.json"
MANIFEST = OUT_DIR / "warm_start_c_cpp_counterbalance_manifest.jsonl"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
PACKAGE = ROOT / "runs/local/artifacts/stage10204_c_cpp_abstention_counterbalance_package/c_cpp_abstention_counterbalance_package.json"
INIT_RUNTIME = ROOT / "runs/local/artifacts/stage10202_targeted_contrast_target100m_probe/runtime_model/runtime_model_bundle.json"
TRAINER = ROOT / "legacy_src/scripts/train_agentkernel_lite_encdec.py"
MODEL_CONFIG = ROOT / "configs/model/agentkernel_100m_seq2seq_recovered_target.json"
TOKENIZER_JSON = ROOT / "configs/tokenizer/agentkernel_bpe_1506/tokenizer.json"
TOKENIZER_CONFIG = ROOT / "configs/tokenizer/agentkernel_bpe_1506/tokenizer_config.json"
TOKENIZER_HASHLOCK = ROOT / "configs/tokenizer/agentkernel_bpe_1506_recovered_pointer.json"
TMPDIR = Path('/data/tmp')
RUN_ID = 'stage10209_warm_start_c_cpp_counterbalance_probe'
OUTPUT_DIR = 'runs/local/artifacts/stage10209_warm_start_c_cpp_counterbalance_probe/bounded_decoder_probe'
RUNTIME_MODEL_DIR = 'runs/local/artifacts/stage10209_warm_start_c_cpp_counterbalance_probe/runtime_model'
MAX_STEPS = 32
LEARNING_RATE = '1e-5'
BATCH_SIZE = 2


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding='utf-8')) if path.exists() else {}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
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


def command(split_counts: dict[str, int]) -> list[str]:
    return [
        'env',
        f'TMPDIR={TMPDIR}',
        f'TEMP={TMPDIR}',
        f'TMP={TMPDIR}',
        'conda', 'run', '-n', 'trellis',
        'python', str(TRAINER),
        '--repo-root', str(ROOT),
        '--manifest', str(MANIFEST),
        '--mode', 'bounded_decoder_ce_probe',
        '--probe-scale', 'target_100m',
        '--implementation', 'transformer',
        '--model-config', str(MODEL_CONFIG),
        '--tokenizer-json', str(TOKENIZER_JSON),
        '--tokenizer-config', str(TOKENIZER_CONFIG),
        '--tokenizer-hashlock', str(TOKENIZER_HASHLOCK),
        '--initialize-from-runtime-model', str(INIT_RUNTIME),
        '--execution-authorized-for-recovery-probe',
        '--max-train-rows', str(split_counts.get('train', 0)),
        '--max-eval-rows', '0',
        '--max-strict-rows', str(split_counts.get('strict_eval', 0)),
        '--max-steps', str(MAX_STEPS),
        '--batch-size', str(BATCH_SIZE),
        '--learning-rate', LEARNING_RATE,
        '--max-encoder-tokens', '768',
        '--max-decoder-tokens', '8',
        '--decoder-ce-weight', '0.25',
        '--bounded-choice-aux-weight', '1.0',
        '--bounded-choice-aux-source', 'encoder_option_retrieval',
        '--structured-aux-weight', '0.0',
        '--denoise-weight', '0.0',
        '--eos-loss-weight', '4.0',
        '--enable-generation-audit',
        '--max-generation-rows', '16',
        '--max-generation-tokens', '8',
        '--require-loss-mask-enforcement-audit',
        '--allow-runtime-model-save-for-harness',
        '--runtime-model-save-dir', str(ROOT / RUNTIME_MODEL_DIR),
        '--no-final-checkpoint-export',
        '--skip-final-model-save', '1',
        '--output-dir', str(ROOT / OUTPUT_DIR),
        '--run-id', RUN_ID,
    ]


def build_request() -> dict[str, Any]:
    package = load_json(PACKAGE)
    rows = merged_rows(package)
    write_jsonl(MANIFEST, rows)
    split_counts = {'train': 0, 'eval': 0, 'strict_eval': 0, 'other': 0}
    language_counts: dict[str, int] = {}
    for row in rows:
        split = str(row.get('split') or '')
        split_counts[split if split in split_counts else 'other'] += 1
        language = str(row.get('language_family') or '')
        language_counts[language] = language_counts.get(language, 0) + 1
    cmd = command(split_counts)
    request = {
        'stage': STAGE,
        'stage_name': NAME,
        'created_at_utc': now_utc(),
        'passed': bool(package.get('passed')) and bool(rows) and INIT_RUNTIME.exists(),
        'source_package': display(PACKAGE),
        'initialize_from_runtime_model': display(INIT_RUNTIME),
        'manifest': display(MANIFEST),
        'rows': len(rows),
        'split_counts': split_counts,
        'language_counts': dict(sorted(language_counts.items())),
        'max_steps': MAX_STEPS,
        'learning_rate': LEARNING_RATE,
        'command': cmd,
        'output_dir': OUTPUT_DIR,
        'run_id': RUN_ID,
        'request_status': 'save_enabled_execution_ready' if bool(package.get('passed')) and bool(rows) and INIT_RUNTIME.exists() else 'blocked_by_missing_input',
        'required_runtime_artifacts': [
            'execution_result.json',
            'bounded_choice_eval_audit_strict_eval.json',
            'sample_generation_audit.json',
            'failure_bucket_card.json',
            'runtime_model/model_state.pt',
            'runtime_model/runtime_model_bundle.json',
        ],
        'artifact_purpose': 'warm-start continuation from stage10202 runtime plus repaired c_cpp abstention support from stage10204',
        'required_honesty_gates': [
            'strict eval rows remain identical to stage10200 and stage10149',
            'warm-start source is the saved stage10202 runtime model, not a hidden checkpoint swap',
            'recovered c_cpp abstention rows remain train-only auxiliary and do not create a new score claim on their source bundles',
            'stage10142 standalone decoder contract audit remains binding for any score claim',
        ],
    }
    REQUEST.write_text(json.dumps(request, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    COMMAND_JSON.write_text(json.dumps({'command': cmd, 'cwd': str(ROOT), 'env': 'trellis', 'tmpdir': str(TMPDIR)}, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    SUMMARY.write_text(json.dumps({'stage': STAGE, 'stage_name': NAME, 'passed': request['passed'], 'request': display(REQUEST), 'manifest': display(MANIFEST), 'rows': len(rows), 'max_steps': MAX_STEPS, 'learning_rate': LEARNING_RATE, 'request_status': request['request_status']}, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    return request


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    request = build_request()
    print(json.dumps({'stage': STAGE, 'passed': request['passed'], 'request': display(REQUEST), 'manifest': display(MANIFEST), 'rows': request['rows'], 'max_steps': MAX_STEPS}, indent=2, sort_keys=True))


if __name__ == '__main__':
    main()
