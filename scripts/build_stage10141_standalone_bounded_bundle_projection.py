#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import textwrap
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = 10141
NAME = 'stage10141_standalone_bounded_bundle_projection'
OUT_DIR = ROOT / 'runs/local/artifacts' / NAME
OUT_PATH = OUT_DIR / 'standalone_bounded_bundle_projection.json'
SUMMARY = ROOT / 'runs/summaries' / f'{NAME}.json'
SOURCE = ROOT / 'runs/local/artifacts/stage10129_true_source_backed_multilingual_adjudication_frontier/true_source_backed_multilingual_adjudication_admitted_manifest.json'

BOUND_KINDS = {'candidate_path', 'selected_test', 'visible_evidence_key', 'abstain'}
CHOICE_LABELS = list('ABCDEFGHJKLMNOPQRSTUVWXYZ')


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding='utf-8')) if path.exists() else {}


def display(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def now_utc() -> str:
    return time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())


def snippet(text: str, limit: int = 600) -> str:
    clean = ' '.join(str(text).split())
    return clean if len(clean) <= limit else clean[: max(0, limit - 3)] + '...'


def evidence_sections(bundle: dict[str, Any], visible_keys: list[str]) -> str:
    evidence = bundle.get('maintainer_visible_evidence') if isinstance(bundle.get('maintainer_visible_evidence'), dict) else {}
    sections: list[str] = []
    for key in visible_keys:
        values = evidence.get(key)
        if not isinstance(values, list) or not values:
            continue
        lines = []
        for idx, item in enumerate(values[:2], start=1):
            if not isinstance(item, dict):
                continue
            path = str(item.get('path') or '')
            source_type = str(item.get('source_type') or '')
            text = snippet(str(item.get('text') or ''))
            label = f'{idx}. {path}' if path else f'{idx}.'
            if source_type:
                label += f' [{source_type}]'
            lines.append(f'{label}\n{text}')
        if lines:
            sections.append(f'{key}:\n' + '\n\n'.join(lines))
    return '\n\n'.join(sections)


def contract_for(bundle: dict[str, Any], perspective: str) -> dict[str, Any]:
    for row in bundle.get('perspective_rows') or []:
        if isinstance(row, dict) and str(row.get('perspective') or '') == perspective:
            contract = row.get('prompt_contract')
            if isinstance(contract, dict):
                return contract
    return {}


def deterministic_order(values: list[str], seed: str) -> list[str]:
    return sorted(values, key=lambda value: hashlib.sha256(f'{seed}::{value}'.encode('utf-8')).hexdigest())


def build_option_values(*, answer_kind: str, gold_value: str, contract: dict[str, Any], gold: dict[str, Any]) -> list[str]:
    if answer_kind == 'candidate_path':
        values = [str(v) for v in (gold.get('candidate_paths') or contract.get('candidate_paths') or []) if v]
    elif answer_kind == 'selected_test':
        values = [str(v) for v in (gold.get('selected_tests') or contract.get('selected_tests') or []) if v]
    elif answer_kind == 'visible_evidence_key':
        values = [str(v) for v in (gold.get('visible_evidence_keys') or contract.get('visible_evidence_keys') or []) if v]
    elif answer_kind == 'abstain':
        base = [str(v) for v in (gold.get('candidate_paths') or contract.get('candidate_paths') or []) if v]
        if not base:
            base = [str(v) for v in (gold.get('selected_tests') or contract.get('selected_tests') or []) if v]
        if not base:
            base = [str(v) for v in (gold.get('visible_evidence_keys') or contract.get('visible_evidence_keys') or []) if v]
        values = base + ['ABSTAIN_INSUFFICIENT_EVIDENCE']
    else:
        values = [gold_value]
    seen = set()
    deduped = []
    for value in values:
        if value not in seen:
            seen.add(value)
            deduped.append(value)
    if gold_value not in seen:
        deduped.append(gold_value)
    return deduped


def compile_prompt(bundle: dict[str, Any], gold: dict[str, Any], *, options: list[tuple[str, str]]) -> str:
    perspective = str(gold.get('perspective') or '')
    contract = contract_for(bundle, perspective)
    task = str(contract.get('task') or '')
    visible_keys = [str(v) for v in contract.get('visible_evidence_keys') or [] if v]
    evidence = evidence_sections(bundle, visible_keys)
    option_lines = '\n'.join(f'- {label}: {value}' for label, value in options)
    prompt = f'''
    You are evaluating a maintainer-grade software maintenance root case.

    Language family: {bundle.get('language_family')}
    Bundle id: {bundle.get('bundle_id')}
    Perspective: {perspective}

    Task:
    {task}

    Visible evidence:
    {evidence if evidence else 'No visible evidence blocks were attached.'}

    Options:
    {option_lines}

    Output rule:
    Return only the opaque option label.
    '''
    return textwrap.dedent(prompt).strip() + '\n'


