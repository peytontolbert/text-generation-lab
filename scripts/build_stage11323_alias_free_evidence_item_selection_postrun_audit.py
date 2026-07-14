#!/usr/bin/env python3
from __future__ import annotations
import json, os, sys, time
from pathlib import Path
from typing import Any
import torch
ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path: sys.path.insert(0,str(ROOT))
from legacy_src.agentkernel_lite.modeling_transformer import AgentKernelLiteTransformerConfig, AgentKernelLiteTransformerSeq2Seq
from legacy_src.agentkernel_lite.training_data import AgentKernelBPETokenizer
from legacy_src.agentkernel_lite.training_loop import _load_runtime_model_bundle, _write_bounded_choice_eval_audit
ART=ROOT/'runs/local/artifacts'; STAGE=11323; NAME='stage11323_alias_free_evidence_item_selection_postrun_audit'; OUT=ART/NAME; OUT.mkdir(parents=True,exist_ok=True); SUMMARY=OUT/'alias_free_evidence_item_selection_postrun_audit.json'
RUNTIME=ART/'stage11322_alias_free_evidence_item_selection_probe/runtime_model/runtime_model_bundle.json'
REQUEST=ART/'stage11321_alias_free_evidence_item_selection_probe_request/alias_free_evidence_item_selection_probe_request.json'
PKG=ART/'stage11320_alias_free_evidence_item_selection_package/alias_free_evidence_item_selection_package.json'
SPLITS={
 'alias_validation':ART/'stage11320_alias_free_evidence_item_selection_package/alias_free_evidence_item_selection_validation_rows.jsonl',
 'alias_strict':ART/'stage11320_alias_free_evidence_item_selection_package/alias_free_evidence_item_selection_strict_rows.jsonl',
 'alias_diagnostic':ART/'stage11320_alias_free_evidence_item_selection_package/alias_free_residual_diagnostic_rows.jsonl',
 'canary_validation':ART/'stage11312_deleaked_fail_to_pass_transition_package/deleaked_fail_to_pass_validation_rows.jsonl',
 'canary_strict':ART/'stage11312_deleaked_fail_to_pass_transition_package/deleaked_fail_to_pass_strict_rows.jsonl',
 'canary_residual':ART/'stage11312_deleaked_fail_to_pass_transition_package/deleaked_fail_to_pass_residual_rows.jsonl',
}
SCORERS=['encoder_option_retrieval_evidence_judgment_head','encoder_option_retrieval_verifier_conditioned','encoder_option_retrieval','decoder_first_step']
torch.set_num_threads(max(1,int(os.environ.get('AGENTKERNEL_EVAL_THREADS','8')))); torch.set_num_interop_threads(2); DEVICE=torch.device(os.environ.get('AGENTKERNEL_EVAL_DEVICE','cuda' if torch.cuda.is_available() else 'cpu'))
def rel(p): return str(p.relative_to(ROOT))
def readj(p): return json.loads(p.read_text())
def readl(p): return [json.loads(l) for l in p.read_text().splitlines() if l.strip()] if p.exists() else []
def writej(p,o): p.write_text(json.dumps(o,indent=2,sort_keys=True)+'\n')
def load_runtime():
    b=readj(RUNTIME); md=b['metadata']; cfg=AgentKernelLiteTransformerConfig.from_recovered_target_json(readj(Path(str(md['model_config'])))); m=AgentKernelLiteTransformerSeq2Seq(cfg); init=_load_runtime_model_bundle(RUNTIME, model=m); m.to(DEVICE); m.eval(); tok=AgentKernelBPETokenizer(Path(str(md['tokenizer_json'])), Path(str(md['tokenizer_config']))); return m,tok,init
def metric(card):
    rows=card.get('row_cards') or []; scored=[r for r in rows if isinstance(r.get('constrained_choice_match'),bool)]; c=sum(1 for r in scored if r.get('constrained_choice_match')); return {'rows':len(rows),'scored_rows':len(scored),'correct':c,'exact_accuracy':c/len(scored) if scored else None}
def misses(card):
    out=[]
    for r in card.get('row_cards') or []:
        if r.get('constrained_choice_match') is False:
            out.append({'row_id':r.get('row_id'),'target_text':r.get('target_text'),'predicted':r.get('constrained_choice_top1_label'),'full_vocab_top1_text':r.get('full_vocab_top1_text'),'target_rank_full_vocab':r.get('target_rank_full_vocab')})
    return out[:50]
def main():
    model,tok,init=load_runtime(); scored={}
    for scorer in SCORERS:
        scored[scorer]={}
        for name,path in SPLITS.items():
            rows=readl(path)
            card=_write_bounded_choice_eval_audit(OUT,model=model,rows=rows,tokenizer=tok,max_encoder_tokens=768,max_decoder_tokens=8,split_name=f'{name}_{scorer}',bounded_choice_aux_source=scorer,eval_batch_size=8)
            scored[scorer][name]={'metric':metric(card),'misses':misses(card)}
    prod=scored['encoder_option_retrieval_evidence_judgment_head']
    gates={'alias_strict_at_least_14_of_20':prod['alias_strict']['metric']['correct']>=14,'alias_validation_at_least_15_of_22':prod['alias_validation']['metric']['correct']>=15,'alias_diagnostic_above_3_of_7':prod['alias_diagnostic']['metric']['correct']>3,'canary_strict_22_of_22':prod['canary_strict']['metric']['correct']==22,'canary_validation_at_least_20_of_23':prod['canary_validation']['metric']['correct']>=20,'canary_residual_above_5_of_10':prod['canary_residual']['metric']['correct']>5}
    summary={'stage':STAGE,'stage_name':NAME,'created_at_utc':time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),'passed':True,'decision':'alias_free_evidence_item_selection_postrun_audit_complete','runtime_initialization':init,'gates':gates,'product_metrics':{k:v['metric'] for k,v in prod.items()},'scored':scored,'source_artifacts':{'runtime':rel(RUNTIME),'request':rel(REQUEST),'package':rel(PKG),**{k:rel(v) for k,v in SPLITS.items()}},'outputs':{'summary_json':rel(SUMMARY)}}
    writej(SUMMARY,summary); print(json.dumps({'gates':gates,'product_metrics':summary['product_metrics']},indent=2,sort_keys=True))
if __name__=='__main__': main()
