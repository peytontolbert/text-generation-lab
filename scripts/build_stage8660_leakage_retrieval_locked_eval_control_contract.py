#!/usr/bin/env python3
from __future__ import annotations
import json, time, hashlib
from pathlib import Path
from typing import Any
ROOT=Path(__file__).resolve().parents[1]
OUT_DIR=ROOT/'runs/local/artifacts/stage8660_leakage_retrieval_locked_eval_control_contract'
CONFIG=ROOT/'configs/software_maintainer/leakage_retrieval_locked_eval_control_contract_stage8660.json'
SUMMARY=ROOT/'runs/summaries/stage8660_leakage_retrieval_locked_eval_control_contract.json'
DOC=ROOT/'docs/LEAKAGE_RETRIEVAL_LOCKED_EVAL_CONTROL_CONTRACT_STAGE8660.md'
AUTHORITY_CLOSED={'model_execution_authorized_next':False,'decoder_ce_training_authorized_next':False,'runtime_authorized':False,'source_emission_authorized':False,'body_emission_authorized':False,'gemma_execution_authorized_next':False,'harness_execution_authorized_next':False,'scoring_authorized_next':False,'controller_complete_merge_authorized_next':False,'promotion_ready':False}
SOURCE_GROUPS={
 'repo_graph_sources':['/arxiv/TOLBERT_BRAIN/data/repos/nodes_repos.jsonl','/arxiv/TOLBERT_BRAIN/data/repos/spans_repos.jsonl','/arxiv/TOLBERT_BRAIN/data/repos/level_sizes_repos.json','/arxiv/TOLBERT_BRAIN/scripts/codegraph_core.py','/arxiv/TOLBERT_BRAIN/scripts/code_graph.py','/arxiv/TOLBERT_BRAIN/scripts/repo_graph.py','/arxiv/TOLBERT_BRAIN/modules/program_graph.py'],
 'retrieval_sources':['/arxiv/TOLBERT_BRAIN/scripts/retrieval_sandbox.py','/arxiv/TOLBERT_BRAIN/scripts/eval_retrieval.py','/arxiv/datasets/google--code_x_glue_tc_nl_code_search_adv','/arxiv/repositories/camel-ai__camel/camel/retrievers/bm25_retriever.py','/arxiv/repositories/camel-ai__camel/camel/retrievers/vector_retriever.py','/arxiv/repositories/camel-ai__camel/test/retrievers/test_hybrid_retriever.py','/arxiv/repositories/deepset-ai__haystack/docs-website/docs/pipeline-components/joiners/documentjoiner.mdx','/arxiv/repositories/deepset-ai__haystack/docs-website/docs/pipeline-components/rankers/lostinthemiddleranker.mdx','/arxiv/repositories/deepset-ai__haystack/docs-website/docs/pipeline-components/retrievers/sentencewindowretrieval.mdx'],
 'code_curriculum_sources':['/arxiv/datasets/nvidia--OpenCodeInstruct','/arxiv/datasets/nvidia--OpenCodeReasoning','/arxiv/datasets/google--code_x_glue_cc_code_refinement','/arxiv/datasets/lazarus19--Vibe-Coding-Instruct-V2'],
 'agent_trace_sources':['/arxiv/datasets/nvidia--Open-SWE-Traces','/arxiv/repositories/SWE-agent__SWE-agent','/arxiv/repositories/Aider-AI__aider','/arxiv/repositories/OpenAutoCoder__Agentless'],
 'locked_eval_sources':['/arxiv/repositories/Aider-AI__aider/benchmark/benchmark.py','/arxiv/repositories/Aider-AI__aider/benchmark/swe_bench.py','/arxiv/datasets/ScaleAI--SWE-Atlas-QnA/rubric_evaluation_config.yaml','/arxiv/datasets/ScaleAI--SWE-Atlas-QnA/data/test-00000-of-00001.parquet','/arxiv/repositories/deepeval/deepeval/benchmarks/base_benchmark.py'],
 'safety_security_sources':['/arxiv/repositories/CheatSheetSeries/cheatsheets/Secrets_Management_Cheat_Sheet.md','/arxiv/repositories/CheatSheetSeries/cheatsheets/RAG_Security_Cheat_Sheet.md','/arxiv/repositories/CheatSheetSeries/cheatsheets/Software_Supply_Chain_Security_Cheat_Sheet.md','/arxiv/repositories/CheatSheetSeries/cheatsheets/AI_Agent_Security_Cheat_Sheet.md'],
 'observability_sources':['/arxiv/repositories/deepeval/deepeval/tracing/trace_context.py','/arxiv/repositories/deepeval/deepeval/dataset/test_run_tracer.py','/arxiv/repositories/modelcontextprotocol__servers/src/memory/index.ts']
}

