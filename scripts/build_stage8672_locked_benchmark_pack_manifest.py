#!/usr/bin/env python3
from __future__ import annotations
import hashlib,json,re,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
LINEAGE=ROOT/'configs/software_maintainer/source_inventory_lineage_registry_stage8663.json'
OUT_DIR=ROOT/'runs/local/artifacts/stage8672_locked_benchmark_pack_manifest'
SUMMARY=ROOT/'runs/summaries/stage8672_locked_benchmark_pack_manifest.json'
DOC=ROOT/'docs/LOCKED_BENCHMARK_PACK_MANIFEST_STAGE8672.md'
AUTHORITY_CLOSED={'model_execution_authorized_next':False,'decoder_ce_training_authorized_next':False,'runtime_authorized':False,'source_emission_authorized':False,'body_emission_authorized':False,'gemma_execution_authorized_next':False,'harness_execution_authorized_next':False,'scoring_authorized_next':False,'controller_complete_merge_authorized_next':False,'promotion_ready':False}
def sha(p:Path)->str:
 h=hashlib.sha256(); h.update(p.read_bytes()[:1048576]); return h.hexdigest()
def parse_scores(p:Path):
 rows=[]
 if not p.exists(): return rows
 for line in p.read_text(errors='ignore').splitlines():
  m=re.match(r'([0-9.]+)%\s+(.+)',line.strip())
  if m: rows.append({'score_percent':float(m.group(1)),'label':m.group(2)})
 return rows
def main():
 OUT_DIR.mkdir(parents=True,exist_ok=True)
 lineage=json.loads(LINEAGE.read_text())
 locked=[r for r in lineage['records'] if r.get('locked_eval')]
 packs=[]; failures=[]
 for r in locked:
  p=Path(r['path'])
  pack={'source_id':r['source_id'],'path':r['path'],'exists':p.exists(),'lineage_hash':r['lineage_hash'],'train_eligible':r['train_eligible'],'blocked_training_reason':r.get('blocked_training_reason'),'artifact_hash':r.get('content_hash_prefix'),'task_pack_id':'locked_'+r['source_id'],'split_role':'locked_regression','promotion_only':True,'hidden_final':False,'thresholds':{},'slice_tags':[],'parsed_scores':[]}
  name=p.name.lower()
  if 'swe_bench' in name or 'benchmark' in name: pack['slice_tags']+=['swe_bench','software_agent_benchmark']; pack['thresholds']={'no_regression_required':True,'report_only_score_floor':0.0}
  if 'rubric' in name: pack['slice_tags']+=['rubric_judge','calibration_required']; pack['thresholds']={'rubric_parse_required':True,'judge_verifier_disagreement_report_required':True}
  if p.suffix=='.parquet': pack['slice_tags']+=['locked_dataset_parquet']; pack['thresholds']={'contamination_zero_required':True}
  if p.name in {'swe-bench.txt','swe-bench-lite.txt'}: pack['parsed_scores']=parse_scores(p)
  if pack['train_eligible']: failures.append('locked_pack_train_eligible:'+r['path'])
  if pack['blocked_training_reason']!='locked_eval_source_never_mined_into_training': failures.append('locked_pack_missing_block_reason:'+r['path'])
  packs.append(pack)
 required_tags={'swe_bench','rubric_judge','locked_dataset_parquet'}
 found=set(t for p in packs for t in p['slice_tags'])
 missing=sorted(required_tags-found)
 if missing: failures.append('missing_required_locked_pack_tags:'+','.join(missing))
 card={'stage':8672,'stage_name':'stage8672_locked_benchmark_pack_manifest','passed':not failures,'authority':AUTHORITY_CLOSED,'benchmark_packs':packs,'metrics':{'locked_packs':len(packs),'promotion_only_packs':sum(1 for p in packs if p['promotion_only']),'train_eligible_packs':sum(1 for p in packs if p['train_eligible']),'slice_tags':sorted(found),'parsed_score_rows':sum(len(p['parsed_scores']) for p in packs),'failures':failures,'model_execution_authorized_next':False,'decoder_ce_training_authorized_next':False,'denoise_ce_training_authorized_next':False,'runtime_authorized':False,'promotion_ready':False},'decision':'Locked benchmark pack manifest is versioned and promotion-only.' if not failures else 'Locked benchmark pack manifest failed boundary checks.','next_best_step':'Attach locked benchmark packs to graph and use them as promotion-only regression sources; never mine them into train/dev-failure rows.','created_at_utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime())}
 (OUT_DIR/'locked_benchmark_pack_manifest.json').write_text(json.dumps(card,indent=2,sort_keys=True)+'\n')
 with (OUT_DIR/'locked_benchmark_packs.jsonl').open('w') as f:
  for p in packs: f.write(json.dumps(p,sort_keys=True)+'\n')
 SUMMARY.write_text(json.dumps(card,indent=2,sort_keys=True)+'\n')
 DOC.write_text('# Stage8672 Locked Benchmark Pack Manifest\n\n'+f"Passed: `{card['passed']}`\n\n- Locked packs: `{len(packs)}`\n- Promotion-only packs: `{card['metrics']['promotion_only_packs']}`\n- Train-eligible packs: `{card['metrics']['train_eligible_packs']}`\n- Slice tags: `{card['metrics']['slice_tags']}`\n- Failures: `{failures}`\n\nAll authorities remain closed.\n")
 print(json.dumps(card,indent=2,sort_keys=True)); raise SystemExit(0 if card['passed'] else 1)
if __name__=='__main__': main()
