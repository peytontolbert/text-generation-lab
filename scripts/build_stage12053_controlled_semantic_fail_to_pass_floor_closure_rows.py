#!/usr/bin/env python3
"""Create controlled semantic FAIL_TO_PASS floor-closure rows across four languages."""
from __future__ import annotations

import hashlib, json, os, shutil, subprocess, time
from collections import Counter
from pathlib import Path
from typing import Any

ROOT=Path('runs/local/artifacts/stage12053_controlled_semantic_fail_to_pass_floor_closure_rows').resolve()
FIXTURE_ROOT=ROOT/'fixture_repos'
ROWS=ROOT/'controlled_semantic_fail_to_pass_floor_closure_rows.jsonl'
SUMMARY=ROOT/'controlled_semantic_fail_to_pass_floor_closure_rows.json'
SUMMARY_MIRROR=Path('runs/summaries/stage12053_controlled_semantic_fail_to_pass_floor_closure_rows.json')
LABELS=list('ABCDEFGH')
TRANSITION_TEXT={
 'PASS_TO_PASS':'focused verifier executed from local source and passed',
 'PASS_CURRENT_BUILD_AND_RUN':'build and runnable verifier both passed',
 'PASS_CURRENT_BUILD':'build or collection passed but runnable verifier body did not execute',
 'FAIL_TO_PASS':'controlled broken state failed and restored or repaired source passed',
 'NOT_EXERCISED':'command did not exercise or collect the selected verifier',
 'INSUFFICIENT_EVIDENCE':'environment is underhydrated so no trustworthy transition is available',
 'FAIL_TO_FAIL':'verifier failed in the current local source state',
 'VERIFIER_REMOVED':'verifier evidence was removed and the row should abstain',
}

def py_fixture(i,name,src,test,old,new):
 return {'id':f'python_{i}_{name}','language_family':'python','repo_family':'stage12053_python_semantic_fixture','files':{'logic.py':src,'test_logic.py':test},'command':['python','-m','pytest','-q','-c','/dev/null','test_logic.py'],'source_file':'logic.py','find':old,'replace':new,'selected_verifier_path':f'test_logic.py::{name}'}
def cpp_fixture(i,name,src,test,old,new):
 return {'id':f'cpp_{i}_{name}','language_family':'c_cpp','repo_family':'stage12053_cpp_semantic_fixture','files':{'logic.hpp':src,'test_logic.cpp':test},'command':['bash','-lc','g++ -std=c++17 test_logic.cpp -o test_logic && ./test_logic'],'source_file':'logic.hpp','find':old,'replace':new,'selected_verifier_path':f'test_logic.cpp::{name}'}
def rust_fixture(i,name,src,old,new):
 return {'id':f'rust_{i}_{name}','language_family':'rust','repo_family':'stage12053_rust_semantic_fixture','files':{'Cargo.toml':f'[package]\nname="stage12053_rust_{i}"\nversion="0.1.0"\nedition="2021"\n','src/lib.rs':src},'command':['conda','run','-n','trellis','cargo','test','--quiet'],'source_file':'src/lib.rs','find':old,'replace':new,'selected_verifier_path':f'cargo test --quiet {name}'}
def js_fixture(i,name,src,test,old,new):
 return {'id':f'web_{i}_{name}','language_family':'web_js_ts_html','repo_family':'stage12053_web_semantic_fixture','files':{'package.json':'{"type":"module","scripts":{"test":"node test_logic.js"}}\n','logic.js':src,'test_logic.js':test},'command':['npm','test','--','--silent'],'source_file':'logic.js','find':old,'replace':new,'selected_verifier_path':f'npm test -- --silent {name}'}