def compile_bounded_row(bundle: dict[str, Any], gold: dict[str, Any]) -> dict[str, Any] | None:
    perspective = str(gold.get('perspective') or '')
    answer_kind = str(gold.get('gold_answer_kind') or '')
    gold_value = str(gold.get('gold_answer_value') or '')
    if answer_kind not in BOUND_KINDS:
        return None
    contract = contract_for(bundle, perspective)
    values = build_option_values(answer_kind=answer_kind, gold_value=gold_value, contract=contract, gold=gold)
    seed = f"{bundle['bundle_id']}::{perspective}::{answer_kind}"
    ordered_values = deterministic_order(values, seed)
    if len(ordered_values) > len(CHOICE_LABELS):
        raise ValueError(f'too_many_options::{bundle["bundle_id"]}::{perspective}')
    options = list(zip(CHOICE_LABELS[: len(ordered_values)], ordered_values))
    label_by_value = {value: label for label, value in options}
    prompt = compile_prompt(bundle, gold, options=options)
    return {
        'row_id': f"{bundle['bundle_id']}::{perspective}::bounded",
        'bundle_id': bundle['bundle_id'],
        'language_family': bundle['language_family'],
        'route': 'DIRECT_ANSWER_MAINTAINER_BUNDLE_BOUNDED',
        'objective_family': 'maintainer_bundle_bounded_choice',
        'surface': 'edit_localization',
        'task_type': perspective,
        'perspective': perspective,
        'original_answer_kind': answer_kind,
        'expected_answer_kind': 'opaque_choice',
        'expected_label': label_by_value[gold_value],
        'prompt': prompt,
        'prompt_text': prompt,
        'input_text': prompt,
        'query_text': f"maintainer_bundle_bounded::{bundle['language_family']}::{perspective}::{answer_kind}",
        'target_text': label_by_value[gold_value],
        'split': 'strict_eval',
        'opaque_options': [{'label': label, 'value': value} for label, value in options],
        'opaque_choice_count': len(options),
        'gold_value': gold_value,
        'selected_tests': list(gold.get('selected_tests') or []),
        'candidate_paths': list(gold.get('candidate_paths') or []),
        'visible_evidence_keys': list(gold.get('visible_evidence_keys') or []),
        'anti_cheat': {
            'opaque_labels': True,
            'deterministic_option_shuffle': True,
            'freeform_rows_excluded_from_projection': True,
            'projection_is_auxiliary_not_primary_maintainer_score': True,
        },
    }


def build_payload() -> dict[str, Any]:
    data = load_json(SOURCE)
    bundles = [row for row in data.get('rows') or [] if isinstance(row, dict)]
    runs = []
    excluded = []
    counts = {'bundles': 0, 'rows': 0, 'excluded_freeform_rows': 0}
    for bundle in bundles:
        gold_path = ROOT / str(bundle.get('perspective_gold_adjudication') or '')
        gold = load_json(gold_path)
        answers = [row for row in gold.get('perspective_gold_answers') or [] if isinstance(row, dict)]
        bounded_rows = []
        for answer in answers:
            bounded = compile_bounded_row(bundle, answer)
            if bounded is None:
                excluded.append({
                    'bundle_id': bundle['bundle_id'],
                    'language_family': bundle['language_family'],
                    'perspective': answer.get('perspective'),
                    'answer_kind': answer.get('gold_answer_kind'),
                })
                counts['excluded_freeform_rows'] += 1
                continue
            bounded_rows.append(bounded)
        if not bounded_rows:
            continue
        counts['bundles'] += 1
        counts['rows'] += len(bounded_rows)
        task_pack = {
            'bundle_id': bundle['bundle_id'],
            'task_pack_id': bundle['bundle_id'],
            'source_id': bundle['bundle_id'],
            'lineage_hash': bundle['bundle_id'],
            'split_role': 'locked_regression',
            'train_eligible': False,
            'promotion_only': True,
            'hidden_final': False,
            'language_family': bundle['language_family'],
            'skill_area': 'edit_localization',
            'slice_tags': ['maintainer_bundle', bundle['language_family'], 'bounded_projection', 'admitted'],
            'thresholds': {'must_compare_100m_and_gemma': True, 'projection_only': True},
            'blocked_training_reason': 'bounded_projection_eval_only',
            'rows': bounded_rows,
            'maintainer_bundle_mode': True,
            'projection_mode': 'bounded_choice_auxiliary',
            'gold_answers_path': display(gold_path),
        }
        runs.append({
            'cell_key': f"standalone_projection::{bundle['language_family']}::{bundle['bundle_id']}",
            'task_pack': task_pack,
            'hundred_m_backend': {
                'kind': 'preserved_bundle_prompt_generation',
                'model_bundle_manifest': '/arxiv/preserved_checkpoints_20260609/data/agentkernel-seq2seq-text-lab/runs/local/artifacts/pocketpal_controller_100m_stage1076_direct_answer_full_finetune_v415/agentkernel_lite_encdec_manifest.json',
                'model_weights': '/arxiv/preserved_checkpoints_20260609/data/agentkernel-seq2seq-text-lab/runs/local/artifacts/pocketpal_controller_100m_stage1076_direct_answer_full_finetune_v415/model/model.safetensors',
                'tokenizer_json': 'configs/tokenizer/agentkernel_bpe_1506/tokenizer.json',
                'tokenizer_config': 'configs/tokenizer/agentkernel_bpe_1506/tokenizer_config.json',
                'max_encoder_tokens': 1024,
                'max_new_tokens': 16,
                'device': 'cpu',
            },
            'gemma_backend': {
                'kind': 'ollama_generate',
                'model': 'gemma3:12b',
                'seed': 0,
                'temperature': 0.0,
            },
        })
    return {
        'stage': STAGE,
        'stage_name': NAME,
        'created_at_utc': now_utc(),
        'source': display(SOURCE),
        'passed': bool(runs),
        'metrics': counts,
        'excluded_rows': excluded,
        'runs': runs,
    }


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    payload = build_payload()
    OUT_PATH.write_text(json.dumps(payload, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    SUMMARY.write_text(json.dumps({'stage': STAGE, 'passed': payload['passed'], 'payload': display(OUT_PATH), 'metrics': payload['metrics'], 'excluded_rows': len(payload['excluded_rows'])}, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    print(json.dumps({'stage': STAGE, 'passed': payload['passed'], 'payload': display(OUT_PATH), 'metrics': payload['metrics'], 'excluded_rows': len(payload['excluded_rows'])}, indent=2, sort_keys=True))


if __name__ == '__main__':
    main()
