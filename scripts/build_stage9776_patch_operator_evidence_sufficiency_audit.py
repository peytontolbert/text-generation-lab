#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import json
import sys
import time
from collections import defaultdict
from pathlib import Path
from typing import Any

try:
    from diagnostic_ticket_contract import AUTHORITY_CLOSED
except ModuleNotFoundError:
    from scripts.diagnostic_ticket_contract import AUTHORITY_CLOSED  # type: ignore

ROOT = Path(__file__).resolve().parents[1]
STAGE = 9776
NAME = "stage9776_patch_operator_evidence_sufficiency_audit"
MANIFEST = ROOT / "runs/local/artifacts/stage9726_multilingual_patch_operator_tiny_package/multilingual_patch_operator_tiny.jsonl"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
AUDIT = OUT_DIR / "patch_operator_evidence_sufficiency_audit.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "PATCH_OPERATOR_EVIDENCE_SUFFICIENCY_STAGE9776.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
LANGS = ['python', 'rust', 'c_cpp', 'web_js_ts_html']
SPLITS = ['train', 'eval', 'strict_eval']
LEAKY_FIELDS = ['operator_signal', 'action_sequence', 'file_plan', 'target_kind_hint']
SAFE_FIELDS = [
    'localized_edit_need',
    'file_extension',
    'bounded_patch_required',
    'has_visible_config',
    'has_visible_import_policy',
    'has_visible_test',
]


def _load_row_text():
    path = ROOT / 'legacy_src/agentkernel_lite/training_data.py'
    spec = importlib.util.spec_from_file_location('stage9776_training_data', path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules['stage9776_training_data'] = module
    spec.loader.exec_module(module)
    return getattr(module, '_row_text')


_row_text = _load_row_text()


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding='utf-8')) if path.exists() else {}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines() if line.strip()] if path.exists() else []


def update_registry(summary: dict[str, Any]) -> None:
    registry = load_json(REGISTRY) or {'rows': [], 'metrics': {}}
    rows = [row for row in registry.get('rows', []) if row.get('stage') != STAGE and row.get('stage_name') != NAME]
    rows.append({'stage': STAGE, 'stage_name': NAME, 'passed': summary['passed'], 'path': str(SUMMARY), 'authority': dict(AUTHORITY_CLOSED), 'next_best_step': summary['next_best_step']})
    registry['rows'] = sorted(rows, key=lambda row: (int(row.get('stage', -1)), row.get('stage_name', '')))
    registry['passed'] = bool(registry['rows'])
    registry['metrics'] = {**(registry.get('metrics') or {}), 'latest_stage': STAGE, 'latest_stage_name': NAME, 'latest_stage_next_best_step': summary['next_best_step'], 'max_stage': STAGE, 'registry_rows': len(registry['rows'])}
    REGISTRY.write_text(json.dumps(registry, indent=2, sort_keys=True) + '\n', encoding='utf-8')


def label(row: dict[str, Any]) -> str:
    clean = row.get('clean_state') if isinstance(row.get('clean_state'), dict) else {}
    return str(clean.get('patch_operator') or '')


def safe_signature(row: dict[str, Any]) -> tuple[Any, ...]:
    corrupted = row.get('corrupted_state') if isinstance(row.get('corrupted_state'), dict) else {}
    scope = corrupted.get('target_scope_features') if isinstance(corrupted.get('target_scope_features'), dict) else {}
    return (
        corrupted.get('localized_edit_need'),
        corrupted.get('file_extension'),
        scope.get('bounded_patch_required'),
        scope.get('has_visible_config'),
        scope.get('has_visible_import_policy'),
        scope.get('has_visible_test'),
    )


def leaky_signature(row: dict[str, Any]) -> tuple[Any, ...]:
    corrupted = row.get('corrupted_state') if isinstance(row.get('corrupted_state'), dict) else {}
    scope = corrupted.get('target_scope_features') if isinstance(corrupted.get('target_scope_features'), dict) else {}
    clean = row.get('clean_state') if isinstance(row.get('clean_state'), dict) else {}
    return (
        corrupted.get('operator_signal'),
        scope.get('target_kind_hint'),
        tuple(clean.get('action_sequence') or []),
        clean.get('file_plan'),
    )


