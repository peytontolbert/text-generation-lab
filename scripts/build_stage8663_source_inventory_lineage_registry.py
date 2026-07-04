#!/usr/bin/env python3
from __future__ import annotations
import hashlib,json,time
from pathlib import Path
from typing import Any
ROOT=Path(__file__).resolve().parents[1]
CONTRACT=ROOT/'configs/software_maintainer/leakage_retrieval_locked_eval_control_contract_stage8660.json'
OUT_DIR=ROOT/'runs/local/artifacts/stage8663_source_inventory_lineage_registry'
SUMMARY=ROOT/'runs/summaries/stage8663_source_inventory_lineage_registry.json'
DOC=ROOT/'docs/SOURCE_INVENTORY_LINEAGE_REGISTRY_STAGE8663.md'
CONFIG=ROOT/'configs/software_maintainer/source_inventory_lineage_registry_stage8663.json'
AUTHORITY_CLOSED={'model_execution_authorized_next':False,'decoder_ce_training_authorized_next':False,'runtime_authorized':False,'source_emission_authorized':False,'body_emission_authorized':False,'gemma_execution_authorized_next':False,'harness_execution_authorized_next':False,'scoring_authorized_next':False,'controller_complete_merge_authorized_next':False,'promotion_ready':False}
ROLE_POLICY={
 'repo_graph_sources':{'allowed_roles':['graph_feature_source','symbol_binding_evidence_source'],'train_eligible':True,'locked_eval':False,'hidden_final':False},
 'retrieval_sources':{'allowed_roles':['retrieval_baseline_source','evidence_retrieval_source'],'train_eligible':True,'locked_eval':False,'hidden_final':False},
 'code_curriculum_sources':{'allowed_roles':['candidate_curriculum_source','dev_failure_mining_source'],'train_eligible':True,'locked_eval':False,'hidden_final':False},
 'agent_trace_sources':{'allowed_roles':['trajectory_mining_source','dev_failure_mining_source'],'train_eligible':True,'locked_eval':False,'hidden_final':False},
 'locked_eval_sources':{'allowed_roles':['locked_regression_eval_source','promotion_only_eval_source'],'train_eligible':False,'locked_eval':True,'hidden_final':False},
 'safety_security_sources':{'allowed_roles':['safety_policy_reference','security_filter_reference'],'train_eligible':False,'locked_eval':False,'hidden_final':False},
 'observability_sources':{'allowed_roles':['observability_reference','trace_schema_reference'],'train_eligible':False,'locked_eval':False,'hidden_final':False},
}
def hash_file(p:Path, max_bytes:int=1048576)->str|None:
 if not p.is_file(): return None
 h=hashlib.sha256()
 with p.open('rb') as f:
  remaining=max_bytes
  while remaining>0:
   chunk=f.read(min(65536,remaining))
   if not chunk: break
   h.update(chunk); remaining-=len(chunk)
 return h.hexdigest()
def listing_hash(p:Path)->str|None:
 if not p.is_dir(): return None
 h=hashlib.sha256(); count=0
 for f in sorted(x for x in p.rglob('*') if x.is_file()):
  rel=str(f.relative_to(p)); st=f.stat(); count+=1
  h.update(rel.encode()); h.update(str(st.st_size).encode()); h.update(str(int(st.st_mtime)).encode())
 return h.hexdigest()
def license_status(path:Path)->str:
 base=path if path.is_dir() else path.parent
 names={x.name.lower() for x in base.iterdir()} if base.exists() and base.is_dir() else set()
 if any(n.startswith('license') or n in {'copying','notice'} for n in names): return 'license_file_present'
 if (base/'README.md').exists(): return 'readme_present_license_unknown'
 return 'unknown'
