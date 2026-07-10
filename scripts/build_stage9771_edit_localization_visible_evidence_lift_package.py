#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any
import importlib.util
import sys

try:
    from diagnostic_ticket_contract import AUTHORITY_CLOSED
except ModuleNotFoundError:
    from scripts.diagnostic_ticket_contract import AUTHORITY_CLOSED  # type: ignore

ROOT = Path(__file__).resolve().parents[1]
STAGE = 9771
NAME = "stage9771_edit_localization_visible_evidence_lift_package"
SOURCE = ROOT / "runs/local/artifacts/stage9743_multilingual_edit_localization_target_only_package/multilingual_edit_localization_target_only.jsonl"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
MANIFEST = OUT_DIR / "edit_localization_visible_evidence_lift.jsonl"
AUDIT = OUT_DIR / "edit_localization_visible_evidence_lift_audit.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "EDIT_LOCALIZATION_VISIBLE_EVIDENCE_LIFT_STAGE9771.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
LANGS = ["python", "rust", "c_cpp", "web_js_ts_html"]
SPLITS = ["train", "eval", "strict_eval"]
KEEP_LABELS = [
    "TARGET_CONFIG",
    "TARGET_ENTRYPOINT",
    "TARGET_FILE",
    "TARGET_SYMBOL",
    "TARGET_TEST",
]


def _load_row_text():
    path = ROOT / 'legacy_src/agentkernel_lite/training_data.py'
    spec = importlib.util.spec_from_file_location('stage9771_training_data', path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules['stage9771_training_data'] = module
    spec.loader.exec_module(module)
    return getattr(module, '_row_text')


_row_text = _load_row_text()


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding='utf-8')) if path.exists() else {}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines() if line.strip()] if path.exists() else []


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(''.join(json.dumps(row, sort_keys=True) + '\n' for row in rows), encoding='utf-8')


def lifted_input_state(row: dict[str, Any]) -> dict[str, Any]:
    corrupted = row.get('corrupted_state') if isinstance(row.get('corrupted_state'), dict) else {}
    neutral = corrupted.get('neutral_context_bits') if isinstance(corrupted.get('neutral_context_bits'), dict) else {}
    return {
        'task_observation': str(corrupted.get('task_observation') or ''),
        'visible_locality_evidence': str(corrupted.get('visible_locality_evidence') or ''),
        'file_extension': str(corrupted.get('file_extension') or ''),
        'context_config_visible': bool(neutral.get('config_visible', False)),
        'context_entrypoint_visible': bool(neutral.get('entrypoint_visible', False)),
        'context_symbol_names_visible': bool(neutral.get('symbol_names_visible', False)),
        'context_tests_visible': bool(neutral.get('tests_visible', False)),
    }


def lift_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    lifted = []
    for row in rows:
        new_row = dict(row)
        new_row['input_state'] = lifted_input_state(row)
        new_row['surface'] = 'edit_localization_visible_evidence_lift_v1'
        anti_cheat = dict(row.get('anti_cheat') or {})
        anti_cheat['visible_locality_evidence_lifted'] = True
        anti_cheat['target_label_literals_in_lifted_evidence'] = False
        anti_cheat['action_sequence_lifted'] = False
        anti_cheat['file_plan_lifted'] = False
        anti_cheat['locality_signal_lifted'] = False
        new_row['anti_cheat'] = anti_cheat
        lifted.append(new_row)
    return lifted


def _bucket_key(row: dict[str, Any]) -> tuple[str, str]:
    return str(row.get('language_family') or ''), str(row.get('split') or '')


def _label(row: dict[str, Any]) -> str:
    clean = row.get('clean_state') if isinstance(row.get('clean_state'), dict) else {}
    return str(clean.get('edit_localization_target') or '')


