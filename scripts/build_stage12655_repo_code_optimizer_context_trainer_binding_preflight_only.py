#!/usr/bin/env python3
# Bind repo/code optimizer context to a trainer implementation without invoking training.
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any, Mapping

ROOT=Path(__file__).resolve().parents[1]
STAGE="stage12655_repo_code_optimizer_context_trainer_binding_preflight_only"
OUT=ROOT/"runs/local/artifacts"/STAGE
SUMMARY=ROOT/"runs/summaries"/f"{STAGE}.json"
S12654=ROOT/"runs/local/artifacts/stage12654_repo_code_retention_shortcut_baseline_plan_preflight_only"
S12654_SUMMARY=ROOT/"runs/summaries/stage12654_repo_code_retention_shortcut_baseline_plan_preflight_only.json"
TRAINER=ROOT/"legacy_src/scripts/train_agentkernel_lite_encdec.py"
MODEL_CONFIG=ROOT/"configs/model/agentkernel_100m_seq2seq_recovered_target.json"
MANIFEST=ROOT/"runs/local/artifacts/stage12651_repo_code_curriculum_ingestion_contract_preflight_only/private/repo_code_curriculum_ingest_manifest.jsonl"
EXPECTED_HASHES={
 "stage12654_summary":"4ab36d9c2410e6e2226beb227b6255f6113a66abc60c05def0f72f68f56247d8",
 "stage12654_contract":"a0c78da61f289af78ad827001fe8d12bd55a00b83fef98b0f3c21597e895391f",
 "stage12654_pointer":"9fdbfcae966234b58939e0bd9fd1a8020230aa4870be8cf14413472174be8867",
 "stage12654_private_packet":"1632f08a470d2db6f90baebc24b4597bf69c66c9023488fec221d41f7f05f427",
 "stage12654_script_bytes":"4d37735a4628f50d77e42d548bd09f03196ff98a61bf87b65608301885e5b02c",
 "stage12654_tests_bytes":"6233158bc5722b397b3ee0273ec21c76b6d2795285abb6b5ad0780f52843c067",
 "trainer_bytes":"06dc20186a4f4767bfd7c6ccc8209f374d738ec1f8696cabbc2a16472422971a",
 "model_config_bytes":"dda55307003800072d98070a4f744ebd0f8262c5680fa1b0f74c5724b32f5a77",
}
EXPECTED_STAGE12654_ARTIFACTS=["contract.json","digest_pointer.json","private/repo_code_retention_shortcut_baseline_plan_packet.json","summary.json"]
FALSE_FIELDS=("training_admission_allowed","training_allowed","training_run_allowed","training_admitted","strict_eval_admitted","sealed_eval_admitted","strict_eval_eligible","sealed_eval_eligible","implementation_ready","stage12595_allowed","replay_trustworthy","level_3_materialized","gpu_allocation_requested","cuda2_training_allowed","vm_runner_execution_allowed","runtime_authorized","model_execution_authorized_next","source_emission_authorized","body_emission_authorized","decoder_ce_training_authorized_next","transition_head_training_authorized_next","promotion_ready","optimizer_step_authorized")
FORBIDDEN=("/data/","/arxiv/",'"model_input":','"target_text":',"source_lineage","source_row_id","source_ref","repo_graph_and_symbol_binding","PLACEHOLDER","TODO","TBD","<fill")

class Stage12655OptimizerBindingError(RuntimeError): pass

def stable_hash(v: Any)->str:
 return hashlib.sha256(json.dumps(v,sort_keys=True,separators=(",",":"),ensure_ascii=True).encode("ascii")).hexdigest()
def sha256_bytes(data: bytes)->str: return hashlib.sha256(data).hexdigest()
def read_json(p: Path)->dict[str,Any]:
 v=json.loads(p.read_text(encoding="utf-8"))
 if not isinstance(v,dict): raise Stage12655OptimizerBindingError("json_object_required:"+p.name)
 return v
def write_json(p: Path,v: Any)->None:
 p.parent.mkdir(parents=True,exist_ok=True); data=json.dumps(v,indent=2,sort_keys=True,ensure_ascii=True).encode("ascii")+b"\n"
 with p.open("wb") as f: f.write(data); f.flush(); os.fsync(f.fileno())
