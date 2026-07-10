from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path


def _load():
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root))
    sys.path.insert(0, str(root / 'scripts'))
    path = root / 'scripts/build_stage9873_edit_localization_field_attention_margin_gemma_comparison.py'
    spec = importlib.util.spec_from_file_location('stage9873_cmp', path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules['stage9873_cmp'] = module
    spec.loader.exec_module(module)
    return module


def test_stage9873_build_audit_dry_run_shapes_results():
    mod = _load()
    audit, rows = mod.build_audit(execute_gemma=False)
    assert audit['passed'] is True
    assert audit['gemma_executed'] is False
    assert set(audit['splits']) == {'eval', 'strict_eval'}
    assert len(audit['comparisons']) == 8
    assert len(rows) == 32
    first = rows[0]
    assert first['raw_output'] == '[dry-run]'
    assert first['split'] in {'eval', 'strict_eval'}


def test_stage9873_uses_stage9872_model_rows_path():
    mod = _load()
    assert 'stage9872_edit_localization_field_attention_margin_best_state_target_100m_probe' in str(mod.MODEL_ROWS)
    assert 'stage9867_edit_localization_label_identity_probe' in str(mod.MANIFEST)
