#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / 'runs/local/artifacts'
STAGE = 11305
NAME = 'stage11305_per_option_semantic_candidate_schema_package'
OUT_DIR = ARTIFACTS / NAME
SUMMARY_JSON = OUT_DIR / 'per_option_semantic_candidate_schema_package.json'

BASE_PACKAGE = ARTIFACTS / 'stage11198_role_focused_residual_support_package'
FACT_PACKAGE = ARTIFACTS / 'stage11296_capped_fact_rich_verifier_package'
RESIDUAL_BANK = ARTIFACTS / 'stage11195_clean_residual_successor_bank/clean_residual_successor_bank.jsonl'

INPUTS = {
    'base_train': BASE_PACKAGE / 'agentkernel_lite_encdec_train.jsonl',
    'base_validation': BASE_PACKAGE / 'agentkernel_lite_encdec_validation.jsonl',
    'base_strict': BASE_PACKAGE / 'agentkernel_lite_encdec_strict_eval.jsonl',
    'fact_train': FACT_PACKAGE / 'capped_fact_rich_verifier_train_rows.jsonl',
    'fact_validation': FACT_PACKAGE / 'capped_fact_rich_verifier_validation_rows.jsonl',
    'fact_strict': FACT_PACKAGE / 'capped_fact_rich_verifier_strict_rows.jsonl',
    'residual': RESIDUAL_BANK,
}

OUTPUTS = {
    'train': OUT_DIR / 'semantic_candidate_schema_train_rows.jsonl',
    'validation': OUT_DIR / 'semantic_candidate_schema_validation_rows.jsonl',
    'strict': OUT_DIR / 'semantic_candidate_schema_strict_rows.jsonl',
    'judgment_validation': OUT_DIR / 'semantic_candidate_schema_judgment_validation_rows.jsonl',
    'judgment_strict': OUT_DIR / 'semantic_candidate_schema_judgment_strict_rows.jsonl',
    'residual': OUT_DIR / 'semantic_candidate_schema_residual_rows.jsonl',
    'option_audit': OUT_DIR / 'semantic_candidate_option_audit.jsonl',
}

EVIDENCE_ROLES = {
    'candidate_change_surface',
    'verifier_and_test_constraint',
    'symptom_or_call_path_analogue',
    'nearby_definition_or_usage_context',
    'external_analogue_reference',
    'algorithmic_background_reference',
    'background_context',
}
TRANSITIONS = ['FAIL_TO_PASS', 'PASS_TO_PASS', 'FAIL_TO_FAIL', 'NOT_EXERCISED', 'INSUFFICIENT_EVIDENCE', 'NEEDS_VERIFIER']


def now_utc() -> str:
    return time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines() if line.strip()] if path.exists() else []


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + '\n', encoding='utf-8')


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(''.join(json.dumps(row, sort_keys=True) + '\n' for row in rows), encoding='utf-8')


def root_key(row: dict[str, Any]) -> str:
    return str(row.get('root_id') or row.get('source_root_id') or row.get('root_lineage_key') or row.get('row_id') or '')


def target_label(row: dict[str, Any]) -> str:
    target = row.get('target') if isinstance(row.get('target'), dict) else {}
    for value in [
        target.get('bounded_choice_target_label'),
        row.get('bounded_choice_target_label'),
        target.get('target_text'),
        row.get('target_text'),
        target.get('target_ref'),
        row.get('target_ref'),
        row.get('decoder_text'),
    ]:
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ''


def gold_value(row: dict[str, Any]) -> str:
    sps = row.get('standalone_projection_source') if isinstance(row.get('standalone_projection_source'), dict) else {}
    for value in [sps.get('gold_value'), row.get('semantic_target_value'), row.get('gold_value')]:
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ''


def infer_target_label_from_gold(row: dict[str, Any]) -> str:
    sps = row.get('standalone_projection_source') if isinstance(row.get('standalone_projection_source'), dict) else {}
    gold = gold_value(row)
    for option in sps.get('opaque_options') or []:
        if isinstance(option, dict) and str(option.get('value') or '').strip() == gold:
            return str(option.get('label') or '').strip()
    return ''


def transition_from_value(value: str) -> str:
    text = str(value).upper()
    for transition in TRANSITIONS:
        if transition in text:
            return transition
    return 'NONE'


def test_id_from_value(value: str) -> str:
    text = str(value).strip()
    if '|' in text:
        return text.split('|', 1)[0].strip()
    m = re.match(r'([A-Z]+\d+)\b', text)
    return m.group(1) if m else ''