FIXTURES=[
 py_fixture(1,'zero_timeout_preserved','def normalize_timeout(v):\n    return v\n','from logic import normalize_timeout\ndef test_zero_timeout_preserved():\n    assert normalize_timeout(0)==0\n    assert normalize_timeout(5)==5\n','    return v\n','    return v or None\n'),
 py_fixture(2,'case_preserved','def key(v):\n    return v\n','from logic import key\ndef test_case_preserved():\n    assert key("ApiKey")=="ApiKey"\n','    return v\n','    return v.lower()\n'),
 py_fixture(3,'negative_clamped','def clamp(v):\n    return 0 if v < 0 else v\n','from logic import clamp\ndef test_negative_clamped():\n    assert clamp(-4)==0\n    assert clamp(7)==7\n','    return 0 if v < 0 else v\n','    return v\n'),
 py_fixture(4,'none_distinct_from_empty','def normalize(v):\n    return "missing" if v is None else v\n','from logic import normalize\ndef test_none_distinct_from_empty():\n    assert normalize(None)=="missing"\n    assert normalize("")==""\n','    return "missing" if v is None else v\n','    return "missing" if not v else v\n'),
 py_fixture(5,'dedupe_order_preserved','def dedupe(xs):\n    return list(dict.fromkeys(xs))\n','from logic import dedupe\ndef test_dedupe_order_preserved():\n    assert dedupe([3,1,3,2])==[3,1,2]\n','    return list(dict.fromkeys(xs))\n','    return sorted(set(xs))\n'),
 py_fixture(6,'boundary_inclusive','def in_window(v):\n    return 10 <= v <= 20\n','from logic import in_window\ndef test_boundary_inclusive():\n    assert in_window(10)\n    assert in_window(20)\n    assert not in_window(21)\n','    return 10 <= v <= 20\n','    return 10 < v < 20\n'),
 py_fixture(7,'prefix_checked','def has_prefix(v):\n    return v.startswith("clh_")\n','from logic import has_prefix\ndef test_prefix_checked():\n    assert has_prefix("clh_abc")\n    assert not has_prefix("bad_abc")\n','    return v.startswith("clh_")\n','    return "clh_" in v\n'),
 cpp_fixture(1,'zero_id','#pragma once\ninline int keep(int v){ return v; }\n','#include <cassert>\n#include "logic.hpp"\nint main(){ assert(keep(0)==0); assert(keep(9)==9); }\n','return v;','return v==0?-1:v;'),
 cpp_fixture(2,'clamp','#pragma once\ninline int clamp(int v){ return v<0?0:v; }\n','#include <cassert>\n#include "logic.hpp"\nint main(){ assert(clamp(-2)==0); assert(clamp(5)==5); }\n','return v<0?0:v;','return v;'),
 cpp_fixture(3,'inclusive','#pragma once\ninline bool in_range(int v){ return v>=3 && v<=8; }\n','#include <cassert>\n#include "logic.hpp"\nint main(){ assert(in_range(3)); assert(in_range(8)); assert(!in_range(9)); }\n','return v>=3 && v<=8;','return v>3 && v<8;'),
 cpp_fixture(4,'case_token','#pragma once\n#include <string>\ninline std::string token(std::string v){ return v; }\n','#include <cassert>\n#include "logic.hpp"\nint main(){ assert(token("ApiKey")=="ApiKey"); }\n','return v;','for(auto &c:v)c=tolower(c); return v;'),
 cpp_fixture(5,'or_policy','#pragma once\ninline bool allowed(bool admin,bool owner){ return admin || owner; }\n','#include <cassert>\n#include "logic.hpp"\nint main(){ assert(allowed(true,false)); assert(allowed(false,true)); assert(!allowed(false,false)); }\n','return admin || owner;','return admin && owner;'),
 cpp_fixture(6,'min_len','#pragma once\n#include <string>\ninline bool valid(const std::string& s){ return s.size()>=3; }\n','#include <cassert>\n#include "logic.hpp"\nint main(){ assert(valid("abc")); assert(!valid("ab")); }\n','return s.size()>=3;','return s.size()>3;'),
 rust_fixture(1,'zero_timeout','pub fn keep(v: Option<u64>)->Option<u64>{ v }\n#[cfg(test)] mod tests{use super::*; #[test] fn zero_timeout(){assert_eq!(keep(Some(0)),Some(0));}}\n','pub fn keep(v: Option<u64>)->Option<u64>{ v }','pub fn keep(v: Option<u64>)->Option<u64>{ v.filter(|x| *x>0) }'),
 rust_fixture(2,'case_token','pub fn token(v:&str)->String{ v.to_string() }\n#[cfg(test)] mod tests{use super::*; #[test] fn case_token(){assert_eq!(token("ApiKey"),"ApiKey");}}\n','v.to_string()','v.to_lowercase()'),
 rust_fixture(3,'clamp','pub fn clamp(v:i32)->i32{ if v<0 {0} else {v} }\n#[cfg(test)] mod tests{use super::*; #[test] fn clamp(){assert_eq!(clamp(-2),0); assert_eq!(clamp(4),4);}}\n','if v<0 {0} else {v}','v'),
 rust_fixture(4,'inclusive','pub fn in_range(v:i32)->bool{ v>=3 && v<=8 }\n#[cfg(test)] mod tests{use super::*; #[test] fn inclusive(){assert!(in_range(3)); assert!(in_range(8)); assert!(!in_range(9));}}\n','v>=3 && v<=8','v>3 && v<8'),
 rust_fixture(5,'dedupe','use std::collections::HashSet; pub fn dedupe(xs:&[i32])->Vec<i32>{let mut seen=HashSet::new(); xs.iter().copied().filter(|x|seen.insert(*x)).collect()}\n#[cfg(test)] mod tests{use super::*; #[test] fn dedupe(){assert_eq!(dedupe(&[3,1,3,2]), vec![3,1,2]);}}\n','xs.iter().copied().filter(|x|seen.insert(*x)).collect()','{ let mut v:Vec<i32>=xs.iter().copied().collect(); v.sort(); v.dedup(); v }'),
 rust_fixture(6,'prefix','pub fn has_prefix(v:&str)->bool{ v.starts_with("clh_") }\n#[cfg(test)] mod tests{use super::*; #[test] fn prefix(){assert!(has_prefix("clh_abc")); assert!(!has_prefix("bad_clh_abc"));}}\n','v.starts_with("clh_")','v.contains("clh_")'),
 js_fixture(1,'zero_port','export function port(v){ return v; }\n','import assert from "node:assert/strict"; import {port} from "./logic.js"; assert.equal(port(0),0); assert.equal(port(8080),8080);\n','return v;','return v || 3000;'),
 js_fixture(2,'case_slug','export function slug(v){ return v; }\n','import assert from "node:assert/strict"; import {slug} from "./logic.js"; assert.equal(slug("APIKey"),"APIKey");\n','return v;','return v.toLowerCase();'),
 js_fixture(3,'clamp','export function clamp(v){ return v<0?0:v; }\n','import assert from "node:assert/strict"; import {clamp} from "./logic.js"; assert.equal(clamp(-2),0); assert.equal(clamp(4),4);\n','return v<0?0:v;','return v;'),
 js_fixture(4,'inclusive','export function inRange(v){ return v>=3 && v<=8; }\n','import assert from "node:assert/strict"; import {inRange} from "./logic.js"; assert.equal(inRange(3),true); assert.equal(inRange(8),true); assert.equal(inRange(9),false);\n','return v>=3 && v<=8;','return v>3 && v<8;'),
 js_fixture(5,'dedupe','export function dedupe(xs){ return [...new Set(xs)]; }\n','import assert from "node:assert/strict"; import {dedupe} from "./logic.js"; assert.deepEqual(dedupe([3,1,3,2]),[3,1,2]);\n','return [...new Set(xs)];','return [...new Set(xs)].sort();'),
 js_fixture(6,'prefix','export function hasPrefix(v){ return v.startsWith("clh_"); }\n','import assert from "node:assert/strict"; import {hasPrefix} from "./logic.js"; assert.equal(hasPrefix("clh_abc"),true); assert.equal(hasPrefix("bad_clh_abc"),false);\n','v.startsWith("clh_")','v.includes("clh_")'),
]

