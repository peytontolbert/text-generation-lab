#!/usr/bin/env python3
"""Build guarded request for candidate-selection repair training."""
from __future__ import annotations

import collections
import datetime as dt
import json
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
STAGE = 12090
NAME = 'stage12090_candidate_selection_repair_training_request'
OUT = REPO / 'runs/local/artifacts' / NAME
SUMMARIES = REPO / 'runs/summaries'
SUMMARY = OUT / 'candidate_selection_repair_training_request.json'
MIRROR = SUMMARIES / f'{NAME}.json'
MANIFEST = OUT / 'candidate_selection_repair_training_manifest.jsonl'
COMMAND_JSON = OUT / 'candidate_selection_repair_training_command.json'
BASE_MANIFEST = REPO / 'runs/local/artifacts/stage11923_transition_listwise_head_only_probe_request/transition_listwise_head_only_manifest.jsonl'
REPAIR_ROWS = REPO / 'runs/local/artifacts/stage12088_candidate_selection_repair_packet/candidate_selection_repair_rows.jsonl'
LOCAL_AUDIT = REPO / 'runs/summaries/stage12089_candidate_selection_repair_local_audit.json'
INIT_RUNTIME = REPO / 'runs/local/artifacts/stage11924_transition_listwise_head_only_probe/runtime_model/runtime_model_bundle.json'
PRESERVE_RUNTIME = REPO / 'runs/local/artifacts/stage11507_preservation_strengthened_evidence_judgment_probe/runtime_model/runtime_model_bundle.json'
RUNTIME_DIR = REPO / 'runs/local/artifacts/stage12091_candidate_selection_repair_training_probe/runtime_model'
OUTPUT_DIR = REPO / 'runs/local/artifacts/stage12091_candidate_selection_repair_training_probe/bounded_decoder_probe'
TRAIN_SCRIPT = REPO / 'legacy_src/scripts/train_agentkernel_lite_encdec.py'
MODEL_CONFIG = REPO / 'configs/model/agentkernel_100m_seq2seq_recovered_target.json'
TOKENIZER_JSON = REPO / 'configs/tokenizer/agentkernel_bpe_1506/tokenizer.json'
TOKENIZER_CONFIG = REPO / 'configs/tokenizer/agentkernel_bpe_1506/tokenizer_config.json'
TOKENIZER_HASHLOCK = REPO / 'configs/tokenizer/agentkernel_bpe_1506_recovered_pointer.json'


def rel(p: Path) -> str:
    return str(p.relative_to(REPO))


def read_json(p: Path) -> Any:
    return json.loads(p.read_text())


def read_jsonl(p: Path) -> list[dict[str, Any]]:
    return [json.loads(l) for l in p.read_text().splitlines() if l.strip()]


def write_json(p: Path, x: Any) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(x, indent=2, sort_keys=True) + '\n')


def write_jsonl(p: Path, rows: list[dict[str, Any]]) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open('w') as f:
        for r in rows:
            f.write(json.dumps(r, sort_keys=True) + '\n')


def split_of(row: dict[str, Any]) -> str:
    return str(row.get('split') or row.get('package_split') or '')


def target_value(row: dict[str, Any]) -> str:
    return (row.get('target') or {}).get('semantic_value') or row.get('standalone_projection_source', {}).get('gold_value') or ''


