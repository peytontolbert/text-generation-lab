#!/usr/bin/env python3
"""Materialize a subfamily-aware next-action repair packet after Stage12075 regression."""
from __future__ import annotations

import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = 12080
NAME = 'stage12080_next_action_subfamily_repair_packet'
OUT = ROOT / 'runs/local/artifacts' / NAME
SUMMARY = OUT / 'next_action_subfamily_repair_packet.json'
MIRROR = ROOT / 'runs/summaries' / f'{NAME}.json'
SRC_ROWS = ROOT / 'runs/local/artifacts/stage11897_transition_record_projection_rows/transition_projection_rows.jsonl'
DESIGN = ROOT / 'runs/summaries/stage12079_next_action_repair_design.json'
LOSS_GAIN = ROOT / 'runs/local/artifacts/stage12078_next_action_loss_gain_atlas/next_action_loss_gain_records.jsonl'
ROWS_OUT = OUT / 'next_action_subfamily_repair_rows.jsonl'


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


def subfamily(row_or_id: Any) -> str:
    rid = row_or_id if isinstance(row_or_id, str) else row_or_id['row_id']
    return rid.split('::')[-2]


def target_value(row: dict[str, Any]) -> str:
    return (row.get('target') or {}).get('semantic_value') or row.get('standalone_projection_source', {}).get('gold_value') or ''


def clone(row: dict[str, Any], subpacket: str, ordinal: int) -> dict[str, Any]:
    r = json.loads(json.dumps(row))
    r['row_id'] = f"{row['row_id']}::stage12080::{subpacket}::{ordinal}"
    r['split'] = 'train'
    r['package_split'] = 'train'
    r['train_support_only'] = True
    r['strict_eval_eligible'] = False
    r['source_heldout_admissible'] = False
    r['stage12080_subpacket'] = subpacket
    r['stage12080_source_row_id'] = row['row_id']
    r['stage12080_subfamily'] = subfamily(row)
    r['stage12080_target_value'] = target_value(row)
    sp = dict(r.get('standalone_projection_source') or {})
    if r.get('opaque_options') and not sp.get('opaque_options'):
        sp['opaque_options'] = r['opaque_options']
    if r.get('target'):
        sp.setdefault('gold_label', r['target'].get('bounded_choice_target_label') or r.get('target_label'))
        sp.setdefault('gold_value', r['target'].get('semantic_value'))
    r['standalone_projection_source'] = sp
    r['loss_mask'] = {'bounded_choice_aux': True, 'decoder_ce': True, 'structured_aux': True, 'transition_projection': True}
    ac = dict(r.get('anti_cheat') or {})
    ac.update({
        'deterministic_option_shuffle': bool(ac.get('deterministic_option_shuffle', True)),
        'target_label_not_visible_before_options': True,
        'projection_from_verified_transition_record': True,
        'not_promotable_eval_row': True,
        'stage12080_replay_or_analogue_support': True,
    })
    r['anti_cheat'] = ac
    return r


def cycle_pick(rows: list[dict[str, Any]], count: int, subpacket: str, start: int = 0) -> list[dict[str, Any]]:
    if not rows:
        return []
    out = []
    for i in range(count):
        out.append(clone(rows[(start + i) % len(rows)], subpacket, i + 1))
    return out


