from __future__ import annotations

import importlib
import sys
from pathlib import Path

import torch


def _load():
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / 'legacy_src'))
    return importlib.import_module('agentkernel_lite.training_loop')


def test_field_telemetry_ignores_surplus_logits_outside_active_vocab():
    mod = _load()
    inverse = {0: 'K', 1: 'M', 2: 'R', 3: 'T', 4: 'Z'}
    logits = torch.tensor([0.4, 0.3, 0.2, 0.1, 0.0, 9.0, 8.0], dtype=torch.float32)
    record = mod._field_telemetry_record(
        row_id='row-1',
        split='eval',
        field='edit_localization',
        target='K',
        logits=logits,
        inverse=inverse,
    )
    assert record['pred'] == 'K'
    assert record['pred_index'] == 0
    assert all(item['label'] in inverse.values() for item in record['top_k'])
    assert all(item['label'] not in {'5', '6'} for item in record['top_k'])
