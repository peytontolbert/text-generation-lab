#!/usr/bin/env python3
"""Build guarded request for candidate-selection-only transition head training."""
from __future__ import annotations

import collections
import datetime as dt
import json
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
STAGE = 12095
NAME = 'stage12095_candidate_head_only_candidate_selection_request'
OUT = REPO / 'runs/local/artifacts' / NAME
SUMMARIES = REPO / 'runs/summaries'
SUMMARY = OUT / 'candidate_head_only_candidate_selection_request.json'
MIRROR = SUMMARIES / f'{NAME}.json'
MANIFEST = OUT / 'candidate_head_only_candidate_selection_manifest.jsonl'
COMMAND_JSON = OUT / 'candidate_head_only_candidate_selection_command.json'
BASE_MANIFEST = REPO / 'runs/local/artifacts/stage11923_transition_listwise_head_only_probe_request/transition_listwise_head_only_manifest.jsonl'
REPAIR_ROWS = REPO / 'runs/local/artifacts/stage12088_candidate_selection_repair_packet/candidate_selection_repair_rows.jsonl'
DESIGN = REPO / 'runs/summaries/stage12094_separate_head_or_two_phase_candidate_next_action_ablation_design.json'
INIT_RUNTIME = REPO / 'runs/local/artifacts/stage11924_transition_listwise_head_only_probe/runtime_model/runtime_model_bundle.json'
PRESERVE_RUNTIME = REPO / 'runs/local/artifacts/stage11507_preservation_strengthened_evidence_judgment_probe/runtime_model/runtime_model_bundle.json'
RUNTIME_DIR = REPO / 'runs/local/artifacts/stage12096_candidate_head_only_candidate_selection_probe/runtime_model'
OUTPUT_DIR = REPO / 'runs/local/artifacts/stage12096_candidate_head_only_candidate_selection_probe/bounded_decoder_probe'
TRAIN_SCRIPT = REPO / 'legacy_src/scripts/train_agentkernel_lite_encdec.py'
MODEL_CONFIG = REPO / 'configs/model/agentkernel_100m_seq2seq_recovered_target.json'
TOKENIZER_JSON = REPO / 'configs/tokenizer/agentkernel_bpe_1506/tokenizer.json'
TOKENIZER_CONFIG = REPO / 'configs/tokenizer/agentkernel_bpe_1506/tokenizer_config.json'
TOKENIZER_HASHLOCK = REPO / 'configs/tokenizer/agentkernel_bpe_1506_recovered_pointer.json'


def rel(path: Path) -> str:
    return str(path.relative_to(REPO))


