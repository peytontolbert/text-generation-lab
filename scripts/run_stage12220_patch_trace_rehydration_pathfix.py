#!/usr/bin/env python3
from __future__ import annotations
import hashlib,json,os,shlex,subprocess,time
from collections import Counter
from pathlib import Path
from typing import Any
ROOT=Path(__file__).resolve().parents[1]
STAGE='stage12220_patch_trace_rehydration_pathfix'
OUT=ROOT/'runs/local/artifacts'/STAGE
SUMMARY=ROOT/'runs/summaries'/f'{STAGE}.json'
TIMEOUT=120
CANDIDATES=[
 {'episode_id':'stage12201_episode_4454e7ec6de38e9f','repo_family':'agent-framework','language_family':'python','root_id':'/arxiv/repositories/agent-framework','cwd':'/arxiv/repositories/agent-framework','argv':['python','-m','pytest','-q','-c','/dev/null','-o','cache_dir=/data/tmp/stage12220_pytest_cache','python/packages/ag-ui/tests/ag_ui/golden/test_scenario_workflow.py'],'pythonpath':['/arxiv/repositories/agent-framework/python/packages/core','/arxiv/repositories/agent-framework/python/packages/ag-ui'],'patch_diff_ref':'/data/agentkernel-seq2seq-text-lab/runs/local/artifacts/stage12201_patch_evidence_recovery/diffs/082d75a430798cad03a39ed2cc8a787be6600cd95ba6b1044ddd237af96d0d19.patch'},
 {'episode_id':'stage12201_episode_e547aba70f65a981','repo_family':'agent-governance-toolkit','language_family':'python','root_id':'/arxiv/repositories/agent-governance-toolkit','cwd':'/arxiv/repositories/agent-governance-toolkit/agent-governance-python','argv':['python','-m','pytest','-q','-c','/dev/null','-o','cache_dir=/data/tmp/stage12220_pytest_cache','agent-compliance/tests/test_governance_attestation.py'],'pythonpath':['/arxiv/repositories/agent-governance-toolkit/agent-governance-python/agent-compliance/src'],'patch_diff_ref':'/data/agentkernel-seq2seq-text-lab/runs/local/artifacts/stage12201_patch_evidence_recovery/diffs/3e27b911077c10c2a85670640424238112e58ff0edbbce1a65cea9044cc100d3.patch'},
 {'episode_id':'stage12201_episode_96e2100deb5dca72','repo_family':'autogen','language_family':'python','root_id':'/arxiv/repositories/autogen','cwd':'/arxiv/repositories/autogen','argv':['python','-m','pytest','-q','-c','/dev/null','-o','cache_dir=/data/tmp/stage12220_pytest_cache','python/packages/autogen-core/tests/test_memory.py'],'pythonpath':['/arxiv/repositories/autogen/python/packages/autogen-core/src'],'patch_diff_ref':'/data/agentkernel-seq2seq-text-lab/runs/local/artifacts/stage12201_patch_evidence_recovery/diffs/dbad6ef16f2c51adf048148cba3aca0281af24bc6b9d894c45522bbc52cecb4a.patch'},
 {'episode_id':'stage12201_episode_b9835fda3cb12663','repo_family':'distilabel','language_family':'python','root_id':'/arxiv/repositories/distilabel','cwd':'/arxiv/repositories/distilabel','argv':['python','-m','pytest','-q','-c','/dev/null','-o','cache_dir=/data/tmp/stage12220_pytest_cache','tests/unit/cli/pipeline/test_app.py'],'pythonpath':['/arxiv/repositories/distilabel/src'],'patch_diff_ref':'/data/agentkernel-seq2seq-text-lab/runs/local/artifacts/stage12201_patch_evidence_recovery/diffs/5474d0c47348e391c01b9d72564e63341b99771d33772ce41f1779f531ec04d8.patch'},
]
ENV_BLOCK=['modulenotfounderror','importerror','no module named','not installed','could not find','api key','network','connection','requires']
def sid(prefix,*parts):
 return prefix+'_'+hashlib.sha256('\n'.join(json.dumps(p,sort_keys=True,default=str) for p in parts).encode()).hexdigest()[:16]
def write_jsonl(path,rows):
 path.parent.mkdir(parents=True,exist_ok=True)
 with path.open('w') as f:
  for r in rows:f.write(json.dumps(r,sort_keys=True)+'\n')
def write_json(path,obj):
 path.parent.mkdir(parents=True,exist_ok=True); path.write_text(json.dumps(obj,indent=2,sort_keys=True)+'\n')
def classify(rc,stdout,stderr):
 c=(str(stdout)+'\n'+str(stderr)).lower()
 if rc==0:return 'PASS_CURRENT_STATE'
 if any(x in c for x in ENV_BLOCK):return 'ENV_BLOCKED'
 return 'FAIL_CURRENT_STATE'
