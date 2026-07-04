#!/usr/bin/env python3
from __future__ import annotations
import json, time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'configs/software_maintainer/infrastructure_support_modules_recovery_index_stage8658.json'
SUMMARY=ROOT/'runs/summaries/stage8658_infrastructure_support_modules_recovery_index.json'
DOC=ROOT/'docs/INFRASTRUCTURE_SUPPORT_MODULES_RECOVERY_INDEX_STAGE8658.md'
AUTHORITY_CLOSED={
 'model_execution_authorized_next':False,'decoder_ce_training_authorized_next':False,'runtime_authorized':False,
 'source_emission_authorized':False,'body_emission_authorized':False,'gemma_execution_authorized_next':False,
 'harness_execution_authorized_next':False,'scoring_authorized_next':False,'controller_complete_merge_authorized_next':False,'promotion_ready':False}
COMPONENTS={
 'traced_eval_observability':{
  'pipeline_phase':'evaluation_observability','role':'Capture structured eval spans, tool calls, inputs, outputs, and metric attribution so failures compile into dataset patches instead of narrative notes.',
  'outputs':['trace_id','span_tree','metric_events','failure_packet','dataset_patch_link'],'local_status':'reference_recovered_not_integrated',
  'recovered_refs':['/arxiv/repositories/deepeval/deepeval/tracing/trace_context.py','/arxiv/repositories/deepeval/deepeval/tracing/trace_test_manager.py','/arxiv/repositories/deepeval/skills/deepeval-tracing/LICENSE'],
  'next':'Define a trace schema shared by dataset judge, eval harness, and curriculum compiler.'},
 'eval_trace_to_dataset_patch_loop':{
  'pipeline_phase':'curriculum_compiler','role':'Convert observed eval traces and failures into auditable add/remove/relabel/rebalance dataset operations.',
  'outputs':['failure_cluster','dataset_operation','source_failures','expected_metric_delta','patch_status'],'local_status':'missing_as_first_class_loop',
  'recovered_refs':['/arxiv/repositories/deepeval/docs/public/img/confident-trace-to-dataset.png','/arxiv/repositories/deepeval/deepeval/dataset/test_run_tracer.py'],
  'next':'Add dataset_patch records to every failure-cluster resolution stage.'},
 'knowledge_graph_memory_store':{
  'pipeline_phase':'agent_memory','role':'Persist skills, source facts, tool outcomes, and repo entities as typed graph memories with retrieval/update semantics.',
  'outputs':['memory_node','memory_edge','entity_id','relationship_type','retrieval_path'],'local_status':'reference_recovered_not_integrated',
  'recovered_refs':['/arxiv/repositories/modelcontextprotocol__servers/src/memory/index.ts','/arxiv/repositories/modelcontextprotocol__servers/src/memory/README.md','/arxiv/repositories/modelcontextprotocol__servers/src/memory/__tests__/knowledge-graph.test.ts'],
  'next':'Bind central graph nodes to durable memory keys before trace-mined skill promotion.'},
 'neural_longterm_memory_module':{
  'pipeline_phase':'model_architecture','role':'Explore compressed long-horizon state/memory modules that can summarize repo/task history before bounded attention decoding.',
  'outputs':['memory_state','retrieval_state','compression_loss','staleness_score'],'local_status':'concept_recovered_not_current_architecture',
  'recovered_refs':['/arxiv/repositories/titans-pytorch/titans_pytorch/neural_memory.py','/arxiv/repositories/titans-pytorch/titans_pytorch/memory_models.py'],
  'next':'Keep as V2.8+ architecture track after source-backed transition objectives are stable.'},
 'concrete_trace_profiler':{
  'pipeline_phase':'model_interpretability_and_runtime','role':'Trace model/tool computation graphs and resource use to catch shape/device/control-flow mistakes and expensive paths.',
  'outputs':['op_trace','shape_trace','flop_count','resource_hotspot','failure_site'],'local_status':'reference_recovered_not_integrated',
  'recovered_refs':['/arxiv/repositories/nni/nni/common/concrete_trace_utils/concrete_tracer.py','/arxiv/repositories/nni/nni/common/concrete_trace_utils/flop_utils.py','/arxiv/repositories/cutlass/include/cutlass/trace.h'],
  'next':'Use for trainer/probe debug once model execution is authorized, not before.'},
 'hpo_nas_sweeper':{
  'pipeline_phase':'training_engineering','role':'Track controlled hyperparameter and architecture sweeps under reproducible benchmark cards rather than ad hoc stage changes.',
  'outputs':['sweep_id','trial_config','metric_delta','selected_config','rejected_config_reason'],'local_status':'reference_recovered_not_integrated',
  'recovered_refs':['/arxiv/repositories/nni/nni/nas/benchmark/evaluator.py','/arxiv/repositories/nni/docs/source/hpo/hpo_benchmark.rst','/arxiv/repositories/nni/examples/nas/benchmarks/nasbench201.sh'],
  'next':'Only enable after locked eval/canary monitor exists.'},
 'model_compression_quantization_fusion':{
  'pipeline_phase':'deployment_efficiency','role':'Recover quantization/fusion/compression references for small-model deployment after correctness gates pass.',
  'outputs':['quantization_mode','fusion_pattern','latency_delta','accuracy_delta'],'local_status':'future_efficiency_track',
  'recovered_refs':['/arxiv/repositories/nni/docs/source/compression/fusion_compress.rst','/arxiv/repositories/cutlass/examples/13_two_tensor_op_fusion/README.md','/arxiv/repositories/cutlass/examples/37_gemm_layernorm_gemm_fusion/gemm_layernorm.cu'],
  'next':'Do not optimize deployment until transition/data gates stop failing.'},
 'repository_universe_builder':{
  'pipeline_phase':'source_ingestion','role':'Build heterogeneous repo/file/symbol embeddings, graph edges, and repo similarity for source-backed curriculum sampling.',
  'outputs':['repo_vector','entity_embedding','repo_knn_edge','universe_manifest'],'local_status':'session_recovered_concept_needs_rebuild',
  'recovered_refs':['/home/peyton/.codex/sessions/2025/11/26/rollout-2025-11-26T00-55-44-019abda8-c0d8-7803-8a77-1e0fcf0dc577.jsonl','/arxiv/TOLBERT_BRAIN/scripts/repo_graph.py','/arxiv/TOLBERT_BRAIN/modules/program_graph.py'],
  'next':'Rebuild as source inventory extension after Stage8655a.'},
 'arxiv_repo_paper_crosslinker':{
  'pipeline_phase':'knowledge_retrieval','role':'Link repos, papers, model concepts, and implementation references in one retrieval space for training-data/source discovery.',
  'outputs':['paper_repo_similarity','paper_cluster','related_repo','concept_source_link'],'local_status':'session_recovered_concept_needs_rebuild',
  'recovered_refs':['/home/peyton/.codex/sessions/2025/11/26/rollout-2025-11-26T00-55-44-019abda8-c0d8-7803-8a77-1e0fcf0dc577.jsonl','/arxiv/TOLBERT_BRAIN/scripts/eval_retrieval.py'],
  'next':'Keep as retrieval-source enrichment, not direct model training data.'},
 'skill_tool_registry':{
  'pipeline_phase':'agent_tooling','role':'Index available tools, skills, actions, schemas, permissions, and failure modes as structured tool-selection context.',
  'outputs':['tool_id','skill_id','allowed_action','permission_boundary','tool_failure_mode'],'local_status':'missing_as_training_surface',
  'recovered_refs':['/arxiv/repositories/modelcontextprotocol__servers/src/git/README.md','/arxiv/repositories/modelcontextprotocol__servers/src/fetch/README.md','/arxiv/repositories/modelcontextprotocol__servers/src/memory/README.md'],
  'next':'Create tool/action ontology rows for observe-orient-act trajectory training.'},
 'latency_resource_observability':{
  'pipeline_phase':'runtime_governance','role':'Track latency, memory, token, and tool costs so the controller learns bounded maintenance rather than unlimited search.',
  'outputs':['latency_ms','memory_peak','token_count','tool_cost','budget_violation'],'local_status':'missing_as_unified_telemetry',
  'recovered_refs':['/arxiv/repositories/deepeval/deepeval/tracing/trace_context.py','/arxiv/repositories/nni/nni/common/concrete_trace_utils/flop_utils.py'],
  'next':'Integrate with cost_budget_scheduler and eval metric cards.'},
 'benchmark_task_pack_manager':{
  'pipeline_phase':'evaluation','role':'Maintain benchmark packs, task rotations, and regression thresholds for software-maintainer skills.',
  'outputs':['task_pack_id','slice_tags','thresholds','rotation_policy','regression_block'],'local_status':'reference_recovered_not_integrated',
  'recovered_refs':['/arxiv/repositories/Aider-AI__aider/benchmark/benchmark.py','/arxiv/repositories/deepeval/deepeval/benchmarks/base_benchmark.py','/arxiv/datasets/ScaleAI--SWE-Atlas-QnA/rubric_evaluation_config.yaml'],
  'next':'Pair with golden_locked_eval_suite before any promotion-ready claim.'}
}

