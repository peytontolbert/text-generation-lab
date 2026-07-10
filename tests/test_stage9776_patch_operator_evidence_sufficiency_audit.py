from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load():
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / 'scripts'))
    path = root / 'scripts/build_stage9776_patch_operator_evidence_sufficiency_audit.py'
    spec = importlib.util.spec_from_file_location('stage9776', path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_stage9776_finds_patch_operator_safe_evidence_collapse():
    mod = _load()
    audit = mod.build_audit()
    assert audit['passed'] is True
    assert audit['bucket_count'] == 12
    assert audit['baseline_surface_collapsed_bucket_count'] == 12
    assert audit['collapsed_safe_bucket_count'] == 12
    assert audit['separable_only_with_leaky_fields_bucket_count'] == 12
