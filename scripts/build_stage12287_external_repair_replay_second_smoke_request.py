#!/usr/bin/env python3
from __future__ import annotations
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
STAGE='stage12287_external_repair_replay_second_smoke_request'
READY=ROOT/'runs/local/artifacts/stage12284_external_repair_commit_pair_preflight/replay_ready_targets.jsonl'
OUT=ROOT/f'runs/local/artifacts/{STAGE}'
SUMMARY=ROOT/f'runs/summaries/{STAGE}.json'
selected_ids=['stage12244_replay_001','stage12244_replay_011','stage12244_replay_012','stage12244_replay_007','stage12244_replay_008']
rows=[]
for line in open(READY):
    if line.strip():
        r=json.loads(line)
        if r['request_id'] in selected_ids: rows.append(r)
rows.sort(key=lambda r:selected_ids.index(r['request_id']))
summary={'stage':STAGE,'decision':'second_smoke_request_ready_metadata_ranked','selected_request_ids':[r['request_id'] for r in rows],'selected_count':len(rows),'selection_rationale':{'avoid_prior_failed':['stage12244_replay_003','stage12244_replay_005','stage12244_replay_013','stage12244_replay_018'],'prefer':'low changed_file_count, focused selected test file, Python/Web first, Rust held back after timeout'},'execution_policy':{'write_root':'/data/tmp/stage12287_external_repair_replay_second_smoke','network':'forbidden','gpu_visible':False,'timeout_seconds_per_phase':120,'training_allowed':False},'training_rows_emitted':0,'admitted_rows':0,'next_stage':'stage12288_external_repair_replay_second_smoke_executor'}
OUT.mkdir(parents=True,exist_ok=True)
with (OUT/'second_smoke_targets.jsonl').open('w',encoding='utf-8') as f:
    for r in rows: f.write(json.dumps(r,sort_keys=True)+'\n')
(OUT/'EXTERNAL_REPAIR_REPLAY_SECOND_SMOKE_REQUEST_STAGE12287.md').write_text('# Stage12287 Second Smoke Request\n\n'+json.dumps(summary,indent=2)+'\n',encoding='utf-8')
(OUT/'second_smoke_request_summary.json').write_text(json.dumps(summary,indent=2,sort_keys=True)+'\n',encoding='utf-8')
SUMMARY.parent.mkdir(parents=True,exist_ok=True); SUMMARY.write_text(json.dumps(summary,indent=2,sort_keys=True)+'\n',encoding='utf-8')
