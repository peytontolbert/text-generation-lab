#!/usr/bin/env python3
from __future__ import annotations

import json
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
STAGE = 'stage12159_selected_test_counterfactual_expansion_training_request'
OUT = REPO / 'runs/local/artifacts' / STAGE
SUMMARY = REPO / 'runs/summaries' / f'{STAGE}.json'
BASE = REPO / 'runs/local/artifacts/stage11923_transition_listwise_head_only_probe_request/transition_listwise_head_only_manifest.jsonl'
EXPANSION = REPO / 'runs/local/artifacts/stage12155_selected_test_counterfactual_expansion_package/expanded_counterfactual_rows.jsonl'
MERGED = OUT / 'selected_test_counterfactual_expansion_training_manifest.jsonl'
COMMAND_JSON = OUT / 'training_command.json'
REQUEST_JSON = OUT / 'training_request.json'
RUNTIME_OUT = REPO / 'runs/local/artifacts/stage12160_selected_test_counterfactual_expansion_training_probe/runtime_model'
PROBE_OUT = REPO / 'runs/local/artifacts/stage12160_selected_test_counterfactual_expansion_training_probe/bounded_decoder_probe'


def load_jsonl(path: Path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def write_json(path: Path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, sort_keys=True) + '\n')


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    base_rows = load_jsonl(BASE)
    expansion_rows = load_jsonl(EXPANSION)

    base_ids = {r.get('row_id') for r in base_rows}
    duplicate_expansion = [r.get('row_id') for r in expansion_rows if r.get('row_id') in base_ids]
    if duplicate_expansion:
        raise SystemExit(f'duplicate row ids in expansion: {duplicate_expansion[:5]}')

    for row in expansion_rows:
        if row.get('split') != 'train' or row.get('strict_eval_eligible') is True or row.get('training_allowed') is True:
            raise SystemExit(f'bad expansion row split/flags: {row.get("row_id")}')

    merged_rows = base_rows + expansion_rows
    MERGED.write_text('\n'.join(json.dumps(row, sort_keys=True) for row in merged_rows) + '\n')

    split_counts = Counter(r.get('split') or r.get('package_split') for r in merged_rows)
    train_count = split_counts.get('train', 0)
    eval_count = split_counts.get('eval', 0)
    strict_count = split_counts.get('strict_eval', 0)
    lang_counts = Counter(r.get('language_family') for r in merged_rows if (r.get('split') or r.get('package_split')) == 'train')
    task_counts = Counter(r.get('task_type') for r in merged_rows if (r.get('split') or r.get('package_split')) == 'train')

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
        'conda', 'run', '-n', 'trellis',
        'python', str(REPO / 'legacy_src/scripts/train_agentkernel_lite_encdec.py'),
        '--repo-root', str(REPO),
        '--manifest', str(MERGED),
        '--mode', 'bounded_decoder_ce_probe',
        '--probe-scale', 'target_100m',
        '--implementation', 'transformer',
        '--model-config', str(REPO / 'configs/model/agentkernel_100m_seq2seq_recovered_target.json'),
        '--tokenizer-json', str(REPO / 'configs/tokenizer/agentkernel_bpe_1506/tokenizer.json'),
        '--tokenizer-config', str(REPO / 'configs/tokenizer/agentkernel_bpe_1506/tokenizer_config.json'),
        '--tokenizer-hashlock', str(REPO / 'configs/tokenizer/agentkernel_bpe_1506_recovered_pointer.json'),
        '--execution-authorized-for-recovery-probe',
        '--max-train-rows', str(train_count),
        '--max-eval-rows', str(eval_count),
        '--max-strict-rows', str(strict_count),
        '--max-steps', '256',
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
        '--bounded-choice-contrast-weight', '0.3',
        '--bounded-choice-contrast-margin', '0.08',
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
        '--runtime-model-save-dir', str(RUNTIME_OUT),
        '--initialize-from-runtime-model', str(REPO / 'runs/local/artifacts/stage11924_transition_listwise_head_only_probe/runtime_model/runtime_model_bundle.json'),
        '--preservation-reference-runtime-model', str(REPO / 'runs/local/artifacts/stage11507_preservation_strengthened_evidence_judgment_probe/runtime_model/runtime_model_bundle.json'),
        '--preservation-kl-weight', '4.0',
        '--no-final-checkpoint-export',
        '--output-dir', str(PROBE_OUT),
    ]

    request = {
        'stage': STAGE,
        'created_at_utc': datetime.now(UTC).replace(microsecond=0).isoformat().replace('+00:00', 'Z'),
        'decision': 'request_only_ready_for_guarded_stage12160_execution',
        'execute_now': False,
        'merged_manifest': str(MERGED.relative_to(REPO)),
        'base_manifest': str(BASE.relative_to(REPO)),
        'expansion_manifest': str(EXPANSION.relative_to(REPO)),
        'base_rows': len(base_rows),
        'expansion_rows': len(expansion_rows),
        'total_rows': len(merged_rows),
        'split_counts': dict(sorted(split_counts.items())),
        'train_language_counts': dict(sorted(lang_counts.items())),
        'train_task_counts': dict(sorted(task_counts.items())),
        'duplicate_expansion_row_ids': duplicate_expansion,
        'gpu_policy': {
            'CUDA_VISIBLE_DEVICES': '2',
            'NVIDIA_VISIBLE_DEVICES': '2',
            'AGENTKERNEL_TRAIN_DEVICE': 'cuda:0',
            'AGENTKERNEL_EVAL_DEVICE': 'cuda:0',
            'physical_gpu_allowed': '2_only',
        },
        'training_allowed_by_request': False,
        'promotion_eligible': False,
        'claim_boundary': 'Diagnostic training request only. Promotion requires postrun audits versus Stage11924, Stage12099 route, protected compact gates, and source-heldout smoke.',
        'command_json': str(COMMAND_JSON.relative_to(REPO)),
        'runtime_output': str(RUNTIME_OUT.relative_to(REPO)),
        'probe_output': str(PROBE_OUT.relative_to(REPO)),
        'postrun_required_stage': 'stage12161_selected_test_counterfactual_expansion_training_postrun_audit',
    }
    write_json(COMMAND_JSON, command)
    write_json(REQUEST_JSON, request)
    write_json(OUT / 'summary.json', request)
    write_json(SUMMARY, request)
    print(json.dumps(request, indent=2, sort_keys=True))


if __name__ == '__main__':
    main()
