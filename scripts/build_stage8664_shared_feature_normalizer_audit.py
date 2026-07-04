#!/usr/bin/env python3
from __future__ import annotations
import json,time
from pathlib import Path
from typing import Any
ROOT=Path(__file__).resolve().parents[1]
OUT_DIR=ROOT/'runs/local/artifacts/stage8664_shared_feature_normalizer_audit'
SUMMARY=ROOT/'runs/summaries/stage8664_shared_feature_normalizer_audit.json'
DOC=ROOT/'docs/SHARED_FEATURE_NORMALIZER_AUDIT_STAGE8664.md'
CONFIG=ROOT/'configs/software_maintainer/shared_feature_normalizer_stage8664.json'
AUTHORITY_CLOSED={'model_execution_authorized_next':False,'decoder_ce_training_authorized_next':False,'runtime_authorized':False,'source_emission_authorized':False,'body_emission_authorized':False,'gemma_execution_authorized_next':False,'harness_execution_authorized_next':False,'scoring_authorized_next':False,'controller_complete_merge_authorized_next':False,'promotion_ready':False}
MANIFESTS=[
 'runs/local/artifacts/stage8630_intent_to_build_neutral_manifest/intent_to_build_neutral_manifest.jsonl',
 'runs/local/artifacts/stage8636_edit_localization_neutral_manifest/edit_localization_neutral_manifest.jsonl',
 'runs/local/artifacts/stage8638_patch_operator_neutral_manifest/patch_operator_neutral_manifest.jsonl',
 'runs/local/artifacts/stage8643_verifier_repair_neutral_manifest/verifier_repair_neutral_manifest.jsonl',
 'runs/local/artifacts/stage8645_bounded_decoder_arguments_neutral_manifest/bounded_decoder_arguments_neutral_manifest.jsonl',
 'runs/local/artifacts/stage8647_output_repair_denoise_neutral_manifest/output_repair_denoise_neutral_manifest.jsonl',
 'runs/local/artifacts/stage8618_symbol_binding_counterfactual_with_test_patch/combined_symbol_binding_candidates.jsonl',
]
ALIASES={
 'row_id':['row_id'], 'split':['split'], 'objective_family':['objective_family','corrupted_state.task_family'], 'route':['route','judge_route_card.route','target.label'], 'semantic_key':['semantic_key'],
 'language':['corrupted_state.language','graph_input.nodes[].features.language_family'], 'file_extension':['corrupted_state.file_extension'], 'source_stage':['source_stage'],
 'decoder_budget_ok':['corrupted_state.budget.decoder_budget_ok','judge_route_card.features.decoder_budget_ok'], 'decode_allowed':['judge_route_card.features.decode_allowed'],
 'missing_evidence':['judge_route_card.features.missing_evidence','corrupted_state.repo_state.missing_context_signal'], 'target_tokens':['judge_route_card.features.target_tokens'],
 'encoder_has_internal_token':['judge_route_card.features.encoder_has_internal_token'], 'target_has_internal_token':['judge_route_card.features.target_has_internal_token'], 'target_text_copied_in_encoder':['judge_route_card.features.target_text_copied_in_encoder'],
 'evidence_text':['corrupted_state.available_evidence','corrupted_state.repair_signal','corrupted_state.verifier_feedback','corrupted_state.candidate_surface'],
 'import_state':['corrupted_state.import_state'], 'allowed_repository_visible':['corrupted_state.repo_state.allowed_repository_visible'], 'blocked_dependency_signal':['corrupted_state.repo_state.blocked_dependency_signal'],
 'graph_id':['graph_input.graph_id'], 'query_kind':['graph_input.query_kind','query.query_kind'], 'query_node_id':['query.query_node_id'], 'node_type':['graph_input.nodes[].node_type'], 'edge_type':['graph_input.edges[].edge_type'],
 'degree_bucket':['graph_input.nodes[].features.degree_bucket'], 'import_count_bucket':['graph_input.nodes[].features.import_count_bucket'], 'definition_count_bucket':['graph_input.nodes[].features.definition_count_bucket'], 'call_count_bucket':['graph_input.nodes[].features.call_count_bucket'], 'path_depth_bucket':['graph_input.nodes[].features.path_depth_bucket'],
 'source_file_is_test':['query.features.source_file_is_test','graph_input.nodes[].features.is_test'], 'source_ref_path':['source_ref.path'], 'source_ref_corpus':['source_ref.corpus'],
 'authority_model_execution':['authority.model_execution_authorized_next','authority.training_authorized'], 'authority_decoder_ce':['authority.decoder_ce_training_authorized_next','authority.decoder_ce_authorized'], 'authority_runtime':['authority.runtime_authorized'], 'authority_source_emission':['authority.source_emission_authorized'], 'authority_body_emission':['authority.body_emission_authorized'],
 'loss_decoder_ce':['loss_mask.decoder_ce'], 'loss_denoise_ce':['loss_mask.denoise_ce'], 'loss_runtime_reward':['loss_mask.runtime_reward'], 'loss_symbol_binding_ce':['loss_mask.symbol_binding_ce'], 'loss_action_sequence_ce':['loss_mask.action_sequence_ce'], 'loss_file_plan_ce':['loss_mask.file_plan_ce'],
}
FORBIDDEN_TRUE={'authority_model_execution','authority_decoder_ce','authority_runtime','authority_source_emission','authority_body_emission','loss_decoder_ce','loss_denoise_ce','loss_runtime_reward'}
def values_at(obj:Any, path:str)->list[Any]:
 parts=path.split('.')
 cur=[obj]
 for part in parts:
  nxt=[]
  arr=part.endswith('[]'); key=part[:-2] if arr else part
  for item in cur:
   if isinstance(item,dict) and key in item:
    val=item[key]
    if arr and isinstance(val,list): nxt.extend(val)
    else: nxt.append(val)
   elif isinstance(item,list):
    for x in item:
     if isinstance(x,dict) and key in x:
      val=x[key]
      if arr and isinstance(val,list): nxt.extend(val)
      else: nxt.append(val)
  cur=nxt
  if not cur: break
 return cur
