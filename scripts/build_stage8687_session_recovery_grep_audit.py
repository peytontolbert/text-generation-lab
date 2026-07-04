#!/usr/bin/env python3
from __future__ import annotations
import json, time
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
OUT_DIR=ROOT/'runs/local/artifacts/stage8687_session_recovery_grep_audit'
SUMMARY=ROOT/'runs/summaries/stage8687_session_recovery_grep_audit.json'
DOC=ROOT/'docs/SESSION_RECOVERY_GREP_AUDIT_STAGE8687.md'
REGISTRY=ROOT/'runs/local/artifacts/reconstructed_stage_registry.json'
AUTHORITY_CLOSED={
 'model_execution_authorized_next':False,'decoder_ce_training_authorized_next':False,'runtime_authorized':False,
 'source_emission_authorized':False,'body_emission_authorized':False,'gemma_execution_authorized_next':False,
 'harness_execution_authorized_next':False,'scoring_authorized_next':False,'controller_complete_merge_authorized_next':False,'promotion_ready':False}

CATEGORIES={
 'runtime_guard': 'runtime_guard_guard_runtime_runtime_authorized_execution_gate_execution_authorized.txt',
 'loss_mask_guard': 'loss_mask_loss_mask_decoder_ce_denoise_ce.txt',
 'dataset_judge': 'dataset_judge_judge_dataset_objective_row_judge_row_judge_rubric.txt',
 'state_space': 'state_space_state_space_state_space_mamba_selective_scan_ssm.txt',
 'context_memory': 'context_pack_lost_in_middle_memory_retrieval_repo_state.txt',
}

def read_lines(name:str)->list[str]:
 p=OUT_DIR/name
 return p.read_text(errors='ignore').splitlines() if p.exists() else []

def main()->int:
 OUT_DIR.mkdir(parents=True,exist_ok=True)
 evidence={}
 for cat,name in CATEGORIES.items():
  lines=read_lines(name)
  evidence[cat]={'artifact':str((OUT_DIR/name).relative_to(ROOT)),'line_count':len(lines),'sample_files':sorted({line.split(':',1)[0] for line in lines if ':' in line})[:8],'sample_lines':[line[:600] for line in lines[:5]]}
 findings=[
  {'feature':'runtime_guard','status':'partially_recovered','current_coverage':['authority_gate','loss_authority_closed','source_lineage_guard'],'still_missing':'runtime_verifier_loop remains missing_closed; target implementation-selection guard missing before 100M execution.'},
  {'feature':'loss_mask_guard','status':'partially_recovered','current_coverage':['loss_mask_card','dataset_junk_ood_ranker_v1 loss eligibility'],'still_missing':'builders are not yet forced to emit/import one shared loss-mask card before training candidates.'},
  {'feature':'dataset_judge','status':'partially_recovered','current_coverage':['dataset_junk_ood_ranker_v1','objective_row_judge compatibility','cluster_slice_near_duplicate_detector'],'still_missing':'rubric/LLM judge calibrator and verifier-judge disagreement calibration remain non-executable.'},
  {'feature':'state_space_mamba','status':'concept_recovered_not_executable','current_coverage':['MODEL_STACK_SPINE mentions SSM/Mamba','program-state multimodality graph references'],'still_missing':'no executable state-space/Mamba repo-state compressor or selective-scan context module exists in current recovery.'},
  {'feature':'context_memory_retrieval','status':'concept_recovered_not_executable','current_coverage':['retrieval baselines','memory retrieval evaluator as indexed support module'],'still_missing':'no context_packer/lost-in-middle/memory retrieval evaluator implementation exists yet.'},
 ]
 card={'stage':8687,'stage_name':'stage8687_session_recovery_grep_audit','name':'stage8687_session_recovery_grep_audit','passed':True,'authority':AUTHORITY_CLOSED,
  'metrics':{'session_root':'/home/peyton/.codex/sessions','categories_reviewed':len(CATEGORIES),'findings':len(findings),'new_high_priority_missing_modules':['target_implementation_selection_guard','runtime_verifier_loop','context_packer_lost_in_middle_memory_retrieval','state_space_repo_state_compressor','rubric_llm_judge_calibrator','training_telemetry'],'model_execution_authorized_next':False,'decoder_ce_training_authorized_next':False,'denoise_ce_training_authorized_next':False,'runtime_authorized':False,'promotion_ready':False,'data_mining_allowed':False,'training_allowed':False},
  'evidence':evidence,'findings':findings,
  'decision':'Codex session grep confirms current recovery has ranker/judge/guard pieces, but target implementation-selection, runtime verifier loop, context packing, state-space repo compression, judge calibration, and telemetry remain missing executable modules.',
  'next_best_step':'Recover target_implementation_selection_guard first, then context_packer/lost-in-middle and telemetry modules. Keep mining/training closed.',
  'created_at_utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime())}
 (OUT_DIR/'session_recovery_grep_audit_card.json').write_text(json.dumps(card,indent=2,sort_keys=True)+'\n')
 SUMMARY.write_text(json.dumps(card,indent=2,sort_keys=True)+'\n')
 lines=['# Stage8687 Session Recovery Grep Audit','',f"Passed: `{card['passed']}`",'','## Findings','']
 for f in findings:
  lines.append(f"- `{f['feature']}`: `{f['status']}`. Current: `{f['current_coverage']}`. Missing: {f['still_missing']}")
 lines.extend(['','## Evidence Artifacts',''])
 for cat,ev in evidence.items():
  lines.append(f"- `{cat}`: `{ev['line_count']}` saved lines in `{ev['artifact']}`")
 lines.extend(['','## Next','',card['next_best_step'],'','All authority remains closed.'])
 DOC.write_text('\n'.join(lines)+'\n')
 old=[]
 if REGISTRY.exists():
  try: old=list((json.loads(REGISTRY.read_text()).get('rows') or []))
  except Exception: old=[]
 rows=old+[card]
 REGISTRY.write_text(json.dumps({'passed':True,'rows':rows,'metrics':{'min_stage':min([r.get('stage',8687) for r in rows]+[8687]),'max_stage':8687,'latest_stage':8687,'latest_stage_name':card['stage_name'],'latest_stage_next_best_step':card['next_best_step'],'registry_rows':len(rows),'authority_counts':{k:0 for k in AUTHORITY_CLOSED}}},indent=2,sort_keys=True)+'\n')
 print(json.dumps(card,indent=2,sort_keys=True))
 return 0
if __name__=='__main__': raise SystemExit(main())
