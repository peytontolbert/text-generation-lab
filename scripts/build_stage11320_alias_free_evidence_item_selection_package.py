#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import re
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

ROOT=Path(__file__).resolve().parents[1]
ART=ROOT/'runs/local/artifacts'
STAGE=11320
NAME='stage11320_alias_free_evidence_item_selection_package'
OUT=ART/NAME
SUMMARY=OUT/'alias_free_evidence_item_selection_package.json'
SRC=ART/'stage11276_capped_direct_retrieval_evidence_package'
INPUTS={
 'train':SRC/'capped_direct_retrieval_evidence_train_rows.jsonl',
 'validation':SRC/'capped_direct_retrieval_evidence_validation_rows.jsonl',
 'strict':SRC/'capped_direct_retrieval_evidence_strict_rows.jsonl',
}
OUTPUTS={k:OUT/f'alias_free_evidence_item_selection_{k}_rows.jsonl' for k in INPUTS}
OUTPUTS['diagnostic']=OUT/'alias_free_residual_diagnostic_rows.jsonl'
DIAG=ART/'stage11318_alias_free_residual_evidence_item_materialization/alias_free_residual_evidence_item_rows.jsonl'
LABELS=list('ABCDEFGH')
TARGET_MAP={
 'DECISIVE_VERIFIER_TEST_CONSTRAINT':'verifier_and_test_constraint',
 'SUPPORTING_CANDIDATE_CHANGE_SURFACE':'candidate_change_surface',
 'SUPPORTING_SYMPTOM_OR_CALL_PATH':'symptom_or_call_path_analogue',
 'DISTRACTOR_BACKGROUND_CONTEXT':'background_context',
}
TASK_TEXT={
 'DECISIVE_VERIFIER_TEST_CONSTRAINT':'Task: Choose the evidence item that contains concrete selected-test, verifier, command-result, assertion, or expected-outcome evidence.',
 'SUPPORTING_CANDIDATE_CHANGE_SURFACE':'Task: Choose the evidence item that contains the modified source, configuration, implementation, or changed artifact surface.',
 'SUPPORTING_SYMPTOM_OR_CALL_PATH':'Task: Choose the evidence item that contains symptom, call-path, runtime behavior, or failure analogue evidence.',
 'DISTRACTOR_BACKGROUND_CONTEXT':'Task: Choose the item that is only broad background context rather than direct maintainer evidence.',
}

def now(): return time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
def rel(p:Path): return str(p.relative_to(ROOT))
def read_jsonl(p:Path): return [json.loads(l) for l in p.read_text().splitlines() if l.strip()] if p.exists() else []
def write_jsonl(p:Path, rows): p.parent.mkdir(parents=True, exist_ok=True); p.write_text(''.join(json.dumps(r,sort_keys=True)+'\n' for r in rows))
def write_json(p:Path,o): p.parent.mkdir(parents=True, exist_ok=True); p.write_text(json.dumps(o,indent=2,sort_keys=True)+'\n')
def root(r): return str(r.get('root_id') or r.get('source_root_id') or r.get('root_lineage_key') or r.get('row_id') or '')
def gold(r):
    s=r.get('standalone_projection_source') or {}
    return str(s.get('gold_value') or r.get('semantic_target_value') or '')
def extract_candidate(prompt:str)->str:
    marker='Candidate evidence item:'
    text=prompt.split(marker,1)[1] if marker in prompt else prompt
    text=text.split('\nOptions:',1)[0]
    text=text.split('\nAnswer:',1)[0]
    return re.sub(r'\s+',' ',text).strip()