def run(c):
 env=os.environ.copy(); env.update({'CUDA_VISIBLE_DEVICES':'','PYTHONDONTWRITEBYTECODE':'1','HF_HUB_OFFLINE':'1','TRANSFORMERS_OFFLINE':'1','WANDB_DISABLED':'true','OPENAI_API_KEY':'','ANTHROPIC_API_KEY':''})
 env['PYTHONPATH']=':'.join(c['pythonpath']+[env.get('PYTHONPATH','')])
 st=time.time()
 try:
  p=subprocess.run(c['argv'],cwd=c['cwd'],env=env,text=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=TIMEOUT)
  return {'candidate':c,'returncode':p.returncode,'stdout':p.stdout[-4000:],'stderr':p.stderr[-4000:],'duration_sec':round(time.time()-st,3),'pythonpath':c['pythonpath']}
 except subprocess.TimeoutExpired as e:
  return {'candidate':c,'returncode':124,'stdout':str(e.stdout or '')[-4000:],'stderr':(str(e.stderr or '')+'\nTIMEOUT')[-4000:],'duration_sec':round(time.time()-st,3),'pythonpath':c['pythonpath']}
def rec(o):
 c=o['candidate']; t=classify(o['returncode'],o['stdout'],o['stderr'])
 if t=='ENV_BLOCKED': return None
 eid=sid('stage12220_episode',c['episode_id'],o['returncode'],o['stdout'],o['stderr']); cmd=sid('stage12220_command',eid)
 return {'episode_id':eid,'source_stage':STAGE,'source_stage12201_episode_id':c['episode_id'],'admission_level_effective':'level_3_single_step_closed_loop_with_patch_context_verifier_observation','root_id':c['root_id'],'repo_family':c['repo_family'],'language_family':c['language_family'],'split':'train_support','patch_trace':{'has_patch_trace':True,'patch_diff':c['patch_diff_ref'],'patch_apply_evidence':'not_applied_by_stage12220_pathfix_smoke','counts_toward_patch_trace_floor':False},'candidate_action_set':{'candidate_set_id':sid('stage12220_candidates',eid),'chosen_action_id':'A' if t=='PASS_CURRENT_STATE' else 'B','candidate_actions':[{'action_id':'A','action_type':'VERIFY','role':'PASS_CURRENT_STATE','is_chosen':t=='PASS_CURRENT_STATE'},{'action_id':'B','action_type':'VERIFY','role':'FAIL_CURRENT_STATE','is_chosen':t=='FAIL_CURRENT_STATE'},{'action_id':'C','action_type':'ABSTAIN','role':'INSUFFICIENT_EVIDENCE','is_chosen':False}]},'candidate_action_count':3,'chosen_action':{'action_type':'VERIFY','role':t},'command_result':{'command_result_id':cmd,'command':' '.join(shlex.quote(x) for x in c['argv']),'cwd':c['cwd'],'returncode':o['returncode'],'duration_sec':o['duration_sec'],'stdout_tail':o['stdout'],'stderr_tail':o['stderr'],'pythonpath':o['pythonpath']},'verifier_status':t,'verifier_transition':t,'verifier_result':{'verifier_status':t,'verifier_transition':t,'command_text':' '.join(shlex.quote(x) for x in c['argv']),'cwd':c['cwd'],'exit_code':o['returncode'],'stdout_excerpt':o['stdout'],'stderr_excerpt':o['stderr'],'runnable_verifier_proof':t=='PASS_CURRENT_STATE'},'state_before':{'root_id':c['root_id'],'known_facts':['same-source patch diff exists','pathfix verifier command selected']},'state_after':{'root_id':c['root_id'],'verifier_transition':t,'new_facts':[f'pathfix verifier observed {t}']},'ordered_events':['STATE_BEFORE','VERIFY','COMMAND_OBSERVATION','VERIFIER_RESULT','STATE_AFTER','STOP_CONTINUE_DECISION'],'stop_decision':{'continue_or_stop':'CONTINUE','reason':'pathfix smoke is evidence, not clean replay acceptance'},'train_support_only':True,'strict_eval_eligible':False,'source_heldout_admissible':False,'training_allowed':False}
def main():
 obs=[run(c) for c in CANDIDATES]
 records=[]; diag=[]
 for o in obs:
  r=rec(o)
  if r: records.append(r)
  else: diag.append(o)
 OUT.mkdir(parents=True,exist_ok=True)
 write_jsonl(OUT/'pathfix_observations.jsonl',obs); write_jsonl(OUT/'pathfix_rehydrated_records.jsonl',records); write_jsonl(OUT/'pathfix_diagnostics.jsonl',diag)
 summary={'stage':STAGE,'decision':'pathfix_records_materialized' if records else 'blocked_no_pathfix_records','candidate_count':len(CANDIDATES),'record_count':len(records),'diagnostic_count':len(diag),'transition_counts':dict(Counter(r['verifier_transition'] for r in records)),'diagnostic_transition_counts':dict(Counter(classify(o['returncode'],o['stdout'],o['stderr']) for o in diag)),'language_counts':dict(Counter(r['language_family'] for r in records)),'tests_executed':True,'training_allowed':False,'gpu_policy':'CUDA_VISIBLE_DEVICES empty; CPU-only commands','claim_boundary':'Pathfix smoke only. Patch diff was not applied/replayed; records do not count toward strict patch-trace floor.','artifact_paths':{'records':str(OUT/'pathfix_rehydrated_records.jsonl'),'observations':str(OUT/'pathfix_observations.jsonl'),'diagnostics':str(OUT/'pathfix_diagnostics.jsonl')}}
 write_json(OUT/'summary.json',summary); write_json(SUMMARY,summary); print(json.dumps(summary,indent=2,sort_keys=True))
if __name__=='__main__': main()
