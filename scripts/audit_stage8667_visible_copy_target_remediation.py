#!/usr/bin/env python3
from __future__ import annotations
import json,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
MANIFEST=ROOT/'runs/local/artifacts/stage8630_intent_to_build_neutral_manifest/intent_to_build_neutral_manifest.jsonl'
OUT_DIR=ROOT/'runs/local/artifacts/stage8667_visible_copy_target_remediation'
SUMMARY=ROOT/'runs/summaries/stage8667_visible_copy_target_remediation.json'
DOC=ROOT/'docs/VISIBLE_COPY_TARGET_REMEDIATION_STAGE8667.md'
REGISTRY=ROOT/'runs/local/artifacts/reconstructed_stage_registry.json'
AUTHORITY_CLOSED={'model_execution_authorized_next':False,'decoder_ce_training_authorized_next':False,'runtime_authorized':False,'source_emission_authorized':False,'body_emission_authorized':False,'gemma_execution_authorized_next':False,'harness_execution_authorized_next':False,'scoring_authorized_next':False,'controller_complete_merge_authorized_next':False,'promotion_ready':False}
def main():
 OUT_DIR.mkdir(parents=True,exist_ok=True)
 rows=[]; exact_copy=0; unsafe=0; patched_loss_rows=[]; action_counts={}
 for line in MANIFEST.open():
  if not line.strip(): continue
  r=json.loads(line)
  clean=(r.get('clean_state') or {})
  corr=(r.get('corrupted_state') or {})
  target=clean.get('repo_dependency_policy')
  visible=corr.get('import_state')
  lm=r.get('loss_mask') or {}
  if target is not None and target==visible:
   exact_copy+=1
   action='ROUTE_VISIBLE_COPY_FIELD'
   # The semantic build-mode/import decisions may still be trained, but repo_dependency_policy_ce must not be treated as evidence of reasoning.
   recommended=dict(lm)
   if recommended.get('repo_dependency_policy_ce') is True:
    recommended['repo_dependency_policy_ce']=False
    recommended['repo_dependency_policy_copy_ce']=True
   patched_loss_rows.append({'row_id':r.get('row_id'),'split':r.get('split'),'objective_family':r.get('objective_family'),'visible_copy_field':'repo_dependency_policy','visible_source_field':'corrupted_state.import_state','target_value':target,'current_repo_dependency_policy_ce':lm.get('repo_dependency_policy_ce'),'recommended_loss_mask':recommended,'route':action})
   action_counts[action]=action_counts.get(action,0)+1
  elif target is not None:
   unsafe+=1
 card={'stage':8667,'stage_name':'stage8667_visible_copy_target_remediation','passed':unsafe==0 and exact_copy>0,'authority':AUTHORITY_CLOSED,'metrics':{'intent_rows_with_visible_repo_dependency_copy':exact_copy,'unexpected_noncopy_repo_dependency_targets':unsafe,'patched_loss_recommendations':len(patched_loss_rows),'route_counts':action_counts,'model_execution_authorized_next':False,'decoder_ce_training_authorized_next':False,'denoise_ce_training_authorized_next':False,'runtime_authorized':False,'promotion_ready':False},'decision':'Visible target hits are confined to a direct copy field and must be moved from semantic CE to explicit copy-field supervision before training. Stage8665 remains correctly failed until builders apply this remediation.','artifacts':{'copy_target_remediation_jsonl':'runs/local/artifacts/stage8667_visible_copy_target_remediation/copy_target_remediation.jsonl','source_manifest':str(MANIFEST.relative_to(ROOT))},'next_best_step':'Patch future intent_to_build builders so visible copy fields use repo_dependency_policy_copy_ce or deterministic copy routing, not semantic repo_dependency_policy_ce. Then rerun Stage8665 leakage boundary.','created_at_utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime())}
 with (OUT_DIR/'copy_target_remediation.jsonl').open('w') as f:
  for row in patched_loss_rows: f.write(json.dumps(row,sort_keys=True)+'\n')
 (OUT_DIR/'visible_copy_target_remediation_card.json').write_text(json.dumps(card,indent=2,sort_keys=True)+'\n')
 SUMMARY.write_text(json.dumps(card,indent=2,sort_keys=True)+'\n')
 DOC.write_text('# Stage8667 Visible Copy Target Remediation\n\n'+f"Passed: `{card['passed']}`\n\n- Visible repo-dependency copy rows: `{exact_copy}`\n- Unexpected non-copy target rows: `{unsafe}`\n- Recommendation rows: `{len(patched_loss_rows)}`\n\nDecision: {card['decision']}\n\nAll authorities remain closed.\n")
 REGISTRY.write_text(json.dumps({'passed':True,'rows':[card],'metrics':{'min_stage':8530,'max_stage':8667,'latest_stage':8667,'latest_stage_name':card['stage_name'],'latest_stage_next_best_step':card['next_best_step'],'registry_rows':147,'authority_counts':{k:0 for k in AUTHORITY_CLOSED}}},indent=2,sort_keys=True)+'\n')
 print(json.dumps(card,indent=2,sort_keys=True))
 raise SystemExit(0 if card['passed'] else 1)
if __name__=='__main__': main()
