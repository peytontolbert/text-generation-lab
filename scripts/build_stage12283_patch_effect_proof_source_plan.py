#!/usr/bin/env python3
from __future__ import annotations
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
STAGE='stage12283_patch_effect_proof_source_plan'
OUT=ROOT/f'runs/local/artifacts/{STAGE}'
SUMMARY=ROOT/f'runs/summaries/{STAGE}.json'
plan={
 'stage':STAGE,
 'decision':'patch_effect_proof_source_plan_ready_execution_required',
 'diagnosis':'chat-mined patch/verifier loops are useful for transition support but insufficient for external comparable repair; use replayable external commit pairs for real patch-effect proof.',
 'primary_source':{
   'stage':'stage12244_external_repair_commit_pair_replay_request',
   'request':'runs/local/artifacts/stage12244_external_repair_commit_pair_replay_request/external_repair_commit_pair_replay_request.json',
   'targets':'runs/local/artifacts/stage12244_external_repair_commit_pair_replay_request/replay_targets.jsonl',
   'target_count':20,
   'language_counts':{'python':12,'web_js_ts_html':4,'rust':4},
   'repo_families':['pytest','sympy','eslint','biome','BrowserGym','SWE-bench']
 },
 'proof_levels':{
   'PE0_candidate':'commit pair plus verifier command only; no row admission',
   'PE1_preflight':'test path exists, source diff not test-only, patch applies to before, no network/GPU/install requirement',
   'PE2_executed_phases':'before verifier observed fail, before_plus_patch observed pass, after observed pass with logs captured',
   'PE3_semantic_patch_effect':'failure is behavior/code-related, verifier semantically targets changed path, no post same-family failure remains',
   'PE4_external_comparable_repair':'PE1+PE2+PE3, external repo, no protected overlap, anti-cheat renderable',
   'PE5_strict_eval_eligible':'PE4 plus sealed split lineage, option permutation, no target leakage, no train/source overlap'
 },
 'hard_rejects':['syntax_only_mutation','env_dependency_network_gpu_install_failure','missing_test_or_no_tests','selected_test_added_only_by_patch','weak_or_unrelated_verifier','pass_to_pass_only','cross_lineage_diff_command_verifier','post_failure_remains_same_family','prior_patch_attachment','raw_patch_or_log_emitted_to_model_input'],
 'next_execution_stage':'stage12284_external_repair_commit_pair_replay_preflight',
 'execution_policy':{'write_root':'/data/tmp/stage12284_external_repair_replay','network':'forbidden','gpu_visible':False,'timeout_seconds_per_phase':120,'training_allowed':False},
 'expected_outputs':['phase_status_records.jsonl','patch_effect_proof_candidates.jsonl','preflight_rejects.jsonl','replay_summary.json'],
 'admission_gate':{'external_comparable_patch_trace_rows_min_before_training':5,'external_fail_to_pass_rows_min_before_training':5,'all_rows_require_PE4':True},
 'training_rows_emitted':0,
 'admitted_rows':0
}
OUT.mkdir(parents=True,exist_ok=True)
(OUT/'patch_effect_proof_source_plan.json').write_text(json.dumps(plan,indent=2,sort_keys=True)+'\n',encoding='utf-8')
(OUT/'PATCH_EFFECT_PROOF_SOURCE_PLAN_STAGE12283.md').write_text('# Stage12283 Patch Effect Proof Source Plan\n\n'+json.dumps(plan,indent=2)+'\n',encoding='utf-8')
SUMMARY.parent.mkdir(parents=True,exist_ok=True); SUMMARY.write_text(json.dumps(plan,indent=2,sort_keys=True)+'\n',encoding='utf-8')
