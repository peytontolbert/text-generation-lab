#!/usr/bin/env python3
from __future__ import annotations
import json, time
from pathlib import Path
from typing import Any
try:
    from diagnostic_ticket_contract import AUTHORITY_CLOSED
except ModuleNotFoundError:
    from scripts.diagnostic_ticket_contract import AUTHORITY_CLOSED  # type: ignore
ROOT=Path(__file__).resolve().parents[1]; STAGE=9707; NAME='stage9707_symbol_binding_sampler_target100m_execution_audit'
SOURCE=ROOT/'runs/summaries/stage9706_symbol_binding_sampler_target100m_contract_preflight_audit.json'
RUN=ROOT/'runs/local/artifacts/stage9707_symbol_binding_sampler_target100m_execution/symbol_binding_probe'
OUT=ROOT/'runs/local/artifacts'/NAME; AUDIT=OUT/'symbol_binding_sampler_target100m_execution_audit.json'; SUMMARY=ROOT/'runs/summaries'/f'{NAME}.json'; DOC=ROOT/'docs'/'SYMBOL_BINDING_SAMPLER_TARGET100M_EXECUTION_STAGE9707.md'; REG=ROOT/'runs/local/artifacts/reconstructed_stage_registry.json'
def load(p:Path)->dict[str,Any]: return json.loads(p.read_text()) if p.exists() else {}
def update(summary):
 reg=load(REG) or {'rows':[],'metrics':{}}; rows=[r for r in reg.get('rows',[]) if r.get('stage')!=STAGE and r.get('stage_name')!=NAME]
 rows.append({'stage':STAGE,'stage_name':NAME,'passed':summary['passed'],'path':str(SUMMARY),'authority':dict(AUTHORITY_CLOSED),'next_best_step':summary['next_best_step']}); reg['rows']=sorted(rows,key=lambda r:(int(r.get('stage',-1)),r.get('stage_name',''))); reg['passed']=bool(reg['rows']); reg['metrics']={**(reg.get('metrics') or {}),'latest_stage':STAGE,'latest_stage_name':NAME,'latest_stage_next_best_step':summary['next_best_step'],'max_stage':STAGE,'registry_rows':len(reg['rows'])}; REG.write_text(json.dumps(reg,indent=2,sort_keys=True)+'\n')
def main():
 OUT.mkdir(parents=True,exist_ok=True); SUMMARY.parent.mkdir(parents=True,exist_ok=True); DOC.parent.mkdir(parents=True,exist_ok=True)
 src=load(SOURCE); result=load(RUN/'execution_result.json'); conf=load(RUN/'structured_confusion_matrix.json'); deltas=load(RUN/'module_delta_norms.json'); fail=[]
 eval_exact=result.get('eval',{}).get('eval',{}).get('field_exact',{}).get('symbol_binding',{}).get('exact'); strict_exact=result.get('eval',{}).get('strict_eval',{}).get('field_exact',{}).get('symbol_binding',{}).get('exact')
 if src.get('passed') is not True: fail.append('stage9706_not_passed')
 if result.get('required_artifacts_written') is not True: fail.append('required_artifacts_missing')
 if result.get('structured_batch_sampler')!='label_balanced_by_primary_field': fail.append('sampler_not_label_balanced')
 if result.get('native_feature_ablation_rows')!=32: fail.append('native_ablation_rows_not_32')
 for k in ['runtime_executed','gemma_executed','harness_executed','final_checkpoint_exported']:
  if result.get(k): fail.append(f'closed_boundary_opened:{k}')
 buckets=deltas.get('delta_norm_by_bucket') or {}
 for b in ['decoder','decoder_attention','decoder_mlp','embeddings','lm_head']:
  if float(buckets.get(b,0) or 0)!=0.0: fail.append(f'frozen_bucket_moved:{b}')
 quality=bool(eval_exact and strict_exact and eval_exact>=0.85 and strict_exact>=0.85)
 next_step='Build Stage9708 contrastive symbol-binding repair rows for import/test/retrieve distinctions, or run a longer checkpoint-selected structured probe only after exposure/shortcut audit.'
 audit={'stage':STAGE,'name':NAME,'passed':not fail,'quality_passed':quality,'promotion_ready':False,'failures':fail,'source_stage9706_summary':str(SOURCE.relative_to(ROOT)),'run_dir':str(RUN.relative_to(ROOT)),'metrics':{'eval_symbol_binding_exact':eval_exact,'strict_symbol_binding_exact':strict_exact,'estimated_parameter_count':result.get('implementation',{}).get('estimated_parameter_count'),'native_ablation_rows':result.get('native_feature_ablation_rows'),'structured_batch_sampler':result.get('structured_batch_sampler'),'decoder_delta_norm':deltas.get('decoder_delta_norm')},'confusion':conf,'authority':dict(AUTHORITY_CLOSED),'next_best_step':next_step}
 AUDIT.write_text(json.dumps(audit,indent=2,sort_keys=True)+'\n')
 summary={'stage':STAGE,'name':NAME,'passed':not fail,'quality_passed':quality,'promotion_ready':False,'created_at_unix':int(time.time()),'artifacts':{'audit':str(AUDIT.relative_to(ROOT)),'run_dir':str(RUN.relative_to(ROOT)),'doc':str(DOC.relative_to(ROOT))},'metrics':audit['metrics'],'authority':dict(AUTHORITY_CLOSED),'next_best_step':next_step}
 SUMMARY.write_text(json.dumps(summary,indent=2,sort_keys=True)+'\n')
 DOC.write_text(f"# Stage9707 Symbol-Binding Sampler Target-100M Execution\n\nExecution safe: `{not fail}`\n\nQuality passed: `{quality}`\n\nEval exact: `{eval_exact}`\n\nStrict exact: `{strict_exact}`\n\nNext: {next_step}\n")
 update(summary); print(json.dumps(summary,indent=2,sort_keys=True))
if __name__=='__main__': main()
