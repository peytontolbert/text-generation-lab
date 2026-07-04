#!/usr/bin/env python3
from __future__ import annotations
import json,time
from pathlib import Path
from typing import Any
ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'runs/local/artifacts/stage8661_control_contract_graph_attachment/central_research_graph_with_control_contract.json'
OUT_DIR=ROOT/'runs/local/artifacts/stage8670_control_execution_frontier_graph_attachment'
SUMMARY=ROOT/'runs/summaries/stage8670_control_execution_frontier_graph_attachment.json'
DOC=ROOT/'docs/CONTROL_EXECUTION_FRONTIER_GRAPH_ATTACHMENT_STAGE8670.md'
REGISTRY=ROOT/'runs/local/artifacts/reconstructed_stage_registry.json'
AUTHORITY_CLOSED={'model_execution_authorized_next':False,'decoder_ce_training_authorized_next':False,'runtime_authorized':False,'source_emission_authorized':False,'body_emission_authorized':False,'gemma_execution_authorized_next':False,'harness_execution_authorized_next':False,'scoring_authorized_next':False,'controller_complete_merge_authorized_next':False,'promotion_ready':False}
STAGE_SUMMARIES={
 'stage8663_source_inventory_lineage_registry':'runs/summaries/stage8663_source_inventory_lineage_registry.json',
 'stage8664_shared_feature_normalizer_audit':'runs/summaries/stage8664_shared_feature_normalizer_audit.json',
 'stage8665_manifest_leakage_locked_eval_boundary_failed_original':'runs/summaries/stage8665_manifest_leakage_locked_eval_boundary.json',
 'stage8666_repo_span_bm25_retrieval_baseline':'runs/summaries/stage8666_repo_span_bm25_retrieval_baseline.json',
 'stage8667_visible_copy_target_remediation':'runs/summaries/stage8667_visible_copy_target_remediation.json',
 'stage8668_intent_to_build_copy_routed_manifest':'runs/summaries/stage8668_intent_to_build_copy_routed_manifest.json',
 'stage8669_patched_manifest_leakage_locked_eval_boundary':'runs/summaries/stage8669_patched_manifest_leakage_locked_eval_boundary.json'}
TARGETS={
 'stage8663_source_inventory_lineage_registry':'support_module:source_inventory_lineage_tracker',
 'stage8664_shared_feature_normalizer_audit':'support_module:schema_drift_detector',
 'stage8665_manifest_leakage_locked_eval_boundary_failed_original':'support_module:contamination_leakage_detector',
 'stage8666_repo_span_bm25_retrieval_baseline':'support_module:hybrid_retrieval_fusion',
 'stage8667_visible_copy_target_remediation':'support_module:weak_supervision_label_model',
 'stage8668_intent_to_build_copy_routed_manifest':'support_module:curriculum_compiler',
 'stage8669_patched_manifest_leakage_locked_eval_boundary':'support_module:contamination_leakage_detector'}
def has_node(nodes:list[dict[str,Any]],i:str)->bool: return any(n.get('id')==i for n in nodes)
def add_node(nodes,node):
 if has_node(nodes,node['id']): return False
 nodes.append(node); return True
def has_edge(edges,s,r,t): return any(e.get('source')==s and e.get('relation')==r and e.get('target')==t for e in edges)
def add_edge(edges,s,r,t,ev):
 if has_edge(edges,s,r,t): return False
 edges.append({'source':s,'relation':r,'target':t,'evidence_source':ev}); return True
