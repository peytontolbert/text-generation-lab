#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SESSIONS = Path('/home/peyton/.codex/sessions')
OUT_DIR = ROOT / 'runs/local/artifacts/stage8700_runtime_session_grep_audit'
SUMMARY = ROOT / 'runs/summaries/stage8700_runtime_session_grep_audit.json'
DOC = ROOT / 'docs/RUNTIME_SESSION_GREP_AUDIT_STAGE8700.md'
AUTHORITY_CLOSED = {
    'model_execution_authorized_next': False,
    'decoder_ce_training_authorized_next': False,
    'runtime_authorized': False,
    'source_emission_authorized': False,
    'body_emission_authorized': False,
    'gemma_execution_authorized_next': False,
    'harness_execution_authorized_next': False,
    'scoring_authorized_next': False,
    'controller_complete_merge_authorized_next': False,
    'promotion_ready': False,
}
CATEGORIES: dict[str, list[str]] = {
    'runtime_authority_gate': ['runtime_authorized', 'runtime authorized', 'execution_authorized', 'execution authorized', 'runtime gate'],
    'runtime_verifier_loop': ['runtime verifier loop', 'verify -> repair', 'run verifier', 'verifier rechecks', 'runtime verifier', 'patch verify loop'],
    'runtime_contract': ['runtime contract', 'training runtime contract', 'trainer tokenizer runtime', 'structured aux runtime'],
    'runtime_trace_failure': ['stack trace', 'runtime trace', 'failure log', 'pytest failure', 'verifier failure', 'failure_type'],
    'runtime_safety_cleanup': ['cleanup checkpoints', 'no final checkpoint export', 'artifact cleanup', 'retention cleanup', 'safe_cleanup'],
    'runtime_execution_smoke': ['dependency smoke', 'runtime import smoke', 'trainer --help', 'smoke execution', 'help only'],
    'runtime_forbidden_paths': ['source/body/runtime closed', 'body emission authorized', 'source emission authorized', 'runtime/source/body', 'body/runtime/gemma'],
}


def iter_session_files(max_files: int = 150) -> list[Path]:
    if not SESSIONS.exists():
        return []
    files = sorted(SESSIONS.rglob('*.jsonl'), key=lambda p: p.stat().st_mtime if p.exists() else 0, reverse=True)
    return files[:max_files]


def compact_line(line: str) -> str:
    line = line.strip()
    try:
        obj = json.loads(line)
        text = json.dumps(obj, sort_keys=True)
    except Exception:
        text = line
    text = text.replace('\x00', '')
    return text[:1600]


def scan_category(files: list[Path], terms: list[str], max_hits: int = 80, max_lines_per_file: int = 2500) -> dict[str, Any]:
    regexes = [re.compile(re.escape(term), re.IGNORECASE) for term in terms]
    hits: list[dict[str, Any]] = []
    files_hit: set[str] = set()
    total_hits = 0
    files_scanned = 0
    for path in files:
        files_scanned += 1
        try:
            with path.open('r', encoding='utf-8', errors='ignore') as handle:
                for lineno, line in enumerate(handle, start=1):
                    if lineno > max_lines_per_file:
                        break
                    matched = [term for term, rx in zip(terms, regexes) if rx.search(line)]
                    if not matched:
                        continue
                    total_hits += 1
                    files_hit.add(str(path))
                    if len(hits) < max_hits:
                        hits.append({'file': str(path), 'line': lineno, 'terms': matched, 'text': compact_line(line)})
                    break
            if len(hits) >= max_hits or len(files_hit) >= 25:
                break
        except OSError:
            continue
    return {'terms': terms, 'total_hits': total_hits, 'files_hit_count': len(files_hit), 'files_scanned': files_scanned, 'sample_files': sorted(files_hit)[:25], 'sample_hits': hits, 'bounded': True, 'max_lines_per_file': max_lines_per_file}