def first(obj:Any, paths:list[str])->Any:
 vals=[]
 for p in paths: vals.extend(values_at(obj,p))
 if not vals: return None
 if len(vals)==1: return vals[0]
 return vals
def normalize(row:dict[str,Any])->dict[str,Any]:
 return {canon:first(row,paths) for canon,paths in ALIASES.items()}
def main():
 OUT_DIR.mkdir(parents=True,exist_ok=True)
 failures=[]; per=[]; normalized_samples=[]; alias_hits={k:0 for k in ALIASES}; rows_total=0; old_authority_alias_hits=0
 for rel in MANIFESTS:
  path=ROOT/rel
  stats={'manifest':rel,'exists':path.exists(),'rows':0,'normalized_rows':0,'forbidden_true_rows':0,'missing_core_rows':0,'alias_hits':{}}
  if not path.exists(): failures.append(f'missing_manifest:{rel}'); per.append(stats); continue
  for line in path.open():
   if not line.strip(): continue
   row=json.loads(line); rows_total+=1; stats['rows']+=1
   norm=normalize(row); stats['normalized_rows']+=1
   if len(normalized_samples)<80: normalized_samples.append({'manifest':rel,'row_id':row.get('row_id'), 'normalized':norm})
   for canon,paths in ALIASES.items():
    if norm.get(canon) is not None:
     alias_hits[canon]+=1; stats['alias_hits'][canon]=stats['alias_hits'].get(canon,0)+1
   if values_at(row,'authority.decoder_ce_authorized') or values_at(row,'authority.training_authorized'): old_authority_alias_hits+=1
   for key in FORBIDDEN_TRUE:
    v=norm.get(key)
    if v is True or (isinstance(v,list) and any(x is True for x in v)):
     stats['forbidden_true_rows']+=1
   if not norm.get('row_id') or not norm.get('split') or not norm.get('objective_family'):
    stats['missing_core_rows']+=1
  if stats['forbidden_true_rows']: failures.append(f'forbidden_true:{rel}:{stats["forbidden_true_rows"]}')
  if stats['missing_core_rows']: failures.append(f'missing_core:{rel}:{stats["missing_core_rows"]}')
  per.append(stats)
 missing_aliases=[k for k,v in alias_hits.items() if v==0 and k not in {'degree_bucket'}]
 if rows_total==0: failures.append('no_rows_seen')
 contract={'stage':8664,'stage_name':'stage8664_shared_feature_normalizer_audit','passed':not failures,'authority':AUTHORITY_CLOSED,'aliases':ALIASES,'manifests':MANIFESTS,'per_manifest':per,'metrics':{'rows_total':rows_total,'manifests':len(MANIFESTS),'alias_count':len(ALIASES),'alias_hits':alias_hits,'missing_aliases':missing_aliases,'old_authority_alias_hits':old_authority_alias_hits,'failures':failures,'model_execution_authorized_next':False,'decoder_ce_training_authorized_next':False,'denoise_ce_training_authorized_next':False,'runtime_authorized':False,'promotion_ready':False},'decision':'Shared feature normalizer covers recovered manifests without reopening forbidden authority/loss paths.' if not failures else 'Shared feature normalizer failed; fix failures before use.','next_best_step':'Use this alias map in graph/symbol builders and add a hard schema-drift audit for every new manifest.','created_at_utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime())}
 CONFIG.write_text(json.dumps(contract,indent=2,sort_keys=True)+'\n')
 SUMMARY.write_text(json.dumps(contract,indent=2,sort_keys=True)+'\n')
 (OUT_DIR/'shared_feature_normalizer.json').write_text(json.dumps(contract,indent=2,sort_keys=True)+'\n')
 with (OUT_DIR/'normalized_sample_rows.jsonl').open('w') as f:
  for r in normalized_samples: f.write(json.dumps(r,sort_keys=True)+'\n')
 lines=['# Stage8664 Shared Feature Normalizer Audit','','Canonical alias map and schema-drift audit over recovered manifests.','','## Metrics']
 for k,v in contract['metrics'].items():
  if k!='alias_hits': lines.append(f'- `{k}`: `{v}`')
 lines += ['','## Boundary','Forbidden authority/loss paths must remain false: `decoder_ce`, `denoise_ce`, `runtime_reward`, model/runtime/source/body authorities.']
 DOC.write_text('\n'.join(lines)+'\n')
 print(json.dumps(contract,indent=2,sort_keys=True))
 raise SystemExit(0 if contract['passed'] else 1)
if __name__=='__main__': main()
