#!/usr/bin/env python3
from __future__ import annotations

import copy, hashlib, json, time
from collections import Counter, defaultdict
from pathlib import Path

try:
    from diagnostic_ticket_contract import AUTHORITY_CLOSED
except ModuleNotFoundError:
    from scripts.diagnostic_ticket_contract import AUTHORITY_CLOSED  # type: ignore

ROOT=Path(__file__).resolve().parents[1]
STAGE=9421
NAME='stage9421_targeted_suffix_choice_confusion_repair_manifest'
SOURCE_SUMMARY=ROOT/'runs/summaries/stage9420_balanced_suffix_choice_residual_diagnosis.json'
SOURCE_MANIFEST=ROOT/'runs/local/artifacts/stage9417_balanced_suffix_choice_support_manifest/balanced_suffix_choice_support_manifest.jsonl'
OUT_DIR=ROOT/'runs/local/artifacts'/NAME
MANIFEST=OUT_DIR/'targeted_suffix_choice_confusion_repair_manifest.jsonl'
AUDIT=OUT_DIR/'targeted_suffix_choice_confusion_repair_manifest_audit.json'
SUMMARY=ROOT/'runs/summaries'/f'{NAME}.json'
DOC=ROOT/'docs'/'TARGETED_SUFFIX_CHOICE_CONFUSION_REPAIR_MANIFEST_STAGE9421.md'
REGISTRY=ROOT/'runs/local/artifacts/reconstructed_stage_registry.json'

PAIR_FEATURES={
 'expected_assertion_behavior__keep_value_small': {'evidence_focus':'assertion_expected_value','continuation_scope':'preserve_observed_assertion','negative_neighbor':'localized_step_continuation'},
 'localized_repair_step__keep_response': {'evidence_focus':'localized_step_instruction','continuation_scope':'response_boundary','negative_neighbor':'assertion_or_operator_choice'},
 'checked_symbol_evidence__keep_decision_compatible': {'evidence_focus':'checked_symbol_binding','continuation_scope':'decision_compatibility','negative_neighbor':'localized_step_continuation'},
 'verified_patch_operator__use_repo': {'evidence_focus':'verified_operator_target','continuation_scope':'repo_operator_argument','negative_neighbor':'localized_step_continuation'},
 'repaired_state__keep_answer_focused': {'evidence_focus':'repaired_state_slot','continuation_scope':'state_surface_answer','negative_neighbor':'wrapper_plan_surface'},
 'wrapper_plan__keep_answer_focused': {'evidence_focus':'wrapper_plan_adapter','continuation_scope':'plan_surface_answer','negative_neighbor':'repaired_state_slot'},
}
REPAIR_LABELS=list(PAIR_FEATURES)
LOSS_KEYS=['surface_role_ce','repair_surface_ce','build_mode_ce','allowed_import_policy_ce','blocked_import_policy_ce','repo_dependency_policy_ce','action_sequence_ce','file_plan_ce','symbol_binding_ce','edit_localization_ce','patch_operator_ce','verifier_repair_ce','suffix_choice_ce','decoder_ce','denoise_ce','runtime_reward']

def load_json(p:Path)->dict:
    return json.loads(p.read_text()) if p.exists() else {}
def load_jsonl(p:Path)->list[dict]:
    return [json.loads(l) for l in p.read_text().splitlines() if l.strip()]
def write_jsonl(p:Path, rows:list[dict])->None:
    p.write_text(''.join(json.dumps(r,sort_keys=True)+'\n' for r in rows))
def choice(r:dict)->str:
    return str((r.get('clean_state') or {}).get('suffix_choice'))
def sid(seed:str)->str:
    return 'stage9421_suffix_choice_confusion_'+hashlib.sha256(seed.encode()).hexdigest()[:16]

