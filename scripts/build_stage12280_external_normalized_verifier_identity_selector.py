#!/usr/bin/env python3
"""Build Stage12280 external normalized verifier identity selector."""
from __future__ import annotations
import hashlib,json,re
from collections import Counter,defaultdict
from pathlib import Path
from typing import Any
ROOT=Path(__file__).resolve().parents[1]
STAGE='stage12280_external_normalized_verifier_identity_selector'
CODEX=Path('/home/peyton/.codex/sessions')
PROFILES=ROOT/'runs/local/artifacts/stage12263_high_value_window_profiler/source_shard_profiles.jsonl'
PAIRS=ROOT/'runs/local/artifacts/stage12259_codex_tool_call_observation_pairer/tool_call_observation_pairs.jsonl'
MANIFEST=ROOT/'runs/local/artifacts/stage12258_live_codex_chat_reconstruction_index/per_chat_manifest.jsonl'
OUT=ROOT/f'runs/local/artifacts/{STAGE}'
SUMMARY=ROOT/f'runs/summaries/{STAGE}.json'
SELF={'agentkernel-seq2seq-text-lab','parameter-golf'}
VERIFY={'pytest','ctest','cargo','npm','pnpm','yarn','node','npx','make','cmake','python','python3','vitest','tsc'}
INSPECT={'rg','grep','find','sed','cat','ls','jq','tail','head','nl','git','pwd'}

def h(prefix,*parts): return prefix+'_'+hashlib.sha256(json.dumps(parts,sort_keys=True,default=str).encode()).hexdigest()[:20]
def sha1(s): return hashlib.sha1(s.encode()).hexdigest()
def iterj(p):
    with p.open('r',encoding='utf-8',errors='ignore') as f:
        for line in f:
            line=line.strip()
            if line: yield json.loads(line)
def write_json(p,v): p.parent.mkdir(parents=True,exist_ok=True); p.write_text(json.dumps(v,indent=2,sort_keys=True)+'\n',encoding='utf-8')
def write_jsonl(p,rows):
    p.parent.mkdir(parents=True,exist_ok=True)
    with p.open('w',encoding='utf-8') as f:
        for r in rows: f.write(json.dumps(r,sort_keys=True)+'\n')
def path_family(path): return (path or '').rstrip('/').split('/')[-1] or 'unknown'
def lang(fam,heads):
    ks=set(heads)
    if {'cargo','rustc'}&ks: return 'rust'
    if {'npm','npx','pnpm','yarn','node','tsc','vitest'}&ks or fam in {'bddy','staticpeytonsite','website'}: return 'web_js_ts_html'
    if {'cmake','make','gcc','g++','cc','ctest'}&ks: return 'c_cpp'
    return 'python'
def chat_roots():
    out={}
    for r in iterj(MANIFEST):
        cwd=None
        if r.get('workspace_root_hints_top'): cwd=r['workspace_root_hints_top'][0][0]
        elif r.get('cwd_hints_top'): cwd=r['cwd_hints_top'][0][0]
        fam=path_family(cwd)
        out[r['chat_id']]={'repo_family_label':fam,'repo_family_digest':h('repo_family',cwd or r['chat_id']),'cwd_hint_digest':h('cwd_hint',cwd or r['chat_id']),'repo_kind':'self_research_repo' if fam in SELF else 'external_or_other_repo','language_family_hint':lang(fam,r.get('command_head_counts') or {}),'raw_cwd_path_emitted':False}
    return out
def raw_paths():
    out={}
    for p in CODEX.rglob('*.jsonl') if CODEX.exists() else []:
        if p.is_file(): out[sha1(str(p))]=p
    return out
def load_line(p,line):
    if not p or line<=0: return None
    with p.open('rb') as f:
        for i,raw in enumerate(f,1):
            if i==line:
                try: return json.loads(raw.decode('utf-8',errors='ignore'))
                except Exception: return None
            if i>line: break
    return None
def args_from_obj(o):
    if not isinstance(o,dict): return {}
    payload=o.get('payload') if isinstance(o.get('payload'),dict) else {}
    a=payload.get('arguments')
    if isinstance(a,str):
        try: return json.loads(a)
        except Exception: return {}
    return a if isinstance(a,dict) else {}
def output_from_obj(o):
    if not isinstance(o,dict): return ''
    payload=o.get('payload') if isinstance(o.get('payload'),dict) else {}
    v=payload.get('output')
    if isinstance(v,str): return v
    return '' if v is None else json.dumps(v,sort_keys=True,default=str)
