from __future__ import annotations

import importlib
import sys
from pathlib import Path

import pytest

pytest.importorskip('torch.nn.functional')


def _load():
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / 'legacy_src'))
    return importlib.import_module('agentkernel_lite.training_loop')


def test_structured_best_state_metrics_uses_eval_only():
    mod = _load()
    exact_sum, loss_sum = mod._structured_best_state_metrics(
        {'joint_proxy_exact': 0.375, 'loss': 1.9},
        {'joint_proxy_exact': 0.375, 'loss': 2.1},
    )
    assert exact_sum == 0.375
    assert loss_sum == 1.9


def test_structured_best_state_selection_prefers_higher_exact_before_lower_loss():
    mod = _load()
    baseline_exact, baseline_loss = mod._structured_best_state_metrics(
        {'joint_proxy_exact': 0.375, 'loss': 1.0},
        {'joint_proxy_exact': 0.99, 'loss': 0.01},
    )
    better_exact, worse_loss = mod._structured_best_state_metrics(
        {'joint_proxy_exact': 0.5, 'loss': 9.0},
        {'joint_proxy_exact': 0.0, 'loss': 99.0},
    )
    tied_exact, better_loss = mod._structured_best_state_metrics(
        {'joint_proxy_exact': 0.375, 'loss': 0.9},
        {'joint_proxy_exact': 0.0, 'loss': 99.0},
    )
    assert better_exact > baseline_exact
    assert worse_loss > baseline_loss
    assert tied_exact == baseline_exact
    assert better_loss < baseline_loss


def test_strict_metrics_cannot_change_selection_metrics():
    mod = _load()
    eval_record = {'joint_proxy_exact': 0.4, 'loss': 1.25}
    weak_strict = {'joint_proxy_exact': 0.0, 'loss': 100.0}
    strong_strict = {'joint_proxy_exact': 1.0, 'loss': 0.0}
    assert mod._structured_best_state_metrics(eval_record, weak_strict) == mod._structured_best_state_metrics(eval_record, strong_strict)
