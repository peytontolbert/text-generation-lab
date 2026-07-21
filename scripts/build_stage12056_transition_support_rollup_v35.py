#!/usr/bin/env python3
from __future__ import annotations
import json
from collections import Counter
from pathlib import Path
from typing import Any
ROOT=Path('runs/local/artifacts/stage12056_transition_support_rollup_v35'); BASE=Path('runs/local/artifacts/stage12054_transition_support_rollup_v34/transition_support_rows_v34.jsonl'); ADDED=Path('runs/local/artifacts/stage12055_controlled_semantic_fail_to_pass_supplement_rows/controlled_semantic_fail_to_pass_supplement_rows.jsonl'); ROWS_OUT=ROOT/'transition_support_rows_v35.jsonl'; SUMMARY=ROOT/'transition_support_rollup_v35.json'; SUMMARY_MIRROR=Path('runs/summaries/stage12056_transition_support_rollup_v35.json')
LANG={'python':50,'rust':50,'c_cpp':50,'web_js_ts_html':50}; STAT={'FAIL_TO_PASS':50,'PASS_TO_PASS':100,'PASS_CURRENT_BUILD':40,'PASS_CURRENT_BUILD_AND_RUN':40,'INSUFFICIENT_EVIDENCE':40,'NOT_EXERCISED':40}
def read_jsonl(p:Path)->list[dict[str,Any]]: return [json.loads(l) for l in p.read_text().splitlines() if l.strip()] if p.exists() else []
def write_jsonl(p:Path,rows): p.write_text(''.join(json.dumps(r,sort_keys=True)+'\n' for r in rows))
def root_key(r): return r.get('root_lineage_key') or r.get('root_id') or r.get('source_root_id') or r.get('source_bundle_id') or r.get('row_id')
def rem(c,f): return {k:max(0,v-c.get(k,0)) for k,v in f.items()}
def main():
 ROOT.mkdir(parents=True,exist_ok=True); SUMMARY_MIRROR.parent.mkdir(parents=True,exist_ok=True); rows=[]; seen=set(); dup=0
 for source,path in [('stage12054',BASE),('stage12055',ADDED)]:
  for row in read_jsonl(path):
   out=dict(row); out['stage12056_source']=source; out['split']='train'; out['split_role']='stage12056_transition_support_v35_train_support_only'; out['train_support_only']=True; out['strict_eval_eligible']=False; out['source_heldout_admissible']=False; key=(out.get('row_id'),root_key(out),out.get('observed_verifier_transition'))
   if key in seen: dup+=1; continue
   seen.add(key); rows.append(out)
 write_jsonl(ROWS_OUT,rows); lang=Counter(r.get('language_family') for r in rows); status=Counter(r.get('observed_verifier_transition') for r in rows); repo=Counter(r.get('repo_family') for r in rows); rl=rem(lang,LANG); rs=rem(status,STAT); ready=all(v==0 for v in rl.values()) and all(v==0 for v in rs.values())
 summary={'stage':'stage12056_transition_support_rollup_v35','base_rows_path':str(BASE),'added_rows_path':str(ADDED),'rows_path':str(ROWS_OUT),'base_rows':len(read_jsonl(BASE)),'added_rows':len(read_jsonl(ADDED)),'duplicate_rows_skipped':dup,'total_rows':len(rows),'unique_roots':len({root_key(r) for r in rows}),'language_counts':dict(sorted(lang.items())),'status_counts':dict(sorted(status.items())),'repo_family_counts_top30':dict(repo.most_common(30)),'remaining_language_floor':rl,'remaining_status_floor':rs,'train_ready_against_transition_root_250_floors':ready,'controlled_semantic_fail_to_pass_supplement_added':len(read_jsonl(ADDED)),'decision':'support_inventory_v35_floor_ready_requires_anti_cheat_audit' if ready else 'support_inventory_v35_not_train_ready','reason':'All Transition-Root-250 language and status floors are met; run anti-cheat, split/root overlap, repo-concentration, and controlled-fixture ratio audits before training.' if ready else 'Some floors remain unmet.','claim_boundary':'Support inventory only. Controlled semantic fixtures are not source-heldout or strict eval evidence; no model promotion follows from v35 alone.','next_stage_recommendation':{'stage':'stage12057_transition_support_v35_audit','action':'Run anti-cheat, split/root overlap, repo concentration, singleton, target leak, and controlled-fixture ratio audits before training.'}}
 SUMMARY.write_text(json.dumps(summary,indent=2,sort_keys=True)+'\n'); SUMMARY_MIRROR.write_text(json.dumps(summary,indent=2,sort_keys=True)+'\n'); print(json.dumps(summary,indent=2,sort_keys=True))
if __name__=='__main__': main()
