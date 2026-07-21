#!/usr/bin/env python3
"""Build Stage12284 external repair commit-pair preflight.

Non-mutating preflight over Stage12244 replay targets. Uses git object queries and
diff metadata only; does not checkout, apply patches, execute verifiers, or emit
raw patch bodies.
"""
from __future__ import annotations
import hashlib, json, subprocess, shlex
from collections import Counter
from pathlib import Path
from typing import Any
ROOT=Path(__file__).resolve().parents[1]
STAGE='stage12284_external_repair_commit_pair_preflight'
TARGETS=ROOT/'runs/local/artifacts/stage12244_external_repair_commit_pair_replay_request/replay_targets.jsonl'
OUT=ROOT/f'runs/local/artifacts/{STAGE}'
SUMMARY=ROOT/f'runs/summaries/{STAGE}.json'

def h(prefix,*parts): return prefix+'_'+hashlib.sha256(json.dumps(parts,sort_keys=True,default=str).encode()).hexdigest()[:20]
def iterj(p):
    with p.open('r',encoding='utf-8') as f:
        for l in f:
            l=l.strip()
            if l: yield json.loads(l)
def run(cmd,cwd):
    try:
        cp=subprocess.run(cmd,cwd=cwd,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,timeout=20)
        return cp.returncode,cp.stdout,cp.stderr
    except Exception as e:
        return 999,'',str(e)
def commit_exists(repo,rev):
    rc,out,err=run(['git','rev-parse','--verify',f'{rev}^{{commit}}'],repo)
    return rc==0,out.strip()
def resolve_before(repo,before,after):
    if before=='parent':
        rc,out,err=run(['git','rev-parse',f'{after}^'],repo)
        return (rc==0,out.strip() if rc==0 else None)
    ok,full=commit_exists(repo,before); return ok,full if ok else None
def diff_files(repo,before,after):
    rc,out,err=run(['git','diff','--name-status',before,after],repo)
    if rc!=0: return None,err
    rows=[]
    for line in out.splitlines():
        parts=line.split('\t')
        if len(parts)>=2: rows.append({'status':parts[0],'path_digest':h('path',parts[-1]),'path_tail':parts[-1].split('/')[-1]})
    return rows,None
def path_exists_at(repo,rev,path):
    rc,out,err=run(['git','cat-file','-e',f'{rev}:{path}'],repo)
    return rc==0
def command_paths(cmd):
    toks=shlex.split(cmd)
    return [t for t in toks if ('/' in t or t.endswith(('.py','.js','.rs'))) and not t.startswith('-')]
def classify_diff(files):
    if not files: return 'empty_or_unknown'
    tails=' '.join(f['path_tail'].lower() for f in files)
    if all(('test' in f['path_tail'].lower() or 'spec' in f['path_tail'].lower()) for f in files): return 'test_only'
    if any(t.endswith(('.md','.txt','.rst')) for t in tails.split()):
        if all(t.endswith(('.md','.txt','.rst')) for t in tails.split()): return 'docs_only'
    return 'runtime_code_or_mixed'
def main():
    rows=[]; ready=[]; rejects=[]
    for t in iterj(TARGETS):
        repo=Path(t['repo_path'])
        hard=[]
        repo_exists=repo.exists() and (repo/'.git').exists()
        before_full=after_full=None
        if not repo_exists: hard.append('repo_missing_or_not_git')
        else:
            ok_after,after_full=commit_exists(repo,t['commit_after'])
            if not ok_after: hard.append('commit_after_missing')
            ok_before,before_full=resolve_before(repo,t['commit_before'],t['commit_after']) if ok_after else (False,None)
            if not ok_before: hard.append('commit_before_missing')
        files=[]; diff_error=None; test_paths=[]; test_paths_exist=[]
        if not hard:
            files,diff_error=diff_files(repo,before_full,after_full)
            if diff_error: hard.append('diff_failed')
            dclass=classify_diff(files)
            if dclass in {'test_only','docs_only','empty_or_unknown'}: hard.append(f'diff_{dclass}')
            test_paths=command_paths(t['verifier_command'])
            for p in test_paths:
                test_paths_exist.append({'path_digest':h('test_path',p),'exists_before':path_exists_at(repo,before_full,p),'tail':p.split('/')[-1]})
            if test_paths and not any(x['exists_before'] for x in test_paths_exist): hard.append('selected_test_missing_at_before')
        else:
            dclass='unknown'
        rec={'schema_version':'patch_effect_preflight_v1','stage':STAGE,'request_id':t['request_id'],'repo_family':t['repo_family'],'language_family':t['language_family'],'source_lineage':{'repo_kind':'external_or_other_repo','repo_family_digest':h('repo_family',t['repo_family'],t['repo_path']),'commit_before_digest':h('commit',before_full or t['commit_before']),'commit_after_digest':h('commit',after_full or t['commit_after']),'single_source_proven':repo_exists},'verifier_command_digest':h('verifier_command',t['repo_family'],t['verifier_command']),'verifier_command_head':shlex.split(t['verifier_command'])[0] if t.get('verifier_command') else None,'diff_metadata':{'changed_file_count':len(files or []),'changed_files':files or [],'semantic_diff_class':dclass,'raw_patch_body_emitted':False},'selected_test_refs':test_paths_exist,'preflight_level':'PE1_PRELIGHT_READY' if not hard else 'A0_REJECTED','hard_reject_codes':hard,'admission':{'training_allowed':False,'replay_allowed':not hard,'external_comparable_patch_trace_countable':False,'external_fail_to_pass_countable':False,'strict_eval_eligible':False},'guardrails':{'raw_patch_body_emitted':False,'raw_verifier_output_emitted':False,'raw_source_path_emitted':False}}
        rows.append(rec)
        (ready if not hard else rejects).append(rec)
    summary={'stage':STAGE,'decision':'external_repair_commit_pair_preflight_complete_replay_queue_ready' if ready else 'external_repair_commit_pair_preflight_zero_ready','input_targets':len(rows),'preflight_ready_targets':len(ready),'rejected_targets':len(rejects),'ready_by_language':dict(Counter(r['language_family'] for r in ready)),'ready_by_repo':dict(Counter(r['repo_family'] for r in ready)),'reject_counts':dict(Counter(code for r in rejects for code in r['hard_reject_codes'])),'training_rows_emitted':0,'admitted_rows':0,'external_comparable_patch_trace_rows':0,'external_fail_to_pass_rows':0,'next_stage':'stage12285_external_repair_commit_pair_replay_executor'}
    OUT.mkdir(parents=True,exist_ok=True)
    for name,data in [('preflight_records.jsonl',rows),('replay_ready_targets.jsonl',ready),('preflight_rejects.jsonl',rejects)]:
        with (OUT/name).open('w',encoding='utf-8') as f:
            for r in data: f.write(json.dumps(r,sort_keys=True)+'\n')
    (OUT/'EXTERNAL_REPAIR_COMMIT_PAIR_PREFLIGHT_STAGE12284.md').write_text('# Stage12284 External Repair Commit Pair Preflight\n\n'+json.dumps(summary,indent=2)+'\n',encoding='utf-8')
    (OUT/'external_repair_commit_pair_preflight_summary.json').write_text(json.dumps(summary,indent=2,sort_keys=True)+'\n',encoding='utf-8')
    SUMMARY.parent.mkdir(parents=True,exist_ok=True); SUMMARY.write_text(json.dumps(summary,indent=2,sort_keys=True)+'\n',encoding='utf-8')
if __name__=='__main__': main()