def write_json(path:Path,payload:Any): path.parent.mkdir(parents=True,exist_ok=True); path.write_text(json.dumps(payload,indent=2,sort_keys=True)+'\n')
def write_jsonl(path:Path,rows:list[dict[str,Any]]): path.write_text(''.join(json.dumps(r,sort_keys=True)+'\n' for r in rows))
def build_fixture(spec):
 root=FIXTURE_ROOT/spec['id'];
 if root.exists(): shutil.rmtree(root)
 root.mkdir(parents=True)
 for name,text in spec['files'].items():
  path=root/name; path.parent.mkdir(parents=True,exist_ok=True); path.write_text(text)
 return root
def run_cmd(cwd:Path,cmd:list[str],log_name:str):
 env=os.environ.copy(); env.update({'CUDA_VISIBLE_DEVICES':'','NVIDIA_VISIBLE_DEVICES':'','TMPDIR':str(ROOT/'tmp'),'TEMP':str(ROOT/'tmp'),'TMP':str(ROOT/'tmp')})
 (ROOT/'tmp').mkdir(parents=True,exist_ok=True); (ROOT/'logs').mkdir(parents=True,exist_ok=True)
 started=time.time()
 try:
  proc=subprocess.run(cmd,cwd=str(cwd),env=env,text=True,capture_output=True,stdin=subprocess.DEVNULL,timeout=45,check=False)
  payload={'command':cmd,'cwd':str(cwd),'returncode':proc.returncode,'timed_out':False,'duration_sec':round(time.time()-started,3),'stdout_tail':(proc.stdout or '')[-3000:],'stderr_tail':(proc.stderr or '')[-3000:]}
 except subprocess.TimeoutExpired as exc:
  payload={'command':cmd,'cwd':str(cwd),'returncode':124,'timed_out':True,'duration_sec':round(time.time()-started,3),'stdout_tail':exc.stdout if isinstance(exc.stdout,str) else '', 'stderr_tail': exc.stderr if isinstance(exc.stderr,str) else ''}
 write_json(ROOT/'logs'/f'{log_name}.json',payload); return {**payload,'log_path':str(ROOT/'logs'/f'{log_name}.json')}