def role_from_value(value: str, task_type: str) -> str:
    raw = str(value).strip()
    prefix = raw.split('|', 1)[0].strip()
    if prefix in EVIDENCE_ROLES:
        return prefix
    if task_type.startswith('verifier_outcome') or transition_from_value(raw) != 'NONE':
        return 'verifier_and_test_constraint'
    if raw.upper().startswith('ABSTAIN') or 'INSUFFICIENT' in raw.upper():
        return 'insufficient_evidence_option'
    return 'candidate_value_surface'


def normalize_option(option: dict[str, Any], *, row: dict[str, Any], option_index: int) -> tuple[dict[str, Any], dict[str, Any]]:
    task = str(row.get('task_type') or '').strip()
    label = str(option.get('label') or '').strip()
    value = str(option.get('value') or '').strip()
    transition = transition_from_value(value)
    metadata = {
        'schema_version': 'stage11305_per_option_semantic_candidate_v1',
        'option_index': option_index,
        'candidate_label': label,
        'candidate_value_family': 'verifier_transition' if transition != 'NONE' else ('evidence_role' if role_from_value(value, task) in EVIDENCE_ROLES else 'generic_candidate'),
        'task_type': task,
        'evidence_role': role_from_value(value, task),
        'verifier_transition': transition,
        'test_id': test_id_from_value(value),
        'value_token_count_proxy': len(value.replace('|', ' ').split()),
    }
    out = dict(option)
    out['semantic_candidate'] = metadata
    audit = {
        'row_id': row.get('row_id'),
        'label': label,
        'value': value,
        **metadata,
    }
    return out, audit


def normalize_row(row: dict[str, Any], *, source_split: str) -> tuple[dict[str, Any], list[dict[str, Any]], dict[str, Any]]:
    out = dict(row)
    out['semantic_candidate_schema_version'] = 'stage11305_per_option_semantic_candidate_v1'
    out['source_split_before_stage11305'] = source_split
    sps = dict(out.get('standalone_projection_source') or {})
    options = sps.get('opaque_options') or []
    normalized_options = []
    option_audits = []
    for idx, option in enumerate(options):
        if not isinstance(option, dict):
            continue
        normalized, audit = normalize_option(option, row=out, option_index=idx)
        normalized_options.append(normalized)
        option_audits.append(audit)
    sps['opaque_options'] = normalized_options
    sps['option_semantic_schema_version'] = 'stage11305_per_option_semantic_candidate_v1'
    sps['option_semantic_records'] = [opt.get('semantic_candidate') for opt in normalized_options]
    out['standalone_projection_source'] = sps

    label = target_label(out)
    inferred = infer_target_label_from_gold(out)
    if not label and inferred:
        out['target_text'] = inferred
        out['decoder_text'] = inferred
        out['bounded_choice_target_label'] = inferred
        label = inferred
    target_in_options = bool(label and any(str(opt.get('label') or '').strip() == label for opt in normalized_options))
    gold = gold_value(out)
    gold_in_options = bool(gold and any(str(opt.get('value') or '').strip() == gold for opt in normalized_options))
    roles = [str((opt.get('semantic_candidate') or {}).get('evidence_role') or '') for opt in normalized_options]
    transitions = [str((opt.get('semantic_candidate') or {}).get('verifier_transition') or '') for opt in normalized_options]
    row_audit = {
        'row_id': out.get('row_id'),
        'source_split': source_split,
        'task_type': out.get('task_type'),
        'language_family': out.get('language_family'),
        'root_id': root_key(out),
        'option_count': len(normalized_options),
        'target_label': label,
        'gold_value': gold,
        'target_in_options': target_in_options,
        'gold_value_in_options': gold_in_options,
        'has_per_option_semantic_metadata': bool(normalized_options) and all(isinstance(opt.get('semantic_candidate'), dict) for opt in normalized_options),
        'evidence_roles': sorted(set(role for role in roles if role)),
        'verifier_transitions': sorted(set(t for t in transitions if t and t != 'NONE')),
        'singleton_option': len(normalized_options) <= 1,
        'admitted_for_semantic_candidate_training': target_in_options and len(normalized_options) > 1,
        'blockers': [],
    }
    if not normalized_options:
        row_audit['blockers'].append('missing_options')
    if not label:
        row_audit['blockers'].append('missing_target_label')
    if label and not target_in_options:
        row_audit['blockers'].append('target_label_not_in_options')
    if len(normalized_options) <= 1:
        row_audit['blockers'].append('singleton_or_empty_options')
    return out, option_audits, row_audit


