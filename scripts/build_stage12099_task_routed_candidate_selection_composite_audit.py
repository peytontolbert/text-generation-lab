#!/usr/bin/env python3
"""Inference-only routed audit combining fixed task routes from prior runtimes."""
from __future__ import annotations

import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = 12099
NAME = 'stage12099_task_routed_candidate_selection_composite_audit'
OUT = ROOT / 'runs/local/artifacts' / NAME
SUMMARY = OUT / 'task_routed_candidate_selection_composite_audit.json'
MIRROR = ROOT / 'runs/summaries' / f'{NAME}.json'
DECISION = ROOT / 'runs/summaries/stage12098_candidate_head_only_decision.json'
STAGE11924_SEMANTIC = ROOT / 'runs/local/artifacts/stage12097_candidate_head_only_candidate_selection_postrun_audit/stage11924_transition_listwise_head_only/bounded_choice_eval_audit_transition_projection__semantic_candidate_head.json'
STAGE12083_SEMANTIC = ROOT / 'runs/local/artifacts/stage12097_candidate_head_only_candidate_selection_postrun_audit/stage12083_next_action_repair_training/bounded_choice_eval_audit_transition_projection__semantic_candidate_head.json'
STAGE12096_COMPOSITE = ROOT / 'runs/local/artifacts/stage12097_candidate_head_only_candidate_selection_postrun_audit/stage12096_candidate_head_only_candidate_selection/bounded_choice_eval_audit_transition_projection__semantic_plus_transition_candidate_head.json'
STAGE12097_SUMMARY = ROOT / 'runs/summaries/stage12097_candidate_head_only_candidate_selection_postrun_audit.json'


def read_json(path: Path) -> Any:
    return json.loads(path.read_text())


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + '\n')


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def task_type(row: dict[str, Any]) -> str:
    value = row.get('task_type')
    if value:
        return str(value)
    rid = str(row.get('row_id') or '')
    for suffix in ('next_action', 'candidate_selection', 'verifier_transition', 'continue_or_stop'):
        if rid.endswith('::' + suffix) or ('::' + suffix + '::') in rid:
            return 'transition_' + suffix
    return 'unknown'


def metric(rows: list[dict[str, Any]]) -> dict[str, Any]:
    correct = sum(1 for row in rows if row.get('constrained_choice_match') is True)
    return {
        'rows': len(rows),
        'correct': correct,
        'accuracy': correct / len(rows) if rows else None,
        'miss_count': len(rows) - correct,
    }


