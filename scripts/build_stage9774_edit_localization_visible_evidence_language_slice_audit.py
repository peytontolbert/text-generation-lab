#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from collections import defaultdict
from pathlib import Path
from typing import Any

try:
    from diagnostic_ticket_contract import AUTHORITY_CLOSED
except ModuleNotFoundError:
    from scripts.diagnostic_ticket_contract import AUTHORITY_CLOSED  # type: ignore

ROOT = Path(__file__).resolve().parents[1]
STAGE = 9774
NAME = "stage9774_edit_localization_visible_evidence_language_slice_audit"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
AUDIT = OUT_DIR / "edit_localization_visible_evidence_language_slice_audit.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "EDIT_LOCALIZATION_VISIBLE_EVIDENCE_LANGUAGE_SLICE_AUDIT_STAGE9774.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
SOURCE_SUMMARY = ROOT / "runs/summaries/stage9773_edit_localization_visible_evidence_execution_audit.json"
BASELINE_AUDIT = ROOT / "runs/local/artifacts/stage9745_edit_localization_target_only_language_slice_audit/edit_localization_target_only_language_slice_audit.json"
MANIFEST = ROOT / "runs/local/artifacts/stage9771_edit_localization_visible_evidence_lift_package/edit_localization_visible_evidence_lift.jsonl"
LOGITS = ROOT / "runs/local/artifacts/stage9773_edit_localization_visible_evidence_exec/row_field_logits.jsonl"
LANGS = ['python', 'rust', 'c_cpp', 'web_js_ts_html']
SPLITS = ['eval', 'strict_eval']
EXPECTED_ROWS_PER_LANGUAGE_SPLIT = 5


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


def build_audit() -> dict[str, Any]:
    source = load_json(SOURCE_SUMMARY)
    baseline = load_json(BASELINE_AUDIT)
    manifest = {row['row_id']: row['language_family'] for row in load_jsonl(MANIFEST)}
    logits = load_jsonl(LOGITS)
    grouped = defaultdict(lambda: defaultdict(lambda: {'rows': 0, 'correct': 0, 'pred_counts': defaultdict(int)}))
    failures: list[str] = []
    for row in logits:
        row_id = row.get('row_id')
        if row_id not in manifest:
            failures.append('unmapped_row_id')
            continue
        lang = manifest[row_id]
        split = row.get('split')
        pred = row.get('pred')
        grouped[lang][split]['rows'] += 1
        grouped[lang][split]['correct'] += int(row.get('correct') is True)
        if pred is not None:
            grouped[lang][split]['pred_counts'][str(pred)] += 1
    baseline_slices = baseline.get('language_slices') if isinstance(baseline.get('language_slices'), dict) else {}
    language_slices = {}
    uniform_improvement = True
    for lang in LANGS:
        language_slices[lang] = {}
        baseline_lang = baseline_slices.get(lang) if isinstance(baseline_slices.get(lang), dict) else {}
        for split in SPLITS:
            rows = grouped[lang][split]['rows']
            correct = grouped[lang][split]['correct']
            pred_counts = dict(sorted(grouped[lang][split]['pred_counts'].items()))
            baseline_split = baseline_lang.get(split) if isinstance(baseline_lang.get(split), dict) else {}
            baseline_exact = baseline_split.get('exact')
            exact = (correct / rows) if rows else None
            if rows != EXPECTED_ROWS_PER_LANGUAGE_SPLIT:
                failures.append(f'unexpected_rows:{lang}:{split}')
            if baseline_exact is None or exact is None or exact <= float(baseline_exact):
                uniform_improvement = False
            language_slices[lang][split] = {
                'rows': rows,
                'correct': correct,
                'exact': exact,
                'baseline_exact': baseline_exact,
                'improved_over_stage9745': None if baseline_exact is None or exact is None else bool(exact > float(baseline_exact)),
                'pred_counts': pred_counts,
            }
    if source.get('passed') is not True:
        failures.append('stage9773_not_passed')
    if baseline.get('passed') is not True:
        failures.append('stage9745_not_passed')
    return {
        'passed': not failures,
        'failures': failures,
        'language_slices': language_slices,
        'uniform_improvement_over_stage9745': uniform_improvement,
        'authority': dict(AUTHORITY_CLOSED),
    }


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)
    audit = build_audit()
    AUDIT.write_text(json.dumps(audit, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    next_step = 'If Stage9771 improves only some languages, use the slice gaps to decide whether more visible evidence or more balanced counterexamples are needed before another multilingual Gemma comparison.'
    summary = {
        'stage': STAGE,
        'stage_name': NAME,
        'name': NAME,
        'passed': audit['passed'],
        'authority': dict(AUTHORITY_CLOSED),
        'metrics': {**dict(AUTHORITY_CLOSED), 'uniform_improvement_over_stage9745': audit['uniform_improvement_over_stage9745']},
        'artifacts': {'audit': str(AUDIT.relative_to(ROOT)), 'doc': str(DOC.relative_to(ROOT))},
        'decision': 'Recorded the per-language effect of the visible-evidence edit-localization intervention against the prior target-only language-slice baseline.',
        'next_best_step': next_step,
        'created_at_utc': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    DOC.write_text('\n'.join([
        '# Stage9774 Edit Localization Visible Evidence Language Slice Audit',
        '',
        f"Passed: `{summary['passed']}`",
        f"Uniform improvement over Stage9745: `{audit['uniform_improvement_over_stage9745']}`",
        f"Language slices: `{audit['language_slices']}`",
        '',
        'This stage compares per-language visible-evidence results against the prior target-only edit-localization baseline.',
        '',
        f'Next: {next_step}',
        '',
    ]), encoding='utf-8')
    if summary['passed']:
        update_registry(summary)
    print(json.dumps({'stage': STAGE, 'passed': summary['passed'], 'uniform_improvement_over_stage9745': audit['uniform_improvement_over_stage9745'], 'failures': audit['failures'], 'next_best_step': next_step}, indent=2, sort_keys=True))
    if audit['failures']:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
