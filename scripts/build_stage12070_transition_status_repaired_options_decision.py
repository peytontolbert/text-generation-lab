#!/usr/bin/env python3
from __future__ import annotations
import json, time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
ART=ROOT/'runs/local/artifacts'; SUM=ROOT/'runs/summaries'
NAME='stage12070_transition_status_repaired_options_decision'
OUT=ART/NAME; SUMMARY=OUT/'transition_status_repaired_options_decision.json'
AUDIT=ART/'stage12069_transition_status_head_repaired_options_composite_audit/transition_status_head_repaired_options_composite_audit.json'
PREFLIGHT=ART/'stage12067_status_head_repaired_options_differentiability_preflight/status_head_repaired_options_differentiability_preflight.json'

def rel(p): return str(p.relative_to(ROOT))
def load(p): return json.loads(p.read_text())
def main():
    OUT.mkdir(parents=True,exist_ok=True); SUM.mkdir(parents=True,exist_ok=True)
    audit=load(AUDIT); pre=load(PREFLIGHT)
    comp=audit['results']['stage12068_composite']
    by_task=comp['transition_by_task']
    weakest=sorted(by_task.items(), key=lambda kv: kv[1]['accuracy'])[0]
    payload={
        'stage':12070,
        'stage_name':NAME,
        'created_at_utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),
        'decision':'keep_stage11924_selected_transition_frontier_stage12068_is_retention_only',
        'selected_transition_frontier':'stage11924_transition_listwise_head_only_probe',
        'status_head_result':{
            'stage12067_preflight_passed':pre.get('passed'),
            'stage12068_runtime_saved':True,
            'stage12069_composite_score':comp['transition_projection_composite'],
            'gemma_reference':{'correct':386,'rows':640},
            'stage11924_reference':audit['results']['stage11924_baseline']['transition_projection_routed'],
        },
        'why_not_promoted':[
            'Composite routing retained Stage11924 at 364/640 but did not improve it.',
            'It remains below Gemma same-manifest 386/640.',
            'The status-head path is now technically viable after option mirroring, but verifier-transition did not become the main limiter.'
        ],
        'remaining_transition_breakdown':by_task,
        'weakest_family':{'task_type':weakest[0], **weakest[1]},
        'next_recommendation':{
            'recommended_stage':'stage12071_next_action_gap_atlas',
            'goal':'Analyze the 109/160 transition_next_action misses and build targeted next-action support/contrast rows rather than more verifier-status rows.',
            'minimum_next_probe_gate':{'old_transition_640':'>364 to count as progress; >386 for Gemma win','protected_gates':'filtered strict 22/22, old strict 23/23, residual >=7/10, smoke >=6/12'},
            'avoid':'Do not rerun broad v35/status-head integration; it already proved retention only.'
        },
        'source_artifacts':{'audit':rel(AUDIT),'preflight':rel(PREFLIGHT),'stage12069_summary':'runs/summaries/stage12069_transition_status_head_repaired_options_composite_audit.json'},
        'outputs':{'summary':rel(SUMMARY),'summary_mirror':f'runs/summaries/{NAME}.json'},
    }
    SUMMARY.write_text(json.dumps(payload,indent=2,sort_keys=True)+'\n')
    (SUM/f'{NAME}.json').write_text(json.dumps(payload,indent=2,sort_keys=True)+'\n')
    print(json.dumps({'decision':payload['decision'],'score':payload['status_head_result']['stage12069_composite_score'],'weakest_family':payload['weakest_family']},indent=2,sort_keys=True))
if __name__=='__main__': main()