def options(row_id,language):
 keyed=[(hashlib.sha256(f'{row_id}::{v}'.encode()).hexdigest(),v,t) for v,t in TRANSITION_TEXT.items()]
 return [{'label':lab,'canonical_value':v,'value':v,'text':t,'role':'verifier_transition_status','artifact_type':f'{language}_verifier_status'} for lab,(_,v,t) in zip(LABELS,sorted(keyed))]
def make_row(spec,root,baseline,mutant,restored):
 semantic='FAIL_TO_PASS'; row_id=f"stage12053::{spec['repo_family']}::{spec['id']}"; opts=options(row_id,spec['language_family']); target_label=next(o['label'] for o in opts if o['canonical_value']==semantic)
 prompt='\n'.join([f"Language: {spec['language_family']}",'Perspective: transition_verifier_transition','Task: choose the verifier transition proven by baseline, semantic mutation, and restored-source evidence.',f"Repository family: {spec['repo_family']}",f"Fixture root: {root}",f"Source file mutated: {spec['source_file']}",f"Selected verifier: {spec['selected_verifier_path']}",f"Baseline rc: {baseline['returncode']} tail: {(baseline.get('stdout_tail') or baseline.get('stderr_tail') or '')[-700:]}",f"Mutant rc: {mutant['returncode']} tail: {(mutant.get('stdout_tail') or mutant.get('stderr_tail') or '')[-700:]}",f"Restored rc: {restored['returncode']} tail: {(restored.get('stdout_tail') or restored.get('stderr_tail') or '')[-700:]}",'Options:',*[f"{o['label']}. {o['text']}" for o in opts],'Answer:'])
 return {'row_id':row_id,'root_id':row_id,'root_lineage_key':f"stage12053::{spec['repo_family']}::{spec['id']}",'source_root_id':row_id,'source_bundle_id':row_id,'repo_id':spec['repo_family'],'repo_family':spec['repo_family'],'language_family':spec['language_family'],'task_type':'transition_verifier_transition','split':'train','split_role':'stage12053_controlled_semantic_fail_to_pass_floor_closure_train_support_only','train_support_only':True,'strict_eval_eligible':False,'source_heldout_admissible':False,'selected_test_anchor':True,'verifier_anchor':True,'input_text':prompt,'prompt_text':prompt,'target_text':target_label,'decoder_text':target_label,'bounded_choice_target_label':target_label,'target':{'bounded_choice_target_label':target_label,'decoder_text':target_label,'semantic_value':semantic},'opaque_options':opts,'observed_verifier_transition':semantic,'semantic_mutation':{'mutation_kind':spec['id'],'source_file':spec['source_file'],'baseline_returncode':baseline['returncode'],'mutant_returncode':mutant['returncode'],'restored_returncode':restored['returncode']},'anti_cheat':{'deterministic_option_shuffle':True,'target_label_not_visible_before_options':True,'target_value_not_visible_before_options':True,'singleton_options':False,'controlled_fixture_train_support_only':True,'semantic_mutation_not_syntax_only':True,'baseline_mutant_restore_all_observed':True,'train_support_only':True},'standalone_projection_source':{'projection_mode':'stage12053_controlled_semantic_fail_to_pass_floor_closure_rows','fixture_repo':str(root),'selected_verifier_path':spec['selected_verifier_path'],'source_file':spec['source_file'],'observed_verifier_transition':semantic,'tool_or_verifier_observation':{'baseline':baseline,'mutant':mutant,'restored':restored}}}
