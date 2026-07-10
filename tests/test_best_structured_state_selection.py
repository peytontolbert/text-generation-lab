from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

pytest.importorskip('torch.nn.functional')


def _load():
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / 'legacy_src'))
    path = root / 'legacy_src/agentkernel_lite/training_loop.py'
    spec = importlib.util.spec_from_file_location('stage_best_structured_state_training_loop', path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules['stage_best_structured_state_training_loop'] = module
    spec.loader.exec_module(module)
    return module


def test_structured_best_state_metrics_returns_exact_and_loss_sums():
    mod = _load()
    exact_sum, loss_sum = mod._structured_best_state_metrics(
        {'joint_proxy_exact': 0.375, 'loss': 1.9},
        {'joint_proxy_exact': 0.375, 'loss': 2.1},
    )
    assert exact_sum == 0.75
    assert loss_sum == 4.0


def test_structured_best_state_selection_prefers_higher_exact_before_lower_loss():
    mod = _load()
    baseline_exact, baseline_loss = mod._structured_best_state_metrics(
        {'joint_proxy_exact': 0.375, 'loss': 1.0},
        {'joint_proxy_exact': 0.375, 'loss': 1.0},
    )
    better_exact, worse_loss = mod._structured_best_state_metrics(
        {'joint_proxy_exact': 0.5, 'loss': 9.0},
        {'joint_proxy_exact': 0.5, 'loss': 9.0},
    )
    tied_exact, better_loss = mod._structured_best_state_metrics(
        {'joint_proxy_exact': 0.375, 'loss': 0.9},
        {'joint_proxy_exact': 0.375, 'loss': 0.8},
    )
    assert better_exact > baseline_exact
    assert worse_loss > baseline_loss
    assert tied_exact == baseline_exact
    assert better_loss < baseline_loss
