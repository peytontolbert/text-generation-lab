#!/usr/bin/env python3
from __future__ import annotations
import hashlib,json,os,shlex,shutil,subprocess,time
from pathlib import Path
from collections import Counter
from typing import Any
ROOT=Path(__file__).resolve().parents[1]
STAGE='stage12286_external_repair_replay_smoke_executor'
TARGETS=ROOT/'runs/local/artifacts/stage12285_external_repair_replay_executor_request/default_smoke_targets.jsonl'
ORIGINAL=ROOT/'runs/local/artifacts/stage12244_external_repair_commit_pair_replay_request/replay_targets.jsonl'
WORK_ROOT=Path('/data/tmp/stage12285_external_repair_replay')
OUT=ROOT/f'runs/local/artifacts/{STAGE}'
SUMMARY=ROOT/f'runs/summaries/{STAGE}.json'
TIMEOUT=120

def h(prefix,*parts): return prefix+'_'+hashlib.sha256(json.dumps(parts,sort_keys=True,default=str).encode()).hexdigest()[:20]
def digest_bytes(b:bytes): return hashlib.sha256(b).hexdigest()
def iterj(p):
    with p.open('r',encoding='utf-8') as f:
        for l in f:
            l=l.strip()
            if l: yield json.loads(l)
def run(cmd,cwd,timeout=TIMEOUT,env=None):
    t=time.time()
    try:
        cp=subprocess.run(cmd,cwd=cwd,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=timeout,env=env)
        return {'returncode':cp.returncode,'timed_out':False,'duration_sec':round(time.time()-t,3),'stdout_digest':digest_bytes(cp.stdout),'stderr_digest':digest_bytes(cp.stderr),'stdout_bytes':len(cp.stdout),'stderr_bytes':len(cp.stderr)}
    except subprocess.TimeoutExpired as e:
        return {'returncode':None,'timed_out':True,'duration_sec':round(time.time()-t,3),'stdout_digest':digest_bytes(e.stdout or b''),'stderr_digest':digest_bytes(e.stderr or b''),'stdout_bytes':len(e.stdout or b''),'stderr_bytes':len(e.stderr or b'')}
def status(res):
    if res['timed_out']: return 'TIMEOUT'
    return 'PASS' if res['returncode']==0 else 'FAIL'
def git(repo,args,timeout=60): return run(['git']+args,repo,timeout=timeout)
def checkout(repo,rev):
    git(repo,['reset','--hard'],timeout=60); git(repo,['clean','-fdx'],timeout=60)
    return git(repo,['checkout','--force',rev],timeout=60)
