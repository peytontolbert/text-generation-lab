#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import json
import sys
import time
import urllib.request
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

try:
    from diagnostic_ticket_contract import AUTHORITY_CLOSED
except ModuleNotFoundError:
    from scripts.diagnostic_ticket_contract import AUTHORITY_CLOSED  # type: ignore

ROOT = Path(__file__).resolve().parents[1]
STAGE = 9775
NAME = "stage9775_edit_localization_visible_evidence_gemma_comparison"
MANIFEST = ROOT / "runs/local/artifacts/stage9771_edit_localization_visible_evidence_lift_package/edit_localization_visible_evidence_lift.jsonl"
BASELINE = ROOT / "runs/local/artifacts/stage9774_edit_localization_visible_evidence_language_slice_audit/edit_localization_visible_evidence_language_slice_audit.json"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
AUDIT = OUT_DIR / "edit_localization_visible_evidence_gemma_comparison.json"
ROWS_OUT = OUT_DIR / "edit_localization_visible_evidence_gemma_rows.jsonl"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "EDIT_LOCALIZATION_VISIBLE_EVIDENCE_GEMMA_COMPARISON_STAGE9775.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
MODEL_ID = 'gemma3:12b'
SPLIT = 'strict_eval'
LANGS = ['python', 'rust', 'c_cpp', 'web_js_ts_html']
FIELD = 'edit_localization'
LABEL_FIELD = 'edit_localization_target'


def _load_row_text():
    path = ROOT / 'legacy_src/agentkernel_lite/training_data.py'
    spec = importlib.util.spec_from_file_location('stage9775_training_data', path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules['stage9775_training_data'] = module
    spec.loader.exec_module(module)
    return getattr(module, '_row_text')


_row_text = _load_row_text()


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding='utf-8')) if path.exists() else {}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines() if line.strip()] if path.exists() else []


def _label(row: dict[str, Any]) -> str:
    clean = row.get('clean_state') if isinstance(row.get('clean_state'), dict) else {}
    return str(clean.get(LABEL_FIELD) or '')


def label_vocab(rows: list[dict[str, Any]]) -> list[str]:
    return sorted({_label(row) for row in rows if _label(row)})


def build_prompt(row: dict[str, Any], labels: list[str]) -> str:
    return '\n'.join([
        'You are evaluating a structured software-maintenance state.',
        f'Return only the exact label for `{FIELD}`.',
        f"Valid labels: {', '.join(labels)}",
        'Do not explain your answer. Output one label only.',
        '',
        'Structured input surface:',
        _row_text(row),
    ])


