#!/usr/bin/env python3
"""Design the repair package after Stage12075 next-action regression."""
from __future__ import annotations

import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STAGE = 12079
NAME = 'stage12079_next_action_repair_design'
OUT = ROOT / 'runs/local/artifacts' / NAME
SUMMARY = OUT / 'next_action_repair_design.json'
MIRROR = ROOT / 'runs/summaries' / f'{NAME}.json'
ATLAS = ROOT / 'runs/summaries/stage12078_next_action_loss_gain_atlas.json'
RECORDS = ROOT / 'runs/local/artifacts/stage12078_next_action_loss_gain_atlas/next_action_loss_gain_records.jsonl'


def read_json(path: Path):
    return json.loads(path.read_text())


def iter_jsonl(path: Path):
    for line in path.read_text().splitlines():
        if line.strip():
            yield json.loads(line)


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def write_json(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + '\n')


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    atlas = read_json(ATLAS)
    rows = list(iter_jsonl(RECORDS))
    gains = [r for r in rows if r['direction'] == 'gain']
    losses = [r for r in rows if r['direction'] == 'loss']
    next_losses = [r for r in losses if r['task_type'] == 'transition_next_action']
    next_gains = [r for r in gains if r['task_type'] == 'transition_next_action']
    selected_verifier_losses = [r for r in next_losses if r['subfamily'] in {'evidence_citation_selected_verifier', 'answerable_evidence_citation_build_constraint', 'answerable_evidence_citation_build_run_constraint'}]
    patch_gains = [r for r in next_gains if 'patch_impact' in r['subfamily']]

    repair_contract = {
        'stage': STAGE,
        'stage_name': NAME,
        'created_at_utc': datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00','Z'),
        'decision': 'design_next_action_repair_packet_do_not_train_yet',
        'selected_transition_frontier': 'stage11924_transition_listwise_head_only_probe',
        'rejected_runtime': 'stage12075_next_action_guarded_training_probe',
        'failure_summary': {
            'old_transition_delta': atlas['score_delta']['old_transition_640'],
            'next_action_delta': atlas['score_delta']['transition_next_action'],
            'gains': len(gains),
            'losses': len(losses),
            'selected_verifier_next_action_losses': len(selected_verifier_losses),
            'patch_impact_next_action_gains': len(patch_gains),
            'dominant_loss_shift': 'RETRIEVE_EVIDENCE -> PLAN_PATCH on selected-verifier/evidence-citation rows',
            'dominant_gain_shift': 'RETRIEVE_EVIDENCE -> PLAN_PATCH on patch-impact rows',
        },
        'repair_hypothesis': 'Stage12073 made PLAN_PATCH broadly more attractive. That is correct for patch-impact rows, but wrong for evidence-citation/selected-verifier rows where the next action should remain retrieve/select/verify rather than patch.',
        'materialization_contract': {
            'do_not_reuse_stage12073_as_is': True,
            'packet_name': 'stage12080_next_action_subfamily_repair_packet',
            'rows_total_target': 160,
            'required_subpackets': {
                'selected_verifier_retrieval_preservation': {
                    'rows': 60,
                    'source': 'clone/analogue from Stage12076 lost selected-verifier rows plus disjoint roots when available',
                    'gold_distribution': {'RETRIEVE_EVIDENCE': 35, 'SELECT_TEST': 15, 'VERIFY_RESULT': 10},
                    'hard_negatives': ['PLAN_PATCH', 'APPLY_PATCH_ABSTRACT'],
                    'purpose': 'Prevent selected-verifier evidence rows from collapsing to PLAN_PATCH.',
                },
                'patch_impact_plan_positive': {
                    'rows': 35,
                    'source': 'patch-impact rows where source+verifier evidence is enough to plan a bounded patch',
                    'gold_distribution': {'PLAN_PATCH': 25, 'VERIFY_RESULT': 10},
                    'hard_negatives': ['RETRIEVE_EVIDENCE', 'ABSTAIN_OR_ROLLBACK'],
                    'purpose': 'Preserve the genuine Stage12075 gains without applying them globally.',
                },
                'symptom_localization_preservation': {
                    'rows': 25,
                    'source': 'symptom_localization_source_surface candidate/next-action analogues',
                    'gold_distribution': {'LOCALIZE_FAILURE': 15, 'RETRIEVE_EVIDENCE': 10},
                    'hard_negatives': ['SELECT_TEST', 'PLAN_PATCH'],
                    'purpose': 'Avoid selected-test overcorrection on source-surface localization rows.',
                },
                'candidate_selection_do_not_regress': {
                    'rows': 40,
                    'source': 'Stage12076 candidate-selection lost/gained row analogues',
                    'gold_distribution': {'semantic_role_target': 40},
                    'hard_negatives': ['the Stage12075 wrong prediction for each row'],
                    'purpose': 'Protect shared semantic-candidate geometry; Stage12075 also lost candidate-selection rows.',
                },
            },
            'weighting_rule': 'Do not let synthetic patch/abstain rows exceed 35% of next-action repair train rows.',
            'routing_rule': 'If using the same semantic_candidate_head, include selected-verifier preservation rows in every training epoch before patch-impact positives.',
            'anti_cheat': [
                'opaque labels shuffled deterministically',
                'semantic target not visible before options',
                'standalone_projection_source.opaque_options mirrored',
                'no singleton options',
                'root lineage isolated from strict/protected rows unless row is explicitly old-manifest replay',
            ],
        },
        'local_preflight_before_full_probe': {
            'recommended_stage': 'stage12081_next_action_repair_local_audit',
            'evaluate_against': {
                'lost_rows_from_stage12076': len(losses),
                'gained_rows_from_stage12076': len(gains),
                'selected_verifier_next_action_losses': len(selected_verifier_losses),
            },
            'pass_conditions': {
                'lost_rows_recovered': '>=20/26',
                'selected_verifier_losses_recovered': f'>={max(1, int(len(selected_verifier_losses) * 0.75))}/{len(selected_verifier_losses)}',
                'gained_rows_preserved': '>=10/12',
                'no_new_target_value_leaks': True,
                'no_option_mirror_missing': True,
            },
        },
        'full_probe_gate_after_local_pass': {
            'old_transition_640': '>364/640 required for progress, >386/640 for Gemma win',
            'transition_next_action': '>51/160',
            'transition_candidate_selection': '>=89/160',
            'protected_filtered_strict': '22/22',
            'protected_old_canary_strict': '23/23',
            'residual_bank': '>=7/10',
            'source_heldout_smoke': '>=6/12',
        },
        'loss_gain_examples': {
            'selected_verifier_losses': selected_verifier_losses[:20],
            'patch_impact_gains': patch_gains[:20],
        },
        'source_artifacts': {'atlas': rel(ATLAS), 'records': rel(RECORDS)},
        'outputs': {'summary': rel(SUMMARY), 'summary_mirror': rel(MIRROR)},
    }
    write_json(SUMMARY, repair_contract)
    write_json(MIRROR, repair_contract)
    print(json.dumps(repair_contract, indent=2, sort_keys=True))


if __name__ == '__main__':
    main()
