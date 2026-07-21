#!/usr/bin/env python3
"""Build a loss/gain atlas for the rejected Stage12075 next-action probe."""
from __future__ import annotations

import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = 12078
NAME = 'stage12078_next_action_loss_gain_atlas'
OUT = ROOT / 'runs/local/artifacts' / NAME
SUMMARY = OUT / 'next_action_loss_gain_atlas.json'
MIRROR = ROOT / 'runs/summaries' / f'{NAME}.json'
AUDIT = ROOT / 'runs/summaries/stage12076_next_action_guarded_training_postrun_audit.json'
SRC_ROWS = ROOT / 'runs/local/artifacts/stage11897_transition_record_projection_rows/transition_projection_rows.jsonl'
BASE_CARD = ROOT / 'runs/local/artifacts/stage12076_next_action_guarded_training_postrun_audit/stage11924_transition_listwise_head_only/bounded_choice_eval_audit_transition_projection__semantic_candidate_head.json'
POST_CARD = ROOT / 'runs/local/artifacts/stage12076_next_action_guarded_training_postrun_audit/stage12075_next_action_guarded_training/bounded_choice_eval_audit_transition_projection__semantic_candidate_head.json'


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


def option_value(row: dict[str, Any], label: str | None) -> str | None:
    if not label:
        return None
    opts = row.get('standalone_projection_source', {}).get('opaque_options') or row.get('opaque_options') or []
    for opt in opts:
        if opt.get('label') == label:
            return opt.get('value')
    return None


def parse_task(row_id: str) -> str:
    for suffix in ('next_action', 'candidate_selection', 'verifier_transition', 'continue_or_stop'):
        if row_id.endswith('::' + suffix) or ('::' + suffix + '::') in row_id:
            return 'transition_' + suffix
    return 'unknown'


def parse_subfamily(row_id: str) -> str:
    parts = row_id.split('::')
    if len(parts) >= 2:
        return parts[-2]
    return 'unknown'


def parse_language(row_id: str, src: dict[str, Any] | None) -> str:
    if src and src.get('language_family'):
        return src['language_family']
    for lang in ('python', 'rust', 'c_cpp', 'web_js_ts_html'):
        if f'::{lang}::' in row_id:
            return lang
    return 'unknown'


