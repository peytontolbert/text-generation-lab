#!/usr/bin/env python3
"""Composite routed audit for Stage12068 repaired status head."""
from __future__ import annotations

import json, os, shutil, sys, time
from pathlib import Path
from typing import Any
import torch

ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path: sys.path.insert(0,str(ROOT))
from legacy_src.agentkernel_lite.modeling_transformer import AgentKernelLiteTransformerConfig, AgentKernelLiteTransformerSeq2Seq
from legacy_src.agentkernel_lite.training_data import AgentKernelBPETokenizer
from legacy_src.agentkernel_lite.training_loop import _load_runtime_model_bundle, _write_bounded_choice_eval_audit

ART=ROOT/'runs/local/artifacts'; SUM=ROOT/'runs/summaries'
NAME='stage12069_transition_status_head_repaired_options_composite_audit'
OUT=ART/NAME; SUMMARY=OUT/'transition_status_head_repaired_options_composite_audit.json'
TRANSITION_ROWS=ART/'stage11897_transition_record_projection_rows/transition_projection_rows.jsonl'
RUNTIME=ART/'stage12068_transition_status_head_ablation_repaired_options_probe/runtime_model/runtime_model_bundle.json'
BASE_AUDIT=ART/'stage12060_guarded_transition_training_postrun_audit/guarded_transition_training_postrun_audit.json'
PROTECTED_ROWSETS={
 'residual_bank':ART/'stage11442_targeted_residual_role_support_package/semantic_candidate_residual_bank.jsonl',
 'filtered_strict':ART/'stage11442_targeted_residual_role_support_package/agentkernel_lite_encdec_strict_eval.jsonl',
 'old_canary_strict':ART/'stage11429_selected_test_rust_support_package/agentkernel_lite_encdec_strict_eval.jsonl',
 'filtered_validation':ART/'stage11442_targeted_residual_role_support_package/agentkernel_lite_encdec_validation.jsonl',
 'old_canary_validation':ART/'stage11429_selected_test_rust_support_package/agentkernel_lite_encdec_validation.jsonl',
 'verifier_grounded_source_heldout_smoke':ART/'stage11740_verifier_grounded_source_heldout_successor_score/verifier_grounded_successor_rows.jsonl',
}
SEMANTIC='encoder_option_retrieval_semantic_candidate_head'
STATUS='encoder_option_retrieval_transition_status_head'
COMPACT='encoder_option_retrieval_evidence_judgment_head'

torch.set_num_threads(max(1,int(os.environ.get('AGENTKERNEL_EVAL_THREADS','8'))))
try: torch.set_num_interop_threads(max(1,min(4,int(os.environ.get('AGENTKERNEL_EVAL_THREADS','8')))))
except RuntimeError: pass
DEVICE=torch.device(os.environ.get('AGENTKERNEL_EVAL_DEVICE','cuda' if torch.cuda.is_available() else 'cpu'))

def rel(p:Path)->str:
    try: return str(p.relative_to(ROOT))
    except ValueError: return str(p)

def read_json(p:Path)->Any: return json.loads(p.read_text())
def read_jsonl(p:Path)->list[dict[str,Any]]: return [json.loads(l) for l in p.read_text().splitlines() if l.strip()]
def write_json(p:Path,payload:Any)->None:
    p.parent.mkdir(parents=True,exist_ok=True); p.write_text(json.dumps(payload,indent=2,sort_keys=True)+'\n')

def normalize_row(row:dict[str,Any])->dict[str,Any]:
    out=dict(row); source=dict(out.get('standalone_projection_source') or {})
    source.setdefault('opaque_options', out.get('opaque_options') or [])
    out['standalone_projection_source']=source
    if not isinstance(out.get('target'),dict):
        label=out.get('bounded_choice_target_label') or out.get('target_label') or out.get('target_text')
        out['target']={'decoder_text':out.get('decoder_text') or label,'bounded_choice_target_label':label}
    out.setdefault('loss_mask',{'decoder_ce':True,'bounded_choice_aux':True})
    return out

