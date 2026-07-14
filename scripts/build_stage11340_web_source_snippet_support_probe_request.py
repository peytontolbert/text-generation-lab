#!/usr/bin/env python3
from __future__ import annotations
import json, time
from pathlib import Path
from typing import Any
ROOT=Path(__file__).resolve().parents[1]
ART=ROOT/'runs/local/artifacts'
STAGE=11340; NAME='stage11340_web_source_snippet_support_probe_request'
OUT=ART/NAME; OUT.mkdir(parents=True,exist_ok=True)
SUMMARY=OUT/'web_source_snippet_support_probe_request.json'; CMD=OUT/'web_source_snippet_support_probe_command.json'; MAN=OUT/'web_source_snippet_support_probe_manifest.jsonl'
TRAIN=ART/'stage11338_web_source_snippet_evidence_materialization/web_source_snippet_evidence_rows.jsonl'
CANARY=ART/'stage11312_deleaked_fail_to_pass_transition_package'
VAL=CANARY/'deleaked_fail_to_pass_validation_rows.jsonl'; STRICT=CANARY/'deleaked_fail_to_pass_strict_rows.jsonl'
INIT=ART/'stage11200_role_focused_residual_probe/runtime_model/runtime_model_bundle.json'
RUN=ART/'stage11341_web_source_snippet_support_probe'; PROBE=RUN/'bounded_decoder_probe'; RUNTIME=RUN/'runtime_model'
def readl(p:Path)->list[dict[str,Any]]: return [json.loads(l) for l in p.read_text().splitlines() if l.strip()] if p.exists() else []
def writej(p,o): p.write_text(json.dumps(o,indent=2,sort_keys=True)+'\n')
def writel(p,rows): p.write_text(''.join(json.dumps(r,sort_keys=True)+'\n' for r in rows))
def rel(p): return str(p.relative_to(ROOT))
def root(r): return str(r.get('root_id') or r.get('source_root_id') or r.get('root_lineage_key') or r.get('row_id') or '')
train=readl(TRAIN); val=readl(VAL); strict=readl(STRICT)
protected={root(r) for r in val+strict}
over=sorted({root(r) for r in train}&protected)
if over: raise SystemExit(f'root overlap with canary: {over[:5]}')
rows=[]
for split,rs in [('train',train),('eval',val),('strict_eval',strict)]:
    for r in rs:
        x=dict(r); x['split']=split; rows.append(x)
writel(MAN,rows)
cmd=['env','CUDA_VISIBLE_DEVICES=2','PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True','TMPDIR=/data/tmp','TEMP=/data/tmp','TMP=/data/tmp','conda','run','-n','trellis','python',str(ROOT/'legacy_src/scripts/train_agentkernel_lite_encdec.py'),'--repo-root',str(ROOT),'--manifest',str(MAN),'--mode','bounded_decoder_ce_probe','--probe-scale','target_100m','--implementation','transformer','--model-config',str(ROOT/'configs/model/agentkernel_100m_seq2seq_recovered_target.json'),'--tokenizer-json',str(ROOT/'configs/tokenizer/agentkernel_bpe_1506/tokenizer.json'),'--tokenizer-config',str(ROOT/'configs/tokenizer/agentkernel_bpe_1506/tokenizer_config.json'),'--tokenizer-hashlock',str(ROOT/'configs/tokenizer/agentkernel_bpe_1506_recovered_pointer.json'),'--execution-authorized-for-recovery-probe','--max-train-rows',str(len(train)),'--max-eval-rows',str(len(val)),'--max-strict-rows',str(len(strict)),'--max-steps','64','--batch-size','3','--learning-rate','4e-6','--max-encoder-tokens','768','--max-decoder-tokens','16','--decoder-ce-weight','0.1','--bounded-choice-aux-weight','2.0','--bounded-choice-aux-source','encoder_option_retrieval_evidence_judgment_head','--bounded-decoder-train-sampler','residual_family_balanced','--structured-aux-weight','0.0','--denoise-weight','0.0','--eos-loss-weight','4.0','--enable-generation-audit','--max-generation-rows','8','--max-generation-tokens','16','--require-loss-mask-enforcement-audit','--allow-runtime-model-save-for-harness','--runtime-model-save-dir',str(RUNTIME),'--initialize-from-runtime-model',str(INIT),'--preservation-reference-runtime-model',str(INIT),'--bounded-choice-contrast-weight','1.0','--bounded-choice-contrast-margin','0.10','--preservation-kl-weight','0.75','--no-final-checkpoint-export','--output-dir',str(PROBE)]
summary={'stage':STAGE,'stage_name':NAME,'created_at_utc':time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),'passed':True,'decision':'web_source_snippet_support_probe_requested_diagnostic_only','metrics':{'train_rows':len(train),'eval_rows':len(val),'strict_rows':len(strict),'root_overlaps':over},'source_artifacts':{'train':rel(TRAIN),'canary_validation':rel(VAL),'canary_strict':rel(STRICT),'init_runtime':rel(INIT)},'outputs':{'summary':rel(SUMMARY),'command':rel(CMD),'manifest':rel(MAN),'probe_dir':rel(PROBE),'runtime_model':rel(RUNTIME)},'promotion_gate':{'diagnostic_only':True,'web_source_snippet_train_score_should_improve':'above 7/21 current-runtime baseline','canary_strict_must_remain':'22/22','canary_validation_must_remain':'>=20/23'},'command':cmd}
writej(CMD,{'command':cmd}); writej(SUMMARY,summary); print(json.dumps({'passed':True,'metrics':summary['metrics'],'cmd':rel(CMD)},indent=2))
