#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import time
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / 'runs/local/artifacts'
STAGE = 11332
NAME = 'stage11332_web_alias_free_evidence_materialization'
OUT = ART / NAME
SUMMARY = OUT / 'web_alias_free_evidence_materialization.json'
READY = ART / 'stage11331_rust_web_gap_recovery_manifest/web_ready_candidate_queue.jsonl'
OUT_ROWS = OUT / 'web_alias_free_evidence_rows.jsonl'
OUT_BLOCKED = OUT / 'web_alias_free_evidence_blocked.jsonl'
LABELS = list('ABCDEFGH')
ROLE_CLASS = {
    'verifier_and_test_constraint': 'DECISIVE_VERIFIER_TEST_CONSTRAINT',
    'candidate_change_surface': 'SUPPORTING_CANDIDATE_CHANGE_SURFACE',
    'symptom_or_call_path_analogue': 'SUPPORTING_SYMPTOM_OR_CALL_PATH',
}
TASKS = {
    'verifier_and_test_constraint': 'Task: Choose the evidence item that contains concrete selected-test, verifier, assertion, fixture, or expected-output evidence.',
    'candidate_change_surface': 'Task: Choose the evidence item that contains the changed implementation, source, configuration, fixture, or artifact surface.',
    'symptom_or_call_path_analogue': 'Task: Choose the evidence item that contains symptom, runtime behavior, call-path, or failure-context evidence.',
}


def now() -> str:
    return time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(''.join(json.dumps(row, sort_keys=True) + '\n' for row in rows))


def write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, sort_keys=True) + '\n')


def compact_paths(paths: list[str], limit: int = 8) -> str:
    clean = [str(p) for p in paths if str(p).strip()]
    if not clean:
        return ''
    suffix = '' if len(clean) <= limit else f' (+{len(clean) - limit} more)'
    return ', '.join(clean[:limit]) + suffix


