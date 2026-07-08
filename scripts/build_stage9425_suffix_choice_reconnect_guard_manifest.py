#!/usr/bin/env python3
from __future__ import annotations
import json, time
from collections import Counter
from pathlib import Path
try:
    from diagnostic_ticket_contract import AUTHORITY_CLOSED
except ModuleNotFoundError:
    from scripts.diagnostic_ticket_contract import AUTHORITY_CLOSED  # type: ignore
ROOT=Path(__file__).resolve().parents[1]
STAGE=9425
NAME='stage9425_suffix_choice_reconnect_guard_manifest'
SOURCE_SUMMARY=ROOT/'runs/summaries/stage9424_targeted_suffix_choice_interference_diagnosis.json'
STAGE9419_AUDIT=ROOT/'runs/local/artifacts/stage9419_suffix_choice_control_probe/stage9419_suffix_choice_control_probe_audit.json'
STAGE9419_LOGITS=ROOT/'runs/local/artifacts/stage9419_suffix_choice_control_probe/row_field_logits.jsonl'
STAGE9417_MANIFEST=ROOT/'runs/local/artifacts/stage9417_balanced_suffix_choice_support_manifest/balanced_suffix_choice_support_manifest.jsonl'
OUT_DIR=ROOT/'runs/local/artifacts'/NAME
PROMOTION=OUT_DIR/'suffix_choice_reconnect_guard_manifest.jsonl'
QUARANTINE=OUT_DIR/'suffix_choice_residual_quarantine_manifest.jsonl'
AUDIT=OUT_DIR/'suffix_choice_reconnect_guard_audit.json'
SUMMARY=ROOT/'runs/summaries'/f'{NAME}.json'
DOC=ROOT/'docs'/'SUFFIX_CHOICE_RECONNECT_GUARD_MANIFEST_STAGE9425.md'
REGISTRY=ROOT/'runs/local/artifacts/reconstructed_stage_registry.json'
RESIDUAL_LABELS={
    'verified_patch_operator__use_repo',
    'repaired_state__keep_answer_focused',
    'checked_symbol_evidence__keep_decision_compatible',
    'expected_assertion_behavior__keep_value_small',
}

def lj(p:Path)->dict:
    return json.loads(p.read_text()) if p.exists() else {}
def ljl(p:Path)->list[dict]:
    return [json.loads(l) for l in p.read_text().splitlines() if l.strip()] if p.exists() else []
def wjl(p:Path, rows:list[dict])->None:
    p.write_text(''.join(json.dumps(r,sort_keys=True)+'\n' for r in rows))

