#!/usr/bin/env python3
"""Materialize candidate-selection repair rows after Stage12087 design."""
from __future__ import annotations

import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = 12088
NAME = 'stage12088_candidate_selection_repair_packet'
OUT = ROOT / 'runs/local/artifacts' / NAME
SUMMARY = OUT / 'candidate_selection_repair_packet.json'
MIRROR = ROOT / 'runs/summaries' / f'{NAME}.json'
ROWS_OUT = OUT / 'candidate_selection_repair_rows.jsonl'
DESIGN = ROOT / 'runs/summaries/stage12087_candidate_selection_repair_design.json'
RECORDS = ROOT / 'runs/local/artifacts/stage12086_candidate_selection_regression_atlas/candidate_selection_regression_records.jsonl'
SRC_ROWS = ROOT / 'runs/local/artifacts/stage11897_transition_record_projection_rows/transition_projection_rows.jsonl'


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


def target_value(row: dict[str, Any]) -> str:
    return (row.get('target') or {}).get('semantic_value') or row.get('standalone_projection_source', {}).get('gold_value') or ''


def clone(row: dict[str, Any], record: dict[str, Any], subpacket: str, ordinal: int) -> dict[str, Any]:
    out = json.loads(json.dumps(row))
    out['row_id'] = f"{row['row_id']}::stage12088::{subpacket}::{ordinal}"
    out['split'] = 'train'
    out['package_split'] = 'train'
    out['train_support_only'] = True
    out['strict_eval_eligible'] = False
    out['source_heldout_admissible'] = False
    out['stage12088_subpacket'] = subpacket
    out['stage12088_source_row_id'] = row['row_id']
    out['stage12088_source_direction'] = record.get('direction')
    out['stage12088_source_task_type'] = record.get('task_type')
    out['stage12088_source_subfamily'] = record.get('subfamily')
    out['stage12088_hard_negative_role'] = (
        record.get('post_pred_role') if record.get('direction') == 'loss' else record.get('base_pred_role')
    )
    out['stage12088_hard_negative_value'] = (
        record.get('post_pred_value') if record.get('direction') == 'loss' else record.get('base_pred_value')
    )
    out['stage12088_target_role'] = record.get('target_role')
    out['stage12088_target_value'] = record.get('target_value')
    sp = dict(out.get('standalone_projection_source') or {})
    if out.get('opaque_options') and not sp.get('opaque_options'):
        sp['opaque_options'] = out['opaque_options']
    if out.get('target'):
        sp.setdefault('gold_label', out['target'].get('bounded_choice_target_label') or out.get('target_label'))
        sp.setdefault('gold_value', out['target'].get('semantic_value'))
    out['standalone_projection_source'] = sp
    out['loss_mask'] = {
        'bounded_choice_aux': True,
        'decoder_ce': True,
        'structured_aux': True,
        'transition_projection': True,
        'candidate_selection_repair': subpacket.startswith('candidate_selection'),
        'next_action_preservation': 'next_action' in subpacket,
    }
    ac = dict(out.get('anti_cheat') or {})
    ac.update({
        'deterministic_option_shuffle': bool(ac.get('deterministic_option_shuffle', True)),
        'target_label_not_visible_before_options': True,
        'projection_from_verified_transition_record': True,
        'not_promotable_eval_row': True,
        'stage12088_replay_or_analogue_support': True,
    })
    out['anti_cheat'] = ac
    return out


def cycle(records: list[dict[str, Any]], source_by_id: dict[str, dict[str, Any]], count: int, subpacket: str) -> list[dict[str, Any]]:
    if not records:
        return []
    out = []
    for i in range(count):
        rec = records[i % len(records)]
        src = source_by_id.get(rec['row_id'])
        if src:
            out.append(clone(src, rec, subpacket, i + 1))
    return out


