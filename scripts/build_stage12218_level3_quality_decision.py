#!/usr/bin/env python3
"""Decision artifact after Stage12213 QC, Stage12216 normalization, and Stage12217 queue."""
from __future__ import annotations
import json
from pathlib import Path
from typing import Any

ROOT=Path(__file__).resolve().parents[1]
STAGE='stage12218_level3_quality_decision'
OUT=ROOT/'runs/local/artifacts'/STAGE
SUMMARY=ROOT/'runs/summaries'/f'{STAGE}.json'

def load(path: str) -> Any:
    return json.loads((ROOT/path).read_text())

def write(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, sort_keys=True)+'\n')

qc=load('runs/summaries/stage12213_level3_dataset_quality_control.json')
norm=load('runs/summaries/stage12216_normalized_verifier_observation_dataset.json')
queue=load('runs/summaries/stage12217_patch_trace_verifier_rehydration_queue.json')
roll=load('runs/summaries/stage12206_level3_passfail_training_rollup.json')

decision={
    'stage': STAGE,
    'decision': 'normalize_verifier_observation_support_and_prepare_patch_rehydration_next',
    'training_allowed': False,
    'inputs': {
        'quality_control': 'runs/summaries/stage12213_level3_dataset_quality_control.json',
        'normalized_verifier_observation': 'runs/summaries/stage12216_normalized_verifier_observation_dataset.json',
        'patch_rehydration_queue': 'runs/summaries/stage12217_patch_trace_verifier_rehydration_queue.json',
        'passfail_rollup': 'runs/summaries/stage12206_level3_passfail_training_rollup.json',
    },
    'current_status': {
        'stage12206_repo_capped_passfail_rows': roll.get('repo_capped_passfail_count'),
        'stage12216_normalized_rows': norm.get('row_count'),
        'stage12216_blocked_rows': norm.get('blocked_row_count'),
        'stage12216_patch_trace_floor_rows': 0,
        'stage12217_rehydration_queue_count': queue.get('queue_count'),
        'stage12217_top10_count': queue.get('top10_count'),
    },
    'normalized_dataset_audit': norm.get('audit'),
    'claim_boundary': [
        'Stage12216 is normalized verifier-observation train-support only.',
        'Stage12216 must not be counted as patch-trace or full unbounded maintainer training supply.',
        'Stage12217 is a verifier rehydration queue only; Stage12201 remains level_2 until same-root commands execute and pass admission.',
    ],
    'next_stage_sequence': [
        'stage12219_patch_trace_rehydration_smoke_request: execute 3-5 CPU-only commands from Stage12217 top queue, no mutation, no network, short timeout.',
        'stage12220_patch_trace_rehydration_admission: admit only rows with same-root command output, verifier_result, state_before/state_after, stop decision, and patch diff/apply evidence.',
        'stage12221_level3_patch_trace_gate_audit: require >=8 patch-trace rows before any closed-loop trajectory training request.',
    ],
    'hard_guards': qc.get('hard_rejects'),
    'minimum_gate': qc.get('minimum_next_gate'),
    'artifacts': {
        'normalized_records': norm.get('artifact_paths',{}).get('records'),
        'blocked_normalization_rows': norm.get('artifact_paths',{}).get('blocked'),
        'patch_rehydration_top10': queue.get('artifact_paths',{}).get('top10'),
        'patch_rehydration_queue': queue.get('artifact_paths',{}).get('queue'),
    },
}
OUT.mkdir(parents=True, exist_ok=True)
write(OUT/'summary.json', decision)
write(SUMMARY, decision)
print(json.dumps(decision, indent=2, sort_keys=True))