def counts(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        'rows': len(rows),
        'roots': len({root_key(row) for row in rows}),
        'by_language': dict(sorted(Counter(str(row.get('language_family') or 'unknown') for row in rows).items())),
        'by_task': dict(sorted(Counter(str(row.get('task_type') or 'unknown') for row in rows).items())),
        'by_target_value': dict(sorted(Counter(gold_value(row) or 'unknown' for row in rows).items())),
    }


def main() -> None:
    rows = {name: load_jsonl(path) for name, path in INPUTS.items()}
    train_source = rows['fact_train'] + rows['base_train']
    split_sources = {
        'train': train_source,
        'validation': rows['base_validation'],
        'strict': rows['base_strict'],
        'judgment_validation': rows['fact_validation'],
        'judgment_strict': rows['fact_strict'],
        'residual': rows['residual'],
    }
    normalized: dict[str, list[dict[str, Any]]] = {}
    row_audits: list[dict[str, Any]] = []
    option_audits: list[dict[str, Any]] = []
    for split, split_rows in split_sources.items():
        normalized_rows = []
        for row in split_rows:
            norm, opt_audit, row_audit = normalize_row(row, source_split=split)
            norm['split'] = 'eval' if split in {'validation', 'judgment_validation', 'residual'} else ('strict_eval' if split in {'strict', 'judgment_strict'} else 'train')
            normalized_rows.append(norm)
            option_audits.extend(opt_audit)
            row_audits.append(row_audit)
        normalized[split] = normalized_rows

    write_jsonl(OUTPUTS['train'], normalized['train'])
    write_jsonl(OUTPUTS['validation'], normalized['validation'])
    write_jsonl(OUTPUTS['strict'], normalized['strict'])
    write_jsonl(OUTPUTS['judgment_validation'], normalized['judgment_validation'])
    write_jsonl(OUTPUTS['judgment_strict'], normalized['judgment_strict'])
    write_jsonl(OUTPUTS['residual'], normalized['residual'])
    write_jsonl(OUTPUTS['option_audit'], option_audits)

    by_split_audit: dict[str, dict[str, Any]] = {}
    for split in split_sources:
        audits = [audit for audit in row_audits if audit['source_split'] == split]
        by_split_audit[split] = {
            'rows': len(audits),
            'admitted_for_semantic_candidate_training': sum(1 for audit in audits if audit['admitted_for_semantic_candidate_training']),
            'blocked_rows': sum(1 for audit in audits if audit['blockers']),
            'blockers': dict(sorted(Counter(blocker for audit in audits for blocker in audit['blockers']).items())),
            'singleton_option_rows': sum(1 for audit in audits if audit['singleton_option']),
            'target_missing_rows': [audit['row_id'] for audit in audits if 'missing_target_label' in audit['blockers']][:30],
        }

    train_roots = {root_key(row) for row in normalized['train']}
    protected_roots = {root_key(row) for split in ['validation', 'strict', 'judgment_validation', 'judgment_strict', 'residual'] for row in normalized[split]}
    root_overlaps = sorted(train_roots & protected_roots)
    residual_audits = [audit for audit in row_audits if audit['source_split'] == 'residual']
    summary = {
        'stage': STAGE,
        'stage_name': NAME,
        'created_at_utc': now_utc(),
        'passed': not root_overlaps and by_split_audit['residual']['blocked_rows'] == 0,
        'decision': 'per_option_semantic_candidate_schema_package_built',
        'purpose': 'Normalize bounded rows so scorer objectives can consume per-option task, evidence-role, and verifier-transition metadata instead of inferring all semantics from option value strings.',
        'gold_leak_policy': {
            'per_option_metadata_contains_gold_flags': False,
            'target_label_preserved_at_row_level': True,
            'option_metadata_is_candidate_derived_only': True,
        },
        'counts': {split: counts(split_rows) for split, split_rows in normalized.items()},
        'audit': {
            'by_split': by_split_audit,
            'train_protected_root_overlap_count': len(root_overlaps),
            'train_protected_root_overlaps': root_overlaps[:50],
            'option_metadata_rows': len(option_audits),
            'residual_rows': residual_audits,
        },
        'source_artifacts': {name: rel(path) for name, path in INPUTS.items()},
        'outputs': {name: rel(path) for name, path in OUTPUTS.items()},
        'next_action': {
            'recommended_stage': 'stage11306_per_option_semantic_candidate_probe_request',
            'requirements': [
                'Use the normalized train/eval/strict/residual rows from Stage11305.',
                'Use encoder_option_retrieval_semantic_candidate_head so the new per-option metadata is actually consumed.',
                'Do not promote unless clean strict remains 22/22, residual exceeds 5/10, and verifier_and_test_constraint residual exceeds 0/3.',
            ]
        }
    }
    write_json(SUMMARY_JSON, summary)
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == '__main__':
    main()
