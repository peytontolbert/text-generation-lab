#!/usr/bin/env python3
"""Local preflight audit for the Stage12088 candidate-selection repair packet."""
from __future__ import annotations

import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = 12089
NAME = 'stage12089_candidate_selection_repair_local_audit'
OUT = ROOT / 'runs/local/artifacts' / NAME
SUMMARY = OUT / 'candidate_selection_repair_local_audit.json'
MIRROR = ROOT / 'runs/summaries' / f'{NAME}.json'
DESIGN = ROOT / 'runs/summaries/stage12087_candidate_selection_repair_design.json'
PACKET = ROOT / 'runs/summaries/stage12088_candidate_selection_repair_packet.json'
ROWS = ROOT / 'runs/local/artifacts/stage12088_candidate_selection_repair_packet/candidate_selection_repair_rows.jsonl'
RECORDS = ROOT / 'runs/local/artifacts/stage12086_candidate_selection_regression_atlas/candidate_selection_regression_records.jsonl'


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
    packet = read_json(PACKET)
    rows = list(iter_jsonl(ROWS))
    records = list(iter_jsonl(RECORDS))

    cand_losses = {r['row_id'] for r in records if r.get('task_type') == 'transition_candidate_selection' and r.get('direction') == 'loss'}
    cand_gains = {r['row_id'] for r in records if r.get('task_type') == 'transition_candidate_selection' and r.get('direction') == 'gain'}
    next_gains = {r['row_id'] for r in records if r.get('task_type') == 'transition_next_action' and r.get('direction') == 'gain'}
    next_losses = {r['row_id'] for r in records if r.get('task_type') == 'transition_next_action' and r.get('direction') == 'loss'}

    sources_by_subpacket: dict[str, set[str]] = {}
    for row in rows:
        sources_by_subpacket.setdefault(row['stage12088_subpacket'], set()).add(row['stage12088_source_row_id'])

    covered = {
        'candidate_selection_losses': len(cand_losses & sources_by_subpacket.get('candidate_selection_regression_replay', set())),
        'candidate_selection_gains': len(cand_gains & sources_by_subpacket.get('candidate_selection_gain_preservation', set())),
        'next_action_gains': len(next_gains & sources_by_subpacket.get('next_action_gain_preservation', set())),
        'next_action_losses': len(next_losses & sources_by_subpacket.get('selected_verifier_next_action_preservation', set())),
    }
    totals = {
        'candidate_selection_losses': len(cand_losses),
        'candidate_selection_gains': len(cand_gains),
        'next_action_gains': len(next_gains),
        'next_action_losses': len(next_losses),
    }
    thresholds = {
        'candidate_selection_losses': max(1, int(totals['candidate_selection_losses'] * 0.8)),
        'candidate_selection_gains': max(1, int(totals['candidate_selection_gains'] * 0.75)),
        'next_action_gains': max(1, int(totals['next_action_gains'] * 0.8)),
        'next_action_losses': max(1, int(totals['next_action_losses'] * 0.6)),
    }
    anti_cheat = {
        'prompt_target_leak_count': sum(1 for r in rows if prompt_leak(r)),
        'option_mirror_missing_count': sum(1 for r in rows if r.get('opaque_options') and not r.get('standalone_projection_source', {}).get('opaque_options')),
        'singleton_option_count': sum(1 for r in rows if len(r.get('opaque_options') or []) <= 1),
        'unsafe_loss_mask_count': sum(1 for r in rows if not any((r.get('loss_mask') or {}).values())),
        'missing_source_metadata_count': sum(1 for r in rows if not r.get('stage12088_source_row_id') or not r.get('stage12088_source_direction')),
    }
    pass_conditions = {
        'packet_admitted': packet.get('decision') == 'candidate_selection_repair_packet_admitted_no_training_launched',
        'rows_160': len(rows) == 160,
        'candidate_selection_losses_covered': covered['candidate_selection_losses'] >= thresholds['candidate_selection_losses'],
        'candidate_selection_gains_covered': covered['candidate_selection_gains'] >= thresholds['candidate_selection_gains'],
        'next_action_gains_covered': covered['next_action_gains'] >= thresholds['next_action_gains'],
        'next_action_losses_guarded': covered['next_action_losses'] >= thresholds['next_action_losses'],
        'no_target_leak': anti_cheat['prompt_target_leak_count'] == 0,
        'no_option_mirror_missing': anti_cheat['option_mirror_missing_count'] == 0,
        'no_singleton_options': anti_cheat['singleton_option_count'] == 0,
        'safe_loss_masks': anti_cheat['unsafe_loss_mask_count'] == 0,
        'source_metadata_present': anti_cheat['missing_source_metadata_count'] == 0,
    }
    passes = all(pass_conditions.values())
    summary = {
        'stage': STAGE,
        'stage_name': NAME,
        'created_at_utc': datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00', 'Z'),
        'decision': 'local_audit_passed_training_request_allowed' if passes else 'local_audit_failed_do_not_train',
        'selected_transition_frontier': 'stage11924_transition_listwise_head_only_probe',
        'candidate_runtime_under_repair': 'stage12083_next_action_repair_training_probe',
        'covered': covered,
        'totals': totals,
        'thresholds': thresholds,
        'anti_cheat': anti_cheat,
        'pass_conditions': pass_conditions,
        'subpacket_counts': dict(Counter(r['stage12088_subpacket'] for r in rows)),
        'task_counts': dict(Counter(r.get('task_type') for r in rows)),
        'target_value_counts': dict(Counter(target_value(r) for r in rows)),
        'postrun_gate_if_training_request_is_built': design['postrun_promotion_gate'],
        'next_stage': {
            'recommended': 'stage12090_candidate_selection_repair_training_request' if passes else None,
            'training_allowed': passes,
            'do_not_train_if_failed': not passes,
        },
        'source_artifacts': {
            'design': rel(DESIGN),
            'packet_summary': rel(PACKET),
            'packet_rows': rel(ROWS),
            'stage12086_records': rel(RECORDS),
        },
        'outputs': {
            'summary': rel(SUMMARY),
            'summary_mirror': rel(MIRROR),
        },
    }
    write_json(SUMMARY, summary)
    write_json(MIRROR, summary)
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == '__main__':
    main()
