#!/usr/bin/env python3
"""Audit Stage12056/v35 transition support inventory before any training."""
from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

ROOT = Path('runs/local/artifacts/stage12057_transition_support_v35_audit')
ROWS_IN = Path('runs/local/artifacts/stage12056_transition_support_rollup_v35/transition_support_rows_v35.jsonl')
ROLLUP_SUMMARY = Path('runs/summaries/stage12056_transition_support_rollup_v35.json')
AUDIT = ROOT / 'transition_support_v35_audit.json'
ROW_ISSUES = ROOT / 'transition_support_v35_row_issues.jsonl'
SUMMARY_MIRROR = Path('runs/summaries/stage12057_transition_support_v35_audit.json')

LANGUAGE_FLOORS = {'python': 50, 'rust': 50, 'c_cpp': 50, 'web_js_ts_html': 50}
STATUS_FLOORS = {
    'FAIL_TO_PASS': 50,
    'PASS_TO_PASS': 100,
    'PASS_CURRENT_BUILD': 40,
    'PASS_CURRENT_BUILD_AND_RUN': 40,
    'INSUFFICIENT_EVIDENCE': 40,
    'NOT_EXERCISED': 40,
}
TRANSITION_TEXT = {
    'PASS_TO_PASS': 'focused verifier executed from local source and passed',
    'PASS_CURRENT_BUILD_AND_RUN': 'build and runnable verifier both passed',
    'PASS_CURRENT_BUILD': 'build or collection passed but runnable verifier body did not execute',
    'FAIL_TO_PASS': 'controlled broken state failed and restored or repaired source passed',
    'NOT_EXERCISED': 'command did not exercise or collect the selected verifier',
    'INSUFFICIENT_EVIDENCE': 'environment is underhydrated so no trustworthy transition is available',
    'FAIL_TO_FAIL': 'verifier failed in the current local source state',
    'VERIFIER_REMOVED': 'verifier evidence was removed and the row should abstain',
}
STATUS_TEXT_ALIASES = {
    'PASS_TO_PASS': {
        'focused verifier executed from local source and passed',
        'selected verifier executed successfully and all tests passed',
        'focused verifier executed and passed',
    },
    'PASS_CURRENT_BUILD': {
        'build or collection passed but runnable verifier body did not execute',
        'collection or build probe completed successfully but did not execute the verifier body',
        'focused verifier collected from local source but was not executed',
        'only collection/build succeeded; verifier body did not execute',
    },
    'FAIL_TO_PASS': {
        'controlled broken state failed and restored or repaired source passed',
        'baseline passed, controlled mutation failed focused verifier, restored source passed',
    },
    'INSUFFICIENT_EVIDENCE': {
        'environment is underhydrated so no trustworthy transition is available',
        'evidence is insufficient because no verifier command was observed',
        'insufficient evidence because no local-source verifier was observed',
    },
    'NOT_EXERCISED': {
        'command did not exercise or collect the selected verifier',
        'candidate verifier did not exercise the target behavior or did not collect',
        'selected verifier failed or did not exercise the target state',
    },
}

HARD_BLOCKER_KINDS = {
    'duplicate_row_id',
    'singleton_options',
    'missing_options',
    'missing_target_label',
    'missing_target_semantic',
    'target_label_before_options',
    'target_value_before_options',
    'target_label_not_in_options',
    'target_value_not_in_options',
    'missing_deterministic_shuffle_flag',
    'strict_eval_marked_true_in_support_package',
    'source_heldout_marked_true_in_support_package',
    'non_train_split',
}


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()] if path.exists() else []


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(''.join(json.dumps(row, sort_keys=True) + '\n' for row in rows))


def root_key(row: dict[str, Any]) -> str:
    return str(row.get('root_lineage_key') or row.get('root_id') or row.get('source_root_id') or row.get('source_bundle_id') or row.get('row_id'))


def target_label(row: dict[str, Any]) -> str | None:
    return row.get('bounded_choice_target_label') or (row.get('target') or {}).get('bounded_choice_target_label') or row.get('decoder_text') or row.get('target_text')


