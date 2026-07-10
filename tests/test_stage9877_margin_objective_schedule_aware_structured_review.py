from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load():
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root))
    sys.path.insert(0, str(root / 'scripts'))
    path = root / 'scripts/build_stage9877_margin_objective_schedule_aware_structured_review.py'
    spec = importlib.util.spec_from_file_location('stage9877_mod', path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules['stage9877_mod'] = module
    spec.loader.exec_module(module)
    return module


def test_stage9877_gives_edit_localization_longer_best_state_schedule():
    mod = _load()
    edit = mod.SURFACES['edit_localization']
    symbol = mod.SURFACES['symbol_binding']
    assert edit['max_steps'] == 32
    assert edit['eval_interval'] == 1
    assert edit['restore_best'] is True
    assert symbol['max_steps'] == 8
    assert symbol['restore_best'] is False