def make_item(row: dict[str, Any], role: str) -> str:
    if role == 'verifier_and_test_constraint':
        text = compact_paths(row.get('verifier_and_test_constraint_paths') or [])
        return f'Selected check/fixture paths: {text}; route={row.get("test_selection_route")}' if text else ''
    if role == 'candidate_change_surface':
        text = compact_paths(row.get('candidate_change_surface_paths') or [])
        return f'Changed source/artifact paths: {text}' if text else ''
    if role == 'symptom_or_call_path_analogue':
        text = compact_paths(row.get('symptom_or_call_path_analogue_paths') or row.get('key_symbols') or [])
        return f'Runtime/context symbols or paths: {text}' if text else ''
    return ''


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    rows = []
    blocked = []
    for source in read_jsonl(READY):
        if source.get('language_family') != 'web_js_ts_html':
            continue
        if source.get('already_materialized_in_stage11275'):
            # Keep this queue focused on new Web material that was not already used by the direct package.
            continue
        root_id = str(source.get('root_id'))
        items = []
        for role in ['candidate_change_surface', 'verifier_and_test_constraint', 'symptom_or_call_path_analogue']:
            text = make_item(source, role)
            if text:
                items.append({'role': role, 'text': text})
        roles = {item['role'] for item in items}
        required = {'candidate_change_surface', 'verifier_and_test_constraint'}
        if not required.issubset(roles):
            blocked.append({'root_id': root_id, 'repo_family': source.get('repo_family'), 'blockers': ['missing_changed_or_verifier_item'], 'roles': sorted(roles)})
            continue
        for desired in sorted(roles):
            if desired not in ROLE_CLASS:
                continue
            seed = hashlib.sha256(f'{STAGE}:{root_id}:{desired}'.encode()).hexdigest()
            records = []
            evidence_lines = []
            for idx, item in enumerate(items):
                eid = f'E{idx+1:02d}'
                value = f'{eid}. {item["text"]}'
                evidence_lines.append(value)
                records.append((idx, eid, item, value))
            records = sorted(records, key=lambda rec: hashlib.sha256((seed + rec[1]).encode()).hexdigest())
            options = []
            target_label = ''
            for option_index, (orig_idx, eid, item, value) in enumerate(records):
                label = LABELS[option_index]
                options.append({
                    'label': label,
                    'value': value,
                    'semantic_candidate': {
                        'schema_version': 'stage11332_web_alias_free_evidence_materialization_v1',
                        'candidate_label': label,
                        'candidate_value_family': 'alias_free_web_evidence_item_text',
                        'option_index': option_index,
                        'task_type': 'evidence_citation',
                        'evidence_role': item['role'],
                        'test_id': eid,
                        'verifier_transition': 'NONE',
                        'value_token_count_proxy': len(value.split()),
                    },
                })
                if item['role'] == desired:
                    target_label = label
            input_text = '\n'.join([
                'Language: web_js_ts_html',
                'Perspective: evidence_citation',
                TASKS[desired],
                f'Repository family: {source.get("repo_family")}',
                f'Execution route: {source.get("execution_route")}',
                'Visible evidence items:',
                *evidence_lines,
                'Options:',
                *[f'{option["label"]}. {option["value"]}' for option in options],
                'Answer:',
            ])
            rows.append({
                'row_id': f'stage11332::{root_id}::{ROLE_CLASS[desired]}',
                'root_id': root_id,
                'source_root_id': source.get('source_root_id'),
                'root_lineage_key': source.get('root_lineage_key'),
                'source_row_id': source.get('source_row_id'),
                'repo_family': source.get('repo_family'),
                'repo_id': source.get('repo_id'),
                'language_family': 'web_js_ts_html',
                'task_type': 'evidence_citation',
                'split': 'train',
                'package_split': 'train',
                'strict_eval_eligible': False,
                'train_support_only': True,
                'input_text': input_text,
                'prompt_text': input_text,
                'decoder_text': target_label,
                'target_text': target_label,
                'bounded_choice_target_label': target_label,
                'semantic_target_value': desired,
                'opaque_options': options,
                'standalone_projection_source': {
                    'projection_mode': 'web_alias_free_evidence_item_selection',
                    'gold_value': desired,
                    'source_target_class': ROLE_CLASS[desired],
                    'opaque_options': options,
                    'source_candidate': source,
                    'evidence_items_hidden_role_metadata': items,
                },
                'expected_enabled_loss': 'decoder_ce',
                'loss_mask': {'decoder_ce': True},
                'anti_cheat': {
                    'role_alias_options_removed': True,
                    'deterministic_option_shuffle': True,
                    'gold_label_not_in_prompt_before_options': True,
                    'source_candidate_from_stage11237': True,
                    'support_only_not_promotable': True,
                },
            })
    write_jsonl(OUT_ROWS, rows)
    write_jsonl(OUT_BLOCKED, blocked)
    summary = {
        'stage': STAGE,
        'stage_name': NAME,
        'created_at_utc': now(),
        'passed': bool(rows),
        'decision': 'web_alias_free_evidence_rows_materialized_support_only' if rows else 'web_alias_free_evidence_materialization_blocked',
        'counts': {
            'rows': len(rows),
            'roots': len({r['root_id'] for r in rows}),
            'by_gold': dict(sorted(Counter(r['semantic_target_value'] for r in rows).items())),
            'by_repo': dict(sorted(Counter(r['repo_family'] for r in rows).items())),
            'blocked': len(blocked),
        },
        'admissibility': {
            'train_support_only': True,
            'promotable_eval': False,
            'reason': 'Rows are alias-free Web support from path/fact evidence, but not maintainer-grade strict eval because no source snippets or executable verifier outputs are materialized.',
        },
        'source_artifacts': {'web_ready_candidate_queue': rel(READY)},
        'outputs': {'rows': rel(OUT_ROWS), 'blocked': rel(OUT_BLOCKED), 'summary': rel(SUMMARY)},
        'recommended_next_action': 'use as Web support only after combining with canary-preserving package; separately mine pure-Web source snippets and selected-test outputs for promotable eval.',
    }
    write_json(SUMMARY, summary)
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == '__main__':
    main()
