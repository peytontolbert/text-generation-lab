#!/usr/bin/env python3
"""Local coverage audit for Stage12080 repair packet before any training probe."""
from __future__ import annotations

import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STAGE = 12081
NAME = 'stage12081_next_action_repair_local_audit'
OUT = ROOT / 'runs/local/artifacts' / NAME
SUMMARY = OUT / 'next_action_repair_local_audit.json'
MIRROR = ROOT / 'runs/summaries' / f'{NAME}.json'
REPAIR = ROOT / 'runs/local/artifacts/stage12080_next_action_subfamily_repair_packet/next_action_subfamily_repair_rows.jsonl'
REPAIR_SUMMARY = ROOT / 'runs/summaries/stage12080_next_action_subfamily_repair_packet.json'
LOSS_GAIN = ROOT / 'runs/local/artifacts/stage12078_next_action_loss_gain_atlas/next_action_loss_gain_records.jsonl'


def iter_jsonl(path: Path):
    for line in path.read_text().splitlines():
        if line.strip():
            yield json.loads(line)


def read_json(path: Path):
    return json.loads(path.read_text())


def write_json(path: Path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + '\n')


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def target_value(row):
    return (row.get('target') or {}).get('semantic_value') or row.get('standalone_projection_source',{}).get('gold_value') or ''


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    repair_rows = list(iter_jsonl(REPAIR))
    repair_summary = read_json(REPAIR_SUMMARY)
    changes = list(iter_jsonl(LOSS_GAIN))
    repair_sources = Counter(r.get('stage12080_source_row_id') for r in repair_rows)
    repair_subfamilies = Counter(r.get('stage12080_subfamily') for r in repair_rows)
    repair_targets = Counter(target_value(r) for r in repair_rows)

    losses = [r for r in changes if r['direction'] == 'loss']
    gains = [r for r in changes if r['direction'] == 'gain']
    selected_verifier_losses = [r for r in losses if r['task_type']=='transition_next_action' and r['subfamily'] in {'evidence_citation_selected_verifier','answerable_evidence_citation_build_constraint','answerable_evidence_citation_build_run_constraint'}]
    patch_gains = [r for r in gains if r['task_type']=='transition_next_action' and 'patch_impact' in r['subfamily']]

    covered_losses = [r for r in losses if repair_sources.get(r['row_id'], 0) > 0]
    covered_gains = [r for r in gains if repair_sources.get(r['row_id'], 0) > 0]
    covered_selected_losses = [r for r in selected_verifier_losses if repair_sources.get(r['row_id'], 0) > 0]
    covered_patch_gains = [r for r in patch_gains if repair_sources.get(r['row_id'], 0) > 0]

    missing_losses = [r['row_id'] for r in losses if repair_sources.get(r['row_id'], 0) == 0]
    missing_gains = [r['row_id'] for r in gains if repair_sources.get(r['row_id'], 0) == 0]

    gates = {
        'stage12080_admitted': repair_summary['audit']['passes_admission'] is True,
        'lost_rows_covered_at_least_20_of_26': len(covered_losses) >= 20,
        'selected_verifier_losses_covered_at_least_13_of_18': len(covered_selected_losses) >= 13,
        'gained_rows_covered_at_least_10_of_12': len(covered_gains) >= 10,
        'patch_impact_gains_covered_at_least_6_of_7': len(covered_patch_gains) >= 6,
        'packet_has_selected_verifier_preservation_60': repair_summary['audit']['subpacket_counts'].get('selected_verifier_retrieval_preservation') == 60,
        'packet_has_patch_positive_35': repair_summary['audit']['subpacket_counts'].get('patch_impact_plan_positive') == 35,
        'packet_prompt_leaks_zero': repair_summary['audit']['prompt_target_leak_count'] == 0,
        'packet_option_mirror_missing_zero': repair_summary['audit']['option_mirror_missing_count'] == 0,
    }
    passed = all(gates.values())
    payload = {
        'stage': STAGE,
        'stage_name': NAME,
        'created_at_utc': datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00','Z'),
        'decision': 'local_repair_audit_passed_training_request_allowed' if passed else 'local_repair_audit_failed_do_not_train',
        'passed': passed,
        'coverage': {
            'losses_total': len(losses),
            'losses_covered': len(covered_losses),
            'gains_total': len(gains),
            'gains_covered': len(covered_gains),
            'selected_verifier_losses_total': len(selected_verifier_losses),
            'selected_verifier_losses_covered': len(covered_selected_losses),
            'patch_gains_total': len(patch_gains),
            'patch_gains_covered': len(covered_patch_gains),
            'missing_losses': missing_losses,
            'missing_gains': missing_gains,
        },
        'repair_packet': {
            'rows': len(repair_rows),
            'source_rows': len(repair_sources),
            'target_counts': dict(repair_targets),
            'subfamily_counts': dict(repair_subfamilies),
            'subpacket_counts': repair_summary['audit']['subpacket_counts'],
        },
        'gates': gates,
        'next_recommendation': {
            'if_passed': 'build stage12082 guarded repair training request, but keep max steps lower than Stage12075 and preserve Stage11924 selected frontier until postrun audit passes',
            'if_failed': 'repair Stage12080 coverage before training',
            'postrun_promotion_gate': {
                'old_transition_640': '>364/640',
                'transition_next_action': '>51/160',
                'transition_candidate_selection': '>=89/160',
                'protected_gates': 'filtered strict 22/22, old strict 23/23, residual >=7/10, smoke >=6/12',
            },
        },
        'source_artifacts': {'repair_rows': rel(REPAIR), 'repair_summary': rel(REPAIR_SUMMARY), 'loss_gain_records': rel(LOSS_GAIN)},
        'outputs': {'summary': rel(SUMMARY), 'summary_mirror': rel(MIRROR)},
    }
    write_json(SUMMARY, payload)
    write_json(MIRROR, payload)
    print(json.dumps(payload, indent=2, sort_keys=True))

if __name__ == '__main__':
    main()