def sha256_file(path: Path, max_bytes:int=65536)->str|None:
 if not path.is_file(): return None
 h=hashlib.sha256()
 with path.open('rb') as f: h.update(f.read(max_bytes))
 return h.hexdigest()
def inv_path(p:str)->dict[str,Any]:
 path=Path(p); exists=path.exists(); rec={'path':p,'exists':exists,'kind':'missing'}
 if not exists: return rec
 if path.is_dir():
  files=[x for x in path.rglob('*') if x.is_file()]
  rec.update({'kind':'directory','file_count':len(files),'parquet_files':sum(1 for x in files if x.suffix=='.parquet'),'jsonl_files':sum(1 for x in files if x.suffix=='.jsonl'),'readme_present':(path/'README.md').exists(),'sample_files':[str(x) for x in files[:8]]})
 else:
  rec.update({'kind':'file','suffix':path.suffix,'size_bytes':path.stat().st_size,'sha256_prefix64k':sha256_file(path)})
 return rec
LEAKAGE_CONTROLS={
 'label_visibility_block':{'must_check':['target label absent from model_input','clean_state not included in corrupted/model input','label-coded graph IDs disallowed','direct target fields disallowed'],'blocked_if':['target_label_visible','label_coded_id','direct_target_field_visible','clean_state_used_as_input']},
 'source_body_boundary':{'must_check':['raw source bodies not exported to decoder targets','source snippets are evidence spans only','source/body emission authority remains closed'],'blocked_if':['raw_source_body_export_requested','body_leak_flag','source_emission_authorized']},
 'split_contamination':{'must_check':['exact hash overlap zero','semantic key overlap zero','near-duplicate clusters split-safe','locked/hidden eval never mined'],'blocked_if':['train_eval_duplicate','source_split_leak','heldout_overlap','locked_eval_source_used_for_training']},
 'shortcut_proxy_audit':{'must_check':['single-feature baselines below ceilings','metadata-only baseline below evidence-present','proxy counts cannot solve labels'],'blocked_if':['shortcut_dominated_feature','metadata_only_beats_retrieval','count_proxy_solves_target']},
 'secret_pii_security':{'must_check':['secret pattern scan','PII pattern scan','license/security source status'],'blocked_if':['secret_pattern_present','pii_pattern_present','unknown_license_without_review']}
}
RETRIEVAL_CONTROLS={
 'retrieval_baseline_card':{'metrics':['bm25_top1_exact','bm25_top5_recall','dense_top1_exact','dense_top5_recall','hybrid_rrf_top5_recall','rerank_top1_exact'],'blocked_if':['no_evidence_retrieved_for_positive_rows','metadata_only_beats_retrieval','retrieval_disagreement_unrouted']},
 'counterfactual_evidence_card':{'metrics':['evidence_present_accuracy','evidence_removed_drop','wrong_evidence_reject_rate','retrieve_more_rate_on_missing_evidence'],'blocked_if':['evidence_removed_rows_do_not_drop','wrong_evidence_accepted','missing_evidence_not_routed']},
 'context_packing_card':{'metrics':['source_span_kept','critical_span_rank_bucket','dropped_evidence_reason_present','context_budget_ok'],'blocked_if':['critical_span_dropped_without_reason','lost_in_middle_risk_unmeasured','context_budget_missing']},
 'query_expansion_card':{'metrics':['query_variant_count','expansion_source_bits','expansion_lift','expansion_shortcut_baseline'],'blocked_if':['query_expansion_encodes_label','expansion_degrades_retrieval','expansion_shortcut_over_ceiling']}
}
LOCKED_EVAL_CONTROLS={
 'eval_split_policy':{'sets':['train','dev_failure_mining','locked_regression','hidden_final'],'rules':['dev_failure_mining may generate dataset patches','locked_regression is promotion-only','hidden_final is never used for mining or prompt generation','training sources must record lineage']},
 'promotion_gate':{'required':['target slice improves','old canaries non-regress','locked eval leakage zero','benchmark task pack metrics emitted'],'blocked_if':['locked_regression_drop','canary_forgotten_skill','missing_metric_card','hidden_eval_contamination']},
 'trace_to_dataset_boundary':{'allowed':['dev-failure trace to dataset patch','judge/verifier disagreement to review queue'],'forbidden':['locked eval trace to training row','hidden eval trace to synthetic prompt','benchmark answer as decoder target']},
 'benchmark_pack_policy':{'required':['task_pack_id','slice_tags','thresholds','rotation_policy','artifact_paths'],'blocked_if':['unversioned_eval','threshold_missing','rubric_without_calibration']}
}
LOSS_AUTHORITY={'allowed_now':['lineage_inventory_audit','feature_normalization_audit','shortcut_baseline_audit','retrieval_baseline_audit','locked_eval_manifest_audit'],'forbidden_now':['decoder_ce','denoise_ce','runtime_reward','body_source_training','controller_merge','promotion_scoring'],'authority':AUTHORITY_CLOSED}

