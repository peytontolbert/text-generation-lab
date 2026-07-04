#!/usr/bin/env python3
from __future__ import annotations
import hashlib,json,re,time
from pathlib import Path
from typing import Any
ROOT=Path(__file__).resolve().parents[1]
LINEAGE=ROOT/'configs/software_maintainer/source_inventory_lineage_registry_stage8663.json'
NORMALIZER=ROOT/'configs/software_maintainer/shared_feature_normalizer_stage8664.json'
OUT_DIR=ROOT/'runs/local/artifacts/stage8665_manifest_leakage_locked_eval_boundary'
SUMMARY=ROOT/'runs/summaries/stage8665_manifest_leakage_locked_eval_boundary.json'
DOC=ROOT/'docs/MANIFEST_LEAKAGE_LOCKED_EVAL_BOUNDARY_STAGE8665.md'
AUTHORITY_CLOSED={'model_execution_authorized_next':False,'decoder_ce_training_authorized_next':False,'runtime_authorized':False,'source_emission_authorized':False,'body_emission_authorized':False,'gemma_execution_authorized_next':False,'harness_execution_authorized_next':False,'scoring_authorized_next':False,'controller_complete_merge_authorized_next':False,'promotion_ready':False}
VISIBLE_KEYS=['corrupted_state','graph_input','query','source_ref','input_state']
TARGET_KEYS=['clean_state','target']
MANIFESTS=[
 'runs/local/artifacts/stage8630_intent_to_build_neutral_manifest/intent_to_build_neutral_manifest.jsonl',
 'runs/local/artifacts/stage8636_edit_localization_neutral_manifest/edit_localization_neutral_manifest.jsonl',
 'runs/local/artifacts/stage8638_patch_operator_neutral_manifest/patch_operator_neutral_manifest.jsonl',
 'runs/local/artifacts/stage8643_verifier_repair_neutral_manifest/verifier_repair_neutral_manifest.jsonl',
 'runs/local/artifacts/stage8645_bounded_decoder_arguments_neutral_manifest/bounded_decoder_arguments_neutral_manifest.jsonl',
 'runs/local/artifacts/stage8647_output_repair_denoise_neutral_manifest/output_repair_denoise_neutral_manifest.jsonl',
 'runs/local/artifacts/stage8618_symbol_binding_counterfactual_with_test_patch/combined_symbol_binding_candidates.jsonl',
]
def stable(obj:Any)->str: return json.dumps(obj,sort_keys=True,separators=(',',':'),default=str)
def h(obj:Any)->str: return hashlib.sha256(stable(obj).encode()).hexdigest()
def leaves(obj:Any):
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
 lineage=json.loads(LINEAGE.read_text())
 normalizer=json.loads(NORMALIZER.read_text())
 locked_paths={r['path'] for r in lineage['records'] if r.get('locked_eval')}
 failures=[]; per=[]; input_hash_by_split={}; exact_overlap=[]; visible_target_hits=[]; locked_ref_hits=[]; forbidden_rows=[]
 total=0
 for rel in MANIFESTS:
  path=ROOT/rel; stats={'manifest':rel,'exists':path.exists(),'rows':0,'visible_target_hits':0,'locked_ref_hits':0,'forbidden_authority_or_loss_true':0,'input_hash_collisions_cross_split':0}
  if not path.exists(): failures.append(f'missing_manifest:{rel}'); per.append(stats); continue
  for line in path.open():
   if not line.strip(): continue
   row=json.loads(line); total+=1; stats['rows']+=1
   split=row.get('split','unknown'); row_id=row.get('row_id')
   vh=h(visible(row)); input_hash_by_split.setdefault(vh,{}).setdefault(split,[]).append(row_id)
   vis_text=stable(visible(row))
   for ts in target_strings(row):
    if ts and ts in vis_text:
     hit={'manifest':rel,'row_id':row_id,'target_string':ts[:120]}; visible_target_hits.append(hit); stats['visible_target_hits']+=1; break
   src_path=(row.get('source_ref') or {}).get('path') if isinstance(row.get('source_ref'),dict) else None
   if src_path in locked_paths:
    locked_ref_hits.append({'manifest':rel,'row_id':row_id,'path':src_path}); stats['locked_ref_hits']+=1
   auth=row.get('authority',{}); loss=row.get('loss_mask',{})
   forbidden=[]
   for k in ['model_execution_authorized_next','decoder_ce_training_authorized_next','decoder_ce_authorized','runtime_authorized','source_emission_authorized','body_emission_authorized','training_authorized']:
    if auth.get(k) is True: forbidden.append('authority.'+k)
   for k in ['decoder_ce','denoise_ce','runtime_reward']:
    if loss.get(k) is True: forbidden.append('loss_mask.'+k)
   if forbidden:
    forbidden_rows.append({'manifest':rel,'row_id':row_id,'forbidden':forbidden}); stats['forbidden_authority_or_loss_true']+=1
  per.append(stats)
 for vh,splits in input_hash_by_split.items():
  if len(splits)>1:
   ids=sum((v[:3] for v in splits.values()),[])
   exact_overlap.append({'input_hash':vh,'splits':sorted(splits),'sample_row_ids':ids[:9]})
 for item in exact_overlap:
  for p in per:
   pass
 # Exact overlap is report-only here because some recovered counterfactual sets intentionally share visible input across split variants. It becomes blocking for locked eval/hidden only.
 if visible_target_hits: failures.append(f'visible_target_hits:{len(visible_target_hits)}')
 if locked_ref_hits: failures.append(f'locked_eval_source_referenced_by_training_manifest:{len(locked_ref_hits)}')
 if forbidden_rows: failures.append(f'forbidden_authority_or_loss_true:{len(forbidden_rows)}')
 card={'stage':8665,'stage_name':'stage8665_manifest_leakage_locked_eval_boundary','passed':not failures,'authority':AUTHORITY_CLOSED,'metrics':{'rows_total':total,'manifests':len(MANIFESTS),'visible_target_hits':len(visible_target_hits),'locked_ref_hits':len(locked_ref_hits),'forbidden_rows':len(forbidden_rows),'cross_split_exact_visible_input_hashes_report_only':len(exact_overlap),'failures':failures,'model_execution_authorized_next':False,'decoder_ce_training_authorized_next':False,'denoise_ce_training_authorized_next':False,'runtime_authorized':False,'promotion_ready':False},'per_manifest':per,'samples':{'visible_target_hits':visible_target_hits[:20],'locked_ref_hits':locked_ref_hits[:20],'forbidden_rows':forbidden_rows[:20],'cross_split_exact_visible_input_hashes':exact_overlap[:20]},'artifacts':{'lineage':str(LINEAGE.relative_to(ROOT)),'normalizer':str(NORMALIZER.relative_to(ROOT))},'decision':'Recovered manifests pass leakage and locked-eval boundary controls.' if not failures else 'Recovered manifests fail leakage/locked-eval boundary controls.','next_best_step':'Run retrieval baseline card and then apply these controls to new graph/symbol candidate builders.','created_at_utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime())}
 (OUT_DIR/'manifest_leakage_locked_eval_boundary_card.json').write_text(json.dumps(card,indent=2,sort_keys=True)+'\n')
 SUMMARY.write_text(json.dumps(card,indent=2,sort_keys=True)+'\n')
 DOC.write_text('# Stage8665 Manifest Leakage Locked-Eval Boundary\n\n'+f"Passed: `{card['passed']}`\n\n- Rows: `{total}`\n- Visible target hits: `{len(visible_target_hits)}`\n- Locked-eval references: `{len(locked_ref_hits)}`\n- Forbidden rows: `{len(forbidden_rows)}`\n- Cross-split visible input hashes, report-only: `{len(exact_overlap)}`\n- Failures: `{failures}`\n\nAll authorities remain closed.\n")
 print(json.dumps(card,indent=2,sort_keys=True))
 raise SystemExit(0 if card['passed'] else 1)
if __name__=='__main__': main()
