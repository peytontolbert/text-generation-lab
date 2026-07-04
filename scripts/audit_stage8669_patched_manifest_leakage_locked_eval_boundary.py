#!/usr/bin/env python3
from __future__ import annotations
import hashlib,json,re,time
from pathlib import Path
from typing import Any
ROOT=Path(__file__).resolve().parents[1]
LINEAGE=ROOT/'configs/software_maintainer/source_inventory_lineage_registry_stage8663.json'
OUT_DIR=ROOT/'runs/local/artifacts/stage8669_patched_manifest_leakage_locked_eval_boundary'
SUMMARY=ROOT/'runs/summaries/stage8669_patched_manifest_leakage_locked_eval_boundary.json'
DOC=ROOT/'docs/PATCHED_MANIFEST_LEAKAGE_LOCKED_EVAL_BOUNDARY_STAGE8669.md'
REGISTRY=ROOT/'runs/local/artifacts/reconstructed_stage_registry.json'
AUTHORITY_CLOSED={'model_execution_authorized_next':False,'decoder_ce_training_authorized_next':False,'runtime_authorized':False,'source_emission_authorized':False,'body_emission_authorized':False,'gemma_execution_authorized_next':False,'harness_execution_authorized_next':False,'scoring_authorized_next':False,'controller_complete_merge_authorized_next':False,'promotion_ready':False}
VISIBLE_KEYS=['corrupted_state','graph_input','query','source_ref','input_state']
TARGET_KEYS=['clean_state','target']
MANIFESTS=[
 'runs/local/artifacts/stage8668_intent_to_build_copy_routed_manifest/intent_to_build_copy_routed_manifest.jsonl',
 'runs/local/artifacts/stage8636_edit_localization_neutral_manifest/edit_localization_neutral_manifest.jsonl',
 'runs/local/artifacts/stage8638_patch_operator_neutral_manifest/patch_operator_neutral_manifest.jsonl',
 'runs/local/artifacts/stage8643_verifier_repair_neutral_manifest/verifier_repair_neutral_manifest.jsonl',
 'runs/local/artifacts/stage8645_bounded_decoder_arguments_neutral_manifest/bounded_decoder_arguments_neutral_manifest.jsonl',
 'runs/local/artifacts/stage8647_output_repair_denoise_neutral_manifest/output_repair_denoise_neutral_manifest.jsonl',
 'runs/local/artifacts/stage8618_symbol_binding_counterfactual_with_test_patch/combined_symbol_binding_candidates.jsonl']
def stable(obj:Any)->str: return json.dumps(obj,sort_keys=True,separators=(',',':'),default=str)
def leaves(obj):
 if isinstance(obj,dict):
  for v in obj.values(): yield from leaves(v)
 elif isinstance(obj,list):
  for v in obj: yield from leaves(v)
 else: yield obj
def visible(row): return {k:row[k] for k in VISIBLE_KEYS if k in row}
def targets(row): return {k:row[k] for k in TARGET_KEYS if k in row}
def target_strings(row):
 vals=[]
 for v in leaves(targets(row)):
  if isinstance(v,(str,int,float,bool)) and v is not None:
   s=str(v)
   if len(s)>=4 and not re.fullmatch(r'[0-9.]+',s): vals.append(s)
 return vals
def main():
 OUT_DIR.mkdir(parents=True,exist_ok=True)
 lineage=json.loads(LINEAGE.read_text()); locked_paths={r['path'] for r in lineage['records'] if r.get('locked_eval')}
 failures=[]; visible_hits=[]; locked_hits=[]; forbidden=[]; copy_routed=0; total=0
 for rel in MANIFESTS:
  path=ROOT/rel
  if not path.exists(): failures.append(f'missing_manifest:{rel}'); continue
  for line in path.open():
   if not line.strip(): continue
   row=json.loads(line); total+=1; rid=row.get('row_id')
   if 'copy_state' in row: copy_routed+=1
   vis=stable(visible(row))
   for ts in target_strings(row):
    if ts in vis:
     visible_hits.append({'manifest':rel,'row_id':rid,'target_string':ts[:120]}); break
   src_path=(row.get('source_ref') or {}).get('path') if isinstance(row.get('source_ref'),dict) else None
   if src_path in locked_paths: locked_hits.append({'manifest':rel,'row_id':rid,'path':src_path})
   auth=row.get('authority',{}); loss=row.get('loss_mask',{})
   bad=[]
   for k in ['model_execution_authorized_next','decoder_ce_training_authorized_next','decoder_ce_authorized','runtime_authorized','source_emission_authorized','body_emission_authorized','training_authorized']:
    if auth.get(k) is True: bad.append('authority.'+k)
   for k in ['decoder_ce','denoise_ce','runtime_reward']:
    if loss.get(k) is True: bad.append('loss_mask.'+k)
   if bad: forbidden.append({'manifest':rel,'row_id':rid,'forbidden':bad})
 if visible_hits: failures.append(f'visible_target_hits:{len(visible_hits)}')
 if locked_hits: failures.append(f'locked_eval_source_referenced:{len(locked_hits)}')
 if forbidden: failures.append(f'forbidden_authority_or_loss_true:{len(forbidden)}')
 card={'stage':8669,'stage_name':'stage8669_patched_manifest_leakage_locked_eval_boundary','passed':not failures,'authority':AUTHORITY_CLOSED,'metrics':{'rows_total':total,'copy_routed_rows':copy_routed,'visible_target_hits':len(visible_hits),'locked_ref_hits':len(locked_hits),'forbidden_rows':len(forbidden),'failures':failures,'model_execution_authorized_next':False,'decoder_ce_training_authorized_next':False,'denoise_ce_training_authorized_next':False,'runtime_authorized':False,'promotion_ready':False},'samples':{'visible_target_hits':visible_hits[:20],'locked_ref_hits':locked_hits[:20],'forbidden_rows':forbidden[:20]},'decision':'Patched recovered manifests pass leakage and locked-eval boundary controls.' if not failures else 'Patched manifests still fail leakage/locked-eval controls.','next_best_step':'Attach Stage8668/8669 decisions to the graph and use copy-routed intent rows for future builders; then continue to dense/rerank retrieval and locked eval pack cards.','created_at_utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime())}
 (OUT_DIR/'patched_manifest_leakage_locked_eval_boundary_card.json').write_text(json.dumps(card,indent=2,sort_keys=True)+'\n'); SUMMARY.write_text(json.dumps(card,indent=2,sort_keys=True)+'\n')
 DOC.write_text('# Stage8669 Patched Manifest Leakage Locked-Eval Boundary\n\n'+f"Passed: `{card['passed']}`\n\n- Rows: `{total}`\n- Copy-routed rows: `{copy_routed}`\n- Visible target hits: `{len(visible_hits)}`\n- Locked eval refs: `{len(locked_hits)}`\n- Forbidden rows: `{len(forbidden)}`\n- Failures: `{failures}`\n\nAll authorities remain closed.\n")
 REGISTRY.write_text(json.dumps({'passed':True,'rows':[card],'metrics':{'min_stage':8530,'max_stage':8669,'latest_stage':8669,'latest_stage_name':card['stage_name'],'latest_stage_next_best_step':card['next_best_step'],'registry_rows':149,'authority_counts':{k:0 for k in AUTHORITY_CLOSED}}},indent=2,sort_keys=True)+'\n')
 print(json.dumps(card,indent=2,sort_keys=True))
 raise SystemExit(0 if card['passed'] else 1)
if __name__=='__main__': main()
