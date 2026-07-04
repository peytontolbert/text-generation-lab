#!/usr/bin/env python3
from __future__ import annotations
import collections, json, time
from pathlib import Path
from typing import Any
ROOT=Path(__file__).resolve().parents[1]
MANIFEST=ROOT/'runs/local/artifacts/stage8674_source_backed_symbol_binding_candidate_manifest/source_backed_symbol_binding_candidate_manifest.jsonl'
LINEAGE=ROOT/'configs/software_maintainer/source_inventory_lineage_registry_stage8663.json'
OUT_DIR=ROOT/'runs/local/artifacts/stage8675_source_backed_symbol_binding_candidate_manifest_audit'
SUMMARY=ROOT/'runs/summaries/stage8675_source_backed_symbol_binding_candidate_manifest_audit.json'
DOC=ROOT/'docs/SOURCE_BACKED_SYMBOL_BINDING_CANDIDATE_MANIFEST_AUDIT_STAGE8675.md'
AUTHORITY_CLOSED={'model_execution_authorized_next':False,'decoder_ce_training_authorized_next':False,'runtime_authorized':False,'source_emission_authorized':False,'body_emission_authorized':False,'gemma_execution_authorized_next':False,'harness_execution_authorized_next':False,'scoring_authorized_next':False,'controller_complete_merge_authorized_next':False,'promotion_ready':False}
def leaves(o):
 if isinstance(o,dict):
  for v in o.values(): yield from leaves(v)
 elif isinstance(o,list):
  for v in o: yield from leaves(v)
 else: yield o
