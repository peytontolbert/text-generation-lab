#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = 10146
NAME = 'stage10146_v27_standalone_compact_bounded_maintainer_bundle_package'
OUT_DIR = ROOT / 'runs/local/artifacts' / NAME
TRAIN_JSONL = OUT_DIR / 'agentkernel_lite_encdec_train.jsonl'
EVAL_JSONL = OUT_DIR / 'agentkernel_lite_encdec_eval.jsonl'
PACKAGE_JSON = OUT_DIR / 'standalone_compact_bounded_maintainer_bundle_package.json'
SUMMARY = ROOT / 'runs/summaries' / f'{NAME}.json'
SOURCE = ROOT / 'runs/local/artifacts/stage10143_compact_bounded_bundle_projection/compact_bounded_bundle_projection.json'


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding='utf-8')) if path.exists() else {}


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


def grouped_runs(payload: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for run in payload.get('runs') or []:
        if not isinstance(run, dict):
            continue
        language = str(((run.get('task_pack') or {}).get('language_family')) or '')
        grouped.setdefault(language, []).append(run)
    for language in grouped:
        grouped[language] = sorted(grouped[language], key=lambda row: str((row.get('task_pack') or {}).get('bundle_id') or ''))
    return grouped


def trainer_row(source_run: dict[str, Any], row: dict[str, Any], *, split: str) -> dict[str, Any]:
    task_pack = source_run.get('task_pack') or {}
    prompt = str(row.get('prompt_text') or row.get('input_text') or '')
    target = str(row.get('target_text') or row.get('expected_label') or '')
    return {
        'row_id': str(row.get('row_id') or ''),
        'language_family': str(row.get('language_family') or task_pack.get('language_family') or ''),
        'route': 'KEEP_BOUNDED_DECODER',
        'objective_family': 'bounded_decoder_ce',
        'surface': 'maintainer_bundle_compact_bounded_choice',
        'task_type': str(row.get('task_type') or row.get('perspective') or ''),
        'split': split,
        'prompt_text': prompt,
        'input_text': prompt,
        'query_text': str(row.get('query_text') or ''),
        'target_text': target,
        'decoder_text': target,
        'target_token_len': len(target.encode('utf-8')),
        'loss_mask': {'decoder_ce': True},
        'expected_enabled_loss': 'decoder_ce',
        'disable_losses': ['denoise_ce', 'runtime_reward', 'structured_aux'],
        'source_skill_area': 'maintainer_bundle_compact_bounded_choice',
        'source_stage': STAGE,
        'source_row_id': str(row.get('row_id') or ''),
        'source_bundle_id': str(task_pack.get('bundle_id') or ''),
        'semantic_key': f"maintainer_bundle_compact_bounded::{task_pack.get('bundle_id')}::{row.get('perspective')}",
        'anti_cheat': {
            'opaque_labels': True,
            'bundle_level_split_preserved': True,
            'freeform_rows_excluded': True,
            'compact_prompt_contract': True,
            'standalone_decoder_contract_gate_required': True,
            **dict(row.get('anti_cheat') or {}),
        },
        'authority': {
            'model_execution_authorized_next': False,
            'decoder_ce_training_authorized_next': False,
            'denoise_ce_training_authorized_next': False,
            'runtime_authorized': False,
            'source_emission_authorized': False,
            'body_emission_authorized': False,
            'gemma_execution_authorized_next': False,
            'harness_execution_authorized_next': False,
            'scoring_authorized_next': False,
            'controller_complete_merge_authorized_next': False,
            'promotion_ready': False,
        },
        'standalone_projection_source': {
            'projection_stage': 10143,
            'projection_mode': str((task_pack.get('projection_mode') or 'compact_bounded_choice_auxiliary')),
            'gold_answers_path': str(task_pack.get('gold_answers_path') or ''),
            'opaque_options': list(row.get('opaque_options') or []),
            'original_answer_kind': str(row.get('original_answer_kind') or ''),
            'gold_value': str(row.get('gold_value') or ''),
        },
    }


def build_package() -> dict[str, Any]:
    payload = load_json(SOURCE)
    by_language = grouped_runs(payload)
    train_rows: list[dict[str, Any]] = []
    eval_rows: list[dict[str, Any]] = []
    split_manifest: list[dict[str, Any]] = []
    failures: list[str] = []
    for language, runs in sorted(by_language.items()):
        if len(runs) < 2:
            failures.append(f'need_at_least_two_bundles::{language}')
            continue
        train_run, eval_run = runs[0], runs[1]
        train_compiled = [trainer_row(train_run, row, split='train') for row in ((train_run.get('task_pack') or {}).get('rows') or []) if isinstance(row, dict)]
        eval_compiled = [trainer_row(eval_run, row, split='strict_eval') for row in ((eval_run.get('task_pack') or {}).get('rows') or []) if isinstance(row, dict)]
        train_rows.extend(train_compiled)
        eval_rows.extend(eval_compiled)
        split_manifest.append({
            'language_family': language,
            'train_bundle_id': str(((train_run.get('task_pack') or {}).get('bundle_id')) or ''),
            'strict_eval_bundle_id': str(((eval_run.get('task_pack') or {}).get('bundle_id')) or ''),
            'train_rows': len(train_compiled),
            'strict_eval_rows': len(eval_compiled),
        })
    write_jsonl(TRAIN_JSONL, train_rows)
    write_jsonl(EVAL_JSONL, eval_rows)
    metrics = {
        'languages': len(split_manifest),
        'train_rows': len(train_rows),
        'strict_eval_rows': len(eval_rows),
        'bundles_consumed': len(split_manifest) * 2,
    }
    package = {
        'stage': STAGE,
        'stage_name': NAME,
        'created_at_utc': now_utc(),
        'source_projection': display(SOURCE),
        'passed': not failures and bool(train_rows) and bool(eval_rows),
        'metrics': metrics,
        'split_manifest': split_manifest,
        'failures': failures,
        'train_dataset_path': display(TRAIN_JSONL),
        'eval_dataset_path': display(EVAL_JSONL),
        'fit_for': {
            'standalone_decoder_ce_training': True,
            'full_product_harness_training': False,
            'expert_maintainer_primary_score': False,
            'compact_bounded_auxiliary_projection_only': True,
        },
        'required_honesty_gates': [
            'stage10142_standalone_decoder_contract_audit must pass before standalone score claims',
            'bundle-level heldout split must remain intact',
            'freeform maintainer rows remain excluded from compact standalone package',
        ],
    }
    PACKAGE_JSON.write_text(json.dumps(package, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    SUMMARY.write_text(json.dumps({'stage': STAGE, 'passed': package['passed'], 'package': display(PACKAGE_JSON), 'metrics': metrics, 'failures': failures}, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    return package


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    package = build_package()
    print(json.dumps({'stage': STAGE, 'passed': package['passed'], 'package': display(PACKAGE_JSON), 'metrics': package['metrics'], 'failures': package['failures']}, indent=2, sort_keys=True))


if __name__ == '__main__':
    main()