def main():
    WORK_ROOT.mkdir(parents=True,exist_ok=True); OUT.mkdir(parents=True,exist_ok=True)
    original={r['request_id']:r for r in iterj(ORIGINAL)}
    phase_records=[]; candidates=[]; rejects=[]
    env=os.environ.copy(); env['CUDA_VISIBLE_DEVICES']=''; env['PIP_NO_INDEX']='1'; env['HF_HUB_OFFLINE']='1'
    for safe_t in iterj(TARGETS):
        rid=safe_t['request_id']
        t=original.get(rid)
        if not t:
            rejects.append({'request_id':rid,'hard_reject':'original_target_missing'}); continue
        repo_src=Path(t['repo_path']); work=WORK_ROOT/rid
        if work.exists(): shutil.rmtree(work)
        clone=run(['git','clone','--quiet','--no-hardlinks','--no-checkout',str(repo_src),str(work)],ROOT,timeout=120,env=env)
        if status(clone)!='PASS':
            rejects.append({'request_id':rid,'hard_reject':'repo_clone_failed','clone_result':clone}); continue
        before=t['commit_before']; after=t['commit_after']
        if before=='parent':
            rev=run(['git','rev-parse',f'{after}^'],work,timeout=30,env=env)
            before=None # unsupported in this smoke if parent resolution output is not emitted
        cmd=shlex.split(t['verifier_command'])
        # before phase
        checkout(work,before or t['commit_before'])
        before_res=run(cmd,work,timeout=TIMEOUT,env=env); before_status=status(before_res)
        phase_records.append({'request_id':rid,'phase':'before_fail_behavior','status':before_status,'result':before_res,'raw_output_emitted':False})
        if before_status!='FAIL':
            rejects.append({'request_id':rid,'hard_reject':'before_did_not_fail','before_status':before_status}); continue
        # patch phase
        diff_cp=subprocess.run(['git','-C',str(work),'diff','--binary',before or t['commit_before'],after],stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=60)
        patch_digest=digest_bytes(diff_cp.stdout)
        apply_cp=subprocess.run(['git','apply'],cwd=work,input=diff_cp.stdout,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=60)
        if apply_cp.returncode!=0:
            rejects.append({'request_id':rid,'hard_reject':'patch_apply_failed','patch_digest':patch_digest,'apply_stderr_digest':digest_bytes(apply_cp.stderr)}); continue
        patched_res=run(cmd,work,timeout=TIMEOUT,env=env); patched_status=status(patched_res)
        phase_records.append({'request_id':rid,'phase':'before_plus_patch_pass','status':patched_status,'result':patched_res,'raw_output_emitted':False})
        if patched_status!='PASS':
            rejects.append({'request_id':rid,'hard_reject':'before_plus_patch_did_not_pass','patched_status':patched_status,'patch_digest':patch_digest}); continue
        # after phase
        checkout(work,after)
        after_res=run(cmd,work,timeout=TIMEOUT,env=env); after_status=status(after_res)
        phase_records.append({'request_id':rid,'phase':'after_pass','status':after_status,'result':after_res,'raw_output_emitted':False})
        if after_status!='PASS':
            rejects.append({'request_id':rid,'hard_reject':'after_did_not_pass','after_status':after_status,'patch_digest':patch_digest}); continue
        candidates.append({'schema_version':'patch_effect_PE2_candidate_v1','stage':STAGE,'request_id':rid,'repo_family':t['repo_family'],'language_family':t['language_family'],'patch_digest':patch_digest,'verifier_command_digest':h('verifier_command',t['repo_family'],t['verifier_command']),'phase_statuses':{'before_fail_behavior':'FAIL','before_plus_patch_pass':'PASS','after_pass':'PASS'},'admission_level':'PE2_EXECUTED_PHASES','semantic_audit_required':True,'admission':{'train_support_allowed':False,'external_comparable_patch_trace_countable':False,'external_fail_to_pass_countable':False,'strict_eval_eligible':False},'guardrails':{'raw_output_emitted':False,'raw_patch_body_emitted':False,'raw_tool_arguments_emitted':False,'raw_source_path_emitted':False}})
    def wjl(name,rows):
        with (OUT/name).open('w',encoding='utf-8') as f:
            for r in rows: f.write(json.dumps(r,sort_keys=True)+'\n')
    wjl('phase_status_records.jsonl',phase_records); wjl('patch_effect_PE2_candidates.jsonl',candidates); wjl('replay_rejects.jsonl',rejects)
    summary={'stage':STAGE,'decision':'smoke_replay_complete_PE2_candidates_ready_for_semantic_audit' if candidates else 'smoke_replay_complete_zero_PE2','targets_attempted':len(list(iterj(TARGETS))),'phase_records':len(phase_records),'PE2_candidates':len(candidates),'rejects':len(rejects),'candidate_by_language':dict(Counter(c['language_family'] for c in candidates)),'candidate_by_repo':dict(Counter(c['repo_family'] for c in candidates)),'reject_counts':dict(Counter(r['hard_reject'] for r in rejects)),'training_rows_emitted':0,'external_comparable_patch_trace_rows':0,'external_fail_to_pass_rows':0,'next_stage':'stage12287_PE2_semantic_patch_effect_audit'}
    (OUT/'replay_execution_summary.json').write_text(json.dumps(summary,indent=2,sort_keys=True)+'\n',encoding='utf-8')
    (OUT/'EXTERNAL_REPAIR_REPLAY_SMOKE_EXECUTOR_STAGE12286.md').write_text('# Stage12286 External Repair Replay Smoke Executor\n\n'+json.dumps(summary,indent=2)+'\n',encoding='utf-8')
    SUMMARY.parent.mkdir(parents=True,exist_ok=True); SUMMARY.write_text(json.dumps(summary,indent=2,sort_keys=True)+'\n',encoding='utf-8')
if __name__=='__main__': main()
