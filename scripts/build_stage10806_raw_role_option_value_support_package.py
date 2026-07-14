#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / 'runs' / 'local' / 'artifacts'
STAGE = 10806
NAME = 'stage10806_raw_role_option_value_support_package'
OUT_DIR = ARTIFACTS / NAME
SUMMARY_JSON = OUT_DIR / 'raw_role_option_value_support_package.json'
SUPPORT_ROWS_JSONL = OUT_DIR / 'support_rows.jsonl'
TRAIN_ROWS_JSONL = OUT_DIR / 'agentkernel_lite_encdec_train.jsonl'
VALIDATION_ROWS_JSONL = OUT_DIR / 'agentkernel_lite_encdec_validation.jsonl'
STRICT_ROWS_JSONL = OUT_DIR / 'agentkernel_lite_encdec_strict_eval.jsonl'
STRESS_ROWS_JSONL = OUT_DIR / 'agentkernel_lite_encdec_stress_eval.jsonl'

BASE_PACKAGE = ARTIFACTS / 'stage10799_python_plus_rust_competition_support_package' / 'python_plus_rust_competition_support_package.json'
BASE_SUPPORT = ARTIFACTS / 'stage10799_python_plus_rust_competition_support_package' / 'support_rows.jsonl'
BASE_TRAIN = ARTIFACTS / 'stage10799_python_plus_rust_competition_support_package' / 'agentkernel_lite_encdec_train.jsonl'
BASE_VALIDATION = ARTIFACTS / 'stage10799_python_plus_rust_competition_support_package' / 'agentkernel_lite_encdec_validation.jsonl'
BASE_STRICT = ARTIFACTS / 'stage10799_python_plus_rust_competition_support_package' / 'agentkernel_lite_encdec_strict_eval.jsonl'
BASE_STRESS = ARTIFACTS / 'stage10799_python_plus_rust_competition_support_package' / 'agentkernel_lite_encdec_stress_eval.jsonl'


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding='utf-8'))


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines() if line.strip()]


def write_json(path: Path, payload: Any) -> None:
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


def relabel(options: list[dict[str, Any]], raw_options: list[dict[str, Any]], gold_value: str) -> tuple[list[dict[str, str]], str] | None:
    if not raw_options:
        return None
    raw_values = [str(opt.get('value') or '') for opt in raw_options]
    labels = [str(opt.get('label') or '') for opt in options]
    if len(raw_values) != len(labels):
        return None
    paired = [{'label': label, 'value': raw_value} for label, raw_value in zip(labels, raw_values)]
    gold_label = None
    for opt in paired:
        if opt['value'] == gold_value:
            gold_label = opt['label']
            break
    if not gold_label:
        return None
    return paired, gold_label


def raw_role_python_clones(base_support: list[dict[str, Any]]) -> list[dict[str, Any]]:
    clones = []
    for row in base_support:
        if row.get('language_family') != 'python' or row.get('task_type') != 'evidence_citation':
            continue
        proj = row.get('standalone_projection_source') or {}
        raw_options = proj.get('opaque_options') or []
        gold_value = str(proj.get('gold_value') or '')
        relabeled = relabel(row.get('opaque_options') or [], raw_options, gold_value)
        if not relabeled:
            continue
        paired, gold_label = relabeled
        clone = json.loads(json.dumps(row))
        clone['row_id'] = str(row['row_id']).replace('stage10794::', 'stage10806::raw_role::', 1)
        clone['query_text'] = str(row.get('query_text') or '').replace('stage10794::python::', 'stage10806::python_raw_role::', 1)
        clone['route'] = 'raw_role_option_value_support'
        clone['opaque_options'] = paired
        clone['gold_value'] = gold_value
        clone['decoder_text'] = gold_label
        clone['expected_label'] = gold_label
        clone['target_text'] = gold_label
        clone['support_package_stage'] = STAGE
        clone['semantic_key'] = 'raw_evidence_role'
        anti = clone.get('anti_cheat') or {}
        anti['raw_role_option_values'] = True
        anti['same_surface_eval_admissible'] = False
        anti['diagnostic_support_only'] = True
        anti['prompt_target_visible_by_role_contract'] = True
        clone['anti_cheat'] = anti
        clone['support_provenance'] = dict(clone.get('support_provenance') or {})
        clone['support_provenance']['raw_role_clone_stage'] = STAGE
        clone['support_provenance']['original_humanized_values'] = [opt.get('value') for opt in row.get('opaque_options') or []]
        clones.append(clone)
    return clones