def main():
    OUT_DIR.mkdir(parents=True,exist_ok=True); SUMMARY.parent.mkdir(parents=True,exist_ok=True); DOC.parent.mkdir(parents=True,exist_ok=True)
    source=lj(SOURCE_SUMMARY); audit9419=lj(STAGE9419_AUDIT); logits=[r for r in ljl(STAGE9419_LOGITS) if r.get('field')=='suffix_choice']
    base={r.get('row_id'):r for r in ljl(STAGE9417_MANIFEST)}
    promoted=[]; quarantined=[]
    for rec in logits:
        row_id=str(rec.get('row_id'))
        correct=bool(rec.get('correct'))
        target=str(rec.get('target'))
        margin=float(rec.get('margin') or 0.0)
        confidence=float(rec.get('confidence') or 0.0)
        payload={
            'source_stage':'stage9419_suffix_choice_control_probe',
            'source_row_id':row_id,
            'split':rec.get('split'),
            'suffix_choice_target':target,
            'suffix_choice_pred':rec.get('pred'),
            'suffix_choice_correct':correct,
            'confidence':confidence,
            'margin':margin,
            'top_k':rec.get('top_k'),
            'authority':dict(AUTHORITY_CLOSED),
            'decoder_ce_authorized':False,
            'denoise_ce_authorized':False,
            'runtime_authorized':False,
            'gemma_authorized':False,
            'harness_authorized':False,
        }
        # Correct decisions are eligible only as controller-side priors. Very low margins
        # remain guard-only until a future reconnect probe proves generation benefit.
        if correct:
            payload.update({
                'route':'ELIGIBLE_SUFFIX_CHOICE_PRIOR',
                'recommended_next_use':'controller_prior_only_until_denoise_reconnect_probe',
                'generation_reconnect_allowed_now':False,
                'needs_residual_guard': margin < 0.02 or target in RESIDUAL_LABELS,
                'source_manifest_row_present': row_id in base,
            })
            promoted.append(payload)
        else:
            payload.update({
                'route':'QUARANTINE_SUFFIX_CHOICE_RESIDUAL',
                'recommended_next_use':'do_not_reconnect_to_generation',
                'generation_reconnect_allowed_now':False,
                'residual_reason':'stage9419_suffix_choice_wrong',
                'source_manifest_row_present': row_id in base,
            })
            quarantined.append(payload)
    split_counts=Counter(r['split'] for r in promoted+quarantined)
    promoted_counts=Counter(r['suffix_choice_target'] for r in promoted)
    quarantined_counts=Counter(r['suffix_choice_target'] for r in quarantined)
    failures=[]
    if source.get('passed') is not True: failures.append('source_stage9424_not_passed')
    if not audit9419.get('safety_gate_passed'): failures.append('stage9419_not_safety_clean')
    if len(promoted)!=9 or len(quarantined)!=7: failures.append('unexpected_promote_quarantine_counts')
    if any(r['generation_reconnect_allowed_now'] for r in promoted+quarantined): failures.append('generation_reconnect_opened')
    if any(any(bool((r.get('authority') or {}).get(k)) for k in AUTHORITY_CLOSED) for r in promoted+quarantined): failures.append('authority_opened')
    target_pair_promoted=sum(1 for r in promoted if r['suffix_choice_target'] in {'expected_assertion_behavior__keep_value_small','current_repair_invariant__do_not_introduce'})
    if target_pair_promoted!=3: failures.append('target_pair_promoted_count_changed')
    wjl(PROMOTION,promoted); wjl(QUARANTINE,quarantined)
    audit={'passed':not failures,'failures':failures,'source_stage':'stage9419_best_suffix_choice_probe','promoted_rows':len(promoted),'quarantined_rows':len(quarantined),'split_counts':dict(sorted(split_counts.items())),'promoted_choice_counts':dict(sorted(promoted_counts.items())),'quarantined_choice_counts':dict(sorted(quarantined_counts.items())),'target_pair_promoted_rows':target_pair_promoted,'generation_reconnect_allowed_rows':0,'authority':dict(AUTHORITY_CLOSED),'decision':'controller_prior_only; no generation reconnect until a separate denoise reconnect probe is designed'}
    AUDIT.write_text(json.dumps(audit,indent=2,sort_keys=True)+'\n')
    summary={'stage':STAGE,'stage_name':NAME,'name':NAME,'passed':audit['passed'],'authority':dict(AUTHORITY_CLOSED),'metrics':{**dict(AUTHORITY_CLOSED),**audit},'artifacts':{'promotion_manifest':str(PROMOTION.relative_to(ROOT)),'quarantine_manifest':str(QUARANTINE.relative_to(ROOT)),'audit':str(AUDIT.relative_to(ROOT)),'doc':str(DOC.relative_to(ROOT))},'decision':'Promoted only Stage9419-correct suffix-choice decisions as controller priors and quarantined all residuals; no generation authority opened.','next_best_step':'Design a no-generation denoise reconnect preflight that consumes only ELIGIBLE_SUFFIX_CHOICE_PRIOR rows and keeps residual quarantines enforced.','created_at_utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime())}
    SUMMARY.write_text(json.dumps(summary,indent=2,sort_keys=True)+'\n')
    DOC.write_text('\n'.join(['# Stage9425 Suffix Choice Reconnect Guard Manifest','',f"Passed: `{audit['passed']}`",f"Promoted rows: `{len(promoted)}`",f"Quarantined rows: `{len(quarantined)}`",f"Target-pair promoted rows: `{target_pair_promoted}`",'','This does not open generation. Promoted rows are controller priors only until a separate denoise reconnect probe is designed.','']))
    reg=lj(REGISTRY) or {'rows':[],'metrics':{}}
    rr=[r for r in reg.get('rows',[]) if r.get('stage')!=STAGE and r.get('stage_name')!=NAME]
    rr.append({'stage':STAGE,'stage_name':NAME,'passed':summary['passed'],'path':str(SUMMARY),'authority':dict(AUTHORITY_CLOSED),'next_best_step':summary['next_best_step']})
    rr=sorted(rr,key=lambda r:(int(r.get('stage',-1)),r.get('stage_name','')))
    reg['rows']=rr; reg['passed']=summary['passed']; reg['metrics']={**(reg.get('metrics') or {}),'latest_stage':STAGE,'latest_stage_name':NAME,'latest_stage_next_best_step':summary['next_best_step'],'max_stage':STAGE,'registry_rows':len(rr),'authority_counts':{k:0 for k in AUTHORITY_CLOSED}}
    REGISTRY.write_text(json.dumps(reg,indent=2,sort_keys=True)+'\n')
    print(json.dumps({'stage':STAGE,'passed':summary['passed'],'metrics':{'promoted':len(promoted),'quarantined':len(quarantined),'target_pair_promoted':target_pair_promoted}},indent=2,sort_keys=True))
if __name__=='__main__': main()