def main():
 OUT_DIR.mkdir(parents=True,exist_ok=True)
 inventory={g:[inv_path(p) for p in paths] for g,paths in SOURCE_GROUPS.items()}
 missing={g:[r['path'] for r in rows if not r['exists']] for g,rows in inventory.items()}
 missing={k:v for k,v in missing.items() if v}
 source_counts={g:{'entries':len(rows),'existing':sum(1 for r in rows if r['exists']),'directories':sum(1 for r in rows if r.get('kind')=='directory'),'files':sum(1 for r in rows if r.get('kind')=='file'),'parquet_files':sum(r.get('parquet_files',0) for r in rows)} for g,rows in inventory.items()}
 contract={'stage':8660,'stage_name':'stage8660_leakage_retrieval_locked_eval_control_contract','passed':True,'authority':AUTHORITY_CLOSED,'source_inventory':inventory,'controls':{'leakage':LEAKAGE_CONTROLS,'retrieval':RETRIEVAL_CONTROLS,'locked_eval':LOCKED_EVAL_CONTROLS,'loss_authority':LOSS_AUTHORITY},'metrics':{'source_groups':len(SOURCE_GROUPS),'source_counts':source_counts,'missing_sources':missing,'leakage_control_cards':len(LEAKAGE_CONTROLS),'retrieval_control_cards':len(RETRIEVAL_CONTROLS),'locked_eval_control_cards':len(LOCKED_EVAL_CONTROLS),'model_execution_authorized_next':False,'decoder_ce_training_authorized_next':False,'denoise_ce_training_authorized_next':False,'runtime_authorized':False,'promotion_ready':False},'decision':'Recovered a single no-authority control contract tying source lineage, leakage blocking, retrieval evidence, context packing, and locked-eval governance together before any training/runtime reopen.','next_best_step':'Implement Stage8660a/8660b concrete source inventory and shared feature normalizer libraries, then run retrieval and leakage baseline cards on graph/symbol candidate rows.','created_at_utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime())}
 CONFIG.write_text(json.dumps(contract,indent=2,sort_keys=True)+'\n'); SUMMARY.write_text(json.dumps(contract,indent=2,sort_keys=True)+'\n'); (OUT_DIR/'control_contract.json').write_text(json.dumps(contract,indent=2,sort_keys=True)+'\n')
 (OUT_DIR/'source_inventory.json').write_text(json.dumps(inventory,indent=2,sort_keys=True)+'\n')
 lines=['# Stage8660 Leakage/Retrieval/Locked-Eval Control Contract','','This stage restores the missing control spine around source-backed curriculum expansion. It is documentation/configuration only.','','## Source Groups']
 for g,c in source_counts.items(): lines.append(f"- `{g}`: `{c['existing']}/{c['entries']}` entries exist, parquet files under directories: `{c['parquet_files']}`")
 lines += ['','## Leakage Controls']+[f"- `{k}` blocks: {', '.join(v['blocked_if'])}" for k,v in LEAKAGE_CONTROLS.items()]
 lines += ['','## Retrieval Controls']+[f"- `{k}` metrics: {', '.join(v['metrics'])}" for k,v in RETRIEVAL_CONTROLS.items()]
 lines += ['','## Locked Eval Controls']+[f"- `{k}`" for k in LOCKED_EVAL_CONTROLS]
 lines += ['','## Authority','All model/training/runtime/source/body/Gemma/harness/scoring/promotion authorities remain closed.','','## Next Step',contract['next_best_step']]
 DOC.write_text('\n'.join(lines)+'\n')
 print(json.dumps(contract,indent=2,sort_keys=True))
if __name__=='__main__': main()