def entry_record(group:str, row:dict[str,Any])->dict[str,Any]:
 path=Path(row['path']); policy=ROLE_POLICY[group]
 sid='src_'+hashlib.sha256((group+'|'+row['path']).encode()).hexdigest()[:16]
 kind=row.get('kind','missing')
 rec={'source_id':sid,'source_group':group,'path':row['path'],'exists':row.get('exists',False),'kind':kind,'allowed_roles':policy['allowed_roles'],'train_eligible':policy['train_eligible'],'locked_eval':policy['locked_eval'],'hidden_final':policy['hidden_final'],'license_status':license_status(path) if row.get('exists') else 'missing','lineage_hash':None,'content_hash_prefix':None,'file_count':row.get('file_count'),'parquet_files':row.get('parquet_files',0),'jsonl_files':row.get('jsonl_files',0),'readme_present':row.get('readme_present',False),'blocked_training_reason':None}
 if kind=='file':
  rec['content_hash_prefix']=row.get('sha256_prefix64k') or hash_file(path)
  rec['lineage_hash']=hashlib.sha256((sid+'|'+str(rec['content_hash_prefix'])+'|file').encode()).hexdigest()
 elif kind=='directory':
  rec['content_hash_prefix']=listing_hash(path)
  rec['lineage_hash']=hashlib.sha256((sid+'|'+str(rec['content_hash_prefix'])+'|directory').encode()).hexdigest()
 if not rec['train_eligible']:
  rec['blocked_training_reason']='source_role_not_training_eligible'
 if rec['locked_eval']:
  rec['blocked_training_reason']='locked_eval_source_never_mined_into_training'
 return rec
def main():
 OUT_DIR.mkdir(parents=True,exist_ok=True)
 contract=json.loads(CONTRACT.read_text())
 records=[]; failures=[]
 for group, rows in contract['source_inventory'].items():
  if group not in ROLE_POLICY: failures.append(f'group_policy_missing:{group}')
  for row in rows:
   rec=entry_record(group,row); records.append(rec)
   if not rec['exists']: failures.append(f'missing_source:{rec["path"]}')
   if not rec['lineage_hash']: failures.append(f'missing_lineage_hash:{rec["path"]}')
   if rec['locked_eval'] and rec['train_eligible']: failures.append(f'locked_eval_train_eligible:{rec["path"]}')
   if rec['source_group']=='locked_eval_sources' and rec['blocked_training_reason']!='locked_eval_source_never_mined_into_training': failures.append(f'locked_eval_reason_missing:{rec["path"]}')
 source_ids=[r['source_id'] for r in records]
 if len(source_ids)!=len(set(source_ids)): failures.append('duplicate_source_id')
 registry={'stage':8663,'stage_name':'stage8663_source_inventory_lineage_registry','passed':not failures,'authority':AUTHORITY_CLOSED,'records':records,'metrics':{'source_records':len(records),'source_groups':len(set(r['source_group'] for r in records)),'train_eligible_records':sum(1 for r in records if r['train_eligible']),'locked_eval_records':sum(1 for r in records if r['locked_eval']),'non_training_records':sum(1 for r in records if not r['train_eligible']),'parquet_files_indexed':sum(r.get('parquet_files') or 0 for r in records),'failures':failures,'model_execution_authorized_next':False,'decoder_ce_training_authorized_next':False,'denoise_ce_training_authorized_next':False,'runtime_authorized':False,'promotion_ready':False},'decision':'Source lineage registry is ready.' if not failures else 'Source lineage registry failed readiness checks.','next_best_step':'Use source_id and lineage_hash in all graph/symbol/retrieval candidate rows; locked_eval source_ids must be rejected by training builders.','created_at_utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime())}
 CONFIG.write_text(json.dumps(registry,indent=2,sort_keys=True)+'\n')
 SUMMARY.write_text(json.dumps(registry,indent=2,sort_keys=True)+'\n')
 (OUT_DIR/'source_lineage_registry.json').write_text(json.dumps(registry,indent=2,sort_keys=True)+'\n')
 with (OUT_DIR/'source_lineage_registry.jsonl').open('w') as f:
  for r in records: f.write(json.dumps(r,sort_keys=True)+'\n')
 lines=['# Stage8663 Source Inventory Lineage Registry','','Executable source lineage registry derived from Stage8660.','','## Metrics']
 for k,v in registry['metrics'].items(): lines.append(f'- `{k}`: `{v}`')
 lines += ['','## Boundary','Locked-eval sources are explicitly `train_eligible=false` and carry `blocked_training_reason=locked_eval_source_never_mined_into_training`.']
 DOC.write_text('\n'.join(lines)+'\n')
 print(json.dumps(registry,indent=2,sort_keys=True))
 raise SystemExit(0 if registry['passed'] else 1)
if __name__=='__main__': main()