def status(text):
    s=text.lower()
    if not s.strip(): return 'UNKNOWN_EMPTY'
    if re.search(r'(process exited with code|exit code|returncode)[:= ]+0\b',s):
        return 'PASS_WITH_FAILURE_TEXT_REVIEW' if re.search(r'\b(failed|failure|traceback|assertionerror)\b',s) else 'PASS'
    if re.search(r'(process exited with code|exit code|returncode)[:= ]+(?!0\b)\d+',s): return 'FAIL'
    if re.search(r'\b(\d+ failed|failed tests?|failure|assertionerror|traceback|error:)\b',s): return 'FAIL'
    if re.search(r'\b(all tests passed|passed\b|success|ok\b)',s): return 'PASS_WEAK'
    return 'UNKNOWN'
def normalize_cmd(cmd):
    cmd=str(cmd or '').strip()
    cmd=re.sub(r'--max[_-]?output[_-]?tokens\s+\S+','',cmd)
    cmd=re.sub(r'--yield[_-]?time[_-]?ms\s+\S+','',cmd)
    cmd=re.sub(r'\s+',' ',cmd)
    return cmd
def action(tool,head):
    if tool=='apply_patch': return 'patch'
    head=head or ''
    if head in INSPECT: return 'inspect'
    if head in VERIFY or 'test' in head or 'pytest' in head: return 'verify'
    return 'run'
def pair_ref(row): return h('tool_pair_ref',row.get('chat_id'),row.get('call_id'),int(row.get('call_line_number') or 0),int(row.get('output_line_number') or 0))
def build_pairs(raw_index):
    by_chat=defaultdict(list)
    for r in iterj(PAIRS):
        chat=r.get('chat_id'); ref=pair_ref(r); call=int(r.get('call_line_number') or 0); out=int(r.get('output_line_number') or 0)
        rec={'tool_pair_ref':ref,'chat_id':chat,'tool_name':r.get('tool_name'),'command_head':r.get('command_head'),'action_type':action(r.get('tool_name'),r.get('command_head')),'call_line_number':call,'output_line_number':out,'output_digest':r.get('output_digest'),'arguments_digest':r.get('arguments_digest')}
        by_chat[chat].append(rec)
    for rows in by_chat.values(): rows.sort(key=lambda x:(x['call_line_number'],x['output_line_number']))
    return by_chat
