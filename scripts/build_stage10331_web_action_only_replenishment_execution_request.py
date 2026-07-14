#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = 10331
NAME = 'stage10331_web_action_only_replenishment_execution_request'
OUT_DIR = ROOT / 'runs/local/artifacts' / NAME
TRAIN_ROWS_JSONL = OUT_DIR / 'web_action_only_replenishment_train_rows.jsonl'
MANIFEST_JSONL = OUT_DIR / 'web_action_only_replenishment_manifest.jsonl'
REQUEST_JSON = OUT_DIR / 'web_action_only_replenishment_execution_request.json'
COMMAND_JSON = OUT_DIR / 'web_action_only_replenishment_command.json'
SUMMARY = ROOT / 'runs/summaries' / f'{NAME}.json'

BASE_MANIFEST = ROOT / 'runs/local/artifacts/stage10307_source_backed_action_support_plus_execution_request/source_backed_action_support_plus_manifest.jsonl'
INIT_RUNTIME = ROOT / 'runs/local/artifacts/stage10308_source_backed_action_support_plus_probe/runtime_model/runtime_model_bundle.json'
TRAINER = ROOT / 'legacy_src/scripts/train_agentkernel_lite_encdec.py'
MODEL_CONFIG = ROOT / 'configs/model/agentkernel_100m_seq2seq_recovered_target.json'
TOKENIZER_JSON = ROOT / 'configs/tokenizer/agentkernel_bpe_1506/tokenizer.json'
TOKENIZER_CONFIG = ROOT / 'configs/tokenizer/agentkernel_bpe_1506/tokenizer_config.json'
TOKENIZER_HASHLOCK = ROOT / 'configs/tokenizer/agentkernel_bpe_1506_recovered_pointer.json'
TMPDIR = Path('/data/tmp')
REPO_ROOT = Path('/data/bddy/bddy_website')

RUN_ID = 'stage10332_web_action_only_replenishment_probe'
OUTPUT_DIR = 'runs/local/artifacts/stage10332_web_action_only_replenishment_probe/bounded_decoder_probe'
RUNTIME_MODEL_DIR = 'runs/local/artifacts/stage10332_web_action_only_replenishment_probe/runtime_model'
MAX_STEPS = 64
LEARNING_RATE = '8e-6'
BATCH_SIZE = 2
PERMUTATION_COUNT = 3

SOURCE_ROOTS = [
    'localsess_bddy_website_sessseed_codex_sessions_rollout_2025_11_30t16_19_06_019ad58f_8ea0_7322_94d6_9c1b_index_html_9d82612639_aug_1500000_8b46e7f662',
    'localsess_bddy_website_sessseed_codex_sessions_rollout_2025_12_02t03_53_55_019add32_0c01_7ad3_8024_1d55_index_html_d97e16ac45_aug_1500000_8b46e7f662',
    'localsess_bddy_website_sessseed_codex_sessions_rollout_2025_12_02t14_11_07_019adf67_1880_7170_8d2e_9578_index_html_24e465dcc6_aug_1500000_8b46e7f662',
]
CANDIDATE_PATHS = ['index.html', 'package.json', 'vite.config.js']
VISIBLE_EVIDENCE_KEYS = ['candidate_change_surface', 'verifier_and_test_constraint', 'nearby_definition_or_usage_context']
TASK_ROWS = [
    {'perspective': 'symptom_localization', 'answer_kind': 'candidate_path', 'gold_value': 'index.html', 'task': 'Choose the most likely entrypoint or edit target from the visible web maintenance evidence.'},
    {'perspective': 'patch_impact', 'answer_kind': 'candidate_path', 'gold_value': 'index.html', 'task': 'Compare candidate edits by likely behavior change and choose the one most directly tied to the visible page-entry surface.'},
    {'perspective': 'minimal_fix_selection', 'answer_kind': 'candidate_path', 'gold_value': 'index.html', 'task': 'Choose the smallest maintainable intervention supported by the visible build and page-entry evidence.'},
]


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows=[]
    if not path.exists():
        return rows
    with path.open(encoding='utf-8') as h:
        for line in h:
            line=line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + '\n', encoding='utf-8')


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('w', encoding='utf-8') as h:
        for row in rows:
            h.write(json.dumps(row, sort_keys=True) + '\n')


def display(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def now_utc() -> str:
    return time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())


def compact(text: str, limit: int = 1000) -> str:
    clean=str(text).strip()
    return clean if len(clean)<=limit else clean[:limit-3].rstrip()+'...'


def excerpt(path: Path, anchor: str, radius: int = 20) -> str:
    lines=path.read_text(encoding='utf-8', errors='ignore').splitlines()
    idx=0
    for i,line in enumerate(lines):
        if anchor in line:
            idx=i
            break
    start=max(0, idx-radius)
    end=min(len(lines), idx+radius)
    return compact('\n'.join(lines[start:end]))


