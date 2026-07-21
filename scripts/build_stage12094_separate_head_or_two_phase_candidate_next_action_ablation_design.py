#!/usr/bin/env python3
"""Design controlled ablations after Stage12091 candidate/next-action interference."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = 12094
NAME = 'stage12094_separate_head_or_two_phase_candidate_next_action_ablation_design'
OUT = ROOT / 'runs/local/artifacts' / NAME
SUMMARY = OUT / 'separate_head_or_two_phase_ablation_design.json'
MIRROR = ROOT / 'runs/summaries' / f'{NAME}.json'
DECISION = ROOT / 'runs/summaries/stage12093_candidate_selection_repair_training_decision.json'
AUDIT = ROOT / 'runs/summaries/stage12092_candidate_selection_repair_training_postrun_audit.json'
REQUEST = ROOT / 'runs/summaries/stage12090_candidate_selection_repair_training_request.json'
PACKET = ROOT / 'runs/summaries/stage12088_candidate_selection_repair_packet.json'
TRAIN_SCRIPT = ROOT / 'legacy_src/scripts/train_agentkernel_lite_encdec.py'
TRAIN_LOOP = ROOT / 'legacy_src/agentkernel_lite/training_loop.py'


def read_json(path: Path) -> Any:
    return json.loads(path.read_text())


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + '\n')


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    decision = read_json(DECISION)
    audit = read_json(AUDIT)
    request = read_json(REQUEST)
    packet = read_json(PACKET)
    trainer_text = TRAIN_SCRIPT.read_text(encoding='utf-8')
    loop_text = TRAIN_LOOP.read_text(encoding='utf-8')

    capabilities = {
        'transition_candidate_head_available': 'encoder_option_retrieval_transition_candidate_head' in trainer_text and 'bounded_choice_transition_candidate_head' in loop_text,
        'semantic_plus_transition_candidate_route_available': 'encoder_option_retrieval_semantic_plus_transition_candidate_head' in trainer_text,
        'head_only_available': '--bounded-choice-train-head-only' in trainer_text,
        'task_balanced_sampler_available': 'task_balanced' in trainer_text,
        'same_role_listwise_available': 'bounded_choice_same_role_listwise_weight' in trainer_text,
        'verifier_value_listwise_available': 'bounded_choice_verifier_value_listwise_weight' in trainer_text,
    }
    stage11924 = decision['selected_transition_frontier']['by_task']
    stage12083 = decision['diagnostic_result']['stage12083']['by_task']
    stage12091 = decision['diagnostic_result']['stage12091']['by_task']
    design = {
        'stage': STAGE,
        'stage_name': NAME,
        'created_at_utc': datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00', 'Z'),
        'decision': 'ablation_design_ready_do_not_train_same_objective',
        'selected_transition_frontier_remains': decision['selected_transition_frontier'],
        'why_this_stage_exists': {
            'stage12083': {
                'interpretation': 'next_action diagnostic gain, no total frontier gain',
                'by_task': stage12083,
            },
            'stage12091': {
                'interpretation': 'combined candidate-selection repair regressed total and next_action',
                'by_task': stage12091,
            },
            'baseline_by_task': stage11924,
            'failure_lesson': decision['lesson'],
        },
        'trainer_capabilities_verified': capabilities,
        'do_not_repeat': [
            'Do not rerun Stage12090 settings with different row order only.',
            'Do not mix candidate_selection repair and next_action preservation in one shared semantic-head update without isolating the route.',
            'Do not promote Stage12083 or Stage12091; both fail the transition frontier gate.',
        ],
        'controlled_ablation_matrix': {
            'A_candidate_head_only_candidate_rows': {
                'purpose': 'Test whether candidate_selection can recover when trained on a transition-specific candidate head, without next_action preservation rows pulling the same scorer.',
                'train_rows': {
                    'old_replay': 640,
                    'repair_subset': 'Stage12088 transition_candidate_selection rows only, expected 85 rows',
                    'excluded': 'Stage12088 transition_next_action rows',
                },
                'aux_source': 'encoder_option_retrieval_transition_candidate_head',
                'head_only': True,
                'sampler': 'task_balanced',
                'max_steps': 256,
                'learning_rate': '7.5e-5',
                'success_signal': {
                    'transition_candidate_selection': '>=89/160',
                    'transition_next_action': '>=51/160',
                    'old_transition_640': '>=364/640 preferred; do not accept protected regression',
                },
                'promotion_status': 'diagnostic_only unless routed/composite audit also preserves next_action >=59',
            },
            'B_two_phase_candidate_then_next_action': {
                'purpose': 'If A recovers candidate_selection without damaging baseline next_action, initialize a second phase from A and train only next_action preservation/gain rows.',
                'phase1': 'A_candidate_head_only_candidate_rows',
                'phase2_train_rows': {
                    'old_replay': 640,
                    'repair_subset': 'Stage12088 transition_next_action rows only, expected 75 rows',
                },
                'phase2_aux_source': 'encoder_option_retrieval_semantic_plus_transition_candidate_head',
                'phase2_head_only': True,
                'phase2_max_steps': 192,
                'phase2_learning_rate': '3e-5',
                'success_signal': {
                    'transition_candidate_selection': '>=89/160',
                    'transition_next_action': '>=59/160',
                    'old_transition_640': '>364/640',
                },
                'promotion_status': 'first promotable route if protected gates preserve and total improves',
            },
            'C_routed_inference_only_composite': {
                'purpose': 'Evaluate whether existing Stage11924/Stage12083/Stage12091 signals can be combined by task routing without more training.',
                'route': {
                    'candidate_selection': 'best of Stage11924 semantic route or transition_candidate_head candidate-only runtime if A exists',
                    'next_action': 'Stage12083 only if it preserves selected-verifier losses under row-level guard; otherwise Stage11924',
                    'continue_or_stop': 'Stage11924',
                    'verifier_transition': 'Stage11924',
                },
                'success_signal': {
                    'old_transition_640': '>364/640',
                    'no_row_level_shortcut': True,
                    'protected_gates': 'preserved',
                },
                'promotion_status': 'diagnostic unless route is simple, declared before eval, and reproducible on sealed rows',
            },
            'D_more_data_only_stop_condition': {
                'purpose': 'Guard against assuming architecture fixes everything. If A/B fail, the next move is new root-derived transition data, not more packet permutations.',
                'trigger': 'A fails candidate_selection >=89 or B fails next_action >=59 while preserving candidate_selection',
                'next_data_target': 'Transition-Root-250/Transition-5K with true rollout-derived candidate/next_action examples',
            },
        },
        'recommended_immediate_next_stage': {
            'name': 'stage12095_candidate_head_only_candidate_selection_request',
            'reason': 'It changes one variable: train a transition-candidate head on candidate_selection rows only, leaving next_action repair out.',
            'allowed_to_build_request': all(capabilities.values()) and packet['audit']['passes_admission'] and request['passed'],
            'do_not_launch_without_request_gates': True,
            'request_gates': {
                'uses_gpu2_mask': True,
                'head_only_enabled': True,
                'aux_source': 'encoder_option_retrieval_transition_candidate_head',
                'train_rows': '640 old replay + 85 Stage12088 candidate_selection rows',
                'no_next_action_repair_rows': True,
                'runtime_init': 'stage11924',
                'protected_reference': 'stage11507',
            },
        },
        'postrun_gate_for_stage12095': {
            'transition_candidate_selection': '>=89/160',
            'transition_next_action': '>=51/160',
            'transition_continue_or_stop': '>=128/160',
            'transition_verifier_transition': '>=96/160',
            'old_transition_640': '>=364/640 for useful diagnostic, >364/640 for frontier movement',
            'protected_filtered_strict': '22/22',
            'protected_old_canary_strict': '23/23',
            'residual_bank': '>=7/10',
            'source_heldout_smoke': '>=6/12',
        },
        'evidence_used': {
            'stage12092_decision': audit['decision'],
            'stage12092_gates': audit['gates'],
            'stage12090_request_passed': request['passed'],
            'stage12088_packet_audit': packet['audit'],
        },
        'source_artifacts': {
            'stage12093_decision': rel(DECISION),
            'stage12092_audit': rel(AUDIT),
            'stage12090_request': rel(REQUEST),
            'stage12088_packet': rel(PACKET),
            'trainer': rel(TRAIN_SCRIPT),
            'training_loop': rel(TRAIN_LOOP),
        },
        'outputs': {
            'summary': rel(SUMMARY),
            'summary_mirror': rel(MIRROR),
        },
    }
    write_json(SUMMARY, design)
    write_json(MIRROR, design)
    print(json.dumps({
        'decision': design['decision'],
        'trainer_capabilities_verified': capabilities,
        'recommended_immediate_next_stage': design['recommended_immediate_next_stage'],
    }, indent=2, sort_keys=True))


if __name__ == '__main__':
    main()
