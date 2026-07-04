from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

AUTHORITY_CLOSED = {
    "model_execution_authorized_next": False,
    "decoder_ce_training_authorized_next": False,
    "runtime_authorized": False,
    "source_emission_authorized": False,
    "body_emission_authorized": False,
    "gemma_execution_authorized_next": False,
    "harness_execution_authorized_next": False,
    "scoring_authorized_next": False,
    "controller_complete_merge_authorized_next": False,
    "promotion_ready": False,
}


def load_json(path: Path) -> dict[str, Any]:
    value=json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(value, dict):
        raise ValueError(f'not object: {path}')
    return value


def build_plan(args: argparse.Namespace) -> dict[str, Any]:
    model=load_json(args.model_config)
    tokenizer=load_json(args.tokenizer_config)
    manifests=[str(p) for p in args.manifest]
    losses={
        'structured_aux_weight': args.structured_aux_weight,
        'decoder_ce_weight': args.decoder_ce_weight,
        'denoise_weight': args.denoise_weight,
        'runtime_reward_weight': 0.0,
    }
    return {
        'plan_name': args.plan_name,
        'model_config': str(args.model_config),
        'tokenizer_config': str(args.tokenizer_config),
        'model_summary': {
            'parameter_target': model.get('parameter_target') or model.get('target_parameters') or '100m',
            'architecture': model.get('architecture') or model.get('model_type') or 'seq2seq',
            'structured_heads': model.get('structured_heads') or model.get('heads') or [],
        },
        'tokenizer_summary': {
            'tokenizer_type': tokenizer.get('tokenizer_type') or tokenizer.get('type') or 'byte',
            'max_decoder_tokens': args.max_decoder_tokens,
        },
        'manifests': manifests,
        'mode': args.mode,
        'caps': {
            'max_train_rows': args.max_train_rows,
            'max_eval_rows': args.max_eval_rows,
            'max_strict_rows': args.max_strict_rows,
            'max_steps': args.max_steps,
            'batch_size': args.batch_size,
            'max_decoder_tokens': args.max_decoder_tokens,
        },
        'losses': losses,
        'required_audits': [
            'authority_gate',
            'loss_mask_card',
            'shortcut_or_route_audit',
            'final_pre_execution_audit',
            'telemetry_artifact_contract',
        ],
        'required_telemetry': [
            'loss_by_step.jsonl',
            'eval_loss_by_checkpoint.jsonl',
            'row_field_logits.jsonl',
            'row_field_losses.jsonl',
            'row_token_loss.jsonl',
            'module_delta_norms.json',
            'failure_bucket_card.json',
            'cleanup_proof.json',
        ],
        'execution_authorized': False,
        'authority': dict(AUTHORITY_CLOSED),
        'next_best_step': 'audit this training plan before any trainer execution implementation is used',
    }


def parse_args() -> argparse.Namespace:
    p=argparse.ArgumentParser(description='Build a non-executing training plan contract.')
    p.add_argument('--plan-name', default='reconstructed_training_plan')
    p.add_argument('--mode', default='bounded_decoder_ce_probe')
    p.add_argument('--model-config', type=Path, default=Path('configs/model/agentkernel_100m_seq2seq.json'))
    p.add_argument('--tokenizer-config', type=Path, default=Path('configs/tokenizer/byte_tokenizer.json'))
    p.add_argument('--manifest', type=Path, action='append', required=True)
    p.add_argument('--max-train-rows', type=int, default=32)
    p.add_argument('--max-eval-rows', type=int, default=16)
    p.add_argument('--max-strict-rows', type=int, default=16)
    p.add_argument('--max-steps', type=int, default=16)
    p.add_argument('--batch-size', type=int, default=2)
    p.add_argument('--max-decoder-tokens', type=int, default=768)
    p.add_argument('--structured-aux-weight', type=float, default=0.0)
    p.add_argument('--decoder-ce-weight', type=float, default=0.0)
    p.add_argument('--denoise-weight', type=float, default=0.0)
    p.add_argument('--output', type=Path, required=True)
    return p.parse_args()


def main() -> None:
    args=parse_args()
    plan=build_plan(args)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(plan, indent=2, sort_keys=True)+'\n', encoding='utf-8')
    print(json.dumps(plan, indent=2, sort_keys=True))

if __name__ == '__main__':
    main()
