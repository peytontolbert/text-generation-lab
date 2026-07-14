#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = 10794
NAME = 'stage10794_deleaked_python_overflow_support_package'
OUT_DIR = ROOT / 'runs/local/artifacts' / NAME
SUMMARY_JSON = OUT_DIR / 'deleaked_python_overflow_support_package.json'
SUPPORT_ROWS_JSONL = OUT_DIR / 'support_rows.jsonl'
TRAIN_ROWS_JSONL = OUT_DIR / 'agentkernel_lite_encdec_train.jsonl'
VALIDATION_ROWS_JSONL = OUT_DIR / 'agentkernel_lite_encdec_validation.jsonl'
STRICT_ROWS_JSONL = OUT_DIR / 'agentkernel_lite_encdec_strict_eval.jsonl'
STRESS_ROWS_JSONL = OUT_DIR / 'agentkernel_lite_encdec_stress_eval.jsonl'
SUMMARY_CARD = ROOT / 'runs/summaries' / f'{NAME}.json'

BASE_PACKAGE = ROOT / 'runs/local/artifacts/stage10791_larger_root_split_plus_python_overflow_support_package/larger_root_split_plus_python_overflow_support_package.json'
BASE_SUPPORT = ROOT / 'runs/local/artifacts/stage10791_larger_root_split_plus_python_overflow_support_package/support_rows.jsonl'
BASE_TRAIN = ROOT / 'runs/local/artifacts/stage10791_larger_root_split_plus_python_overflow_support_package/agentkernel_lite_encdec_train.jsonl'
BASE_VALIDATION = ROOT / 'runs/local/artifacts/stage10791_larger_root_split_plus_python_overflow_support_package/agentkernel_lite_encdec_validation.jsonl'
BASE_STRICT = ROOT / 'runs/local/artifacts/stage10791_larger_root_split_plus_python_overflow_support_package/agentkernel_lite_encdec_strict_eval.jsonl'
BASE_STRESS = ROOT / 'runs/local/artifacts/stage10791_larger_root_split_plus_python_overflow_support_package/agentkernel_lite_encdec_stress_eval.jsonl'


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding='utf-8'))


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open(encoding='utf-8') as handle:
        for line in handle:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + '\n', encoding='utf-8')


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('w', encoding='utf-8') as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + '\n')


def display(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def now_utc() -> str:
    return time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())


def classify_path(value: str) -> str:
    lower = value.lower()
    name = Path(lower).name
    if lower.endswith(('.yaml', '.yml', '.json', '.toml', '.ini')) or 'config' in name:
        return 'config'
    if '/tests/' in lower or lower.startswith('tests/') or 'test_' in name or name.endswith('_test.py'):
        return 'test'
    if lower.endswith('.py'):
        return 'python'
    return 'file'


def summarize_value(value: str, label: str) -> str:
    if value == 'ABSTAIN_INSUFFICIENT_EVIDENCE':
        return 'insufficient evidence / abstain'
    role_map = {
        'candidate_change_surface': 'changed implementation candidate evidence',
        'nearby_definition_or_usage_context': 'nearby definition or usage context',
        'symptom_or_call_path_analogue': 'symptom or call-path evidence',
        'verifier_and_test_constraint': 'verifier or selected-test constraint',
    }
    if value in role_map:
        return role_map[value]
    kind = classify_path(value)
    base = Path(value).name
    include_base = base != value
    if kind == 'test':
        return f'test candidate {label.lower()} ({base})' if include_base else f'test candidate {label.lower()} (repo-root test file)'
    if kind == 'config':
        return f'config candidate {label.lower()} ({base})' if include_base else f'config candidate {label.lower()} (repo-root config file)'
    if kind == 'python':
        return f'implementation candidate {label.lower()} ({base})' if include_base else f'implementation candidate {label.lower()} (repo-root python file)'
    return f'file candidate {label.lower()} ({base})' if include_base else f'file candidate {label.lower()} (repo-root file)'


def replace_all(text: str, mapping: dict[str, str]) -> str:
    updated = text
    for src in sorted(mapping, key=len, reverse=True):
        updated = updated.replace(src, mapping[src])
    return updated