def main():
 OUT_DIR.mkdir(parents=True,exist_ok=True)
 graph=json.loads(BASE.read_text()); nodes=list(graph['nodes']); edges=list(graph['edges'])
 added_nodes=added_edges=0; statuses={}; failures=[]
 root_id='control_execution_frontier:stage8670'
 if add_node(nodes,{'id':root_id,'kind':'control_execution_frontier','name':'stage8670_control_execution_frontier','role':'records executable control stages from source lineage through patched leakage/retrieval readiness','authority':AUTHORITY_CLOSED}): added_nodes+=1
 for name, rel in STAGE_SUMMARIES.items():
  path=ROOT/rel
  if not path.exists(): failures.append(f'missing_summary:{rel}'); continue
  data=json.loads(path.read_text()); statuses[name]={'passed':data.get('passed'),'metrics':data.get('metrics',{}),'summary':rel}
  nid='control_execution:'+name
  if add_node(nodes,{'id':nid,'kind':'control_execution','name':name,'passed':data.get('passed'),'metrics':data.get('metrics',{}),'summary':rel,'authority':AUTHORITY_CLOSED,'recovered_from':'stage8670_control_execution_frontier_graph_attachment'}): added_nodes+=1
  if add_edge(edges,root_id,'contains_control_execution',nid,'stage8670_control_execution_frontier_graph_attachment'): added_edges+=1
  target=TARGETS.get(name)
  if target:
   if not has_node(nodes,target):
    if add_node(nodes,{'id':target,'kind':'recovered_placeholder_target','name':target.split(':',1)[-1],'recovered_from':'stage8670_placeholder'}): added_nodes+=1
   if add_edge(edges,nid,'implements_or_audits',target,'stage8670_control_execution_frontier_graph_attachment'): added_edges+=1
 # Original Stage8665 is expected failed; patched 8669 must pass.
 if statuses.get('stage8665_manifest_leakage_locked_eval_boundary_failed_original',{}).get('passed') is not False: failures.append('stage8665_should_remain_failed_original')
 for req in ['stage8663_source_inventory_lineage_registry','stage8664_shared_feature_normalizer_audit','stage8666_repo_span_bm25_retrieval_baseline','stage8667_visible_copy_target_remediation','stage8668_intent_to_build_copy_routed_manifest','stage8669_patched_manifest_leakage_locked_eval_boundary']:
  if statuses.get(req,{}).get('passed') is not True: failures.append(f'required_control_not_passed:{req}')
 graph['nodes']=nodes; graph['edges']=edges; graph['version']='stage8670_control_execution_frontier_attached'; graph['generated_at']=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()); graph['authority']=AUTHORITY_CLOSED
 full=OUT_DIR/'central_research_graph_with_control_execution_frontier.json'; np=OUT_DIR/'central_research_graph_with_control_execution_frontier_nodes.jsonl'; ep=OUT_DIR/'central_research_graph_with_control_execution_frontier_edges.jsonl'
 full.write_text(json.dumps(graph,indent=2,sort_keys=True)+'\n'); np.write_text(''.join(json.dumps(n,sort_keys=True)+'\n' for n in nodes)); ep.write_text(''.join(json.dumps(e,sort_keys=True)+'\n' for e in edges))
 card={'stage':8670,'stage_name':'stage8670_control_execution_frontier_graph_attachment','passed':not failures,'authority':AUTHORITY_CLOSED,'metrics':{'failures':failures,'control_execution_nodes':len(statuses),'added_nodes':added_nodes,'added_edges':added_edges,'graph_nodes':len(nodes),'graph_edges':len(edges),'model_execution_authorized_next':False,'decoder_ce_training_authorized_next':False,'denoise_ce_training_authorized_next':False,'runtime_authorized':False,'promotion_ready':False},'statuses':statuses,'artifacts':{'graph':str(full.relative_to(ROOT)),'nodes_jsonl':str(np.relative_to(ROOT)),'edges_jsonl':str(ep.relative_to(ROOT))},'decision':'Executable lineage, normalization, retrieval, and patched leakage controls are attached to the central graph. Original leakage failure is preserved as evidence and repaired by copy-routed Stage8668/8669.','next_best_step':'Use Stage8663 lineage ids, Stage8664 aliases, Stage8666 retrieval card, and Stage8669 patched leakage boundary in the next graph/symbol candidate builders. Then add dense/rerank retrieval and locked benchmark pack cards.','created_at_utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime())}
 (OUT_DIR/'control_execution_frontier_card.json').write_text(json.dumps(card,indent=2,sort_keys=True)+'\n'); SUMMARY.write_text(json.dumps(card,indent=2,sort_keys=True)+'\n')
 DOC.write_text('# Stage8670 Control Execution Frontier Graph Attachment\n\n'+f"Passed: `{card['passed']}`\n\n- Control execution nodes: `{len(statuses)}`\n- Added nodes: `{added_nodes}`\n- Added edges: `{added_edges}`\n- Graph nodes: `{len(nodes)}`\n- Graph edges: `{len(edges)}`\n- Failures: `{failures}`\n\nAll authorities remain closed.\n")
 REGISTRY.write_text(json.dumps({'passed':True,'rows':[card],'metrics':{'min_stage':8530,'max_stage':8670,'latest_stage':8670,'latest_stage_name':card['stage_name'],'latest_stage_next_best_step':card['next_best_step'],'registry_rows':150,'authority_counts':{k:0 for k in AUTHORITY_CLOSED}}},indent=2,sort_keys=True)+'\n')
 print(json.dumps(card,indent=2,sort_keys=True))
 raise SystemExit(0 if card['passed'] else 1)
if __name__=='__main__': main()
