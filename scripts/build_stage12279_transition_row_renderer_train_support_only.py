#!/usr/bin/env python3
"""Build Stage12279 train-support-only transition rows from preflight-approved candidates."""
from __future__ import annotations
import hashlib, json
from collections import Counter
from pathlib import Path
from typing import Any

ROOT=Path(__file__).resolve().parents[1]
STAGE='stage12279_transition_row_renderer_train_support_only'
ALLOWED=ROOT/'runs/local/artifacts/stage12278_transition_row_renderer_preflight/render_allowed_train_support_candidates.jsonl'
PACKETS=ROOT/'runs/local/artifacts/stage12275_semantic_review_packet_for_status_candidates/semantic_review_packets.jsonl'
OUT=ROOT/f'runs/local/artifacts/{STAGE}'
SUMMARY=ROOT/f'runs/summaries/{STAGE}.json'

def sid(prefix,*parts):
    return prefix+'_'+hashlib.sha256(json.dumps(parts,sort_keys=True,default=str).encode()).hexdigest()[:20]

def iter_jsonl(path:Path):
    with path.open('r',encoding='utf-8',errors='ignore') as f:
        for line in f:
            line=line.strip()
            if line: yield json.loads(line)

def write_json(path:Path,val:Any):
    path.parent.mkdir(parents=True,exist_ok=True); path.write_text(json.dumps(val,indent=2,sort_keys=True)+'\n',encoding='utf-8')

def write_jsonl(path:Path,rows:list[dict[str,Any]]):
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('w',encoding='utf-8') as f:
        for r in rows: f.write(json.dumps(r,sort_keys=True)+'\n')

def main():
    packets={r['child_loop_id']:r for r in iter_jsonl(PACKETS)}
    rendered=[]; blocked=[]
    for cand in iter_jsonl(ALLOWED):
        cid=cand['child_loop_id']; pkt=packets.get(cid)
        if not pkt:
            cand['render_blocked_reason']='packet_join_missing'; blocked.append(cand); continue
        lin=cand.get('lineage') or {}; root=cand.get('root_recovery') or {}; review=cand.get('review') or {}
        if not (pkt.get('patch_ref') and pkt.get('pre_verifier_statuses') is not None and pkt.get('post_verifier_statuses')):
            cand['render_blocked_reason']='missing_patch_or_status_refs'; blocked.append(cand); continue
        base={
          'schema_version':'train_support_transition_row_v1',
          'stage':STAGE,
          'source_child_loop_id':cid,
          'row_id':sid('transition_row',cid,'verifier_transition'),
          'split':'train_support_dev',
          'task_family':'transition_verifier_transition',
          'repo_family_label':root.get('repo_family_label'),
          'language_family':root.get('language_family_hint'),
          'source_refs':cand.get('source_refs'),
          'root_lineage_key':lin.get('root_lineage_key'),
          'split_group_id':lin.get('split_group_id'),
          'state_before_ref':sid('state_before',cid,pkt.get('child_span_refs',{}).get('child_start_line')),
          'state_before_summary_codes':['pre_patch_failure_observed','external_repo_hint','semantic_repair_smoke'],
          'candidate_action_set':[
            {'candidate_id':'A','semantic_action':'CONTINUE_REPAIR_AND_VERIFY'},
            {'candidate_id':'B','semantic_action':'STOP_AS_EXTERNAL_COMPARABLE_REPAIR'},
            {'candidate_id':'C','semantic_action':'QUARANTINE_AS_ENV_FAILURE'},
          ],
          'chosen_action':{'candidate_id':'A','semantic_action':'CONTINUE_REPAIR_AND_VERIFY'},
          'observation_status_refs':{
            'pre_verifier_statuses':pkt.get('pre_verifier_statuses'),
            'post_verifier_statuses':pkt.get('post_verifier_statuses'),
            'raw_output_emitted':False,
          },
          'patch_ref_digest':(pkt.get('patch_ref') or {}).get('output_digest'),
          'state_delta_codes':['post_patch_pass_observed','not_same_exact_verifier','train_support_only'],
          'stop_continue_label':'CONTINUE_NOT_PROMOTABLE',
          'verifier_transition_label':'FAIL_TO_PASS_SMOKE_NOT_COMPARABLE',
          'review_decision':review,
          'semantic_relevance_flags':{
            'semantic_verifier_relevance_proven':review.get('semantic_verifier_relevance_proven'),
            'same_verifier_strict_enough':review.get('same_verifier_strict_enough'),
            'patch_effective_enough':review.get('patch_effective_enough'),
            'external_comparable_countable':False,
          },
          'visibility_masks':{
            'pre_action_model_input':['state_before_ref','state_before_summary_codes','candidate_action_set','repo_family_label','language_family'],
            'target_only':['chosen_action','observation_status_refs','state_delta_codes','stop_continue_label','verifier_transition_label'],
            'never_emit':['raw_tool_output','raw_tool_arguments','raw_patch_body','raw_source_path','full_command_text'],
          },
          'admission':{
            'train_support_allowed':True,
            'strict_eval_eligible':False,
            'source_heldout_admissible':False,
            'external_comparable_patch_trace_countable':False,
            'external_fail_to_pass_countable':False,
          },
          'guardrails':{'raw_output_emitted':False,'raw_patch_body_emitted':False,'raw_tool_arguments_emitted':False,'raw_source_path_emitted':False},
        }
        rendered.append(base)
    summary={
      'stage':STAGE,
      'decision':'train_support_transition_rows_rendered_not_eval_not_comparable',
      'input_candidates':len(list(iter_jsonl(ALLOWED))),
      'rendered_rows':len(rendered),
      'blocked_rows':len(blocked),
      'task_family_counts':dict(Counter(r['task_family'] for r in rendered)),
      'repo_family_counts':dict(Counter(r['repo_family_label'] for r in rendered)),
      'external_comparable_patch_trace_rows':0,
      'external_fail_to_pass_rows':0,
      'strict_eval_rows':0,
      'source_heldout_rows':0,
      'raw_guardrail_violations':sum(1 for r in rendered if any(r['guardrails'].values())),
      'next_stage':'stage12280_external_exact_verifier_candidate_expansion',
    }
    write_jsonl(OUT/'train_support_transition_rows.jsonl',rendered)
    write_jsonl(OUT/'render_blocked_rows.jsonl',blocked)
    write_json(OUT/'transition_row_renderer_train_support_summary.json',summary)
    write_json(SUMMARY,summary)
    (OUT/'TRANSITION_ROW_RENDERER_TRAIN_SUPPORT_STAGE12279.md').write_text('# Stage12279 Train-Support Transition Renderer\n\n'+json.dumps(summary,indent=2)+'\n',encoding='utf-8')
if __name__=='__main__': main()