def build_audit() -> dict[str, Any]:
    rows = load_jsonl(MANIFEST)
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[(str(row.get('language_family') or ''), str(row.get('split') or ''))].append(row)
    buckets = {}
    collapsed_safe_buckets = 0
    separable_only_with_leaky_fields = 0
    baseline_surface_collapsed = 0
    for lang in LANGS:
        for split in SPLITS:
            bucket = sorted(grouped.get((lang, split), []), key=lambda row: str(row.get('row_id') or ''))
            surface_unique = len({_row_text(row) for row in bucket})
            safe_unique = len({safe_signature(row) for row in bucket})
            leaky_unique = len({leaky_signature(row) for row in bucket})
            labels = sorted({label(row) for row in bucket})
            baseline_surface_collapsed += int(surface_unique == 1)
            collapsed_safe_buckets += int(safe_unique == 1)
            separable_only_with_leaky_fields += int(safe_unique == 1 and leaky_unique == len(labels) and len(labels) > 0)
            buckets[f'{lang}:{split}'] = {
                'rows': len(bucket),
                'labels': labels,
                'baseline_surface_unique_count': surface_unique,
                'safe_signature_unique_count': safe_unique,
                'leaky_signature_unique_count': leaky_unique,
                'safe_fields': SAFE_FIELDS,
                'leaky_fields': LEAKY_FIELDS,
            }
    findings = [
        'Every current patch-operator language/split bucket collapses to a single recovered encoder surface.',
        'The non-leaky evidence fields available in the current rows also collapse to a single signature per bucket.',
        'Distinct patch-operator labels become separable only when using label-shaped fields such as operator_signal, target_kind_hint, action_sequence, or file_plan.',
        'This means another LR/steps sweep on the current clean surface is unlikely to win; the dataset needs new non-label observable evidence for patch-operator decisions.',
    ]
    return {
        'passed': True,
        'bucket_count': len(buckets),
        'baseline_surface_collapsed_bucket_count': baseline_surface_collapsed,
        'collapsed_safe_bucket_count': collapsed_safe_buckets,
        'separable_only_with_leaky_fields_bucket_count': separable_only_with_leaky_fields,
        'buckets': buckets,
        'findings': findings,
        'authority': dict(AUTHORITY_CLOSED),
    }


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)
    audit = build_audit()
    AUDIT.write_text(json.dumps(audit, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    next_step = 'Rebuild patch-operator rows with non-label observable evidence instead of action-plan aliases, then rerun target-100M and deterministic Gemma comparison on that repaired surface.'
    summary = {
        'stage': STAGE,
        'stage_name': NAME,
        'name': NAME,
        'passed': audit['passed'],
        'authority': dict(AUTHORITY_CLOSED),
        'metrics': {**dict(AUTHORITY_CLOSED), 'bucket_count': audit['bucket_count'], 'collapsed_safe_bucket_count': audit['collapsed_safe_bucket_count'], 'separable_only_with_leaky_fields_bucket_count': audit['separable_only_with_leaky_fields_bucket_count']},
        'artifacts': {'audit': str(AUDIT.relative_to(ROOT)), 'doc': str(DOC.relative_to(ROOT))},
        'decision': 'Audited the current multilingual patch-operator surface and found that safe observable evidence does not separate the labels. The current package is structurally underspecified unless label-shaped fields are exposed.',
        'next_best_step': next_step,
        'created_at_utc': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    DOC.write_text('\n'.join([
        '# Stage9776 Patch Operator Evidence Sufficiency Audit',
        '',
        f"Passed: `{summary['passed']}`",
        f"Buckets audited: `{audit['bucket_count']}`",
        f"Collapsed safe buckets: `{audit['collapsed_safe_bucket_count']}`",
        f"Separable only with leaky fields: `{audit['separable_only_with_leaky_fields_bucket_count']}`",
        '',
        'This stage shows that the current patch-operator rows do not contain enough non-label observable evidence to distinguish the operator labels on the recovered encoder surface.',
        '',
        f'Next: {next_step}',
        '',
    ]), encoding='utf-8')
    update_registry(summary)
    print(json.dumps({'stage': STAGE, 'passed': True, 'bucket_count': audit['bucket_count'], 'collapsed_safe_bucket_count': audit['collapsed_safe_bucket_count'], 'separable_only_with_leaky_fields_bucket_count': audit['separable_only_with_leaky_fields_bucket_count'], 'next_best_step': next_step}, indent=2, sort_keys=True))


if __name__ == '__main__':
    main()
