from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load():
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / 'scripts'))
    path = root / 'scripts/build_stage9847_counterfactual_curriculum_manifest.py'
    spec = importlib.util.spec_from_file_location('stage9847', path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_stage9847_constants_match_expected_curriculum():
    mod = _load()
    assert mod.TRAIN_ROOTS_PER_LANG == 3
    assert mod.TRAIN_ROLES == ['positive_original', 'mixed_replay', 'evidence_removed', 'contradictory_evidence']
    assert mod.EVAL_ROLE == 'evidence_removed'
    assert mod.STRICT_ROLE == 'contradictory_evidence'