def load_runtime(path:Path):
    bundle=read_json(path); md=bundle['metadata']
    config=AgentKernelLiteTransformerConfig.from_recovered_target_json(read_json(Path(str(md['model_config']))))
    model=AgentKernelLiteTransformerSeq2Seq(config)
    init=_load_runtime_model_bundle(path, model=model)
    model.to(DEVICE); model.eval()
    tok=AgentKernelBPETokenizer(Path(str(md['tokenizer_json'])), Path(str(md['tokenizer_config'])))
    return model,tok,init

def metric_from_rows(rows:list[dict[str,Any]])->dict[str,Any]:
    correct=sum(1 for r in rows if r.get('constrained_choice_match') is True)
    total=len(rows)
    return {'rows':total,'correct':correct,'accuracy':correct/total if total else None,'coverage':1.0 if total else None,'miss_count':total-correct}

def metric(card:dict[str,Any])->dict[str,Any]:
    return {'rows':card.get('rows'),'correct':card.get('constrained_choice_correct'),'accuracy':card.get('constrained_choice_top1_accuracy'),'coverage':card.get('constrained_choice_coverage'),'miss_count':sum(1 for r in card.get('row_cards') or [] if r.get('constrained_choice_match') is not True)}

def task_for_row(row:dict[str,Any], by_id:dict[str,dict[str,Any]])->str:
    rid=str(row.get('row_id'))
    task=str((by_id.get(rid) or {}).get('task_type') or row.get('task_type') or '')
    if task: return task
    for suffix in ['next_action','candidate_selection','verifier_transition','continue_or_stop']:
        if rid.endswith('::'+suffix): return 'transition_'+suffix
    return 'unknown'

def group(rows:list[dict[str,Any]], by_id:dict[str,dict[str,Any]], key:str)->dict[str,Any]:
    buckets:dict[str,list[dict[str,Any]]]={}
    for r in rows:
        rid=str(r.get('row_id'))
        src=by_id.get(rid) or {}
        name=str(src.get(key) or (task_for_row(r,by_id) if key=='task_type' else 'unknown'))
        buckets.setdefault(name,[]).append(r)
    return {k:metric_from_rows(v) for k,v in sorted(buckets.items())}