def deterministic_rotate(values: list[str], shift: int) -> list[str]:
    return values[shift:]+values[:shift]


def evidence() -> dict[str, list[dict[str, Any]]]:
    return {
        'candidate_change_surface': [{'path':'index.html','source_type':'local_repo','retrieval_reason':'fresh_bddy_index_seed_change','distance_from_seed':0,'text':excerpt(REPO_ROOT/'index.html','<script',22)}],
        'verifier_and_test_constraint': [
            {'path':'package.json','source_type':'local_repo','retrieval_reason':'build_entry_constraint','distance_from_seed':1,'text':excerpt(REPO_ROOT/'package.json','"build"',16)},
            {'path':'vite.config.js','source_type':'local_repo','retrieval_reason':'vite_build_constraint','distance_from_seed':1,'text':excerpt(REPO_ROOT/'vite.config.js','defineConfig',18)},
        ],
        'nearby_definition_or_usage_context': [
            {'path':'src/main.js','source_type':'local_repo','retrieval_reason':'implementation_neighbor','distance_from_seed':1,'text':excerpt(REPO_ROOT/'src/main.js','class App',22)},
            {'path':'package.json','source_type':'local_repo','retrieval_reason':'build_neighbor','distance_from_seed':1,'text':excerpt(REPO_ROOT/'package.json','"dev"',16)},
        ],
    }


def compile_prompt(root_id: str, ev: dict[str, list[dict[str, Any]]], task: dict[str, str], options: list[tuple[str, str]]) -> str:
    parts=['Language: web_js_ts_html', f'Perspective: {task["perspective"]}', f'Task: {task["task"]}', f'SourceRoot: {root_id}', 'Evidence:']
    for key in VISIBLE_EVIDENCE_KEYS:
        for item in ev.get(key, [])[:2]:
            parts.append(f"{key} [{item['path']}]: {' '.join(str(item['text']).split())}")
    parts.append('Options:')
    parts.extend([f'{label}. {value}' for label,value in options])
    parts.append('Answer:')
    return '\n'.join(parts)+'\n'