def fsync_dir(p: Path)->None:
 fd=os.open(str(p),os.O_RDONLY)
 try: os.fsync(fd)
 finally: os.close(fd)
def false_fields()->dict[str,bool]: return {k:False for k in FALSE_FIELDS}
def check_false(r: Mapping[str,Any], label: str)->None:
 for f in FALSE_FIELDS:
  if r.get(f) is not False: raise Stage12655OptimizerBindingError(f"{label}_gate_drift:{f}")
def assert_sanitized(r: Mapping[str,Any], label: str)->None:
 e=json.dumps(r,sort_keys=True,ensure_ascii=True)
 for n in FORBIDDEN:
  if n in e: raise Stage12655OptimizerBindingError(f"{label}_leak_or_drift:{n}")

def load_inputs()->dict[str,Any]:
 emitted=sorted(p.relative_to(S12654).as_posix() for p in S12654.rglob("*") if p.is_file())
 if emitted!=EXPECTED_STAGE12654_ARTIFACTS: raise Stage12655OptimizerBindingError("stage12654_artifact_manifest_drift")
 summary=read_json(S12654/"summary.json")
 if summary!=read_json(S12654_SUMMARY): raise Stage12655OptimizerBindingError("stage12654_external_summary_mismatch")
 contract=read_json(S12654/"contract.json"); pointer=read_json(S12654/"digest_pointer.json"); private=read_json(S12654/"private/repo_code_retention_shortcut_baseline_plan_packet.json")
 for label,value in (("stage12654_summary",summary),("stage12654_contract",contract),("stage12654_pointer",pointer),("stage12654_private_packet",private)):
  if stable_hash(value)!=EXPECTED_HASHES[label]: raise Stage12655OptimizerBindingError("pin_drift:"+label)
 for label,data in (("stage12654_script_bytes",(ROOT/"scripts/build_stage12654_repo_code_retention_shortcut_baseline_plan_preflight_only.py").read_bytes()),("stage12654_tests_bytes",(ROOT/"tests/test_stage12654_repo_code_retention_shortcut_baseline_plan_preflight_only.py").read_bytes()),("trainer_bytes",TRAINER.read_bytes()),("model_config_bytes",MODEL_CONFIG.read_bytes())):
  if sha256_bytes(data)!=EXPECTED_HASHES[label]: raise Stage12655OptimizerBindingError("pin_drift:"+label)
 if "optimizer_context_not_bound_to_trainer_implementation" not in summary.get("remaining_authorization_blockers",[]): raise Stage12655OptimizerBindingError("target_blocker_missing")
 if summary.get("retention_eval_and_shortcut_baseline_plan_materialized") is not True: raise Stage12655OptimizerBindingError("baseline_plan_not_materialized")
 for label,r in (("summary",summary),("contract",contract),("pointer",pointer),("private",private)):
  check_false(r,"stage12654_"+label); assert_sanitized(r,"stage12654_"+label)
 return {"summary":summary}

