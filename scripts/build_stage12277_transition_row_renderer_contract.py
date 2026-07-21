#!/usr/bin/env python3
"""Build Stage12277 transition-row renderer contract for train-support repairs."""
from __future__ import annotations
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
STAGE='stage12277_transition_row_renderer_contract'
OUT=ROOT/f'runs/local/artifacts/{STAGE}'
SUMMARY=ROOT/f'runs/summaries/{STAGE}.json'

contract={
  'stage':STAGE,
  'decision':'renderer_contract_ready_no_rows_rendered',
  'input_stage':'stage12276_semantic_review_result_ingest',
  'allowed_inputs':'only rows with train_support_allowed=true and strict_eval_eligible=false',
  'forbidden_inputs':['quarantine rows','split_required rows','external_comparable_countable=false rows as eval','any row missing required fields'],
  'required_transition_fields':[
    'root_lineage_key','split_group_id','repo_family_label','language_family','source_refs',
    'state_before_ref','state_before_summary_codes','candidate_action_set','chosen_action',
    'observation_status_refs','patch_ref_digest','state_delta_codes','stop_continue_label',
    'verifier_transition_label','review_decision','semantic_relevance_flags'
  ],
  'visibility_masks':{
    'pre_action_model_input':['state_before_ref','state_before_summary_codes','candidate_action_set','repo_family_label','language_family'],
    'target_only':['chosen_action','observation_status_refs','state_delta_codes','stop_continue_label','verifier_transition_label'],
    'never_emit':['raw_tool_output','raw_tool_arguments','raw_patch_body','raw_source_path','full_command_text']
  },
  'row_types_to_emit':['transition_next_action_train_support','transition_verifier_transition_train_support','transition_continue_or_stop_train_support'],
  'row_types_blocked':['patch_generation','strict_eval','source_heldout_eval','external_comparable_repair_claim'],
  'anti_shortcut_requirements':[
    'opaque option labels shuffled at render time',
    'semantic target stored separately from label',
    'no target status text in pre-action input',
    'self_research rows marked dev_only',
    'external smoke rows marked train_support_only_not_comparable'
  ],
  'minimum_acceptance_before_render':{
    'input_train_support_rows_min':1,
    'quarantine_rows_rendered':0,
    'raw_content_emitted':False,
    'all_required_fields_present':True,
    'all_visibility_masks_present':True
  },
  'next_stage':'stage12278_transition_row_renderer_preflight'
}
OUT.mkdir(parents=True,exist_ok=True)
(OUT/'transition_row_renderer_contract.json').write_text(json.dumps(contract,indent=2,sort_keys=True)+'\n',encoding='utf-8')
(OUT/'TRANSITION_ROW_RENDERER_CONTRACT_STAGE12277.md').write_text('# Stage12277 Transition Row Renderer Contract\n\n'+json.dumps(contract,indent=2)+'\n',encoding='utf-8')
SUMMARY.parent.mkdir(parents=True,exist_ok=True)
SUMMARY.write_text(json.dumps(contract,indent=2,sort_keys=True)+'\n',encoding='utf-8')