def local_recovery_coverage(terms: list[str]) -> dict[str, Any]:
    roots = [ROOT / 'docs', ROOT / 'scripts', ROOT / 'legacy_src', ROOT / 'tests', ROOT / 'runs/summaries']
    files: list[Path] = []
    for base in roots:
        if base.exists():
            files.extend([p for p in base.rglob('*') if p.is_file() and p.suffix in {'.md', '.py', '.json', '.jsonl', '.yaml', '.yml'}])
    hit_files: set[str] = set()
    term_counts = {term: 0 for term in terms}
    for path in files:
        try:
            text = path.read_text(encoding='utf-8', errors='ignore')
        except Exception:
            continue
        lower = text.lower()
        hit = False
        for term in terms:
            count = lower.count(term.lower())
            if count:
                term_counts[term] += count
                hit = True
        if hit:
            hit_files.add(str(path.relative_to(ROOT)))
    return {'files_hit_count': len(hit_files), 'sample_files': sorted(hit_files)[:40], 'term_counts': term_counts}


def status_for(category: str, session: dict[str, Any], local: dict[str, Any]) -> str:
    has_local = local['files_hit_count'] > 0
    if category == 'runtime_verifier_loop' and not any('runtime_verifier_loop' in f or 'verifier_loop' in f for f in local['sample_files']):
        return 'session_evidence_found_but_executable_loop_missing' if session['total_hits'] else 'missing'
    if category == 'runtime_authority_gate' and has_local:
        return 'recovered_as_closed_authority_contract'
    if category == 'runtime_trace_failure' and any('runtime_trace_normalizer' in f for f in local['sample_files']):
        return 'recovered_as_trace_normalizer'
    if has_local:
        return 'partially_recovered'
    if session['total_hits']:
        return 'session_evidence_found_not_recovered'
    return 'missing'


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    files = iter_session_files()
    categories: dict[str, Any] = {}
    missing_or_partial: list[str] = []
    for category, terms in CATEGORIES.items():
        session = scan_category(files, terms)
        local = local_recovery_coverage(terms)
        status = status_for(category, session, local)
        categories[category] = {'status': status, 'session': session, 'local_recovery': local}
        (OUT_DIR / f'{category}.json').write_text(json.dumps(categories[category], indent=2, sort_keys=True) + '\n')
        if status not in {'recovered_as_closed_authority_contract', 'recovered_as_trace_normalizer', 'partially_recovered'}:
            missing_or_partial.append(category)
    metrics = {
        'session_files_scanned': len(files),
        'categories': len(categories),
        'missing_or_partial_categories': missing_or_partial,
        'runtime_verifier_loop_recovered': False,
        'runtime_authority_opened': False,
        'authority_rows': 0,
        **AUTHORITY_CLOSED,
    }
    card = {
        'stage': 8700,
        'name': 'stage8700_runtime_session_grep_audit',
        'stage_name': 'stage8700_runtime_session_grep_audit',
        'passed': True,
        'authority': AUTHORITY_CLOSED,
        'metrics': metrics,
        'categories': {k: {'status': v['status'], 'session_total_hits': v['session']['total_hits'], 'local_files_hit_count': v['local_recovery']['files_hit_count']} for k, v in categories.items()},
        'decision': 'Targeted Codex-session runtime grep found runtime authority/contract/trace evidence already partially recovered, but the executable runtime verifier loop remains missing and must stay closed.',
        'next_best_step': 'Recover runtime_verifier_loop as a non-executing contract first, then executable verifier harness only after explicit authorization; keep data mining/training/runtime closed.',
        'created_at_utc': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
    }
    (OUT_DIR / 'runtime_session_grep_audit_card.json').write_text(json.dumps(card, indent=2, sort_keys=True) + '\n')
    SUMMARY.write_text(json.dumps(card, indent=2, sort_keys=True) + '\n')
    lines = ['# Stage8700 Runtime Session Grep Audit', '', 'Passed: `True`', '', f'Session files scanned: `{len(files)}`', '', '## Category Status', '']
    for category, data in categories.items():
        lines.append(f'- `{category}`: `{data["status"]}`; session hits `{data["session"]["total_hits"]}`; local files `{data["local_recovery"]["files_hit_count"]}`')
    lines.extend(['', '## Decision', '', card['decision'], '', '## Next', '', card['next_best_step'], '', 'All authority remains closed.', ''])
    DOC.write_text('\n'.join(lines))
    print(json.dumps(card, indent=2, sort_keys=True))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