def main():
    OUT_DIR.mkdir(parents=True,exist_ok=True); SUMMARY.parent.mkdir(parents=True,exist_ok=True); DOC.parent.mkdir(parents=True,exist_ok=True)
    source=load_json(SOURCE_SUMMARY); base=load_jsonl(SOURCE_MANIFEST)
    rows=[copy.deepcopy(r) for r in base]
    by_label=defaultdict(list)
    for r in base:
        by_label[choice(r)].append(r)
    added=[]
    for label in REPAIR_LABELS:
        examples=by_label.get(label, [])
        if not examples:
            continue
        for i in range(3):
            t=copy.deepcopy(examples[i % len(examples)])
            t['row_id']=sid(f'{label}:{i}:{t.get("row_id")}')
            t['split']='train'
            t['objective_family']='targeted_suffix_choice_confusion_repair'
            t['targeted_suffix_choice_confusion_repair']=True
            t['source_stage9417_row_id']=t.get('row_id')
            mask={k:False for k in LOSS_KEYS}; mask['suffix_choice_ce']=True; t['loss_mask']=mask
            mi=t.get('model_input') if isinstance(t.get('model_input'),dict) else {}
            mi.update({
                'targeted_suffix_choice_repair': True,
                'targeted_suffix_choice_schema_version': 'stage9421_v1',
                'choice_label_hidden_from_model_input': True,
                'confusion_discriminator_visible': True,
                'confusion_support_variant_index': i,
                **PAIR_FEATURES[label],
            })
            t['model_input']=mi
            auth=t.get('authority') if isinstance(t.get('authority'),dict) else {}
            for k in AUTHORITY_CLOSED: auth[k]=False
            t['authority']=auth
            added.append(t); rows.append(t)
    split_counts=Counter(str(r.get('split')) for r in rows)
    train_counts=Counter(choice(r) for r in rows if r.get('split')=='train')
    loss_counts=Counter(); auth_rows=0; label_leak_rows=0
    for r in rows:
        for k,v in (r.get('loss_mask') if isinstance(r.get('loss_mask'),dict) else {}).items():
            if v: loss_counts[k]+=1
        if any(bool((r.get('authority') or {}).get(k)) for k in AUTHORITY_CLOSED): auth_rows+=1
        lbl=choice(r); blob=json.dumps(r.get('model_input') or {},sort_keys=True)
        if lbl and lbl in blob: label_leak_rows+=1
    failures=[]
    if source.get('passed') is not True: failures.append('source_stage9420_not_passed')
    if split_counts.get('eval')!=9 or split_counts.get('strict_eval')!=7: failures.append('heldout_split_counts_changed')
    if len(added)!=18: failures.append('unexpected_added_rows')
    if loss_counts.get('suffix_choice_ce')!=len(rows) or len(loss_counts)!=1: failures.append('loss_not_suffix_choice_only')
    if auth_rows or label_leak_rows: failures.append('authority_or_label_leak')
    audit={'passed':not failures,'failures':failures,'rows':len(rows),'added_train_support_rows':len(added),'split_counts':dict(sorted(split_counts.items())),'train_choice_counts':dict(sorted(train_counts.items())),'loss_counts':dict(sorted(loss_counts.items())),'authority_rows':auth_rows,'label_leak_rows':label_leak_rows,'targeted_labels':REPAIR_LABELS,'authority':dict(AUTHORITY_CLOSED)}
    write_jsonl(MANIFEST,rows); AUDIT.write_text(json.dumps(audit,indent=2,sort_keys=True)+'\n')
    summary={'stage':STAGE,'stage_name':NAME,'name':NAME,'passed':audit['passed'],'authority':dict(AUTHORITY_CLOSED),'metrics':{**dict(AUTHORITY_CLOSED),**audit},'artifacts':{'manifest':str(MANIFEST.relative_to(ROOT)),'audit':str(AUDIT.relative_to(ROOT)),'doc':str(DOC.relative_to(ROOT))},'decision':'Added targeted train-only suffix-choice confusion repair rows for Stage9420 low-margin residuals.','next_best_step':'Run structured suffix-choice probe on the targeted confusion repair manifest.','created_at_utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime())}
    SUMMARY.write_text(json.dumps(summary,indent=2,sort_keys=True)+'\n')
    DOC.write_text('\n'.join(['# Stage9421 Targeted Suffix Choice Confusion Repair Manifest','',f"Passed: `{audit['passed']}`",f"Rows: `{len(rows)}`",f"Added train support rows: `{len(added)}`",f"Splits: `{dict(sorted(split_counts.items()))}`",'','Structured-only suffix-choice repair. Decoder and denoise generation remain closed.','']))
    reg=load_json(REGISTRY) or {'rows':[],'metrics':{}}
    rr=[r for r in reg.get('rows',[]) if r.get('stage')!=STAGE and r.get('stage_name')!=NAME]
    rr.append({'stage':STAGE,'stage_name':NAME,'passed':summary['passed'],'path':str(SUMMARY),'authority':dict(AUTHORITY_CLOSED),'next_best_step':summary['next_best_step']})
    rr=sorted(rr,key=lambda r:(int(r.get('stage',-1)),r.get('stage_name','')))
    reg['rows']=rr; reg['passed']=summary['passed']; reg['metrics']={**(reg.get('metrics') or {}),'latest_stage':STAGE,'latest_stage_name':NAME,'latest_stage_next_best_step':summary['next_best_step'],'max_stage':STAGE,'registry_rows':len(rr),'authority_counts':{k:0 for k in AUTHORITY_CLOSED}}
    REGISTRY.write_text(json.dumps(reg,indent=2,sort_keys=True)+'\n')
    print(json.dumps({'stage':STAGE,'passed':summary['passed'],'metrics':{'rows':len(rows),'added':len(added),'splits':dict(sorted(split_counts.items()))}},indent=2,sort_keys=True))
if __name__=='__main__': main()