def run_fixture(spec):
 root=build_fixture(spec); source=root/spec['source_file']; original=source.read_text(); baseline=run_cmd(root,spec['command'],f"{spec['id']}_baseline"); source.write_text(original.replace(spec['find'],spec['replace'],1)); mutant=run_cmd(root,spec['command'],f"{spec['id']}_mutant"); source.write_text(original); restored=run_cmd(root,spec['command'],f"{spec['id']}_restored"); restored_matches=source.read_text()==original; admitted=baseline['returncode']==0 and mutant['returncode']!=0 and restored['returncode']==0 and restored_matches; card={'fixture_id':spec['id'],'language_family':spec['language_family'],'repo_family':spec['repo_family'],'baseline':baseline,'mutant':mutant,'restored':restored,'restored_matches_original':restored_matches,'admitted':admitted}; return (make_row(spec,root,baseline,mutant,restored) if admitted else None),card
def main():
 ROOT.mkdir(parents=True,exist_ok=True); SUMMARY_MIRROR.parent.mkdir(parents=True,exist_ok=True); rows=[]; cards=[]
 for spec in FIXTURES:
  row,card=run_fixture(spec); cards.append(card); print(f"{spec['id']} admitted={card['admitted']}",flush=True)
  if row: rows.append(row)
 write_jsonl(ROWS,rows)
 summary={'stage':'stage12053_controlled_semantic_fail_to_pass_floor_closure_rows','rows_path':str(ROWS),'fixture_root':str(FIXTURE_ROOT),'attempted_fixtures':len(FIXTURES),'admitted_rows':len(rows),'unique_roots':len({r['root_lineage_key'] for r in rows}),'language_counts':dict(sorted(Counter(r['language_family'] for r in rows).items())),'status_counts':dict(sorted(Counter(r['observed_verifier_transition'] for r in rows).items())),'repo_family_counts':dict(sorted(Counter(r['repo_family'] for r in rows).items())),'probe_cards':cards,'decision':'admit_controlled_semantic_fail_to_pass_floor_closure_train_support' if rows else 'no_controlled_semantic_fail_to_pass_rows_admitted','claim_boundary':'Controlled semantic fixtures are train-support only. They close verifier-status floor coverage but are not source-heldout or strict eval evidence.','next_stage_recommendation':{'stage':'stage12054_transition_support_rollup_v34','action':'Merge semantic FAIL_TO_PASS floor-closure rows and run anti-cheat/split audits before any training.'}}
 write_json(SUMMARY,summary); write_json(SUMMARY_MIRROR,summary); print(json.dumps({k:summary[k] for k in ['decision','attempted_fixtures','admitted_rows','language_counts','status_counts','next_stage_recommendation']},indent=2,sort_keys=True))
if __name__=='__main__': main()
