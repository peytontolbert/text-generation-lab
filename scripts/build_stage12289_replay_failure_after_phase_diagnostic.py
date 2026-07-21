#!/usr/bin/env python3
from __future__ import annotations
import hashlib,json,os,shlex,shutil,subprocess,time
from pathlib import Path
from collections import Counter
ROOT=Path(__file__).resolve().parents[1]
STAGE='stage12289_replay_failure_after_phase_diagnostic'
ORIGINAL=ROOT/'runs/local/artifacts/stage12244_external_repair_commit_pair_replay_request/replay_targets.jsonl'
REJECTS=[ROOT/'runs/local/artifacts/stage12286_external_repair_replay_smoke_executor/replay_rejects.jsonl',ROOT/'runs/local/artifacts/stage12288_external_repair_replay_second_smoke_executor/replay_rejects.jsonl']
WORK=Path('/data/tmp/stage12289_replay_failure_after_phase')
OUT=ROOT/f'runs/local/artifacts/{STAGE}'
SUMMARY=ROOT/f'runs/summaries/{STAGE}.json'
TIMEOUT=120
def dig(b): return hashlib.sha256(b).hexdigest()
def iterj(p):
    if not p.exists(): return
    with p.open('r',encoding='utf-8') as f:
        for l in f:
            l=l.strip()
            if l: yield json.loads(l)
def run(cmd,cwd,timeout=TIMEOUT,env=None):
    t=time.time()
    try:
        cp=subprocess.run(cmd,cwd=cwd,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=timeout,env=env)
        return {'returncode':cp.returncode,'timed_out':False,'duration_sec':round(time.time()-t,3),'stdout_digest':dig(cp.stdout),'stderr_digest':dig(cp.stderr),'stdout_bytes':len(cp.stdout),'stderr_bytes':len(cp.stderr)}
    except subprocess.TimeoutExpired as e:
        return {'returncode':None,'timed_out':True,'duration_sec':round(time.time()-t,3),'stdout_digest':dig(e.stdout or b''),'stderr_digest':dig(e.stderr or b''),'stdout_bytes':len(e.stdout or b''),'stderr_bytes':len(e.stderr or b'')}
def status(r): return 'TIMEOUT' if r['timed_out'] else ('PASS' if r['returncode']==0 else 'FAIL')
def git(repo,args,timeout=60): return run(['git']+args,repo,timeout=timeout)
def checkout(repo,rev): git(repo,['reset','--hard'],60); git(repo,['clean','-fdx'],60); return git(repo,['checkout','--force',rev],60)
def main():
    orig={r['request_id']:r for r in iterj(ORIGINAL)}
    ids=[]
    for p in REJECTS:
        for r in iterj(p) or []:
            if r.get('hard_reject')=='before_plus_patch_did_not_pass': ids.append(r['request_id'])
    ids=sorted(set(ids))
    WORK.mkdir(parents=True,exist_ok=True); OUT.mkdir(parents=True,exist_ok=True)
    env=os.environ.copy(); env['CUDA_VISIBLE_DEVICES']=''; env['PIP_NO_INDEX']='1'; env['HF_HUB_OFFLINE']='1'
    rows=[]
    for rid in ids:
        t=orig[rid]; repo_src=Path(t['repo_path']); work=WORK/rid
        if work.exists(): shutil.rmtree(work)
        clone=run(['git','clone','--quiet','--no-hardlinks','--no-checkout',str(repo_src),str(work)],ROOT,120,env)
        if status(clone)!='PASS':
            rows.append({'request_id':rid,'after_status':'UNKNOWN_CLONE_FAILED','raw_output_emitted':False}); continue
        after=t['commit_after']; cmd=shlex.split(t['verifier_command'])
        checkout(work,after)
        res=run(cmd,work,TIMEOUT,env); st=status(res)
        rows.append({'request_id':rid,'repo_family':t['repo_family'],'language_family':t['language_family'],'after_status':st,'after_result':res,'raw_output_emitted':False})
    with (OUT/'after_phase_diagnostics.jsonl').open('w',encoding='utf-8') as f:
        for r in rows: f.write(json.dumps(r,sort_keys=True)+'\n')
    summary={'stage':STAGE,'decision':'after_phase_diagnostic_complete','patched_fail_targets_checked':len(rows),'after_status_counts':dict(Counter(r['after_status'] for r in rows)),'targets_where_after_passed':[r['request_id'] for r in rows if r['after_status']=='PASS'],'targets_where_after_failed_or_timeout':[r['request_id'] for r in rows if r['after_status']!='PASS'],'interpretation':'If after also fails, Stage12244 target/verifier is not locally replayable as PE2 under current environment. If after passes while before_plus_patch failed, executor patch application/replay needs repair.','training_rows_emitted':0,'admitted_rows':0,'next_stage':'stage12290_replay_queue_repair_or_retarget_decision'}
    (OUT/'after_phase_diagnostic_summary.json').write_text(json.dumps(summary,indent=2,sort_keys=True)+'\n',encoding='utf-8')
    (OUT/'REPLAY_FAILURE_AFTER_PHASE_DIAGNOSTIC_STAGE12289.md').write_text('# Stage12289 Replay Failure After Phase Diagnostic\n\n'+json.dumps(summary,indent=2)+'\n',encoding='utf-8')
    SUMMARY.parent.mkdir(parents=True,exist_ok=True); SUMMARY.write_text(json.dumps(summary,indent=2,sort_keys=True)+'\n',encoding='utf-8')
if __name__=='__main__': main()
