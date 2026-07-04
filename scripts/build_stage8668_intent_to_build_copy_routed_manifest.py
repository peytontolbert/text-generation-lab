#!/usr/bin/env python3
from __future__ import annotations
import json,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
SRC=ROOT/'runs/local/artifacts/stage8630_intent_to_build_neutral_manifest/intent_to_build_neutral_manifest.jsonl'
OUT_DIR=ROOT/'runs/local/artifacts/stage8668_intent_to_build_copy_routed_manifest'
OUT=OUT_DIR/'intent_to_build_copy_routed_manifest.jsonl'
SUMMARY=ROOT/'runs/summaries/stage8668_intent_to_build_copy_routed_manifest.json'
DOC=ROOT/'docs/INTENT_TO_BUILD_COPY_ROUTED_MANIFEST_STAGE8668.md'
AUTHORITY_CLOSED={'model_execution_authorized_next':False,'decoder_ce_training_authorized_next':False,'runtime_authorized':False,'source_emission_authorized':False,'body_emission_authorized':False,'gemma_execution_authorized_next':False,'harness_execution_authorized_next':False,'scoring_authorized_next':False,'controller_complete_merge_authorized_next':False,'promotion_ready':False}
def main():
 OUT_DIR.mkdir(parents=True,exist_ok=True)
 total=patched=unexpected=0
 with SRC.open() as f, OUT.open('w') as o:
  for line in f:
   if not line.strip(): continue
   r=json.loads(line); total+=1
   clean=r.setdefault('clean_state',{}); corr=r.get('corrupted_state') or {}; lm=r.setdefault('loss_mask',{})
   target=clean.get('repo_dependency_policy'); visible=corr.get('import_state')
   if target is not None and target==visible:
    patched+=1
    clean.pop('repo_dependency_policy',None)
    r.setdefault('copy_state',{})['repo_dependency_policy']={'copy_from':'corrupted_state.import_state','value_visible_in_input':True,'copy_route':'ROUTE_VISIBLE_COPY_FIELD'}
    if lm.get('repo_dependency_policy_ce') is True: lm['repo_dependency_policy_ce']=False
    lm['repo_dependency_policy_copy_ce']=True
    r['source_stage']='stage8668_copy_routed_from_stage8630'
   elif target is not None:
    unexpected+=1
   o.write(json.dumps(r,sort_keys=True)+'\n')
 card={'stage':8668,'stage_name':'stage8668_intent_to_build_copy_routed_manifest','passed':unexpected==0 and patched>0,'authority':AUTHORITY_CLOSED,'metrics':{'rows':total,'copy_routed_rows':patched,'unexpected_noncopy_rows':unexpected,'model_execution_authorized_next':False,'decoder_ce_training_authorized_next':False,'denoise_ce_training_authorized_next':False,'runtime_authorized':False,'promotion_ready':False},'artifacts':{'manifest':str(OUT.relative_to(ROOT)),'source_manifest':str(SRC.relative_to(ROOT))},'decision':'Intent-to-build direct-visible repo_dependency_policy targets are moved out of clean_state and into explicit copy_state supervision.','next_best_step':'Rerun leakage/locked-eval boundary using the copy-routed manifest in place of Stage8630.','created_at_utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime())}
 (OUT_DIR/'copy_routed_manifest_card.json').write_text(json.dumps(card,indent=2,sort_keys=True)+'\n'); SUMMARY.write_text(json.dumps(card,indent=2,sort_keys=True)+'\n')
 DOC.write_text('# Stage8668 Intent To Build Copy Routed Manifest\n\n'+f"Passed: `{card['passed']}`\n\n- Rows: `{total}`\n- Copy-routed rows: `{patched}`\n- Unexpected non-copy rows: `{unexpected}`\n\nAll authorities remain closed.\n")
 print(json.dumps(card,indent=2,sort_keys=True))
 raise SystemExit(0 if card['passed'] else 1)
if __name__=='__main__': main()