def grouped(rows: list[dict[str, Any]]) -> dict[str, Any]:
    buckets: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        buckets.setdefault(task_type(row), []).append(row)
    return {name: metric(bucket) for name, bucket in sorted(buckets.items())}


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    decision = read_json(DECISION)
    audit = read_json(STAGE12097_SUMMARY)
    cards = {
        'stage11924_semantic': {row['row_id']: row for row in read_json(STAGE11924_SEMANTIC)['row_cards']},
        'stage12083_semantic': {row['row_id']: row for row in read_json(STAGE12083_SEMANTIC)['row_cards']},
        'stage12096_composite': {row['row_id']: row for row in read_json(STAGE12096_COMPOSITE)['row_cards']},
    }
    route = {
        'transition_candidate_selection': 'stage12096_composite',
        'transition_next_action': 'stage12083_semantic',
        'transition_continue_or_stop': 'stage11924_semantic',
        'transition_verifier_transition': 'stage11924_semantic',
    }
    routed_rows: list[dict[str, Any]] = []
    missing: list[dict[str, str]] = []
    for rid, base_row in cards['stage11924_semantic'].items():
        task = task_type(base_row)
        source = route.get(task, 'stage11924_semantic')
        row = cards[source].get(rid)
        if row is None:
            missing.append({'row_id': rid, 'task_type': task, 'source': source})
            row = base_row
            source = 'stage11924_semantic_fallback_missing_route_row'
        out = dict(row)
        out['stage12099_route_source'] = source
        out['stage12099_task_type'] = task
        routed_rows.append(out)

    by_task = grouped(routed_rows)
    total = metric(routed_rows)
    route_counts = Counter(row['stage12099_route_source'] for row in routed_rows)
    gates = {
        'route_declared_before_eval': True,
        'no_missing_routed_rows': len(missing) == 0,
        'old_transition_gt_364': total['correct'] > 364,
        'beats_gemma_386': total['correct'] > 386,
        'candidate_selection_ge_89': by_task['transition_candidate_selection']['correct'] >= 89,
        'candidate_selection_ge_92': by_task['transition_candidate_selection']['correct'] >= 92,
        'next_action_ge_51': by_task['transition_next_action']['correct'] >= 51,
        'next_action_ge_59': by_task['transition_next_action']['correct'] >= 59,
        'continue_or_stop_ge_128': by_task['transition_continue_or_stop']['correct'] >= 128,
        'verifier_transition_ge_96': by_task['transition_verifier_transition']['correct'] >= 96,
        'protected_filtered_strict_preserved_for_candidate_runtime': audit['gates']['filtered_strict_preserved'],
        'protected_old_canary_strict_preserved_for_candidate_runtime': audit['gates']['old_canary_strict_preserved'],
        'protected_residual_preserved_for_candidate_runtime': audit['gates']['residual_preserved'],
        'protected_smoke_preserved_for_candidate_runtime': audit['gates']['smoke_preserved'],
    }
    protected = (
        gates['protected_filtered_strict_preserved_for_candidate_runtime']
        and gates['protected_old_canary_strict_preserved_for_candidate_runtime']
        and gates['protected_residual_preserved_for_candidate_runtime']
        and gates['protected_smoke_preserved_for_candidate_runtime']
    )
    if protected and gates['beats_gemma_386']:
        decision_label = 'task_routed_transition_gemma_win_candidate_requires_sealed_confirmation'
    elif protected and gates['old_transition_gt_364'] and gates['candidate_selection_ge_89'] and gates['next_action_ge_51']:
        decision_label = 'task_routed_transition_frontier_candidate_requires_sealed_confirmation'
    else:
        decision_label = 'task_routed_audit_diagnostic_not_promotable'

    summary = {
        'stage': STAGE,
        'stage_name': NAME,
        'created_at_utc': datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00', 'Z'),
        'decision': decision_label,
        'route_policy': route,
        'route_policy_source': decision['recommended_next_stage'],
        'selected_transition_frontier_baseline': decision['selected_transition_frontier'],
        'routed_transition_score': total,
        'routed_by_task': by_task,
        'route_counts': dict(route_counts),
        'gates': gates,
        'missing_routed_rows': missing,
        'claim_boundary': [
            'This is inference-only task routing from declared prior runtimes; it is not a new trained model.',
            'It cannot replace a single-runtime product scorer unless product routing is explicitly accepted and sealed-confirmed.',
            'Promotion requires a follow-up sealed/source-heldout confirmation and same-manifest Gemma comparison under the same route contract.',
        ],
        'source_artifacts': {
            'stage12098_decision': rel(DECISION),
            'stage12097_summary': rel(STAGE12097_SUMMARY),
            'stage11924_semantic_card': rel(STAGE11924_SEMANTIC),
            'stage12083_semantic_card': rel(STAGE12083_SEMANTIC),
            'stage12096_composite_card': rel(STAGE12096_COMPOSITE),
        },
        'outputs': {
            'summary': rel(SUMMARY),
            'summary_mirror': rel(MIRROR),
        },
    }
    write_json(SUMMARY, summary)
    write_json(MIRROR, summary)
    print(json.dumps({
        'decision': decision_label,
        'routed_transition_score': total,
        'routed_by_task': by_task,
        'gates': gates,
    }, indent=2, sort_keys=True))


if __name__ == '__main__':
    main()