def deleak_row(row: dict[str, Any]) -> dict[str, Any]:
    copied = json.loads(json.dumps(row))
    mapping = {}
    original_options = copied.get('opaque_options') or []
    new_options = []
    original_value_map = {}
    for opt in original_options:
        label = str(opt['label'])
        original_value = str(opt['value'])
        original_value_map[label] = original_value
        summarized = summarize_value(original_value, label)
        mapping[original_value] = summarized
        new_options.append({'label': label, 'value': summarized})
    for literal, summary in {
        'candidate_change_surface': 'changed implementation candidate evidence',
        'nearby_definition_or_usage_context': 'nearby definition or usage context',
        'symptom_or_call_path_analogue': 'symptom or call-path evidence',
        'verifier_and_test_constraint': 'verifier or selected-test constraint',
    }.items():
        mapping[literal] = summary
    prompt = str(copied.get('prompt_text') or copied.get('input_text') or '')
    prompt = replace_all(prompt, mapping)
    copied['prompt_text'] = prompt
    copied['input_text'] = prompt
    copied['opaque_options'] = new_options
    copied['route'] = 'python_overflow_support_second_wave_deleaked'
    copied['row_id'] = str(copied['row_id']).replace('stage10791::', 'stage10794::', 1)
    copied['query_text'] = str(copied.get('query_text') or '').replace('stage10791::', 'stage10794::', 1)
    anti_cheat = copied.get('anti_cheat') or {}
    anti_cheat['prompt_target_leak_false'] = True
    anti_cheat['deleaked_support_candidate'] = True
    anti_cheat['exact_gold_strings_removed_from_prompt_prefix'] = True
    copied['anti_cheat'] = anti_cheat
    provenance = copied.get('support_provenance') or {}
    provenance['deleak_stage'] = STAGE
    provenance['original_option_values'] = original_value_map
    copied['support_provenance'] = provenance
    return copied


def main() -> None:
    base_package = load_json(BASE_PACKAGE)
    base_support = load_jsonl(BASE_SUPPORT)
    base_train = load_jsonl(BASE_TRAIN)
    base_validation = load_jsonl(BASE_VALIDATION)
    base_strict = load_jsonl(BASE_STRICT)
    base_stress = load_jsonl(BASE_STRESS)

    original_support_row_ids = {str(row['row_id']) for row in base_support}
    preserved_train = [row for row in base_train if str(row.get('row_id') or '') not in original_support_row_ids]
    deleaked_support = [deleak_row(row) for row in base_support]
    merged_train = preserved_train + deleaked_support

    payload = {
        'stage': STAGE,
        'stage_name': NAME,
        'created_at_utc': now_utc(),
        'passed': True,
        'decision': 'deleaked_python_overflow_support_package_ready',
        'claim_scope': [
            'Rewrite the second-wave Python overflow support package so gold paths and evidence-role literals are not exposed verbatim before the option set.',
            'Keep the train/validation/strict/stress split structure from the larger-root-split package unchanged except for replacing the leaky Python overflow support rows.',
            'Preserve support-only scope; this package is still non-promotable and exists to make the next training probe honest.',
        ],
        'metrics': {
            'original_support_rows': len(base_support),
            'deleaked_support_rows': len(deleaked_support),
            'preserved_non_support_train_rows': len(preserved_train),
            'merged_train_rows': len(merged_train),
        },
        'headline_findings': [
            'The second-wave Python support rows are now rewritten onto summarized candidate descriptions rather than verbatim gold path or role literals.',
            'This package is designed specifically to clear prompt-target leakage while preserving label supervision and row counts.',
            'A fresh leak audit is still required before any new support probe uses it.',
        ],
        'next_best_step': 'Run a fresh leak audit on this de-leaked successor package; if it passes, use it instead of stage10791 for the next support-only probe.',
        'source_artifacts': {
            'base_package': display(BASE_PACKAGE),
            'base_support_rows': display(BASE_SUPPORT),
        },
        'outputs': {
            'summary_json': display(SUMMARY_JSON),
            'support_rows': display(SUPPORT_ROWS_JSONL),
            'train_rows': display(TRAIN_ROWS_JSONL),
            'validation_rows': display(VALIDATION_ROWS_JSONL),
            'strict_rows': display(STRICT_ROWS_JSONL),
            'stress_rows': display(STRESS_ROWS_JSONL),
        },
    }

    write_jsonl(SUPPORT_ROWS_JSONL, deleaked_support)
    write_jsonl(TRAIN_ROWS_JSONL, merged_train)
    write_jsonl(VALIDATION_ROWS_JSONL, base_validation)
    write_jsonl(STRICT_ROWS_JSONL, base_strict)
    write_jsonl(STRESS_ROWS_JSONL, base_stress)
    write_json(SUMMARY_JSON, payload)
    write_json(SUMMARY_CARD, {
        'stage': STAGE,
        'passed': True,
        'decision': payload['decision'],
        'deleaked_support_rows': len(deleaked_support),
    })
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == '__main__':
    main()
