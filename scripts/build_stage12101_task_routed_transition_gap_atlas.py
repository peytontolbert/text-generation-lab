#!/usr/bin/env python3
"""Build gap atlas for the Stage12099 task-routed transition candidate."""
from __future__ import annotations

import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = 12101
NAME = 'stage12101_task_routed_transition_gap_atlas'
OUT = ROOT / 'runs/local/artifacts' / NAME
SUMMARY = OUT / 'task_routed_transition_gap_atlas.json'
MIRROR = ROOT / 'runs/summaries' / f'{NAME}.json'
ROWS_OUT = OUT / 'task_routed_transition_gap_rows.jsonl'
ROUTE_AUDIT = ROOT / 'runs/summaries/stage12099_task_routed_candidate_selection_composite_audit.json'
GEMMA_ROWS = ROOT / 'runs/local/artifacts/stage11943_transition_gemma_gap_atlas/transition_gemma_gap_rows.jsonl'
GEMMA_SUMMARY = ROOT / 'runs/summaries/stage11943_transition_gemma_gap_atlas.json'
STAGE11924_SEMANTIC = ROOT / 'runs/local/artifacts/stage12097_candidate_head_only_candidate_selection_postrun_audit/stage11924_transition_listwise_head_only/bounded_choice_eval_audit_transition_projection__semantic_candidate_head.json'
STAGE12083_SEMANTIC = ROOT / 'runs/local/artifacts/stage12097_candidate_head_only_candidate_selection_postrun_audit/stage12083_next_action_repair_training/bounded_choice_eval_audit_transition_projection__semantic_candidate_head.json'
STAGE12096_COMPOSITE = ROOT / 'runs/local/artifacts/stage12097_candidate_head_only_candidate_selection_postrun_audit/stage12096_candidate_head_only_candidate_selection/bounded_choice_eval_audit_transition_projection__semantic_plus_transition_candidate_head.json'


def read_json(path: Path) -> Any:
    return json.loads(path.read_text())


def iter_jsonl(path: Path):
    for line in path.read_text().splitlines():
        if line.strip():
            yield json.loads(line)


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


def option_for(row: dict[str, Any], label: str | None) -> dict[str, Any] | None:
    if not label:
        return None
    for opt in row.get('option_labels') or []:
        pass
    # Audit row cards do not preserve full option objects; Gemma rows do. Keep a
    # compact label-level atlas here and rely on Stage11943 for option details.
    return None


def metric(rows: list[dict[str, Any]], pred_key: str) -> int:
    return sum(1 for row in rows if row.get(pred_key) == row.get('target_label'))


