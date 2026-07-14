#!/usr/bin/env python3
from __future__ import annotations
import hashlib, json, time
from collections import Counter
from pathlib import Path
from typing import Any
ROOT=Path(__file__).resolve().parents[1]
ART=ROOT/'runs/local/artifacts'
STAGE=11338; NAME='stage11338_web_source_snippet_evidence_materialization'
OUT=ART/NAME; SUMMARY=OUT/'web_source_snippet_evidence_materialization.json'
READY=ART/'stage11331_rust_web_gap_recovery_manifest/web_ready_candidate_queue.jsonl'
REPO=Path('/data/tmp/stage11338_sphinx_source')
OUT_ROWS=OUT/'web_source_snippet_evidence_rows.jsonl'; OUT_BLOCKED=OUT/'web_source_snippet_evidence_blocked.jsonl'
LABELS=list('ABCDEFGH')
ROLE_CLASS={'verifier_and_test_constraint':'DECISIVE_VERIFIER_TEST_CONSTRAINT','candidate_change_surface':'SUPPORTING_CANDIDATE_CHANGE_SURFACE','symptom_or_call_path_analogue':'SUPPORTING_SYMPTOM_OR_CALL_PATH'}
TASKS={
 'verifier_and_test_constraint':'Task: Choose the evidence item containing concrete selected-test, fixture, expected-output, assertion, or verifier evidence.',
 'candidate_change_surface':'Task: Choose the evidence item containing the changed implementation, source, configuration, fixture, or artifact surface.',
 'symptom_or_call_path_analogue':'Task: Choose the evidence item containing symptom, runtime behavior, call-path, or failure-context evidence.',
}

def now(): return time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
def rel(p:Path): return str(p.relative_to(ROOT)) if str(p).startswith(str(ROOT)) else str(p)
def readl(p): return [json.loads(l) for l in p.read_text().splitlines() if l.strip()] if p.exists() else []
def writel(p,rows): p.parent.mkdir(parents=True,exist_ok=True); p.write_text(''.join(json.dumps(r,sort_keys=True)+'\n' for r in rows))
def writej(p,o): p.parent.mkdir(parents=True,exist_ok=True); p.write_text(json.dumps(o,indent=2,sort_keys=True)+'\n')
def snippet(path:str, max_lines:int=18)->str:
    f=REPO/path
    if not f.exists(): return ''
    lines=f.read_text(errors='replace').splitlines()
    # Prefer lines that contain search/test/assert/index terms when available.
    anchors=[i for i,l in enumerate(lines) if any(tok in l.lower() for tok in ['search','assert','index','fixture','cpp','meta','keyword'])]
    start=max(0,(anchors[0] if anchors else 0)-2)
    part=lines[start:start+max_lines]
    return f'{path} lines {start+1}-{start+len(part)}:\n'+'\n'.join(part)
def compact(paths:list[str], max_items:int=2)->list[str]:
    return [str(x) for x in paths if str(x).strip()][:max_items]
def make_items(row:dict[str,Any])->list[dict[str,str]]:
    items=[]
    changed=[]
    for p in compact(row.get('candidate_change_surface_paths') or [],2):
        s=snippet(p)
        if s: changed.append(s)
    if changed:
        items.append({'role':'candidate_change_surface','text':'Changed/source evidence:\n'+'\n---\n'.join(changed)})
    verifier=[]
    preferred=[]
    for p in row.get('verifier_and_test_constraint_paths') or []:
        if p.endswith('searchindex.js') or p.endswith('index.rst'):
            preferred.append(p)
    for p in compact(preferred or (row.get('verifier_and_test_constraint_paths') or []),2):
        s=snippet(p)
        if s: verifier.append(s)
    if verifier:
        items.append({'role':'verifier_and_test_constraint','text':'Selected verifier/fixture evidence:\n'+'\n---\n'.join(verifier)})
    syms=', '.join((row.get('symptom_or_call_path_analogue_paths') or row.get('key_symbols') or [])[:10])
    if syms:
        items.append({'role':'symptom_or_call_path_analogue','text':'Runtime/call-path context symbols from source inventory: '+syms})
    return items