def compile_train_rows(ev: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    rows=[]
    for root_id in SOURCE_ROOTS:
        bundle_id=f'stage10331::{root_id}::web_js_ts_html'
        for task in TASK_ROWS:
            labels=list('ABC')
            for shift in range(PERMUTATION_COUNT):
                ordered_values=deterministic_rotate(CANDIDATE_PATHS, shift)
                options=list(zip(labels, ordered_values))
                label_by_value={v:l for l,v in options}
                prompt=compile_prompt(root_id, ev, task, options)
                rows.append({
                    'row_id': f"{bundle_id}::{task['perspective']}::compact_bounded::perm_{shift:02d}",
                    'semantic_key': f"web_action_only_replenishment::{root_id}::{task['perspective']}::perm_{shift:02d}",
                    'bundle_id': bundle_id,
                    'source_bundle_id': bundle_id,
                    'source_row_id': f"{bundle_id}::{task['perspective']}::compact_bounded",
                    'source_stage': STAGE,
                    'source_skill_area': 'maintainer_bundle_compact_bounded_choice',
                    'language_family': 'web_js_ts_html',
                    'task_type': task['perspective'],
                    'surface': 'maintainer_bundle_compact_bounded_choice',
                    'route': 'KEEP_BOUNDED_DECODER',
                    'objective_family': 'bounded_decoder_ce',
                    'query_text': f"compact_bounded::web_js_ts_html::{task['perspective']}::candidate_path::perm_{shift:02d}",
                    'prompt_text': prompt,
                    'input_text': prompt,
                    'target_text': label_by_value['index.html'],
                    'decoder_text': label_by_value['index.html'],
                    'target_token_len': len(label_by_value['index.html'].encode('utf-8')),
                    'split': 'train',
                    'loss_mask': {'decoder_ce': True},
                    'disable_losses': [],
                    'expected_enabled_loss': 'decoder_ce',
                    'standalone_projection_source': {
                        'gold_value': 'index.html',
                        'opaque_options': [{'label':label,'value':value} for label,value in options],
                        'original_answer_kind': 'candidate_path',
                        'projection_mode': 'compact_bounded_choice_auxiliary',
                        'projection_stage': STAGE,
                        'claim_boundary': {'train_support_only': True, 'same_surface_eval_admissible': False, 'fresh_web_root': True, 'action_only_support': True},
                    },
                    'authority': {'body_emission_authorized': False,'controller_complete_merge_authorized_next': False,'decoder_ce_training_authorized_next': False,'denoise_ce_training_authorized_next': False,'gemma_execution_authorized_next': False,'harness_execution_authorized_next': False,'model_execution_authorized_next': False,'promotion_ready': False,'runtime_authorized': False,'scoring_authorized_next': False,'source_emission_authorized': False},
                    'anti_cheat': {'compact_prompt_contract': True,'deterministic_option_shuffle': True,'opaque_labels': True,'reviewed_bundle_source': True,'train_support_only': True,'not_for_primary_maintainer_claim': True,'fresh_source_backed_root': True,'index_vs_vite_support': True,'action_only_support': True},
                })
    return rows


def main() -> None:
    base_rows=load_jsonl(BASE_MANIFEST)
    base_train=[r for r in base_rows if r.get('split')=='train']
    base_strict=[r for r in base_rows if r.get('split')=='strict_eval']
    train_rows=compile_train_rows(evidence())
    combined=train_rows+base_train+base_strict
    write_jsonl(TRAIN_ROWS_JSONL, train_rows)
    write_jsonl(MANIFEST_JSONL, combined)
    split_counts={}; language_counts={}
    for row in combined:
        split_counts[row['split']]=split_counts.get(row['split'],0)+1
        language_counts[row['language_family']]=language_counts.get(row['language_family'],0)+1
    command=['env',f'TMPDIR={TMPDIR}',f'TEMP={TMPDIR}',f'TMP={TMPDIR}','conda','run','-n','trellis','python',str(TRAINER),'--repo-root',str(ROOT),'--manifest',str(MANIFEST_JSONL),'--mode','bounded_decoder_ce_probe','--probe-scale','target_100m','--implementation','transformer','--model-config',str(MODEL_CONFIG),'--tokenizer-json',str(TOKENIZER_JSON),'--tokenizer-config',str(TOKENIZER_CONFIG),'--tokenizer-hashlock',str(TOKENIZER_HASHLOCK),'--execution-authorized-for-recovery-probe','--max-train-rows',str(split_counts.get('train',0)),'--max-eval-rows','0','--max-strict-rows',str(split_counts.get('strict_eval',0)),'--max-steps',str(MAX_STEPS),'--batch-size',str(BATCH_SIZE),'--learning-rate',LEARNING_RATE,'--max-encoder-tokens','768','--max-decoder-tokens','8','--decoder-ce-weight','0.2','--bounded-choice-aux-weight','1.0','--bounded-choice-aux-source','encoder_option_retrieval','--structured-aux-weight','0.0','--denoise-weight','0.0','--eos-loss-weight','4.0','--enable-generation-audit','--max-generation-rows','16','--max-generation-tokens','8','--require-loss-mask-enforcement-audit','--allow-runtime-model-save-for-harness','--runtime-model-save-dir',str(ROOT / RUNTIME_MODEL_DIR),'--initialize-from-runtime-model',str(INIT_RUNTIME),'--no-final-checkpoint-export','--skip-final-model-save','1','--output-dir',str(ROOT / OUTPUT_DIR),'--run-id',RUN_ID]
    request={'stage':STAGE,'stage_name':NAME,'created_at_utc':now_utc(),'passed':True,'decision':'fresh_web_action_only_replenishment_ready','manifest':display(MANIFEST_JSONL),'source_manifests':{'base':display(BASE_MANIFEST),'support_train_rows':display(TRAIN_ROWS_JSONL)},'split_counts':split_counts,'language_counts':language_counts,'rows':len(combined),'max_steps':MAX_STEPS,'learning_rate':LEARNING_RATE,'initialize_from_runtime_model':display(INIT_RUNTIME),'required_honesty_gates':['strict eval rows remain identical to stage10307/stage10308','fresh web rows are train-support-only and excluded from headline same-surface Gemma claims','web support rows use concrete repo snippets from /data/bddy/bddy_website','no evidence_citation rows are added to avoid cross-language citation bias drift'],'next_best_step':'run one frontloaded warm-start probe and check whether web action gains survive without the c_cpp evidence-citation regression','command':command,'output_dir':OUTPUT_DIR,'run_id':RUN_ID}
    write_json(REQUEST_JSON, request)
    write_json(COMMAND_JSON, {'command':command,'cwd':str(ROOT),'env':'trellis','tmpdir':str(TMPDIR)})
    write_json(SUMMARY, {'stage':STAGE,'stage_name':NAME,'passed':True,'artifact':display(REQUEST_JSON),'next_best_step':request['next_best_step']})
    print(json.dumps({'stage':STAGE,'passed':True,'artifact':display(REQUEST_JSON),'train_rows':len(train_rows)}, indent=2))

if __name__=='__main__':
    main()
