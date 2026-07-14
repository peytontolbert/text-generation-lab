#!/usr/bin/env python3
"""Materialize PASS_CURRENT_BUILD_AND_RUN transition rows from paired build+test evidence."""
from __future__ import annotations
import hashlib,json,os,re,subprocess,time
from collections import Counter
from pathlib import Path
from typing import Any
ROOT=Path(__file__).resolve().parents[1]; ART=ROOT/'runs/local/artifacts'; OUT=ART/'stage11991_pass_build_and_run_transition_probe'; SUMMARY=OUT/'pass_build_and_run_transition_probe.json'; ROWS=OUT/'pass_build_and_run_rows.jsonl'; TMP=Path(os.environ.get('TMPDIR') or '/data/tmp')/'stage11991_pass_build_and_run_transition_probe'
STATUS_OPTIONS=[('PASS_TO_PASS','focused verifier/test executed from local source and passed'),('PASS_CURRENT_BUILD','build/typecheck/static check completed but no test body executed'),('PASS_CURRENT_BUILD_AND_RUN','build/typecheck completed and a runnable verifier/test also passed'),('FAIL_TO_PASS','controlled mutation failed and restored source passed'),('FAIL_TO_FAIL','verifier ran and failed in current local source state'),('NOT_EXERCISED','command did not exercise selected verifier path'),('INSUFFICIENT_EVIDENCE','workspace dependencies or package manager state are underhydrated'),('VERIFIER_REMOVED','verifier evidence was removed and row should abstain')]
LABELS=list('ABCDEFGHI')
WEB_PACKAGES=['@modelcontextprotocol/core','@modelcontextprotocol/client','@modelcontextprotocol/server']
RUST_ROOTS=[{'repo_family':'llama-adapter','path':'/data/repositories/LLaMA-Adapter/gorilla/gorilla-main/eval/eval-scripts/codebleu/parser/tree-sitter-python'},{'repo_family':'git','path':'/data/repositories/git/contrib/libgit-sys'}]
def now(): return time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
def rel(p):
 try: return str(p.relative_to(ROOT))
 except ValueError: return str(p)
def write_json(p,payload): p.parent.mkdir(parents=True,exist_ok=True); p.write_text(json.dumps(payload,indent=2,sort_keys=True)+'\n')
def write_jsonl(p,rows): p.parent.mkdir(parents=True,exist_ok=True); p.write_text(''.join(json.dumps(r,sort_keys=True)+'\n' for r in rows))
def run_cmd(cmd,cwd,timeout,log):
 (OUT/'logs').mkdir(parents=True,exist_ok=True); env=os.environ.copy(); env.update({'CUDA_VISIBLE_DEVICES':'','NVIDIA_VISIBLE_DEVICES':'','TMPDIR':str(TMP),'TEMP':str(TMP),'TMP':str(TMP),'CI':'1','NO_COLOR':'1'})
 st=time.time()
 try:
  proc=subprocess.run(cmd,cwd=str(cwd),env=env,text=True,capture_output=True,stdin=subprocess.DEVNULL,timeout=timeout,check=False); rc=proc.returncode; out=proc.stdout or ''; err=proc.stderr or ''; to=False
 except subprocess.TimeoutExpired as e:
  rc=124; out=e.stdout if isinstance(e.stdout,str) else ''; err=e.stderr if isinstance(e.stderr,str) else ''; to=True
 payload={'command':cmd,'cwd':str(cwd),'returncode':rc,'timed_out':to,'duration_sec':round(time.time()-st,3),'stdout_tail':out[-6000:],'stderr_tail':err[-4000:]}
 path=OUT/'logs'/f'{log}.json'; write_json(path,payload); return {**payload,'log_path':rel(path)}
def test_count(text):
 m=re.search(r'Tests\s+(\d+)\s+passed', text)
 if m: return int(m.group(1))
 total=0; found=False
 for m in re.finditer(r'(\d+)\s+passed', text): found=True; total+=int(m.group(1))
 return total if found else None
def ok_build(obs): return obs.get('returncode')==0 and not obs.get('timed_out')
def ok_test(obs): return ok_build(obs) and (test_count(str(obs.get('stdout_tail') or '')+'\n'+str(obs.get('stderr_tail') or '')) or 0)>0
def shuffled(row_id):
 keyed=[(hashlib.sha256(f'{row_id}::{s}'.encode()).hexdigest(),s,t) for s,t in STATUS_OPTIONS]; opts=[]; target=''
 for label,(_,s,t) in zip(LABELS,sorted(keyed)):
  opts.append({'label':label,'value':s,'text':t,'role':'verifier_transition_status','artifact_type':'build_and_run_status','canonical_value':s})
  if s=='PASS_CURRENT_BUILD_AND_RUN': target=label
 return opts,target