def main():
    rows=[]; blocked=[]; OUT.mkdir(parents=True,exist_ok=True)
    for src in readl(READY):
        if src.get('language_family')!='web_js_ts_html': continue
        items=make_items(src); roles={i['role'] for i in items}; root=str(src.get('root_id'))
        if not {'candidate_change_surface','verifier_and_test_constraint'}.issubset(roles):
            blocked.append({'root_id':root,'repo_family':src.get('repo_family'),'blockers':['missing_source_snippet_for_changed_or_verifier'],'roles':sorted(roles)})
            continue
        for desired in sorted(roles):
            seed=hashlib.sha256(f'{STAGE}:{root}:{desired}'.encode()).hexdigest()
            records=[]; evidence=[]
            for idx,item in enumerate(items):
                eid=f'E{idx+1:02d}'; value=f'{eid}. {item["text"][:1600]}'
                evidence.append(value); records.append((idx,eid,item,value))
            records=sorted(records,key=lambda rec: hashlib.sha256((seed+rec[1]).encode()).hexdigest())
            opts=[]; target=''
            for oi,(orig,eid,item,value) in enumerate(records):
                label=LABELS[oi]
                opts.append({'label':label,'value':value,'semantic_candidate':{'schema_version':'stage11338_web_source_snippet_evidence_v1','candidate_label':label,'candidate_value_family':'web_source_snippet_evidence_item','option_index':oi,'task_type':'evidence_citation','evidence_role':item['role'],'test_id':eid,'verifier_transition':'NONE','value_token_count_proxy':len(value.split())}})
                if item['role']==desired: target=label
            text='\n'.join(['Language: web_js_ts_html','Perspective: evidence_citation',TASKS[desired],f'Repository family: {src.get("repo_family")}',f'Execution route: {src.get("execution_route")}',f'Source repository snapshot: {REPO}','Visible evidence items:',*evidence,'Options:',*[f'{o["label"]}. {o["value"]}' for o in opts],'Answer:'])
            rows.append({'row_id':f'stage11338::{root}::{ROLE_CLASS[desired]}','root_id':root,'source_root_id':src.get('source_root_id'),'root_lineage_key':src.get('root_lineage_key'),'source_row_id':src.get('source_row_id'),'repo_family':src.get('repo_family'),'repo_id':src.get('repo_id'),'language_family':'web_js_ts_html','task_type':'evidence_citation','split':'train','package_split':'train','strict_eval_eligible':False,'train_support_only':True,'input_text':text,'prompt_text':text,'decoder_text':target,'target_text':target,'bounded_choice_target_label':target,'semantic_target_value':desired,'opaque_options':opts,'standalone_projection_source':{'projection_mode':'web_source_snippet_evidence_item_selection','gold_value':desired,'source_target_class':ROLE_CLASS[desired],'opaque_options':opts,'source_candidate':src,'evidence_items_hidden_role_metadata':items,'source_repo_path':str(REPO)},'expected_enabled_loss':'decoder_ce','loss_mask':{'decoder_ce':True},'anti_cheat':{'role_alias_options_removed':True,'source_snippets_materialized':True,'deterministic_option_shuffle':True,'gold_label_not_in_prompt_before_options':True,'support_only_not_promotable':True}})
    writel(OUT_ROWS,rows); writel(OUT_BLOCKED,blocked)
    summary={'stage':STAGE,'stage_name':NAME,'created_at_utc':now(),'passed':bool(rows),'decision':'web_source_snippet_evidence_rows_materialized_support_only' if rows else 'web_source_snippet_evidence_materialization_blocked','counts':{'rows':len(rows),'roots':len({r['root_id'] for r in rows}),'by_gold':dict(sorted(Counter(r['semantic_target_value'] for r in rows).items())),'by_repo':dict(sorted(Counter(r['repo_family'] for r in rows).items())),'blocked':len(blocked)},'admissibility':{'train_support_only':True,'promotable_eval':False,'reason':'Rows contain real source snippets from a current shallow clone, but no locked historical commit or executed verifier output; use as support only.'},'source_artifacts':{'web_ready_candidate_queue':rel(READY),'sphinx_clone':str(REPO)},'outputs':{'rows':rel(OUT_ROWS),'blocked':rel(OUT_BLOCKED),'summary':rel(SUMMARY)},'recommended_next_action':'score Stage11200 on source-snippet Web rows; only run a canary-preserving diagnostic if baseline is weak.'}
    writej(SUMMARY,summary); print(json.dumps(summary,indent=2,sort_keys=True))
if __name__=='__main__': main()