def rust_diagnostic_clone(strict_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    wanted = 'stage10126::tokenizers::tokenizers::rust::evidence_citation::reviewed_v27_compact'
    clones = []
    for row in strict_rows:
        if row.get('row_id') != wanted:
            continue
        clone = json.loads(json.dumps(row))
        clone['row_id'] = 'stage10806::diagnostic_same_surface::tokenizers::rust::evidence_citation::support_candidate'
        clone['split'] = 'train'
        clone['split_role'] = 'diagnostic_support'
        clone['strict_eval_eligible'] = False
        clone['train_support_only'] = True
        clone['source_heldout_admissible'] = False
        clone['route'] = 'raw_role_option_value_support_same_surface_diagnostic'
        clone['support_package_stage'] = STAGE
        clone['loss_mask'] = {'decoder_ce': True}
        anti = clone.get('anti_cheat') or {}
        anti['same_surface_eval_admissible'] = False
        anti['diagnostic_same_surface_clone'] = True
        anti['prompt_target_visible_by_role_contract'] = True
        clone['anti_cheat'] = anti
        clones.append(clone)
    return clones


def main() -> None:
    base_package = load_json(BASE_PACKAGE)
    base_support = load_jsonl(BASE_SUPPORT)
    base_train = load_jsonl(BASE_TRAIN)
    base_validation = load_jsonl(BASE_VALIDATION)
    base_strict = load_jsonl(BASE_STRICT)
    base_stress = load_jsonl(BASE_STRESS)

    python_clones = raw_role_python_clones(base_support)
    rust_clones = rust_diagnostic_clone(base_strict)
    added_support = python_clones + rust_clones

    added_ids = [str(r['row_id']) for r in added_support]
    if len(added_ids) != len(set(added_ids)):
        raise SystemExit('duplicate added support ids detected')
    train_ids = {str(r['row_id']) for r in base_train}
    overlap = sorted(train_ids.intersection(added_ids))
    if overlap:
        raise SystemExit(f'added support rows already in base train: {overlap[:5]}')

    merged_support = list(base_support) + added_support
    merged_train = list(base_train) + added_support

    payload = {
        'stage': STAGE,
        'stage_name': NAME,
        'created_at_utc': now_utc(),
        'passed': True,
        'decision': 'raw_role_option_value_support_package_ready',
        'claim_scope': [
            'Add targeted raw role-key option-value support so encoder_option_retrieval sees the same option interface as the remaining Rust strict residual.',
            'Keep the honest strict frontier unchanged while adding diagnostic-only support rows for raw evidence-role semantics.',
            'Explicitly mark any same-surface Rust clone as diagnostic-only and non-promotable.',
        ],
        'metrics': {
            'base_train_rows': len(base_train),
            'base_support_rows': len(base_support),
            'python_raw_role_clones': len(python_clones),
            'rust_same_surface_diagnostic_clones': len(rust_clones),
            'added_support_rows': len(added_support),
            'merged_train_rows': len(merged_train),
            'added_languages': dict(sorted(Counter(str(r.get('language_family') or 'unknown') for r in added_support).items())),
        },
        'headline_findings': [
            'Existing Python support already contained the raw role-key option set in provenance, so these rows can be cloned onto the raw retrieval interface without changing the heldout frontier.',
            'The Rust tokenizers residual is added only as a same-surface diagnostic clone because the goal is interface repair, not a promotable benchmark claim.',
            'This package should be used only for diagnostic support probes until disjoint Rust raw-role support exists.',
        ],
        'next_best_step': 'Run a diagnostic probe from the latest runtime and check whether encoder_option_retrieval now flips the Rust residual without introducing new strict regressions.',
        'source_artifacts': {
            'base_package': display(BASE_PACKAGE),
            'base_support_rows': display(BASE_SUPPORT),
            'base_strict_rows': display(BASE_STRICT),
            'base_package_metrics': base_package.get('metrics'),
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

    write_jsonl(SUPPORT_ROWS_JSONL, merged_support)
    write_jsonl(TRAIN_ROWS_JSONL, merged_train)
    write_jsonl(VALIDATION_ROWS_JSONL, base_validation)
    write_jsonl(STRICT_ROWS_JSONL, base_strict)
    write_jsonl(STRESS_ROWS_JSONL, base_stress)
    write_json(SUMMARY_JSON, payload)
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == '__main__':
    main()