def prompt_leak(row: dict[str, Any]) -> bool:
    text = row.get('input_text') or row.get('prompt_text') or ''
    before = text.split('CANDIDATES', 1)[0].split('Options:', 1)[0]
    tv = str(target_value(row) or '')
    if not tv or len(tv) <= 1:
        return False
    return tv in before


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    design = read_json(DESIGN)
    records = list(iter_jsonl(RECORDS))
    source_by_id = {r['row_id']: r for r in iter_jsonl(SRC_ROWS)}

    cand_losses = [r for r in records if r.get('task_type') == 'transition_candidate_selection' and r.get('direction') == 'loss']
    cand_gains = [r for r in records if r.get('task_type') == 'transition_candidate_selection' and r.get('direction') == 'gain']
    next_gains = [r for r in records if r.get('task_type') == 'transition_next_action' and r.get('direction') == 'gain']
    next_losses = [r for r in records if r.get('task_type') == 'transition_next_action' and r.get('direction') == 'loss']

    rows: list[dict[str, Any]] = []
    rows += cycle(cand_losses, source_by_id, 60, 'candidate_selection_regression_replay')
    rows += cycle(cand_gains, source_by_id, 25, 'candidate_selection_gain_preservation')
    rows += cycle(next_gains, source_by_id, 45, 'next_action_gain_preservation')
    rows += cycle(next_losses, source_by_id, 30, 'selected_verifier_next_action_preservation')

    with ROWS_OUT.open('w') as f:
        for row in rows:
            f.write(json.dumps(row, sort_keys=True) + '\n')

    subpacket_counts = Counter(r['stage12088_subpacket'] for r in rows)
    source_counts = Counter(r['stage12088_source_row_id'] for r in rows)
    task_counts = Counter(r.get('task_type') for r in rows)
    target_values = Counter(target_value(r) for r in rows)
    target_roles = Counter(r.get('stage12088_target_role') for r in rows)
    hard_negative_roles = Counter(r.get('stage12088_hard_negative_role') for r in rows)
    audit = {
        'rows': len(rows),
        'unique_source_rows': len(source_counts),
        'duplicate_source_rows': sum(1 for v in source_counts.values() if v > 1),
        'subpacket_counts': dict(subpacket_counts),
        'task_counts': dict(task_counts),
        'target_value_counts': dict(target_values),
        'target_role_counts': dict(target_roles),
        'hard_negative_role_counts': dict(hard_negative_roles),
        'prompt_target_leak_count': sum(1 for r in rows if prompt_leak(r)),
        'option_mirror_missing_count': sum(1 for r in rows if r.get('opaque_options') and not r.get('standalone_projection_source', {}).get('opaque_options')),
        'singleton_option_count': sum(1 for r in rows if len(r.get('opaque_options') or []) <= 1),
        'unsafe_loss_mask_count': sum(1 for r in rows if not any((r.get('loss_mask') or {}).values())),
        'missing_source_row_count': sum(1 for r in records if r.get('row_id') not in source_by_id),
        'covered_candidate_selection_losses': len({r['stage12088_source_row_id'] for r in rows if r['stage12088_subpacket'] == 'candidate_selection_regression_replay'}),
        'covered_candidate_selection_gains': len({r['stage12088_source_row_id'] for r in rows if r['stage12088_subpacket'] == 'candidate_selection_gain_preservation'}),
        'covered_next_action_gains': len({r['stage12088_source_row_id'] for r in rows if r['stage12088_subpacket'] == 'next_action_gain_preservation'}),
        'covered_next_action_losses': len({r['stage12088_source_row_id'] for r in rows if r['stage12088_subpacket'] == 'selected_verifier_next_action_preservation'}),
        'passes_admission': False,
    }
    audit['passes_admission'] = (
        audit['rows'] == 160
        and audit['subpacket_counts'].get('candidate_selection_regression_replay') == 60
        and audit['subpacket_counts'].get('candidate_selection_gain_preservation') == 25
        and audit['subpacket_counts'].get('next_action_gain_preservation') == 45
        and audit['subpacket_counts'].get('selected_verifier_next_action_preservation') == 30
        and audit['covered_candidate_selection_losses'] == len(cand_losses)
        and audit['covered_candidate_selection_gains'] == len(cand_gains)
        and audit['covered_next_action_gains'] == len(next_gains)
        and audit['covered_next_action_losses'] >= 13
        and audit['prompt_target_leak_count'] == 0
        and audit['option_mirror_missing_count'] == 0
        and audit['singleton_option_count'] == 0
        and audit['unsafe_loss_mask_count'] == 0
    )

    summary = {
        'stage': STAGE,
        'stage_name': NAME,
        'created_at_utc': datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00', 'Z'),
        'decision': 'candidate_selection_repair_packet_admitted_no_training_launched' if audit['passes_admission'] else 'candidate_selection_repair_packet_blocked',
        'selected_transition_frontier': 'stage11924_transition_listwise_head_only_probe',
        'purpose': 'Restore Stage12083 candidate-selection losses while preserving next-action gains.',
        'training_allowed': False,
        'audit': audit,
        'next_stage': {
            'recommended': 'stage12089_candidate_selection_repair_local_audit',
            'do_not_skip': True,
            'purpose': 'Verify coverage and anti-cheat gates before any guarded training request.',
        },
        'source_artifacts': {
            'design': rel(DESIGN),
            'stage12086_records': rel(RECORDS),
            'source_rows': rel(SRC_ROWS),
        },
        'outputs': {
            'rows': rel(ROWS_OUT),
            'summary': rel(SUMMARY),
            'summary_mirror': rel(MIRROR),
        },
        'design_reference': design['materialization_contract'],
    }
    write_json(SUMMARY, summary)
    write_json(MIRROR, summary)
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == '__main__':
    main()