def main():
 missing={k:[r for r in c['recovered_refs'] if r.startswith('/') and not Path(r).exists()] for k,c in COMPONENTS.items()}
 missing={k:v for k,v in missing.items() if v}
 card={'stage':8658,'stage_name':'stage8658_infrastructure_support_modules_recovery_index','passed':True,'authority':AUTHORITY_CLOSED,'components':COMPONENTS,
       'metrics':{'infrastructure_support_components':len(COMPONENTS),'missing_recovered_refs':missing,'pipeline_phases':sorted({c['pipeline_phase'] for c in COMPONENTS.values()}),'model_execution_authorized_next':False,'decoder_ce_training_authorized_next':False,'denoise_ce_training_authorized_next':False,'runtime_authorized':False,'promotion_ready':False},
       'decision':'Recovered infrastructure support modules required to make the training loop observable, reproducible, memory-aware, and governed. This is no-authority indexing only.',
       'next_best_step':'Attach Stage8658 to the central graph, then prioritize traced-eval, source-lineage, benchmark-pack, and tool-registry schemas before training or runtime reopen.',
       'created_at_utc':time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}
 OUT.write_text(json.dumps(card,indent=2,sort_keys=True)+'\n')
 SUMMARY.write_text(json.dumps(card,indent=2,sort_keys=True)+'\n')
 lines=['# Stage8658 Infrastructure Support Modules Recovery Index','','No-authority recovery of infrastructure modules needed around the 100M maintainer training loop.','','## Modules']
 for n,c in sorted(COMPONENTS.items()): lines.append(f"- `{n}`: {c['role']} Status: `{c['local_status']}`. Next: {c['next']}")
 lines += ['','## Authority','All model/training/runtime/promotion authorities remain closed.']
 DOC.write_text('\n'.join(lines)+'\n')
 print(json.dumps(card,indent=2,sort_keys=True))
if __name__=='__main__': main()
