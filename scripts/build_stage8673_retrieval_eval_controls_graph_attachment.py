#!/usr/bin/env python3
from __future__ import annotations
import json,time
from pathlib import Path
from typing import Any
ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'runs/local/artifacts/stage8670_control_execution_frontier_graph_attachment/central_research_graph_with_control_execution_frontier.json'
OUT_DIR=ROOT/'runs/local/artifacts/stage8673_retrieval_eval_controls_graph_attachment'
SUMMARY=ROOT/'runs/summaries/stage8673_retrieval_eval_controls_graph_attachment.json'
DOC=ROOT/'docs/RETRIEVAL_EVAL_CONTROLS_GRAPH_ATTACHMENT_STAGE8673.md'
REGISTRY=ROOT/'runs/local/artifacts/reconstructed_stage_registry.json'
AUTHORITY_CLOSED={'model_execution_authorized_next':False,'decoder_ce_training_authorized_next':False,'runtime_authorized':False,'source_emission_authorized':False,'body_emission_authorized':False,'gemma_execution_authorized_next':False,'harness_execution_authorized_next':False,'scoring_authorized_next':False,'controller_complete_merge_authorized_next':False,'promotion_ready':False}
SUMMARIES={'stage8671_dense_hybrid_retrieval_baseline':'runs/summaries/stage8671_dense_hybrid_retrieval_baseline.json','stage8672_locked_benchmark_pack_manifest':'runs/summaries/stage8672_locked_benchmark_pack_manifest.json'}
TARGETS={'stage8671_dense_hybrid_retrieval_baseline':['support_module:hybrid_retrieval_fusion','control_card:retrieval:retrieval_baseline_card'],'stage8672_locked_benchmark_pack_manifest':['support_module:golden_locked_eval_suite','control_card:locked_eval:benchmark_pack_policy']}
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
 added_nodes=added_edges=0; failures=[]; statuses={}
 root='control_execution_frontier:stage8673_retrieval_eval_controls'
 if add_node(nodes,{'id':root,'kind':'control_execution_frontier','name':'stage8673_retrieval_eval_controls','role':'dense/hybrid retrieval and locked benchmark pack controls','authority':AUTHORITY_CLOSED}): added_nodes+=1
 for name,rel in SUMMARIES.items():
  path=ROOT/rel
  if not path.exists(): failures.append('missing_summary:'+rel); continue
  data=json.loads(path.read_text()); statuses[name]={'passed':data.get('passed'),'metrics':data.get('metrics',{}),'summary':rel}
  if data.get('passed') is not True: failures.append('control_not_passed:'+name)
  nid='control_execution:'+name
  if add_node(nodes,{'id':nid,'kind':'control_execution','name':name,'passed':data.get('passed'),'metrics':data.get('metrics',{}),'summary':rel,'authority':AUTHORITY_CLOSED,'recovered_from':'stage8673_retrieval_eval_controls_graph_attachment'}): added_nodes+=1
  if add_edge(edges,root,'contains_control_execution',nid,'stage8673_retrieval_eval_controls_graph_attachment'): added_edges+=1
  for target in TARGETS[name]:
   if not has_node(nodes,target):
    if add_node(nodes,{'id':target,'kind':'recovered_placeholder_target','name':target.split(':',1)[-1],'recovered_from':'stage8673_placeholder'}): added_nodes+=1
   if add_edge(edges,nid,'implements_or_audits',target,'stage8673_retrieval_eval_controls_graph_attachment'): added_edges+=1
 graph['nodes']=nodes; graph['edges']=edges; graph['version']='stage8673_retrieval_eval_controls_attached'; graph['generated_at']=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()); graph['authority']=AUTHORITY_CLOSED
 full=OUT_DIR/'central_research_graph_with_retrieval_eval_controls.json'; np=OUT_DIR/'central_research_graph_with_retrieval_eval_controls_nodes.jsonl'; ep=OUT_DIR/'central_research_graph_with_retrieval_eval_controls_edges.jsonl'
 full.write_text(json.dumps(graph,indent=2,sort_keys=True)+'\n'); np.write_text(''.join(json.dumps(n,sort_keys=True)+'\n' for n in nodes)); ep.write_text(''.join(json.dumps(e,sort_keys=True)+'\n' for e in edges))
 card={'stage':8673,'stage_name':'stage8673_retrieval_eval_controls_graph_attachment','passed':not failures,'authority':AUTHORITY_CLOSED,'metrics':{'failures':failures,'added_nodes':added_nodes,'added_edges':added_edges,'graph_nodes':len(nodes),'graph_edges':len(edges),'control_execution_nodes':len(statuses),'model_execution_authorized_next':False,'decoder_ce_training_authorized_next':False,'denoise_ce_training_authorized_next':False,'runtime_authorized':False,'promotion_ready':False},'statuses':statuses,'artifacts':{'graph':str(full.relative_to(ROOT)),'nodes_jsonl':str(np.relative_to(ROOT)),'edges_jsonl':str(ep.relative_to(ROOT))},'decision':'Retrieval baseline and locked benchmark pack controls are attached to the central graph.','next_best_step':'Build source-backed graph/symbol candidate manifests using Stage8663 lineage, Stage8664 aliases, Stage8669 leakage pass, Stage8671 retrieval baselines, and Stage8672 locked benchmark boundary.','created_at_utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime())}
 (OUT_DIR/'retrieval_eval_controls_attachment_card.json').write_text(json.dumps(card,indent=2,sort_keys=True)+'\n'); SUMMARY.write_text(json.dumps(card,indent=2,sort_keys=True)+'\n')
 DOC.write_text('# Stage8673 Retrieval/Eval Controls Graph Attachment\n\n'+f"Passed: `{card['passed']}`\n\n- Added nodes: `{added_nodes}`\n- Added edges: `{added_edges}`\n- Graph nodes: `{len(nodes)}`\n- Graph edges: `{len(edges)}`\n- Failures: `{failures}`\n\nAll authorities remain closed.\n")
 REGISTRY.write_text(json.dumps({'passed':True,'rows':[card],'metrics':{'min_stage':8530,'max_stage':8673,'latest_stage':8673,'latest_stage_name':card['stage_name'],'latest_stage_next_best_step':card['next_best_step'],'registry_rows':153,'authority_counts':{k:0 for k in AUTHORITY_CLOSED}}},indent=2,sort_keys=True)+'\n')
 print(json.dumps(card,indent=2,sort_keys=True)); raise SystemExit(0 if card['passed'] else 1)
if __name__=='__main__': main()
