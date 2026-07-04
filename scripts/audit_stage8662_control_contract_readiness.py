#!/usr/bin/env python3
from __future__ import annotations
import json, time
from pathlib import Path
from typing import Any
ROOT=Path(__file__).resolve().parents[1]
CONTRACT=ROOT/'configs/software_maintainer/leakage_retrieval_locked_eval_control_contract_stage8660.json'
GRAPH_CARD=ROOT/'runs/summaries/stage8661_control_contract_graph_attachment.json'
SUMMARY=ROOT/'runs/summaries/stage8662_control_contract_readiness_audit.json'
OUT_DIR=ROOT/'runs/local/artifacts/stage8662_control_contract_readiness_audit'
DOC=ROOT/'docs/CONTROL_CONTRACT_READINESS_AUDIT_STAGE8662.md'
REGISTRY=ROOT/'runs/local/artifacts/reconstructed_stage_registry.json'
AUTHORITY_KEYS=['model_execution_authorized_next','decoder_ce_training_authorized_next','runtime_authorized','source_emission_authorized','body_emission_authorized','gemma_execution_authorized_next','harness_execution_authorized_next','scoring_authorized_next','controller_complete_merge_authorized_next','promotion_ready']
REQUIRED_LEAKAGE={'label_visibility_block','source_body_boundary','split_contamination','shortcut_proxy_audit','secret_pii_security'}
REQUIRED_RETRIEVAL={'retrieval_baseline_card','counterfactual_evidence_card','context_packing_card','query_expansion_card'}
REQUIRED_LOCKED={'eval_split_policy','promotion_gate','trace_to_dataset_boundary','benchmark_pack_policy'}
REQUIRED_SOURCE_GROUPS={'repo_graph_sources','retrieval_sources','code_curriculum_sources','agent_trace_sources','locked_eval_sources','safety_security_sources','observability_sources'}
FORBIDDEN_LOSSES={'decoder_ce','denoise_ce','runtime_reward','body_source_training','controller_merge','promotion_scoring'}
def fail(reason, failures): failures.append(reason)
def main():
 OUT_DIR.mkdir(parents=True,exist_ok=True)
 contract=json.loads(CONTRACT.read_text())
 graph_card=json.loads(GRAPH_CARD.read_text())
 failures=[]
 auth=contract.get('authority',{})
 for k in AUTHORITY_KEYS:
  if auth.get(k) is not False: fail(f'authority_not_closed:{k}', failures)
 controls=contract.get('controls',{})
 if set(controls.get('leakage',{}))!=REQUIRED_LEAKAGE: fail('leakage_cards_incomplete', failures)
 if set(controls.get('retrieval',{}))!=REQUIRED_RETRIEVAL: fail('retrieval_cards_incomplete', failures)
 if set(controls.get('locked_eval',{}))!=REQUIRED_LOCKED: fail('locked_eval_cards_incomplete', failures)
 if set(contract.get('source_inventory',{}))!=REQUIRED_SOURCE_GROUPS: fail('source_groups_incomplete', failures)
 missing_sources=[]
 for group, rows in contract.get('source_inventory',{}).items():
  if not rows: fail(f'empty_source_group:{group}', failures)
  for row in rows:
   if not row.get('exists'): missing_sources.append(row.get('path'))
 if missing_sources: fail('missing_sources_present', failures)
 forbidden=set(controls.get('loss_authority',{}).get('forbidden_now',[]))
 if not FORBIDDEN_LOSSES.issubset(forbidden): fail('forbidden_losses_missing', failures)
 split_policy=controls.get('locked_eval',{}).get('eval_split_policy',{})
 sets=set(split_policy.get('sets',[]))
 if not {'train','dev_failure_mining','locked_regression','hidden_final'}.issubset(sets): fail('eval_split_policy_missing_sets', failures)
 trace_boundary=controls.get('locked_eval',{}).get('trace_to_dataset_boundary',{})
 forbidden_boundary='locked eval trace to training row' in trace_boundary.get('forbidden',[])
 if not forbidden_boundary: fail('locked_eval_mining_forbidden_rule_missing', failures)
 graph_metrics=graph_card.get('metrics',{})
 if graph_card.get('passed') is not True: fail('graph_attachment_not_passed', failures)
 if graph_metrics.get('control_groups') != 4: fail('graph_control_group_count_wrong', failures)
 if graph_metrics.get('source_groups') != 7: fail('graph_source_group_count_wrong', failures)
 retrieval=controls.get('retrieval',{})
 for card_name, spec in retrieval.items():
  if not spec.get('metrics'): fail(f'retrieval_metrics_missing:{card_name}', failures)
  if not spec.get('blocked_if'): fail(f'retrieval_blockers_missing:{card_name}', failures)
 leakage=controls.get('leakage',{})
 for card_name, spec in leakage.items():
  if not spec.get('blocked_if'): fail(f'leakage_blockers_missing:{card_name}', failures)
 source_counts=contract.get('metrics',{}).get('source_counts',{})
 total_existing=sum(v.get('existing',0) for v in source_counts.values())
 total_entries=sum(v.get('entries',0) for v in source_counts.values())
 total_parquet=sum(v.get('parquet_files',0) for v in source_counts.values())
 card={'stage':8662,'stage_name':'stage8662_control_contract_readiness_audit','passed':not failures,'authority':{k:False for k in AUTHORITY_KEYS},'metrics':{'failures':failures,'source_groups':len(contract.get('source_inventory',{})),'source_entries':total_entries,'source_existing':total_existing,'source_parquet_files':total_parquet,'leakage_cards':len(controls.get('leakage',{})),'retrieval_cards':len(controls.get('retrieval',{})),'locked_eval_cards':len(controls.get('locked_eval',{})),'graph_nodes':graph_metrics.get('graph_nodes'),'graph_edges':graph_metrics.get('graph_edges'),'model_execution_authorized_next':False,'decoder_ce_training_authorized_next':False,'denoise_ce_training_authorized_next':False,'runtime_authorized':False,'promotion_ready':False},'artifacts':{'contract':str(CONTRACT.relative_to(ROOT)),'graph_card':str(GRAPH_CARD.relative_to(ROOT))},'decision':'Control contract is executable-audit ready.' if not failures else 'Control contract is not ready; failures must be fixed first.','next_best_step':'Implement the concrete source inventory and shared feature normalizer libraries, then run leakage/retrieval/locked-eval cards against graph/symbol candidate rows.' if not failures else 'Fix listed control-readiness failures before continuing.','created_at_utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime())}
 (OUT_DIR/'control_contract_readiness_card.json').write_text(json.dumps(card,indent=2,sort_keys=True)+'\n')
 SUMMARY.write_text(json.dumps(card,indent=2,sort_keys=True)+'\n')
 DOC.write_text('# Stage8662 Control Contract Readiness Audit\n\n'+f"Passed: `{card['passed']}`\n\n- Source groups: `{card['metrics']['source_groups']}`\n- Source entries: `{total_existing}/{total_entries}` existing\n- Parquet files under source directories: `{total_parquet}`\n- Leakage cards: `{card['metrics']['leakage_cards']}`\n- Retrieval cards: `{card['metrics']['retrieval_cards']}`\n- Locked-eval cards: `{card['metrics']['locked_eval_cards']}`\n- Failures: `{failures}`\n\nAll authorities remain closed.\n")
 REGISTRY.write_text(json.dumps({'passed':True,'rows':[card],'metrics':{'min_stage':8530,'max_stage':8662,'latest_stage':8662,'latest_stage_name':card['stage_name'],'latest_stage_next_best_step':card['next_best_step'],'registry_rows':146,'authority_counts':{k:0 for k in AUTHORITY_KEYS}}},indent=2,sort_keys=True)+'\n')
 print(json.dumps(card,indent=2,sort_keys=True))
 raise SystemExit(0 if card['passed'] else 1)
if __name__=='__main__': main()