def role_for_target(t:str)->str: return TARGET_MAP.get(t,'background_context')
def task_for_target(t:str)->str: return TASK_TEXT.get(t,'Task: Choose the evidence item requested by the maintainer decision objective.')
def make_rows(rows:list[dict[str,Any]], split:str)->tuple[list[dict[str,Any]], list[dict[str,Any]]]:
    groups=defaultdict(list)
    for r in rows:
        groups[root(r)].append(r)
    out=[]; blocked=[]
    for rk, rs in groups.items():
        candidates=[]
        seen=set()
        for r in rs:
            tgt=gold(r)
            item=extract_candidate(str(r.get('prompt_text') or r.get('input_text') or ''))
            if not item or tgt not in TARGET_MAP: continue
            key=(tgt,item[:200])
            if key in seen: continue
            seen.add(key)
            candidates.append({'target_class':tgt,'role':role_for_target(tgt),'item':item,'source_row_id':r.get('row_id'),'language_family':r.get('language_family'),'repo_family':r.get('repo_family'),'repo_id':r.get('repo_id')})
        if len(candidates)<2:
            blocked.append({'root_id':rk,'blockers':['fewer_than_two_candidates'],'candidate_count':len(candidates)})
            continue
        for desired in sorted({c['target_class'] for c in candidates}):
            matches=[i for i,c in enumerate(candidates) if c['target_class']==desired]
            if len(matches)!=1:
                blocked.append({'root_id':rk,'blockers':[f'desired_class_{desired}_match_count_{len(matches)}'],'candidate_count':len(candidates)})
                continue
            evidence_lines=[]
            records=[]
            for idx,c in enumerate(candidates):
                eid=f'E{idx+1:02d}'
                evidence_lines.append(f'{eid}. {c["item"][:900]}')
                records.append((idx,eid,c))
            seed=hashlib.sha256((rk+desired).encode()).hexdigest()
            records=sorted(records,key=lambda rec: hashlib.sha256((seed+rec[1]).encode()).hexdigest())
            opts=[]; target_label=''
            for oi,(orig,eid,c) in enumerate(records):
                label=LABELS[oi]
                evidence_value = evidence_lines[orig]
                opts.append({'label':label,'value':evidence_value,'semantic_candidate':{'schema_version':'stage11320_alias_free_evidence_item_selection_v1','option_index':oi,'candidate_label':label,'candidate_value_family':'alias_free_evidence_item_text','task_type':'evidence_citation','evidence_role':c['role'],'verifier_transition':'NONE','test_id':eid,'value_token_count_proxy':len(evidence_value.split())}})
                if orig==matches[0]: target_label=label
            base=rs[0]
            input_text='\n'.join([f'Language: {base.get("language_family")}', 'Perspective: evidence_citation', task_for_target(desired), f'Repository family: {base.get("repo_family")}', 'Visible evidence items:', *evidence_lines, 'Options:', *[f'{o["label"]}. {o["value"]}' for o in opts], 'Answer:'])
            out.append({'row_id':f'stage11320::{rk}::{desired}', 'root_id':rk, 'source_root_id':rk, 'root_lineage_key':rk, 'language_family':base.get('language_family'), 'repo_family':base.get('repo_family'), 'repo_id':base.get('repo_id'), 'task_type':'evidence_citation', 'split':'train' if split=='train' else ('strict_eval' if split=='strict' else 'eval'), 'package_split':split, 'strict_eval_eligible':split=='strict', 'train_support_only':split=='train', 'input_text':input_text, 'prompt_text':input_text, 'decoder_text':target_label, 'target_text':target_label, 'bounded_choice_target_label':target_label, 'semantic_target_value':role_for_target(desired), 'opaque_options':opts, 'standalone_projection_source':{'projection_mode':'alias_free_evidence_item_selection','gold_value':role_for_target(desired),'source_target_class':desired,'opaque_options':opts,'evidence_items_hidden_role_metadata':candidates}, 'expected_enabled_loss':'decoder_ce', 'loss_mask': {'decoder_ce': True}})
    return out,blocked

def counts(rows): return {'rows':len(rows),'roots':len({root(r) for r in rows}),'by_language':dict(sorted(Counter(str(r.get('language_family')) for r in rows).items())),'by_gold':dict(sorted(Counter(str((r.get('standalone_projection_source') or {}).get('gold_value')) for r in rows).items())),'by_target_label':dict(sorted(Counter(str(r.get('target_text')) for r in rows).items()))}
def main():
    OUT.mkdir(parents=True,exist_ok=True)
    all_blocked=[]; built={}
    for split,path in INPUTS.items():
        rows,blocked=make_rows(read_jsonl(path), split)
        built[split]=rows; all_blocked.extend({'split':split,**b} for b in blocked)
        write_jsonl(OUTPUTS[split], rows)
    diag=read_jsonl(DIAG); write_jsonl(OUTPUTS['diagnostic'], diag)
    train_roots={root(r) for r in built['train']}; val_roots={root(r) for r in built['validation']}; strict_roots={root(r) for r in built['strict']}
    overlaps={'train_validation':sorted(train_roots&val_roots),'train_strict':sorted(train_roots&strict_roots),'validation_strict':sorted(val_roots&strict_roots)}
    summary={'stage':STAGE,'stage_name':NAME,'created_at_utc':now(),'passed':bool(built['train']) and not any(overlaps.values()),'decision':'alias_free_evidence_item_selection_package_ready' if bool(built['train']) and not any(overlaps.values()) else 'alias_free_evidence_item_selection_package_blocked','counts':{k:counts(v) for k,v in built.items()},'diagnostic_counts':counts(diag),'audit':{'root_overlap':overlaps,'blocked_rows':len(all_blocked),'blocked_examples':all_blocked[:30],'target_position_distribution':{k:dict(sorted(Counter(r.get('target_text') for r in v).items())) for k,v in built.items()}},'source_artifacts':{k:rel(v) for k,v in INPUTS.items()}|{'diagnostic':rel(DIAG)},'outputs':{k:rel(v) for k,v in OUTPUTS.items()},'next_action':'stage11321_alias_free_evidence_item_selection_probe_request'}
    write_json(SUMMARY, summary)
    print(json.dumps(summary,indent=2,sort_keys=True))
if __name__=='__main__': main()
