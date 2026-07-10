from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load():
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root))
    sys.path.insert(0, str(root / 'scripts'))
    path = root / 'scripts/build_stage9876_margin_objective_structured_tiny_execution_review.py'
    spec = importlib.util.spec_from_file_location('stage9876_mod', path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules['stage9876_mod'] = module
    spec.loader.exec_module(module)
    return module


def test_stage9876_sources_stage9875_manifests():
    mod = _load()
    assert 'stage9875_margin_objective_target_100m_contract_only_preflight' in str(mod.SOURCE_SUMMARY)
    assert 'stage9875_margin_objective_target_100m_contract_only_preflight/manifests' in str(mod.SOURCE_MANIFEST_DIR)
    assert set(mod.SURFACES) == {'symbol_binding', 'edit_localization', 'patch_operator_selection', 'verifier_failure_repair_or_abstain'}