def stable(o): return json.dumps(o,sort_keys=True,separators=(',',':'),default=str)
def main():
 OUT_DIR.mkdir(parents=True,exist_ok=True)
 lin=json.loads(LINEAGE.read_text())['records']; lin_by_id={r['source_id']:r for r in lin}; locked={r['source_id'] for r in lin if r.get('locked_eval')}
 failures=[]; rows=[]; actions=collections.Counter(); splits=collections.Counter(); feature_values=collections.defaultdict(collections.Counter); visible_target_hits=[]; forbidden=[]; missing=[]
 for line in MANIFEST.open():
  if not line.strip(): continue
  r=json.loads(line); rows.append(r); clean=r.get('clean_state') or {}; action=clean.get('binding_action'); actions[action]+=1; splits[r.get('split')]+=1
  # Required lineage and retrieval controls.
  sl=r.get('source_lineage') or {}; rc=r.get('retrieval_control') or {}
  for key in ['graph_nodes_source_id','graph_nodes_lineage_hash','graph_spans_source_id','graph_spans_lineage_hash']:
   if not sl.get(key): missing.append({'row_id':r.get('row_id'),'missing':key})
  if sl.get('graph_nodes_source_id') in locked or sl.get('graph_spans_source_id') in locked: missing.append({'row_id':r.get('row_id'),'missing':'locked_lineage_used'})
  if sl.get('graph_nodes_source_id') not in lin_by_id or sl.get('graph_spans_source_id') not in lin_by_id: missing.append({'row_id':r.get('row_id'),'missing':'unknown_lineage_source_id'})
  for key in ['bm25_top5_recall','dense_top5_recall','hybrid_rrf_top5_recall']:
   if key not in rc: missing.append({'row_id':r.get('row_id'),'missing':'retrieval_control.'+key})
  if rc.get('bm25_top5_recall',0) < .90: missing.append({'row_id':r.get('row_id'),'missing':'bm25_recall_floor'})
  # Leakage: target strings should not appear in graph_input/query/source_lineage/retrieval_control.
  visible={k:r[k] for k in ['graph_input','query','source_lineage','retrieval_control'] if k in r}
  vis=stable(visible)
  for v in leaves(clean):
   if isinstance(v,str) and len(v)>=4 and v in vis:
    visible_target_hits.append({'row_id':r.get('row_id'),'target_string':v[:120]}); break
  auth=r.get('authority') or {}; loss=r.get('loss_mask') or {}
  for k,v in auth.items():
   if v is True: forbidden.append({'row_id':r.get('row_id'),'field':'authority.'+k})
  for k in ['decoder_ce','denoise_ce','runtime_reward','symbol_binding_ce','source_backed_symbol_binding_candidate_ce']:
   if loss.get(k) is True: forbidden.append({'row_id':r.get('row_id'),'field':'loss_mask.'+k})
  g=r.get('graph_input') or {}; q=r.get('query') or {}
  feature_values['query_kind'][g.get('query_kind')]+=1
  feature_values['source_file_is_test'][str((q.get('features') or {}).get('source_file_is_test'))]+=1
  for n in g.get('nodes',[]):
   if n.get('node_type')=='file':
    nf=n.get('features') or {}
    for f in ['import_count_bucket','definition_count_bucket','call_count_bucket','path_depth_bucket','is_test']:
     feature_values[f][str(nf.get(f))]+=1
 if not rows: failures.append('no_rows')
 if missing: failures.append(f'missing_required_controls:{len(missing)}')
 if visible_target_hits: failures.append(f'visible_target_hits:{len(visible_target_hits)}')
 if forbidden: failures.append(f'forbidden_authority_or_loss:{len(forbidden)}')
 if len(set(actions.values()))!=1: failures.append('actions_not_balanced')
 # Shortcut risk report: max majority per single feature bucket. Report/block only if a feature has enough support and predicts one action >0.80.
 shortcut=[]
 for feat in feature_values:
  # Build action distribution by feature value.
  table=collections.defaultdict(collections.Counter)
  for r in rows:
   action=(r.get('clean_state') or {}).get('binding_action'); g=r.get('graph_input') or {}; q=r.get('query') or {}; val=None
   if feat=='query_kind': val=g.get('query_kind')
   elif feat=='source_file_is_test': val=str((q.get('features') or {}).get('source_file_is_test'))
   else:
    for n in g.get('nodes',[]):
     if n.get('node_type')=='file': val=str((n.get('features') or {}).get(feat)); break
   table[val][action]+=1
  for val,c in table.items():
   total=sum(c.values())
   if total>=10:
    maj=max(c.values())/total
    if maj>.80: shortcut.append({'feature':feat,'value':val,'majority':maj,'total':total,'dist':dict(c)})
 if shortcut: failures.append(f'shortcut_feature_cells:{len(shortcut)}')
 card={'stage':8675,'stage_name':'stage8675_source_backed_symbol_binding_candidate_manifest_audit','passed':not failures,'authority':AUTHORITY_CLOSED,'metrics':{'rows':len(rows),'actions':dict(actions),'splits':dict(splits),'missing_required_controls':len(missing),'visible_target_hits':len(visible_target_hits),'forbidden_authority_or_loss':len(forbidden),'shortcut_feature_cells':len(shortcut),'failures':failures,'decoder_ce_training_authorized_next':False,'denoise_ce_training_authorized_next':False,'model_execution_authorized_next':False,'runtime_authorized':False,'promotion_ready':False},'samples':{'missing':missing[:20],'visible_target_hits':visible_target_hits[:20],'forbidden':forbidden[:20],'shortcut':shortcut[:20]},'decision':'Source-backed symbol-binding candidate manifest passes control audit but remains no-authority candidate-only.' if not failures else 'Source-backed symbol-binding candidate manifest failed control audit; keep blocked.','next_best_step':'If passed, attach Stage8674/8675 to graph and use this manifest as the base for graph/symbol retrieval counterfactual expansion; if failed, repair listed failures.','created_at_utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime())}
 (OUT_DIR/'candidate_manifest_audit_card.json').write_text(json.dumps(card,indent=2,sort_keys=True)+'\n'); SUMMARY.write_text(json.dumps(card,indent=2,sort_keys=True)+'\n')
 DOC.write_text('# Stage8675 Source-Backed Symbol Binding Candidate Manifest Audit\n\n'+f"Passed: `{card['passed']}`\n\n- Rows: `{len(rows)}`\n- Actions: `{dict(actions)}`\n- Missing controls: `{len(missing)}`\n- Visible target hits: `{len(visible_target_hits)}`\n- Forbidden authority/loss: `{len(forbidden)}`\n- Shortcut feature cells: `{len(shortcut)}`\n- Failures: `{failures}`\n\nNo training authority opened.\n")
 print(json.dumps(card,indent=2,sort_keys=True)); raise SystemExit(0 if card['passed'] else 1)
if __name__=='__main__': main()
