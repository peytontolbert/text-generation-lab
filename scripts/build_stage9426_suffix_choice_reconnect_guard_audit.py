#!/usr/bin/env python3
from __future__ import annotations
import json,time
from pathlib import Path
try:
 from diagnostic_ticket_contract import AUTHORITY_CLOSED
except ModuleNotFoundError:
 from scripts.diagnostic_ticket_contract import AUTHORITY_CLOSED  # type: ignore
ROOT=Path(__file__).resolve().parents[1]
STAGE=9426
NAME='stage9426_suffix_choice_reconnect_guard_audit'
SOURCE=ROOT/'runs/summaries/stage9425_suffix_choice_reconnect_guard_manifest.json'
PROMO=ROOT/'runs/local/artifacts/stage9425_suffix_choice_reconnect_guard_manifest/suffix_choice_reconnect_guard_manifest.jsonl'
QUAR=ROOT/'runs/local/artifacts/stage9425_suffix_choice_reconnect_guard_manifest/suffix_choice_residual_quarantine_manifest.jsonl'
OUT=ROOT/'runs/local/artifacts'/NAME
AUDIT=OUT/'suffix_choice_reconnect_guard_audit.json'
SUMMARY=ROOT/'runs/summaries'/f'{NAME}.json'
DOC=ROOT/'docs'/'SUFFIX_CHOICE_RECONNECT_GUARD_AUDIT_STAGE9426.md'
REG=ROOT/'runs/local/artifacts/reconstructed_stage_registry.json'
def lj(p): return json.loads(p.read_text()) if p.exists() else {}
def ljl(p): return [json.loads(l) for l in p.read_text().splitlines() if l.strip()] if p.exists() else []
def main():
 OUT.mkdir(parents=True,exist_ok=True); SUMMARY.parent.mkdir(parents=True,exist_ok=True); DOC.parent.mkdir(parents=True,exist_ok=True)
 source=lj(SOURCE); promoted=ljl(PROMO); quarantined=ljl(QUAR)
 failures=[]
 if source.get('passed') is not True: failures.append('source_stage9425_not_passed')
 if len(promoted)!=9 or len(quarantined)!=7: failures.append('bad_manifest_counts')
 pids={r['source_row_id'] for r in promoted}; qids={r['source_row_id'] for r in quarantined}
 if pids & qids: failures.append('promoted_quarantine_overlap')
 if any(r.get('route')!='ELIGIBLE_SUFFIX_CHOICE_PRIOR' for r in promoted): failures.append('bad_promoted_route')
 if any(r.get('route')!='QUARANTINE_SUFFIX_CHOICE_RESIDUAL' for r in quarantined): failures.append('bad_quarantine_route')
 if any(r.get('generation_reconnect_allowed_now') for r in promoted+quarantined): failures.append('generation_reconnect_open')
 if any(r.get('decoder_ce_authorized') or r.get('denoise_ce_authorized') or r.get('runtime_authorized') or r.get('gemma_authorized') or r.get('harness_authorized') for r in promoted+quarantined): failures.append('forbidden_authority_open')
 if any(any(bool((r.get('authority') or {}).get(k)) for k in AUTHORITY_CLOSED) for r in promoted+quarantined): failures.append('authority_flags_open')
 residual_guard_promoted=sum(1 for r in promoted if r.get('needs_residual_guard'))
 audit={'passed':not failures,'failures':failures,'promoted_rows':len(promoted),'quarantined_rows':len(quarantined),'promoted_quarantine_overlap':len(pids&qids),'residual_guard_promoted_rows':residual_guard_promoted,'generation_reconnect_allowed_now':False,'future_reconnect_requirements':['consume only ELIGIBLE_SUFFIX_CHOICE_PRIOR rows','reject any source_row_id in quarantine manifest','keep decoder_ce closed until denoise reconnect generation audit passes','keep runtime/gemma/harness closed until separate authority stage'],'authority':dict(AUTHORITY_CLOSED)}
 AUDIT.write_text(json.dumps(audit,indent=2,sort_keys=True)+'\n')
 summary={'stage':STAGE,'stage_name':NAME,'name':NAME,'passed':audit['passed'],'authority':dict(AUTHORITY_CLOSED),'metrics':{**dict(AUTHORITY_CLOSED),**audit},'artifacts':{'audit':str(AUDIT.relative_to(ROOT)),'doc':str(DOC.relative_to(ROOT))},'decision':'Verified suffix-choice reconnect guard: promoted rows are controller priors only and residual rows are hard-quarantined.','next_best_step':'Build a no-execution denoise reconnect design that references the promotion/quarantine manifests and fails if quarantined rows are included.','created_at_utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime())}
 SUMMARY.write_text(json.dumps(summary,indent=2,sort_keys=True)+'\n')
 DOC.write_text('\n'.join(['# Stage9426 Suffix Choice Reconnect Guard Audit','',f"Passed: `{audit['passed']}`",f"Promoted rows: `{len(promoted)}`",f"Quarantined rows: `{len(quarantined)}`",f"Residual-guard promoted rows: `{residual_guard_promoted}`",'','No generation, decoder CE, denoise CE, runtime, Gemma, or harness authority is opened.','']))
 reg=lj(REG) or {'rows':[],'metrics':{}}
 rr=[r for r in reg.get('rows',[]) if r.get('stage')!=STAGE and r.get('stage_name')!=NAME]
 rr.append({'stage':STAGE,'stage_name':NAME,'passed':summary['passed'],'path':str(SUMMARY),'authority':dict(AUTHORITY_CLOSED),'next_best_step':summary['next_best_step']})
 rr=sorted(rr,key=lambda r:(int(r.get('stage',-1)),r.get('stage_name','')))
 reg['rows']=rr; reg['passed']=summary['passed']; reg['metrics']={**(reg.get('metrics') or {}),'latest_stage':STAGE,'latest_stage_name':summary['stage_name'],'latest_stage_next_best_step':summary['next_best_step'],'max_stage':STAGE,'registry_rows':len(rr),'authority_counts':{k:0 for k in AUTHORITY_CLOSED}}
 REG.write_text(json.dumps(reg,indent=2,sort_keys=True)+'\n')
 print(json.dumps({'stage':STAGE,'passed':summary['passed'],'metrics':{'promoted':len(promoted),'quarantined':len(quarantined),'overlap':len(pids&qids)}},indent=2,sort_keys=True))
if __name__=='__main__': main()
