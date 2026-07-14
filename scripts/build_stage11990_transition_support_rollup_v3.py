#!/usr/bin/env python3
from __future__ import annotations
import json, time
from collections import Counter
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; ART=ROOT/'runs/local/artifacts'; OUT=ART/'stage11990_transition_support_rollup_v3'; SUMMARY=OUT/'transition_support_rollup_v3.json'; ROWS=OUT/'transition_support_rows_v3.jsonl'
SOURCES={'stage11987':ART/'stage11987_transition_support_rollup_v2/transition_support_rows_v2.jsonl','stage11989':ART/'stage11989_web_workspace_admission_audit/web_workspace_admitted_rows.jsonl'}
LANG_FLOORS={'python':50,'rust':50,'c_cpp':50,'web_js_ts_html':50}; STATUS_FLOORS={'FAIL_TO_PASS':50,'PASS_TO_PASS':100,'PASS_CURRENT_BUILD':40,'PASS_CURRENT_BUILD_AND_RUN':40,'INSUFFICIENT_EVIDENCE':40,'NOT_EXERCISED':40}
def now(): return time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
def rel(p):
 try: return str(p.relative_to(ROOT))
 except ValueError: return str(p)
def read_jsonl(p): return [json.loads(l) for l in p.read_text().splitlines() if l.strip()] if p.exists() else []
def write_json(p,payload): p.parent.mkdir(parents=True,exist_ok=True); p.write_text(json.dumps(payload,indent=2,sort_keys=True)+'\n')
def write_jsonl(p,rows): p.parent.mkdir(parents=True,exist_ok=True); p.write_text(''.join(json.dumps(r,sort_keys=True)+'\n' for r in rows))
def rem(f,c): return {k:max(0,v-int(c.get(k,0))) for k,v in f.items()}
def main():
 rows=[]
 for source,path in SOURCES.items():
  for r in read_jsonl(path):
   out=dict(r); out['row_id']=f"{r.get('row_id')}::stage11990_{source}"; out['stage11990_source']=source; out['split']='train'; out['split_role']='stage11990_transition_support_v3_train_support_only'; out['train_support_only']=True; out['strict_eval_eligible']=False; out['source_heldout_admissible']=False; rows.append(out)
 write_jsonl(ROWS,rows)
 lang=Counter(str(r.get('language_family') or 'unknown') for r in rows); status=Counter(str(r.get('observed_verifier_transition') or 'unknown') for r in rows); repos=Counter(str(r.get('repo_family') or r.get('repo_id') or 'unknown') for r in rows); sources=Counter(str(r.get('stage11990_source')) for r in rows); roots={str(r.get('root_lineage_key') or r.get('root_id') or r.get('source_root_id') or r.get('row_id')) for r in rows}
 ready=(len(rows)>=80 and len(roots)>=40 and all(lang.get(k,0)>=20 for k in LANG_FLOORS) and status.get('PASS_TO_PASS',0)>=20 and status.get('PASS_CURRENT_BUILD',0)>=20)
 summary={'stage':11990,'stage_name':'stage11990_transition_support_rollup_v3','created_at_utc':now(),'decision':'transition_support_v3_ready_diagnostic_only','claim_boundary':'Support inventory improved, but remains train-support/diagnostic only and below Transition-Root-250 floors.','source_artifacts':{k:rel(v) for k,v in SOURCES.items()},'summary':{'rows':len(rows),'unique_roots':len(roots),'language_counts':dict(lang),'status_counts':dict(status),'repo_family_counts':dict(repos),'source_counts':dict(sources),'remaining_to_floor':{'language_remaining':rem(LANG_FLOORS,lang),'status_remaining':rem(STATUS_FLOORS,status)},'train_package_ready':ready},'do_not_train_as_frontier_reasons':['web rows now exist but all come from one repo family','Rust/C++/Python root floors remain far below target','FAIL_TO_PASS remains controlled-fixture dominated','PASS_CURRENT_BUILD_AND_RUN, INSUFFICIENT_EVIDENCE, and NOT_EXERCISED floors remain empty'], 'outputs':{'summary':rel(SUMMARY),'rows':rel(ROWS)},'next_stage_recommendation':{'stage':'stage11991_transition_root_status_gap_plan','action':'Target PASS_CURRENT_BUILD_AND_RUN plus real FAIL_TO_PASS/NOT_EXERCISED from broader roots; avoid model probes until support package reaches meaningful root/status breadth.'}}
 write_json(SUMMARY,summary); print(json.dumps({'decision':summary['decision'],'summary':summary['summary'],'next':summary['next_stage_recommendation']},indent=2,sort_keys=True))
if __name__=='__main__': main()
