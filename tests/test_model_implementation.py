from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

torch = pytest.importorskip("torch")

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'legacy_src'))

from agentkernel_lite import AgentKernelLiteConfig, AgentKernelLiteSeq2Seq, build_batch

AUDIT = ROOT / 'scripts' / 'audit_model_implementation.py'


def sample_rows():
    return [
        {
            'row_id': 'r1',
            'split': 'train',
            'language_family': 'python',
            'route': 'KEEP_BOUNDED_DECODER',
            'surface': 'REPAIR_PLAN_ARGS',
            'input_state': {'evidence_state': 'direct_present'},
            'target': {'target_ref': 'target_ref::r1'},
            'decoder_token_len': 32,
            'loss_mask': {'decoder_ce': True},
            'authority': {},
        }
    ]


def test_model_forward_and_decoder_loss_smoke() -> None:
    batch = build_batch(sample_rows(), max_encoder_tokens=64, max_decoder_tokens=32)
    model = AgentKernelLiteSeq2Seq(AgentKernelLiteConfig(hidden_size=32, num_layers=1))
    out = model(batch.input_ids, batch.decoder_input_ids)
    loss = model.decoder_ce_loss(out['decoder_logits'], batch.labels, batch.loss_mask['decoder_ce'])
    assert out['decoder_logits'].shape[:2] == batch.labels.shape
    assert out['structured_logits']
    assert torch.isfinite(loss)


def test_model_implementation_audit_passes(tmp_path: Path) -> None:
    manifest = tmp_path / 'rows.jsonl'
    manifest.write_text('\n'.join(json.dumps(row) for row in sample_rows()) + '\n', encoding='utf-8')
    out = tmp_path / 'audit.json'
    subprocess.run([sys.executable, str(AUDIT), '--manifest', str(manifest), '--output', str(out)], check=True, text=True, capture_output=True)
    card = json.loads(out.read_text())
    assert card['passed'] is True
    assert card['training_attempted'] is False
    assert card['optimizer_step_attempted'] is False