def make_row(kind, repo_family, language, root_key, selected, build_obs, test_obs):
 base=f'stage11991::{repo_family}::{root_key}::PASS_CURRENT_BUILD_AND_RUN'; row_id=base+'::'+hashlib.sha1((base+selected).encode()).hexdigest()[:10]
 opts,label=shuffled(row_id)
 text=(f'Language: {language}\nPerspective: transition_verifier_transition\nTask: choose the verifier transition supported by paired build/typecheck and test evidence.\nRepository family: {repo_family}\nRoot/package: {root_key}\nSelected verifier/build pair: {selected}\nBuild command: {" ".join(build_obs.get("command") or [])}\nBuild return code: {build_obs.get("returncode")}\nTest command: {" ".join(test_obs.get("command") or [])}\nTest return code: {test_obs.get("returncode")}\nObserved test count: {test_count(str(test_obs.get("stdout_tail") or "") + str(test_obs.get("stderr_tail") or ""))}\nBuild stdout tail: {str(build_obs.get("stdout_tail") or "")[-800:]}\nTest stdout tail: {str(test_obs.get("stdout_tail") or "")[-1200:]}\nOptions:\n'+'\n'.join(f'{o["label"]}. {o["text"]}' for o in opts)+'\nAnswer:')
 return {'row_id':row_id,'root_id':base,'root_lineage_key':f'stage11991::{repo_family}::{root_key}','source_root_id':base,'source_bundle_id':base,'repo_id':repo_family,'repo_family':repo_family,'language_family':language,'task_type':'transition_verifier_transition','split':'train','split_role':'stage11991_review_queue_only','train_support_only':True,'strict_eval_eligible':False,'source_heldout_admissible':False,'observed_verifier_transition':'PASS_CURRENT_BUILD_AND_RUN','selected_test_anchor':True,'input_text':text,'prompt_text':text,'decoder_text':label,'target_text':label,'bounded_choice_target_label':label,'target':{'bounded_choice_target_label':label,'decoder_text':label,'semantic_value':'PASS_CURRENT_BUILD_AND_RUN'},'opaque_options':opts,'standalone_projection_source':{'projection_mode':'stage11991_pass_build_and_run_transition_probe','observed_verifier_transition':'PASS_CURRENT_BUILD_AND_RUN','selected_verifier_path':selected,'build_observation':build_obs,'test_observation':test_obs,'opaque_options':opts,'gold_label':label,'gold_value':'PASS_CURRENT_BUILD_AND_RUN'},'loss_mask':{'bounded_choice_aux':True,'decoder_ce':True,'structured_aux':True,'transition_projection':True},'anti_cheat':{'deterministic_option_shuffle':True,'singleton_options':False,'target_label_not_visible_before_options':True,'target_value_not_visible_before_options':False,'target_value_visible_as_observed_verifier_result':True,'review_queue_only':True,'not_merged_into_train':True},'stage11991_kind':kind}
def main():
 OUT.mkdir(parents=True,exist_ok=True); TMP.mkdir(parents=True,exist_ok=True); rows=[]; cards=[]
 for root in RUST_ROOTS:
  cwd=Path(root['path']); build=run_cmd(['cargo','check','--quiet'],cwd,90,root['repo_family']+'_cargo_check'); test=run_cmd(['cargo','test','--quiet','--no-fail-fast'],cwd,120,root['repo_family']+'_cargo_test')
  admitted=ok_build(build) and ok_test(test); cards.append({'kind':'rust','repo_family':root['repo_family'],'admitted_candidate':admitted,'build_rc':build['returncode'],'test_rc':test['returncode'],'test_count':test_count(str(test.get('stdout_tail') or '')+str(test.get('stderr_tail') or ''))})
  if admitted: rows.append(make_row('rust_cargo_build_and_test',root['repo_family'],'rust',root['path'],'cargo check + cargo test',build,test))
 for pkg in WEB_PACKAGES:
  cwd=Path('/data/repositories/modelcontextprotocol__typescript-sdk'); safe=pkg.replace('@','at_').replace('/','__')
  build=run_cmd(['pnpm','--dir',str(cwd),'--filter',pkg,'run','typecheck'],cwd,90,safe+'_typecheck'); test=run_cmd(['pnpm','--dir',str(cwd),'--filter',pkg,'run','test'],cwd,90,safe+'_test')
  admitted=ok_build(build) and ok_test(test); cards.append({'kind':'web','package':pkg,'admitted_candidate':admitted,'build_rc':build['returncode'],'test_rc':test['returncode'],'test_count':test_count(str(test.get('stdout_tail') or '')+str(test.get('stderr_tail') or ''))})
  if admitted: rows.append(make_row('web_typecheck_and_test','modelcontextprotocol__typescript-sdk','web_js_ts_html',pkg,f'{pkg}#typecheck+test',build,test))
 write_jsonl(ROWS,rows)
 summary={'stage':11991,'stage_name':'stage11991_pass_build_and_run_transition_probe','created_at_utc':now(),'decision':'pass_build_and_run_probe_complete_review_only','claim_boundary':'review/admission supply only; no model training or promotion claim','summary':{'rows_emitted':len(rows),'language_counts':dict(Counter(r['language_family'] for r in rows)),'status_counts':dict(Counter(r['observed_verifier_transition'] for r in rows)),'repo_family_counts':dict(Counter(r['repo_family'] for r in rows))},'candidate_cards':cards,'outputs':{'summary':rel(SUMMARY),'rows':rel(ROWS),'logs':rel(OUT/'logs')},'next_stage_recommendation':{'stage':'stage11992_pass_build_and_run_admission_audit','action':'Admit only rows with both successful build/typecheck and positive test count; merge into transition support v4.'}}
 write_json(SUMMARY,summary); print(json.dumps({'decision':summary['decision'],'summary':summary['summary'],'next':summary['next_stage_recommendation']},indent=2,sort_keys=True))
if __name__=='__main__': main()
