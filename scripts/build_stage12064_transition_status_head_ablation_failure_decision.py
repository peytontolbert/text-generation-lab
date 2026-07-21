#!/usr/bin/env python3
"""Record Stage12063 transition-status-head ablation failure."""
from __future__ import annotations
import json, time
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
ART=ROOT/'runs/local/artifacts'
SUM=ROOT/'runs/summaries'
NAME='stage12064_transition_status_head_ablation_failure_decision'
OUT=ART/NAME
SUMMARY=OUT/'transition_status_head_ablation_failure_decision.json'
REQ=ART/'stage12062_transition_status_head_ablation_request/transition_status_head_ablation_request.json'
PROBE=ART/'stage12063_transition_status_head_ablation_probe/bounded_decoder_probe'
LOSS=PROBE/'loss_by_step.jsonl'
RUNTIME=ART/'stage12063_transition_status_head_ablation_probe/runtime_model/runtime_model_bundle.json'
DECISION12061=ART/'stage12061_guarded_transition_training_decision/guarded_transition_training_decision.json'

def rel(p:Path)->str:
    return str(p.relative_to(ROOT))

def load(p:Path):
    return json.loads(p.read_text())

def read_loss_tail():
    rows=[]
    if LOSS.exists():
        with LOSS.open() as f:
            for line in f:
                if line.strip(): rows.append(json.loads(line))
    return rows

def main():
    OUT.mkdir(parents=True,exist_ok=True); SUM.mkdir(parents=True,exist_ok=True)
    req=load(REQ)
    losses=read_loss_tail()
    last=losses[-1] if losses else {}
    payload={
        'stage':12064,
        'stage_name':NAME,
        'created_at_utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),
        'decision':'reject_stage12063_no_runtime_saved_keep_stage11924_selected_transition_frontier',
        'selected_transition_frontier_after_decision':'stage11924_transition_listwise_head_only_probe',
        'failed_probe':'stage12063_transition_status_head_ablation_probe',
        'failure_class':'training_infrastructure_no_grad_under_status_head_only',
        'summary':[
            'Stage12063 passed manifest/loss-mask preflight and began training, but crashed before runtime save.',
            'The failure was RuntimeError: element 0 of tensors does not require grad and does not have a grad_fn.',
            'No Stage12063 runtime exists, so there is no model/audit result to promote.',
            'Stage11924 remains the selected transition frontier at 364/640; Stage12059 remains rejected at 360/640.'
        ],
        'observed_training':{
            'runtime_model_saved':RUNTIME.exists(),
            'loss_rows_written':len(losses),
            'last_completed_step':last.get('step'),
            'last_aux_card':last.get('bounded_choice_aux_card'),
            'last_loss':last.get('loss'),
            'last_row_ids':last.get('row_ids',[])[:20],
        },
        'diagnosis':{
            'request_passed':req.get('passed'),
            'request_train_rows':req.get('row_counts',{}).get('train_rows'),
            'aux_source':'encoder_option_retrieval_transition_status_head',
            'likely_issue':'The selected status-head-only path can produce a non-differentiable aggregate loss for some batches despite valid row task_type and earlier differentiable batches.',
            'not_a_model_regression':'No runtime was saved; protected/model gates were not auditable for Stage12063.'
        },
        'next_recommendation':{
            'recommended_stage':'stage12065_status_head_batch_differentiability_preflight',
            'action':'Add or run a dry preflight over the exact Stage12062 manifest/sampler/source that checks every planned train batch has a differentiable bounded-choice aux loss before spending GPU training.',
            'then':'If preflight finds bad batches, either filter/repair row geometry or use a composite scorer with semantic fallback while freezing/guarding Stage11924 product head.',
            'do_not_do':'Do not rerun Stage12063 unchanged; it will likely fail at the same no-grad batch.'
        },
        'source_artifacts':{
            'request':rel(REQ),
            'probe_dir':rel(PROBE),
            'stage12061_decision':rel(DECISION12061),
            'loss_by_step':rel(LOSS) if LOSS.exists() else None,
        },
        'outputs':{'summary':rel(SUMMARY),'summary_mirror':f'runs/summaries/{NAME}.json'}
    }
    SUMMARY.write_text(json.dumps(payload,indent=2,sort_keys=True)+'\n')
    (SUM/f'{NAME}.json').write_text(json.dumps(payload,indent=2,sort_keys=True)+'\n')
    print(json.dumps({'decision':payload['decision'],'loss_rows_written':len(losses),'runtime_model_saved':RUNTIME.exists(),'last_completed_step':last.get('step')},indent=2,sort_keys=True))
if __name__=='__main__': main()