def target_semantic(row: dict[str, Any]) -> str | None:
    target = row.get('target') or {}
    return row.get('observed_verifier_transition') or target.get('semantic_value') or target.get('canonical_value')


def option_labels(options: list[dict[str, Any]]) -> set[str]:
    return {str(opt.get('label')) for opt in options if opt.get('label') is not None}


def option_values(options: list[dict[str, Any]]) -> set[str]:
    vals: set[str] = set()
    for opt in options:
        for key in ('canonical_value', 'value', 'semantic_value', 'text'):
            if opt.get(key) is not None:
                vals.add(str(opt[key]))
    return vals


def before_options_text(row: dict[str, Any]) -> str:
    text = row.get('prompt_text') or row.get('input_text') or ''
    return text.split('Options:')[0]


def remaining(counts: Counter[str], floors: dict[str, int]) -> dict[str, int]:
    return {key: max(0, floor - counts.get(key, 0)) for key, floor in floors.items()}


def issue(row: dict[str, Any], kind: str, detail: str = '') -> dict[str, Any]:
    return {
        'row_id': row.get('row_id'),
        'root_key': root_key(row),
        'repo_family': row.get('repo_family'),
        'language_family': row.get('language_family'),
        'status': row.get('observed_verifier_transition'),
        'kind': kind,
        'severity': 'blocker' if kind in HARD_BLOCKER_KINDS else 'warning',
        'detail': detail,
    }


