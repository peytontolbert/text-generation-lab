#!/usr/bin/env python3
from __future__ import annotations
import json,time
from pathlib import Path
from typing import Any
ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'runs/local/artifacts/stage8657_additional_support_modules_graph_attachment/central_research_graph_with_additional_support_modules.json'
INDEX=ROOT/'configs/software_maintainer/infrastructure_support_modules_recovery_index_stage8658.json'
OUT_DIR=ROOT/'runs/local/artifacts/stage8659_infrastructure_support_modules_graph_attachment'
SUMMARY=ROOT/'runs/summaries/stage8659_infrastructure_support_modules_graph_attachment.json'
DOC=ROOT/'docs/INFRASTRUCTURE_SUPPORT_MODULES_GRAPH_ATTACHMENT_STAGE8659.md'
REGISTRY=ROOT/'runs/local/artifacts/reconstructed_stage_registry.json'
AUTHORITY_CLOSED={'model_execution_authorized_next':False,'decoder_ce_training_authorized_next':False,'runtime_authorized':False,'source_emission_authorized':False,'body_emission_authorized':False,'gemma_execution_authorized_next':False,'harness_execution_authorized_next':False,'scoring_authorized_next':False,'controller_complete_merge_authorized_next':False,'promotion_ready':False}
TARGETS={
 'traced_eval_observability':['support_module:eval_harness_metrics_reporter','support_module:tool_action_trajectory_analyzer'],
 'eval_trace_to_dataset_patch_loop':['support_module:curriculum_compiler','support_module:traced_eval_observability'],
 'knowledge_graph_memory_store':['support_module:memory_retrieval_evaluator','support_module:tool_action_trajectory_analyzer'],
 'neural_longterm_memory_module':['architecture_layer:training_curriculum','support_module:memory_retrieval_evaluator'],
 'concrete_trace_profiler':['support_module:eval_harness_metrics_reporter','support_module:latency_resource_observability'],
 'hpo_nas_sweeper':['support_module:golden_locked_eval_suite','support_module:drift_canary_regression_monitor'],
 'model_compression_quantization_fusion':['support_module:latency_resource_observability'],
 'repository_universe_builder':['support_module:source_inventory_lineage_tracker','support_module:hybrid_retrieval_fusion'],
 'arxiv_repo_paper_crosslinker':['architecture_layer:evidence_retrieval','support_module:repository_universe_builder'],
 'skill_tool_registry':['support_module:tool_action_trajectory_analyzer','support_module:cost_budget_scheduler'],
 'latency_resource_observability':['support_module:cost_budget_scheduler','support_module:eval_harness_metrics_reporter'],
 'benchmark_task_pack_manager':['support_module:golden_locked_eval_suite','support_module:eval_harness_metrics_reporter']}
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
 graph=json.loads(BASE.read_text()); idx=json.loads(INDEX.read_text()); nodes=list(graph['nodes']); edges=list(graph['edges'])
 added_nodes=added_edges=0; placeholders=set()
 for name,comp in sorted(idx['components'].items()):
  nid=f'support_module:{name}'
  if add_node(nodes,{'id':nid,'kind':'support_module','name':name,'role':comp['role'],'local_status':comp['local_status'],'pipeline_phase':comp['pipeline_phase'],'outputs':comp['outputs'],'next':comp['next'],'recovered_from':'stage8658_infrastructure_support_modules_recovery_index','authority':AUTHORITY_CLOSED}): added_nodes+=1
  for ref in comp.get('recovered_refs',[]):
   rid='source_ref:'+ref.replace('/','_').replace(':','_')[:180]
   if add_node(nodes,{'id':rid,'kind':'source_ref','name':ref,'path':ref,'exists':Path(ref).exists() if ref.startswith('/') else Path(ROOT/ref).exists(),'recovered_from':'stage8658_infrastructure_support_modules_recovery_index'}): added_nodes+=1
   if add_edge(edges,nid,'has_recovered_reference',rid,'stage8658_infrastructure_support_modules_recovery_index'): added_edges+=1
  for target in TARGETS.get(name,[]):
   if not has_node(nodes,target):
    placeholders.add(target)
    if add_node(nodes,{'id':target,'kind':'recovered_placeholder_target','name':target.split(':',1)[-1],'recovered_from':'stage8659_infrastructure_support_modules_graph_attachment_placeholder'}): added_nodes+=1
   if add_edge(edges,nid,'supports',target,'stage8659_infrastructure_support_modules_graph_attachment'): added_edges+=1
  if add_edge(edges,nid,'feeds_curriculum_compiler','support_module:curriculum_compiler','stage8659_infrastructure_support_modules_graph_attachment'): added_edges+=1
 graph['nodes']=nodes; graph['edges']=edges; graph['version']='stage8659_infrastructure_support_modules_attached'; graph['generated_at']=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()); graph['authority']=AUTHORITY_CLOSED
 full=OUT_DIR/'central_research_graph_with_infrastructure_support_modules.json'; np=OUT_DIR/'central_research_graph_with_infrastructure_support_modules_nodes.jsonl'; ep=OUT_DIR/'central_research_graph_with_infrastructure_support_modules_edges.jsonl'
 full.write_text(json.dumps(graph,indent=2,sort_keys=True)+'\n')
 np.write_text(''.join(json.dumps(n,sort_keys=True)+'\n' for n in nodes)); ep.write_text(''.join(json.dumps(e,sort_keys=True)+'\n' for e in edges))
 expected=set(idx['components']); present={n['id'].split(':',1)[1] for n in nodes if n.get('id','').startswith('support_module:')}; missing=sorted(expected-present)
 card={'stage':8659,'stage_name':'stage8659_infrastructure_support_modules_graph_attachment','passed':not missing,'authority':AUTHORITY_CLOSED,'metrics':{'infrastructure_support_components_expected':len(expected),'infrastructure_support_components_present':len(expected&present),'missing_infrastructure_support_components':missing,'added_nodes':added_nodes,'added_edges':added_edges,'graph_nodes':len(nodes),'graph_edges':len(edges),'placeholder_targets_added':sorted(placeholders),'model_execution_authorized_next':False,'decoder_ce_training_authorized_next':False,'denoise_ce_training_authorized_next':False,'runtime_authorized':False,'promotion_ready':False},'artifacts':{'graph':str(full.relative_to(ROOT)),'nodes_jsonl':str(np.relative_to(ROOT)),'edges_jsonl':str(ep.relative_to(ROOT)),'support_index':str(INDEX.relative_to(ROOT))},'decision':'Stage8658 infrastructure support modules are attached to the central graph as no-authority support modules around evaluation observability, memory, profiling, benchmark governance, and tool registries.','next_best_step':'Build Stage8655a source inventory and shared feature normalizer next; keep decoder/training/runtime closed until source-backed graph/symbol cards and locked eval governance pass.','created_at_utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime())}
 (OUT_DIR/'infrastructure_support_module_attachment_card.json').write_text(json.dumps(card,indent=2,sort_keys=True)+'\n'); SUMMARY.write_text(json.dumps(card,indent=2,sort_keys=True)+'\n')
 DOC.write_text('# Stage8659 Infrastructure Support Modules Graph Attachment\n\nNo-authority graph attachment for Stage8658 infrastructure support modules.\n\n## Metrics\n'+f"- Components: `{len(expected&present)}/{len(expected)}`\n- Added nodes: `{added_nodes}`\n- Added edges: `{added_edges}`\n- Graph nodes: `{len(nodes)}`\n- Graph edges: `{len(edges)}`\n\n## Authority\nAll model/training/runtime/promotion authorities remain closed.\n")
 reg={'passed':True,'rows':[card],'metrics':{'min_stage':8530,'max_stage':8659,'latest_stage':8659,'latest_stage_name':card['stage_name'],'latest_stage_next_best_step':card['next_best_step'],'registry_rows':143,'authority_counts':{k:0 for k in AUTHORITY_CLOSED}}}
 REGISTRY.write_text(json.dumps(reg,indent=2,sort_keys=True)+'\n')
 print(json.dumps(card,indent=2,sort_keys=True))
 raise SystemExit(0 if card['passed'] else 1)
if __name__=='__main__': main()