def top(counter: Counter, n: int = 30) -> list[dict[str, Any]]:
    return [{'key': k, 'count': v} for k, v in counter.most_common(n)]


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    route_audit = read_json(ROUTE_AUDIT)
    gemma_summary = read_json(GEMMA_SUMMARY)
    cards = {
        'stage11924_semantic': {row['row_id']: row for row in read_json(STAGE11924_SEMANTIC)['row_cards']},
        'stage12083_semantic': {row['row_id']: row for row in read_json(STAGE12083_SEMANTIC)['row_cards']},
        'stage12096_composite': {row['row_id']: row for row in read_json(STAGE12096_COMPOSITE)['row_cards']},
    }
    gemma = {row['row_id']: row for row in iter_jsonl(GEMMA_ROWS)}
    route = route_audit['route_policy']
    rows: list[dict[str, Any]] = []
    for rid, base_row in cards['stage11924_semantic'].items():
        task = task_type(base_row)
        source = route.get(task, 'stage11924_semantic')
        routed_card = cards[source][rid]
        gemma_row = gemma.get(rid, {})
        target = routed_card.get('bounded_choice_target_label') or routed_card.get('target_text')
        routed_pred = routed_card.get('constrained_choice_top1_label')
        gemma_pred = gemma_row.get('gemma12b_predicted_label')
        has_gemma_label = bool(gemma_row)
        record = {
            'row_id': rid,
            'task_type': task,
            'language_family': routed_card.get('language_family') or gemma_row.get('language_family') or 'unknown',
            'root_id': gemma_row.get('root_id') or 'unknown',
            'route_source': source,
            'target_label': target,
            'routed_predicted_label': routed_pred,
            'gemma12b_predicted_label': gemma_pred,
            'routed_correct': routed_pred == target,
            'gemma_correct': (gemma_pred == target) if has_gemma_label else None,
            'has_gemma_row_label': has_gemma_label,
            'target_option_role': (gemma_row.get('target_option') or {}).get('role'),
            'routed_pred_option_role': (gemma_row.get('hundred_m_option') or {}).get('role') if source == 'stage11924_semantic' else None,
            'gemma_pred_option_role': (gemma_row.get('gemma_option') or {}).get('role'),
        }
        if not has_gemma_label:
            record['comparison_bucket'] = 'gemma_row_not_materialized'
        elif record['routed_correct'] and record['gemma_correct']:
            record['comparison_bucket'] = 'both_correct'
        elif record['routed_correct'] and not record['gemma_correct']:
            record['comparison_bucket'] = 'routed_only_correct'
        elif not record['routed_correct'] and record['gemma_correct']:
            record['comparison_bucket'] = 'gemma_only_correct'
        else:
            record['comparison_bucket'] = 'both_wrong'
        rows.append(record)

    with ROWS_OUT.open('w') as f:
        for row in rows:
            f.write(json.dumps(row, sort_keys=True) + '\n')

    bucket_counts = Counter(row['comparison_bucket'] for row in rows)
    gemma_only = [row for row in rows if row['comparison_bucket'] == 'gemma_only_correct']
    routed_misses = [row for row in rows if not row['routed_correct']]
    both_wrong = [row for row in rows if row['comparison_bucket'] == 'both_wrong']
    routed_correct = sum(1 for row in rows if row['routed_correct'])
    gemma_correct = int(gemma_summary['summary_counts']['both_correct'] + gemma_summary['summary_counts']['gemma_only_correct'])
    summary = {
        'stage': STAGE,
        'stage_name': NAME,
        'created_at_utc': datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00', 'Z'),
        'decision': 'gap_atlas_ready_no_training_launched',
        'route_policy': route,
        'summary_counts': {
            'rows': len(rows),
            'routed_correct': routed_correct,
            'gemma_correct_from_stage11943_summary': gemma_correct,
            'delta_vs_gemma': routed_correct - gemma_correct,
            'gemma_row_labels_materialized': len(gemma),
            'gemma_row_labels_are_gemma_only_subset': True,
            **dict(bucket_counts),
        },
        'routed_by_task': route_audit['routed_by_task'],
        'gemma_only_by_task': top(Counter(row['task_type'] for row in gemma_only)),
        'gemma_only_by_language': top(Counter(row['language_family'] for row in gemma_only)),
        'gemma_only_by_language_task': top(Counter((row['language_family'], row['task_type']) for row in gemma_only)),
        'routed_misses_by_task': top(Counter(row['task_type'] for row in routed_misses)),
        'routed_misses_by_language_task': top(Counter((row['language_family'], row['task_type']) for row in routed_misses)),
        'both_wrong_by_task': top(Counter(row['task_type'] for row in both_wrong)),
        'both_wrong_by_language_task': top(Counter((row['language_family'], row['task_type']) for row in both_wrong)),
        'recommended_next_stage': {
            'name': 'stage12102_task_routed_gap_targeted_data_plan',
            'do_not_train_on_same_manifest_gemma_only_rows': True,
            'requirements': [
                'Use this atlas only to choose disjoint analogue data, not as train rows.',
                'Prioritize Gemma-only buckets where route is still behind, plus both-wrong buckets with high maintainer value.',
                'Keep product-route and standalone-weight scoreboards separate.',
                'Any next training run must preserve Stage12099 route candidate score or explicitly target standalone improvement.',
            ],
        },
        'worklist': {
            'gemma_only_examples': gemma_only[:40],
            'both_wrong_examples': both_wrong[:40],
            'routed_miss_examples': routed_misses[:40],
        },
        'source_artifacts': {
            'stage12099_route_audit': rel(ROUTE_AUDIT),
            'stage11943_gemma_rows': rel(GEMMA_ROWS),
            'stage11943_gemma_summary': rel(GEMMA_SUMMARY),
            'stage11924_semantic_card': rel(STAGE11924_SEMANTIC),
            'stage12083_semantic_card': rel(STAGE12083_SEMANTIC),
            'stage12096_composite_card': rel(STAGE12096_COMPOSITE),
        },
        'outputs': {
            'rows': rel(ROWS_OUT),
            'summary': rel(SUMMARY),
            'summary_mirror': rel(MIRROR),
        },
    }
    write_json(SUMMARY, summary)
    write_json(MIRROR, summary)
    print(json.dumps({
        'decision': summary['decision'],
        'summary_counts': summary['summary_counts'],
        'gemma_only_by_task': summary['gemma_only_by_task'],
        'routed_misses_by_task': summary['routed_misses_by_task'],
    }, indent=2, sort_keys=True))


if __name__ == '__main__':
    main()
