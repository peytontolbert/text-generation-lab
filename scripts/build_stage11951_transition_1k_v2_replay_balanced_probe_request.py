#!/usr/bin/env python3
"""Emit a replay-balanced Transition-1K-v2 probe request."""
from __future__ import annotations
import json, shutil, time
from pathlib import Path
from typing import Any
ROOT=Path(__file__).resolve().parents[1]
ART=ROOT/'runs/local/artifacts'; SUMMARIES=ROOT/'runs/summaries'
STAGE=11951; NAME='stage11951_transition_1k_v2_replay_balanced_probe_request'
OUT=ART/NAME; SUMMARY=OUT/'transition_1k_v2_replay_balanced_probe_request.json'; COMMAND_JSON=OUT/'transition_1k_v2_replay_balanced_command.json'; MANIFEST=OUT/'transition_1k_v2_replay_balanced_manifest.jsonl'
V2_ROWS=ART/'stage11945_transition_1k_v2_multisource_package/transition_projection_rows_v2.jsonl'
OLD_ROWS=ART/'stage11897_transition_record_projection_rows/transition_projection_rows.jsonl'
INIT_RUNTIME=ART/'stage11947_transition_1k_v2_listwise_probe/runtime_model/runtime_model_bundle.json'
PRESERVATION_RUNTIME=ART/'stage11507_preservation_strengthened_evidence_judgment_probe/runtime_model/runtime_model_bundle.json'
RUN_DIR=ART/'stage11952_transition_1k_v2_replay_balanced_probe'; RUNTIME_DIR=RUN_DIR/'runtime_model'; OUTPUT_DIR=RUN_DIR/'bounded_decoder_probe'

def now(): return time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
def rel(p:Path):
    try: return str(p.relative_to(ROOT))
    except ValueError: return str(p)
def read_jsonl(p:Path): return [json.loads(l) for l in p.read_text().splitlines() if l.strip()]
def write_json(p:Path,x:Any): p.parent.mkdir(parents=True,exist_ok=True); p.write_text(json.dumps(x,indent=2,sort_keys=True)+'\n')
def write_jsonl(p:Path,rows:list[dict[str,Any]]): p.parent.mkdir(parents=True,exist_ok=True); p.write_text(''.join(json.dumps(r,sort_keys=True)+'\n' for r in rows))
def train_copy(row:dict[str,Any], tag:str, copy_idx:int=0)->dict[str,Any]:
    out=dict(row); out['row_id']=f"{row.get('row_id')}::{tag}_{copy_idx}"; out['split']='train'; out['package_split']='train'; out['train_support_only']=True; out['strict_eval_eligible']=False; out['stage11951_replay_kind']=tag; out['preservation_exempt']=True
    src=dict(out.get('standalone_projection_source') or {}); src.setdefault('opaque_options', out.get('opaque_options') or []); out['standalone_projection_source']=src
    label=out.get('bounded_choice_target_label') or out.get('target_label') or out.get('target_text')
    if not isinstance(out.get('target'),dict): out['target']={'decoder_text':out.get('decoder_text') or label,'bounded_choice_target_label':label,'semantic_value':out.get('semantic_target_value') or out.get('target_value')}
    lm=dict(out.get('loss_mask') or {}); lm.update({'bounded_choice_aux':True,'structured_aux':True,'transition_projection':True}); out['loss_mask']=lm
    return out

