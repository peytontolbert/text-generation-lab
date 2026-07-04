#!/usr/bin/env python3
from __future__ import annotations
import collections, hashlib, json, time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
SRC=ROOT/'runs/local/artifacts/stage8618_symbol_binding_counterfactual_with_test_patch/combined_symbol_binding_candidates.jsonl'
LINEAGE=ROOT/'configs/software_maintainer/source_inventory_lineage_registry_stage8663.json'
RETRIEVAL=ROOT/'runs/summaries/stage8671_dense_hybrid_retrieval_baseline.json'
OUT_DIR=ROOT/'runs/local/artifacts/stage8674_source_backed_symbol_binding_candidate_manifest'
OUT=OUT_DIR/'source_backed_symbol_binding_candidate_manifest.jsonl'
SUMMARY=ROOT/'runs/summaries/stage8674_source_backed_symbol_binding_candidate_manifest.json'
DOC=ROOT/'docs/SOURCE_BACKED_SYMBOL_BINDING_CANDIDATE_MANIFEST_STAGE8674.md'
AUTHORITY_CLOSED={'model_execution_authorized_next':False,'decoder_ce_training_authorized_next':False,'runtime_authorized':False,'source_emission_authorized':False,'body_emission_authorized':False,'gemma_execution_authorized_next':False,'harness_execution_authorized_next':False,'scoring_authorized_next':False,'controller_complete_merge_authorized_next':False,'promotion_ready':False}
LOSS_MASK={'decoder_ce':False,'denoise_ce':False,'runtime_reward':False,'symbol_binding_ce':False,'source_backed_symbol_binding_candidate_ce':False}
ACTIONS=['RETRIEVE_MORE','BIND_CALL_TO_SYMBOL','BIND_TEST_TO_SYMBOL','ABSTAIN_UNBOUND','BIND_IMPORT_TO_MODULE']
def opaque(s:str,prefix='o')->str: return prefix+'_'+hashlib.sha256(s.encode()).hexdigest()[:16]
def main():
 OUT_DIR.mkdir(parents=True,exist_ok=True)
 lineage=json.loads(LINEAGE.read_text())['records']
 lin_by_path={r['path']:r for r in lineage}
 nodes_lin=lin_by_path['/arxiv/TOLBERT_BRAIN/data/repos/nodes_repos.jsonl']
 spans_lin=lin_by_path['/arxiv/TOLBERT_BRAIN/data/repos/spans_repos.jsonl']
 retrieval=json.loads(RETRIEVAL.read_text())
 buckets=collections.defaultdict(list)
 for line in SRC.open():
  if not line.strip(): continue
  r=json.loads(line); action=(r.get('target') or {}).get('binding_action')
  if action in ACTIONS: buckets[action].append(r)
 cap=min(len(buckets[a]) for a in ACTIONS)
 rows=[]; counts=collections.Counter(); splits=collections.Counter(); source_paths=collections.Counter()
 for action in ACTIONS:
  selected=buckets[action][:cap]
  for idx,r in enumerate(selected):
   old_id=r.get('row_id','')
   graph=r.get('graph_input') or {}; query=r.get('query') or {}; target=r.get('target') or {}; old_src=r.get('source_ref') or {}
   row_id='stage8674_'+opaque(old_id,'row')
   source_paths[old_src.get('path')]+=1
   clean={'binding_action':target.get('binding_action'),'target_node_kind':target.get('target_node_kind')}
   if target.get('target_node_id') is not None:
    clean['target_node_presence']='TARGET_NODE_PRESENT'
   else:
    clean['target_node_presence']='NO_TARGET_NODE'
   # Keep target_node_id out of clean_state/model target because old node IDs can act as memorized identifiers.
   out={
    'row_id':row_id,
    'source_row_id':old_id,
    'split':r.get('split'),
    'objective_family':'source_backed_symbol_binding',
    'source_stage':'stage8674_from_stage8618_with_lineage_controls',
    'semantic_key':f"{r.get('split')}:{action}:{graph.get('query_kind')}:{query.get('query_node_id')}",
    'authority':AUTHORITY_CLOSED,
    'loss_mask':LOSS_MASK,
    'source_lineage':{
      'graph_nodes_source_id':nodes_lin['source_id'], 'graph_nodes_lineage_hash':nodes_lin['lineage_hash'],
      'graph_spans_source_id':spans_lin['source_id'], 'graph_spans_lineage_hash':spans_lin['lineage_hash'],
      'old_source_ref_path':old_src.get('path'), 'old_source_ref_in_model_input':False,
      'locked_eval_source':False, 'train_eligible_lineage':True},
    'retrieval_control':{
      'retrieval_required':True,
      'retrieval_baseline_stage':'stage8671_dense_hybrid_retrieval_baseline',
      'bm25_top5_recall':retrieval['metrics']['bm25_top5'],
      'dense_top5_recall':retrieval['metrics']['dense_top5'],
      'hybrid_rrf_top5_recall':retrieval['metrics']['hybrid_rrf_top5'],
      'metadata_only_disallowed':True,
      'evidence_removed_disallowed':True},
    'graph_input':graph,
    'query':query,
    'clean_state':clean,
    'anti_cheat':{
      'raw_source_included':False,'raw_symbol_names_in_model_input':False,'target_label_in_id':False,'target_node_id_in_model_input':False,'requires_shortcut_audit_before_training':True,'requires_retrieval_card_before_training':True},
    'route':'CANDIDATE_NEEDS_AUDIT'}
   rows.append(out); counts[action]+=1; splits[r.get('split')]+=1
 with OUT.open('w') as f:
  for r in rows: f.write(json.dumps(r,sort_keys=True)+'\n')
 card={'stage':8674,'stage_name':'stage8674_source_backed_symbol_binding_candidate_manifest','passed':len(rows)>0 and len(set(counts.values()))==1,'authority':AUTHORITY_CLOSED,'metrics':{'rows':len(rows),'actions':dict(counts),'cap_per_action':cap,'splits':dict(splits),'old_source_paths':len(source_paths),'decoder_ce_training_authorized_next':False,'denoise_ce_training_authorized_next':False,'model_execution_authorized_next':False,'runtime_authorized':False,'promotion_ready':False},'artifacts':{'manifest':str(OUT.relative_to(ROOT)),'source_manifest':str(SRC.relative_to(ROOT)),'lineage_registry':str(LINEAGE.relative_to(ROOT)),'retrieval_baseline':str(RETRIEVAL.relative_to(ROOT))},'decision':'Built a balanced no-authority source-backed symbol-binding candidate manifest with lineage and retrieval controls; still not training-authorized.','next_best_step':'Run Stage8675 audit for lineage, leakage, shortcut baselines, retrieval control presence, and locked-eval exclusion.','created_at_utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime())}
 (OUT_DIR/'candidate_manifest_card.json').write_text(json.dumps(card,indent=2,sort_keys=True)+'\n'); SUMMARY.write_text(json.dumps(card,indent=2,sort_keys=True)+'\n')
 DOC.write_text('# Stage8674 Source-Backed Symbol Binding Candidate Manifest\n\n'+f"Passed: `{card['passed']}`\n\n- Rows: `{len(rows)}`\n- Cap per action: `{cap}`\n- Actions: `{dict(counts)}`\n- Splits: `{dict(splits)}`\n\nNo training authority opened.\n")
 print(json.dumps(card,indent=2,sort_keys=True)); raise SystemExit(0 if card['passed'] else 1)
if __name__=='__main__': main()
