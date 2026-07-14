#!/usr/bin/env python3
from __future__ import annotations
import json, re, time
from collections import Counter
from pathlib import Path
from typing import Any
ROOT=Path(__file__).resolve().parents[1]; ART=ROOT/'runs/local/artifacts'
OUT=ART/'stage11989_web_workspace_admission_audit'; SUMMARY=OUT/'web_workspace_admission_audit.json'; ADMITTED=OUT/'web_workspace_admitted_rows.jsonl'; REJECTED=OUT/'web_workspace_rejected_rows.jsonl'
SOURCE=ART/'stage11988_web_workspace_transition_probe/web_workspace_transition_rows.jsonl'
def now(): return time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
def rel(p:Path):
 try: return str(p.relative_to(ROOT))
 except ValueError: return str(p)
def read_jsonl(p): return [json.loads(l) for l in p.read_text().splitlines() if l.strip()] if p.exists() else []
def write_json(p,payload): p.parent.mkdir(parents=True,exist_ok=True); p.write_text(json.dumps(payload,indent=2,sort_keys=True)+'\n')
def write_jsonl(p,rows): p.parent.mkdir(parents=True,exist_ok=True); p.write_text(''.join(json.dumps(r,sort_keys=True)+'\n' for r in rows))
def reject_reason(r):
 obs=(r.get('standalone_projection_source') or {}).get('tool_or_verifier_observation') or {}; status=str(r.get('observed_verifier_transition') or '')
 if obs.get('returncode') != 0 or obs.get('timed_out'): return f'nonzero_or_timeout::{status}'
 if status == 'PASS_TO_PASS':
  count=(r.get('standalone_projection_source') or {}).get('observed_test_count')
  if not isinstance(count,int) or count <= 0: return 'pass_to_pass_missing_positive_test_count'
 elif status == 'PASS_CURRENT_BUILD':
  cmd=' '.join(obs.get('command') or [])
  if not any(s in cmd for s in ['typecheck','check','build']): return 'pass_current_build_without_static_build_command'
 else: return f'status_not_admitted::{status}'
 if len((r.get('standalone_projection_source') or {}).get('opaque_options') or r.get('opaque_options') or []) < 2: return 'missing_competing_options'
 anti=r.get('anti_cheat') if isinstance(r.get('anti_cheat'),dict) else {}
 if anti.get('deterministic_option_shuffle') is not True: return 'missing_deterministic_shuffle'
 return None
def main():
 rows=read_jsonl(SOURCE); admitted=[]; rejected=[]
 for r in rows:
  reason=reject_reason(r)
  if reason is None:
   out=dict(r); out['split']='train'; out['split_role']='stage11989_web_workspace_train_support_only'; out['train_support_only']=True; out['strict_eval_eligible']=False; out['source_heldout_admissible']=False; out['stage11989_admission']={'admitted':True,'not_promotable_eval':True,'reason':'workspace_command_observed_with_clean_test_or_typecheck_evidence'}; admitted.append(out)
  else:
   bad=dict(r); bad['stage11989_rejection_reason']=reason; rejected.append(bad)
 write_jsonl(ADMITTED, admitted); write_jsonl(REJECTED, rejected)
 summary={'stage':11989,'stage_name':'stage11989_web_workspace_admission_audit','created_at_utc':now(),'decision':'web_workspace_admission_complete_train_support_only' if admitted else 'web_workspace_admission_complete_no_rows','claim_boundary':'web rows are train-support-only from one repo family; not strict/source-heldout eval','source_artifact':rel(SOURCE),'summary':{'review_rows':len(rows),'admitted_rows':len(admitted),'rejected_rows':len(rejected),'admitted_status_counts':dict(Counter(r.get('observed_verifier_transition') for r in admitted)),'admitted_package_counts':dict(Counter((r.get('stage11988_candidate') or {}).get('package') for r in admitted)),'rejection_reasons':dict(Counter(r.get('stage11989_rejection_reason') for r in rejected))},'outputs':{'summary':rel(SUMMARY),'admitted':rel(ADMITTED),'rejected':rel(REJECTED)},'next_stage_recommendation':{'stage':'stage11990_transition_support_rollup_v3','action':'Merge web workspace rows into support inventory; still do not promote or train as frontier until broader root/status floors improve.'}}
 write_json(SUMMARY, summary); print(json.dumps({'decision':summary['decision'],'summary':summary['summary'],'next':summary['next_stage_recommendation']},indent=2,sort_keys=True))
if __name__=='__main__': main()
