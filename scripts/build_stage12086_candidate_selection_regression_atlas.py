#!/usr/bin/env python3
"""Analyze candidate-selection regressions that cancelled Stage12083 next-action gains."""
from __future__ import annotations

import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = 12086
NAME = 'stage12086_candidate_selection_regression_atlas'
OUT = ROOT / 'runs/local/artifacts' / NAME
SUMMARY = OUT / 'candidate_selection_regression_atlas.json'
MIRROR = ROOT / 'runs/summaries' / f'{NAME}.json'
AUDIT = ROOT / 'runs/summaries/stage12084_next_action_repair_training_postrun_audit.json'
SRC_ROWS = ROOT / 'runs/local/artifacts/stage11897_transition_record_projection_rows/transition_projection_rows.jsonl'
BASE_CARD = ROOT / 'runs/local/artifacts/stage12084_next_action_repair_training_postrun_audit/stage11924_transition_listwise_head_only/bounded_choice_eval_audit_transition_projection__semantic_candidate_head.json'
POST_CARD = ROOT / 'runs/local/artifacts/stage12084_next_action_repair_training_postrun_audit/stage12083_next_action_repair_training/bounded_choice_eval_audit_transition_projection__semantic_candidate_head.json'


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


def option(row: dict[str, Any], label: str | None) -> dict[str, Any]:
    if not label:
        return {}
    opts = row.get('standalone_projection_source', {}).get('opaque_options') or row.get('opaque_options') or []
    for opt in opts:
        if opt.get('label') == label:
            return opt
    return {}


def option_value(row: dict[str, Any], label: str | None) -> str | None:
    return option(row, label).get('value')


def option_role(row: dict[str, Any], label: str | None) -> str | None:
    return option(row, label).get('role')


def task_type(row_id: str) -> str:
    for suffix in ('next_action', 'candidate_selection', 'verifier_transition', 'continue_or_stop'):
        if row_id.endswith('::' + suffix) or ('::' + suffix + '::') in row_id:
            return 'transition_' + suffix
    return 'unknown'


def subfamily(row_id: str) -> str:
    parts = row_id.split('::')
    return parts[-2] if len(parts) >= 2 else 'unknown'


def language(row_id: str, src: dict[str, Any] | None) -> str:
    if src and src.get('language_family'):
        return src['language_family']
    for lang in ('python','rust','c_cpp','web_js_ts_html'):
        if f'::{lang}::' in row_id:
            return lang
    return 'unknown'


def root_family(row_id: str) -> str:
    p = row_id.split('::')
    return '::'.join(p[2:4]) if len(p) >= 4 else row_id


def enrich(rid: str, direction: str, src: dict[str, Any] | None, b: dict[str, Any], p: dict[str, Any]) -> dict[str, Any]:
    target_label = b.get('bounded_choice_target_label') or p.get('bounded_choice_target_label')
    base_label = b.get('constrained_choice_top1_label')
    post_label = p.get('constrained_choice_top1_label')
    src = src or {}
    return {
        'direction': direction,
        'row_id': rid,
        'task_type': task_type(rid),
        'subfamily': subfamily(rid),
        'language_family': language(rid, src),
        'root_family': root_family(rid),
        'target_label': target_label,
        'target_role': option_role(src, target_label),
        'target_value': option_value(src, target_label),
        'base_pred_label': base_label,
        'base_pred_role': option_role(src, base_label),
        'base_pred_value': option_value(src, base_label),
        'post_pred_label': post_label,
        'post_pred_role': option_role(src, post_label),
        'post_pred_value': option_value(src, post_label),
        'target_rank_full_vocab_base': b.get('target_rank_full_vocab'),
        'target_rank_full_vocab_post': p.get('target_rank_full_vocab'),
        'full_vocab_top1_base': b.get('full_vocab_top1_text'),
        'full_vocab_top1_post': p.get('full_vocab_top1_text'),
    }


