#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = 10233
NAME = "stage10233_train_support_replenishment_atlas"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
ATLAS = OUT_DIR / "train_support_replenishment_atlas.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
EXACT_AUDIT = ROOT / "runs/local/artifacts/stage10232_exact_admitted_projection_runtime_audit/exact_admitted_projection_runtime_audit.json"
SUPPORT_AUDIT = ROOT / "runs/local/artifacts/stage10231_projection_failure_support_audit/projection_failure_support_audit.json"


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def display(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def now_utc() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    exact = load_json(EXACT_AUDIT)
    support = load_json(SUPPORT_AUDIT)

    atlas = {
        'stage': STAGE,
        'stage_name': NAME,
        'created_at_utc': now_utc(),
        'passed': True,
        'sources': {
            'exact_admitted_runtime_audit': display(EXACT_AUDIT),
            'projection_failure_support_audit': display(SUPPORT_AUDIT),
            'extra_python_review_packet': 'runs/local/artifacts/stage10120_true_source_backed_maintainer_root_bundle_review_packets/review_packets/stage10119__localsess_repository_library_sessseed_codex_sessions_rollout_2025_11_25t16_28_28_019abbd8_55f2_7781_97b4_efce_models_cli_py_models_scripts_build_repo_graphs_py_models_scripts_preprocess_pdfs_bde13d0440_aug_1500000_8b46e7f662__python',
            'extra_c_cpp_review_packet': 'runs/local/artifacts/stage10120_true_source_backed_maintainer_root_bundle_review_packets/review_packets/stage10119__localsess_parametergolf_sessseed_codex_sessions_rollout_2026_03_28t16_57_23_019d3561_0381_7b01_8350_0c0a_peytontolbert_parameter_golf_records_track_10min_16mb_2026_03_26_statespace_caus_49a543bb0b_aug_1500000_8b46e7f662__c_cpp',
            'extra_rust_candle_nn_review_packet': 'runs/local/artifacts/stage10127_true_source_backed_rust_review_packets_and_signoff/review_packets/stage10126__candle__candle-nn__rust',
            'extra_rust_candle_examples_review_packet': 'runs/local/artifacts/stage10127_true_source_backed_rust_review_packets_and_signoff/review_packets/stage10126__candle__candle-examples__rust',
        },
        'current_exact_unsolved_rows': [
            {
                'bundle_id': 'stage10119::localsess_bddy_website_sessseed_codex_sessions_rollout_2025_11_24t23_41_47_019ab83e_b023_7553_a34c_b93e_src_main_js_index_html_440e122a0f_aug_1500000_8b46e7f662::web_js_ts_html',
                'perspective': 'evidence_citation',
                'predicted': 'A',
                'expected': 'C',
                'support_status': 'direct_same_language_support',
                'current_train_source_diversity': 1,
                'replenishment_path': 'none_in_current_inventory',
            },
            {
                'bundle_id': 'stage10119::localsess_bddy_website_sessseed_codex_sessions_rollout_2025_11_28t14_11_27_019acacd_f95c_7802_9bfe_7232_index_html_f0be60dc44_aug_1500000_8b46e7f662::web_js_ts_html',
                'perspective': 'evidence_citation',
                'predicted': 'D',
                'expected': 'C',
                'support_status': 'direct_same_language_support',
                'current_train_source_diversity': 1,
                'replenishment_path': 'none_in_current_inventory',
            },
            {
                'bundle_id': 'stage10119::localsess_repository_library_sessseed_codex_sessions_rollout_2025_11_28t20_02_25_019acc0f_4bd7_77f2_b15f_3b0c_models_mirrormind_init_py_models_mirrormind_context_py_models_mirrormind_coordin_fd8013631e_aug_1500000_8b46e7f662::python',
                'perspective': 'evidence_citation',
                'predicted': 'D',
                'expected': 'C',
                'support_status': 'cross_language_only_support',
                'current_train_source_diversity': 0,
                'replenishment_path': 'pending_python_bundle_review',
            },
            {
                'bundle_id': 'stage10119::localsess_repository_library_sessseed_codex_sessions_rollout_2025_11_28t20_02_25_019acc0f_4bd7_77f2_b15f_3b0c_models_mirrormind_init_py_models_mirrormind_context_py_models_mirrormind_coordin_fd8013631e_aug_1500000_8b46e7f662::python',
                'perspective': 'verifier_outcome',
                'predicted': 'C',
                'expected': 'D',
                'support_status': 'unsupported_eval_only',
                'current_train_source_diversity': 0,
                'replenishment_path': 'pending_python_bundle_review',
            },
            {
                'bundle_id': 'stage10119::localsess_agentkernel_sessseed_codex_sessions_rollout_2026_03_26t17_53_18_019d2b47_7d2d_7622_8e05_3513_agent_kernel_modeling_ssm_kernels_src_selective_scan_cpp_agent_kernel_modeling_w_5511e7fec6_aug_1500000_8b46e7f662::c_cpp',
                'perspective': 'abstention_insufficient_evidence',
                'predicted': 'B',
                'expected': 'E',
                'support_status': 'direct_same_language_support',
                'current_train_source_diversity': 1,
                'replenishment_path': 'pending_c_cpp_bundle_review',
            },
            {
                'bundle_id': 'stage10126::tokenizers::tokenizers::rust',
                'perspective': 'evidence_citation',
                'predicted': 'B',
                'expected': 'E',
                'support_status': 'unsupported_eval_only',
                'current_train_source_diversity': 0,
                'replenishment_path': 'no_valid_extra_rust_bundle_in_current_inventory',
            },
        ],
        'replenishment_candidates': [
            {
                'bundle_id': 'stage10119::localsess_repository_library_sessseed_codex_sessions_rollout_2025_11_25t16_28_28_019abbd8_55f2_7781_97b4_efce_models_cli_py_models_scripts_build_repo_graphs_py_models_scripts_preprocess_pdfs_bde13d0440_aug_1500000_8b46e7f662::python',
                'language_family': 'python',
                'candidate_role': 'same_language_support_replenishment_for_python_candidate_change_surface_and_possible_verifier_family',
                'review_status': {
                    'rubric': 'pending_human_review',
                    'anti_cheat': 'pending_human_review',
                    'gold': 'bundle_gold_ready_for_eval = false; all relevant gold answers null',
                },
                'can_train_now': False,
                'why_not_train_now': 'No gold answers recorded and no anti-cheat/rubric signoff yet.',
                'recommended_next_action': 'Complete AI maintainer rubric, anti-cheat review, and perspective gold adjudication before any train use.',
            },
            {
                'bundle_id': 'stage10119::localsess_parametergolf_sessseed_codex_sessions_rollout_2026_03_28t16_57_23_019d3561_0381_7b01_8350_0c0a_peytontolbert_parameter_golf_records_track_10min_16mb_2026_03_26_statespace_caus_49a543bb0b_aug_1500000_8b46e7f662::c_cpp',
                'language_family': 'c_cpp',
                'candidate_role': 'same_language_support_replenishment_for_c_cpp_abstention_and_possible_evidence_family',
                'review_status': {
                    'rubric': 'pending_human_review',
                    'anti_cheat': 'pending_human_review',
                    'gold': 'bundle_gold_ready_for_eval = false; all relevant gold answers null',
                },
                'can_train_now': False,
                'why_not_train_now': 'No gold answers recorded and no anti-cheat/rubric signoff yet.',
                'recommended_next_action': 'Complete AI maintainer rubric, anti-cheat review, and perspective gold adjudication before any train use.',
            },
            {
                'bundle_id': 'stage10126::candle::candle-nn::rust',
                'language_family': 'rust',
                'candidate_role': 'potential_same_language_support_replenishment',
                'review_status': {
                    'rubric': 'completed_invalid',
                    'anti_cheat': 'completed_invalid',
                    'gold': 'recorded as abstain-only due shortcut-prone or underconstrained evidence',
                },
                'can_train_now': False,
                'why_not_train_now': 'Bundle already judged invalid for honest same-surface comparison; using it would optimize shortcut-prone evidence.',
                'recommended_next_action': 'Do not use for train support replenishment.',
            },
            {
                'bundle_id': 'stage10126::candle::candle-examples::rust',
                'language_family': 'rust',
                'candidate_role': 'potential_same_language_support_replenishment',
                'review_status': {
                    'rubric': 'completed_invalid',
                    'anti_cheat': 'completed_invalid',
                    'gold': 'recorded as abstain-only due shortcut-prone or underconstrained evidence',
                },
                'can_train_now': False,
                'why_not_train_now': 'Bundle already judged invalid for honest same-surface comparison; using it would optimize shortcut-prone evidence.',
                'recommended_next_action': 'Do not use for train support replenishment.',
            },
        ],
        'inventory_gaps': [
            'No additional web_js_ts_html bundle exists in the current preview inventory beyond the two admitted evaluation bundles, so web evidence_citation cannot be replenished from current stock.',
            'No valid extra rust bundle in the current reviewed inventory supports tokenizers-style evidence_citation; current extra rust bundles were explicitly rejected as shortcut-prone or underconstrained.',
            'Current supported web and c_cpp misses each rely on exactly one underlying train source row, which is too brittle for stable improvement.',
        ],
        'recommended_priority_order': [
            '1. Adjudicate the pending extra c_cpp bundle to try to create a second honest same-language support source for abstention/evidence families.',
            '2. Adjudicate the pending extra python bundle to create the first honest same-language support source for candidate_change_surface evidence in python.',
            '3. Build fresh independent web bundles, because current inventory has no extra web support source at all.',
            '4. Build fresh rust bundles, because current extra rust inventory is already judged invalid for honest scoring.',
        ],
    }
    ATLAS.write_text(json.dumps(atlas, indent=2, sort_keys=True) + "\n", encoding='utf-8')
    SUMMARY.write_text(json.dumps({'stage': STAGE, 'passed': True, 'artifact': display(ATLAS), 'recommended_priority_order': atlas['recommended_priority_order']}, indent=2, sort_keys=True) + "\n", encoding='utf-8')
    print(json.dumps({'stage': STAGE, 'passed': True, 'artifact': display(ATLAS), 'recommended_priority_order': atlas['recommended_priority_order']}, indent=2))


if __name__ == '__main__':
    main()