def read_json(path: Path) -> Any:
    return json.loads(path.read_text())


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + '\n')


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('w') as f:
        for row in rows:
            f.write(json.dumps(row, sort_keys=True) + '\n')


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
    out['stage12095_candidate_head_candidate_selection_support'] = True
    out['row_id'] = f"{out['row_id']}::stage12095_candidate_head_support::{index}"
    loss_mask = dict(out.get('loss_mask') or {})
    loss_mask.update({'bounded_choice_aux': True, 'transition_candidate_head_only': True})
    out['loss_mask'] = loss_mask
    return out


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    SUMMARIES.mkdir(parents=True, exist_ok=True)
    design = read_json(DESIGN)
    base = read_jsonl(BASE_MANIFEST)
    repair_all = read_jsonl(REPAIR_ROWS)
    repair = [row for row in repair_all if row.get('task_type') == 'transition_candidate_selection']

    old_train = [r for r in base if split_of(r) == 'train']
    eval_rows = [r for r in base if split_of(r) == 'eval']
    strict_rows = [r for r in base if split_of(r) == 'strict_eval']

    replay = []
    for row in old_train:
        out = dict(row)
        out['stage12095_replay_source'] = 'stage11923_transition_listwise_head_only_manifest'
        out['row_id'] = f"{out['row_id']}::stage12095_old640_replay"
        replay.append(out)

    repair_rows = [prep_repair(row, index + 1) for index, row in enumerate(repair)]
    manifest_rows = replay + repair_rows + eval_rows + strict_rows
    write_jsonl(MANIFEST, manifest_rows)

    counts = collections.Counter(split_of(row) for row in manifest_rows)
    train = replay + repair_rows
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
        '--max-steps', '256',
        '--batch-size', '8',
        '--learning-rate', '7.5e-5',
        '--max-encoder-tokens', '768',
        '--max-decoder-tokens', '16',
        '--decoder-ce-weight', '0.0',
        '--bounded-choice-aux-weight', '3.0',
        '--bounded-choice-root-group-aux-weight', '0.0',
        '--bounded-choice-aux-source', 'encoder_option_retrieval_transition_candidate_head',
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

    option_mirror_missing = sum(1 for row in train if row.get('opaque_options') and not row.get('standalone_projection_source', {}).get('opaque_options'))
    unsafe_loss = sum(1 for row in train if not any((row.get('loss_mask') or {}).values()))
    gates = {
        'stage12094_allows_request': design['recommended_immediate_next_stage']['allowed_to_build_request'] is True,
        'base_manifest_exists': BASE_MANIFEST.exists(),
        'repair_rows_exists': REPAIR_ROWS.exists(),
        'init_runtime_exists': INIT_RUNTIME.exists(),
        'preserve_runtime_exists': PRESERVE_RUNTIME.exists(),
        'splits_expected': counts == {'train': 725, 'eval': 22, 'strict_eval': 22},
        'old_replay_640': len(replay) == 640,
        'candidate_selection_repair_rows_85': len(repair_rows) == 85,
        'no_next_action_repair_rows': all(row.get('task_type') == 'transition_candidate_selection' for row in repair_rows),
        'option_mirror_missing_zero': option_mirror_missing == 0,
        'unsafe_loss_zero': unsafe_loss == 0,
        'uses_gpu2_mask': 'CUDA_VISIBLE_DEVICES=2' in command and 'NVIDIA_VISIBLE_DEVICES=2' in command,
        'head_only_enabled': '--bounded-choice-train-head-only' in command,
        'transition_candidate_head_selected': 'encoder_option_retrieval_transition_candidate_head' in command,
    }
    passed = all(gates.values())
    summary = {
        'stage': STAGE,
        'stage_name': NAME,
        'created_at_utc': dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace('+00:00', 'Z'),
        'decision': 'candidate_head_only_candidate_selection_request_ready' if passed else 'candidate_head_only_candidate_selection_request_blocked',
        'passed': passed,
        'execute_now': False,
        'hypothesis': 'Candidate-selection repair should be tested on a transition-specific head without mixing next-action repair rows into the same scorer update.',
        'row_counts': {
            'train_rows': counts['train'],
            'old_replay_rows': len(replay),
            'candidate_selection_repair_rows': len(repair_rows),
            'eval_rows': counts['eval'],
            'strict_rows': counts['strict_eval'],
            'repair_subpacket_counts': dict(collections.Counter(row.get('stage12088_subpacket') for row in repair_rows)),
            'repair_target_counts': dict(collections.Counter(target_value(row) for row in repair_rows)),
            'option_mirror_missing': option_mirror_missing,
            'unsafe_loss': unsafe_loss,
        },
        'gates_before_execution': gates,
        'training_controls': {
            'gpu': 'cuda:2 only',
            'init_runtime': rel(INIT_RUNTIME),
            'preservation_reference_runtime': rel(PRESERVE_RUNTIME),
            'max_steps': 256,
            'learning_rate': '7.5e-5',
            'aux_source': 'encoder_option_retrieval_transition_candidate_head',
            'head_only': True,
            'sampler': 'task_balanced',
        },
        'postrun_gate': design['postrun_gate_for_stage12095'],
        'outputs': {
            'summary': rel(SUMMARY),
            'summary_mirror': rel(MIRROR),
            'manifest': rel(MANIFEST),
            'command': rel(COMMAND_JSON),
            'runtime_dir': rel(RUNTIME_DIR),
            'output_dir': rel(OUTPUT_DIR),
        },
        'source_artifacts': {
            'stage12094_design': rel(DESIGN),
            'base_manifest': rel(BASE_MANIFEST),
            'repair_rows': rel(REPAIR_ROWS),
        },
        'next_stage_if_executed': 'stage12096_candidate_head_only_candidate_selection_probe',
        'next_stage_after_execution': 'stage12097_candidate_head_only_candidate_selection_postrun_audit',
    }
    write_json(SUMMARY, summary)
    write_json(MIRROR, summary)
    print(json.dumps({'passed': passed, 'manifest_rows': len(manifest_rows), 'train_rows': counts['train'], 'summary': rel(SUMMARY)}, indent=2))


if __name__ == '__main__':
    main()
