#!/usr/bin/env python3
from __future__ import annotations
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
STAGE='stage12285_external_repair_replay_executor_request'
READY=ROOT/'runs/local/artifacts/stage12284_external_repair_commit_pair_preflight/replay_ready_targets.jsonl'
OUT=ROOT/f'runs/local/artifacts/{STAGE}'
SUMMARY=ROOT/f'runs/summaries/{STAGE}.json'

def iterj(p):
    with p.open('r',encoding='utf-8') as f:
        for l in f:
            l=l.strip()
            if l: yield json.loads(l)
ready=list(iterj(READY))
# Conservative default smoke: shortest-looking focused verifiers by repo/language.
preferred=['stage12244_replay_003','stage12244_replay_013','stage12244_replay_005','stage12244_replay_018']
selected=[r for r in ready if r['request_id'] in preferred]
request={'stage':STAGE,'decision':'executor_request_ready_smoke_subset_reviewed','source_preflight':'runs/summaries/stage12284_external_repair_commit_pair_preflight.json','ready_target_count':len(ready),'default_smoke_target_count':len(selected),'default_smoke_request_ids':[r['request_id'] for r in selected],'execution_policy':{'write_root':'/data/tmp/stage12285_external_repair_replay','network':'forbidden','gpu_visible':False,'timeout_seconds_per_phase':120,'phases':['before_fail_behavior','before_plus_patch_pass','after_pass'],'stop_after_first_env_tooling_failure_per_repo':True,'max_smoke_targets':5,'training_allowed':False},'phase_success_required_for_PE2':{'before_fail_behavior':'FAIL','before_plus_patch_pass':'PASS','after_pass':'PASS'},'hard_rejects':['repo_clone_or_checkout_failed','patch_apply_failed','before_did_not_fail','before_failure_env_or_tooling','before_plus_patch_did_not_pass','after_did_not_pass','post_failure_remains','raw_log_or_patch_body_emitted'],'outputs_expected':['phase_status_records.jsonl','replay_execution_summary.json','patch_effect_candidates_PE2_or_rejects.jsonl'],'admission_after_execution':'none; PE3/PE4 semantic audit required','training_rows_emitted':0,'admitted_rows':0,'next_stage':'stage12286_external_repair_replay_smoke_executor'}
OUT.mkdir(parents=True,exist_ok=True)
(OUT/'external_repair_replay_executor_request.json').write_text(json.dumps(request,indent=2,sort_keys=True)+'\n',encoding='utf-8')
with (OUT/'default_smoke_targets.jsonl').open('w',encoding='utf-8') as f:
    for r in selected: f.write(json.dumps(r,sort_keys=True)+'\n')
(OUT/'EXTERNAL_REPAIR_REPLAY_EXECUTOR_REQUEST_STAGE12285.md').write_text('# Stage12285 External Repair Replay Executor Request\n\n'+json.dumps(request,indent=2)+'\n',encoding='utf-8')
SUMMARY.parent.mkdir(parents=True,exist_ok=True); SUMMARY.write_text(json.dumps(request,indent=2,sort_keys=True)+'\n',encoding='utf-8')