def prompt_leak(row: dict[str, Any]) -> bool:
    text = row.get('input_text') or row.get('prompt_text') or ''
    before = text.split('CANDIDATES', 1)[0].split('Options:', 1)[0]
    tv = target_value(row)
    # Candidate-selection semantic IDs can be opaque one-character labels such
    # as A/B/C.  Scanning those against prose causes false leak positives.
    if not tv or len(str(tv)) <= 1:
        return False
    return tv in before


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    design = read_json(DESIGN)
    source_rows = list(iter_jsonl(SRC_ROWS))
    by_id = {r['row_id']: r for r in source_rows}
    loss_gain = list(iter_jsonl(LOSS_GAIN))

    next_rows = [r for r in source_rows if r.get('task_type') == 'transition_next_action']
    cand_rows = [r for r in source_rows if r.get('task_type') == 'transition_candidate_selection']

    selected_retrieve = [r for r in next_rows if subfamily(r) in {'evidence_citation_selected_verifier','answerable_evidence_citation_build_constraint','answerable_evidence_citation_build_run_constraint'} and target_value(r) == 'RETRIEVE_EVIDENCE']
    selected_test = [r for r in next_rows if subfamily(r).startswith('verifier_outcome_selected') and target_value(r) == 'SELECT_TEST']
    patch_plan = [r for r in next_rows if 'patch_impact' in subfamily(r) and target_value(r) == 'PLAN_PATCH']
    symptom_localize = [r for r in next_rows if 'symptom_localization' in subfamily(r) and target_value(r) == 'LOCALIZE_FAILURE']
    symptom_retrieve = [r for r in next_rows if 'evidence_citation' in subfamily(r) and target_value(r) == 'RETRIEVE_EVIDENCE']

    loss_candidate_ids = [r['row_id'] for r in loss_gain if r['direction'] == 'loss' and r['task_type'] == 'transition_candidate_selection']
    gain_candidate_ids = [r['row_id'] for r in loss_gain if r['direction'] == 'gain' and r['task_type'] == 'transition_candidate_selection']
    candidate_sources = [by_id[rid] for rid in loss_candidate_ids + gain_candidate_ids if rid in by_id]
    if len(candidate_sources) < 40:
        # Fill with same subfamilies that moved in Stage12075, preserving the old targets.
        moved_subfamilies = {r['subfamily'] for r in loss_gain if r['task_type'] == 'transition_candidate_selection'} | {r['subfamily'] for r in loss_gain if r['task_type'] == 'transition_candidate_selection'}
        candidate_sources += [r for r in cand_rows if subfamily(r) in moved_subfamilies]

    rows: list[dict[str, Any]] = []
    # 60 selected-verifier preservation rows: 40 retrieve + 20 selected-test.
    rows += cycle_pick(selected_retrieve, 40, 'selected_verifier_retrieval_preservation')
    rows += cycle_pick(selected_test, 20, 'selected_verifier_retrieval_preservation', start=3)
    # 35 patch positives, preserving the Stage12075 genuine gains but bounded.
    rows += cycle_pick(patch_plan, 35, 'patch_impact_plan_positive')
    # 25 symptom/localization preservation rows.
    rows += cycle_pick(symptom_localize, 20, 'symptom_localization_preservation')
    rows += cycle_pick(symptom_retrieve, 5, 'symptom_localization_preservation')
    # 40 candidate-selection geometry protection rows.
    rows += cycle_pick(candidate_sources, 40, 'candidate_selection_do_not_regress')

    with ROWS_OUT.open('w') as f:
        for row in rows:
            f.write(json.dumps(row, sort_keys=True) + '\n')

    subpacket_counts = Counter(r['stage12080_subpacket'] for r in rows)
    target_counts = Counter(target_value(r) for r in rows)
    task_counts = Counter(r.get('task_type') for r in rows)
    subfamily_counts = Counter(r['stage12080_subfamily'] for r in rows)
    lang_counts = Counter(r.get('language_family') for r in rows)
    source_dup_counts = Counter(r['stage12080_source_row_id'] for r in rows)
    audit = {
        'rows': len(rows),
        'unique_source_rows': len(source_dup_counts),
        'duplicate_source_rows': sum(1 for v in source_dup_counts.values() if v > 1),
        'subpacket_counts': dict(subpacket_counts),
        'task_counts': dict(task_counts),
        'target_counts': dict(target_counts),
        'subfamily_counts': dict(subfamily_counts),
        'language_counts': dict(lang_counts),
        'prompt_target_leak_count': sum(1 for r in rows if prompt_leak(r)),
        'option_mirror_missing_count': sum(1 for r in rows if r.get('opaque_options') and not r.get('standalone_projection_source',{}).get('opaque_options')),
        'singleton_option_count': sum(1 for r in rows if len(r.get('opaque_options') or []) <= 1),
        'unsafe_loss_mask_count': sum(1 for r in rows if not any((r.get('loss_mask') or {}).values())),
        'passes_admission': False,
    }
    audit['passes_admission'] = (
        audit['rows'] == 160 and
        audit['subpacket_counts'].get('selected_verifier_retrieval_preservation') == 60 and
        audit['subpacket_counts'].get('patch_impact_plan_positive') == 35 and
        audit['subpacket_counts'].get('symptom_localization_preservation') == 25 and
        audit['subpacket_counts'].get('candidate_selection_do_not_regress') == 40 and
        audit['prompt_target_leak_count'] == 0 and
        audit['option_mirror_missing_count'] == 0 and
        audit['singleton_option_count'] == 0 and
        audit['unsafe_loss_mask_count'] == 0
    )

    summary = {
        'stage': STAGE,
        'stage_name': 'stage12080_next_action_subfamily_repair_packet',
        'created_at_utc': datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00','Z'),
        'decision': 'repair_packet_admitted_no_training_launched' if audit['passes_admission'] else 'repair_packet_blocked',
        'selected_transition_frontier': 'stage11924_transition_listwise_head_only_probe',
        'purpose': 'Repair Stage12075 overcorrection by preserving selected-verifier RETRIEVE_EVIDENCE behavior while keeping patch-impact PLAN_PATCH positives bounded.',
        'audit': audit,
        'training_allowed': False,
        'next_stage': {
            'recommended': 'stage12081_next_action_repair_local_audit',
            'purpose': 'Evaluate the repair packet against Stage12076 gained/lost rows before any full training probe.',
            'do_not_skip': True,
        },
        'source_artifacts': {'design': rel(DESIGN), 'source_rows': rel(SRC_ROWS), 'loss_gain_records': rel(LOSS_GAIN)},
        'outputs': {'rows': rel(ROWS_OUT), 'summary': rel(SUMMARY), 'summary_mirror': rel(MIRROR)},
        'design_reference': design['materialization_contract'],
    }
    write_json(SUMMARY, summary)
    write_json(MIRROR, summary)
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == '__main__':
    main()