def ollama_generate(prompt: str) -> str:
    payload = json.dumps({
        'model': MODEL_ID,
        'prompt': prompt,
        'stream': False,
        'options': {'seed': 0, 'temperature': 0.0},
    }).encode('utf-8')
    request = urllib.request.Request(
        'http://127.0.0.1:11434/api/generate',
        data=payload,
        headers={'Content-Type': 'application/json'},
    )
    with urllib.request.urlopen(request, timeout=300) as response:
        body = json.loads(response.read().decode('utf-8'))
    return str(body.get('response') or '').strip()


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
    rows = [row for row in load_jsonl(MANIFEST) if row.get('split') == SPLIT]
    labels = label_vocab(load_jsonl(MANIFEST))
    baseline = load_json(BASELINE)
    baseline_slices = baseline.get('language_slices') if isinstance(baseline.get('language_slices'), dict) else {}
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[str(row.get('language_family') or '')].append(row)
    row_outputs: list[dict[str, Any]] = []
    results = []
    wins_100m = 0
    wins_gemma = 0
    ties = 0
    pred_counts: Counter[str] = Counter()
    for lang in LANGS:
        lang_rows = sorted(grouped.get(lang, []), key=lambda row: str(row.get('row_id') or ''))
        correct = 0
        for row in lang_rows:
            prompt = build_prompt(row, labels)
            raw = ollama_generate(prompt)
            pred = raw.splitlines()[0].strip() if raw else ''
            expected = _label(row)
            ok = pred == expected
            correct += int(ok)
            pred_counts[pred] += 1
            row_outputs.append({
                'language': lang,
                'row_id': row.get('row_id'),
                'split': SPLIT,
                'expected_label': expected,
                'predicted_label': pred,
                'correct': ok,
                'raw_output': raw,
                'label_vocab_scope': 'full_packet',
                'decoder_seed': 0,
                'decoder_temperature': 0.0,
                'prompt': prompt,
            })
        gemma_exact = (correct / len(lang_rows)) if lang_rows else None
        baseline_lang = baseline_slices.get(lang) if isinstance(baseline_slices.get(lang), dict) else {}
        model_exact = (baseline_lang.get('strict_eval') or {}).get('exact') if isinstance(baseline_lang.get('strict_eval'), dict) else None
        verdict = 'tie'
        if model_exact is not None and gemma_exact is not None:
            if float(model_exact) > float(gemma_exact):
                verdict = '100m_better'
                wins_100m += 1
            elif float(model_exact) < float(gemma_exact):
                verdict = 'gemma_better'
                wins_gemma += 1
            else:
                ties += 1
        results.append({
            'language': lang,
            'rows': len(lang_rows),
            'gemma_strict_exact': gemma_exact,
            'model_strict_exact_100m': model_exact,
            'verdict': verdict,
        })
    ROWS_OUT.write_text(''.join(json.dumps(row, sort_keys=True) + '\n' for row in row_outputs), encoding='utf-8')
    audit = {
        'passed': True,
        'model_id': MODEL_ID,
        'split': SPLIT,
        'decoder_seed': 0,
        'decoder_temperature': 0.0,
        'label_vocab_scope': 'full_packet',
        'results': results,
        'wins_100m': wins_100m,
        'wins_gemma': wins_gemma,
        'ties': ties,
        'predicted_label_counts': dict(sorted(pred_counts.items())),
        'authority': dict(AUTHORITY_CLOSED),
    }
    AUDIT.write_text(json.dumps(audit, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    next_step = 'Use the Stage9771 lifted package as the new edit-localization comparison surface, then decide whether to harden it further for expert-maintainer anti-cheat review before broadening the same evidence-lift idea.'
    summary = {
        'stage': STAGE,
        'stage_name': NAME,
        'name': NAME,
        'passed': True,
        'authority': dict(AUTHORITY_CLOSED),
        'metrics': {**dict(AUTHORITY_CLOSED), 'wins_100m': wins_100m, 'wins_gemma': wins_gemma, 'ties': ties},
        'artifacts': {'audit': str(AUDIT.relative_to(ROOT)), 'rows': str(ROWS_OUT.relative_to(ROOT)), 'doc': str(DOC.relative_to(ROOT))},
        'decision': 'Compared deterministic Gemma against the Stage9771 lifted edit-localization surface using the same strict-eval language slices as the Stage9774 100M audit.',
        'next_best_step': next_step,
        'created_at_utc': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    DOC.write_text('\n'.join([
        '# Stage9775 Edit Localization Visible Evidence Gemma Comparison',
        '',
        f"Passed: `{summary['passed']}`",
        f"100M wins: `{wins_100m}`",
        f"Gemma wins: `{wins_gemma}`",
        f"Ties: `{ties}`",
        '',
        'This stage compares deterministic Gemma against the Stage9771 lifted edit-localization surface on the same strict-eval language slices used by Stage9774.',
        '',
        f'Next: {next_step}',
        '',
    ]), encoding='utf-8')
    update_registry(summary)
    print(json.dumps({'stage': STAGE, 'wins_100m': wins_100m, 'wins_gemma': wins_gemma, 'ties': ties, 'passed': True, 'next_best_step': next_step}, indent=2, sort_keys=True))


if __name__ == '__main__':
    main()
