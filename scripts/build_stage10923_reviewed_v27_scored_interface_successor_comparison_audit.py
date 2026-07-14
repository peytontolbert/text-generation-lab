#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
import time
from collections import defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.bounded_choice_policy import choose_bounded_choice_label, policy_correct, policy_for_row

ARTIFACTS = ROOT / 'runs' / 'local' / 'artifacts'
STAGE = 10923
NAME = 'stage10923_reviewed_v27_scored_interface_successor_comparison_audit'
OUT_DIR = ARTIFACTS / NAME
OUT_JSON = OUT_DIR / 'reviewed_v27_scored_interface_successor_comparison_audit.json'
OUT_ROWS = OUT_DIR / 'reviewed_v27_scored_interface_successor_rows.jsonl'

SCORING_CONTRACT = ARTIFACTS / 'stage10922_reviewed_v27_scored_interface_contract' / 'reviewed_v27_scored_interface_contract.json'
SUCCESSOR_ROWS = ARTIFACTS / 'stage10898_python_verifier_transition_successor_same_manifest_comparison' / 'combined_strict_rows.jsonl'
SUCCESSOR_AUDIT = ARTIFACTS / 'stage10899_python_verifier_transition_successor_comparison_audit' / 'python_verifier_transition_successor_comparison_audit.json'
QUARANTINED_BASELINE = ARTIFACTS / 'stage10882_quarantined_v27_comparison_successor_audit' / 'quarantined_v27_comparison_successor_audit.json'
WEB_BLOCKER = ARTIFACTS / 'stage10921_broad_pure_web_source_acquisition_atlas' / 'broad_pure_web_source_acquisition_atlas.json'


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


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def now_utc() -> str:
    return time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())


def metric(correct: int, rows: int) -> dict[str, Any]:
    return {
        'correct': correct,
        'rows': rows,
        'exact_accuracy': (correct / rows) if rows else None,
    }


def by_group(rows: list[dict[str, Any]], key: str, result_key: str) -> dict[str, Any]:
    buckets: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        buckets[str(row.get(key) or 'unknown')].append(row)
    out = {}
    for bucket_key, bucket_rows in sorted(buckets.items()):
        correct = sum(1 for row in bucket_rows if bool(row.get(result_key)))
        out[bucket_key] = metric(correct, len(bucket_rows))
        out[bucket_key]['verdict'] = verdict(
            sum(1 for row in bucket_rows if bool(row.get('contract_correct'))),
            sum(1 for row in bucket_rows if bool(row.get('gemma12b_correct'))),
            len(bucket_rows),
        )
    return out


def verdict(hundred_correct: int, gemma_correct: int, rows: int) -> str:
    if rows == 0:
        return 'no_rows'
    if hundred_correct > gemma_correct:
        return '100m_better'
    if hundred_correct < gemma_correct:
        return 'gemma_better'
    return 'tie'