def build_optimizer_binding()->dict[str,Any]:
 trainer_text=TRAINER.read_text(encoding="utf-8")
 required=["--manifest","--mode","--max-train-rows","--max-eval-rows","--max-strict-rows","--max-steps","--learning-rate","--batch-size","--require-loss-mask-enforcement-audit","--no-final-checkpoint-export","--cleanup-checkpoints-after-probe","--skip-final-model-save"]
 missing=[flag for flag in required if flag not in trainer_text]
 if missing: raise Stage12655OptimizerBindingError("trainer_required_flags_missing:"+','.join(missing))
 binding={
  "record_type":"stage12655_private_optimizer_context_trainer_binding_v1",
  "trainer_implementation":"legacy_src/scripts/train_agentkernel_lite_encdec.py",
  "trainer_sha256":EXPECTED_HASHES["trainer_bytes"],
  "model_config":"configs/model/agentkernel_100m_seq2seq_recovered_target.json",
  "model_config_sha256":EXPECTED_HASHES["model_config_bytes"],
  "manifest":"runs/local/artifacts/stage12651_repo_code_curriculum_ingestion_contract_preflight_only/private/repo_code_curriculum_ingest_manifest.jsonl",
  "mode":"repo_graph_probe",
  "optimizer_and_context":{"optimizer":"adamw","learning_rate":5e-5,"batch_size":2,"max_steps":0,"max_train_rows":153,"max_eval_rows":64,"max_strict_rows":0,"max_encoder_tokens":2048,"max_decoder_tokens":768,"loss_mask_enforcement_audit_required":True},
  "required_safety_flags":["--require-loss-mask-enforcement-audit","--no-final-checkpoint-export","--cleanup-checkpoints-after-probe","--skip-final-model-save 1"],
  "device_policy_if_later_authorized":{"CUDA_VISIBLE_DEVICES":"2","forbidden_gpu_ids":["0","1"]},
  "trainer_invocation_allowed":False,"model_forward_allowed":False,"training_allowed":False,"optimizer_step_authorized":False,
 }
 assert_sanitized(binding,"optimizer_binding")
 return binding

def build_packet(inputs: Mapping[str,Any])->tuple[dict[str,Any],dict[str,Any],dict[str,Any],dict[str,Any]]:
 binding=build_optimizer_binding()
 remaining=[b for b in inputs["summary"].get("remaining_authorization_blockers",[]) if b!="optimizer_context_not_bound_to_trainer_implementation"]
 true_fields={"repo_code_knowledge_stage_complete":True,"repo_code_curriculum_layer_complete":True,"retention_eval_and_shortcut_baseline_plan_materialized":True,"optimizer_context_bound_to_trainer_implementation":True,"separate_training_admission_required":True}
 audit={"optimizer_context_bound_to_trainer_implementation":True,"optimizer_binding_sha256":stable_hash(binding),"resolved_authorization_blocker":"optimizer_context_not_bound_to_trainer_implementation","remaining_authorization_blocker_count":len(remaining),"remaining_authorization_blockers":remaining,"trainer_invocation_allowed":False,"model_forward_allowed":False}
 private={"record_type":"stage12655_private_optimizer_context_trainer_binding_packet_v1",**false_fields(),**true_fields,"reviewed_input_hashes":EXPECTED_HASHES,"optimizer_binding":binding,"binding_audit":audit}
 contract={"record_type":"stage12655_public_optimizer_context_trainer_binding_contract_v1",**false_fields(),**true_fields,**audit,"private_packet_sha256":stable_hash(private),"next_required_action":"stage12656_repo_code_cuda2_runtime_contract_preflight_only"}
 summary={"record_type":"stage12655_public_optimizer_context_trainer_binding_summary_v1",**false_fields(),**true_fields,**audit,"stage":STAGE,"decision":"OPTIMIZER_CONTEXT_BOUND_TO_TRAINER_IMPLEMENTATION_NO_TRAINING","private_packet_sha256":stable_hash(private),"contract_sha256":stable_hash(contract),"next_required_action":"stage12656_repo_code_cuda2_runtime_contract_preflight_only"}
 pointer={"record_type":"stage12655_public_optimizer_context_trainer_binding_pointer_v1",**false_fields(),**true_fields,"contract_sha256":stable_hash(contract),"private_packet_sha256":stable_hash(private),"optimizer_binding_sha256":stable_hash(binding)}
 for label,r in (("summary",summary),("contract",contract),("pointer",pointer),("private",private)):
  check_false(r,label); assert_sanitized(r,label)
 return summary,contract,private,pointer

def build(out:Path=OUT, summary_path:Path=SUMMARY)->dict[str,Any]:
 summary,contract,private,pointer=build_packet(load_inputs())
 write_json(out/"contract.json",contract); write_json(out/"digest_pointer.json",pointer); write_json(out/"private/repo_code_optimizer_context_trainer_binding_packet.json",private); write_json(out/"summary.json",summary); write_json(summary_path,summary)
 fsync_dir(out/"private"); fsync_dir(out); fsync_dir(summary_path.parent); return summary
if __name__=="__main__": print(json.dumps(build(),sort_keys=True))