def main():
    v2=read_jsonl(V2_ROWS); old=read_jsonl(OLD_ROWS)
    v2_train=[train_copy(r,'v2_train') for r in v2 if str(r.get('split'))=='train']
    old_replay=[train_copy(r,'old640_replay') for r in old]
    old_next=[train_copy(r,'old640_next_action_extra',1) for r in old if str(r.get('task_type'))=='transition_next_action']
    train_rows=v2_train+old_replay+old_next
    eval_rows=[dict(r,split='eval',package_split='eval') for r in v2 if str(r.get('split'))=='validation']
    strict_rows=[dict(r,split='strict_eval',package_split='strict_eval') for r in v2 if str(r.get('split'))=='strict_eval']
    write_jsonl(MANIFEST, train_rows+eval_rows+strict_rows)
    command=['env','CUDA_VISIBLE_DEVICES=2','NVIDIA_VISIBLE_DEVICES=2','AGENTKERNEL_EVAL_DEVICE=cuda:0','PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True','TMPDIR=/data/tmp','TEMP=/data/tmp','TMP=/data/tmp','conda','run','-n','trellis','python',str(ROOT/'legacy_src/scripts/train_agentkernel_lite_encdec.py'),'--repo-root',str(ROOT),'--manifest',str(MANIFEST),'--mode','bounded_decoder_ce_probe','--probe-scale','target_100m','--implementation','transformer','--model-config',str(ROOT/'configs/model/agentkernel_100m_seq2seq_recovered_target.json'),'--tokenizer-json',str(ROOT/'configs/tokenizer/agentkernel_bpe_1506/tokenizer.json'),'--tokenizer-config',str(ROOT/'configs/tokenizer/agentkernel_bpe_1506/tokenizer_config.json'),'--tokenizer-hashlock',str(ROOT/'configs/tokenizer/agentkernel_bpe_1506_recovered_pointer.json'),'--execution-authorized-for-recovery-probe','--max-train-rows',str(len(train_rows)),'--max-eval-rows',str(len(eval_rows)),'--max-strict-rows',str(len(strict_rows)),'--max-steps','1280','--batch-size','8','--learning-rate','1.5e-4','--max-encoder-tokens','768','--max-decoder-tokens','16','--decoder-ce-weight','0.0','--bounded-choice-aux-weight','3.0','--bounded-choice-root-group-aux-weight','0.0','--bounded-choice-aux-source','encoder_option_retrieval_semantic_candidate_head','--bounded-choice-train-head-only','--bounded-decoder-train-sampler','task_balanced','--bounded-choice-contrast-weight','0.3','--bounded-choice-contrast-margin','0.08','--bounded-choice-same-role-listwise-weight','0.5','--bounded-choice-verifier-value-listwise-weight','0.7','--structured-aux-weight','0.0','--denoise-weight','0.0','--eos-loss-weight','1.0','--enable-generation-audit','--max-generation-rows','8','--max-generation-tokens','8','--require-loss-mask-enforcement-audit','--allow-runtime-model-save-for-harness','--runtime-model-save-dir',str(RUNTIME_DIR),'--initialize-from-runtime-model',str(INIT_RUNTIME),'--preservation-reference-runtime-model',str(PRESERVATION_RUNTIME),'--preservation-kl-weight','4.0','--no-final-checkpoint-export','--output-dir',str(OUTPUT_DIR)]
    gates={'uses_gpu2_mask':'CUDA_VISIBLE_DEVICES=2' in command and 'NVIDIA_VISIBLE_DEVICES=2' in command,'head_only_enabled':'--bounded-choice-train-head-only' in command,'semantic_head_enabled':'encoder_option_retrieval_semantic_candidate_head' in command,'contrast_enabled':'--bounded-choice-contrast-weight' in command and '0.3' in command,'same_role_listwise_enabled':'--bounded-choice-same-role-listwise-weight' in command and '0.5' in command,'verifier_value_listwise_enabled':'--bounded-choice-verifier-value-listwise-weight' in command and '0.7' in command,'v2_train_rows_1240':len(v2_train)==1240,'old_replay_rows_640':len(old_replay)==640,'old_next_action_extra_160':len(old_next)==160,'eval_rows_128':len(eval_rows)==128,'strict_rows_220':len(strict_rows)==220,'init_runtime_exists':INIT_RUNTIME.exists(),'preservation_runtime_exists':PRESERVATION_RUNTIME.exists()}
    artifact={'stage':STAGE,'stage_name':NAME,'created_at_utc':now(),'passed':all(gates.values()),'decision':'transition_1k_v2_replay_balanced_probe_request_ready' if all(gates.values()) else 'transition_1k_v2_replay_balanced_probe_request_blocked','command':command,'gates_before_execution':gates,'row_counts':{'train_rows':len(train_rows),'v2_train_rows':len(v2_train),'old_replay_rows':len(old_replay),'old_next_action_extra_rows':len(old_next),'eval_rows':len(eval_rows),'strict_rows':len(strict_rows)},'hypothesis':'Stage11947 learned Transition-1K-v2 but regressed old 640 transition_next_action; replaying old 640 plus extra next_action should preserve old-manifest performance while retaining v2 validation/strict gains.','intervention':'Initialize from Stage11947 and train only semantic candidate head on v2 train rows plus old 640 replay and extra old next_action replay.','promotion_gate':{'old_transition_manifest_correct':'>=364/640','v2_validation_correct':'>=66/128','v2_strict_correct':'>=123/220','filtered_strict':'22/22','old_canary_strict':'23/23','residual_bank':'>=7/10'},'source_artifacts':{'v2_rows':rel(V2_ROWS),'old_rows':rel(OLD_ROWS),'manifest':rel(MANIFEST),'initialize_from_runtime_model':rel(INIT_RUNTIME),'preservation_reference_runtime_model':rel(PRESERVATION_RUNTIME)},'outputs':{'summary':rel(SUMMARY),'command':rel(COMMAND_JSON),'output_dir':rel(OUTPUT_DIR),'runtime_dir':rel(RUNTIME_DIR)},'claim_boundary':['This is not a Gemma win unless the postrun beats the old and v2 gates and then beats Gemma on same-manifest comparison.','Old 640 replay rows are train support only, not new promotion evidence.']}
    write_json(COMMAND_JSON,{'command':command}); write_json(SUMMARY,artifact); SUMMARIES.mkdir(parents=True,exist_ok=True); shutil.copyfile(SUMMARY,SUMMARIES/f'{NAME}.json')
    print(json.dumps({'decision':artifact['decision'],'passed':artifact['passed'],'row_counts':artifact['row_counts']},indent=2,sort_keys=True))
if __name__=='__main__': main()
