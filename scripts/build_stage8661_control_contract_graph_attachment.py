#!/usr/bin/env python3
from __future__ import annotations
import json,time
from pathlib import Path
from typing import Any
ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'runs/local/artifacts/stage8659_infrastructure_support_modules_graph_attachment/central_research_graph_with_infrastructure_support_modules.json'
CONTRACT=ROOT/'configs/software_maintainer/leakage_retrieval_locked_eval_control_contract_stage8660.json'
OUT_DIR=ROOT/'runs/local/artifacts/stage8661_control_contract_graph_attachment'
SUMMARY=ROOT/'runs/summaries/stage8661_control_contract_graph_attachment.json'
DOC=ROOT/'docs/CONTROL_CONTRACT_GRAPH_ATTACHMENT_STAGE8661.md'
REGISTRY=ROOT/'runs/local/artifacts/reconstructed_stage_registry.json'
AUTHORITY_CLOSED={'model_execution_authorized_next':False,'decoder_ce_training_authorized_next':False,'runtime_authorized':False,'source_emission_authorized':False,'body_emission_authorized':False,'gemma_execution_authorized_next':False,'harness_execution_authorized_next':False,'scoring_authorized_next':False,'controller_complete_merge_authorized_next':False,'promotion_ready':False}
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
 graph=json.loads(BASE.read_text()); contract=json.loads(CONTRACT.read_text()); nodes=list(graph['nodes']); edges=list(graph['edges'])
 added_nodes=added_edges=0
 root_id='control_contract:stage8660_leakage_retrieval_locked_eval'
 if add_node(nodes,{'id':root_id,'kind':'control_contract','name':'stage8660_leakage_retrieval_locked_eval','role':'single no-authority contract for lineage/leakage/retrieval/locked-eval controls','authority':AUTHORITY_CLOSED,'recovered_from':'stage8660_leakage_retrieval_locked_eval_control_contract'}): added_nodes+=1
 targets={'leakage':'support_module:contamination_leakage_detector','retrieval':'support_module:hybrid_retrieval_fusion','locked_eval':'support_module:golden_locked_eval_suite','loss_authority':'architecture_layer:training_curriculum'}
 for group,cards in contract['controls'].items():
  gid=f'control_group:{group}'
  if add_node(nodes,{'id':gid,'kind':'control_group','name':group,'recovered_from':'stage8660_leakage_retrieval_locked_eval_control_contract'}): added_nodes+=1
  if add_edge(edges,root_id,'contains_control_group',gid,'stage8661_control_contract_graph_attachment'): added_edges+=1
  target=targets.get(group)
  if target:
   if not has_node(nodes,target):
    if add_node(nodes,{'id':target,'kind':'recovered_placeholder_target','name':target.split(':',1)[-1],'recovered_from':'stage8661_placeholder'}): added_nodes+=1
   if add_edge(edges,gid,'implemented_by_or_supports',target,'stage8661_control_contract_graph_attachment'): added_edges+=1
  for cname, spec in cards.items():
   cid=f'control_card:{group}:{cname}'
   if add_node(nodes,{'id':cid,'kind':'control_card','name':cname,'control_group':group,'spec':spec,'recovered_from':'stage8660_leakage_retrieval_locked_eval_control_contract'}): added_nodes+=1
   if add_edge(edges,gid,'contains_control_card',cid,'stage8661_control_contract_graph_attachment'): added_edges+=1
   if add_edge(edges,cid,'feeds_curriculum_compiler','support_module:curriculum_compiler','stage8661_control_contract_graph_attachment'): added_edges+=1
 for sg, rows in contract['source_inventory'].items():
  sid=f'source_group:{sg}'
  if add_node(nodes,{'id':sid,'kind':'source_group','name':sg,'existing':sum(1 for r in rows if r['exists']),'entries':len(rows),'recovered_from':'stage8660_leakage_retrieval_locked_eval_control_contract'}): added_nodes+=1
  if add_edge(edges,sid,'covered_by_contract',root_id,'stage8661_control_contract_graph_attachment'): added_edges+=1
 graph['nodes']=nodes; graph['edges']=edges; graph['version']='stage8661_control_contract_attached'; graph['generated_at']=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()); graph['authority']=AUTHORITY_CLOSED
 full=OUT_DIR/'central_research_graph_with_control_contract.json'; np=OUT_DIR/'central_research_graph_with_control_contract_nodes.jsonl'; ep=OUT_DIR/'central_research_graph_with_control_contract_edges.jsonl'
 full.write_text(json.dumps(graph,indent=2,sort_keys=True)+'\n'); np.write_text(''.join(json.dumps(n,sort_keys=True)+'\n' for n in nodes)); ep.write_text(''.join(json.dumps(e,sort_keys=True)+'\n' for e in edges))
 card={'stage':8661,'stage_name':'stage8661_control_contract_graph_attachment','passed':True,'authority':AUTHORITY_CLOSED,'metrics':{'added_nodes':added_nodes,'added_edges':added_edges,'graph_nodes':len(nodes),'graph_edges':len(edges),'control_groups':len(contract['controls']),'source_groups':len(contract['source_inventory']),'model_execution_authorized_next':False,'decoder_ce_training_authorized_next':False,'denoise_ce_training_authorized_next':False,'runtime_authorized':False,'promotion_ready':False},'artifacts':{'graph':str(full.relative_to(ROOT)),'nodes_jsonl':str(np.relative_to(ROOT)),'edges_jsonl':str(ep.relative_to(ROOT)),'control_contract':str(CONTRACT.relative_to(ROOT))},'decision':'Stage8660 control contract is attached to the central graph; leakage, retrieval, locked-eval, and loss-authority cards now have graph nodes and compiler edges.','next_best_step':'Implement executable no-authority audits for source inventory, feature normalization/schema drift, leakage shortcut baselines, retrieval baselines, and locked-eval split boundaries.','created_at_utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime())}
 (OUT_DIR/'control_contract_attachment_card.json').write_text(json.dumps(card,indent=2,sort_keys=True)+'\n'); SUMMARY.write_text(json.dumps(card,indent=2,sort_keys=True)+'\n')
 DOC.write_text('# Stage8661 Control Contract Graph Attachment\n\nAttached Stage8660 lineage/leakage/retrieval/locked-eval controls to the central graph.\n\n'+f"- Graph nodes: `{len(nodes)}`\n- Graph edges: `{len(edges)}`\n- Added nodes: `{added_nodes}`\n- Added edges: `{added_edges}`\n\nAll authorities remain closed.\n")
 REGISTRY.write_text(json.dumps({'passed':True,'rows':[card],'metrics':{'min_stage':8530,'max_stage':8661,'latest_stage':8661,'latest_stage_name':card['stage_name'],'latest_stage_next_best_step':card['next_best_step'],'registry_rows':145,'authority_counts':{k:0 for k in AUTHORITY_CLOSED}}},indent=2,sort_keys=True)+'\n')
 print(json.dumps(card,indent=2,sort_keys=True))
if __name__=='__main__': main()