def profile_ok(r): return not r.get('exclusion_codes') and r.get('audit_bucket')=='patch_verify_loop' and r.get('recommended_parser_mode')=='line_window' and int(r.get('patch_signal_count') or 0)>=1 and int(r.get('verifier_command_count') or 0)>=1
def bucket(n): return 'H1' if n<=1 else ('H2_3' if n<=3 else ('H4_8' if n<=8 else 'H9_PLUS'))
def main():
    roots=chat_roots(); raws=raw_paths(); pairs=build_pairs(raws)
    # Attach normalized identities/statuses lazily per chat.
    enriched={}
    profiles=[r for r in iterj(PROFILES) if profile_ok(r)]
    candidates=[]; counters=Counter(); repo=Counter(); horizon=Counter(); langc=Counter()
    for pr in profiles:
        root=roots.get(pr.get('chat_id'),{})
        if root.get('repo_kind')!='external_or_other_repo': continue
        raw=raws.get(pr.get('source_file_hash_compat'))
        start=int(pr.get('line_start') or 0); end=int(pr.get('line_end') or 0)
        acts=[a.copy() for a in pairs.get(pr.get('chat_id'),[]) if start<=a['call_line_number']<=end]
        if not acts: continue
        for a in acts:
            key=a['tool_pair_ref']
            if key not in enriched:
                obj_call=load_line(raw,a['call_line_number']) if raw else None
                obj_out=load_line(raw,a['output_line_number']) if raw else None
                args=args_from_obj(obj_call)
                cmd=normalize_cmd(args.get('cmd'))
                ident=h('verifier_identity',root.get('repo_family_digest'),a.get('command_head'),cmd) if a['action_type']=='verify' else None
                enriched[key]={'verifier_identity_digest':ident,'status':status(output_from_obj(obj_out)),'raw_output_emitted':False,'raw_arguments_emitted':False,'raw_path_emitted':False}
            a.update(enriched[key])
        patches=[i for i,a in enumerate(acts) if a['action_type']=='patch']
        for po,pi in enumerate(patches):
            prev_out=acts[patches[po-1]]['output_line_number'] if po>0 else start-1
            next_call=acts[patches[po+1]]['call_line_number'] if po+1<len(patches) else end+1
            pre=[a for a in acts if a['action_type']=='verify' and prev_out<a['call_line_number']<acts[pi]['call_line_number']]
            post=[a for a in acts if a['action_type']=='verify' and acts[pi]['output_line_number']<a['call_line_number']<next_call]
            if not pre or not post: continue
            pre_ids={a.get('verifier_identity_digest') for a in pre if a.get('verifier_identity_digest')}
            post_ids={a.get('verifier_identity_digest') for a in post if a.get('verifier_identity_digest')}
            match=pre_ids & post_ids
            if not match: continue
            mid=sorted(match)[0]
            pre_m=[a for a in pre if a.get('verifier_identity_digest')==mid]
            post_m=[a for a in post if a.get('verifier_identity_digest')==mid]
            pre_fail=any(a.get('status')=='FAIL' for a in pre_m)
            post_pass=any(a.get('status') in {'PASS','PASS_WEAK','PASS_WITH_FAILURE_TEXT_REVIEW'} for a in post_m)
            post_fail=any(a.get('status')=='FAIL' for a in post_m)
            if not (pre_fail and post_pass and not post_fail): continue
            rec={'schema_version':'normalized_exact_verifier_candidate_v1','stage':STAGE,'candidate_id':h('norm_exact_candidate',pr.get('task_window_id'),acts[pi]['tool_pair_ref'],mid),'source_refs':{'chat_id':pr.get('chat_id'),'task_window_id':pr.get('task_window_id'),'snapshot_id':pr.get('snapshot_id'),'source_file_hash_compat':pr.get('source_file_hash_compat'),'line_start':pr.get('line_start'),'line_end':pr.get('line_end')},'root_recovery':root,'patch_ref':{'tool_pair_ref':acts[pi]['tool_pair_ref'],'output_digest':acts[pi].get('output_digest'),'raw_patch_body_emitted':False},'matched_verifier_identity_digest':mid,'pre_verifier_refs':[{'tool_pair_ref':a['tool_pair_ref'],'command_head':a.get('command_head'),'status':a.get('status'),'output_digest':a.get('output_digest')} for a in pre_m[-3:]],'post_verifier_refs':[{'tool_pair_ref':a['tool_pair_ref'],'command_head':a.get('command_head'),'status':a.get('status'),'output_digest':a.get('output_digest')} for a in post_m[:8]],'horizon_bucket':bucket(len(post_m)),'deterministic_gates':{'external_repo_hint':True,'normalized_same_verifier_identity':True,'observed_pre_patch_failure':True,'observed_post_patch_pass':True,'no_post_failure_for_matched_identity':True,'semantic_verifier_relevance_proven':False},'admission':{'semantic_review_required':True,'train_support_allowed':False,'strict_eval_eligible':False,'external_comparable_patch_trace_countable':False,'external_fail_to_pass_countable':False},'guardrails':{'raw_output_emitted':False,'raw_tool_arguments_emitted':False,'raw_patch_body_emitted':False,'raw_source_path_emitted':False}}
            candidates.append(rec); repo[root.get('repo_family_label')]+=1; horizon[rec['horizon_bucket']]+=1; langc[root.get('language_family_hint')]+=1
    write_jsonl(OUT/'normalized_exact_verifier_candidates.jsonl',candidates)
    summary={'stage':STAGE,'decision':'normalized_exact_verifier_candidates_ready_for_semantic_review_no_admission','candidate_count':len(candidates),'repo_family_counts':dict(repo),'language_counts':dict(langc),'horizon_counts':dict(horizon),'training_rows_emitted':0,'admitted_rows':0,'external_comparable_patch_trace_rows':0,'external_fail_to_pass_rows':0,'next_stage':'stage12281_semantic_review_packet_normalized_exact_verifiers'}
    write_json(SUMMARY,summary); write_json(OUT/'normalized_exact_verifier_selector_summary.json',summary)
    (OUT/'NORMALIZED_VERIFIER_IDENTITY_SELECTOR_STAGE12280.md').write_text('# Stage12280 Normalized Verifier Identity Selector\n\n'+json.dumps(summary,indent=2)+'\n',encoding='utf-8')
if __name__=='__main__': main()