def parse_root_family(row_id: str) -> str:
    parts = row_id.split('::')
    if len(parts) >= 4:
        return '::'.join(parts[2:4])
    return row_id


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    audit = read_json(AUDIT)
    base_cards = {r['row_id']: r for r in read_json(BASE_CARD)['row_cards']}
    post_cards = {r['row_id']: r for r in read_json(POST_CARD)['row_cards']}
    src_rows = {r['row_id']: r for r in iter_jsonl(SRC_ROWS)}
    changes = audit['transition_changes_vs_stage11924']

    records = []
    for direction, ids in [('gain', changes['gained']), ('loss', changes['lost'])]:
        for rid in ids:
            src = src_rows.get(rid)
            b = base_cards.get(rid, {})
            p = post_cards.get(rid, {})
            target_label = b.get('bounded_choice_target_label') or p.get('bounded_choice_target_label')
            base_pred_label = b.get('constrained_choice_top1_label')
            post_pred_label = p.get('constrained_choice_top1_label')
            rec = {
                'direction': direction,
                'row_id': rid,
                'task_type': parse_task(rid),
                'subfamily': parse_subfamily(rid),
                'language_family': parse_language(rid, src),
                'root_family': parse_root_family(rid),
                'target_label': target_label,
                'target_value': option_value(src or {}, target_label),
                'base_pred_label': base_pred_label,
                'base_pred_value': option_value(src or {}, base_pred_label),
                'post_pred_label': post_pred_label,
                'post_pred_value': option_value(src or {}, post_pred_label),
                'base_full_vocab_top1': b.get('full_vocab_top1_text'),
                'post_full_vocab_top1': p.get('full_vocab_top1_text'),
                'target_rank_full_vocab_base': b.get('target_rank_full_vocab'),
                'target_rank_full_vocab_post': p.get('target_rank_full_vocab'),
                'had_source_row': src is not None,
            }
            records.append(rec)

    def top(counter: Counter, n: int = 30):
        return [{'key': k, 'count': v} for k, v in counter.most_common(n)]

    by_dir = defaultdict(list)
    for r in records:
        by_dir[r['direction']].append(r)

    buckets = {}
    for direction, rows in by_dir.items():
        buckets[direction] = {
            'rows': len(rows),
            'by_task_type': top(Counter(r['task_type'] for r in rows)),
            'by_subfamily': top(Counter(r['subfamily'] for r in rows)),
            'by_language': top(Counter(r['language_family'] for r in rows)),
            'by_target_value': top(Counter(r['target_value'] for r in rows)),
            'by_base_to_post_prediction': top(Counter((r['base_pred_value'], r['post_pred_value']) for r in rows)),
            'by_target_base_post': top(Counter((r['target_value'], r['base_pred_value'], r['post_pred_value']) for r in rows)),
        }

    loss_next_action = [r for r in records if r['direction'] == 'loss' and r['task_type'] == 'transition_next_action']
    gain_next_action = [r for r in records if r['direction'] == 'gain' and r['task_type'] == 'transition_next_action']
    loss_candidate = [r for r in records if r['direction'] == 'loss' and r['task_type'] == 'transition_candidate_selection']
    gain_candidate = [r for r in records if r['direction'] == 'gain' and r['task_type'] == 'transition_candidate_selection']

    diagnosis = []
    if Counter(r['subfamily'] for r in loss_next_action).get('evidence_citation_selected_verifier', 0) >= 5:
        diagnosis.append('Most next-action losses are evidence_citation_selected_verifier rows, so Stage12073 erased selected-verifier behavior while helping patch-impact rows.')
    if Counter(r['subfamily'] for r in gain_next_action).get('patch_impact_source_surface', 0) >= 5:
        diagnosis.append('Most next-action gains are patch_impact_source_surface rows, meaning the synthetic support taught patch-plan timing more than verifier/evidence timing.')
    if len(loss_candidate) > len(gain_candidate):
        diagnosis.append('Candidate-selection losses also increased, so the support affected shared semantic-candidate geometry beyond next_action.')

    next_contract = {
        'recommended_stage': 'stage12079_next_action_repair_design',
        'do_not_train': True,
        'required_changes_before_next_probe': [
            'Split next_action support by subfamily: patch_impact_source_surface, evidence_citation_selected_verifier, verifier_outcome_selected_test, symptom_localization_source_surface.',
            'Add protected replay or support for evidence_citation_selected_verifier::next_action rows lost by Stage12075.',
            'Use lower weight or separate head/routing for synthetic milestone next-action rows until evidence-citation preservation is proven.',
            'Build counterfactual next_action rows where selected verifier evidence makes SELECT_TEST or VERIFY_RESULT correct, and PLAN_PATCH/RETRIEVE_EVIDENCE are explicit hard negatives.',
            'Audit against the Stage12076 lost row set before any full 640 transition probe.',
        ],
        'minimum_local_gate': {
            'lost_rows_recovered_on_training_candidate': '>=20/26 under same product scorer',
            'gained_rows_preserved': '>=10/12',
            'next_action_old_manifest': '>51/160',
            'old_transition_640': '>364/640 for progress',
        },
    }

    rows_path = OUT / 'next_action_loss_gain_records.jsonl'
    with rows_path.open('w') as f:
        for r in records:
            f.write(json.dumps(r, sort_keys=True) + '\n')

    summary = {
        'stage': STAGE,
        'stage_name': NAME,
        'created_at_utc': datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00','Z'),
        'source_artifacts': {
            'stage12076_audit': rel(AUDIT),
            'base_card': rel(BASE_CARD),
            'post_card': rel(POST_CARD),
            'source_rows': rel(SRC_ROWS),
        },
        'score_delta': {
            'old_transition_640': {'stage11924': 364, 'stage12075': 350, 'delta': -14},
            'transition_next_action': {'stage11924': 51, 'stage12075': 40, 'delta': -11},
            'transition_candidate_selection': {'stage11924': 89, 'stage12075': 86, 'delta': -3},
            'transition_continue_or_stop': {'stage11924': 128, 'stage12075': 128, 'delta': 0},
            'transition_verifier_transition': {'stage11924': 96, 'stage12075': 96, 'delta': 0},
        },
        'change_counts': {'gains': len(by_dir['gain']), 'losses': len(by_dir['loss']), 'net': len(by_dir['gain']) - len(by_dir['loss'])},
        'buckets': buckets,
        'key_next_action_patterns': {
            'gains': gain_next_action,
            'losses': loss_next_action,
        },
        'candidate_selection_patterns': {
            'gains': gain_candidate,
            'losses': loss_candidate,
        },
        'diagnosis': diagnosis,
        'next_contract': next_contract,
        'outputs': {'records': rel(rows_path), 'summary': rel(SUMMARY), 'summary_mirror': rel(MIRROR)},
    }
    write_json(SUMMARY, summary)
    write_json(MIRROR, summary)
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == '__main__':
    main()