def top(counter: Counter, n: int = 30) -> list[dict[str, Any]]:
    return [{'key': k, 'count': v} for k, v in counter.most_common(n)]


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    audit = read_json(AUDIT)
    src = {r['row_id']: r for r in iter_jsonl(SRC_ROWS)}
    base_cards = {r['row_id']: r for r in read_json(BASE_CARD)['row_cards']}
    post_cards = {r['row_id']: r for r in read_json(POST_CARD)['row_cards']}
    changes = audit['transition_changes_vs_stage11924']

    records = []
    for direction, ids in [('gain', changes['gained']), ('loss', changes['lost'])]:
        for rid in ids:
            records.append(enrich(rid, direction, src.get(rid), base_cards.get(rid, {}), post_cards.get(rid, {})))

    cand = [r for r in records if r['task_type'] == 'transition_candidate_selection']
    cand_gains = [r for r in cand if r['direction'] == 'gain']
    cand_losses = [r for r in cand if r['direction'] == 'loss']
    next_action = [r for r in records if r['task_type'] == 'transition_next_action']
    next_gains = [r for r in next_action if r['direction'] == 'gain']
    next_losses = [r for r in next_action if r['direction'] == 'loss']

    def bucket(rows: list[dict[str, Any]]) -> dict[str, Any]:
        return {
            'rows': len(rows),
            'by_language': top(Counter(r['language_family'] for r in rows)),
            'by_subfamily': top(Counter(r['subfamily'] for r in rows)),
            'by_target_role': top(Counter(r['target_role'] for r in rows)),
            'by_post_pred_role': top(Counter(r['post_pred_role'] for r in rows)),
            'by_target_to_post_role': top(Counter((r['target_role'], r['post_pred_role']) for r in rows)),
            'by_base_to_post_role': top(Counter((r['base_pred_role'], r['post_pred_role']) for r in rows)),
            'by_target_to_post_value': top(Counter((r['target_value'], r['post_pred_value']) for r in rows)),
        }

    diagnosis = []
    cand_loss_roles = Counter((r['target_role'], r['post_pred_role']) for r in cand_losses)
    if cand_loss_roles:
        diagnosis.append(f"candidate-selection dominant loss shift: {cand_loss_roles.most_common(1)[0][0]} x{cand_loss_roles.most_common(1)[0][1]}")
    if Counter(r['subfamily'] for r in cand_losses).get('answerable_evidence_citation_build_run_constraint', 0) >= 3:
        diagnosis.append('C/C++ evidence/build-run candidate rows are a major regression family.')
    if Counter(r['post_pred_role'] for r in cand_losses).get('candidate_change_surface', 0) >= 3:
        diagnosis.append('Stage12083 over-shifted some candidate-selection rows back toward candidate_change_surface.')
    if Counter(r['post_pred_role'] for r in cand_losses).get('selected_inline_test_anchor', 0) >= 2:
        diagnosis.append('Stage12083 also over-shifted some Rust source-surface rows toward selected_inline_test_anchor.')

    repair_contract = {
        'recommended_stage': 'stage12087_candidate_selection_repair_design',
        'do_not_train_yet': True,
        'needed_packet_shape': {
            'candidate_selection_rows': 80,
            'next_action_rows': 80,
            'purpose': 'Keep Stage12083 next-action gains while restoring candidate-selection to >=89/160.',
            'subpackets': {
                'candidate_selection_regression_replay': {
                    'rows': 46,
                    'source': 'all Stage12084 candidate-selection losses as replay/analogues',
                    'hard_negative': 'Stage12083 wrong post_pred_role/value',
                },
                'candidate_selection_gain_preservation': {
                    'rows': 20,
                    'source': 'Stage12084 candidate-selection gains to avoid reverting improvements',
                    'hard_negative': 'Stage11924 wrong base_pred_role/value',
                },
                'next_action_gain_preservation': {
                    'rows': 40,
                    'source': 'Stage12084 next-action gains, especially ABSTAIN and PLAN_PATCH improvements',
                    'hard_negative': 'Stage11924 wrong base_pred_value',
                },
                'selected_verifier_next_action_preservation': {
                    'rows': 40,
                    'source': 'Stage12084 next-action losses with RETRIEVE_EVIDENCE target',
                    'hard_negative': 'Stage12083 PLAN_PATCH prediction',
                },
            },
        },
        'local_gate_before_training': {
            'candidate_selection_losses_covered': f'>={max(1, int(len(cand_losses)*0.8))}/{len(cand_losses)}',
            'candidate_selection_gains_covered': f'>={max(1, int(len(cand_gains)*0.8))}/{len(cand_gains)}',
            'next_action_gains_covered': f'>={max(1, int(len(next_gains)*0.8))}/{len(next_gains)}',
            'no_target_leak': True,
            'no_option_mirror_missing': True,
        },
        'postrun_gate': {
            'old_transition_640': '>364/640',
            'transition_next_action': '>=59/160',
            'transition_candidate_selection': '>=89/160',
            'protected_gates': 'preserved',
        },
    }

    records_path = OUT / 'candidate_selection_regression_records.jsonl'
    with records_path.open('w') as f:
        for r in records:
            f.write(json.dumps(r, sort_keys=True) + '\n')

    summary = {
        'stage': STAGE,
        'stage_name': NAME,
        'created_at_utc': datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00','Z'),
        'score_delta': {
            'old_transition_640': {'stage11924': 364, 'stage12083': 364, 'delta': 0},
            'transition_next_action': {'stage11924': 51, 'stage12083': 59, 'delta': 8},
            'transition_candidate_selection': {'stage11924': 89, 'stage12083': 81, 'delta': -8},
            'transition_continue_or_stop': {'stage11924': 128, 'stage12083': 128, 'delta': 0},
            'transition_verifier_transition': {'stage11924': 96, 'stage12083': 96, 'delta': 0},
        },
        'change_counts': {'all_gains': len(changes['gained']), 'all_losses': len(changes['lost']), 'candidate_gains': len(cand_gains), 'candidate_losses': len(cand_losses), 'next_action_gains': len(next_gains), 'next_action_losses': len(next_losses)},
        'candidate_selection': {'gains': bucket(cand_gains), 'losses': bucket(cand_losses), 'loss_records': cand_losses, 'gain_records': cand_gains},
        'next_action_reference': {'gains': bucket(next_gains), 'losses': bucket(next_losses)},
        'diagnosis': diagnosis,
        'repair_contract': repair_contract,
        'source_artifacts': {'stage12084_audit': rel(AUDIT), 'base_card': rel(BASE_CARD), 'post_card': rel(POST_CARD), 'source_rows': rel(SRC_ROWS)},
        'outputs': {'records': rel(records_path), 'summary': rel(SUMMARY), 'summary_mirror': rel(MIRROR)},
    }
    write_json(SUMMARY, summary)
    write_json(MIRROR, summary)
    print(json.dumps(summary, indent=2, sort_keys=True))

if __name__ == '__main__':
    main()