def main() -> None:
    ROOT.mkdir(parents=True, exist_ok=True)
    SUMMARY_MIRROR.parent.mkdir(parents=True, exist_ok=True)
    rows = read_jsonl(ROWS_IN)
    issues: list[dict[str, Any]] = []
    seen_row_ids: set[str] = set()
    rows_by_root: defaultdict[str, list[str]] = defaultdict(list)
    controlled_rows = 0

    for row in rows:
        row_id = str(row.get('row_id'))
        if row_id in seen_row_ids:
            issues.append(issue(row, 'duplicate_row_id'))
        seen_row_ids.add(row_id)
        rows_by_root[root_key(row)].append(row_id)

        options = row.get('opaque_options') or []
        if not options:
            issues.append(issue(row, 'missing_options'))
        elif len(options) < 2:
            issues.append(issue(row, 'singleton_options'))

        label = target_label(row)
        semantic = target_semantic(row)
        if not label:
            issues.append(issue(row, 'missing_target_label'))
        if not semantic:
            issues.append(issue(row, 'missing_target_semantic'))

        before = before_options_text(row)
        # Single-letter labels are display aliases; plain character occurrence in prose is not a leak.
        explicit_label_markers = [f'target label: {label}', f'answer: {label}', f'gold label: {label}', f'bounded_choice_target_label: {label}'] if label else []
        if label and any(marker.lower() in before.lower() for marker in explicit_label_markers):
            issues.append(issue(row, 'target_label_before_options', label))
        if semantic and semantic in before:
            issues.append(issue(row, 'target_value_before_options', semantic))
        labels = option_labels(options)
        values = option_values(options)
        if label and labels and str(label) not in labels:
            issues.append(issue(row, 'target_label_not_in_options', label))
        semantic_text = TRANSITION_TEXT.get(str(semantic)) if semantic else None
        aliases = STATUS_TEXT_ALIASES.get(str(semantic), set()) if semantic else set()
        if semantic and values and str(semantic) not in values and semantic_text not in values and values.isdisjoint(aliases):
            issues.append(issue(row, 'target_value_not_in_options', semantic))

        anti = row.get('anti_cheat') or {}
        if anti.get('deterministic_option_shuffle') is not True:
            issues.append(issue(row, 'missing_deterministic_shuffle_flag'))
        if anti.get('singleton_options') is True:
            issues.append(issue(row, 'anti_cheat_singleton_true'))
        if row.get('split') != 'train':
            issues.append(issue(row, 'non_train_split', str(row.get('split'))))
        if row.get('strict_eval_eligible') is True:
            issues.append(issue(row, 'strict_eval_marked_true_in_support_package'))
        if row.get('source_heldout_admissible') is True:
            issues.append(issue(row, 'source_heldout_marked_true_in_support_package'))

        if anti.get('controlled_fixture_train_support_only') is True or str(row.get('repo_family', '')).startswith('stage120'):
            controlled_rows += 1

    duplicate_root_groups = {key: ids for key, ids in rows_by_root.items() if len(ids) > 1}
    for key, ids in duplicate_root_groups.items():
        # Duplicate roots are warnings for support inventory, not hard blockers.
        issues.append({'row_id': None, 'root_key': key, 'repo_family': None, 'language_family': None, 'status': None, 'kind': 'duplicate_root_key_group', 'severity': 'warning', 'detail': f'{len(ids)} rows share root key'})

    lang = Counter(str(r.get('language_family')) for r in rows)
    status = Counter(str(r.get('observed_verifier_transition')) for r in rows)
    repo = Counter(str(r.get('repo_family')) for r in rows)
    top_repo_share = (repo.most_common(1)[0][1] / len(rows)) if rows else 0.0
    repo_over_10pct = {name: count for name, count in repo.items() if rows and count / len(rows) > 0.10}
    repo_over_15pct = {name: count for name, count in repo.items() if rows and count / len(rows) > 0.15}
    controlled_ratio = controlled_rows / len(rows) if rows else 0.0
    hard_blockers = [i for i in issues if i.get('severity') == 'blocker']
    warnings = [i for i in issues if i.get('severity') == 'warning']
    floor_remaining_language = remaining(lang, LANGUAGE_FLOORS)
    floor_remaining_status = remaining(status, STATUS_FLOORS)
    floors_met = all(v == 0 for v in floor_remaining_language.values()) and all(v == 0 for v in floor_remaining_status.values())
    concentration_warning = bool(repo_over_10pct) or controlled_ratio > 0.15
    train_ready = floors_met and not hard_blockers
    promote_ready = train_ready and not repo_over_15pct and controlled_ratio <= 0.15

    write_jsonl(ROW_ISSUES, issues)
    summary = {
        'stage': 'stage12057_transition_support_v35_audit',
        'rows_path': str(ROWS_IN),
        'rollup_summary_path': str(ROLLUP_SUMMARY),
        'row_issues_path': str(ROW_ISSUES),
        'total_rows': len(rows),
        'unique_roots': len(rows_by_root),
        'duplicate_root_groups': len(duplicate_root_groups),
        'language_counts': dict(sorted(lang.items())),
        'status_counts': dict(sorted(status.items())),
        'remaining_language_floor': floor_remaining_language,
        'remaining_status_floor': floor_remaining_status,
        'floors_met': floors_met,
        'hard_blocker_count': len(hard_blockers),
        'warning_count': len(warnings),
        'issue_counts': dict(sorted(Counter(i['kind'] for i in issues).items())),
        'repo_family_counts_top30': dict(repo.most_common(30)),
        'repo_family_over_10pct': repo_over_10pct,
        'repo_family_over_15pct': repo_over_15pct,
        'top_repo_share': round(top_repo_share, 4),
        'controlled_fixture_rows': controlled_rows,
        'controlled_fixture_ratio': round(controlled_ratio, 4),
        'concentration_warning': concentration_warning,
        'train_ready_against_floor_and_hard_audit': train_ready,
        'promotion_ready_without_concentration_warning': promote_ready,
        'decision': 'audit_pass_train_request_allowed_with_warnings' if train_ready else 'audit_failed_repair_before_training',
        'claim_boundary': 'This audit only authorizes considering a guarded training request. It does not prove model progress, source-heldout generalization, or Gemma superiority.',
        'next_stage_recommendation': {
            'stage': 'stage12058_guarded_transition_training_request' if train_ready else 'stage12058_transition_support_v35_repair',
            'action': 'Build a guarded training request with protected canary/residual/source-heldout audits and report concentration caveats.' if train_ready else 'Repair hard blockers before any training request.',
        },
    }
    AUDIT.write_text(json.dumps(summary, indent=2, sort_keys=True) + '\n')
    SUMMARY_MIRROR.write_text(json.dumps(summary, indent=2, sort_keys=True) + '\n')
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == '__main__':
    main()
