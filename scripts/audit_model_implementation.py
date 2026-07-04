from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT / 'legacy_src') not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / 'legacy_src'))
if str(REPO_ROOT / 'scripts') not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / 'scripts'))

from stage_summary_schema import AUTHORITY_KEYS


def read_jsonl(path: Path, limit: int) -> list[dict]:
    rows=[]
    for line in path.read_text(encoding='utf-8').splitlines():
        if line.strip():
            rows.append(json.loads(line))
            if len(rows) >= limit:
                break
    return rows


def audit(args: argparse.Namespace) -> dict:
    errors=[]
    gates={}
    try:
        import torch
        from agentkernel_lite import AgentKernelLiteConfig, AgentKernelLiteSeq2Seq, build_batch
        gates['torch_import_ok']=True
    except Exception as exc:
        return {'passed': False, 'errors': [f'import failed: {exc}'], 'gates': {'torch_import_ok': False}, 'authority': {k: False for k in AUTHORITY_KEYS}}
    rows=read_jsonl(args.manifest, args.rows)
    gates['rows_loaded']=bool(rows)
    if not rows:
        errors.append('no rows loaded')
    config_payload=json.loads(args.model_config.read_text(encoding='utf-8')) if args.model_config.is_file() else {}
    config=AgentKernelLiteConfig.from_json(config_payload)
    model=AgentKernelLiteSeq2Seq(config)
    model.eval()
    batch=build_batch(rows, max_encoder_tokens=args.max_encoder_tokens, max_decoder_tokens=args.max_decoder_tokens)
    with torch.no_grad():
        out=model(batch.input_ids, batch.decoder_input_ids)
        loss=model.decoder_ce_loss(out['decoder_logits'], batch.labels, batch.loss_mask.get('decoder_ce'))
    gates['decoder_logits_shape_ok']=tuple(out['decoder_logits'].shape[:2]) == tuple(batch.labels.shape)
    gates['structured_logits_present']=bool(out['structured_logits'])
    gates['loss_is_finite']=bool(torch.isfinite(loss).item())
    gates['optimizer_step_attempted']=False
    gates['checkpoint_written']=False
    if not gates['decoder_logits_shape_ok']:
        errors.append('decoder logits shape mismatch')
    if not gates['structured_logits_present']:
        errors.append('structured logits missing')
    if not gates['loss_is_finite']:
        errors.append('loss is not finite')
    return {
        'passed': not errors,
        'errors': errors,
        'gates': gates,
        'rows': len(rows),
        'input_shape': list(batch.input_ids.shape),
        'decoder_input_shape': list(batch.decoder_input_ids.shape),
        'label_shape': list(batch.labels.shape),
        'decoder_logits_shape': list(out['decoder_logits'].shape),
        'structured_head_count': len(out['structured_logits']),
        'loss_value': float(loss.item()),
        'model_execution_kind': 'forward_loss_smoke_no_grad_no_optimizer',
        'optimizer_step_attempted': False,
        'training_attempted': False,
        'authority': {k: False for k in AUTHORITY_KEYS},
        'next_best_step': 'wire model implementation into trainer only behind explicit tiny execution authorization',
    }


def parse_args() -> argparse.Namespace:
    p=argparse.ArgumentParser(description='Audit recovered model implementation interfaces without training.')
    p.add_argument('--manifest', type=Path, required=True)
    p.add_argument('--model-config', type=Path, default=Path('configs/model/agentkernel_100m_seq2seq.json'))
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--rows', type=int, default=4)
    p.add_argument('--max-encoder-tokens', type=int, default=128)
    p.add_argument('--max-decoder-tokens', type=int, default=128)
    return p.parse_args()


def main() -> None:
    args=parse_args()
    card=audit(args)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(card, indent=2, sort_keys=True)+'\n', encoding='utf-8')
    print(json.dumps(card, indent=2, sort_keys=True))
    raise SystemExit(0 if card['passed'] else 1)

if __name__ == '__main__':
    main()