def prep_repair(row: dict[str, Any], index: int) -> dict[str, Any]:
    out = dict(row)
    out['split'] = 'train'
    out['package_split'] = 'train'
    out['train_support_only'] = True
    out['strict_eval_eligible'] = False
    out['source_heldout_admissible'] = False
    out['stage12090_candidate_selection_repair_support'] = True
    out['row_id'] = f"{out['row_id']}::stage12090_repair_support::{index}"
    return out


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    SUMMARIES.mkdir(parents=True, exist_ok=True)
    base = read_jsonl(BASE_MANIFEST)
    repair = read_jsonl(REPAIR_ROWS)
    audit = read_json(LOCAL_AUDIT)

    old_train = [r for r in base if split_of(r) == 'train']
    eval_rows = [r for r in base if split_of(r) == 'eval']
    strict_rows = [r for r in base if split_of(r) == 'strict_eval']

    replay = []
    for row in old_train:
        out = dict(row)
        out['stage12090_replay_source'] = 'stage11923_transition_listwise_head_only_manifest'
        out['row_id'] = f"{out['row_id']}::stage12090_old640_replay"
        replay.append(out)

    repair_rows = [prep_repair(row, i + 1) for i, row in enumerate(repair)]
    manifest_rows = replay + repair_rows + eval_rows + strict_rows
    write_jsonl(MANIFEST, manifest_rows)

    counts = collections.Counter(split_of(r) for r in manifest_rows)
    train = replay + repair_rows
    task_counts = collections.Counter(r.get('task_type') for r in train)
    repair_subpackets = collections.Counter(r.get('stage12088_subpacket') for r in repair_rows)
    repair_targets = collections.Counter(target_value(r) for r in repair_rows)
    option_mirror_missing = sum(1 for r in train if r.get('opaque_options') and not r.get('standalone_projection_source', {}).get('opaque_options'))
    unsafe_loss = sum(1 for r in train if not any((r.get('loss_mask') or {}).values()))

    command = [
        'env',
        'CUDA_VISIBLE_DEVICES=2',
        'NVIDIA_VISIBLE_DEVICES=2',
        'AGENTKERNEL_EVAL_DEVICE=cuda:0',
        'AGENTKERNEL_TRAIN_DEVICE=cuda:0',
        'PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True',
        'TMPDIR=/data/tmp',
        'TEMP=/data/tmp',
        'TMP=/data/tmp',
        'conda', 'run', '-n', 'trellis', 'python', str(TRAIN_SCRIPT),
        '--repo-root', str(REPO),
        '--manifest', str(MANIFEST),
        '--mode', 'bounded_decoder_ce_probe',
        '--probe-scale', 'target_100m',
        '--implementation', 'transformer',
        '--model-config', str(MODEL_CONFIG),
        '--tokenizer-json', str(TOKENIZER_JSON),
        '--tokenizer-config', str(TOKENIZER_CONFIG),
        '--tokenizer-hashlock', str(TOKENIZER_HASHLOCK),
        '--execution-authorized-for-recovery-probe',
        '--max-train-rows', str(counts['train']),
        '--max-eval-rows', str(counts['eval']),
        '--max-strict-rows', str(counts['strict_eval']),
        '--max-steps', '384',
        '--batch-size', '8',
        '--learning-rate', '5e-5',
        '--max-encoder-tokens', '768',
        '--max-decoder-tokens', '16',
        '--decoder-ce-weight', '0.0',
        '--bounded-choice-aux-weight', '3.0',
        '--bounded-choice-root-group-aux-weight', '0.0',
        '--bounded-choice-aux-source', 'encoder_option_retrieval_semantic_candidate_head',
        '--bounded-choice-train-head-only',
        '--bounded-decoder-train-sampler', 'task_balanced',
        '--bounded-choice-contrast-weight', '0.25',
        '--bounded-choice-contrast-margin', '0.06',
        '--bounded-choice-same-role-listwise-weight', '0.5',
        '--bounded-choice-verifier-value-listwise-weight', '0.7',
        '--structured-aux-weight', '0.0',
        '--denoise-weight', '0.0',
        '--eos-loss-weight', '1.0',
        '--enable-generation-audit',
        '--max-generation-rows', '8',
        '--max-generation-tokens', '8',
        '--require-loss-mask-enforcement-audit',
        '--allow-runtime-model-save-for-harness',
        '--runtime-model-save-dir', str(RUNTIME_DIR),
        '--initialize-from-runtime-model', str(INIT_RUNTIME),
        '--preservation-reference-runtime-model', str(PRESERVE_RUNTIME),
        '--preservation-kl-weight', '4.0',
        '--no-final-checkpoint-export',
        '--output-dir', str(OUTPUT_DIR),
    ]
    write_json(COMMAND_JSON, command)

    gates = {
        'base_manifest_exists': BASE_MANIFEST.exists(),
        'repair_rows_exists': REPAIR_ROWS.exists(),
        'local_audit_passed': audit.get('decision') == 'local_audit_passed_training_request_allowed',
        'init_runtime_exists': INIT_RUNTIME.exists(),
        'preserve_runtime_exists': PRESERVE_RUNTIME.exists(),
        'splits_expected': counts == {'train': 800, 'eval': 22, 'strict_eval': 22},
        'repair_rows_160': len(repair_rows) == 160,
        'candidate_selection_repair_rows_85': sum(1 for r in repair_rows if r.get('task_type') == 'transition_candidate_selection') == 85,
        'next_action_preservation_rows_75': sum(1 for r in repair_rows if r.get('task_type') == 'transition_next_action') == 75,
        'option_mirror_missing_zero': option_mirror_missing == 0,
        'unsafe_loss_zero': unsafe_loss == 0,
        'uses_gpu2_mask': 'CUDA_VISIBLE_DEVICES=2' in command and 'NVIDIA_VISIBLE_DEVICES=2' in command,
        'head_only_enabled': '--bounded-choice-train-head-only' in command,
    }
    passed = all(gates.values())
    summary = {
        'stage': STAGE,
        'stage_name': NAME,
        'created_at_utc': dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace('+00:00', 'Z'),
        'decision': 'candidate_selection_repair_training_request_ready' if passed else 'candidate_selection_repair_training_request_blocked',
        'passed': passed,
        'execute_now': False,
        'hypothesis': 'Candidate-selection regression replay plus next-action preservation can move total transition score above 364/640 while keeping next_action >=59/160 and restoring candidate_selection >=89/160.',
        'row_counts': {
            'train_rows': counts['train'],
            'old_replay_rows': len(replay),
            'repair_rows': len(repair_rows),
            'eval_rows': counts['eval'],
            'strict_rows': counts['strict_eval'],
            'train_task_counts': dict(task_counts),
            'repair_subpacket_counts': dict(repair_subpackets),
            'repair_target_counts': dict(repair_targets),
            'option_mirror_missing': option_mirror_missing,
            'unsafe_loss': unsafe_loss,
        },
        'gates_before_execution': gates,
        'training_controls': {
            'gpu': 'cuda:2 only',
            'init_runtime': rel(INIT_RUNTIME),
            'preservation_reference_runtime': rel(PRESERVE_RUNTIME),
            'max_steps': 384,
            'learning_rate': '5e-5',
            'contrast_weight': 0.25,
            'head_only': True,
            'sampler': 'task_balanced',
        },
        'promotion_gate': {
            'old_transition_640': '>364/640',
            'transition_next_action': '>=59/160',
            'transition_candidate_selection': '>=89/160',
            'transition_continue_or_stop': '>=128/160',
            'transition_verifier_transition': '>=96/160',
            'protected_filtered_strict': '22/22',
            'protected_old_canary_strict': '23/23',
            'residual_bank': '>=7/10',
            'source_heldout_smoke': '>=6/12',
        },
        'outputs': {
            'summary': rel(SUMMARY),
            'summary_mirror': rel(MIRROR),
            'manifest': rel(MANIFEST),
            'command': rel(COMMAND_JSON),
            'runtime_dir': rel(RUNTIME_DIR),
            'output_dir': rel(OUTPUT_DIR),
        },
        'source_artifacts': {
            'base_manifest': rel(BASE_MANIFEST),
            'repair_rows': rel(REPAIR_ROWS),
            'stage12089_audit': rel(LOCAL_AUDIT),
        },
        'next_stage_if_executed': 'stage12091_candidate_selection_repair_training_probe',
        'next_stage_after_execution': 'stage12092_candidate_selection_repair_training_postrun_audit',
    }
    write_json(SUMMARY, summary)
    write_json(MIRROR, summary)
    print(json.dumps({'passed': passed, 'manifest_rows': len(manifest_rows), 'train_rows': counts['train'], 'summary': rel(SUMMARY)}, indent=2))


if __name__ == '__main__':
    main()
