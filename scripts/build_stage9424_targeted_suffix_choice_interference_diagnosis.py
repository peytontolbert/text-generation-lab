#!/usr/bin/env python3
from __future__ import annotations
import json,time
from collections import Counter
from pathlib import Path
try:
 from diagnostic_ticket_contract import AUTHORITY_CLOSED
except ModuleNotFoundError:
 from scripts.diagnostic_ticket_contract import AUTHORITY_CLOSED  # type: ignore
ROOT=Path(__file__).resolve().parents[1]; STAGE=9424; NAME='stage9424_targeted_suffix_choice_interference_diagnosis'
RUN_DIR=ROOT/'runs/local/artifacts/stage9423_suffix_choice_control_probe'; OUT_DIR=ROOT/'runs/local/artifacts'/NAME
DIAG=OUT_DIR/'targeted_suffix_choice_interference_diagnosis.json'; SUMMARY=ROOT/'runs/summaries'/f'{NAME}.json'; DOC=ROOT/'docs'/'TARGETED_SUFFIX_CHOICE_INTERFERENCE_DIAGNOSIS_STAGE9424.md'; REG=ROOT/'runs/local/artifacts/reconstructed_stage_registry.json'
def lj(p): return json.loads(p.read_text()) if p.exists() else {}
def ljl(p): return [json.loads(l) for l in p.read_text().splitlines() if l.strip()] if p.exists() else []
def main():
 OUT_DIR.mkdir(parents=True,exist_ok=True); SUMMARY.parent.mkdir(parents=True,exist_ok=True); DOC.parent.mkdir(parents=True,exist_ok=True)
 audit=lj(RUN_DIR/'stage9423_suffix_choice_control_probe_audit.json'); logits=[r for r in ljl(RUN_DIR/'row_field_logits.jsonl') if r.get('field')=='suffix_choice']
 errs=[r for r in logits if not r.get('correct')]; conf=Counter(f"{r.get('target')} => {r.get('pred')}" for r in errs)
 target_pair={'expected_assertion_behavior__keep_value_small','current_repair_invariant__do_not_introduce'}
 tp=[r for r in logits if r.get('target') in target_pair]
 diag={'passed':True,'source_stage':9423,'safety_preserved':bool(audit.get('safety_gate_passed')),'quality_passed':bool(audit.get('quality_gate_passed')),'stage9419_baseline_exact_by_split':{'eval':5,'strict_eval':4},'stage9419_baseline_target_pair_exact':'3/4','stage9423_exact_by_split':audit.get('suffix_choice_exact_by_split'),'stage9423_target_pair_exact':f"{sum(1 for r in tp if r.get('correct'))}/{len(tp)}",'confusion_counts':dict(sorted(conf.items())),'findings':['targeted_confusion_support_preserved_safety','targeted_confusion_support_regressed_quality_vs_stage9419','targeted_feature_support_overbiased_localized_or_checked_choices','do_not_build_on_stage9421_or_stage9423','branch_back_to_stage9417_or_stage9419_for_next_patch'],'recommended_contract':{'branch_from':'stage9417_balanced_suffix_choice_support_manifest','do_not_build_on':['stage9421_targeted_suffix_choice_confusion_repair_manifest','stage9423_targeted_suffix_choice_control_probe'],'next_patch_type':'lower_weight_or_holdout_specific_boundary_choice_probe','keep_closed':['decoder_ce','denoise_ce','runtime','gemma','harness','checkpoint_export']},'authority':dict(AUTHORITY_CLOSED)}
 DIAG.write_text(json.dumps(diag,indent=2,sort_keys=True)+'\n')
 summary={'stage':STAGE,'stage_name':NAME,'name':NAME,'passed':True,'authority':dict(AUTHORITY_CLOSED),'metrics':{**dict(AUTHORITY_CLOSED),**{k:v for k,v in diag.items() if k not in {'authority','recommended_contract'}}},'artifacts':{'diagnosis':str(DIAG.relative_to(ROOT)),'doc':str(DOC.relative_to(ROOT))},'decision':'Stage9423 is safety-clean but interferes with suffix-choice quality; branch back to Stage9417/9419.','next_best_step':'Design a lower-interference suffix-choice patch from Stage9417, or reconnect only the Stage9419-passing control decisions to denoise generation with residual guardrails.','created_at_utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime())}
 SUMMARY.write_text(json.dumps(summary,indent=2,sort_keys=True)+'\n')
 DOC.write_text('\n'.join(['# Stage9424 Targeted Suffix Choice Interference Diagnosis','',f"Safety preserved: `{diag['safety_preserved']}`",f"Stage9419 baseline exact: `{diag['stage9419_baseline_exact_by_split']}`",f"Stage9423 exact: `{diag['stage9423_exact_by_split']}`",f"Stage9423 target pair: `{diag['stage9423_target_pair_exact']}`",'','Do not build on Stage9421/9423. Branch back to Stage9417/9419.','']))
 reg=lj(REG) or {'rows':[],'metrics':{}}; rr=[r for r in reg.get('rows',[]) if r.get('stage')!=STAGE and r.get('stage_name')!=NAME]
 rr.append({'stage':STAGE,'stage_name':NAME,'passed':True,'path':str(SUMMARY),'authority':dict(AUTHORITY_CLOSED),'next_best_step':summary['next_best_step']}); rr=sorted(rr,key=lambda r:(int(r.get('stage',-1)),r.get('stage_name','')))
 reg['rows']=rr; reg['passed']=True; reg['metrics']={**(reg.get('metrics') or {}),'latest_stage':STAGE,'latest_stage_name':NAME,'latest_stage_next_best_step':summary['next_best_step'],'max_stage':STAGE,'registry_rows':len(rr),'authority_counts':{k:0 for k in AUTHORITY_CLOSED}}
 REG.write_text(json.dumps(reg,indent=2,sort_keys=True)+'\n')
 print(json.dumps({'stage':STAGE,'passed':True,'metrics':{'stage9423_exact':audit.get('suffix_choice_exact_by_split'),'target_pair':diag['stage9423_target_pair_exact']}},indent=2,sort_keys=True))
if __name__=='__main__': main()