def main():
    OUT.mkdir(parents=True,exist_ok=True); SUM.mkdir(parents=True,exist_ok=True)
    transition=[normalize_row(r) for r in read_jsonl(TRANSITION_ROWS)]
    by_id={str(r.get('row_id')):r for r in transition}
    protected={name:[normalize_row(r) for r in read_jsonl(path)] for name,path in PROTECTED_ROWSETS.items()}
    model,tok,init=load_runtime(RUNTIME)
    semantic_card=_write_bounded_choice_eval_audit(OUT/'stage12068_semantic_route', model=model, rows=transition, tokenizer=tok, max_encoder_tokens=768, max_decoder_tokens=16, split_name='transition_projection__semantic_candidate_head', bounded_choice_aux_source=SEMANTIC, eval_batch_size=8)
    status_card=_write_bounded_choice_eval_audit(OUT/'stage12068_status_route', model=model, rows=transition, tokenizer=tok, max_encoder_tokens=768, max_decoder_tokens=16, split_name='transition_projection__transition_status_head', bounded_choice_aux_source=STATUS, eval_batch_size=8)
    semantic_rows={r['row_id']:r for r in semantic_card.get('row_cards') or []}
    status_rows={r['row_id']:r for r in status_card.get('row_cards') or []}
    composite=[]
    for src in transition:
        rid=str(src.get('row_id'))
        task=str(src.get('task_type') or '')
        chosen=(status_rows if task=='transition_verifier_transition' else semantic_rows).get(rid)
        if chosen is None:
            chosen=semantic_rows.get(rid) or status_rows.get(rid)
        if chosen is not None:
            row=dict(chosen); row['composite_route']=STATUS if task=='transition_verifier_transition' else SEMANTIC; row['task_type_from_source']=task
            composite.append(row)
    protected_metrics={}
    for name,rows in protected.items():
        card=_write_bounded_choice_eval_audit(OUT/'stage12068_compact_route', model=model, rows=rows, tokenizer=tok, max_encoder_tokens=768, max_decoder_tokens=16, split_name=f'protected__{name}__evidence_judgment_head', bounded_choice_aux_source=COMPACT, eval_batch_size=8)
        protected_metrics[f'protected::{name}']=metric(card)
    base=read_json(BASE_AUDIT)['results']['stage11924_transition_listwise_head_only']
    stage12059=read_json(BASE_AUDIT)['results']['stage12059_guarded_transition_training']
    results={'transition_projection_composite':metric_from_rows(composite),'transition_by_task':group(composite,by_id,'task_type'),'transition_by_language':group(composite,by_id,'language_family'), **protected_metrics}
    base_semantic_rows={r['row_id']:r for r in _write_bounded_choice_eval_audit(OUT/'stage11924_baseline_semantic_route', model=model, rows=transition, tokenizer=tok, max_encoder_tokens=768, max_decoder_tokens=16, split_name='stage11924_baseline_transition_projection__semantic_candidate_head', bounded_choice_aux_source=SEMANTIC, eval_batch_size=8).get('row_cards') or []}
    base_verifier_rows=[r for rid,r in base_semantic_rows.items() if str((by_id.get(str(rid)) or {}).get('task_type'))=='transition_verifier_transition']
    composite_verifier_rows=[r for r in composite if r.get('task_type_from_source')=='transition_verifier_transition']
    gates={
        'transition_projection_retains_stage11924_baseline':results['transition_projection_composite']['correct']>=base['transition_projection_routed']['correct'],
        'transition_projection_beats_gemma_386':results['transition_projection_composite']['correct']>386,
        'transition_projection_beats_stage12059':results['transition_projection_composite']['correct']>stage12059['transition_projection_routed']['correct'],
        'verifier_transition_subset_improves_stage11924':metric_from_rows(composite_verifier_rows)['correct'] >= metric_from_rows(base_verifier_rows)['correct'],
        'filtered_strict_preserved':results['protected::filtered_strict']['correct']==22,
        'old_canary_strict_preserved':results['protected::old_canary_strict']['correct']==23,
        'filtered_validation_preserved':results['protected::filtered_validation']['correct']>=20,
        'old_canary_validation_preserved':results['protected::old_canary_validation']['correct']>=21,
        'residual_preserved':results['protected::residual_bank']['correct']>=7,
        'smoke_preserved':results['protected::verifier_grounded_source_heldout_smoke']['correct']>=6,
    }
    protected_ok=all(gates[k] for k in ['filtered_strict_preserved','old_canary_strict_preserved','filtered_validation_preserved','old_canary_validation_preserved','residual_preserved','smoke_preserved'])
    if protected_ok and gates['transition_projection_beats_gemma_386']:
        decision='stage12068_composite_promotable_gemma_win_candidate'
    elif protected_ok and gates['transition_projection_retains_stage11924_baseline']:
        decision='stage12068_composite_retention_candidate_no_gemma_win'
    else:
        decision='stage12068_composite_rejected_keep_stage11924'
    summary={'stage':12069,'stage_name':NAME,'created_at_utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),'decision':decision,'device':str(DEVICE),'route_policy':{'transition_verifier_transition':STATUS,'other_transition_rows':SEMANTIC,'compact_protected_rows':COMPACT},'gates':gates,'results':{'stage11924_baseline':base,'stage12059_rejected':stage12059,'stage12068_composite':results},'runtime_initialization':init,'source_artifacts':{'runtime':rel(RUNTIME),'transition_rows':rel(TRANSITION_ROWS),'base_audit':rel(BASE_AUDIT),'protected_rowsets':{k:rel(v) for k,v in PROTECTED_ROWSETS.items()}},'outputs':{'summary':rel(SUMMARY),'summary_mirror':f'runs/summaries/{NAME}.json','audit_dir':rel(OUT)}}
    write_json(SUMMARY,summary); shutil.copyfile(SUMMARY,SUM/f'{NAME}.json')
    print(json.dumps({'decision':decision,'composite':results['transition_projection_composite'],'gates':gates},indent=2,sort_keys=True))
if __name__=='__main__': main()
