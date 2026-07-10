from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

torch = pytest.importorskip('torch')
pytest.importorskip('torch.nn.functional')


def _load():
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / 'legacy_src'))
    path = root / 'legacy_src/agentkernel_lite/training_loop.py'
    spec = importlib.util.spec_from_file_location('stage_structured_margin_training_loop', path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules['stage_structured_margin_training_loop'] = module
    spec.loader.exec_module(module)
    return module


def test_structured_margin_loss_zero_when_target_beats_rest_by_margin():
    mod = _load()
    logits = torch.tensor([[1.0, 0.8, -0.1]], dtype=torch.float32)
    targets = torch.tensor([0], dtype=torch.long)
    loss = mod._structured_margin_loss(logits, targets, margin=0.1)
    assert torch.isclose(loss, torch.tensor(0.0))


def test_structured_margin_loss_positive_when_hardest_negative_beats_target():
    mod = _load()
    logits = torch.tensor([[0.2, 0.4, -0.1]], dtype=torch.float32)
    targets = torch.tensor([0], dtype=torch.long)
    loss = mod._structured_margin_loss(logits, targets, margin=0.05)
    assert loss.item() > 0.0


def test_structured_field_loss_exceeds_ce_when_margin_violated():
    mod = _load()
    logits = torch.tensor([[0.2, 0.4, -0.1]], dtype=torch.float32)
    targets = torch.tensor([0], dtype=torch.long)
    ce = torch.nn.functional.cross_entropy(logits, targets)
    combined = mod._structured_field_loss(logits, targets)
    assert combined.item() > ce.item()