def summarize_surface_uniqueness(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    grouped: dict[tuple[str, str], dict[str, str]] = defaultdict(dict)
    for row in rows:
        grouped[_bucket_key(row)][_label(row)] = _row_text(row)
    summary: dict[str, dict[str, Any]] = {}
    for (lang, split), mapping in grouped.items():
        unique_count = len(set(mapping.values()))
        summary[f'{lang}:{split}'] = {
            'label_count': len(mapping),
            'unique_surface_count': unique_count,
            'all_labels_surface_distinct': unique_count == len(mapping) == len(KEEP_LABELS),
        }
    return dict(sorted(summary.items()))


def collect_failures(rows: list[dict[str, Any]]) -> list[str]:
    failures: list[str] = []
    for row in rows:
        text = _row_text(row)
        if 'TARGET_' in text:
            failures.append(f"target_label_literal_present:{row.get('row_id')}")
        if 'LOCALIZE_' in text or 'PLAN_PATCH' in text or 'READ_' in text or 'BIND_SYMBOL' in text:
            failures.append(f"action_sequence_leak_present:{row.get('row_id')}")
        anti = row.get('anti_cheat') if isinstance(row.get('anti_cheat'), dict) else {}
        if anti.get('file_plan_lifted') is not False:
            failures.append(f"file_plan_lift_flag_invalid:{row.get('row_id')}")
        if anti.get('locality_signal_lifted') is not False:
            failures.append(f"locality_signal_lift_flag_invalid:{row.get('row_id')}")
    return failures


def update_registry(summary: dict[str, Any]) -> None:
    registry = load_json(REGISTRY) or {'rows': [], 'metrics': {}}
    rows = [row for row in registry.get('rows', []) if row.get('stage') != STAGE and row.get('stage_name') != NAME]
    rows.append({'stage': STAGE, 'stage_name': NAME, 'passed': summary['passed'], 'path': str(SUMMARY), 'authority': dict(AUTHORITY_CLOSED), 'next_best_step': summary['next_best_step']})
    registry['rows'] = sorted(rows, key=lambda row: (int(row.get('stage', -1)), row.get('stage_name', '')))
    registry['passed'] = bool(registry['rows'])
    registry['metrics'] = {**(registry.get('metrics') or {}), 'latest_stage': STAGE, 'latest_stage_name': NAME, 'latest_stage_next_best_step': summary['next_best_step'], 'max_stage': STAGE, 'registry_rows': len(registry['rows'])}
    REGISTRY.write_text(json.dumps(registry, indent=2, sort_keys=True) + '\n', encoding='utf-8')


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)
    source_rows = load_jsonl(SOURCE)
    lifted_rows = lift_rows(source_rows)
    write_jsonl(MANIFEST, lifted_rows)
    baseline_uniqueness = summarize_surface_uniqueness(source_rows)
    lifted_uniqueness = summarize_surface_uniqueness(lifted_rows)
    failures = collect_failures(lifted_rows)
    improved_buckets = 0
    for key, base in baseline_uniqueness.items():
        lifted = lifted_uniqueness.get(key, {})
        if lifted.get('unique_surface_count', 0) > base.get('unique_surface_count', 0):
            improved_buckets += 1
    audit = {
        'passed': not failures,
        'rows': len(lifted_rows),
        'language_counts': dict(sorted(Counter(str(row.get('language_family') or '') for row in lifted_rows).items())),
        'split_counts': dict(sorted(Counter(str(row.get('split') or '') for row in lifted_rows).items())),
        'label_counts': dict(sorted(Counter(_label(row) for row in lifted_rows).items())),
        'baseline_surface_uniqueness': baseline_uniqueness,
        'lifted_surface_uniqueness': lifted_uniqueness,
        'improved_bucket_count': improved_buckets,
        'failures': failures,
        'anti_cheat_findings': [
            'Lifted evidence excludes target label literals, action_sequence, file_plan, locality_signal, raw source, and source row ids.',
            'Visible locality evidence is surfaced as observed task evidence, not as the canonical target label.',
            'This package should still be reviewed against expert-maintainer expectations because the lifted evidence phrases are templated and semantically strong.',
        ],
        'authority': dict(AUTHORITY_CLOSED),
    }
    AUDIT.write_text(json.dumps(audit, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    next_step = 'Train and compare a 100M edit-localization run on the visible-evidence-lift package, then verify whether it breaks the current 0.2 multilingual tie against deterministic Gemma.'
    summary = {
        'stage': STAGE,
        'stage_name': NAME,
        'name': NAME,
        'passed': audit['passed'],
        'authority': dict(AUTHORITY_CLOSED),
        'metrics': {**dict(AUTHORITY_CLOSED), 'rows': audit['rows'], 'improved_bucket_count': improved_buckets},
        'artifacts': {'manifest': str(MANIFEST.relative_to(ROOT)), 'audit': str(AUDIT.relative_to(ROOT)), 'doc': str(DOC.relative_to(ROOT))},
        'decision': 'Materialized an edit-localization package that lifts visible, label-free locality evidence into the encoder surface. This directly addresses the recovered surface bottleneck where the baseline serializer exposed too little information to separate config, entrypoint, file, symbol, and test targets.',
        'next_best_step': next_step,
        'created_at_utc': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    DOC.write_text('\n'.join([
        '# Stage9771 Edit Localization Visible Evidence Lift Package',
        '',
        f"Passed: `{summary['passed']}`",
        f"Rows: `{audit['rows']}`",
        f"Improved language/split buckets: `{audit['improved_bucket_count']}`",
        '',
        'This package lifts non-label literal locality evidence into `input_state` so the recovered encoder surface can actually see the distinctions that the target-only baseline was hiding.',
        '',
        'Anti-cheat notes:',
        '- target label literals are not lifted',
        '- action sequence and file plan are not lifted',
        '- locality signal ids are not lifted',
        '- raw source and source row ids remain hidden',
        '',
        f'Next: {next_step}',
        '',
    ]), encoding='utf-8')
    if summary['passed']:
        update_registry(summary)
    print(json.dumps({'stage': STAGE, 'passed': summary['passed'], 'rows': audit['rows'], 'improved_bucket_count': improved_buckets, 'failures': failures, 'next_best_step': next_step}, indent=2, sort_keys=True))
    if failures:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
