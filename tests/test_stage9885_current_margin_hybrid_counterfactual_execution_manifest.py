from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load():
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / 'scripts'))
    path = root / 'scripts/build_stage9885_current_margin_hybrid_counterfactual_execution_manifest.py'
    spec = importlib.util.spec_from_file_location('stage9885', path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_stage9885_builds_hybrid_manifest_with_strict_anchors_for_k_and_t():
    mod = _load()
    rows = mod.build_rows()
    audit = mod.build_audit(rows)
    assert audit['passed'] is True
    assert audit['rows'] == 48
    assert audit['split_counts'] == {'eval': 16, 'strict_eval': 16, 'train': 16}
    assert audit['kept_obligations']['POSITIVE_ORIGINAL_STRICT_ANCHOR'] == 8
    assert audit['kept_obligations']['MIXED_REPLAY'] == 8
    assert audit['strict_label_balance'] == {'K': 4, 'M': 4, 'R': 4, 'T': 4}


def test_stage9885_strict_eval_uses_clean_anchors_for_k_t_and_mixed_for_m_r():
    mod = _load()
    rows = mod.build_rows()
    strict = [row for row in rows if row['split'] == 'strict_eval']
    by_label = {}
    for row in strict:
        by_label.setdefault(row['target']['decoder_text'], set()).add(row['obligation_type'])
    assert by_label['K'] == {'POSITIVE_ORIGINAL_STRICT_ANCHOR'}
    assert by_label['T'] == {'POSITIVE_ORIGINAL_STRICT_ANCHOR'}
    assert by_label['M'] == {'MIXED_REPLAY'}
    assert by_label['R'] == {'MIXED_REPLAY'}