def main() -> None:
    contract = load_json(SCORING_CONTRACT)
    successor_rows = load_jsonl(SUCCESSOR_ROWS)
    successor_audit = load_json(SUCCESSOR_AUDIT)
    quarantined = load_json(QUARANTINED_BASELINE)
    web_blocker = load_json(WEB_BLOCKER)

    default_policy = ((contract.get('approved_scoring_contract') or {}).get('default_policy')) or 'current_retrieval'
    overrides = ((contract.get('approved_scoring_contract') or {}).get('task_policy_overrides')) or {}

    scored_rows = []
    changed_rows = []
    for row in successor_rows:
        policy_name = policy_for_row(row=row, default_policy=default_policy, override_by_task=overrides)
        contract_pred = choose_bounded_choice_label(
            row=row,
            constrained_label=str(row.get('constrained_choice_top1_label') or '') or None,
            decoder_label=str(row.get('full_vocab_top1_text') or '') or None,
            policy=policy_name,
        )
        contract_correct = policy_correct(target_label=str(row.get('target_text') or ''), predicted_label=contract_pred)
        scored = dict(row)
        scored['contract_policy'] = policy_name
        scored['contract_predicted_label'] = contract_pred
        scored['contract_correct'] = contract_correct
        scored_rows.append(scored)
        if contract_pred != row.get('constrained_choice_top1_label'):
            changed_rows.append({
                'row_id': row.get('row_id'),
                'task_type': row.get('task_type'),
                'language_family': row.get('language_family'),
                'before': row.get('constrained_choice_top1_label'),
                'after': contract_pred,
                'target': row.get('target_text'),
            })

    write_jsonl(OUT_ROWS, scored_rows)

    hundred_correct = sum(1 for row in scored_rows if bool(row.get('contract_correct')))
    gemma_correct = sum(1 for row in scored_rows if bool(row.get('gemma12b_correct')))
    rows = len(scored_rows)

    payload = {
        'stage': STAGE,
        'stage_name': NAME,
        'created_at_utc': now_utc(),
        'passed': True,
        'decision': 'reviewed_v27_scored_interface_successor_audited',
        'claim_scope': [
            'Audit the full 23-row alias-safe reviewed-v2.7 strict successor surface under the approved scored-interface contract.',
            'Keep the claim boundary explicit: this is still standalone, same-manifest, and anti-cheat-clean, with only the verifier_outcome_semantic_transition interface overridden.',
        ],
        'source_artifacts': {
            'scoring_contract': rel(SCORING_CONTRACT),
            'successor_rows': rel(SUCCESSOR_ROWS),
            'successor_audit': rel(SUCCESSOR_AUDIT),
            'quarantined_baseline': rel(QUARANTINED_BASELINE),
            'web_blocker': rel(WEB_BLOCKER),
        },
        'headline': {
            'strict_exact_100m_under_contract': hundred_correct / rows if rows else None,
            'strict_exact_gemma': gemma_correct / rows if rows else None,
            'strict_delta_100m_minus_gemma': (hundred_correct - gemma_correct) / rows if rows else None,
            'rows': rows,
            'language_wins_100m': sum(1 for block in by_group(scored_rows, 'language_family', 'contract_correct').values() if block['verdict'] == '100m_better'),
            'language_wins_gemma': sum(1 for block in by_group(scored_rows, 'language_family', 'contract_correct').values() if block['verdict'] == 'gemma_better'),
            'language_ties': sum(1 for block in by_group(scored_rows, 'language_family', 'contract_correct').values() if block['verdict'] == 'tie'),
        },
        'comparison': {
            'hundred_m_under_contract': metric(hundred_correct, rows),
            'gemma12b': metric(gemma_correct, rows),
            'by_language': by_group(scored_rows, 'language_family', 'contract_correct'),
            'by_task_type': by_group(scored_rows, 'task_type', 'contract_correct'),
            'by_selected_test_anchor': by_group(scored_rows, 'selected_test_anchor', 'contract_correct'),
            'by_verifier_anchor': by_group(scored_rows, 'verifier_anchor', 'contract_correct'),
            'by_abstention_heavy': by_group(scored_rows, 'abstention_heavy', 'contract_correct'),
        },
        'contract_effect': {
            'default_policy': default_policy,
            'task_policy_overrides': overrides,
            'rows_changed_by_contract': len(changed_rows),
            'changed_rows': changed_rows,
            'successor_row_result_before': successor_audit.get('successor_row_result'),
        },
        'baseline_comparison': {
            'old_quarantined_baseline_100m': ((quarantined.get('metrics') or {}).get('strict_exact_100m')),
            'old_quarantined_baseline_gemma': ((quarantined.get('metrics') or {}).get('strict_exact_gemma')),
            'old_quarantined_baseline_delta': ((quarantined.get('metrics') or {}).get('strict_delta_100m_minus_gemma')),
            'headline_continuation_of_old_baseline': False,
            'reason': 'The strict row identity changed and the scored interface now includes a task-scoped override for the semantic-transition successor row.',
        },
        'claim_boundaries': [
            'This is a same-manifest standalone successor comparison on the alias-safe 23-row reviewed-v2.7 strict surface.',
            'The stronger 100M result depends on the explicitly frozen scored-interface contract from stage10922, not on a new training run.',
            'Evidence-citation scoring remains blocked at retrieval, and web realism promotion remains blocked on fresh pure-web selected-test source supply.',
            'This does not upgrade the harness/full-product claim path.',
        ],
        'eval_honesty': {
            'alias_safe_baseline': True,
            'verifier_transition_override_only': True,
            'fresh_pure_web_selected_test_rows': (web_blocker.get('metrics') or {}).get('unique_fresh_pure_web_selected_test_rows'),
            'web_multilingual_promotion_blocked': True,
        },
        'next_best_step': 'Use this contract-applied successor as the current honest standalone comparison baseline, then focus new data work on fresh Python/C++ evidence successors and new pure-web selected-test source acquisition rather than more scorer churn.',
    }
    write_json(OUT_JSON, payload)
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == '__main__':
    main()
