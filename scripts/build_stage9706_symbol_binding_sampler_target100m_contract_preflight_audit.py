#!/usr/bin/env python3
from __future__ import annotations
import json, time
from pathlib import Path
from typing import Any
try:
    from diagnostic_ticket_contract import AUTHORITY_CLOSED
except ModuleNotFoundError:
    from scripts.diagnostic_ticket_contract import AUTHORITY_CLOSED  # type: ignore
ROOT=Path(__file__).resolve().parents[1]
STAGE=9706
NAME='stage9706_symbol_binding_sampler_target100m_contract_preflight_audit'
SOURCE=ROOT/'runs/summaries/stage9705_structured_label_balanced_sampler_patch_audit.json'
CONTRACT_DIR=ROOT/'runs/local/artifacts/stage9706_symbol_binding_sampler_target100m_contract_preflight/contract_only'
CARD=CONTRACT_DIR/'probe_contract_audit.json'
OUT=ROOT/'runs/local/artifacts'/NAME
AUDIT=OUT/'symbol_binding_sampler_target100m_contract_preflight_audit.json'
SUMMARY=ROOT/'runs/summaries'/f'{NAME}.json'
DOC=ROOT/'docs'/'SYMBOL_BINDING_SAMPLER_TARGET100M_CONTRACT_PREFLIGHT_STAGE9706.md'
REGISTRY=ROOT/'runs/local/artifacts/reconstructed_stage_registry.json'

def load(path:Path)->dict[str,Any]: return json.loads(path.read_text()) if path.exists() else {}

def update(summary):
    reg=load(REGISTRY) or {'rows':[],'metrics':{}}
    rows=[r for r in reg.get('rows',[]) if r.get('stage')!=STAGE and r.get('stage_name')!=NAME]
    rows.append({'stage':STAGE,'stage_name':NAME,'passed':summary['passed'],'path':str(SUMMARY),'authority':dict(AUTHORITY_CLOSED),'next_best_step':summary['next_best_step']})
    reg['rows']=sorted(rows,key=lambda r:(int(r.get('stage',-1)),r.get('stage_name','')))
    reg['passed']=bool(reg['rows'])
    reg['metrics']={**(reg.get('metrics') or {}),'latest_stage':STAGE,'latest_stage_name':NAME,'latest_stage_next_best_step':summary['next_best_step'],'max_stage':STAGE,'registry_rows':len(reg['rows'])}
    REGISTRY.write_text(json.dumps(reg,indent=2,sort_keys=True)+'\n')

def main():
    OUT.mkdir(parents=True,exist_ok=True); SUMMARY.parent.mkdir(parents=True,exist_ok=True); DOC.parent.mkdir(parents=True,exist_ok=True)
    src=load(SOURCE); card=load(CARD); fail=[]
    if src.get('passed') is not True: fail.append('stage9705_not_passed')
    if card.get('passed') is not True: fail.append('contract_not_passed')
    if card.get('probe_scale')!='target_100m': fail.append('not_target100m')
    if card.get('native_feature_ablation_audit_required') is not True: fail.append('native_ablation_not_required')
    if card.get('model_execution_attempted') is not False: fail.append('model_execution_attempted')
    if card.get('loss_counts',{}).get('symbol_binding_ce')!=64: fail.append('symbol_binding_loss_not_64')
    if card.get('split_counts')!={'train':32,'eval':16,'strict_eval':16,'other':0}: fail.append('bad_split_counts')
    next_step='Run Stage9707 target-100M symbol-binding execution with the Stage9705 label-balanced sampler; audit quality and exposure before any decoder work.'
    audit={'stage':STAGE,'name':NAME,'passed':not fail,'failures':fail,'quality_passed':False,'promotion_ready':False,'execution_authorized_next':False,'source_stage9705_summary':str(SOURCE.relative_to(ROOT)),'contract_dir':str(CONTRACT_DIR.relative_to(ROOT)),'metrics':{'probe_scale':card.get('probe_scale'),'native_feature_ablation_audit_required':card.get('native_feature_ablation_audit_required'),'symbol_binding_loss_count':card.get('loss_counts',{}).get('symbol_binding_ce'),'split_counts':card.get('split_counts'),'model_execution_attempted':card.get('model_execution_attempted')},'authority':dict(AUTHORITY_CLOSED),'next_best_step':next_step}
    AUDIT.write_text(json.dumps(audit,indent=2,sort_keys=True)+'\n')
    summary={'stage':STAGE,'name':NAME,'passed':not fail,'quality_passed':False,'promotion_ready':False,'execution_authorized_next':False,'created_at_unix':int(time.time()),'artifacts':{'audit':str(AUDIT.relative_to(ROOT)),'contract_dir':str(CONTRACT_DIR.relative_to(ROOT)),'doc':str(DOC.relative_to(ROOT))},'metrics':audit['metrics'],'authority':dict(AUTHORITY_CLOSED),'next_best_step':next_step}
    SUMMARY.write_text(json.dumps(summary,indent=2,sort_keys=True)+'\n')
    DOC.write_text(f"# Stage9706 Symbol-Binding Sampler Target-100M Contract Preflight\n\nPassed: `{not fail}`\n\nNext: {next_step}\n")
    update(summary); print(json.dumps(summary,indent=2,sort_keys=True))
if __name__=='__main__': main()
