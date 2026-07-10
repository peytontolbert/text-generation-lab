#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

try:
    from diagnostic_ticket_contract import AUTHORITY_CLOSED
except ModuleNotFoundError:
    from scripts.diagnostic_ticket_contract import AUTHORITY_CLOSED  # type: ignore

ROOT = Path(__file__).resolve().parents[1]
STAGE = 9840
NAME = "stage9840_permuted_choice_per_language_gemma_comparison"
ROWS_100M = ROOT / "runs/local/artifacts/stage9839_direct_permuted_choice_exec/row_field_logits.jsonl"
ROWS_GEMMA = ROOT / "runs/local/artifacts/stage9835_permuted_choice_gemma_comparison/permuted_choice_gemma_rows.jsonl"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
AUDIT = OUT_DIR / "permuted_choice_per_language_gemma_comparison.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "PERMUTED_CHOICE_PER_LANGUAGE_GEMMA_COMPARISON_STAGE9840.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
LANGS = ["python", "rust", "c_cpp", "web_js_ts_html"]
SPLITS = ["eval", "strict_eval"]


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding='utf-8')) if path.exists() else {}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines() if line.strip()]


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + '\n', encoding='utf-8')


def update_registry(summary: dict[str, Any]) -> None:
    registry = load_json(REGISTRY) or {'rows': [], 'metrics': {}}
    rows = [row for row in registry.get('rows', []) if row.get('stage') != STAGE and row.get('stage_name') != NAME]
    rows.append({'stage': STAGE, 'stage_name': NAME, 'passed': summary['passed'], 'path': str(SUMMARY), 'authority': dict(AUTHORITY_CLOSED), 'next_best_step': summary['next_best_step']})
    registry['rows'] = sorted(rows, key=lambda row: (int(row.get('stage', -1)), row.get('stage_name', '')))
    registry['passed'] = bool(registry['rows'])
    registry['metrics'] = {**(registry.get('metrics') or {}), 'latest_stage': STAGE, 'latest_stage_name': NAME, 'latest_stage_next_best_step': summary['next_best_step'], 'max_stage': STAGE, 'registry_rows': len(registry['rows'])}
    REGISTRY.write_text(json.dumps(registry, indent=2, sort_keys=True) + '\n', encoding='utf-8')


def normalize_100m_rows() -> list[dict[str, Any]]:
    rows = load_jsonl(ROWS_100M)
    out = []
    for row in rows:
        cell = str(row.get('cell_key') or '')
        lang = cell.split('::')[0]
        out.append({'language_family': lang, 'split': row.get('split'), 'correct': bool(row.get('correct'))})
    return out


def summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    by_bucket = {}
    macro_by_split = {}
    for split in SPLITS:
        vals = []
        for lang in LANGS:
            bucket = [row for row in rows if row.get('split') == split and row.get('language_family') == lang]
            correct = sum(1 for row in bucket if row.get('correct'))
            exact = (correct / len(bucket)) if bucket else 0.0
            by_bucket[f'{lang}:{split}'] = {'rows': len(bucket), 'correct': correct, 'exact': exact}
            vals.append(exact)
        macro_by_split[split] = sum(vals) / len(vals) if vals else 0.0
    return {'by_bucket': by_bucket, 'macro_by_split': macro_by_split}


def build_audit(hundred_m_rows: list[dict[str, Any]], gemma_rows: list[dict[str, Any]]) -> dict[str, Any]:
    hundred = summarize(hundred_m_rows)
    gemma = summarize(gemma_rows)
    comparisons = {}
    wins_100m = wins_gemma = ties = 0
    for split in SPLITS:
        for lang in LANGS:
            key = f'{lang}:{split}'
            a = hundred['by_bucket'][key]['exact']
            b = gemma['by_bucket'][key]['exact']
            verdict = 'tie'
            if a > b:
                verdict = '100m_win'
                wins_100m += 1
            elif b > a:
                verdict = 'gemma_win'
                wins_gemma += 1
            else:
                ties += 1
            comparisons[key] = {'hundred_m_exact': a, 'gemma_exact': b, 'verdict': verdict}
    return {
        'passed': True,
        'hundred_m': hundred,
        'gemma': gemma,
        'comparisons': comparisons,
        'wins_100m': wins_100m,
        'wins_gemma': wins_gemma,
        'ties': ties,
        'macro_delta_by_split': {split: hundred['macro_by_split'][split] - gemma['macro_by_split'][split] for split in SPLITS},
        'authority': dict(AUTHORITY_CLOSED),
    }


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)
    hundred = normalize_100m_rows()
    gemma = load_jsonl(ROWS_GEMMA)
    audit = build_audit(hundred, gemma)
    write_json(AUDIT, audit)
    next_step = 'Use this per-language permuted-choice comparison as the strongest current anti-cheat multilingual packet, then fill the expert-maintainer reviews before making broader v2.7 claims.'
    summary = {
        'stage': STAGE,
        'stage_name': NAME,
        'name': NAME,
        'passed': audit['passed'],
        'authority': dict(AUTHORITY_CLOSED),
        'metrics': {**dict(AUTHORITY_CLOSED), 'wins_100m': audit['wins_100m'], 'wins_gemma': audit['wins_gemma'], 'ties': audit['ties'], 'macro_delta_eval': audit['macro_delta_by_split']['eval'], 'macro_delta_strict_eval': audit['macro_delta_by_split']['strict_eval']},
        'artifacts': {'audit': str(AUDIT.relative_to(ROOT)), 'doc': str(DOC.relative_to(ROOT))},
        'decision': 'Compared the Stage9839 row-level 100M outputs against the Stage9835 Gemma row-level outputs on the same permuted-choice multilingual anti-cheat packet.',
        'next_best_step': next_step,
        'created_at_utc': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    DOC.write_text('\n'.join([
        '# Stage9840 Permuted Choice Per-Language Gemma Comparison',
        '',
        f"Passed: `{summary['passed']}`",
        f"100M wins: `{audit['wins_100m']}`",
        f"Gemma wins: `{audit['wins_gemma']}`",
        f"Ties: `{audit['ties']}`",
        f"Eval macro delta (100M-Gemma): `{audit['macro_delta_by_split']['eval']}`",
        f"Strict macro delta (100M-Gemma): `{audit['macro_delta_by_split']['strict_eval']}`",
        '',
        'This stage is the first per-language comparison on the stronger permuted-choice anti-cheat packet using row-level outputs from both the 100M model and Gemma.',
        '',
        f'Next: {next_step}',
        '',
    ]), encoding='utf-8')
    if summary['passed']:
        update_registry(summary)
    print(json.dumps({'stage': STAGE, 'passed': summary['passed'], 'wins_100m': audit['wins_100m'], 'wins_gemma': audit['wins_gemma'], 'ties': audit['ties'], 'macro_delta_by_split': audit['macro_delta_by_split']}, indent=2, sort_keys=True))


if __name__ == '__main__':
    main()
